//! Health check handlers for the MAI REST API.
//!
//! Provides aggregate health, per-adapter health, hardware telemetry,
//! and system resource monitoring. All telemetry is local-only and
//! never transmitted off-device.

use axum::Json;
use axum::extract::State;
use axum::response::IntoResponse;
use tracing::debug;

use crate::errors::ApiError;
use crate::state::AppState;
use crate::types::{
    AdapterHealthSummary, GpuHealthSummary, HardwareHealthSummary, HealthResponse, ProfileInfo,
    SystemHealthSummary,
};

use mai_core::health::NetworkState;

// ─── Aggregate Health ──────────────────────────────────────────────

/// GET /v1/health
///
/// Returns aggregate system health: adapter statuses, hardware state,
/// system resources, and computed alert level. Available to all profiles
/// (health is not a privileged operation).
#[allow(clippy::cast_precision_loss)]
pub async fn aggregate_health(
    State(state): State<AppState>,
    profile: ProfileInfo,
) -> Result<impl IntoResponse, ApiError> {
    let health = state.health.read().await;
    let snapshot = health.get_snapshot();

    let adapters: Vec<AdapterHealthSummary> = snapshot
        .adapters
        .values()
        .map(AdapterHealthSummary::from)
        .collect();

    let gpus: Vec<GpuHealthSummary> = snapshot
        .hardware
        .gpus
        .iter()
        .map(GpuHealthSummary::from)
        .collect();

    let air_gap_status = match &snapshot.hardware.network_state {
        NetworkState::AirGapCompliant => "compliant",
        NetworkState::Connected => "connected",
        NetworkState::NonCompliant { .. } => "non_compliant",
    };

    let disk_pct = if snapshot.system.disk_total_bytes > 0 {
        (snapshot.system.disk_used_bytes as f32 / snapshot.system.disk_total_bytes as f32) * 100.0
    } else {
        0.0
    };
    let ram_pct = if snapshot.system.ram_total_bytes > 0 {
        (snapshot.system.ram_used_bytes as f32 / snapshot.system.ram_total_bytes as f32) * 100.0
    } else {
        0.0
    };

    let overall_status = match snapshot.alert_level {
        mai_core::health::AlertLevel::Normal | mai_core::health::AlertLevel::Warn => "healthy",
        mai_core::health::AlertLevel::Degrade => "degraded",
        mai_core::health::AlertLevel::Critical | mai_core::health::AlertLevel::Shutdown => {
            "unhealthy"
        }
    };

    let response = HealthResponse {
        status: overall_status.to_string(),
        alert_level: crate::types::alert_level_to_string(snapshot.alert_level),
        adapters,
        hardware: HardwareHealthSummary {
            gpus,
            air_gap_status: air_gap_status.to_string(),
        },
        system: SystemHealthSummary {
            disk_utilization_percent: disk_pct,
            ram_utilization_percent: ram_pct,
            cpu_utilization_percent: snapshot.system.cpu_utilization * 100.0,
        },
    };

    debug!(
        status = %response.status,
        alert = %response.alert_level,
        adapters = response.adapters.len(),
        "Health snapshot served"
    );

    Ok(Json(response))
}

// ─── Adapter Health ────────────────────────────────────────────────

/// GET /v1/health/adapters
///
/// Returns per-adapter health details. Adapter identifiers are opaque
/// strings; backend implementation names are never exposed.
pub async fn adapter_health(
    State(state): State<AppState>,
    _profile: ProfileInfo,
) -> Result<impl IntoResponse, ApiError> {
    let health = state.health.read().await;
    let snapshot = health.get_snapshot();

    let adapters: Vec<AdapterHealthSummary> = snapshot
        .adapters
        .values()
        .map(AdapterHealthSummary::from)
        .collect();

    Ok(Json(serde_json::json!({
        "adapters": adapters,
        "total": adapters.len(),
        "healthy": adapters.iter().filter(|a| a.status == "healthy").count(),
    })))
}

// ─── Hardware Health ───────────────────────────────────────────────

/// GET /v1/health/hardware
///
/// Returns GPU temperatures, VRAM utilization, power draw, thermal state,
/// and air-gap compliance. All data sourced from HIL telemetry.
pub async fn hardware_health(
    State(state): State<AppState>,
    _profile: ProfileInfo,
) -> Result<impl IntoResponse, ApiError> {
    let health = state.health.read().await;
    let snapshot = health.get_snapshot();

    let gpus: Vec<GpuHealthSummary> = snapshot
        .hardware
        .gpus
        .iter()
        .map(GpuHealthSummary::from)
        .collect();

    let air_gap_status = match &snapshot.hardware.network_state {
        NetworkState::AirGapCompliant => "compliant",
        NetworkState::Connected => "connected",
        NetworkState::NonCompliant { .. } => "non_compliant",
    };

    Ok(Json(HardwareHealthSummary {
        gpus,
        air_gap_status: air_gap_status.to_string(),
    }))
}

// ─── System Health ─────────────────────────────────────────────────

/// GET /v1/health/system
///
/// Returns disk, RAM, and CPU utilization percentages. All metrics
/// are computed locally and never transmitted off-device.
#[allow(clippy::cast_precision_loss)]
pub async fn system_health(
    State(state): State<AppState>,
    _profile: ProfileInfo,
) -> Result<impl IntoResponse, ApiError> {
    let health = state.health.read().await;
    let snapshot = health.get_snapshot();

    let disk_pct = if snapshot.system.disk_total_bytes > 0 {
        (snapshot.system.disk_used_bytes as f32 / snapshot.system.disk_total_bytes as f32) * 100.0
    } else {
        0.0
    };
    let ram_pct = if snapshot.system.ram_total_bytes > 0 {
        (snapshot.system.ram_used_bytes as f32 / snapshot.system.ram_total_bytes as f32) * 100.0
    } else {
        0.0
    };

    Ok(Json(SystemHealthSummary {
        disk_utilization_percent: disk_pct,
        ram_utilization_percent: ram_pct,
        cpu_utilization_percent: snapshot.system.cpu_utilization * 100.0,
    }))
}

// ─── SHIP-11: Operational Health Probes ────────────────────────────
//
// Four-state semantics, suitable for systemd `WatchdogSec` /
// Kubernetes liveness/readiness probes / load-balancer health
// checks. These are *operational* health (process / dependency
// liveness) and live alongside the existing aggregate / hardware /
// system endpoints, which expose *hardware* health (GPU temps, etc).
//
// | endpoint                 | what it means                                          | failure code |
// |--------------------------|--------------------------------------------------------|--------------|
// | `/v1/health/live`        | the process is running and the runtime is responsive   | n/a (always 200) |
// | `/v1/health/ready`       | this instance can accept allowed traffic               | 503          |
// | `/v1/health/production`  | every production invariant holds (per SHIP-02 / SHIP-11) | 503        |
//
// `degraded` and `unsafe` are *response statuses* returned in the JSON
// body, not separate endpoints — orchestrators can treat any non-200
// the same way regardless of body, and humans get a richer reason
// list when they curl the endpoint by hand.

/// SHIP-11 health-probe response body.
///
/// `status` is always one of `live` / `ready` / `degraded` / `unsafe`
/// — matching the SHIP-HARDENING-PLAN §10 "Health Semantics" table.
/// `reasons` is empty on success; on failure it lists the specific
/// invariants that were violated (e.g. `["audit_writer_unresponsive",
/// "audit_chain_broken_at_42"]`). Operators read this body to triage;
/// machines just look at the HTTP status code.
#[derive(Debug, serde::Serialize)]
pub struct ProbeResponse {
    /// `live` | `ready` | `degraded` | `unsafe`.
    pub status: &'static str,
    /// Empty on success; populated with specific check IDs on failure.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub reasons: Vec<String>,
}

/// `GET /v1/health/live`
///
/// Always returns `200 OK` with `{"status":"live"}`. If this handler
/// can execute and serialize a response, the process is — by
/// definition — live. Used as the systemd watchdog ping and as the
/// k8s liveness probe (anything heavier risks restarting a healthy
/// pod that is mid-startup).
pub async fn live_probe() -> impl IntoResponse {
    Json(ProbeResponse {
        status: "live",
        reasons: Vec::new(),
    })
}

/// `GET /v1/health/ready`
///
/// Returns `200 OK` if this instance can accept allowed traffic, or
/// `503 Service Unavailable` if a critical dependency is unresponsive.
///
/// Readiness criteria (SHIP-HARDENING-PLAN §10):
///
/// 1. The audit writer's `entry_count()` returns within 250 ms — if
///    audit storage is broken, every request would otherwise write to
///    a dead WAL and we'd be silently un-auditable.
/// 2. The hardware health alert level is not `Shutdown` — a
///    `Critical` alert is still served (operators may have set it
///    deliberately during a drill), but a `Shutdown` means the power
///    state machine has told us to stop accepting work.
///
/// Failures are reported by ID in the response body; the HTTP status
/// is what orchestrators key off.
pub async fn ready_probe(State(state): State<AppState>) -> impl IntoResponse {
    use axum::http::StatusCode;
    use tokio::time::{Duration as TokioDuration, timeout};

    let mut reasons = Vec::new();

    // (1) audit writer responsive
    let writer = state.audit_writer.clone();
    let audit_ok = timeout(TokioDuration::from_millis(250), async move {
        writer.entry_count().await
    })
    .await;
    match audit_ok {
        Ok(Ok(_)) => {}
        Ok(Err(e)) => {
            reasons.push(format!(
                "audit_writer_error:{}",
                e.chars().take(64).collect::<String>()
            ));
        }
        Err(_) => {
            reasons.push("audit_writer_unresponsive".to_string());
        }
    }

    // (2) hardware alert level not Shutdown
    {
        let health = state.health.read().await;
        let snapshot = health.get_snapshot();
        if matches!(snapshot.alert_level, mai_core::health::AlertLevel::Shutdown) {
            reasons.push("hardware_shutdown_alert".to_string());
        }
    }

    let body = if reasons.is_empty() {
        ProbeResponse {
            status: "ready",
            reasons,
        }
    } else {
        ProbeResponse {
            status: "degraded",
            reasons,
        }
    };
    let code = if body.reasons.is_empty() {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };
    (code, Json(body))
}

/// `GET /v1/health/production`
///
/// Returns `200 OK` if every production invariant holds, or
/// `503 Service Unavailable` if any do not. This is the strictest
/// probe — orchestrators that should *only* route real-tenant traffic
/// at a production-grade instance key off this endpoint instead of
/// `/v1/health/ready`. The SHIP-07 `/v1/system/production-readiness`
/// endpoint (when it lands) is the *introspection* counterpart: it
/// returns the full report; this probe returns a status code.
///
/// Production criteria (SHIP-HARDENING-PLAN §10, intersection with
/// SHIP-02 production guard):
///
/// 1. All [`ready_probe`] criteria, plus
/// 2. The recent audit chain (last 64 entries) verifies, and
/// 3. The hardware alert level is `Normal` or `Warn` (a `Degrade`
///    state means a real production tenant should be routed away).
pub async fn production_probe(State(state): State<AppState>) -> impl IntoResponse {
    use axum::http::StatusCode;
    use tokio::time::{Duration as TokioDuration, timeout};

    let mut reasons = Vec::new();

    // (1) audit writer responsive within 250 ms
    let writer = state.audit_writer.clone();
    let audit_ok = timeout(TokioDuration::from_millis(250), async move {
        writer.entry_count().await
    })
    .await;
    match audit_ok {
        Ok(Ok(_)) => {}
        Ok(Err(e)) => {
            reasons.push(format!(
                "audit_writer_error:{}",
                e.chars().take(64).collect::<String>()
            ));
        }
        Err(_) => {
            reasons.push("audit_writer_unresponsive".to_string());
        }
    }

    // (2) recent audit chain verifies
    let writer = state.audit_writer.clone();
    if let Ok(Ok(recent)) = timeout(TokioDuration::from_millis(500), async move {
        writer.read_recent(64).await
    })
    .await
        && let Err((idx, msg)) = crate::audit::verify_chain(&recent)
    {
        reasons.push(format!(
            "audit_chain_broken_at_{}:{}",
            idx,
            msg.chars().take(48).collect::<String>()
        ));
    }

    // (3) hardware alert level is Normal or Warn
    {
        let health = state.health.read().await;
        let snapshot = health.get_snapshot();
        match snapshot.alert_level {
            mai_core::health::AlertLevel::Normal | mai_core::health::AlertLevel::Warn => {}
            mai_core::health::AlertLevel::Degrade => {
                reasons.push("hardware_degrade".to_string());
            }
            mai_core::health::AlertLevel::Critical => {
                reasons.push("hardware_critical".to_string());
            }
            mai_core::health::AlertLevel::Shutdown => {
                reasons.push("hardware_shutdown".to_string());
            }
        }
    }

    let body = if reasons.is_empty() {
        ProbeResponse {
            status: "ready",
            reasons,
        }
    } else {
        // Any failure of a production invariant moves us to "unsafe"
        // — the spec distinguishes this from "degraded" (which is
        // returned by /v1/health/ready when *some* dependency is
        // failing but the instance can still serve allowed traffic).
        ProbeResponse {
            status: "unsafe",
            reasons,
        }
    };
    let code = if body.reasons.is_empty() {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };
    (code, Json(body))
}
