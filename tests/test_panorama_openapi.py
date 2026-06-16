import pytest

from app.panorama.api_search import PanoramaApiIndex
from app.panorama.client import PanoramaConfigError, PanoramaReadOnlyClient
from app.panorama.guardrails import GuardrailError, validate_read_only_operation


SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Sample Panorama API", "version": "11.2"},
    "components": {
        "parameters": {
            "location": {
                "name": "location",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
                "description": "The config location",
            }
        }
    },
    "paths": {
        "/restapi/v11.2/Objects/Addresses": {
            "get": {
                "operationId": "get-addresses",
                "summary": "Get address objects",
                "description": "Returns address objects from Panorama.",
                "tags": ["Objects"],
                "parameters": [{"$ref": "#/components/parameters/location"}],
            },
            "post": {
                "operationId": "create-address",
                "summary": "Create address object",
                "tags": ["Objects"],
            },
        },
        "/restapi/v11.2/Policies/SecurityRules": {
            "get": {
                "operationId": "get-security-rules",
                "summary": "Get security policy rules",
                "description": "Returns security policy rules.",
                "tags": ["Policies"],
            }
        },
    },
}


class FakeResponse:
    status_code = 200
    ok = True
    headers = {"content-type": "application/json"}
    text = '{"result":"ok"}'

    def json(self):
        return {"result": "ok"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params, headers, timeout, verify):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
                "verify": verify,
            }
        )
        return FakeResponse()


def test_search_finds_read_only_address_endpoint():
    index = PanoramaApiIndex(SAMPLE_SPEC)

    results = index.search("address objects", method="GET", limit=5)

    assert results[0]["method"] == "GET"
    assert results[0]["path"] == "/restapi/v11.2/Objects/Addresses"
    assert results[0]["read_only"] is True
    assert "Get address objects" in results[0]["summary"]


def test_endpoint_details_resolve_parameter_refs():
    index = PanoramaApiIndex(SAMPLE_SPEC)

    details = index.get_endpoint("/restapi/v11.2/Objects/Addresses", "GET")

    assert details["operation_id"] == "get-addresses"
    assert details["parameters"][0]["name"] == "location"
    assert details["parameters"][0]["required"] is True


def test_guardrails_reject_write_methods_and_unknown_paths():
    index = PanoramaApiIndex(SAMPLE_SPEC)

    with pytest.raises(GuardrailError, match="Only GET"):
        validate_read_only_operation(index, "POST", "/restapi/v11.2/Objects/Addresses")

    with pytest.raises(GuardrailError, match="not present"):
        validate_read_only_operation(index, "GET", "/restapi/v11.2/Unknown")


def test_guardrails_reject_absolute_urls():
    index = PanoramaApiIndex(SAMPLE_SPEC)

    with pytest.raises(GuardrailError, match="path only"):
        validate_read_only_operation(index, "GET", "https://panorama.local/restapi/v11.2/Objects/Addresses")


def test_client_requires_runtime_credentials():
    index = PanoramaApiIndex(SAMPLE_SPEC)
    client = PanoramaReadOnlyClient(index, base_url="", api_key="")

    with pytest.raises(PanoramaConfigError):
        client.call_get("/restapi/v11.2/Objects/Addresses")


def test_client_calls_validated_get_with_secret_header_but_redacts_response_metadata():
    index = PanoramaApiIndex(SAMPLE_SPEC)
    fake_session = FakeSession()
    client = PanoramaReadOnlyClient(
        index,
        base_url="https://panorama.local",
        api_key="super-secret-api-key",
        verify_ssl=False,
        session=fake_session,
    )

    result = client.call_get(
        "/restapi/v11.2/Objects/Addresses",
        params={"location": "shared"},
        timeout=7,
    )

    assert result["ok"] is True
    assert result["response"] == {"result": "ok"}
    assert "super-secret-api-key" not in repr(result)
    assert fake_session.calls[0]["headers"]["X-PAN-KEY"] == "super-secret-api-key"
    assert fake_session.calls[0]["url"] == "https://panorama.local/restapi/v11.2/Objects/Addresses"
    assert fake_session.calls[0]["params"] == {"location": "shared"}
    assert fake_session.calls[0]["verify"] is False
