# 01-05: Error Taxonomy & Failure Propagation

## Error Wrapping Rule

Backend-specific errors NEVER leak past `AdapterManager`. All errors are normalized to `MAIError` variants before reaching the API surface.

## Primary Error Domains

| Error Type | HTTP/gRPC Code | Source | Retry Hint |
|------------|----------------|--------|------------|
| `ModelNotFound` | 404 / NOT_FOUND | Registry | Check `/v1/models` |
| `ContextExceeded` | 422 / INVALID_ARGUMENT | Adapter | Reduce prompt/context window |
| `AdapterTimeout` | 504 / GATEWAY_TIMEOUT | AdapterManager | Retry with backoff |
| `HardwareFault` | 503 / UNAVAILABLE | HIL/Driver | Check `/v1/health/hardware` |
| `OOM` | 507 / INSUFFICIENT_STORAGE | MemoryManager | Unload models or reduce batch |
| `AdapterCrashed` | 502 / BAD_GATEWAY | Process Supervisor | Auto-retry in 1-2s |
| `AuthDenied` | 403 / PERMISSION_DENIED | API Middleware | Verify `X-IM-Profile` |
| `AirGapViolation` | 503 / SERVICE_UNAVAILABLE | API Startup | Check physical switch |

## Propagation Rules

- `Untrusted Adapter` panics -> `AdapterManager` catches -> logs -> restarts with exponential backoff -> returns `AdapterCrashed` to scheduler -> scheduler reroutes or queues.
- `HIL` detects thermal limit -> `PowerStateController` triggers `ThermalThrottle` -> scheduler applies backpressure -> clients receive throttled `202 Accepted` with retry-after header.
- `Vault` integrity fails -> `SecureLoadContext` aborts load -> returns `IntegrityViolation` -> model marked `corrupted` in registry -> alert logged.
