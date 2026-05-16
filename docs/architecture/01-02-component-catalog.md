# 01-02: Component Catalog

| Component | Crate/Path | Language | Trust | Purpose |
|-----------|------------|----------|-------|---------|
| Model Scheduler | `mai-core/scheduler.rs` | Rust | Trusted | Request routing, priority queues, multi-GPU distribution |
| Model Registry | `mai-core/registry.rs` | Rust | Trusted | Manifest parsing, state machine, versioning, air-gap updates |
| Power State Machine | `mai-core/power.rs` | Rust | Trusted | Sleep transitions, auto-demotion, thermal integration |
| Health Monitor | `mai-core/health.rs` | Rust | Trusted | Heartbeat, telemetry aggregation, alert escalation |
| Hot-Swap Manager | `mai-core/hotswap.rs` | Rust | Trusted | Zero-downtime model/adapter replacement with rollback |
| HIL Traits | `mai-hil/src/traits/` | Rust | Trusted | `HardwareProbe`, `PowerStateController`, `MemoryManager`, `SecureLoadContext` |
| NVIDIA Driver | `mai-hil/src/drivers/nvidia.rs` | Rust | Trusted | NVML-based detection, power limits, VRAM tracking |
| AMD Driver | `mai-hil/src/drivers/amd.rs` | Rust | Trusted | ROCm-based detection and management |
| CPU Driver | `mai-hil/src/drivers/cpu.rs` | Rust | Trusted | AVX-512 fallback compute target |
| TetraMem Stub | `mai-hil/src/drivers/tetramem_stub.rs` | Rust | Trusted | Future QM interface (compiles, returns `NotImplemented`) |
| API Server | `mai-api/src/` | Rust | Trusted | axum REST + tonic gRPC + streaming |
| Vault Interface | `mai-core/vault.rs` | Rust | Trusted | ZFS model storage, PQC ops, audit trail, profiles |
| Backend Adapters | `adapters/` | Python | Untrusted | Ollama, vLLM, llama.cpp, TGI, TensorRT-LLM, ExLlamaV2, SGLang |
| SDKs | `mai-sdk-python/`, `mai-sdk-rs/` | Py/Rust | Neutral | Type-safe client libraries for L4-L5 apps |
