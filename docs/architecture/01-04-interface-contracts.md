# 01-04: Interface Contract Index

| Contract | Defined In | Implemented In | Stability |
|----------|------------|----------------|-----------|
| HIL Traits (`HardwareProbe`, `PowerStateController`, `MemoryManager`, `SecureLoadContext`) | Session 02 | Session 06 | Hardware-generation agnostic |
| `InferenceAdapter` Trait + `AdapterBase` | Session 03 | Session 08 | Backend-agnostic |
| Core Kernel APIs (Scheduler, Registry, Health, Power, HotSwap) | Session 04 | Session 07 | Trusted TCB |
| REST API (OpenAPI 3.1) | Session 05 | Session 11 | Backward-compatible |
| gRPC API (Proto3) | Session 05 | Session 11 | Low-latency internal |
| Streaming Protocol (SSE + WebSocket) | Session 05 | Session 11 | Token-delta standard |
| Python/Rust SDKs | Session 05 | Session 11 | Application compile target |
| Vault Interface (ZFS, PQC, Profiles, Audit) | Session 12 | Session 12 | Sovereign storage boundary |
| Agent/RAG Interface | Session 13 | Session 13 | Context & tool routing |
| Model Package Format | Session 15 | Session 15 | Air-gap update standard |
