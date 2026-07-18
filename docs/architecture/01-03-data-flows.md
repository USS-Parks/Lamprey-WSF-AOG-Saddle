# 01-03: Data Flow Diagrams

## Inference Request Lifecycle

1. `App` -> `POST /v1/chat/completions`
2. `API Server` validates `X-IM-Profile` header, checks rate limits
3. Request enters `Scheduler` queue with priority tier
4. `Scheduler` queries `Registry` for loaded models & capabilities
5. If no model loaded: check Sentinel capability -> if insufficient, trigger `Full Inference` promotion
6. `Scheduler` selects optimal adapter (round-robin, least-loaded, affinity)
7. `AdapterManager` routes to Python adapter process via PyO3 FFI
8. Adapter streams tokens from backend
9. Tokens flow upstream -> `API Server` -> SSE/WebSocket -> `App`
10. `Audit Middleware` writes PQC-signed entry to vault (local-only)

## Model Load/Unload Cycle

`Request` -> `Registry` parses TOML manifest -> `MemoryManager` checks VRAM -> `SecureLoadContext` verifies SHA-256 hash tree -> TPM unseals ML-KEM key -> ZFS decrypts weights -> VRAM map -> Adapter health-check -> `Registry` state: `loaded` -> `active`

## Sleep Transitions (GPU Era)

`DeepVault (2W)` -> Wake trigger -> `Sentinel (8W, configured small model)` -> Request exceeds capability -> Queue -> GPU wake -> `Full Inference (350W, configured primary models)` -> Serve -> 12min idle -> Auto-demote -> `Sentinel` -> 2hr idle -> `DeepVault`
