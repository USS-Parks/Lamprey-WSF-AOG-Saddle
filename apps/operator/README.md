# Operator/Admin Dashboard

Session 30 reference scaffold #5. Read-only snapshot of every plane
of a local MAI instance: models, scheduler, adapters, power, air-gap
status, audit-log preview, trust-bundle state. Plain-text or JSON
output. Designed for cron and on-call use, not pretty TUI.

## What it demonstrates

- Coverage across the SDK's read-side namespaces (`client.models`,
  `client.scheduler`, `client.admin`, `client.power`, `client.system`,
  `client.trust`).
- Graceful degradation — each panel catches its own errors via the
  `_safe()` helper; one failing area doesn't kill the dashboard.
- Trust-bundle panel demonstrates the BF-6 stub path (currently
  reports `not-provisioned`; flips to real state once BF-6 lands).
- Non-zero exit only if a **core** panel (models/scheduler/power/airgap)
  fails — perfect for monitoring.

## Run

```powershell
python apps/operator/main.py
python apps/operator/main.py --json | jq '.panels[].name'
```

Sample output:
```
=== MAI Operator Dashboard ===
[OK ] models     2/3 loaded
[OK ] scheduler  queue=0 active=1 p95=2.5ms
[OK ] adapters   1 adapter(s)
[OK ] power      state=full_inference ~220W
[OK ] airgap     enabled=True verified=True net=air_gap_compliant
[OK ] audit      120 total, showing 10
[ERR] trust      not-provisioned
      ! trust API is not provisioned in this build (BF-6 pending)...
```

## Configure

Edit [`config.toml`](config.toml). Each `[display].<panel>` flag
toggles a section. `audit_limit` caps the audit-log preview rows.

## Tests

```powershell
pytest apps/operator/tests/
```

- `test_smoke.py` — each `_safe()` panel renders OK with mocked endpoints,
  graceful error rendering for failed panels, trust BF-6 stub flows.
- `test_integration.py` — full dashboard render under a synthetic
  server with all panels populated; exit code 0 when all core panels
  green; exit code 5 when a core panel errors.

## Migration once BF-6/audit endpoints land

- `panel_trust` already calls `client.trust.bundle_status()` — that
  starts returning real `TrustBundleStatus` instances; no code change.
- `panel_audit` already uses `client.admin.audit_log()`; once the
  audit log is enriched with BF-5 correlation fields, the existing
  panel just picks them up.
