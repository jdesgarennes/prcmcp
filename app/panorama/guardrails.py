from __future__ import annotations

from urllib.parse import urlparse

from .api_search import PanoramaApiIndex


class GuardrailError(ValueError):
    """Raised when a requested Panorama operation violates safety policy."""


def validate_read_only_operation(index: PanoramaApiIndex, method: str, path: str) -> dict:
    """Validate that an operation is an approved read-only Panorama call.

    The MCP tool accepts only an OpenAPI path, never a complete URL, so the model
    cannot redirect credentials to another host. The first release is strictly
    GET-only and only for paths present in the bundled OpenAPI document.
    """

    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc:
        raise GuardrailError("Pass an OpenAPI path only, not a full URL")

    if not path.startswith("/"):
        raise GuardrailError("OpenAPI path must start with '/'")

    method_upper = method.upper()
    if method_upper != "GET":
        raise GuardrailError("Only GET requests are allowed by the read-only Panorama MCP tool")

    try:
        endpoint = index.get_endpoint(path, method_upper)
    except KeyError as exc:
        raise GuardrailError(f"GET {path} is not present in the Panorama OpenAPI spec") from exc

    if not endpoint.get("read_only"):
        raise GuardrailError(f"GET {path} is not classified as read-only")

    return endpoint
