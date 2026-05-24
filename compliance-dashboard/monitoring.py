"""Operator monitoring helpers for the MAI dashboard.

The dashboard is intentionally a thin window over ``mai-api``. This
module gathers the live operational surfaces into small, renderable
panels without storing state of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mai.client import MaiClient


@dataclass(frozen=True)
class MonitorPanel:
    """A compact operator panel rendered by ``/monitoring``."""

    name: str
    state: str
    summary: str
    rows: list[tuple[str, str]] = field(default_factory=list)
    error: str | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _first(value: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return default


def _state_for_status(status_code: int) -> str:
    if status_code < 300:
        return "ok"
    if status_code < 500:
        return "warn"
    return "crit"


def _raw_get(client: MaiClient, path: str) -> tuple[int, Any]:
    """Read an endpoint, preserving non-2xx status bodies when possible."""

    transport = getattr(client, "_http", None)
    if transport is not None and hasattr(transport, "get"):
        response = transport.get(path)
    else:
        response = client._request_with_retry("GET", path)

    status_code = int(getattr(response, "status_code", 200))
    try:
        payload = response.json()
    except Exception:
        payload = getattr(response, "text", "")
    return status_code, payload


def _raw_json(client: MaiClient, path: str) -> dict[str, Any]:
    status_code, payload = _raw_get(client, path)
    if status_code >= 400:
        raise RuntimeError(f"{path} returned HTTP {status_code}")
    return payload if isinstance(payload, dict) else {}


def _safe_panel(name: str, collector) -> MonitorPanel:  # type: ignore[no-untyped-def]
    try:
        return collector()
    except Exception as exc:
        return MonitorPanel(
            name=name,
            state="crit",
            summary="unavailable",
            error=f"{type(exc).__name__}: {exc}",
        )


def panel_probes(client: MaiClient) -> MonitorPanel:
    """Collect live / ready / production health probe status."""

    rows: list[tuple[str, str]] = []
    worst = "ok"
    for label, path in (
        ("live", "/health/live"),
        ("ready", "/health/ready"),
        ("production", "/health/production"),
    ):
        status_code, payload = _raw_get(client, path)
        state = _state_for_status(status_code)
        if state == "crit":
            worst = "crit"
        elif state == "warn" and worst == "ok":
            worst = "warn"
        body = payload if isinstance(payload, dict) else {}
        status = body.get("status", "unknown")
        reasons = body.get("reasons") or []
        reason_text = f" ({', '.join(str(r) for r in reasons)})" if reasons else ""
        rows.append((label, f"HTTP {status_code} / {status}{reason_text}"))

    summary = "all probes passing" if worst == "ok" else "probe attention required"
    return MonitorPanel("Health probes", worst, summary, rows)


def panel_runtime(client: MaiClient) -> MonitorPanel:
    """Collect aggregate health and resource utilization."""

    health = _raw_json(client, "/health")
    system = _as_dict(health.get("system", {}))
    hardware = _as_dict(health.get("hardware", {}))
    adapters = health.get("adapters", [])
    adapter_count = len(adapters) if isinstance(adapters, list) else 0
    status = str(health.get("status", "unknown"))
    state = "ok" if status == "healthy" else "warn" if status == "degraded" else "crit"
    rows = [
        ("alert", str(health.get("alert_level", status))),
        ("adapters", str(adapter_count)),
        ("air gap", str(hardware.get("air_gap_status", hardware.get("network_state", "unknown")))),
        ("cpu", f"{float(system.get('cpu_utilization_percent', 0.0)):.1f}%"),
        ("ram", f"{float(system.get('ram_utilization_percent', 0.0)):.1f}%"),
        ("disk", f"{float(system.get('disk_utilization_percent', 0.0)):.1f}%"),
    ]
    return MonitorPanel("Runtime", state, status, rows)


def panel_scheduler(client: MaiClient) -> MonitorPanel:
    """Collect scheduler queue and anomaly state."""

    metrics = _as_dict(client.scheduler.metrics())
    anomalies = _as_dict(client.scheduler.anomalies())
    anomaly_rows = anomalies.get("anomalies", [])
    anomaly_count = len(anomaly_rows) if isinstance(anomaly_rows, list) else 0
    queue_depth = int(_first(metrics, "queue_depth", "total_queue_depth", default=0) or 0)
    rejected = int(_first(metrics, "rejected_total", "total_rejected", default=0) or 0)
    active = int(_first(metrics, "active_requests", "requests_in_flight", default=0) or 0)
    state = "crit" if anomaly_count else "warn" if queue_depth > 0 else "ok"
    rows = [
        ("queue depth", str(queue_depth)),
        ("active requests", str(active)),
        ("scheduled total", str(_first(metrics, "scheduled_total", "total_scheduled", default=0))),
        ("rejected total", str(rejected)),
        ("p95 wait", f"{float(_first(metrics, 'p95_wait_ms', default=0.0) or 0.0):.1f} ms"),
        ("recent anomalies", str(anomaly_count)),
    ]
    return MonitorPanel("Scheduler", state, f"queue={queue_depth} active={active}", rows)


def panel_power_and_airgap(client: MaiClient) -> MonitorPanel:
    """Collect current power and connectivity posture."""

    power = _raw_json(client, "/power/state")
    airgap = _raw_json(client, "/system/airgap")
    connectivity = str(_first(airgap, "connectivity", "network_state", default="unknown"))
    air_gapped = bool(_first(airgap, "is_air_gapped", "air_gap_verified", default=False))
    state = "ok" if air_gapped or connectivity in {"air-gapped", "air_gap_compliant"} else "warn"
    estimated_watts = _first(
        power,
        "estimated_watts",
        "estimated_power_watts",
        default="unknown",
    )
    rows = [
        ("power state", str(power.get("state", "unknown"))),
        ("estimated watts", str(estimated_watts)),
        ("connectivity", connectivity),
        ("local only", str(_first(airgap, "requires_local_only", default="unknown"))),
        ("cloud route", str(_first(airgap, "permits_cloud_route", default="unknown"))),
    ]
    return MonitorPanel("Power and air-gap", state, connectivity, rows)


def panel_trust_and_audit(client: MaiClient) -> MonitorPanel:
    """Collect trust posture and compliance audit integrity."""

    trust = _as_dict(client.trust.status())
    compliance = client.compliance.get_status()
    integrity = _as_dict(compliance.audit_integrity)
    last_verify = str(integrity.get("last_verify", "unknown"))
    trust_mode = str(trust.get("mode", "unknown"))
    state = "ok"
    if last_verify not in {"verified", "unknown"} or trust_mode in {"expired", "degraded"}:
        state = "warn"
    if integrity.get("last_verify_error"):
        state = "crit"
    rows = [
        ("trust mode", trust_mode),
        ("bundle", str(trust.get("bundle_version") or "(none)")),
        ("claims", str(trust.get("claim_count", 0))),
        ("offline backlog", str(trust.get("offline_backlog", 0))),
        ("audit entries", str(integrity.get("entry_count", 0))),
        ("audit verify", last_verify),
    ]
    return MonitorPanel("Trust and audit", state, f"{trust_mode} / {last_verify}", rows)


def panel_metrics(client: MaiClient) -> MonitorPanel:
    """Collect Prometheus exposition health."""

    status_code, body = _raw_get(client, "/metrics")
    text = body if isinstance(body, str) else str(body)
    families = [
        line.split()[2]
        for line in text.splitlines()
        if line.startswith("# TYPE ") and len(line.split()) >= 3
    ]
    state = _state_for_status(status_code)
    rows = [("families", str(len(families)))]
    for family in families[:8]:
        rows.append(("metric", family))
    return MonitorPanel("Metrics", state, f"HTTP {status_code}, {len(families)} families", rows)


def collect_monitoring_snapshot(client: MaiClient) -> list[MonitorPanel]:
    """Return the monitoring panels shown on the operator page."""

    return [
        _safe_panel("Health probes", lambda: panel_probes(client)),
        _safe_panel("Runtime", lambda: panel_runtime(client)),
        _safe_panel("Scheduler", lambda: panel_scheduler(client)),
        _safe_panel("Power and air-gap", lambda: panel_power_and_airgap(client)),
        _safe_panel("Trust and audit", lambda: panel_trust_and_audit(client)),
        _safe_panel("Metrics", lambda: panel_metrics(client)),
    ]
