from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SPEC_PATH = Path(__file__).resolve().parents[2] / "resources" / "palo-openapi.json"


class OpenApiSpecError(RuntimeError):
    """Raised when the Panorama OpenAPI spec cannot be loaded or understood."""


def get_default_spec_path() -> Path:
    """Return the configured OpenAPI spec path, defaulting to resources/palo-openapi.json."""

    return Path(os.environ.get("PANORAMA_OPENAPI_PATH", DEFAULT_SPEC_PATH)).expanduser()


def load_openapi_spec(path: str | Path | None = None) -> dict[str, Any]:
    """Load the Panorama OpenAPI document from JSON.

    The repo currently carries Palo Alto's Panorama REST API OpenAPI document as
    JSON. This loader deliberately fails fast with clear messages so MCP tool
    users know whether the issue is a missing resources file or malformed JSON.
    """

    spec_path = Path(path).expanduser() if path else get_default_spec_path()
    if not spec_path.exists():
        raise OpenApiSpecError(f"OpenAPI spec not found: {spec_path}")

    try:
        with spec_path.open("r", encoding="utf-8") as handle:
            spec = json.load(handle)
    except json.JSONDecodeError as exc:
        raise OpenApiSpecError(f"OpenAPI spec is not valid JSON: {spec_path}: {exc}") from exc

    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        raise OpenApiSpecError("OpenAPI spec must be a JSON object with a 'paths' object")
    return spec


def resolve_ref(spec: dict[str, Any], value: Any) -> Any:
    """Resolve a local JSON pointer reference inside the OpenAPI spec.

    Only local refs like '#/components/parameters/location' are resolved. Remote
    refs are returned unchanged because this server should not fetch arbitrary
    URLs from an OpenAPI document.
    """

    if not isinstance(value, dict) or "$ref" not in value:
        return value

    ref = value["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return value

    current: Any = spec
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            return value
        current = current[part]
    return current
