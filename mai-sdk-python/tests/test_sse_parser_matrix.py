"""SSE line parsing and error construction matrix tests."""

from __future__ import annotations

import json

import httpx
import pytest
from mai.client import _build_error, _parse_sse_line
from mai.errors import MaiError


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("", None),
        (" ", None),
        (":keepalive", None),
        (": keepalive with space", None),
        ("\n", None),
        ("data: [DONE]", None),
        ("data: {\"a\": 1}", "{\"a\": 1}"),
        ("data: {\"a\": 1}\n", "{\"a\": 1}"),
        ("data: [DONE]\n", None),
        ("data: [DONE]\r\n", None),
        ("data: {\"a\": 1}\r\n", "{\"a\": 1}"),
        ("event: message", None),
        ("id: 1", None),
        ("data:{\"a\": 1}", None),  # must include the space after "data:"
        ("data: ", None),  # stripped -> "data:"; treated as non-data line
    ],
)
def test_parse_sse_line_matrix(line: str, expected: str | None) -> None:
    assert _parse_sse_line(line) == expected


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (401, {"error": {"code": "MAI-4001", "message": "forbidden"}}),
        (404, {"error": {"code": "MAI-2001", "message": "missing"}}),
        (429, {"error": {"code": "MAI-5002", "message": "rate limited"}}),
        (500, {"error": {"code": "MAI-3001", "message": "internal"}}),
    ],
)
def test_build_error_returns_typed_mai_error(status: int, body: dict) -> None:
    req = httpx.Request("GET", "http://example/v1/health/live")
    resp = httpx.Response(status_code=status, request=req, json=body)
    err = _build_error(resp)
    assert isinstance(err, MaiError)
    # A typed error must preserve the HTTP status.
    assert err.status_code == status


def test_build_error_handles_non_json_payload() -> None:
    req = httpx.Request("GET", "http://example/v1/models")
    resp = httpx.Response(status_code=500, request=req, content=b"not json")
    err = _build_error(resp)
    assert isinstance(err, MaiError)
    assert err.status_code == 500
    assert "not json" in err.message.lower() or err.message


def test_parse_sse_line_plus_json_round_trip() -> None:
    payload = {"id": "evt-1", "choices": [{"delta": {"content": "hi"}}]}
    line = f"data: {json.dumps(payload)}"
    data = _parse_sse_line(line)
    if data is None:
        pytest.fail("expected SSE parser to return a JSON payload for data: lines")
    parsed = json.loads(data)
    assert parsed["id"] == "evt-1"
    assert parsed["choices"][0]["delta"]["content"] == "hi"
