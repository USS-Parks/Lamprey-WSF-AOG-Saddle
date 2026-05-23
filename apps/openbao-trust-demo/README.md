# OpenBao-Backed Local Trust Demo

Session 30 reference scaffold #6 (per [BUILD-EXECUTION-PLAN-V2-UPDATED.md](../../../BUILD-EXECUTION-PLAN-V2-UPDATED.md)
§"Sessions 30-31: Application Scaffolds", #6).

Walks the full Trust Manifold three-ring pipeline end-to-end:

```
+-----------------------+        +----------------------------+        +-----------------------+
|  Cloud OpenBao Core   |  --->  |   Lamprey Trust Bridge     |  --->  |  Local Trust Cache    |
|  (simulated here)     |        |   (mint short-lived claim) |        |  (BF-4 store + audit) |
+-----------------------+        +----------------------------+        +-----------------------+
```

The scaffold simulates the cloud bridge locally because BF-6 (the
SDK-side wiring for real `client.trust.*` + `client.auth.exchange_token`
endpoints) lands later. The wire shape is the same — only the source
of the claim swaps.

## What it demonstrates

1. **`simulate_bridge_authentication()`** — builds a short-lived
   [`TrustClaim`](../../mai-sdk-python/src/mai/types.py) with the same
   fields the cloud bridge will return.
2. **`audit_correlation_id()`** — stable per-claim ID used by Session 42's
   audit log to join cloud-side events with local-side decisions.
3. **`check_local_trust_bundle()`** — calls `client.trust.bundle_status()`
   and gracefully falls back when the SDK raises `TrustNotProvisionedError`
   (BF-6 stub today).
4. **`exchange_for_session_token()`** — same pattern against
   `client.auth.exchange_token()`.
5. **`build_lamprey_metadata()`** — assembles the payload S42's
   `AuditFeed` consumes (claim_id, tenant_id, subject_hash,
   service_identity, trust_bundle_version, route_decision,
   correlation_id, bundle state).
6. **`run_inference()`** — sends one authenticated chat completion, with
   the audit metadata pinned into the system prompt for downstream
   middleware to extract.
7. **`print_audit_summary()`** — prints the audit-ready JSON.

## Run

```powershell
$env:MAI_API_KEY = "im-..."
# full pipeline (sends real inference):
python apps/openbao-trust-demo/main.py
# dry-run (steps 1-5 + step 7, no inference call):
python apps/openbao-trust-demo/main.py --dry-run
# custom prompt:
python apps/openbao-trust-demo/main.py --prompt "Summarize my session policy."
```

## Configure

Edit [`config.toml`](config.toml). Sections:

- `[bridge]` — simulated bridge identity + claim TTL
- `[claim]` — identity payload (tenant_id, subject_id, roles, scopes,
  allowed_routes, allowed_models, max_data_classification)
- `[audit]` — correlation-ID prefix
- `[chat]` — model + sampling parameters + default prompt

## Tests

```powershell
pytest apps/openbao-trust-demo/tests/
```

- `test_smoke.py` — every pipeline step in isolation, BF-6 stub
  fallbacks, dry-run mode, config defaults.
- `test_integration.py` — full seven-step run with `httpx.MockTransport`,
  including a verified-bundle path (monkeypatched) and an expired-claim
  refusal path.

## When BF-6 lands

Three call sites change:

1. `simulate_bridge_authentication()` becomes
   `cloud_bridge.authenticate(user_id, device_fingerprint)`.
2. `check_local_trust_bundle()` keeps the same name, but the SDK no
   longer raises and `bundle_status()` returns a real `TrustBundleStatus`.
3. `exchange_for_session_token()` returns a real signed token.

Everything else — the correlation ID, the metadata assembly, the audit
print — stays identical. That continuity is the contract this scaffold
freezes in.
