# MAI Compliance Dashboard

The Session 44 compliance dashboard. The single exception to the
"no L6 UI" rule: this thin FastAPI app gives compliance officers,
regulators, and acquirers a way to see and drive every Lamprey
control surface (policy / audit / reports / trust / alerts).

The dashboard talks to the mai-api server via the official Python
SDK (`mai.client.MaiClient`). It holds no state of its own.

## Pages

| Path        | Purpose                                                 |
|-------------|---------------------------------------------------------|
| `/`         | Overview: trust mode, module status, audit integrity    |
| `/audit`    | Tamper-evident audit log viewer (searchable, paginated) |
| `/reports`  | Report listing + generation form + download links       |
| `/policy`   | Per-module toggles + template swap                      |
| `/alerts`   | Live alert feed (subscribe to /v1/compliance/feed)      |
| `/health`   | JSON health probe (used by uptime monitors)             |

## Environment

| Variable                       | Purpose                                | Default                  |
|--------------------------------|----------------------------------------|--------------------------|
| `MAI_DASHBOARD_API_BASE_URL`   | mai-api base URL                       | `http://127.0.0.1:8080/v1` |
| `MAI_DASHBOARD_API_TOKEN`      | API key the SDK sends to mai-api       | (none)                   |
| `MAI_DASHBOARD_ADMIN_TOKEN`    | Token the dashboard demands from users | `dashboard-dev`          |

Every page requires the `X-IM-Auth-Token` header to match
`MAI_DASHBOARD_ADMIN_TOKEN`. This is the dashboard's own gate; the SDK
still authenticates separately against mai-api with its own key.

## Run locally

```bash
pip install fastapi uvicorn jinja2 httpx pydantic
PYTHONPATH=mai-sdk-python/src \
  uvicorn compliance_dashboard.app:app --reload --port 8090
```

Then hit:

```bash
curl -H "X-IM-Auth-Token: dashboard-dev" http://127.0.0.1:8090/
curl -H "X-IM-Auth-Token: dashboard-dev" http://127.0.0.1:8090/health
```

## Tests

```bash
PYTHONPATH=mai-sdk-python/src \
  python -m pytest mai/compliance-dashboard/tests/
```

The test suite stubs the SDK client so no real mai-api is required.

## File layout

- `app.py`           — FastAPI entry point with the six dashboard pages
- `alerts.py`        — Helpers for the SSE alert feed
- `audit_viewer.py`  — Search-form normalisation + row flattening
- `reports.py`       — Generation form + summary aggregation
- `util.py`          — Shared env + SDK client factory + admin gate
- `tests/`           — pytest coverage for each module
