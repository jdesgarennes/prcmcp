from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "x-pan-key",
    "x_pan_key",
)

REDACTED = "[REDACTED]"


def _is_sensitive_key(key: object) -> bool:
    key_text = str(key).lower().replace("-", "_")
    return any(part in key_text for part in SENSITIVE_KEY_PARTS)


def redact(value: Any) -> Any:
    """Recursively redact obvious secrets while preserving useful audit context."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_key(key) else redact(item)
            for key, item in value.items()
        }

    if isinstance(value, str):
        return value

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]

    return value
