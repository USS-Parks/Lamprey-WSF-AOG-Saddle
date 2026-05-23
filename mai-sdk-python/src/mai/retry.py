"""Retry policy with exponential backoff and jitter.

Public surface so apps can construct their own policy and pass it
to ``MaiClient`` / ``AsyncMaiClient``.

Default policy retries:
    - 429 (rate limit, honors ``Retry-After`` when present)
    - 503 (overloaded)
    - 5xx (server error)
    - ``ConnectionError`` (network failure)
    - ``TimeoutError`` (request timed out)

Default policy does NOT retry:
    - 400 (bad request)
    - 401 (auth failure)
    - 403 (permission denied)
    - 404 (not found)
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from mai.errors import MaiError


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retry behavior.

    Args:
        max_retries: Maximum number of retries (not counting the
            first attempt). Set to 0 to disable retries.
        base_delay: Initial delay in seconds for the first retry.
        max_delay: Cap on the computed delay regardless of attempt.
        jitter: Fraction of the computed delay to add as random jitter
            (0.0 disables jitter, 1.0 doubles the delay range).
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 0.25

    def compute_delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Compute the delay before the next retry.

        Args:
            attempt: Zero-indexed attempt number that just failed.
                ``attempt == 0`` means the first call failed and we are
                about to make the second call.
            retry_after: Server-provided ``Retry-After`` value, in
                seconds. If present, takes precedence over backoff.

        Returns:
            Delay in seconds before the next attempt.
        """
        if retry_after is not None:
            return min(float(retry_after), self.max_delay)

        backoff = self.base_delay * (2 ** attempt)
        backoff = min(backoff, self.max_delay)

        if self.jitter > 0:
            jitter_amount = backoff * self.jitter
            backoff += random.uniform(0, jitter_amount)  # noqa: S311 — not for crypto

        return float(backoff)

    def should_retry(self, error: MaiError, attempt: int) -> float | None:
        """Decide whether to retry, returning delay (seconds) or None.

        Args:
            error: The error raised by the failed attempt.
            attempt: Zero-indexed attempt number that just failed.

        Returns:
            Float seconds to wait before retry, or ``None`` to stop.
        """
        if attempt >= self.max_retries:
            return None
        if not error.is_retryable:
            return None
        retry_after: float | None = (
            float(error.retry_after) if error.retry_after is not None else None
        )
        return self.compute_delay(attempt, retry_after=retry_after)


DEFAULT_RETRY_POLICY = RetryPolicy()
"""Sensible default: 3 retries, 1s base, 30s cap, 25% jitter."""


NO_RETRY_POLICY = RetryPolicy(max_retries=0)
"""Disable retries entirely (useful for tests and idempotency-sensitive paths)."""


__all__ = [
    "DEFAULT_RETRY_POLICY",
    "NO_RETRY_POLICY",
    "RetryPolicy",
]
