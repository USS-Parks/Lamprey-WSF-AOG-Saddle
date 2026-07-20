//! SAD-43 professional scheduling cycle.
//!
//! The original Phase-S selector remains useful for a single placement, but a
//! control-plane scheduler needs more than filter/score: a coherent revision,
//! tenant fairness, quota-aware atomic reservations, bounded permits, gang
//! rollback, and a compare-and-swap bind. This module supplies that stateful,
//! deterministic layer while reusing the SAD-32 deny-wins filters.

use std::collections::{BTreeMap, BTreeSet};
use std::panic::{AssertUnwindSafe, catch_unwind};

use chrono::{DateTime, Utc};
use saddle_estate::{Capacity, QuotaResources};

use crate::{ScheduleRequest, Scheduler, attested_scheduler};

/// Every integer resource dimension governed by scheduling and quota.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ResourceVector {
    pub cpu_millis: u64,
    pub memory_mb: u64,
    pub ephemeral_storage_mb: u64,
    pub gpu: u64,
    pub npu: u64,
    pub accelerator_memory_mb: u64,
    pub slots: u64,
    pub spend_cents: u64,
    pub extended: BTreeMap<String, u64>,
}

impl ResourceVector {
    #[must_use]
    pub fn from_capacity(value: Capacity) -> Self {
        Self {
            cpu_millis: value.cpu_millis,
            memory_mb: value.memory_mb,
            gpu: u64::from(value.gpu),
            slots: u64::from(value.max_workloads),
            ..Self::default()
        }
    }

    #[must_use]
    pub fn from_quota(value: QuotaResources) -> Self {
        Self {
            cpu_millis: value.cpu_millis,
            memory_mb: value.memory_mb,
            ephemeral_storage_mb: value.ephemeral_storage_mb,
            gpu: u64::from(value.gpu),
            npu: u64::from(value.npu),
            accelerator_memory_mb: value.accelerator_memory_mb,
            slots: u64::from(value.replicas),
            spend_cents: value.spend_cents,
            extended: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn fits_within(&self, limit: &Self) -> bool {
        self.cpu_millis <= limit.cpu_millis
            && self.memory_mb <= limit.memory_mb
            && self.ephemeral_storage_mb <= limit.ephemeral_storage_mb
            && self.gpu <= limit.gpu
            && self.npu <= limit.npu
            && self.accelerator_memory_mb <= limit.accelerator_memory_mb
            && self.slots <= limit.slots
            && self.spend_cents <= limit.spend_cents
            && self
                .extended
                .iter()
                .all(|(name, value)| *value <= limit.extended.get(name).copied().unwrap_or(0))
    }

    fn checked_add(&self, other: &Self) -> Option<Self> {
        let mut extended = self.extended.clone();
        for (name, value) in &other.extended {
            let entry = extended.entry(name.clone()).or_default();
            *entry = entry.checked_add(*value)?;
        }
        Some(Self {
            cpu_millis: self.cpu_millis.checked_add(other.cpu_millis)?,
            memory_mb: self.memory_mb.checked_add(other.memory_mb)?,
            ephemeral_storage_mb: self
                .ephemeral_storage_mb
                .checked_add(other.ephemeral_storage_mb)?,
            gpu: self.gpu.checked_add(other.gpu)?,
            npu: self.npu.checked_add(other.npu)?,
            accelerator_memory_mb: self
                .accelerator_memory_mb
                .checked_add(other.accelerator_memory_mb)?,
            slots: self.slots.checked_add(other.slots)?,
            spend_cents: self.spend_cents.checked_add(other.spend_cents)?,
            extended,
        })
    }

    fn checked_sub(&self, other: &Self) -> Option<Self> {
        let mut extended = self.extended.clone();
        for (name, value) in &other.extended {
            let entry = extended.get_mut(name)?;
            *entry = entry.checked_sub(*value)?;
        }
        Some(Self {
            cpu_millis: self.cpu_millis.checked_sub(other.cpu_millis)?,
            memory_mb: self.memory_mb.checked_sub(other.memory_mb)?,
            ephemeral_storage_mb: self
                .ephemeral_storage_mb
                .checked_sub(other.ephemeral_storage_mb)?,
            gpu: self.gpu.checked_sub(other.gpu)?,
            npu: self.npu.checked_sub(other.npu)?,
            accelerator_memory_mb: self
                .accelerator_memory_mb
                .checked_sub(other.accelerator_memory_mb)?,
            slots: self.slots.checked_sub(other.slots)?,
            spend_cents: self.spend_cents.checked_sub(other.spend_cents)?,
            extended,
        })
    }

    fn dominant_share_bps(&self, total: &Self, weight: u32) -> u64 {
        let weight = u64::from(weight.max(1));
        let mut dominant = 0u64;
        for (used, capacity) in [
            (self.cpu_millis, total.cpu_millis),
            (self.memory_mb, total.memory_mb),
            (self.ephemeral_storage_mb, total.ephemeral_storage_mb),
            (self.gpu, total.gpu),
            (self.npu, total.npu),
            (self.accelerator_memory_mb, total.accelerator_memory_mb),
            (self.slots, total.slots),
            (self.spend_cents, total.spend_cents),
        ] {
            if let Some(share) = used.saturating_mul(10_000).checked_div(capacity) {
                dominant = dominant.max(share);
            }
        }
        for (name, used) in &self.extended {
            if let Some(capacity) = total.extended.get(name).copied().filter(|value| *value > 0) {
                dominant = dominant.max(used.saturating_mul(10_000) / capacity);
            }
        }
        dominant.saturating_mul(1_000) / weight
    }

    fn utilization_score(&self, capacity: &Self) -> i64 {
        let mut sum = 0u64;
        let mut dimensions = 0u64;
        for (free, total) in [
            (self.cpu_millis, capacity.cpu_millis),
            (self.memory_mb, capacity.memory_mb),
            (self.ephemeral_storage_mb, capacity.ephemeral_storage_mb),
            (self.gpu, capacity.gpu),
            (self.npu, capacity.npu),
            (self.accelerator_memory_mb, capacity.accelerator_memory_mb),
            (self.slots, capacity.slots),
        ] {
            if let Some(free_share) = free.saturating_mul(1_000).checked_div(total) {
                sum = sum.saturating_add(free_share);
                dimensions += 1;
            }
        }
        sum.checked_div(dimensions)
            .and_then(|mean| i64::try_from(mean).ok())
            .unwrap_or(0)
    }
}

/// Immutable identity of one replica/generation. This is the double-bind key.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct WorkIdentity {
    pub uid: String,
    pub generation: u64,
    pub replica: u32,
}

impl WorkIdentity {
    fn stable_key(&self) -> String {
        format!("{}:{}:{}", self.uid, self.generation, self.replica)
    }
}

/// All-or-nothing placement-group membership.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GangSpec {
    pub id: String,
    pub min_members: usize,
    pub expected_members: usize,
    pub topology_key: Option<String>,
}

/// One admitted replica waiting for professional scheduling.
#[derive(Debug, Clone)]
pub struct QueuedWork {
    pub identity: WorkIdentity,
    pub request: ScheduleRequest,
    pub tenant: String,
    pub estate: String,
    pub priority: i32,
    pub priority_authorized: bool,
    pub enqueue_sequence: u64,
    pub waiting_cycles: u64,
    pub resources: ResourceVector,
    pub runtime_class: String,
    pub required_labels: BTreeMap<String, String>,
    pub tolerated_taints: BTreeSet<String>,
    pub required_topology_key: Option<String>,
    pub preferred_accelerator_domain: Option<String>,
    pub minimum_interconnect_score: Option<u32>,
    pub estimated_value_cents: u64,
    pub gang: Option<GangSpec>,
    pub protected: bool,
    pub disruptible: bool,
    pub wasted_work_units: u64,
}

/// Scheduler-facing node state with authoritative topology and metering.
#[derive(Debug, Clone)]
pub struct ProfessionalNode {
    pub snapshot: crate::NodeSnapshot,
    pub estate: String,
    pub allowed_tenants: BTreeSet<String>,
    pub lease_expires_at: DateTime<Utc>,
    pub cordoned: bool,
    pub runtime_classes: BTreeSet<String>,
    pub labels: BTreeMap<String, String>,
    pub taints: BTreeSet<String>,
    pub topology_domains: BTreeMap<String, String>,
    pub accelerator_domain: Option<String>,
    /// Authoritative 0..=1000 interconnect quality; absence is ineligible when
    /// a workload declares an interconnect floor.
    pub interconnect_score: Option<u32>,
    pub capacity: ResourceVector,
    pub allocatable: ResourceVector,
    /// Authoritative estimated cost for the requested resource window.
    pub metered_cost_cents: Option<u64>,
}

impl ProfessionalNode {
    fn sync_legacy_allocatable(&mut self) {
        self.snapshot.allocatable.cpu_millis = self.allocatable.cpu_millis;
        self.snapshot.allocatable.memory_mb = self.allocatable.memory_mb;
        self.snapshot.allocatable.gpu = u32::try_from(self.allocatable.gpu).unwrap_or(u32::MAX);
        self.snapshot.allocatable.max_workloads =
            u32::try_from(self.allocatable.slots).unwrap_or(u32::MAX);
    }
}

/// Tenant DRF and quota account. Weight 1000 is neutral.
#[derive(Debug, Clone)]
pub struct TenantAccount {
    pub weight: u32,
    pub hard: ResourceVector,
    pub guaranteed: ResourceVector,
    pub used: ResourceVector,
}

/// Durable result of a successful bind.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Binding {
    pub identity: WorkIdentity,
    pub workload: String,
    pub tenant: String,
    pub node: String,
    pub resources: ResourceVector,
    pub priority: i32,
    pub protected: bool,
    pub disruptible: bool,
    pub wasted_work_units: u64,
}

#[derive(Debug, Clone)]
struct ReservationAllocation {
    work: QueuedWork,
    node: String,
}

#[derive(Debug, Clone)]
struct Reservation {
    allocations: Vec<ReservationAllocation>,
    expires_at_tick: Option<u64>,
}

/// Mutable CAS-guarded scheduling truth. Clone-before-commit makes every
/// reserve/permit/pre-bind/bind cycle transactional.
#[derive(Debug, Clone)]
pub struct SchedulingState {
    revision: u64,
    nodes: BTreeMap<String, ProfessionalNode>,
    tenants: BTreeMap<String, TenantAccount>,
    reservations: BTreeMap<String, Reservation>,
    bindings: BTreeMap<WorkIdentity, Binding>,
}

impl SchedulingState {
    #[must_use]
    pub fn new(
        revision: u64,
        nodes: impl IntoIterator<Item = ProfessionalNode>,
        tenants: BTreeMap<String, TenantAccount>,
    ) -> Self {
        Self {
            revision,
            nodes: nodes
                .into_iter()
                .map(|node| (node.snapshot.name.clone(), node))
                .collect(),
            tenants,
            reservations: BTreeMap::new(),
            bindings: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.revision
    }

    #[must_use]
    pub fn nodes(&self) -> &BTreeMap<String, ProfessionalNode> {
        &self.nodes
    }

    #[must_use]
    pub fn tenants(&self) -> &BTreeMap<String, TenantAccount> {
        &self.tenants
    }

    #[must_use]
    pub fn bindings(&self) -> &BTreeMap<WorkIdentity, Binding> {
        &self.bindings
    }

    #[must_use]
    pub fn reservation_count(&self) -> usize {
        self.reservations.len()
    }

    /// Recompute all capacity/quota accounting from reservations and bindings.
    pub fn check_invariants(&self) -> Result<(), SchedulerFailure> {
        let mut node_used: BTreeMap<String, ResourceVector> = self
            .nodes
            .keys()
            .map(|name| (name.clone(), ResourceVector::default()))
            .collect();
        let mut tenant_used: BTreeMap<String, ResourceVector> = self
            .tenants
            .keys()
            .map(|name| (name.clone(), ResourceVector::default()))
            .collect();
        let mut identities = BTreeSet::new();

        let mut account = |identity: &WorkIdentity,
                           tenant: &str,
                           resources: &ResourceVector,
                           node: &str|
         -> Result<(), SchedulerFailure> {
            if !identities.insert(identity.clone()) {
                return Err(SchedulerFailure::Invariant(
                    "one replica/generation is reserved or bound more than once".to_owned(),
                ));
            }
            let node_total = node_used.get_mut(node).ok_or_else(|| {
                SchedulerFailure::Invariant(format!("allocation references missing node {node}"))
            })?;
            *node_total = node_total
                .checked_add(resources)
                .ok_or(SchedulerFailure::ArithmeticOverflow)?;
            let tenant_total = tenant_used.get_mut(tenant).ok_or_else(|| {
                SchedulerFailure::Invariant(format!(
                    "allocation references missing tenant {tenant}"
                ))
            })?;
            *tenant_total = tenant_total
                .checked_add(resources)
                .ok_or(SchedulerFailure::ArithmeticOverflow)?;
            Ok(())
        };

        for reservation in self.reservations.values() {
            for allocation in &reservation.allocations {
                account(
                    &allocation.work.identity,
                    &allocation.work.tenant,
                    &allocation.work.resources,
                    &allocation.node,
                )?;
            }
        }
        for binding in self.bindings.values() {
            account(
                &binding.identity,
                &binding.tenant,
                &binding.resources,
                &binding.node,
            )?;
        }

        for (name, node) in &self.nodes {
            let used = node_used.get(name).expect("node accounting initialized");
            let expected_free = node.capacity.checked_sub(used).ok_or_else(|| {
                SchedulerFailure::Invariant(format!("node {name} oversubscribed"))
            })?;
            if node.allocatable != expected_free {
                return Err(SchedulerFailure::Invariant(format!(
                    "node {name} allocatable does not match reservations and bindings"
                )));
            }
        }
        for (tenant, account) in &self.tenants {
            let expected = tenant_used
                .get(tenant)
                .expect("tenant accounting initialized");
            if &account.used != expected || !account.used.fits_within(&account.hard) {
                return Err(SchedulerFailure::Invariant(format!(
                    "tenant {tenant} quota accounting mismatch or oversubscription"
                )));
            }
        }
        Ok(())
    }
}

/// Ordered extension phases required by the architecture contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CyclePhase {
    QueueSort,
    PreFilter,
    Filter,
    PostFilter,
    PreScore,
    Score,
    NormalizeScore,
    Reserve,
    Unreserve,
    Permit,
    PreBind,
    Bind,
    PostBind,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FailurePosture {
    Pending,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PluginDescriptor {
    pub name: &'static str,
    pub version: &'static str,
    pub phase: CyclePhase,
    pub timeout_steps: u32,
    pub failure_posture: FailurePosture,
}

#[derive(Debug, Clone, Default)]
pub struct PluginContext {
    pub workloads: Vec<WorkIdentity>,
    pub candidates: Vec<String>,
    pub scores: BTreeMap<String, i64>,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PluginError {
    Rejected(String),
    Timeout,
}

/// Deterministic extension point. Plugins receive only immutable cycle inputs
/// projected into [`PluginContext`]; state mutation remains inside the atomic
/// core, so an extension cannot bypass quota or bind CAS.
pub trait CyclePlugin: Send + Sync {
    fn descriptor(&self) -> PluginDescriptor;
    fn run(&self, context: &mut PluginContext) -> Result<(), PluginError>;
}

struct CorePlugin(PluginDescriptor);

impl CyclePlugin for CorePlugin {
    fn descriptor(&self) -> PluginDescriptor {
        self.0.clone()
    }

    fn run(&self, _context: &mut PluginContext) -> Result<(), PluginError> {
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PermitDecision {
    Approve,
    Wait { until_tick: u64 },
    Reject { reason: String },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScoreBreakdown {
    pub utilization: i64,
    pub topology: i64,
    pub locality: i64,
    pub spread: i64,
    pub roi: i64,
    pub consolidation: i64,
    pub total: i64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScoringPolicy {
    pub utilization_weight: i64,
    pub topology_weight: i64,
    pub locality_weight: i64,
    pub spread_weight: i64,
    pub roi_weight: i64,
    pub consolidation_weight: i64,
}

impl Default for ScoringPolicy {
    fn default() -> Self {
        Self {
            utilization_weight: 1,
            topology_weight: 1,
            locality_weight: 1,
            spread_weight: 1,
            roi_weight: 1,
            consolidation_weight: 0,
        }
    }
}

impl ScoringPolicy {
    pub fn validate(&self) -> Result<(), SchedulerFailure> {
        if [
            self.utilization_weight,
            self.topology_weight,
            self.locality_weight,
            self.spread_weight,
            self.roi_weight,
            self.consolidation_weight,
        ]
        .iter()
        .any(|weight| *weight < 0)
        {
            return Err(SchedulerFailure::InvalidConfiguration(
                "scoring weights cannot be negative".to_owned(),
            ));
        }
        if self.spread_weight > 0 && self.consolidation_weight > 0 {
            return Err(SchedulerFailure::InvalidConfiguration(
                "spread and consolidation are opposing postures".to_owned(),
            ));
        }
        Ok(())
    }
}

/// Replayable decision receipt without workload content.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CycleReceipt {
    pub snapshot_revision: u64,
    pub committed_revision: Option<u64>,
    pub phases: Vec<CyclePhase>,
    pub plugin_versions: Vec<String>,
    pub filter_reasons: BTreeMap<String, Vec<String>>,
    pub scores: BTreeMap<String, ScoreBreakdown>,
    pub chosen_nodes: Vec<String>,
    pub reservation_id: Option<String>,
    pub tie_break_inputs: Vec<String>,
}

impl CycleReceipt {
    fn new(snapshot_revision: u64) -> Self {
        Self {
            snapshot_revision,
            committed_revision: None,
            phases: Vec::new(),
            plugin_versions: Vec::new(),
            filter_reasons: BTreeMap::new(),
            scores: BTreeMap::new(),
            chosen_nodes: Vec::new(),
            reservation_id: None,
            tie_break_inputs: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CycleOutcome {
    Bound(Vec<Binding>),
    Waiting {
        reservation_id: String,
        until_tick: u64,
    },
    Pending {
        reasons: Vec<String>,
    },
    Rejected {
        reason: String,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CycleResult {
    pub outcome: CycleOutcome,
    pub receipt: CycleReceipt,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SchedulerFailure {
    StaleSnapshot { expected: u64, actual: u64 },
    UnknownTenant(String),
    UnauthorizedPriority,
    InvalidGang(String),
    AlreadyBound(WorkIdentity),
    MissingReservation(String),
    QuotaExceeded(String),
    ArithmeticOverflow,
    InvalidConfiguration(String),
    PluginFailed { plugin: String, reason: String },
    PluginPanicked { plugin: String },
    Invariant(String),
}

/// Deterministic multi-victim preemption plan. Execution remains a separate
/// CAS cycle so the caller can receipt eviction and re-check disruption state.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProfessionalPreemptionPlan {
    pub node: String,
    pub victims: Vec<WorkIdentity>,
    pub reclaimed: ResourceVector,
}

/// Full SAD-43 queue-to-post-bind scheduler.
pub struct ProfessionalScheduler {
    state: SchedulingState,
    feasibility: Scheduler,
    plugins: BTreeMap<CyclePhase, Vec<Box<dyn CyclePlugin>>>,
    scoring: ScoringPolicy,
    starvation_bound_cycles: u64,
}

impl ProfessionalScheduler {
    pub fn new(state: SchedulingState) -> Result<Self, SchedulerFailure> {
        let scoring = ScoringPolicy::default();
        scoring.validate()?;
        let mut scheduler = Self {
            state,
            feasibility: attested_scheduler(),
            plugins: BTreeMap::new(),
            scoring,
            starvation_bound_cycles: 32,
        };
        for phase in Self::ordered_phases() {
            scheduler.register_plugin(Box::new(CorePlugin(PluginDescriptor {
                name: "saddle-core",
                version: "sad43/v1",
                phase,
                timeout_steps: 1,
                failure_posture: FailurePosture::Failed,
            })))?;
        }
        scheduler.state.check_invariants()?;
        Ok(scheduler)
    }

    fn ordered_phases() -> [CyclePhase; 13] {
        [
            CyclePhase::QueueSort,
            CyclePhase::PreFilter,
            CyclePhase::Filter,
            CyclePhase::PostFilter,
            CyclePhase::PreScore,
            CyclePhase::Score,
            CyclePhase::NormalizeScore,
            CyclePhase::Reserve,
            CyclePhase::Unreserve,
            CyclePhase::Permit,
            CyclePhase::PreBind,
            CyclePhase::Bind,
            CyclePhase::PostBind,
        ]
    }

    pub fn register_plugin(
        &mut self,
        plugin: Box<dyn CyclePlugin>,
    ) -> Result<(), SchedulerFailure> {
        let descriptor = plugin.descriptor();
        if descriptor.name.trim().is_empty()
            || descriptor.version.trim().is_empty()
            || descriptor.timeout_steps == 0
        {
            return Err(SchedulerFailure::InvalidConfiguration(
                "plugins require name, version, and a non-zero deterministic timeout".to_owned(),
            ));
        }
        self.plugins
            .entry(descriptor.phase)
            .or_default()
            .push(plugin);
        Ok(())
    }

    pub fn set_scoring_policy(&mut self, scoring: ScoringPolicy) -> Result<(), SchedulerFailure> {
        scoring.validate()?;
        self.scoring = scoring;
        Ok(())
    }

    #[must_use]
    pub fn state(&self) -> &SchedulingState {
        &self.state
    }

    /// Weighted-DRF queue sort with guaranteed-minimum and starvation boosts.
    pub fn order_queue(&self, queue: &[QueuedWork]) -> Result<Vec<QueuedWork>, SchedulerFailure> {
        for work in queue {
            self.validate_work(work)?;
        }
        let total =
            self.state
                .nodes
                .values()
                .try_fold(ResourceVector::default(), |sum, node| {
                    sum.checked_add(&node.capacity)
                        .ok_or(SchedulerFailure::ArithmeticOverflow)
                })?;
        let mut ordered = queue.to_vec();
        ordered.sort_by(|left, right| {
            let left_account = &self.state.tenants[&left.tenant];
            let right_account = &self.state.tenants[&right.tenant];
            let left_starved =
                left.waiting_cycles >= self.starvation_bound_cycles && self.has_feasible_node(left);
            let right_starved = right.waiting_cycles >= self.starvation_bound_cycles
                && self.has_feasible_node(right);
            let left_below_guarantee = !left_account.guaranteed.fits_within(&left_account.used);
            let right_below_guarantee = !right_account.guaranteed.fits_within(&right_account.used);
            let left_share = left_account
                .used
                .dominant_share_bps(&total, left_account.weight);
            let right_share = right_account
                .used
                .dominant_share_bps(&total, right_account.weight);
            right_starved
                .cmp(&left_starved)
                .then_with(|| right_below_guarantee.cmp(&left_below_guarantee))
                .then_with(|| left_share.cmp(&right_share))
                .then_with(|| right.priority.cmp(&left.priority))
                .then_with(|| right.waiting_cycles.cmp(&left.waiting_cycles))
                .then_with(|| left.enqueue_sequence.cmp(&right.enqueue_sequence))
                .then_with(|| left.identity.cmp(&right.identity))
        });
        Ok(ordered)
    }

    pub fn schedule_one(
        &mut self,
        expected_revision: u64,
        work: QueuedWork,
        permit: PermitDecision,
        tick: u64,
    ) -> Result<CycleResult, SchedulerFailure> {
        self.schedule_gang(expected_revision, vec![work], permit, tick)
    }

    /// Schedule and atomically reserve/bind a complete gang. A failed phase
    /// discards the cloned transaction, so partial reservations cannot leak.
    pub fn schedule_gang(
        &mut self,
        expected_revision: u64,
        mut works: Vec<QueuedWork>,
        permit: PermitDecision,
        tick: u64,
    ) -> Result<CycleResult, SchedulerFailure> {
        self.require_revision(expected_revision)?;
        if works.is_empty() {
            return Err(SchedulerFailure::InvalidGang(
                "a scheduling cycle has no members".to_owned(),
            ));
        }
        for work in &works {
            self.validate_work(work)?;
            if self.state.bindings.contains_key(&work.identity) {
                return Err(SchedulerFailure::AlreadyBound(work.identity.clone()));
            }
        }
        self.validate_gang(&works)?;
        works.sort_by(|left, right| left.identity.cmp(&right.identity));

        let mut receipt = CycleReceipt::new(expected_revision);
        let mut context = PluginContext {
            workloads: works.iter().map(|work| work.identity.clone()).collect(),
            ..PluginContext::default()
        };
        self.run_phase(CyclePhase::QueueSort, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::PreFilter, &mut context, &mut receipt)?;

        let mut transaction = self.state.clone();
        let mut selected = Vec::with_capacity(works.len());
        let gang_domain = works
            .first()
            .and_then(|work| work.gang.as_ref())
            .and_then(|gang| gang.topology_key.as_deref());
        let mut selected_domain: Option<String> = None;
        for work in &works {
            let (node, breakdown, reasons, tie_break) =
                self.select_node(&transaction, work, gang_domain, selected_domain.as_deref())?;
            for (name, node_reasons) in reasons {
                receipt
                    .filter_reasons
                    .entry(name)
                    .or_default()
                    .extend(node_reasons);
            }
            let Some(node) = node else {
                self.run_phase(CyclePhase::Filter, &mut context, &mut receipt)?;
                self.run_phase(CyclePhase::PostFilter, &mut context, &mut receipt)?;
                let reasons = receipt.filter_reasons.values().flatten().cloned().collect();
                return Ok(CycleResult {
                    outcome: CycleOutcome::Pending { reasons },
                    receipt,
                });
            };
            if let Some(key) = gang_domain {
                selected_domain = transaction.nodes[&node].topology_domains.get(key).cloned();
            }
            receipt.scores.insert(node.clone(), breakdown);
            receipt.tie_break_inputs.push(tie_break);
            transaction.reserve_node_only(&node, &work.resources)?;
            selected.push((work.clone(), node));
        }
        context.candidates = selected.iter().map(|(_, node)| node.clone()).collect();
        context.scores = receipt
            .scores
            .iter()
            .map(|(node, score)| (node.clone(), score.total))
            .collect();
        self.run_phase(CyclePhase::Filter, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::PostFilter, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::PreScore, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::Score, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::NormalizeScore, &mut context, &mut receipt)?;

        // Rebuild the transaction from the coherent revision; the selection
        // clone above only prevents intra-gang node oversubscription.
        transaction = self.state.clone();
        let reservation_id = Self::reservation_id(expected_revision, &works);
        transaction.reserve(&reservation_id, &selected)?;
        receipt.reservation_id = Some(reservation_id.clone());
        receipt.chosen_nodes = selected.iter().map(|(_, node)| node.clone()).collect();
        self.run_phase(CyclePhase::Reserve, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::Permit, &mut context, &mut receipt)?;

        match permit {
            PermitDecision::Reject { reason } => {
                self.run_phase(CyclePhase::Unreserve, &mut context, &mut receipt)?;
                Ok(CycleResult {
                    outcome: CycleOutcome::Rejected { reason },
                    receipt,
                })
            }
            PermitDecision::Wait { until_tick } => {
                if until_tick <= tick {
                    self.run_phase(CyclePhase::Unreserve, &mut context, &mut receipt)?;
                    return Ok(CycleResult {
                        outcome: CycleOutcome::Rejected {
                            reason: "permit deadline is not in the future".to_owned(),
                        },
                        receipt,
                    });
                }
                transaction
                    .reservations
                    .get_mut(&reservation_id)
                    .expect("reservation created")
                    .expires_at_tick = Some(until_tick);
                transaction.revision = expected_revision.saturating_add(1);
                transaction.check_invariants()?;
                receipt.committed_revision = Some(transaction.revision);
                self.state = transaction;
                Ok(CycleResult {
                    outcome: CycleOutcome::Waiting {
                        reservation_id,
                        until_tick,
                    },
                    receipt,
                })
            }
            PermitDecision::Approve => {
                self.finish_bind(transaction, reservation_id, context, receipt)
            }
        }
    }

    /// Continue or reject a bounded permit wait using a fresh state revision.
    pub fn resolve_permit(
        &mut self,
        expected_revision: u64,
        reservation_id: &str,
        decision: PermitDecision,
        tick: u64,
    ) -> Result<CycleResult, SchedulerFailure> {
        self.require_revision(expected_revision)?;
        let reservation = self
            .state
            .reservations
            .get(reservation_id)
            .cloned()
            .ok_or_else(|| SchedulerFailure::MissingReservation(reservation_id.to_owned()))?;
        let mut receipt = CycleReceipt::new(expected_revision);
        receipt.reservation_id = Some(reservation_id.to_owned());
        receipt.chosen_nodes = reservation
            .allocations
            .iter()
            .map(|allocation| allocation.node.clone())
            .collect();
        let mut context = PluginContext {
            workloads: reservation
                .allocations
                .iter()
                .map(|allocation| allocation.work.identity.clone())
                .collect(),
            candidates: receipt.chosen_nodes.clone(),
            ..PluginContext::default()
        };
        self.run_phase(CyclePhase::Permit, &mut context, &mut receipt)?;
        let expired = reservation
            .expires_at_tick
            .is_some_and(|deadline| tick >= deadline);
        match decision {
            PermitDecision::Approve if !expired => self.finish_bind(
                self.state.clone(),
                reservation_id.to_owned(),
                context,
                receipt,
            ),
            PermitDecision::Wait { until_tick } if !expired && until_tick > tick => {
                let mut transaction = self.state.clone();
                transaction
                    .reservations
                    .get_mut(reservation_id)
                    .expect("reservation exists")
                    .expires_at_tick = Some(until_tick);
                transaction.revision = expected_revision.saturating_add(1);
                receipt.committed_revision = Some(transaction.revision);
                self.state = transaction;
                Ok(CycleResult {
                    outcome: CycleOutcome::Waiting {
                        reservation_id: reservation_id.to_owned(),
                        until_tick,
                    },
                    receipt,
                })
            }
            PermitDecision::Reject { reason } => {
                self.unreserve_committed(
                    expected_revision,
                    reservation_id,
                    &mut context,
                    &mut receipt,
                )?;
                Ok(CycleResult {
                    outcome: CycleOutcome::Rejected { reason },
                    receipt,
                })
            }
            _ => {
                self.unreserve_committed(
                    expected_revision,
                    reservation_id,
                    &mut context,
                    &mut receipt,
                )?;
                Ok(CycleResult {
                    outcome: CycleOutcome::Rejected {
                        reason: "permit expired or invalid transition".to_owned(),
                    },
                    receipt,
                })
            }
        }
    }

    /// Expire all permit waits at or before `tick`, releasing node and quota
    /// reservations idempotently in one revision.
    pub fn expire_permits(&mut self, tick: u64) -> Result<usize, SchedulerFailure> {
        let expired: Vec<String> = self
            .state
            .reservations
            .iter()
            .filter(|(_, reservation)| {
                reservation
                    .expires_at_tick
                    .is_some_and(|deadline| tick >= deadline)
            })
            .map(|(id, _)| id.clone())
            .collect();
        if expired.is_empty() {
            return Ok(0);
        }
        let mut transaction = self.state.clone();
        for id in &expired {
            transaction.unreserve(id)?;
        }
        transaction.revision = transaction.revision.saturating_add(1);
        transaction.check_invariants()?;
        self.state = transaction;
        Ok(expired.len())
    }

    /// Release a completed binding and return capacity/quota exactly once.
    pub fn release_binding(
        &mut self,
        expected_revision: u64,
        identity: &WorkIdentity,
    ) -> Result<(), SchedulerFailure> {
        self.require_revision(expected_revision)?;
        let mut transaction = self.state.clone();
        let binding = transaction.bindings.remove(identity).ok_or_else(|| {
            SchedulerFailure::Invariant("cannot release a missing binding".to_owned())
        })?;
        transaction.release_allocation(&binding.tenant, &binding.node, &binding.resources)?;
        transaction.revision = expected_revision.saturating_add(1);
        transaction.check_invariants()?;
        self.state = transaction;
        Ok(())
    }

    /// Deterministic multi-victim preemption. Only nodes that pass every hard
    /// predicate except capacity are considered, and only lower-priority,
    /// disruption-allowed bindings can be victims.
    pub fn plan_preemption(
        &self,
        incoming: &QueuedWork,
    ) -> Result<Option<ProfessionalPreemptionPlan>, SchedulerFailure> {
        self.validate_work(incoming)?;
        let mut plans = Vec::new();
        for node in self.state.nodes.values() {
            let legacy = self.feasibility.evaluate(&incoming.request, &node.snapshot);
            if legacy.verdicts.iter().any(|verdict| {
                matches!(
                    verdict,
                    crate::FilterVerdict::Unfit { filter, .. } if *filter != "capacity"
                )
            }) {
                continue;
            }
            if !self.hard_filter(node, incoming, true, None).is_empty() {
                continue;
            }
            if incoming.resources.fits_within(&node.allocatable) {
                continue;
            }
            let mut victims: Vec<&Binding> = self
                .state
                .bindings
                .values()
                .filter(|binding| {
                    binding.node == node.snapshot.name
                        && binding.priority < incoming.priority
                        && binding.disruptible
                        && !binding.protected
                })
                .collect();
            victims.sort_by(|left, right| {
                left.priority
                    .cmp(&right.priority)
                    .then_with(|| left.wasted_work_units.cmp(&right.wasted_work_units))
                    .then_with(|| left.identity.cmp(&right.identity))
            });
            let mut reclaimed = ResourceVector::default();
            let mut selected = Vec::new();
            for victim in victims {
                reclaimed = reclaimed
                    .checked_add(&victim.resources)
                    .ok_or(SchedulerFailure::ArithmeticOverflow)?;
                selected.push(victim.identity.clone());
                let available = node
                    .allocatable
                    .checked_add(&reclaimed)
                    .ok_or(SchedulerFailure::ArithmeticOverflow)?;
                if incoming.resources.fits_within(&available) {
                    plans.push(ProfessionalPreemptionPlan {
                        node: node.snapshot.name.clone(),
                        victims: selected,
                        reclaimed,
                    });
                    break;
                }
            }
        }
        plans.sort_by(|left, right| {
            left.victims
                .len()
                .cmp(&right.victims.len())
                .then_with(|| left.node.cmp(&right.node))
                .then_with(|| left.victims.cmp(&right.victims))
        });
        Ok(plans.into_iter().next())
    }

    fn finish_bind(
        &mut self,
        mut transaction: SchedulingState,
        reservation_id: String,
        mut context: PluginContext,
        mut receipt: CycleReceipt,
    ) -> Result<CycleResult, SchedulerFailure> {
        self.run_phase(CyclePhase::PreBind, &mut context, &mut receipt)?;
        self.run_phase(CyclePhase::Bind, &mut context, &mut receipt)?;
        let bindings = transaction.bind_reservation(&reservation_id)?;
        self.run_phase(CyclePhase::PostBind, &mut context, &mut receipt)?;
        transaction.revision = self.state.revision.saturating_add(1);
        transaction.check_invariants()?;
        receipt.committed_revision = Some(transaction.revision);
        self.state = transaction;
        Ok(CycleResult {
            outcome: CycleOutcome::Bound(bindings),
            receipt,
        })
    }

    fn unreserve_committed(
        &mut self,
        expected_revision: u64,
        reservation_id: &str,
        context: &mut PluginContext,
        receipt: &mut CycleReceipt,
    ) -> Result<(), SchedulerFailure> {
        self.run_phase(CyclePhase::Unreserve, context, receipt)?;
        let mut transaction = self.state.clone();
        transaction.unreserve(reservation_id)?;
        transaction.revision = expected_revision.saturating_add(1);
        transaction.check_invariants()?;
        receipt.committed_revision = Some(transaction.revision);
        self.state = transaction;
        Ok(())
    }

    fn run_phase(
        &self,
        phase: CyclePhase,
        context: &mut PluginContext,
        receipt: &mut CycleReceipt,
    ) -> Result<(), SchedulerFailure> {
        receipt.phases.push(phase);
        for plugin in self.plugins.get(&phase).into_iter().flatten() {
            let descriptor = plugin.descriptor();
            receipt
                .plugin_versions
                .push(format!("{}@{}", descriptor.name, descriptor.version));
            let result = catch_unwind(AssertUnwindSafe(|| plugin.run(context))).map_err(|_| {
                SchedulerFailure::PluginPanicked {
                    plugin: descriptor.name.to_owned(),
                }
            })?;
            result.map_err(|error| SchedulerFailure::PluginFailed {
                plugin: descriptor.name.to_owned(),
                reason: match error {
                    PluginError::Rejected(reason) => reason,
                    PluginError::Timeout => format!(
                        "deterministic timeout after {} steps ({:?})",
                        descriptor.timeout_steps, descriptor.failure_posture
                    ),
                },
            })?;
        }
        Ok(())
    }

    fn select_node(
        &self,
        state: &SchedulingState,
        work: &QueuedWork,
        gang_topology_key: Option<&str>,
        selected_domain: Option<&str>,
    ) -> Result<Selection, SchedulerFailure> {
        let snapshots: Vec<_> = state
            .nodes
            .values()
            .map(|node| node.snapshot.clone())
            .collect();
        let legacy = self.feasibility.evaluate_nodes(&work.request, &snapshots);
        let mut reasons = BTreeMap::new();
        let mut candidates = Vec::new();
        for evaluation in legacy {
            let node_name = evaluation.signals.node.clone();
            let node = &state.nodes[&node_name];
            let mut node_reasons: Vec<String> = evaluation
                .verdicts
                .iter()
                .filter_map(|verdict| match verdict {
                    crate::FilterVerdict::Fit => None,
                    crate::FilterVerdict::Unfit { filter, reason } => {
                        Some(format!("{reason} [{filter}]"))
                    }
                })
                .collect();
            node_reasons.extend(self.hard_filter(
                node,
                work,
                false,
                gang_topology_key.zip(selected_domain),
            ));
            if node_reasons.is_empty() {
                let breakdown = self.score_node(state, node, work);
                let tie = format!("{}:{}", work.identity.stable_key(), node_name);
                candidates.push((node_name, breakdown, stable_hash(&tie), tie));
            } else {
                reasons.insert(node_name, node_reasons);
            }
        }
        candidates.sort_by(|left, right| {
            right
                .1
                .total
                .cmp(&left.1.total)
                .then_with(|| left.2.cmp(&right.2))
                .then_with(|| left.0.cmp(&right.0))
        });
        Ok(match candidates.into_iter().next() {
            Some((node, score, _, tie)) => (Some(node), score, reasons, tie),
            None => (None, ScoreBreakdown::zero(), reasons, String::new()),
        })
    }

    fn hard_filter(
        &self,
        node: &ProfessionalNode,
        work: &QueuedWork,
        ignore_capacity: bool,
        gang_domain: Option<(&str, &str)>,
    ) -> Vec<String> {
        let mut reasons = Vec::new();
        if node.lease_expires_at <= work.request.observed_at {
            reasons.push("node lease is absent or expired [lease]".to_owned());
        }
        if node.cordoned {
            reasons.push("node is cordoned or draining [cordon]".to_owned());
        }
        if node.estate != work.estate {
            reasons.push("node belongs to a different estate [sovereignty]".to_owned());
        }
        if !node.allowed_tenants.contains(&work.tenant) {
            reasons.push("tenant is not eligible on node [sovereignty]".to_owned());
        }
        if !node.runtime_classes.contains(&work.runtime_class) {
            reasons.push("runtime class is unsupported [runtime-class]".to_owned());
        }
        for (key, value) in &work.required_labels {
            if node.labels.get(key) != Some(value) {
                reasons.push(format!("required label {key}={value} is absent [selector]"));
            }
        }
        for taint in &node.taints {
            if !work.tolerated_taints.contains(taint) {
                reasons.push(format!("taint {taint} is not tolerated [taint]"));
            }
        }
        if let Some(key) = work.required_topology_key.as_deref()
            && !node.topology_domains.contains_key(key)
        {
            reasons.push(format!("required topology key {key} is absent [topology]"));
        }
        if let Some((key, domain)) = gang_domain
            && node.topology_domains.get(key).map(String::as_str) != Some(domain)
        {
            reasons.push(format!(
                "gang topology domain {key}={domain} mismatches [topology]"
            ));
        }
        if let Some(minimum) = work.minimum_interconnect_score {
            match node.interconnect_score {
                Some(actual) if actual >= minimum => {}
                Some(actual) => reasons.push(format!(
                    "accelerator interconnect score {actual} is below {minimum} [topology]"
                )),
                None => reasons
                    .push("accelerator interconnect observation is missing [topology]".to_owned()),
            }
        }
        if work.resources.spend_cents > 0 && node.metered_cost_cents.is_none() {
            reasons.push("authoritative cost observation is missing [budget-roi]".to_owned());
        }
        if let Some(account) = self.state.tenants.get(&work.tenant) {
            match account.used.checked_add(&work.resources) {
                Some(prospective) if prospective.fits_within(&account.hard) => {}
                _ => reasons.push("tenant hard quota would be exceeded [quota]".to_owned()),
            }
        } else {
            reasons.push("tenant quota state is missing [quota]".to_owned());
        }
        if !ignore_capacity && !work.resources.fits_within(&node.allocatable) {
            reasons.push("reported allocatable resources are insufficient [capacity]".to_owned());
        }
        reasons
    }

    fn score_node(
        &self,
        state: &SchedulingState,
        node: &ProfessionalNode,
        work: &QueuedWork,
    ) -> ScoreBreakdown {
        let utilization = node.allocatable.utilization_score(&node.capacity);
        let topology = i64::from(node.interconnect_score.unwrap_or(0).min(1_000));
        let locality: i64 =
            if work.preferred_accelerator_domain.as_deref() == node.accelerator_domain.as_deref() {
                1_000
            } else {
                0
            };
        let same_domain = state
            .bindings
            .values()
            .filter(|binding| binding.workload == work.request.workload_name)
            .filter(|binding| {
                state.nodes[&binding.node].accelerator_domain == node.accelerator_domain
            })
            .count();
        let spread = 1_000i64.saturating_sub(
            i64::try_from(same_domain)
                .unwrap_or(i64::MAX)
                .saturating_mul(250),
        );
        let roi = node.metered_cost_cents.map_or(0, |cost| {
            if cost == 0 {
                1_000
            } else {
                i64::try_from(
                    work.estimated_value_cents
                        .saturating_mul(1_000)
                        .checked_div(cost)
                        .unwrap_or(0)
                        .min(1_000),
                )
                .unwrap_or(1_000)
            }
        });
        let consolidation = 1_000i64.saturating_sub(utilization);
        let total = utilization
            .saturating_mul(self.scoring.utilization_weight)
            .saturating_add(topology.saturating_mul(self.scoring.topology_weight))
            .saturating_add(locality.saturating_mul(self.scoring.locality_weight))
            .saturating_add(spread.saturating_mul(self.scoring.spread_weight))
            .saturating_add(roi.saturating_mul(self.scoring.roi_weight))
            .saturating_add(consolidation.saturating_mul(self.scoring.consolidation_weight));
        ScoreBreakdown {
            utilization,
            topology,
            locality,
            spread,
            roi,
            consolidation,
            total,
        }
    }

    fn validate_work(&self, work: &QueuedWork) -> Result<(), SchedulerFailure> {
        if !work.priority_authorized {
            return Err(SchedulerFailure::UnauthorizedPriority);
        }
        if work.tenant.trim().is_empty()
            || work.estate.trim().is_empty()
            || work.runtime_class.trim().is_empty()
        {
            return Err(SchedulerFailure::InvalidConfiguration(
                "tenant, estate, and runtime class are required".to_owned(),
            ));
        }
        if !self.state.tenants.contains_key(&work.tenant) {
            return Err(SchedulerFailure::UnknownTenant(work.tenant.clone()));
        }
        Ok(())
    }

    fn validate_gang(&self, works: &[QueuedWork]) -> Result<(), SchedulerFailure> {
        let Some(gang) = works.first().and_then(|work| work.gang.as_ref()) else {
            if works.len() == 1 {
                return Ok(());
            }
            return Err(SchedulerFailure::InvalidGang(
                "multiple members require a placement-group identity".to_owned(),
            ));
        };
        if gang.id.trim().is_empty()
            || gang.min_members == 0
            || gang.min_members > gang.expected_members
            || works.len() != gang.expected_members
            || works.len() < gang.min_members
        {
            return Err(SchedulerFailure::InvalidGang(
                "placement group is incomplete or has invalid bounds".to_owned(),
            ));
        }
        let tenant = &works[0].tenant;
        let estate = &works[0].estate;
        let mut identities = BTreeSet::new();
        if works.iter().any(|work| {
            work.tenant != *tenant
                || work.estate != *estate
                || work.gang.as_ref() != Some(gang)
                || !identities.insert(work.identity.clone())
        }) {
            return Err(SchedulerFailure::InvalidGang(
                "gang members cross authority or repeat an identity".to_owned(),
            ));
        }
        Ok(())
    }

    fn has_feasible_node(&self, work: &QueuedWork) -> bool {
        self.state
            .nodes
            .values()
            .any(|node| self.hard_filter(node, work, false, None).is_empty())
    }

    fn require_revision(&self, expected: u64) -> Result<(), SchedulerFailure> {
        if expected == self.state.revision {
            Ok(())
        } else {
            Err(SchedulerFailure::StaleSnapshot {
                expected,
                actual: self.state.revision,
            })
        }
    }

    fn reservation_id(revision: u64, works: &[QueuedWork]) -> String {
        let seed = works
            .iter()
            .map(|work| work.identity.stable_key())
            .collect::<Vec<_>>()
            .join("|");
        format!("sad43-r{revision}-{:016x}", stable_hash(&seed))
    }
}

type Selection = (
    Option<String>,
    ScoreBreakdown,
    BTreeMap<String, Vec<String>>,
    String,
);

impl ScoreBreakdown {
    fn zero() -> Self {
        Self {
            utilization: 0,
            topology: 0,
            locality: 0,
            spread: 0,
            roi: 0,
            consolidation: 0,
            total: 0,
        }
    }
}

impl SchedulingState {
    fn reserve_node_only(
        &mut self,
        node: &str,
        resources: &ResourceVector,
    ) -> Result<(), SchedulerFailure> {
        let node = self
            .nodes
            .get_mut(node)
            .ok_or_else(|| SchedulerFailure::Invariant("selected node disappeared".to_owned()))?;
        node.allocatable = node.allocatable.checked_sub(resources).ok_or_else(|| {
            SchedulerFailure::Invariant("node capacity oversubscription".to_owned())
        })?;
        node.sync_legacy_allocatable();
        Ok(())
    }

    fn reserve(
        &mut self,
        reservation_id: &str,
        selected: &[(QueuedWork, String)],
    ) -> Result<(), SchedulerFailure> {
        if self.reservations.contains_key(reservation_id) {
            return Err(SchedulerFailure::Invariant(
                "reservation id already exists".to_owned(),
            ));
        }
        let mut tenant_additions: BTreeMap<String, ResourceVector> = BTreeMap::new();
        for (work, node) in selected {
            if self.bindings.contains_key(&work.identity)
                || self.reservations.values().any(|reservation| {
                    reservation
                        .allocations
                        .iter()
                        .any(|allocation| allocation.work.identity == work.identity)
                })
            {
                return Err(SchedulerFailure::AlreadyBound(work.identity.clone()));
            }
            self.reserve_node_only(node, &work.resources)?;
            let addition = tenant_additions.entry(work.tenant.clone()).or_default();
            *addition = addition
                .checked_add(&work.resources)
                .ok_or(SchedulerFailure::ArithmeticOverflow)?;
        }
        for (tenant, addition) in tenant_additions {
            let account = self
                .tenants
                .get_mut(&tenant)
                .ok_or_else(|| SchedulerFailure::UnknownTenant(tenant.clone()))?;
            let prospective = account
                .used
                .checked_add(&addition)
                .ok_or(SchedulerFailure::ArithmeticOverflow)?;
            if !prospective.fits_within(&account.hard) {
                return Err(SchedulerFailure::QuotaExceeded(tenant));
            }
            account.used = prospective;
        }
        self.reservations.insert(
            reservation_id.to_owned(),
            Reservation {
                allocations: selected
                    .iter()
                    .map(|(work, node)| ReservationAllocation {
                        work: work.clone(),
                        node: node.clone(),
                    })
                    .collect(),
                expires_at_tick: None,
            },
        );
        Ok(())
    }

    fn bind_reservation(&mut self, reservation_id: &str) -> Result<Vec<Binding>, SchedulerFailure> {
        let reservation = self
            .reservations
            .remove(reservation_id)
            .ok_or_else(|| SchedulerFailure::MissingReservation(reservation_id.to_owned()))?;
        let mut bindings = Vec::with_capacity(reservation.allocations.len());
        for allocation in reservation.allocations {
            if self.bindings.contains_key(&allocation.work.identity) {
                return Err(SchedulerFailure::AlreadyBound(
                    allocation.work.identity.clone(),
                ));
            }
            let binding = Binding {
                identity: allocation.work.identity.clone(),
                workload: allocation.work.request.workload_name,
                tenant: allocation.work.tenant,
                node: allocation.node,
                resources: allocation.work.resources,
                priority: allocation.work.priority,
                protected: allocation.work.protected,
                disruptible: allocation.work.disruptible,
                wasted_work_units: allocation.work.wasted_work_units,
            };
            self.bindings
                .insert(binding.identity.clone(), binding.clone());
            bindings.push(binding);
        }
        Ok(bindings)
    }

    fn unreserve(&mut self, reservation_id: &str) -> Result<(), SchedulerFailure> {
        let reservation = self
            .reservations
            .remove(reservation_id)
            .ok_or_else(|| SchedulerFailure::MissingReservation(reservation_id.to_owned()))?;
        for allocation in reservation.allocations {
            self.release_allocation(
                &allocation.work.tenant,
                &allocation.node,
                &allocation.work.resources,
            )?;
        }
        Ok(())
    }

    fn release_allocation(
        &mut self,
        tenant: &str,
        node: &str,
        resources: &ResourceVector,
    ) -> Result<(), SchedulerFailure> {
        let node = self
            .nodes
            .get_mut(node)
            .ok_or_else(|| SchedulerFailure::Invariant("allocated node disappeared".to_owned()))?;
        node.allocatable = node
            .allocatable
            .checked_add(resources)
            .ok_or(SchedulerFailure::ArithmeticOverflow)?;
        if !node.allocatable.fits_within(&node.capacity) {
            return Err(SchedulerFailure::Invariant(
                "resource release exceeds node capacity".to_owned(),
            ));
        }
        node.sync_legacy_allocatable();
        let account = self
            .tenants
            .get_mut(tenant)
            .ok_or_else(|| SchedulerFailure::UnknownTenant(tenant.to_owned()))?;
        account.used = account.used.checked_sub(resources).ok_or_else(|| {
            SchedulerFailure::Invariant("resource release exceeds tenant usage".to_owned())
        })?;
        Ok(())
    }
}

/// Fixed FNV-1a tie-breaker: stable across processes and platforms.
fn stable_hash(value: &str) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325u64;
    for byte in value.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    hash
}

/// Bounded scheduler queue classes with explicit wake transitions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum QueueClass {
    Active,
    Backoff,
    Unschedulable,
    PermitWait,
}

#[derive(Debug, Clone)]
pub struct BoundedQueues {
    capacity: usize,
    entries: BTreeMap<WorkIdentity, (QueueClass, QueuedWork)>,
}

impl BoundedQueues {
    #[must_use]
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity,
            entries: BTreeMap::new(),
        }
    }

    pub fn enqueue(&mut self, class: QueueClass, work: QueuedWork) -> Result<(), SchedulerFailure> {
        if self.entries.len() >= self.capacity && !self.entries.contains_key(&work.identity) {
            return Err(SchedulerFailure::Invariant(
                "scheduler queue capacity reached".to_owned(),
            ));
        }
        self.entries.insert(work.identity.clone(), (class, work));
        Ok(())
    }

    /// Wake a bounded class on a concrete estate event (capacity, quota,
    /// topology, policy, or permit change) by moving all of it to Active.
    pub fn wake(&mut self, class: QueueClass) -> usize {
        let mut moved = 0;
        for (current, _) in self.entries.values_mut() {
            if *current == class {
                *current = QueueClass::Active;
                moved += 1;
            }
        }
        moved
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    #[must_use]
    pub fn class_of(&self, identity: &WorkIdentity) -> Option<QueueClass> {
        self.entries.get(identity).map(|(class, _)| *class)
    }
}
