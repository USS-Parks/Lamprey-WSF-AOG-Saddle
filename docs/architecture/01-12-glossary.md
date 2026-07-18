# 01-12: MAI Glossary

| Term | Definition |
|------|------------|
| MAI | Model Abstraction Interface. L3 sovereign inference layer. |
| HIL | Hardware Interface Layer. Typed trait boundary between core and drivers. |
| TCB | Trusted Computing Base. Rust core + drivers only. |
| Capsule | Untrusted adapter process sandboxed from hardware. |
| Syscall Interface | Stable L3-L4 API contract (REST/gRPC). |
| Air-Gap | Default operational state. Zero network assumptions. |
| Deep Vault Sleep | 2W power state. GPU off, vault locked, WoL active. |
| Sentinel Mode | 8W standby. Small model handles simple tasks. |
| Full Inference | 350W active. Primary models loaded. |
| PQC | Post-Quantum Cryptography. ML-KEM/ML-DSA standard. |
| QM | Quantum Memristor. 2028+ hardware era target. |
| VRAM OOM | Video RAM Out-Of-Memory. Triggers eviction or fallback. |
| LRU Eviction | Least Recently Used model unload to free VRAM. |
| AdapterManager | Rust supervisor for Python adapter processes. |
| SecureLoadContext | HIL trait for TPM-attested, PQC-decrypted model loading. |
| CapabilityDescriptor | Struct describing hardware specs to the scheduler. |
