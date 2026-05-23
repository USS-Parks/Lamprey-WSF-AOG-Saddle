# Compliance-Routed

Session 30 reference scaffold #3. Placeholder for the integration
point Lamprey (Sessions 36-44) will fill. Runs a **local mock router**
today whose decision shape matches what the real
`/v1/compliance/decide` endpoint will return.

## What it demonstrates

- The exact `RouteDecision` shape applications will receive from
  Lamprey: `route`, `flags`, `reason`, `policy_version`, `decided_by`.
- Rule evaluation order: first-match-wins over a TOML table.
- Conservative fallback: if no rule matches, the decision is `deny`
  with `NO_MATCHING_RULE`.
- How an app dispatches based on a decision (`local_only` /
  `local_preferred` -> server; `deny` -> refuse; `cloud_allowed` ->
  reserved for the future cloud transport).

## Run

```powershell
python apps/compliance-routed/main.py "Summarize this" `
  --scope ocap --classification tribal_protected --decision-only
```

Sample stderr output:
```json
{
  "decision": {
    "route": "local_only",
    "flags": ["OCAP_REQUIRED", "NO_CLOUD"],
    "reason": "OCAP-governed data; cloud routing forbidden",
    "matched_rule_index": 0,
    "decided_by": "local-mock",
    "policy_version": "mock-v0"
  }
}
```

Drop `--decision-only` to actually dispatch the chat (requires a
reachable MAI server).

## How to migrate to real Lamprey

Replace `MockComplianceRouter` with the SDK call once it lands:

```python
# today
router = MockComplianceRouter(cfg["routing"]["rules"])
decision = router.decide(metadata)

# post-S41-HTTP-wiring (deferred to its own session)
decision = client.compliance.decide(metadata)
```

The `RouteDecision` dataclass is wire-compatible with
`mai-compliance::AggregateDecision` (route, flags, reason,
policy_version, decided_by). No app-side refactor needed.

## Tests

```powershell
pytest apps/compliance-routed/tests/
```

- `test_smoke.py` — each rule path resolves to the right decision; no
  matching rule yields `deny`; `--decision-only` skips the SDK.
- `test_integration.py` — full pipe: decision + dispatch + chat
  response under each scope class.
