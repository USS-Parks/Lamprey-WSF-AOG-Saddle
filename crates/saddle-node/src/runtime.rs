//! Last-responsible-moment runtime authorization for assigned AOG workloads.
//!
//! A node never starts a driver from desired state alone. The scheduler's
//! signed child capability must bind the exact tenant, workload UID and digest,
//! placement UID, node identity, workload kind role, and expiry. Revocation and
//! signature checks happen immediately before [`WorkloadDriver::start`].

use chrono::{DateTime, Utc};
use std::collections::{HashMap, HashSet};
use std::sync::Mutex;

use fabric_contracts::{Classification, TrustToken};
use fabric_crypto::Verifier;
use fabric_revocation::RevocationSnapshot;
use saddle_estate::{Placement, Workload, WorkloadKind};
use sha2::{Digest, Sha256};

use crate::driver::{DriverError, WorkloadDriver, WorkloadHandle, WorkloadRun};

/// Fixed least-privilege AOG role for a managed workload kind.
#[must_use]
pub fn workload_role(kind: WorkloadKind) -> &'static str {
    match kind {
        WorkloadKind::Gateway => "aog:model:dispatch",
        WorkloadKind::Toolproxy => "aog:tool:broker",
        WorkloadKind::Approvals => "aog:approval:decide",
        WorkloadKind::Agent => "aog:agent:run",
        WorkloadKind::Inference => "aog:inference:serve",
    }
}

/// Stable runtime class projected from a managed workload kind.
#[must_use]
pub fn runtime_class(kind: WorkloadKind) -> &'static str {
    match kind {
        WorkloadKind::Gateway => "aog-gateway",
        WorkloadKind::Toolproxy => "aog-toolproxy",
        WorkloadKind::Approvals => "aog-approvals",
        WorkloadKind::Agent => "aog-agent",
        WorkloadKind::Inference => "aog-inference",
    }
}

/// Canonical digest of the immutable runtime inputs and workload generation.
///
/// # Errors
/// Returns a serialization error only if a future workload field cannot be
/// represented by `serde_json`.
pub fn workload_digest(workload: &Workload) -> Result<String, serde_json::Error> {
    // Replica count is deployment topology, not a runtime input: scaling must
    // not roll already-running replicas. Runtime/trust inputs remain bound.
    let canonical = serde_json::to_vec(&(
        &workload.metadata.uid,
        workload.spec.workload_kind,
        workload.spec.ring,
        workload.spec.classification_ceiling,
        &workload.spec.image,
        &workload.spec.command,
        &workload.spec.capability,
        &workload.spec.scheduling,
    ))?;
    Ok(hex::encode(Sha256::digest(canonical)))
}

/// Expected service identity for one placement-specific child capability.
#[must_use]
pub fn service_identity(
    tenant: &str,
    kind: WorkloadKind,
    node_identity: &str,
    placement_uid: &str,
) -> String {
    format!(
        "saddle/{tenant}/{}/{node_identity}/{placement_uid}",
        runtime_class(kind)
    )
}

/// Exact assignment the node will pass to its driver after authorization.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeAssignment {
    pub run: WorkloadRun,
    pub tenant: String,
    pub node_identity: String,
    pub placement_uid: String,
    pub token_id: String,
    pub workload_uid: String,
    pub workload_digest: String,
    pub workload_kind: WorkloadKind,
    pub classification_ceiling: Classification,
}

impl RuntimeAssignment {
    /// Project an admitted workload and its exact binding into a node assignment.
    ///
    /// # Errors
    /// Fails closed when identity or binding fields are absent or inconsistent.
    pub fn from_resources(
        workload: &Workload,
        placement: &Placement,
        node_identity: &str,
    ) -> Result<Self, RuntimeAuthorizationError> {
        if workload.metadata.uid.trim().is_empty()
            || placement.metadata.uid.trim().is_empty()
            || placement.spec.token_id.trim().is_empty()
            || placement.spec.node != node_identity
            || placement.spec.workload != workload.metadata.name
        {
            return Err(RuntimeAuthorizationError::Binding);
        }
        let tenant = workload
            .metadata
            .tenant
            .as_deref()
            .filter(|tenant| !tenant.trim().is_empty())
            .ok_or(RuntimeAuthorizationError::Binding)?
            .to_owned();
        let digest = workload_digest(workload)
            .map_err(|error| RuntimeAuthorizationError::Digest(error.to_string()))?;
        Ok(Self {
            run: WorkloadRun {
                name: placement.metadata.name.clone(),
                image: workload.spec.image.clone(),
                command: workload.spec.command.clone(),
            },
            tenant,
            node_identity: node_identity.to_owned(),
            placement_uid: placement.metadata.uid.clone(),
            token_id: placement.spec.token_id.clone(),
            workload_uid: workload.metadata.uid.clone(),
            workload_digest: digest,
            workload_kind: workload.spec.workload_kind,
            classification_ceiling: workload.spec.classification_ceiling,
        })
    }
}

/// Fail-closed runtime authorization error.
#[derive(Debug, thiserror::Error)]
pub enum RuntimeAuthorizationError {
    #[error("assignment binding is incomplete or inconsistent")]
    Binding,
    #[error("workload digest failed: {0}")]
    Digest(String),
    #[error("runtime capability signature is invalid")]
    Signature,
    #[error("runtime capability is expired or malformed")]
    Expired,
    #[error("runtime capability has been revoked")]
    Revoked,
    #[error("runtime capability does not exactly bind the assignment")]
    Scope,
    #[error("driver: {0}")]
    Driver(#[from] DriverError),
}

/// Verify `token` against `assignment` and start only after every check passes.
pub fn start_authorized(
    driver: &dyn WorkloadDriver,
    assignment: &RuntimeAssignment,
    token: &TrustToken,
    revocation: &RevocationSnapshot,
    now: DateTime<Utc>,
    verifier: &dyn Verifier,
    anchor_public_key: &[u8],
) -> Result<WorkloadHandle, RuntimeAuthorizationError> {
    fabric_token::verify(token, verifier, anchor_public_key)
        .map_err(|_| RuntimeAuthorizationError::Signature)?;
    if fabric_token::is_expired(token, now).map_err(|_| RuntimeAuthorizationError::Expired)? {
        return Err(RuntimeAuthorizationError::Expired);
    }
    if revocation.revokes(token).is_some() {
        return Err(RuntimeAuthorizationError::Revoked);
    }
    let expected_identity = service_identity(
        &assignment.tenant,
        assignment.workload_kind,
        &assignment.node_identity,
        &assignment.placement_uid,
    );
    let expected_role = workload_role(assignment.workload_kind);
    let exact = token.token_id == assignment.token_id
        && token.tenant_id == assignment.tenant
        && token.subject_id.as_deref() == Some(assignment.workload_uid.as_str())
        && token.subject_hash == assignment.workload_digest
        && token.service_identity.as_deref() == Some(expected_identity.as_str())
        && token.identity_id.as_deref() == Some(assignment.placement_uid.as_str())
        && token.roles.as_slice() == [expected_role]
        && token.max_data_classification >= assignment.classification_ceiling;
    if !exact {
        return Err(RuntimeAuthorizationError::Scope);
    }
    driver.start(&assignment.run).map_err(Into::into)
}

/// One desired assignment plus the signed child capability fetched for it.
#[derive(Debug, Clone)]
pub struct AuthorizedAssignment {
    pub assignment: RuntimeAssignment,
    pub token: TrustToken,
}

/// Observable result of one node reconciliation pass.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RuntimeSync {
    pub started: Vec<String>,
    pub stopped: Vec<String>,
    pub denied: Vec<String>,
    pub running: Vec<String>,
}

struct RunningWorkload {
    digest: String,
    handle: WorkloadHandle,
}

/// Node lifecycle reconciler. Missing, changed, or unauthorized assignments are
/// stopped; only currently verified children reach the real driver.
pub struct NodeRuntime<D: WorkloadDriver> {
    driver: D,
    running: Mutex<HashMap<String, RunningWorkload>>,
}

impl<D: WorkloadDriver> NodeRuntime<D> {
    #[must_use]
    pub fn new(driver: D) -> Self {
        Self {
            driver,
            running: Mutex::new(HashMap::new()),
        }
    }

    /// Reconcile the exact currently assigned children.
    ///
    /// # Errors
    /// Returns a driver stop/start error. Authorization failures are reported in
    /// `denied` after stopping any matching old instance.
    pub fn reconcile(
        &self,
        desired: &[AuthorizedAssignment],
        revocation: &RevocationSnapshot,
        now: DateTime<Utc>,
        verifier: &dyn Verifier,
        anchor_public_key: &[u8],
    ) -> Result<RuntimeSync, RuntimeAuthorizationError> {
        let desired_names: HashSet<&str> = desired
            .iter()
            .map(|entry| entry.assignment.run.name.as_str())
            .collect();
        let mut running = self.running.lock().expect("node runtime lock");
        let mut sync = RuntimeSync::default();

        let removed: Vec<String> = running
            .keys()
            .filter(|name| !desired_names.contains(name.as_str()))
            .cloned()
            .collect();
        for name in removed {
            if let Some(old) = running.remove(&name) {
                self.driver.stop(&old.handle)?;
                sync.stopped.push(name);
            }
        }

        for entry in desired {
            let name = entry.assignment.run.name.clone();
            let changed = running
                .get(&name)
                .is_some_and(|old| old.digest != entry.assignment.workload_digest);
            if changed && let Some(old) = running.remove(&name) {
                self.driver.stop(&old.handle)?;
                sync.stopped.push(name.clone());
            }
            if running.contains_key(&name) {
                continue;
            }
            match start_authorized(
                &self.driver,
                &entry.assignment,
                &entry.token,
                revocation,
                now,
                verifier,
                anchor_public_key,
            ) {
                Ok(handle) => {
                    running.insert(
                        name.clone(),
                        RunningWorkload {
                            digest: entry.assignment.workload_digest.clone(),
                            handle,
                        },
                    );
                    sync.started.push(name);
                }
                Err(
                    RuntimeAuthorizationError::Signature
                    | RuntimeAuthorizationError::Expired
                    | RuntimeAuthorizationError::Revoked
                    | RuntimeAuthorizationError::Scope,
                ) => sync.denied.push(name),
                Err(error) => return Err(error),
            }
        }

        sync.running = running.keys().cloned().collect();
        sync.started.sort();
        sync.stopped.sort();
        sync.denied.sort();
        sync.running.sort();
        Ok(sync)
    }
}
