"""Exception hierarchy and HTTP-status-to-exception mapping."""

from __future__ import annotations

import pytest
from mai.errors import (
    AirGapViolationError,
    AuthenticationError,
    BadRequestError,
    ClaimExpiredError,
    MaiError,
    NotFoundError,
    PowerStateUnavailableError,
    RateLimitError,
    ServerError,
    from_response,
    from_transport,
)
from mai.errors import (
    PermissionError as MaiPermissionError,
)
from mai.errors import (
    TimeoutError as MaiTimeoutError,
)
from mai.types import ErrorResponse


def _resp(
    code: str, type_: str, message: str = "x", retry_after: int | None = None,
) -> ErrorResponse:
    payload: dict[str, object] = {"code": code, "type": type_, "message": message}
    if retry_after is not None:
        payload["retry_after_seconds"] = retry_after
    return ErrorResponse(error=payload)  # type: ignore[arg-type]


@pytest.mark.parametrize(("status", "type_", "expected"), [
    (400, "invalid_request", BadRequestError),
    (401, "authentication_failed", AuthenticationError),
    (403, "permission_denied", MaiPermissionError),
    (403, "air_gap_violation", AirGapViolationError),
    (404, "internal_error", NotFoundError),
    (429, "rate_limited", RateLimitError),
    (500, "internal_error", ServerError),
    (503, "power_state_unavailable", PowerStateUnavailableError),
    (504, "timeout", MaiTimeoutError),
])
def test_from_response_maps_status_to_class(
    status: int, type_: str, expected: type[MaiError],
) -> None:
    err = from_response(_resp("MAI-X100", type_), status)
    assert isinstance(err, expected)
    assert err.status_code == status


def test_rate_limit_carries_retry_after() -> None:
    err = from_response(_resp("MAI-R001", "rate_limited", retry_after=12), 429)
    assert isinstance(err, RateLimitError)
    assert err.retry_after == 12
    assert err.is_retryable


def test_auth_with_expired_claim_code_yields_claim_expired() -> None:
    err = from_response(_resp("MAI-A101", "authentication_failed"), 401)
    assert isinstance(err, ClaimExpiredError)
    assert isinstance(err, AuthenticationError)


def test_non_retryable_for_4xx() -> None:
    for status, type_ in [(401, "authentication_failed"),
                          (403, "permission_denied"),
                          (404, "internal_error"),
                          (400, "invalid_request")]:
        err = from_response(_resp("MAI-X", type_), status)
        assert not err.is_retryable, f"{status}/{type_} should not be retryable"


def test_retryable_for_429_and_503() -> None:
    err429 = from_response(_resp("MAI-R", "rate_limited"), 429)
    err503 = from_response(_resp("MAI-O", "overloaded"), 503)
    assert err429.is_retryable
    assert err503.is_retryable


def test_from_transport_maps_httpx_exceptions() -> None:
    import httpx
    err = from_transport(httpx.ConnectError("dns failure"))
    assert "network error" in str(err)
    err2 = from_transport(httpx.ReadTimeout("read"))
    assert isinstance(err2, MaiTimeoutError)


def test_legacy_types_maierror_is_same_class() -> None:
    from mai.types import MaiError as LegacyMaiError
    assert LegacyMaiError is MaiError
