"""RetryPolicy backoff math and should_retry decisions."""

from __future__ import annotations

from mai.errors import (
    AuthenticationError,
    MaiError,
    NotFoundError,
    PowerStateUnavailableError,
    RateLimitError,
    ServerError,
)
from mai.retry import DEFAULT_RETRY_POLICY, NO_RETRY_POLICY, RetryPolicy


def test_default_policy_values() -> None:
    p = DEFAULT_RETRY_POLICY
    assert p.max_retries == 3
    assert p.base_delay == 1.0
    assert p.max_delay == 30.0


def test_no_retry_policy_disables_retries() -> None:
    p = NO_RETRY_POLICY
    err = RateLimitError("rate", status_code=429)
    assert p.should_retry(err, 0) is None


def test_exponential_backoff_no_jitter() -> None:
    p = RetryPolicy(max_retries=5, base_delay=1.0, max_delay=30.0, jitter=0.0)
    assert p.compute_delay(0) == 1.0
    assert p.compute_delay(1) == 2.0
    assert p.compute_delay(2) == 4.0
    assert p.compute_delay(3) == 8.0
    assert p.compute_delay(4) == 16.0
    # Capped
    assert p.compute_delay(10) == 30.0


def test_retry_after_overrides_backoff() -> None:
    p = RetryPolicy(max_retries=5, base_delay=1.0, jitter=0.0)
    assert p.compute_delay(5, retry_after=7) == 7.0


def test_retry_after_capped_by_max_delay() -> None:
    p = RetryPolicy(max_retries=5, max_delay=10.0, jitter=0.0)
    assert p.compute_delay(0, retry_after=500) == 10.0


def test_jitter_adds_random_within_bounds() -> None:
    p = RetryPolicy(max_retries=1, base_delay=4.0, max_delay=30.0, jitter=0.5)
    for _ in range(50):
        delay = p.compute_delay(0)
        assert 4.0 <= delay <= 4.0 * 1.5


def test_should_retry_stops_at_max_retries() -> None:
    p = RetryPolicy(max_retries=2, base_delay=0.1, jitter=0.0)
    err = ServerError("boom", status_code=500)
    assert p.should_retry(err, 0) is not None
    assert p.should_retry(err, 1) is not None
    assert p.should_retry(err, 2) is None


def test_should_retry_skips_non_retryable() -> None:
    p = RetryPolicy(max_retries=5)
    assert p.should_retry(AuthenticationError("nope", status_code=401), 0) is None
    assert p.should_retry(NotFoundError("missing", status_code=404), 0) is None


def test_should_retry_honors_server_retry_after() -> None:
    p = RetryPolicy(max_retries=5, jitter=0.0)
    err = MaiError("limited")
    err.retry_after = 9
    err.status_code = 429
    delay = p.should_retry(err, 0)
    assert delay == 9.0


def test_power_state_unavailable_is_retryable() -> None:
    p = RetryPolicy(max_retries=2, base_delay=0.1, jitter=0.0)
    err = PowerStateUnavailableError("sleeping", status_code=503)
    assert p.should_retry(err, 0) is not None
