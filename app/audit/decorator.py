from __future__ import annotations

import inspect
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar, cast

from .config import AuditConfig
from .redaction import redact
from .syslog_sink import send_syslog_json

F = TypeVar("F", bound=Callable[..., Any])
LOGGER = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bound_arguments(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        signature = inspect.signature(func)
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except Exception:
        return {"args": args, "kwargs": kwargs}


def _logical_success(result: Any) -> bool:
    if isinstance(result, dict):
        if result.get("ok") is False:
            return False
        if "error" in result and result.get("error"):
            return False
    return True


def _emit_event(event: dict[str, Any], config: AuditConfig) -> None:
    delivered = send_syslog_json(event, config)
    print(
        "AUDIT_SYSLOG_ATTEMPT "
        f"tool={event.get('tool', 'unknown')} "
        f"success={event.get('success', False)} "
        f"delivered={delivered} "
        f"truncated={event.get('result_truncated', False)} "
        f"destination={config.syslog_host}:{config.syslog_port}",
        flush=True,
    )
    if not delivered:
        LOGGER.warning("failed to send audit event to syslog", extra={"tool": event.get("tool")})


def audit_tool(func: F) -> F:
    """Audit an MCP tool call to LogRhythm syslog without blocking the tool."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        config = AuditConfig.from_env()
        if not config.enabled:
            return func(*args, **kwargs)

        started = time.perf_counter()
        arguments = _bound_arguments(func, args, kwargs)
        base_event: dict[str, Any] = {
            "event_type": "mcp_tool_call",
            "timestamp": _timestamp(),
            "server": config.server_name,
            "environment": config.environment,
            "user": str(arguments.pop("audit_user", "unknown") or "unknown"),
            "source": str(arguments.pop("audit_source", "unknown") or "unknown"),
            "tool": func.__name__,
            "arguments": redact(arguments),
        }

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            event = {
                **base_event,
                "success": False,
                "duration_ms": duration_ms,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "result": None,
                "result_truncated": False,
            }
            _emit_event(redact(event), config)
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        event = {
            **base_event,
            "success": _logical_success(result),
            "duration_ms": duration_ms,
            "result": redact(result) if config.log_full_results else None,
            "result_truncated": False,
        }
        _emit_event(redact(event), config)
        return result

    # Preserve FastMCP's tool metadata/signature without setting __wrapped__.
    # FastMCP inspects callables deeply; exposing __wrapped__ can cause it to
    # register/call the original function and bypass the audit wrapper.
    wrapper.__name__ = func.__name__
    wrapper.__qualname__ = func.__qualname__
    wrapper.__doc__ = func.__doc__
    wrapper.__module__ = func.__module__
    wrapper.__annotations__ = getattr(func, "__annotations__", {}).copy()
    wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]
    return cast(F, wrapper)
