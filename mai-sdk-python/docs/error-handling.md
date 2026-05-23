# Error handling

All SDK exceptions inherit from `mai.MaiError`. Catch the base class
when you only need to know "the call failed". Catch a subclass when
the response shape matters.

## Hierarchy

```
MaiError
    BadRequestError              HTTP 400 — your request was invalid
    AuthenticationError          HTTP 401 — missing/invalid credentials
        ClaimExpiredError        — trust claim expired (BF-2 surface)
    PermissionError              HTTP 403 — not allowed
        AirGapViolationError     — server reported air-gap policy violation
    NotFoundError                HTTP 404
    RateLimitError               HTTP 429 — `retry_after` is set
    ServerError                  HTTP 5xx
    PowerStateUnavailableError   server is in a sleep state
    ConnectionError              network failed before reaching the server
    TimeoutError                 request exceeded its timeout
    TrustCacheStaleError         local trust cache stale/expired (BF-4)
```

## Catch by class

```python
from mai import (
    MaiClient, MaiError, AuthenticationError, RateLimitError,
    ConnectionError as MaiConnectionError,
)

with MaiClient.load() as client:
    try:
        response = client.chat("...", messages)
    except AuthenticationError:
        # rotate credentials, prompt the user
        ...
    except RateLimitError as e:
        # honor server backoff hint
        time.sleep(e.retry_after or 1)
    except MaiConnectionError:
        # network down; try later or surface
        ...
    except MaiError as e:
        # anything else — log e.code, e.message, e.request_id
        log.error("MAI %s: %s", e.code, e.message)
```

## Fields available on any MaiError

| Field        | Description                                        |
| ------------ | -------------------------------------------------- |
| `message`    | Human-readable string (same as `str(e)`)           |
| `code`       | MAI error code (`MAI-XYYY`)                        |
| `error_type` | Server-side classification                         |
| `status_code`| HTTP status (if a response was returned)           |
| `retry_after`| Seconds (set on RateLimit and some 5xx)            |
| `request_id` | Server request id, when present                    |
| `is_retryable`| Convenience boolean                               |

## Auto-retry

The SDK's `RetryPolicy` retries 429/500/502/503/504, connection
errors, and timeouts. It does NOT retry 400/401/403/404. The error
that ultimately surfaces is the one from the last attempt.

## Trust-specific errors

`client.trust.*` and `client.auth.exchange_token` raise
`TrustNotProvisionedError` (a subclass of `MaiError`) in Session 29
because the server side ships in BF-6. Production code can branch
on this to fall back to API-key auth.

```python
from mai._namespaces import TrustNotProvisionedError

try:
    status = client.trust.bundle_status()
except TrustNotProvisionedError:
    status = None  # operate in API-key mode
```
