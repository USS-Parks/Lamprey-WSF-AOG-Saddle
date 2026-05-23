//! Application state shared across all axum handlers.
//!
//! AppState holds Arc references to every mai-core component the API
//! server needs. It is injected into handlers via axum's State extractor.
//! All components are thread-safe (Arc + Mutex/RwLock internally).

use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};

use crate::audit::AuditWriter;
use crate::auth::AuthState;
use crate::config::ServerConfig;

use mai_adapters::manager::AdapterManager;
use mai_compliance::audit::AuditLog as ComplianceAuditLog;
use mai_compliance::bundle::{AcceptAllBundleVerifier, BundleVerifier};
use mai_compliance::policy::{PolicyManager, PolicyTemplate};
use mai_compliance::reports::ReportManager;
use mai_compliance::trust_cache::{CacheThresholds, LocalTrustCache};
use mai_core::airgap::AirGapPolicy;
use mai_core::health::HealthMonitor;
use mai_core::hotswap::HotSwapManager;
use mai_core::power::PowerStateMachine;
use mai_core::registry::ModelRegistry;
use mai_scheduler::Scheduler;
use mai_scheduler::metrics::MetricsCollector;

/// Shared application state for all request handlers.
///
/// Cloned into each handler via `axum::extract::State<AppState>`.
/// All inner fields are behind Arc so cloning is cheap (pointer bump).
#[derive(Clone)]
pub struct AppState {
    /// Model scheduler: routes inference requests to instances (mai-scheduler)
    pub scheduler: Arc<dyn Scheduler>,
    /// Model registry: manifest management and lifecycle tracking
    pub registry: Arc<RwLock<ModelRegistry>>,
    /// Health monitor: adapter heartbeats, hardware telemetry, alerts
    pub health: Arc<RwLock<HealthMonitor>>,
    /// Power state machine: sleep mode transitions
    pub power: Arc<RwLock<PowerStateMachine>>,
    /// Hot-swap manager: zero-downtime model updates
    pub hotswap: Arc<RwLock<HotSwapManager>>,
    /// Audit trail writer (trait object for testability)
    pub audit_writer: Arc<dyn AuditWriter>,
    /// Server configuration (may be hot-reloaded)
    pub config: Arc<RwLock<ServerConfig>>,
    /// Authentication state (token validator)
    pub auth: AuthState,
    /// Adapter manager: spawns and manages Python adapter subprocesses
    pub adapter_manager: Arc<Mutex<AdapterManager>>,
    /// Metrics collector: request lifecycle, health scoring, anomaly detection
    pub metrics_collector: Arc<MetricsCollector>,
    /// Session 28: canonical connectivity state shared with mai-adapters
    /// and mai-compliance. Defaults to `AirGapped` when constructed via
    /// [`AppState::new`]; override with [`AppState::with_airgap_policy`].
    pub airgap_policy: AirGapPolicy,
    /// BF-4: local trust cache. Holds the most recent signed policy
    /// bundle plus per-claim revocation snapshots. Defaults to an empty
    /// cache with stock thresholds; production wires a real refresher.
    pub trust_cache: Arc<RwLock<LocalTrustCache>>,
    /// BF-3: verifier used when ingesting a signed bundle. Defaults to
    /// [`AcceptAllBundleVerifier`] so bring-up works without a key
    /// material; production wires `MlDsaBundleVerifier` with the
    /// vault-anchored registry.
    pub bundle_verifier: Arc<dyn BundleVerifier + Send + Sync>,
    /// S41: policy runtime (composer + decision cache + audit feed).
    /// Internally `Arc<Mutex<…>>` so cloning the AppState is cheap.
    pub policy_manager: PolicyManager,
    /// S42: tamper-evident compliance audit log.
    pub compliance_audit: ComplianceAuditLog,
    /// S43: compliance report generator façade.
    pub report_manager: Arc<ReportManager>,
}

impl AppState {
    /// Construct a new AppState from pre-built components.
    ///
    /// All components must be fully initialized before constructing AppState.
    /// The API server does not own component lifecycle; it borrows via Arc.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        scheduler: Arc<dyn Scheduler>,
        registry: Arc<RwLock<ModelRegistry>>,
        health: Arc<RwLock<HealthMonitor>>,
        power: Arc<RwLock<PowerStateMachine>>,
        hotswap: Arc<RwLock<HotSwapManager>>,
        audit_writer: Arc<dyn AuditWriter>,
        config: Arc<RwLock<ServerConfig>>,
        auth: AuthState,
        adapter_manager: Arc<Mutex<AdapterManager>>,
        metrics_collector: Arc<MetricsCollector>,
    ) -> Self {
        let compliance_audit = ComplianceAuditLog::builder().build();
        let report_manager = Arc::new(ReportManager::builder(compliance_audit.clone()).build());
        let trust_cache = LocalTrustCache::new(CacheThresholds::default())
            .expect("default trust-cache thresholds are valid");
        Self {
            scheduler,
            registry,
            health,
            power,
            hotswap,
            audit_writer,
            config,
            auth,
            adapter_manager,
            metrics_collector,
            airgap_policy: AirGapPolicy::default(),
            trust_cache: Arc::new(RwLock::new(trust_cache)),
            bundle_verifier: Arc::new(AcceptAllBundleVerifier),
            policy_manager: PolicyManager::from_template(PolicyTemplate::Standard),
            compliance_audit,
            report_manager,
        }
    }

    /// Replace the air-gap policy in this state. Used by server bootstrap
    /// to inject a policy that's already wired to the hardware switch
    /// reader or to a deterministic dev-mode policy.
    #[must_use]
    pub fn with_airgap_policy(mut self, policy: AirGapPolicy) -> Self {
        self.airgap_policy = policy;
        self
    }

    /// Override the local trust cache. Used at bootstrap to inject a
    /// cache that's already pre-loaded from disk or wired to a
    /// background refresher.
    #[must_use]
    pub fn with_trust_cache(mut self, cache: Arc<RwLock<LocalTrustCache>>) -> Self {
        self.trust_cache = cache;
        self
    }

    /// Override the bundle verifier. Production wires
    /// `MlDsaBundleVerifier` with the vault-anchored registry; tests
    /// keep the [`AcceptAllBundleVerifier`] default.
    #[must_use]
    pub fn with_bundle_verifier(mut self, verifier: Arc<dyn BundleVerifier + Send + Sync>) -> Self {
        self.bundle_verifier = verifier;
        self
    }

    /// Override the policy manager. Bootstrap may wire a manager
    /// pre-loaded from a tenant-specific template (Healthcare /
    /// Defense / TribalGovernment).
    #[must_use]
    pub fn with_policy_manager(mut self, manager: PolicyManager) -> Self {
        self.policy_manager = manager;
        self
    }

    /// Override the compliance audit log and rebuild the dependent
    /// [`ReportManager`] so the report engine queries the new log.
    #[must_use]
    pub fn with_compliance_audit(mut self, audit: ComplianceAuditLog) -> Self {
        let report_manager = Arc::new(ReportManager::builder(audit.clone()).build());
        self.compliance_audit = audit;
        self.report_manager = report_manager;
        self
    }

    /// Override the report manager directly (e.g. when a custom
    /// template registry has been registered).
    #[must_use]
    pub fn with_report_manager(mut self, manager: Arc<ReportManager>) -> Self {
        self.report_manager = manager;
        self
    }
}

// ─── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // Compile-time check: AppState must be Clone + Send + Sync
    fn _assert_clone_send_sync<T: Clone + Send + Sync>() {}

    #[test]
    fn test_appstate_is_clone_send_sync() {
        _assert_clone_send_sync::<AppState>();
    }
}
