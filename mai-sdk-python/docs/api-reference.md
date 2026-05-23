# MAI SDK — API Reference

Synchronous (`MaiClient`) and async (`AsyncMaiClient`) clients expose
the same surface. Async methods are awaitable and async-generators
where the sync version is a generator.

## Construction

```python
MaiClient()                        # defaults (localhost:8420)
MaiClient(MaiClientConfig(...))    # explicit config
MaiClient.from_env(**overrides)    # env vars + overrides
MaiClient.from_file(path)          # TOML file
MaiClient.load(path=None, **kw)    # overrides > env > file > defaults
```

## Top-level convenience

| Method                              | Endpoint                          |
| ----------------------------------- | --------------------------------- |
| `chat(model, messages, ...)`        | POST `/v1/chat/completions`       |
| `chat_stream(model, messages, ...)` | POST `/v1/chat/completions` (SSE) |
| `complete(model, prompt, ...)`      | POST `/v1/completions`            |
| `stream_completions(model, prompt)` | POST `/v1/completions` (SSE)      |
| `embed(model, input_)`              | POST `/v1/embeddings`             |
| `structured(model, prompt, schema)` | POST `/v1/generate/structured`    |
| `function_call(model, msgs, fns)`   | POST `/v1/generate/function_call` |
| `health()`                          | GET  `/v1/health`                 |
| `health_check()` → bool             | GET  `/v1/health` (silent)        |
| `list_models()`                     | GET  `/v1/models`                 |
| `get_model(model_id)`               | GET  `/v1/models/{id}`            |
| `hardware_health()`                 | GET  `/v1/health/hardware`        |
| `power_state()`                     | GET  `/v1/power/state`            |

Spec aliases: `completions`, `embeddings`, `stream_chat`,
`structured_generation`.

## Namespaces

### `client.models`

| Method                   | Endpoint                              |
| ------------------------ | ------------------------------------- |
| `list(**filters)`        | GET  `/v1/models`                     |
| `get(model_id)`          | GET  `/v1/models/{id}`                |
| `load(model_id)`         | POST `/v1/models/{id}/load`           |
| `unload(model_id)`       | POST `/v1/models/{id}/unload`         |
| `benchmark(model_id)`    | POST `/v1/models/{id}/benchmark`      |
| `get_benchmark(model_id)`| GET  `/v1/models/{id}/benchmark`      |
| `discover(path=None)`    | POST `/v1/models/discover`            |
| `install(package_bytes)` | POST `/v1/models/install` (multipart) |
| `remove(model_id)`       | POST `/v1/models/{id}/remove`         |

### `client.power`

| Method                  | Endpoint                    |
| ----------------------- | --------------------------- |
| `get_state()`           | GET  `/v1/power/state`      |
| `transition(request)`   | POST `/v1/power/transition` |

### `client.system`

| Method               | Endpoint                       |
| -------------------- | ------------------------------ |
| `airgap()`           | GET  `/v1/system/airgap`       |
| `system_health()`    | GET  `/v1/health/system`       |
| `hardware_health()`  | GET  `/v1/health/hardware`     |

### `client.scheduler`

| Method                       | Endpoint                                       |
| ---------------------------- | ---------------------------------------------- |
| `metrics()`                  | GET  `/v1/scheduler/metrics`                   |
| `instance_metrics(id)`       | GET  `/v1/scheduler/instances/{id}/metrics`    |
| `instance_health(id)`        | GET  `/v1/scheduler/instances/{id}/health`     |
| `anomalies()`                | GET  `/v1/scheduler/anomalies`                 |

### `client.updates`

| Method                              | Endpoint                       |
| ----------------------------------- | ------------------------------ |
| `check()`                           | GET  `/v1/updates/check`       |
| `download(component, target_ver)`   | POST `/v1/updates/download`    |
| `status()`                          | GET  `/v1/updates/status`      |

### `client.admin` (requires admin auth)

| Method                  | Endpoint                  |
| ----------------------- | ------------------------- |
| `list_profiles()`       | GET  `/v1/profiles`       |
| `get_profile(id)`       | GET  `/v1/profiles/{id}`  |
| `audit_log(...)`        | GET  `/v1/audit/log`      |
| `adapters()`            | GET  `/v1/adapters`       |
| `registry()`            | GET  `/v1/registry`       |
| `registry_scan()`       | POST `/v1/registry/scan`  |

### `client.auth` (stubbed until BF-6)

| Method                  | Status                                          |
| ----------------------- | ----------------------------------------------- |
| `exchange_token(claim)` | Raises `TrustNotProvisionedError` (BF-6 pending)|

### `client.trust` (stubbed until BF-6)

| Method                              | Status                            |
| ----------------------------------- | --------------------------------- |
| `claims()`                          | Raises `TrustNotProvisionedError` |
| `bundle_status()`                   | Raises `TrustNotProvisionedError` |
| `revocation_status(subject_hash)`   | Raises `TrustNotProvisionedError` |

### `client.compliance` (Sessions 36-44)

Any attribute access raises `NotImplementedError` until Lamprey lands.
Reserved so application code can do feature detection now.

## Exception hierarchy

```
MaiError
    BadRequestError              (400)
    AuthenticationError          (401)
        ClaimExpiredError        (trust claim expired)
    PermissionError              (403)
        AirGapViolationError
    NotFoundError                (404)
    RateLimitError               (429, carries retry_after)
    ServerError                  (5xx)
    PowerStateUnavailableError   (503)
    ConnectionError              (network)
    TimeoutError                 (request timeout)
    TrustCacheStaleError         (local trust cache stale/expired)
```

See [error-handling.md](error-handling.md) for catch patterns.

## Retry

Default retries: 429, 500/502/503/504, connection errors, timeouts.
Non-retryable: 400, 401, 403, 404.

```python
from mai import RetryPolicy, MaiClientConfig

cfg = MaiClientConfig(retry=RetryPolicy(
    max_retries=5, base_delay=0.5, max_delay=60.0, jitter=0.3,
))
```

Pass `RetryPolicy(max_retries=0)` (or import `NO_RETRY_POLICY`) to
disable retries entirely.
