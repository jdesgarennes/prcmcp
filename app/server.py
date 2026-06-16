# app/server.py
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.panorama.api_search import PanoramaApiIndex
from app.panorama.client import PanoramaConfigError, PanoramaReadOnlyClient
from app.panorama.guardrails import GuardrailError
from app.panorama.openapi_loader import OpenApiSpecError, load_openapi_spec

mcp = FastMCP("PRC MCP")

_INDEX: PanoramaApiIndex | None = None


def _get_index() -> PanoramaApiIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = PanoramaApiIndex(load_openapi_spec())
    return _INDEX


@mcp.tool()
def ping() -> str:
    """Basic health test tool."""
    return "pong from prcmcp"


@mcp.tool()
def panorama_config_status() -> dict[str, Any]:
    """Show whether Panorama runtime config is present without exposing secrets."""
    try:
        index = _get_index()
        return PanoramaReadOnlyClient(index).status()
    except OpenApiSpecError as exc:
        return {"configured": False, "error": str(exc)}


@mcp.tool()
def list_panorama_api_categories() -> list[dict[str, Any]]:
    """List OpenAPI tags/categories and how many read-only GET endpoints each has."""
    return _get_index().categories()


@mcp.tool()
def search_panorama_api(query: str, method: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Search the bundled Panorama OpenAPI spec for matching endpoints.

    Use this before calling Panorama so the agent can discover the correct path,
    required query parameters, and whether an endpoint is read-only.
    """
    return _get_index().search(query=query, method=method, limit=limit)


@mcp.tool()
def get_panorama_endpoint(path: str, method: str = "GET") -> dict[str, Any]:
    """Return detailed OpenAPI documentation for one Panorama endpoint."""
    try:
        return _get_index().get_endpoint(path, method)
    except KeyError as exc:
        return {"error": str(exc), "method": method.upper(), "path": path}


@mcp.tool()
def call_panorama_read_api(path: str, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    """Call a validated read-only GET endpoint on Panorama.

    Guardrails:
    - accepts an OpenAPI path only, never a full URL
    - allows only GET operations present in resources/palo-openapi.json
    - uses PANORAMA_BASE_URL and PANORAMA_API_KEY from server-side env vars
    - never returns the API key to the agent
    """
    try:
        return PanoramaReadOnlyClient(_get_index()).call_get(path=path, params=params, timeout=timeout)
    except (GuardrailError, PanoramaConfigError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "path": path}
