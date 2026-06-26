import json

from app.audit.config import AuditConfig
from app.audit.decorator import audit_tool
from app.audit.redaction import REDACTED, redact
from app.audit.syslog_sink import prepare_event_payload


def test_redaction_removes_obvious_secrets():
    data = {
        "PANORAMA_API_KEY": "secret-key",
        "headers": {"X-PAN-KEY": "secret-header", "content-type": "json"},
        "nested": [{"password": "secret-password"}],
    }

    redacted = redact(data)

    assert redacted["PANORAMA_API_KEY"] == REDACTED
    assert redacted["headers"]["X-PAN-KEY"] == REDACTED
    assert redacted["headers"]["content-type"] == "json"
    assert redacted["nested"][0]["password"] == REDACTED
    assert "secret-key" not in repr(redacted)
    assert "secret-header" not in repr(redacted)
    assert "secret-password" not in repr(redacted)


def test_audit_decorator_emits_full_result_with_redaction(monkeypatch):
    events = []

    def fake_send(event, config):
        events.append((event, config))
        return True

    monkeypatch.setattr("app.audit.decorator.send_syslog_json", fake_send)
    monkeypatch.setenv("AUDIT_ENV", "lab")

    @audit_tool
    def sample_tool(path: str, api_key: str):
        return {"ok": True, "response": {"path": path, "token": "secret-token", "items": [1, 2]}}

    result = sample_tool("/restapi/v11.2/Objects/Addresses", "secret-input")

    assert result["ok"] is True
    assert len(events) == 1
    event, config = events[0]
    assert isinstance(config, AuditConfig)
    assert event["event_type"] == "mcp_tool_call"
    assert event["environment"] == "lab"
    assert event["tool"] == "sample_tool"
    assert event["success"] is True
    assert event["arguments"]["path"] == "/restapi/v11.2/Objects/Addresses"
    assert event["arguments"]["api_key"] == REDACTED
    assert event["result"]["response"]["token"] == REDACTED
    assert event["result"]["response"]["items"] == [1, 2]
    assert "secret-input" not in repr(event)
    assert "secret-token" not in repr(event)


def test_prepare_event_payload_truncates_large_results():
    event = {
        "event_type": "mcp_tool_call",
        "timestamp": "2026-01-01T00:00:00Z",
        "server": "prcmcp",
        "environment": "lab",
        "tool": "large_tool",
        "success": True,
        "result": {"items": ["x" * 100 for _ in range(100)]},
        "result_truncated": False,
    }

    payload, truncated = prepare_event_payload(event, max_bytes=1200)
    parsed = json.loads(payload)

    assert truncated is True
    assert len(payload.encode("utf-8")) <= 1200
    assert parsed["result_truncated"] is True
    assert parsed["result"]["truncated"] is True
    assert parsed["result"]["original_size_bytes"] > 1200
