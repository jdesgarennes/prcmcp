from __future__ import annotations

import re
from typing import Any

from .openapi_loader import resolve_ref

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_:-]+", text) if len(token) > 1}


def _is_read_only(method: str, path: str) -> bool:
    # For the first version, read-only means HTTP GET only. Even if a vendor uses
    # action suffixes such as ':rename', non-GET methods are denied elsewhere.
    return method.upper() == "GET" and not path.lower().startswith("/api/?type=keygen")


class PanoramaApiIndex:
    """Searchable index over the Panorama OpenAPI paths."""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.endpoints = self._build_endpoints()

    def _build_endpoints(self) -> list[dict[str, Any]]:
        endpoints: list[dict[str, Any]] = []
        for path, path_item in self.spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            path_parameters = path_item.get("parameters", [])
            for method, operation in path_item.items():
                if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                    continue
                all_parameters = list(path_parameters) + list(operation.get("parameters", []))
                parameters = [resolve_ref(self.spec, param) for param in all_parameters]
                tags = operation.get("tags", []) or []
                endpoint = {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "summary": _clean_text(operation.get("summary")),
                    "description": _clean_text(operation.get("description")),
                    "tags": tags,
                    "parameters": parameters,
                    "read_only": _is_read_only(method, path),
                    "has_request_body": "requestBody" in operation,
                }
                searchable = " ".join(
                    [
                        path,
                        endpoint["method"],
                        endpoint["operation_id"] or "",
                        endpoint["summary"],
                        endpoint["description"],
                        " ".join(map(str, tags)),
                    ]
                )
                endpoint["_search_text"] = searchable.lower()
                endpoint["_tokens"] = _tokens(searchable)
                endpoints.append(endpoint)
        return endpoints

    def categories(self) -> list[dict[str, Any]]:
        counts: dict[str, dict[str, Any]] = {}
        for endpoint in self.endpoints:
            tags = endpoint.get("tags") or ["untagged"]
            for tag in tags:
                info = counts.setdefault(str(tag), {"tag": str(tag), "endpoints": 0, "read_only_get_endpoints": 0})
                info["endpoints"] += 1
                if endpoint["read_only"]:
                    info["read_only_get_endpoints"] += 1
        return sorted(counts.values(), key=lambda item: item["tag"].lower())

    def search(self, query: str, method: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        query = (query or "").strip()
        method_upper = method.upper() if method else None
        query_tokens = _tokens(query)
        scored: list[tuple[int, dict[str, Any]]] = []

        for endpoint in self.endpoints:
            if method_upper and endpoint["method"] != method_upper:
                continue
            score = 0
            if query:
                lower_query = query.lower()
                if lower_query in endpoint["_search_text"]:
                    score += 20
                overlap = query_tokens.intersection(endpoint["_tokens"])
                score += len(overlap) * 10
                for token in query_tokens:
                    if token in endpoint["path"].lower():
                        score += 8
                    if token in endpoint["summary"].lower():
                        score += 6
                    if token in endpoint["description"].lower():
                        score += 3
            else:
                score = 1

            if score > 0:
                scored.append((score, endpoint))

        scored.sort(key=lambda item: (-item[0], item[1]["path"], item[1]["method"]))
        return [self._public_summary(endpoint, score) for score, endpoint in scored[: max(1, min(limit, 50))]]

    def get_endpoint(self, path: str, method: str = "GET") -> dict[str, Any]:
        method_upper = method.upper()
        for endpoint in self.endpoints:
            if endpoint["path"] == path and endpoint["method"] == method_upper:
                return self._public_details(endpoint)
        raise KeyError(f"Endpoint not found in OpenAPI spec: {method_upper} {path}")

    def has_operation(self, path: str, method: str = "GET") -> bool:
        try:
            self.get_endpoint(path, method)
            return True
        except KeyError:
            return False

    def _public_summary(self, endpoint: dict[str, Any], score: int | None = None) -> dict[str, Any]:
        item = {
            "method": endpoint["method"],
            "path": endpoint["path"],
            "operation_id": endpoint["operation_id"],
            "summary": endpoint["summary"],
            "description": endpoint["description"][:500],
            "tags": endpoint["tags"],
            "read_only": endpoint["read_only"],
            "required_parameters": [
                param.get("name")
                for param in endpoint.get("parameters", [])
                if isinstance(param, dict) and param.get("required")
            ],
        }
        if score is not None:
            item["score"] = score
        return item

    def _public_details(self, endpoint: dict[str, Any]) -> dict[str, Any]:
        details = self._public_summary(endpoint)
        details.update(
            {
                "parameters": endpoint.get("parameters", []),
                "has_request_body": endpoint.get("has_request_body", False),
            }
        )
        return details
