# 01-10: Technology Choices & Rationale

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Core Kernel | Rust (2024 ed, 1.80+) | Memory safety without GC, zero-cost abstractions, minimal TCB, strict borrow checker enforces trust boundaries |
| HIL & Drivers | Rust | Direct hardware access requires `unsafe`; confined to drivers only. NVML/ROCm bindings mature |
| API Server | axum + tonic | Async-first, single binary, excellent SSE/WebSocket support, gRPC performance |
| Backend Adapters | Python (3.12) | Ecosystem dominance: vLLM, Ollama, llama-cpp-python all ship Python clients first |
| FFI Bridge | PyO3 | Typed, safe, mature Rust<->Python interop. Enables process isolation |
| Serialization | serde + TOML | Strong typing, human-readable config, industry standard |
| Async Runtime | tokio | De facto Rust async, battle-tested, integrates cleanly with axum/tonic |
| PQC | liboqs-rust | NIST-standardized ML-KEM/ML-DSA, production-ready, ahead of 2030 mandate |
| Testing | cargo test + pytest | Language-native, supports feature-gated integration tests, mockable HIL |
