"""End-to-end coverage for the compliance dashboard.

Stubs the SDK client so no real mai-api server is required.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure both the SDK src dir and the dashboard parent are importable.
_DASH_PARENT = Path(__file__).resolve().parents[2]
_SDK_SRC = _DASH_PARENT / "mai-sdk-python" / "src"
for path in (_DASH_PARENT, _SDK_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _import_dashboard():
    # Import via the *hyphenated* directory by aliasing the module path.
    spec = importlib.util.spec_from_file_location(
        "compliance_dashboard.app",
        _DASH_PARENT / "compliance-dashboard" / "app.py",
        submodule_search_locations=[str(_DASH_PARENT / "compliance-dashboard")],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load compliance_dashboard.app")
    # Create the package shell so the relative imports inside app.py resolve.
    pkg_spec = importlib.util.spec_from_file_location(
        "compliance_dashboard",
        _DASH_PARENT / "compliance-dashboard" / "__init__.py",
        submodule_search_locations=[str(_DASH_PARENT / "compliance-dashboard")],
    )
    pkg = importlib.util.module_from_spec(pkg_spec)  # type: ignore[arg-type]
    sys.modules["compliance_dashboard"] = pkg
    pkg_spec.loader.exec_module(pkg)  # type: ignore[union-attr]

    for sub in ("util", "alerts", "audit_viewer", "reports"):
        sub_spec = importlib.util.spec_from_file_location(
            f"compliance_dashboard.{sub}",
            _DASH_PARENT / "compliance-dashboard" / f"{sub}.py",
        )
        mod = importlib.util.module_from_spec(sub_spec)  # type: ignore[arg-type]
        sys.modules[f"compliance_dashboard.{sub}"] = mod
        sub_spec.loader.exec_module(mod)  # type: ignore[union-attr]

    module = importlib.util.module_from_spec(spec)
    sys.modules["compliance_dashboard.app"] = module
    spec.loader.exec_module(module)
    return module


app_module = _import_dashboard()


def _stub_client() -> MagicMock:
    """Build a MagicMock that mirrors the slice of MaiClient we use."""
    from mai.types import (
        AuditQueryResponse,
        ComplianceIntegrity,
        ComplianceModuleStatus,
        ComplianceReport,
        ComplianceReportList,
        ComplianceStatus,
        TrustBundleStatus,
        TrustClaimsResponse,
        TrustStatusResponse,
    )

    client = MagicMock()
    client.trust.status.return_value = TrustStatusResponse(
        mode="air-gapped",
        bundle_version=None,
        last_refresh_secs=None,
        age_secs=None,
        claim_count=0,
        airgap={"connectivity": "air-gapped", "permits_cloud_route": False,
                "requires_local_only": True, "is_air_gapped": True},
        offline_backlog=0,
    )
    client.trust.bundle_status.return_value = TrustBundleStatus(
        bundle_version=None, last_refresh_secs=None, age_secs=None,
        connectivity="air-gapped", is_emergency_only=False,
    )
    client.trust.claims.return_value = TrustClaimsResponse(claims=[], total=0)

    integrity = ComplianceIntegrity(
        entry_count=0, chain_count=0, head_hash="00" * 32,
        last_verify="unknown", last_verify_error=None,
    )
    client.compliance.get_status.return_value = ComplianceStatus(
        modules=[ComplianceModuleStatus(module="hipaa", enabled=True, priority=0)],
        priority=["hipaa"], reload_count=0,
        audit_integrity=integrity, subscribers=0,
    )
    client.compliance.get_policies.return_value = [
        {"module": "hipaa", "enabled": True, "priority": 0},
    ]
    client.compliance.query_audit.return_value = AuditQueryResponse(rows=[], total=0)
    client.compliance.list_reports.return_value = ComplianceReportList(reports=[], total=0)
    sample_report = ComplianceReport(
        id="rep-1", report_type="system_activity", status="complete",
        output_format="json", from_unix_nanos=0, to_unix_nanos=100,
        tenant=None, created_at_unix_nanos=1, completed_at_unix_nanos=2,
        content_hash_hex="ab" * 32, signature_hex=None, error=None,
        protected=False, schedule_id=None,
    )
    client.compliance.get_report.return_value = sample_report
    client.compliance.download_report.return_value = b'{"hi": true}'
    client.compliance.generate_report.return_value = sample_report
    client.compliance.update_policy.return_value = {
        "module": "hipaa", "enabled": False, "changed": True,
    }
    client.compliance.apply_template.return_value = {"template": "defense"}
    return client


@pytest.fixture
def client():
    stub = _stub_client()
    app_module.app.dependency_overrides[app_module.get_client] = lambda: stub
    try:
        yield TestClient(app_module.app), stub
    finally:
        app_module.app.dependency_overrides.clear()


def _auth() -> dict[str, str]:
    return {"X-IM-Auth-Token": "dashboard-dev"}


def test_unauthenticated_request_is_rejected(client) -> None:
    tc, _ = client
    r = tc.get("/")
    assert r.status_code == 401


def test_overview_renders_trust_and_module_state(client) -> None:
    tc, _ = client
    r = tc.get("/", headers=_auth())
    assert r.status_code == 200
    assert "Trust Manifold" in r.text
    assert "air-gapped" in r.text
    assert "hipaa" in r.text


def test_audit_page_renders_form_even_with_empty_results(client) -> None:
    tc, _ = client
    r = tc.get("/audit", headers=_auth())
    assert r.status_code == 200
    assert "Results (0)" in r.text


def test_audit_search_passes_filters_to_sdk(client) -> None:
    tc, stub = client
    r = tc.get("/audit?module=hipaa&decision=deny&limit=25", headers=_auth())
    assert r.status_code == 200
    stub.compliance.query_audit.assert_called_once_with(
        limit=25, module="hipaa", decision="deny",
    )


def test_reports_page_renders_generate_form(client) -> None:
    tc, _ = client
    r = tc.get("/reports", headers=_auth())
    assert r.status_code == 200
    assert "Generate report" in r.text
    assert "HIPAA Audit Trail" in r.text


def test_reports_generate_round_trips(client) -> None:
    tc, stub = client
    r = tc.post(
        "/reports/generate",
        data={
            "report_type": "system_activity",
            "from_unix_nanos": "0",
            "to_unix_nanos": "1000",
            "format": "json",
            "tenant": "acme",
        },
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["id"] == "rep-1"
    stub.compliance.generate_report.assert_called_once()


def test_reports_generate_rejects_inverted_range(client) -> None:
    tc, _ = client
    r = tc.post(
        "/reports/generate",
        data={
            "report_type": "system_activity",
            "from_unix_nanos": "1000",
            "to_unix_nanos": "0",
            "format": "json",
        },
        headers=_auth(),
    )
    assert r.status_code == 400


def test_reports_download_returns_body_bytes(client) -> None:
    tc, stub = client
    r = tc.get("/reports/rep-1/download", headers=_auth())
    assert r.status_code == 200
    assert r.content == b'{"hi": true}'
    assert r.headers["content-type"].startswith("application/json")
    stub.compliance.download_report.assert_called_once_with("rep-1")


def test_policy_page_renders_template_picker_and_modules(client) -> None:
    tc, _ = client
    r = tc.get("/policy", headers=_auth())
    assert r.status_code == 200
    assert "Templates" in r.text
    assert "hipaa" in r.text


def test_policy_toggle_passes_enabled_to_sdk(client) -> None:
    tc, stub = client
    r = tc.post("/policy/hipaa/toggle", data={"enabled": "false"}, headers=_auth())
    assert r.status_code == 200
    stub.compliance.update_policy.assert_called_once_with("hipaa", enabled=False)


def test_policy_template_apply_calls_sdk(client) -> None:
    tc, stub = client
    r = tc.post("/policy/template", data={"template": "defense"}, headers=_auth())
    assert r.status_code == 200
    stub.compliance.apply_template.assert_called_once_with("defense")


def test_alerts_page_lists_event_kinds(client) -> None:
    tc, _ = client
    r = tc.get("/alerts", headers=_auth())
    assert r.status_code == 200
    assert "decision_made" in r.text
    assert "violation_detected" in r.text


def test_health_returns_module_and_integrity_snapshot(client) -> None:
    tc, _ = client
    r = tc.get("/health", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["healthy"] is True
    assert body["modules"][0]["module"] == "hipaa"
    assert body["audit_integrity"]["last_verify"] == "unknown"


def test_health_reports_unhealthy_when_sdk_raises(client) -> None:
    tc, stub = client
    from mai.errors import MaiError

    stub.compliance.get_status.side_effect = MaiError("upstream down")
    r = tc.get("/health", headers=_auth())
    assert r.status_code == 502
    assert r.json()["healthy"] is False


# ─── Module-level helper coverage ────────────────────────────────

def test_alerts_severity_mapping() -> None:
    from compliance_dashboard.alerts import severity_for

    assert severity_for("decision_made") == "info"
    assert severity_for("policy_changed") == "info"
    assert severity_for("module_state_changed") == "warning"
    assert severity_for("violation_detected") == "critical"
    assert severity_for("garbage") == "info"


def test_alerts_alert_from_event_round_trip() -> None:
    from compliance_dashboard.alerts import alert_from_event

    alert = alert_from_event({
        "kind": "violation_detected",
        "timestamp_unix_ms": 1234,
        "tenant_id": "acme",
        "request_id": "r-1",
        "decision": {"allowed": False},
    })
    assert alert.severity == "critical"
    assert alert.timestamp_unix_ms == 1234
    assert "acme" in alert.headline


def test_audit_filter_sdk_kwargs_omits_none() -> None:
    from compliance_dashboard.audit_viewer import AuditFilter

    f = AuditFilter()
    assert f.sdk_kwargs() == {"limit": 50}
    f2 = AuditFilter(module="hipaa", decision="deny", tenant="acme", limit=10)
    kwargs = f2.sdk_kwargs()
    assert kwargs == {
        "limit": 10, "module": "hipaa", "decision": "deny", "tenant": "acme",
    }


def test_audit_normalisation_rejects_unknown_values() -> None:
    from compliance_dashboard.audit_viewer import (
        clamp_limit, normalise_decision, normalise_module,
    )

    assert normalise_module("HIPAA") == "hipaa"
    assert normalise_module("garbage") is None
    assert normalise_decision("DENY") == "deny"
    assert normalise_decision("escalate") is None
    assert clamp_limit(0) == 50
    assert clamp_limit(10_000) == 500


def test_reports_generate_form_validation() -> None:
    from compliance_dashboard.reports import GenerateForm

    good = GenerateForm(
        report_type="system_activity",
        from_unix_nanos=0, to_unix_nanos=10, format="json",
    )
    assert good.validate() == []
    bad = GenerateForm(
        report_type="invented", from_unix_nanos=10, to_unix_nanos=0,
        format="pdf",
    )
    errors = bad.validate()
    assert any("Unknown report template" in e for e in errors)
    assert any("Unsupported format" in e for e in errors)
    assert any("to_unix_nanos" in e for e in errors)


def test_reports_summarise_counts_status_groups() -> None:
    from compliance_dashboard.reports import summarise
    from mai.types import ComplianceReport

    def _r(status: str, protected: bool = False) -> ComplianceReport:
        return ComplianceReport(
            id=f"r-{status}", report_type="system_activity",
            status=status, output_format="json",
            from_unix_nanos=0, to_unix_nanos=1,
            tenant=None, created_at_unix_nanos=1,
            completed_at_unix_nanos=1, content_hash_hex=None,
            signature_hex=None, error=None, protected=protected,
            schedule_id=None,
        )

    summary = summarise([
        _r("complete"), _r("complete", protected=True),
        _r("pending"), _r("failed"),
    ])
    assert summary.total == 4
    assert summary.complete == 2
    assert summary.pending == 1
    assert summary.failed == 1
    assert summary.protected == 1
