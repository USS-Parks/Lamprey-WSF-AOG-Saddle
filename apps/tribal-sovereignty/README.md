# Tribal Data Sovereignty Demo

Session 30 reference scaffold #4. Local-only protected-data flow.
Builds a `TrustClaim` whose `allowed_routes=["local_only"]` and
proves operations *cannot* leak off the local node — the route
guard refuses before the SDK call would even happen.

## What it demonstrates

- **`TrustClaim` shape end-to-end** — the same dataclass the SDK
  ships in `mai.types.TrustClaim`. Mock construction today; real
  exchange via `client.auth.exchange_token(claim)` once BF-6 lands.
- **Sovereignty guard** — two-stage validation:
  - `guard_route(claim, intended_route)` rejects routes not in
    `claim.allowed_routes`.
  - `guard_model(claim, model)` rejects models not in
    `claim.allowed_models`.
- **OCAP-shaped audit metadata** — every request logs
  `tenant_id`, `subject_id`, `subject_hash`, `compliance_scopes`,
  `service_identity`, and `trust_bundle_version` so the eventual
  Lamprey audit layer (Sessions 42-44) can correlate by claim_id.

## Run

```powershell
# Local-only is allowed; cloud is not.
python apps/tribal-sovereignty/main.py "Summarize the corpus" --dry-run

# This should refuse with exit code 4:
python apps/tribal-sovereignty/main.py "Summarize the corpus" `
  --intended-route cloud_allowed --dry-run
```

## How this maps to OCAP enforcement upstream

The mock guard is exactly what `mai-compliance::OcapEvaluator` does
server-side, just earlier in the pipeline. When the policy runtime
HTTP routes land (post-S41), this scaffold's `guard_route` becomes:

```python
decision = client.compliance.decide(metadata)
if decision.route not in claim.allowed_routes:
    raise SovereigntyViolation(...)
```

No app-level changes — the SDK shape was designed against the same
`AggregateDecision` the policy runtime emits.

## Tests

```powershell
pytest apps/tribal-sovereignty/tests/
```

- `test_smoke.py` — guard accepts allowed routes/models, rejects
  forbidden ones, corpus loads under the protected_data dir,
  `--dry-run` does not call the SDK.
- `test_integration.py` — full pipeline: claim → guard pass → chat
  call → response; plus a refusal path showing no SDK call when
  guard fails.
