from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AuditConfig:
    enabled: bool = True
    environment: str = "unknown"
    server_name: str = "prcmcp"
    syslog_host: str = "syslog.pechanga.com"
    syslog_port: int = 514
    log_full_results: bool = True
    max_event_bytes: int = 32768

    @classmethod
    def from_env(cls) -> "AuditConfig":
        return cls(
            enabled=_env_bool("AUDIT_ENABLED", True),
            environment=os.getenv("AUDIT_ENV") or os.getenv("KUBERNETES_NAMESPACE") or "unknown",
            server_name=os.getenv("AUDIT_SERVER_NAME", "prcmcp"),
            syslog_host=os.getenv("LOGRHYTHM_SYSLOG_HOST", "syslog.pechanga.com"),
            syslog_port=_env_int("LOGRHYTHM_SYSLOG_PORT", 514),
            log_full_results=_env_bool("AUDIT_LOG_FULL_RESULTS", True),
            max_event_bytes=_env_int("AUDIT_MAX_EVENT_BYTES", 32768),
        )
