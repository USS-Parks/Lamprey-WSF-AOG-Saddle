"""Error payload robustness matrix tests."""

from __future__ import annotations

import httpx
import pytest

from mai.client import _build_error
from mai.errors import MaiError


@pytest.mark.parametrize(
    ("status", "json_body"),
    [
        (400, {"error": {"code": "MAI-1001", "type": "invalid_request", "message": "bad"}}),
        (401, {"error": {"code": "MAI-4001", "type": "authentication_failed", "message": "no"}}),
        (403, {"error": {"code": "MAI-4002", "type": "permission_denied", "message": "no"}}),
        (404, {"error": {"code": "MAI-2001", "type": "internal_error", "message": "missing"}}),
        (409, {"error": {"code": "MAI-5001", "type": "conflict", "message": "conflict"}}),
        (413, {"error": {"code": "MAI-1002", "type": "invalid_request", "message": "too big"}}),
        (415, {"error": {"code": "MAI-1003", "type": "invalid_request", "message": "media"}}),
        (422, {"error": {"code": "MAI-1004", "type": "invalid_request", "message": "unprocessable"}}),
        (429, {"error": {"code": "MAI-5002", "type": "rate_limited", "message": "slow"}}),
        (500, {"error": {"code": "MAI-3001", "type": "internal_error", "message": "boom"}}),
        (503, {"error": {"code": "MAI-3002", "type": "overloaded", "message": "busy"}}),
    ],
)
def test_build_error_json_matrix(status: int, json_body: dict) -> None:
    req = httpx.Request("POST", "http://example/v1/chat/completions")
    resp = httpx.Response(status_code=status, request=req, json=json_body)
    err = _build_error(resp)
    assert isinstance(err, MaiError)
    assert err.status_code == status
    assert isinstance(err.message, str)
    assert err.message != ""


@pytest.mark.parametrize(
    ("status", "content"),
    [
        (500, b""),
        (500, b"not json"),
        (502, b"<html>bad gateway</html>"),
        (503, b"{"),
        (504, b"}"),
    ],
)
def test_build_error_non_json_matrix(status: int, content: bytes) -> None:
    req = httpx.Request("GET", "http://example/v1/models")
    resp = httpx.Response(status_code=status, request=req, content=content)
    err = _build_error(resp)
    assert isinstance(err, MaiError)
    assert err.status_code == status


@pytest.mark.parametrize(
    ("status", "json_body"),
    [
        (500, {}),
        (500, {"error": {}}),
        (500, {"error": {"message": "x"}}),
        (500, {"error": {"code": "MAI-3001"}}),
        (500, {"error": {"type": "internal_error"}}),
        (500, {"error": "not-a-dict"}),
        (500, {"errors": [{"message": "x"}]}),
    ],
)
def test_build_error_weird_json_shapes_do_not_crash(
    status: int, json_body: dict,
) -> None:
    req = httpx.Request("GET", "http://example/v1/health/ready")
    resp = httpx.Response(status_code=status, request=req, json=json_body)
    err = _build_error(resp)
    assert isinstance(err, MaiError)
    assert err.status_code == status

