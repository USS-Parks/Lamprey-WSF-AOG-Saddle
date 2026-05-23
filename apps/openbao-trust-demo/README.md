# OpenBao-Backed Trust Manifold Demo

Proves the Trust Manifold chain end to end: identity enters the trust
plane, a short-lived claim reaches the local node, policy enforces a
local-only route, and the audit log links every event into one
verifiable chain without any regulated payload crossing the cloud
boundary.

```text
+-----------------------+        +----------------------------+        +-----------------------+
|  Cloud OpenBao Core   |  --->  |   Lamprey Trust Bridge     |  --->  |  Local Trust Cache    |
|  (local-dev stub;     |        |   (mint short-lived claim) |        |  (live bundle_status  |
|   one swap to go)     |        |                            |        |   + exchange_token)   |
+-----------------------+        +----------------------------+        +-----------------------+
```

The bridge claim source is a local-dev stub today. Steps 3 and 4,
`GET /v1/trust/bundle_status` and `POST /v1/auth/exchange_token`, hit
live `mai-api` endpoints. Only the body of `exchange_token` swaps when
live OpenBao bring-up lands; the wire shape and everything downstream
stay identical.

---

## What Each Step Proves

| # | What it proves | Function | Live or stub |
|---:|---|---|---|
| 1 | The bridge mints a short-lived `TrustClaim` carrying the same fields a cloud bridge returns: `tenant_id`, `subject_id`, `subject_hash`, `compliance_scopes`, `allowed_routes`, `trust_bundle_version`. | `simulate_bridge_authentication()` | Local-dev stub |
| 2 | A stable `correlation_id` derived from the claim joins cloud-side credential events with local-side policy decisions in the audit log. | `audit_correlation_id()` | No network call |
| 3 | The local node continues operating on its signed bundle even when the cloud trust core is unreachable; `bundle_status` returns a stable shape in both connected and unreachable states. | `check_local_trust_bundle()` -> `client.trust.bundle_status()` | Live endpoint |
| 4 | The local node exchanges the claim for a session token; the call degrades gracefully to a claim-derived placeholder if the server is down. | `exchange_for_session_token()` -> `client.auth.exchange_token()` | Live endpoint |
| 5 | Lamprey assembles the full audit payload before inference runs: claim ID, tenant, subject hash, service identity, bundle version, route decision, correlation ID. | `build_lamprey_metadata()` | No network call |
| 6 | An authenticated inference request routes through the compliance engine; audit metadata travels with the request for downstream middleware. | `run_inference()` | Live endpoint |
| 7 | The audit summary prints a JSON object linking credential event, policy decision, and inference request via `correlation_id`, the join key into the tamper-evident audit chain. | `print_audit_summary()` | No network call |
| 8 | An expired or degraded bundle forces restricted routing; the degraded-bundle integration test exercises the full `Connected -> Degraded -> Stale -> Expired` state path. | `test_integration.py` degraded-bundle path | Test-controlled |

---

## Runbook

### Prerequisites

- `mai-api` running on port 8420: `cargo run --bin mai-api`
- API key from first-boot stdout: `$env:MAI_API_KEY = "im-..."`
- Python dependencies installed: `pip install -e mai-sdk-python`

### Run

```powershell
# Verify tests pass against live endpoints first:
pytest apps/openbao-trust-demo/tests/ -v

# Dry-run: steps 1-5 and 7, no inference call:
python apps/openbao-trust-demo/main.py --dry-run

# Full pipeline: all seven steps including inference:
python apps/openbao-trust-demo/main.py

# Custom prompt:
python apps/openbao-trust-demo/main.py --prompt "Summarize my session policy."
```

### Expected Output

A successful run prints an audit-ready JSON summary:

```json
{
  "claim_id": "claim-<uuid>",
  "tenant_id": "im-demo",
  "subject_hash": "sha256:<32 hex>",
  "service_identity": "openbao-trust-bridge",
  "trust_bundle_version": "local-dev",
  "route_decision": "local_only",
  "correlation_id": "openbao-demo-claim-<uuid>",
  "bundle_state": "live",
  "bundle_connectivity": "connected",
  "bundle_signature_verified": true
}
```

`bundle_signature_verified: true` confirms the local trust cache
accepted the signed bundle. `route_decision: local_only` confirms
Lamprey enforced the compliance scope.

### Verify The Audit Chain

With the `correlation_id` from the output, query and re-verify the
chain against the live API:

```powershell
# Pull the correlated audit chain:
curl "http://localhost:8420/v1/compliance/audit?correlation_id=openbao-demo-claim-<uuid>" `
  -H "X-IM-Auth-Token: $env:MAI_API_KEY"

# Re-verify chain integrity:
curl -X POST "http://localhost:8420/v1/compliance/audit/verify" `
  -H "X-IM-Auth-Token: $env:MAI_API_KEY"
```

Chain verification uses BLAKE3 link integrity plus ML-DSA-87 periodic
signatures. Off-host re-verification requires only the public key and
canonical JSON: no MAI source code and no vendor trust.

### Exercise Degraded-Bundle Behavior

Run the integration test that expires the bundle and confirms routing
tightens:

```powershell
pytest apps/openbao-trust-demo/tests/test_integration.py -v -k "degraded_bundle"
```

The test confirms that `LocalTrustCache` transitions through
`Connected`, `Degraded`, `Stale`, and `Expired`, and that the policy
composer restricts routes at each boundary. The audit log records the
refusal with the expired bundle version and the `correlation_id`
intact.

---

## Configure

Edit [config.toml](config.toml):

- `[bridge]`: bridge identity and claim TTL used by the local-dev stub;
  fields match the cloud bridge schema.
- `[claim]`: identity payload: `tenant_id`, `subject_id`, `roles`,
  `compliance_scopes`, `allowed_routes`, `allowed_models`,
  `max_data_classification`.
- `[audit]`: correlation-ID prefix.
- `[chat]`: model, sampling parameters, default prompt.

---

## Tests

```powershell
pytest apps/openbao-trust-demo/tests/ -v
```

`test_smoke.py` proves each of the seven pipeline steps in isolation.
It covers live-endpoint calls, unreachable-server fallback behavior,
dry-run mode, and config defaults.

`test_integration.py` proves the full pipeline end to end using
`httpx.MockTransport`. It includes the degraded-bundle path and an
expired-claim refusal path, and confirms the audit chain shape at each
stage.

---

## Production Swap Contract

When live OpenBao bring-up lands, exactly one call site changes:

```python
simulate_bridge_authentication()
```

becomes:

```python
cloud_bridge.authenticate(user_id, device_fingerprint)
```

Steps 3 and 4 already hit live endpoints. Only the body of
`POST /v1/auth/exchange_token` swaps from the local-dev token stub to
real OpenBao Transit signing. The `correlation_id`, metadata assembly,
audit print, and chain verification call are identical before and
after. That continuity is the contract this scaffold freezes in, and
the guarantee that no client code moves when the bridge goes live.

See [BUYER-INTEGRATION-GUIDE.md](../../../docs/BUYER-INTEGRATION-GUIDE.md)
for the full swap contract and wire-shape guarantee.
