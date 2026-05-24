# MAI Compliance Dashboard

The compliance dashboard is the operator-facing proof surface for MAI's
Lamprey governance layer. It gives compliance officers, regulators, and
acquirers a single UI to see trust state, inspect audit decisions, drive
policy, generate signed compliance reports, and watch the live alert
feed without writing code or calling APIs directly.

The dashboard talks to the `mai-api` server through the official Python
SDK (`mai.client.MaiClient`). It holds no state of its own. Every value
it displays comes from a live SDK call; every action it takes drives a
live API endpoint. The audit chain, policy decisions, and signed reports
all live in `mai-api`. The dashboard is the window into them, not the
record itself.

---

## Who Uses This And For What

### Compliance Officer: Routine Review

A compliance officer doing a routine review of AI activity on a
regulated node follows this sequence:

1. **Overview (`/`):** confirm trust mode is `connected` and audit
   integrity is clean before looking at anything else. If the trust
   panel shows `degraded` or `stale`, investigate before proceeding.
2. **Audit (`/audit`):** filter by tenant and date range. Confirm every
   decision has a `correlation_id` and `policy_version`. Look for any
   `route_decision` values other than `local_only_allowed` on HIPAA- or
   OCAP-scoped requests.
3. **Reports (`/reports`):** generate the period report for the relevant
   template: HIPAA, ITAR, or OCAP. Download it. The report carries a
   `TrustSection` and an ML-DSA-87 certification signature that can be
   verified off-host.
4. **Monitoring (`/monitoring`):** confirm live/ready/production probes,
   scheduler queue depth, power state, air-gap posture, trust state,
   audit integrity, and Prometheus metrics exposure.
5. **Alerts (`/alerts`):** review flagged events from the period.
   Alerts are emitted by the `/v1/compliance/feed` SSE stream in real
   time; the page replays recent events on load.

### Regulator: Spot Audit

A regulator conducting a spot audit needs to trace a specific decision
or incident from identity to outcome:

1. **Audit (`/audit`):** search by `correlation_id`, tenant, policy
   module, or date range to locate the relevant entries. Each row shows
   the credential event ID, Lamprey decision ID, MAI request ID, route
   decision, and policy version that governed it.
2. **Overview (`/`):** confirm the trust bundle version and signature
   status. The trust panel shows current state; audit entries carry the
   bundle version active when each decision was made.
3. **Reports (`/reports`):** generate a signed report for the period
   and verify the certification signature with `verify_certified_report`
   off-host. The ML-DSA-87 signature over canonical JSON means
   verification requires only the public key, not access to MAI.

### Acquirer: Technical Due Diligence

An acquirer's technical reviewer can use the dashboard to verify the
five defensible points from `ACQUISITION-PACKAGE.md`:

1. **Overview (`/`):** confirm `mode=connected`, bundle version, claim
   count, offline backlog, and `bundle_signature_verified=true`.
   Disconnect the cloud trust core and confirm the panel transitions to
   `degraded` without interrupting the dashboard.
2. **Policy (`/policy`):** confirm active modules, their enable/disable
   state, and the compliance template. Toggle a module off and on;
   confirm the change takes effect without restarting the server.
3. **Audit (`/audit`):** filter by a known `correlation_id` from the
   Trust Manifold demo. Confirm the credential, decision, and inference
   events are present and linked.
4. **Reports (`/reports`):** generate HIPAA and OCAP reports. Confirm
   each carries a `TrustSection`, then verify a certification off-host.
5. **Monitoring (`/monitoring`):** confirm readiness, production safety,
   scheduler pressure, and metrics exposure before driving the demo.
6. **Alerts (`/alerts`):** confirm events arrive in real time as
   requests route through Lamprey.

---

## Pages

| Path | What it shows | What you can establish from it |
|---|---|---|
| `/` | Trust mode, connectivity state, bundle version and signature status, compliance module status, audit chain integrity | Whether the node is operating on a valid signed bundle; whether the audit chain has been tampered with; which policy modules are active |
| `/audit` | Tamper-evident audit log, searchable by tenant, module, route decision, date range, and correlation ID | The full decision trail for any request: which credential authorized it, which policy governed it, what route was assigned, which bundle version was active |
| `/reports` | Report listing, generation form, download links | Signed compliance reports for HIPAA, ITAR, OCAP, SystemActivity, and MonthlyDigest; each carries a TrustSection and an ML-DSA-87 certification verifiable off-host |
| `/policy` | Per-module enable/disable toggles, compliance template selector, policy reload | Live policy configuration; changes take effect immediately without restarting the server |
| `/alerts` | Live alert feed from the `/v1/compliance/feed` SSE stream | Real-time visibility into policy decisions and flagged events as they happen |
| `/monitoring` | Live/ready/production probes, runtime utilization, scheduler queue, power and air-gap posture, trust/audit state, Prometheus family count | Whether the node is safe to receive traffic, whether capacity is under pressure, and whether machine monitoring is wired |
| `/health` | JSON health probe | Whether the dashboard can reach `mai-api` and the SDK is authenticated; used by uptime monitors |

---

## Authentication

The dashboard has two independent authentication layers.

**Dashboard gate:** every page requires the `X-IM-Auth-Token` request
header to match `MAI_DASHBOARD_ADMIN_TOKEN`. This gate controls who can
open the dashboard UI. The default token for local development is
`dashboard-dev`; set a strong value in production.

**SDK gate:** the dashboard authenticates against `mai-api` using
`MAI_DASHBOARD_API_TOKEN` as the SDK's API key. This key governs what
the dashboard can read and write from the API. It is separate from the
dashboard gate and must be set independently.

A request that clears the dashboard gate but uses an invalid API token
will reach the dashboard pages but receive API errors on every data
fetch. Set both tokens before opening the UI.

---

## Environment

| Variable | Purpose | Default |
|---|---|---|
| `MAI_DASHBOARD_API_BASE_URL` | `mai-api` base URL: the backend, not the dashboard | `http://127.0.0.1:8080/v1` |
| `MAI_DASHBOARD_API_TOKEN` | API key the SDK sends to `mai-api` | (none) |
| `MAI_DASHBOARD_ADMIN_TOKEN` | Token the dashboard requires from users | `dashboard-dev` |

The dashboard itself runs on a separate port, 8090 in the command below.
`MAI_DASHBOARD_API_BASE_URL` is the address of the `mai-api` backend,
not the dashboard's own address.

---

## Run

```powershell
pip install fastapi uvicorn jinja2 httpx pydantic

$env:PYTHONPATH = "mai-sdk-python/src"
$env:MAI_DASHBOARD_API_TOKEN = "im-..."
uvicorn compliance_dashboard.app:app --reload --port 8090
```

Confirm both layers are working:

```powershell
# Dashboard gate + health probe:
curl -H "X-IM-Auth-Token: dashboard-dev" http://127.0.0.1:8090/health

# Dashboard gate + overview page:
curl -H "X-IM-Auth-Token: dashboard-dev" http://127.0.0.1:8090/
```

A healthy response from `/health` confirms the dashboard reached
`mai-api` and the SDK authenticated successfully.

---

## Tests

```powershell
$env:PYTHONPATH = "mai-sdk-python/src"
python -m pytest mai/compliance-dashboard/tests/
```

The test suite stubs the SDK client; no running `mai-api` is required.
Twenty-two tests cover each module: overview trust-panel rendering, audit
search and row flattening, report generation and summary aggregation,
SSE alert feed parsing, monitoring panel rendering, policy toggle
handling, and the admin gate.

---

## File Layout

- `app.py`: FastAPI entry point with the seven dashboard pages.
- `alerts.py`: helpers for the SSE alert feed.
- `audit_viewer.py`: search-form normalization and row flattening.
- `monitoring.py`: operator monitoring panel collectors.
- `reports.py`: generation form and summary aggregation.
- `util.py`: shared env, SDK client factory, and admin gate.
- `tests/`: pytest coverage for each module.
