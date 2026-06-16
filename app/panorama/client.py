from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import requests

from .api_search import PanoramaApiIndex
from .guardrails import validate_read_only_operation


class PanoramaConfigError(RuntimeError):
    """Raised when required Panorama runtime configuration is missing."""


def _bool_from_env(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class PanoramaReadOnlyClient:
    """Small, guarded Panorama REST API client for read-only GET calls."""

    def __init__(
        self,
        index: PanoramaApiIndex,
        base_url: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool | None = None,
        session: Any | None = None,
    ):
        self.index = index
        self.base_url = (base_url or os.environ.get("PANORAMA_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("PANORAMA_API_KEY") or ""
        self.verify_ssl = _bool_from_env(os.environ.get("PANORAMA_VERIFY_SSL"), True) if verify_ssl is None else verify_ssl
        self.session = session or requests.Session()

    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured(),
            "base_url_set": bool(self.base_url),
            "api_key_set": bool(self.api_key),
            "verify_ssl": self.verify_ssl,
            "openapi_endpoints": len(self.index.endpoints),
        }

    def call_get(self, path: str, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
        endpoint = validate_read_only_operation(self.index, "GET", path)
        if not self.configured():
            raise PanoramaConfigError(
                "PANORAMA_BASE_URL and PANORAMA_API_KEY must be set in the runtime environment"
            )

        safe_params = params or {}
        if not isinstance(safe_params, dict):
            raise ValueError("params must be a JSON object/dict")

        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        response = self.session.get(
            url,
            params=safe_params,
            headers={
                "X-PAN-KEY": self.api_key,
                "Accept": "application/json",
            },
            timeout=timeout,
            verify=self.verify_ssl,
        )

        content_type = response.headers.get("content-type", "")
        try:
            body: Any = response.json() if "json" in content_type.lower() else response.text
        except ValueError:
            body = response.text

        return {
            "method": "GET",
            "path": path,
            "url_host": self.base_url,
            "status_code": response.status_code,
            "ok": response.ok,
            "endpoint": {
                "summary": endpoint.get("summary"),
                "operation_id": endpoint.get("operation_id"),
            },
            "response": body,
        }
