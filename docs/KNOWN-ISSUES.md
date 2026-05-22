# MAI Known Issues

**Project:** Island Mountain Model Abstraction Interface (MAI)
**Last Updated:** 2026-05-22

---

## Active Issues

### 1. Rust Toolchain Availability

**Severity:** Low (development workflow only)
**Affects:** Sessions 11a-11e, all future sessions
**Status:** Resolved in current workspace

This workspace currently has Cargo available (`cargo 1.95.0`). Earlier sessions ran in a sandbox without a Rust toolchain, so older handoff notes may say `cargo check`, `cargo clippy`, and `cargo fmt` could not run in-session. That limitation no longer applies here.

**Action:** Run the standard Rust gates in-session when practical: `cargo check --workspace`, `cargo clippy --workspace -- -D warnings -A clippy::pedantic`, and `cargo fmt --check`.

### 2. cargo fmt Drift

**Severity:** Low (cosmetic)
**Affects:** All Rust files
**Status:** Resolved 2026-05-21, monitor for new drift

Formatting drift accumulated across earlier sessions, then was resolved by the 2026-05-21 CI fix pass across 14 Rust files.

**Action:** Keep running `cargo fmt --check` before marking code sessions complete. If generated protobuf code causes conflicts, add `#[rustfmt::skip]` or exclude in `rustfmt.toml`. See docs/BUILD.md for details.

### 7. Axum 0.7 vs 0.8 Handler Trait Version Conflict

**Severity:** Medium (affects new 2+-extractor handlers that use body extractors)
**Affects:** `mai-api/src/handlers/models.rs` (install_model), `mai-api/src/routes.rs`
**Status:** Workaround in place (Session 24, 2026-05-21)

`tonic 0.12.3` transitively depends on `axum 0.7.9` while `mai-api` directly depends on `axum 0.8.9`. Both export a `Handler` trait. The compiler cannot resolve which `Handler` impl to use for async functions with 2+ extractors when `T3` is a `FromRequest` (body) type that exists in both versions (e.g. `Json<T>`, `Bytes`). Custom `FromRequest` types in `mai-api` also fail because the function type matches the generic pattern of both crate versions before where-clause checking.

**Workaround:** Register body-consuming routes via `post_service(service_fn(...))` (Tower `Service`) instead of `post(handler)` (axum `Handler`). See `routes.rs` and `install_handler_raw` in `handlers/models.rs`.

### 8. Phase 1 Hardware-Dependent Exit Criteria Deferred to Burn-In

**Severity:** Expected (hardware-only verification)
**Affects:** Gate C / Session 34 acceptance
**Status:** Documented 2026-05-22 (Session 35)

Four Phase 1 exit criteria from `MAI-BUILD-PROMPT-ROSTER-v2.md` require target hardware and cannot be verified in CI:

- `test_scout_config_boots` — needs 1x RTX 4090 + Ollama + Qwen3-14B and a <60s timing measurement.
- `test_ranger_config_boots` — needs 2x H100 + vLLM tensor parallel + Qwen3-70B and a <90s timing measurement.
- `test_two_gpu_configs` — needs both NVIDIA and AMD hardware.
- `test_72_hour_stability` — time-dependent.

**Action:** Run these as part of deployment validation on the target hardware. `scripts/burn-in.sh` emits a `phase1-deferred.txt` artifact per run that names them explicitly so the deferral is never silent. See `docs/INTEGRATION-COVERAGE.md` for the full coverage map.

### 9. SDK Apps Scaffold Pending Sessions 29-31

**Severity:** Low (Gate C work-around in place)
**Affects:** Gate C "SDK and at least one app scaffold run against packaged deployment"
**Status:** Smoke-client substitute 2026-05-22 (Session 35); proper scaffolds Sessions 29-31

A full L4-L5 application scaffold is the deliverable of Sessions 29-31 (Developer/App Release Train). For Gate C closure, `tools/smoke/smoke_client.py` is the minimal end-to-end probe that verifies the SDK boundary against a packaged deployment. It exercises health, model list, and scheduler metrics using only the standard library so it runs without an SDK install. When Sessions 29-31 land, replace the smoke client with the real scaffold in the Gate C evidence map.

### 6. Registry scan_models Placeholder

**Severity:** Expected (placeholder)
**Affects:** `mai-api/src/grpc/registry.rs`
**Status:** By design, resolved in Session 15

`ModelRegistry` has no `scan_models()` method. The gRPC `ScanModels` RPC returns an empty list. Session 15 (Model Management) adds the real model scanning and discovery pipeline.

---

## Deferred Items (Out of Scope)

These items are explicitly excluded from the current build. See PROJECT.md for scope boundaries.

- L6 UI (React dashboard, onboarding wizard)
- Remote support tunnel (network service, not MAI)
- Landfall Council (multi-user chat variant)
- Full L4 agent logic (RAG pipeline internals, tool implementations)
- Full L5 application logic (only scaffolds built in Session 16)
- TetraMem adapter implementation (stub interface only via HIL)
- Photonic adapter implementation (stub interface only via HIL)
- Audio/STT binary frame processing (acknowledged in WebSocket, deferred to Session 13)
- Tool calling execution (acknowledged in WebSocket, deferred to Session 13)

---

## Resolved Issues (Historical)

### Session 03 Audit: FFI Blocking Issues (RESOLVED)

Three blocking FFI issues in the Backend Adapter Framework spec. All fixed during Session 03 audit. See SESSION-LOG-ARCHIVE-01.md for details.

### Session 10 CI: pytest Collection Failures (RESOLVED)

Missing `adapters/__init__.py` and AdapterBase constructor signature mismatch. Fixed 2026-05-17. See SESSION-LOG.md maintenance log.

### Session 11d: Invented mai-core APIs (RESOLVED)

All 6 gRPC service files initially coded against non-existent APIs. All rewritten from scratch against verified interfaces during audit. See SESSION-LOG.md Session 11d notes.

### Session 11e: Proto Message Type Mismatches (RESOLVED)

Integration tests used `LoadModelRequest` (doesn't exist), empty `ListModelsRequest` (has profile_id field), ChatMessage with `tool_calls`/`tool_call_id` (proto only has role/content/name). All fixed during Audit Pass 1.

### Issue #3: Sglang Adapter self._raw_config (RESOLVED)

**Resolved:** 2026-05-19 (Adapter Contract Alignment maintenance session)

The Sglang adapter referenced `self._raw_config` in its `initialize()` method, but `AdapterBase` stores config as `self._config`. Fixed by changing to `self._config`. Confirmed via grep: no remaining references to `_raw_config` in the codebase.

### Issue #4: StubVault in Server Bootstrap (RESOLVED)

**Resolved:** Session 12, 2026-05-18

The server used a `StubVault` placeholder. Real ZfsVault now available in mai-vault crate. StubVault retained for bootstrap/testing only.

### Issue #5: Placeholder Token Producers in Streaming (RESOLVED)

**Resolved:** Session 14b, 2026-05-20

Streaming handlers previously used simulated token producers. Session 14b wired the real inference path end-to-end through AdapterManager, connecting adapter IPC output to the SSE streaming channel.

---

*Document derived from MAI-BUILD-PROMPT-ROSTER.md | 2026-05-15 | Island Mountain AI | Confidential*
