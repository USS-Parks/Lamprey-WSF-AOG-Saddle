# 01-01: Trust Model & Cascade Failure Prevention

## Three Trust Zones

1. **Trusted (Rust):** `mai-core`, `mai-hil`, `mai-api`, `mai-sdk-rs`. Direct hardware access permitted. Minimal `unsafe` footprint confined strictly to driver implementations. Forms the Trusted Computing Base (TCB).

2. **Untrusted Adapters (Python/PyO3):** `adapters/*`. Sandboxed capsules. Zero hardware access. Communicate exclusively through typed HIL traits. If a backend panics, `AdapterManager` catches it, logs, and initiates exponential backoff restart.

3. **Untrusted Applications (L4-L6):** Isolated processes. Call MAI only via L3-L4 syscall interface (REST/gRPC). Cannot address VRAM, read model weights, or bypass routing.

## Boundary Enforcement

- **Adapter -> HIL:** Typed trait calls. No raw pointers, no `unsafe` bridge crossing.
- **App -> API:** Strict OpenAPI/Proto3 validation. Auth middleware gates all requests.
- **Core -> Driver:** `unsafe` isolated to `mai-hil/src/drivers/`. `mai-core` uses only safe HIL trait abstractions.
- **Crash Isolation:** Each adapter runs in a dedicated OS process with cgroups limits. Core monitors via heartbeat (5s interval, 3 strikes -> restart).

## Data Flow Integrity

All inference requests pass through: `App -> API -> Auth -> Scheduler -> AdapterManager -> Adapter -> Backend -> Stream -> App`. No shortcut paths exist. Backend errors are wrapped in `AdapterError` before crossing the boundary.
