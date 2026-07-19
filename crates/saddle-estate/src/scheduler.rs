//! Declarative resources required by the professional scheduler. These types
//! are desired-state contracts; scheduling behavior lands in later SAD prompts.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

use crate::kinds::{AttestationProfile, Phase};
use crate::{EstateError, EstateKind, Kind, Resource, Validate};

fn invalid(kind: Kind, reason: impl Into<String>) -> EstateError {
    EstateError::Invalid {
        kind,
        reason: reason.into(),
    }
}

/// Integer resource dimensions governed by [`ResourceQuota`]. A zero hard
/// ceiling means unavailable, never unlimited.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuotaResources {
    #[serde(default)]
    pub cpu_millis: u64,
    #[serde(default)]
    pub memory_mb: u64,
    #[serde(default)]
    pub ephemeral_storage_mb: u64,
    #[serde(default)]
    pub gpu: u32,
    #[serde(default)]
    pub npu: u32,
    #[serde(default)]
    pub accelerator_memory_mb: u64,
    #[serde(default)]
    pub replicas: u32,
    #[serde(default)]
    pub spend_cents: u64,
    #[serde(default)]
    pub model_actions: u64,
    #[serde(default)]
    pub tool_actions: u64,
}

impl QuotaResources {
    fn fits_within(self, hard: Self) -> bool {
        self.cpu_millis <= hard.cpu_millis
            && self.memory_mb <= hard.memory_mb
            && self.ephemeral_storage_mb <= hard.ephemeral_storage_mb
            && self.gpu <= hard.gpu
            && self.npu <= hard.npu
            && self.accelerator_memory_mb <= hard.accelerator_memory_mb
            && self.replicas <= hard.replicas
            && self.spend_cents <= hard.spend_cents
            && self.model_actions <= hard.model_actions
            && self.tool_actions <= hard.tool_actions
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceQuotaSpec {
    pub hard: QuotaResources,
    #[serde(default)]
    pub guaranteed: QuotaResources,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceQuotaStatus {
    #[serde(default)]
    pub used: QuotaResources,
    #[serde(default)]
    pub observed_generation: u64,
}

impl EstateKind for ResourceQuotaSpec {
    const KIND: Kind = Kind::ResourceQuota;
}

impl Validate for ResourceQuotaSpec {
    fn validate(&self) -> Result<(), EstateError> {
        if self.hard == QuotaResources::default() {
            return Err(invalid(Kind::ResourceQuota, "hard quota is empty"));
        }
        if !self.guaranteed.fits_within(self.hard) {
            return Err(invalid(
                Kind::ResourceQuota,
                "guaranteed resources exceed a hard ceiling",
            ));
        }
        Ok(())
    }
}

pub type ResourceQuota = Resource<ResourceQuotaSpec, ResourceQuotaStatus>;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PreemptionPolicy {
    #[default]
    Never,
    LowerPriority,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PriorityClassSpec {
    pub value: i32,
    #[serde(default)]
    pub preemption: PreemptionPolicy,
    /// Protected classes require estate authority at admission; this flag alone
    /// never grants it.
    #[serde(default)]
    pub protected: bool,
    #[serde(default)]
    pub description: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PriorityClassStatus {
    #[serde(default)]
    pub observed_generation: u64,
}

impl EstateKind for PriorityClassSpec {
    const KIND: Kind = Kind::PriorityClass;
}

impl Validate for PriorityClassSpec {
    fn validate(&self) -> Result<(), EstateError> {
        if !(-1_000_000..=1_000_000).contains(&self.value) {
            return Err(invalid(
                Kind::PriorityClass,
                "value is outside the bounded range",
            ));
        }
        Ok(())
    }
}

pub type PriorityClass = Resource<PriorityClassSpec, PriorityClassStatus>;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlacementGroupSpec {
    pub workloads: Vec<String>,
    pub min_members: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub topology_key: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlacementGroupStatus {
    #[serde(default)]
    pub phase: Phase,
    #[serde(default)]
    pub scheduled_members: u32,
    #[serde(default)]
    pub observed_generation: u64,
}

impl EstateKind for PlacementGroupSpec {
    const KIND: Kind = Kind::PlacementGroup;
}

impl Validate for PlacementGroupSpec {
    fn validate(&self) -> Result<(), EstateError> {
        let unique = self.workloads.iter().collect::<BTreeSet<_>>();
        if self.workloads.is_empty()
            || unique.len() != self.workloads.len()
            || self.workloads.iter().any(|name| name.trim().is_empty())
        {
            return Err(invalid(
                Kind::PlacementGroup,
                "workloads must be non-empty, unique names",
            ));
        }
        if self.min_members == 0 || self.min_members as usize > self.workloads.len() {
            return Err(invalid(
                Kind::PlacementGroup,
                "min_members must be within the declared workload set",
            ));
        }
        if self
            .topology_key
            .as_deref()
            .is_some_and(|key| key.trim().is_empty())
        {
            return Err(invalid(Kind::PlacementGroup, "topology_key is empty"));
        }
        Ok(())
    }
}

pub type PlacementGroup = Resource<PlacementGroupSpec, PlacementGroupStatus>;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DisruptionBudgetSpec {
    pub workload: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min_available: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_unavailable: Option<u32>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DisruptionBudgetStatus {
    #[serde(default)]
    pub current_healthy: u32,
    #[serde(default)]
    pub disruptions_allowed: u32,
    #[serde(default)]
    pub observed_generation: u64,
}

impl EstateKind for DisruptionBudgetSpec {
    const KIND: Kind = Kind::DisruptionBudget;
}

impl Validate for DisruptionBudgetSpec {
    fn validate(&self) -> Result<(), EstateError> {
        if self.workload.trim().is_empty() {
            return Err(invalid(Kind::DisruptionBudget, "workload is empty"));
        }
        if self.min_available.is_some() == self.max_unavailable.is_some() {
            return Err(invalid(
                Kind::DisruptionBudget,
                "set exactly one of min_available or max_unavailable",
            ));
        }
        Ok(())
    }
}

pub type DisruptionBudget = Resource<DisruptionBudgetSpec, DisruptionBudgetStatus>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeDriver {
    Process,
    Containerd,
    Wasmtime,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeClassSpec {
    pub driver: RuntimeDriver,
    pub handler: String,
    #[serde(default)]
    pub minimum_attestation: AttestationProfile,
    #[serde(default)]
    pub allowed_measurements: Vec<String>,
    /// Optional registry/driver credential reference, envelope-sealed by
    /// admission before persistence.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub credential_ref: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeClassStatus {
    #[serde(default)]
    pub ready: bool,
    #[serde(default)]
    pub observed_generation: u64,
}

impl EstateKind for RuntimeClassSpec {
    const KIND: Kind = Kind::RuntimeClass;
}

impl Validate for RuntimeClassSpec {
    fn validate(&self) -> Result<(), EstateError> {
        if self.handler.trim().is_empty() {
            return Err(invalid(Kind::RuntimeClass, "handler is empty"));
        }
        let unique = self.allowed_measurements.iter().collect::<BTreeSet<_>>();
        if unique.len() != self.allowed_measurements.len()
            || self
                .allowed_measurements
                .iter()
                .any(|measurement| measurement.trim().is_empty())
        {
            return Err(invalid(
                Kind::RuntimeClass,
                "allowed measurements must be unique and non-empty",
            ));
        }
        if self
            .credential_ref
            .as_deref()
            .is_some_and(|reference| reference.trim().is_empty())
        {
            return Err(invalid(Kind::RuntimeClass, "credential_ref is empty"));
        }
        Ok(())
    }
}

pub type RuntimeClass = Resource<RuntimeClassSpec, RuntimeClassStatus>;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NodeLeaseSpec {
    pub node: String,
    pub holder_identity: String,
    pub renew_time: String,
    pub lease_duration_seconds: u32,
    #[serde(default)]
    pub epoch: u64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NodeLeaseStatus {
    #[serde(default)]
    pub expired: bool,
    #[serde(default)]
    pub observed_generation: u64,
}

impl EstateKind for NodeLeaseSpec {
    const KIND: Kind = Kind::NodeLease;
}

impl Validate for NodeLeaseSpec {
    fn validate(&self) -> Result<(), EstateError> {
        if self.node.trim().is_empty()
            || self.holder_identity.trim().is_empty()
            || self.renew_time.trim().is_empty()
        {
            return Err(invalid(
                Kind::NodeLease,
                "node, holder_identity, and renew_time are required",
            ));
        }
        if !(1..=3_600).contains(&self.lease_duration_seconds) {
            return Err(invalid(
                Kind::NodeLease,
                "lease_duration_seconds must be within 1..=3600",
            ));
        }
        Ok(())
    }
}

pub type NodeLease = Resource<NodeLeaseSpec, NodeLeaseStatus>;
