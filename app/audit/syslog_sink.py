from __future__ import annotations

import json
import socket
import syslog
from datetime import datetime, timezone
from typing import Any

from .config import AuditConfig


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _json_default(value: Any) -> str:
    return repr(value)


def prepare_event_payload(event: dict[str, Any], max_bytes: int) -> tuple[str, bool]:
    """Return JSON payload and whether the event/result had to be truncated."""
    payload = json.dumps(event, default=_json_default, separators=(",", ":"), sort_keys=True)
    if len(payload.encode("utf-8")) <= max_bytes:
        return payload, False

    compact = dict(event)
    result_json = json.dumps(compact.get("result"), default=_json_default, separators=(",", ":"), sort_keys=True)
    preview_bytes = max(256, max_bytes // 3)
    preview = result_json.encode("utf-8")[:preview_bytes].decode("utf-8", errors="replace")
    compact["result"] = {
        "truncated": True,
        "original_size_bytes": len(result_json.encode("utf-8")),
        "preview": preview,
    }
    compact["result_truncated"] = True

    payload = json.dumps(compact, default=_json_default, separators=(",", ":"), sort_keys=True)
    if len(payload.encode("utf-8")) <= max_bytes:
        return payload, True

    # Last-resort truncation for very large argument/error fields.
    trimmed = payload.encode("utf-8")[:max_bytes].decode("utf-8", errors="replace")
    fallback = {
        "event_type": compact.get("event_type", "mcp_tool_call"),
        "timestamp": compact.get("timestamp", _utc_timestamp()),
        "server": compact.get("server", "prcmcp"),
        "environment": compact.get("environment", "unknown"),
        "tool": compact.get("tool", "unknown"),
        "success": compact.get("success", False),
        "result_truncated": True,
        "message_truncated": True,
        "preview": trimmed,
    }
    return json.dumps(fallback, default=_json_default, separators=(",", ":"), sort_keys=True), True


def send_syslog_json(event: dict[str, Any], config: AuditConfig | None = None) -> bool:
    """Send an audit event to LogRhythm via UDP syslog.

    Returns False on best-effort delivery failure. Tool execution should never
    fail only because audit delivery failed.
    """
    config = config or AuditConfig.from_env()
    if not config.enabled:
        return True

    payload, truncated = prepare_event_payload(event, config.max_event_bytes)
    if truncated:
        try:
            event["result_truncated"] = True
        except Exception:
            pass

    # RFC3164-ish syslog frame with JSON payload for SIEM parsing.
    frame = f"<{syslog.LOG_AUTH | syslog.LOG_INFO}>{_utc_timestamp()} {config.server_name} prcmcp-audit: {payload}"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(frame.encode("utf-8"), (config.syslog_host, config.syslog_port))
        return True
    except OSError:
        return False
