//! SAD-43 deterministic property and adversarial scheduler gate.

use std::collections::{BTreeMap, BTreeSet};

use chrono::{DateTime, Duration, Utc};
use fabric_contracts::Classification;
use saddle_estate::{AttestationProfile, Capacity, SchedulingConstraints, WorkloadKind};
use saddle_scheduler::{
    BoundedQueues, CycleOutcome, CyclePhase, CyclePlugin, FailurePosture, GangSpec, PermitDecision,
    PluginContext, PluginDescriptor, PluginError, ProfessionalNode, ProfessionalScheduler,
    QueueClass, QueuedWork, ResourceVector, SchedulerFailure, SchedulingState, TenantAccount,
    WorkIdentity,
};

const HISTORIES: usize = 256;
const STEPS_PER_HISTORY: usize = 64;
const STARVATION_BOUND_CYCLES: u64 = 32;

fn now() -> DateTime<Utc> {
    DateTime::parse_from_rfc3339("2026-07-20T12:00:00Z")
        .unwrap()
        .with_timezone(&Utc)
}

fn resources(cpu: u64, memory: u64, gpu: u64, slots: u64) -> ResourceVector {
    ResourceVector {
        cpu_millis: cpu,
        memory_mb: memory,
        gpu,
        slots,
        ..ResourceVector::default()
    }
}

fn tenant(hard: ResourceVector, guaranteed: ResourceVector, weight: u32) -> TenantAccount {
    TenantAccount {
        weight,
        hard,
        guaranteed,
        used: ResourceVector::default(),
    }
}

#[allow(clippy::too_many_arguments)]
fn node(
    name: &str,
    ring: u8,
    floor: Classification,
    allowed_tenants: &[&str],
    capacity: ResourceVector,
    zone: &str,
    accelerator_domain: &str,
    interconnect_score: Option<u32>,
    cost: Option<u64>,
) -> ProfessionalNode {
    let basic = Capacity {
        cpu_millis: capacity.cpu_millis,
        memory_mb: capacity.memory_mb,
        gpu: u32::try_from(capacity.gpu).unwrap(),
        max_workloads: u32::try_from(capacity.slots).unwrap(),
    };
    ProfessionalNode {
        snapshot: saddle_scheduler::NodeSnapshot {
            name: name.to_owned(),
            ring,
            attestation_floor: floor,
            attestation: AttestationProfile::default(),
            attestation_verified_until: Some((now() + Duration::hours(1)).to_rfc3339()),
            ready: true,
            capacity: basic,
            allocatable: basic,
            last_heartbeat: Some(now().to_rfc3339()),
            resource_version: 7,
        },
        estate: "estate-a".to_owned(),
        allowed_tenants: allowed_tenants
            .iter()
            .map(|value| (*value).to_owned())
            .collect(),
        lease_expires_at: now() + Duration::minutes(5),
        cordoned: false,
        runtime_classes: BTreeSet::from(["process".to_owned(), "containerd".to_owned()]),
        labels: BTreeMap::from([("region".to_owned(), "us-west".to_owned())]),
        taints: BTreeSet::new(),
        topology_domains: BTreeMap::from([
            ("zone".to_owned(), zone.to_owned()),
            (
                "accelerator-island".to_owned(),
                accelerator_domain.to_owned(),
            ),
        ]),
        accelerator_domain: Some(accelerator_domain.to_owned()),
        interconnect_score,
        capacity: capacity.clone(),
        allocatable: capacity,
        metered_cost_cents: cost,
    }
}

fn base_state(nodes: Vec<ProfessionalNode>) -> SchedulingState {
    let hard = resources(64, 128, 16, 64);
    SchedulingState::new(
        1,
        nodes,
        BTreeMap::from([
            (
                "red".to_owned(),
                tenant(hard.clone(), resources(4, 4, 0, 1), 1_000),
            ),
            (
                "blue".to_owned(),
                tenant(hard.clone(), resources(4, 4, 0, 1), 2_000),
            ),
            (
                "green".to_owned(),
                tenant(hard, ResourceVector::default(), 1_000),
            ),
        ]),
    )
}

fn work(id: u64, tenant: &str, request: ResourceVector) -> QueuedWork {
    QueuedWork {
        identity: WorkIdentity {
            uid: format!("uid-{id}"),
            generation: 1,
            replica: 0,
        },
        request: saddle_scheduler::ScheduleRequest {
            workload_name: format!("work-{id}"),
            workload_kind: WorkloadKind::Gateway,
            ring: 1,
            classification_ceiling: Classification::Public,
            constraints: SchedulingConstraints {
                resources: Capacity {
                    cpu_millis: request.cpu_millis,
                    memory_mb: request.memory_mb,
                    gpu: u32::try_from(request.gpu).unwrap(),
                    max_workloads: u32::try_from(request.slots).unwrap(),
                },
                ..SchedulingConstraints::default()
            },
            provider_eligibility: saddle_scheduler::ProviderEligibility::NotRequired,
            observed_at: now(),
            heartbeat_ttl_seconds: 30,
            already_placed_on: Vec::new(),
        },
        tenant: tenant.to_owned(),
        estate: "estate-a".to_owned(),
        priority: 0,
        priority_authorized: true,
        enqueue_sequence: id,
        waiting_cycles: 0,
        resources: request,
        runtime_class: "process".to_owned(),
        required_labels: BTreeMap::new(),
        tolerated_taints: BTreeSet::new(),
        required_topology_key: None,
        preferred_accelerator_domain: None,
        minimum_interconnect_score: None,
        estimated_value_cents: 0,
        gang: None,
        protected: false,
        disruptible: true,
        wasted_work_units: 0,
    }
}

fn one_node_scheduler(capacity: ResourceVector) -> ProfessionalScheduler {
    ProfessionalScheduler::new(base_state(vec![node(
        "node-a",
        1,
        Classification::Secret,
        &["red", "blue", "green"],
        capacity,
        "zone-a",
        "nv-a",
        Some(900),
        Some(5),
    )]))
    .unwrap()
}

#[test]
fn ordered_queue_to_post_bind_cycle_is_replayable_and_cas_guarded() {
    let mut scheduler = one_node_scheduler(resources(8, 16, 2, 4));
    let candidate = work(1, "red", resources(2, 2, 0, 1));
    let result = scheduler
        .schedule_one(1, candidate.clone(), PermitDecision::Approve, 0)
        .unwrap();
    let CycleOutcome::Bound(bindings) = result.outcome else {
        panic!("expected a durable bind")
    };
    assert_eq!(bindings.len(), 1);
    assert_eq!(
        result.receipt.phases,
        vec![
            CyclePhase::QueueSort,
            CyclePhase::PreFilter,
            CyclePhase::Filter,
            CyclePhase::PostFilter,
            CyclePhase::PreScore,
            CyclePhase::Score,
            CyclePhase::NormalizeScore,
            CyclePhase::Reserve,
            CyclePhase::Permit,
            CyclePhase::PreBind,
            CyclePhase::Bind,
            CyclePhase::PostBind,
        ]
    );
    assert_eq!(result.receipt.snapshot_revision, 1);
    assert_eq!(result.receipt.committed_revision, Some(2));
    assert!(result.receipt.reservation_id.is_some());
    assert!(!result.receipt.tie_break_inputs.is_empty());
    assert_eq!(scheduler.state().reservation_count(), 0);
    scheduler.state().check_invariants().unwrap();

    assert_eq!(
        scheduler.schedule_one(1, candidate.clone(), PermitDecision::Approve, 1),
        Err(SchedulerFailure::StaleSnapshot {
            expected: 1,
            actual: 2
        })
    );
    assert_eq!(
        scheduler.schedule_one(2, candidate, PermitDecision::Approve, 1),
        Err(SchedulerFailure::AlreadyBound(WorkIdentity {
            uid: "uid-1".to_owned(),
            generation: 1,
            replica: 0,
        }))
    );
}

#[test]
fn hard_sovereignty_quota_and_capacity_filters_never_relax_under_pressure() {
    let mut state = base_state(vec![
        node(
            "red-only",
            1,
            Classification::Secret,
            &["red"],
            resources(4, 8, 0, 2),
            "zone-a",
            "nv-a",
            Some(900),
            Some(5),
        ),
        node(
            "roomy-blue",
            1,
            Classification::Secret,
            &["blue"],
            resources(64, 128, 0, 16),
            "zone-b",
            "pcie-b",
            Some(400),
            Some(1),
        ),
    ]);
    state.tenants().get("red").unwrap();
    // Rebuild with a deliberately small red hard ceiling.
    state = SchedulingState::new(
        1,
        state.nodes().values().cloned().collect::<Vec<_>>(),
        BTreeMap::from([
            (
                "red".to_owned(),
                tenant(resources(4, 8, 0, 2), ResourceVector::default(), 1_000),
            ),
            (
                "blue".to_owned(),
                tenant(resources(64, 128, 0, 16), ResourceVector::default(), 1_000),
            ),
        ]),
    );
    let mut scheduler = ProfessionalScheduler::new(state).unwrap();
    let first = work(10, "red", resources(3, 2, 0, 1));
    assert!(matches!(
        scheduler
            .schedule_one(1, first, PermitDecision::Approve, 0)
            .unwrap()
            .outcome,
        CycleOutcome::Bound(_)
    ));
    let second = work(11, "red", resources(2, 2, 0, 1));
    let result = scheduler
        .schedule_one(2, second, PermitDecision::Approve, 1)
        .unwrap();
    let CycleOutcome::Pending { reasons } = result.outcome else {
        panic!("red work must remain pending")
    };
    assert!(reasons.iter().any(|reason| reason.contains("quota")));
    assert_eq!(scheduler.state().bindings().len(), 1);
    assert!(
        scheduler.state().nodes()["roomy-blue"]
            .allocatable
            .cpu_millis
            == 64
    );
    scheduler.state().check_invariants().unwrap();
}

#[test]
fn gang_reservation_wait_reject_and_expiry_are_all_or_nothing() {
    let mut scheduler = ProfessionalScheduler::new(base_state(vec![
        node(
            "node-a",
            1,
            Classification::Secret,
            &["red"],
            resources(2, 4, 0, 1),
            "zone-a",
            "nv-a",
            Some(900),
            Some(5),
        ),
        node(
            "node-b",
            1,
            Classification::Secret,
            &["red"],
            resources(2, 4, 0, 1),
            "zone-a",
            "nv-b",
            Some(900),
            Some(5),
        ),
    ]))
    .unwrap();
    let gang = GangSpec {
        id: "gang-a".to_owned(),
        min_members: 2,
        expected_members: 2,
        topology_key: Some("zone".to_owned()),
    };
    let mut first = work(20, "red", resources(2, 2, 0, 1));
    first.gang = Some(gang.clone());
    let mut second = work(21, "red", resources(2, 2, 0, 1));
    second.gang = Some(gang);

    let waiting = scheduler
        .schedule_gang(
            1,
            vec![first.clone(), second.clone()],
            PermitDecision::Wait { until_tick: 10 },
            0,
        )
        .unwrap();
    let CycleOutcome::Waiting { reservation_id, .. } = waiting.outcome else {
        panic!("gang should wait with one atomic reservation")
    };
    assert_eq!(scheduler.state().reservation_count(), 1);
    assert!(
        scheduler
            .state()
            .nodes()
            .values()
            .all(|node| node.allocatable.slots == 0)
    );
    scheduler.state().check_invariants().unwrap();

    assert_eq!(scheduler.expire_permits(9).unwrap(), 0);
    assert_eq!(scheduler.expire_permits(10).unwrap(), 1);
    assert_eq!(scheduler.state().reservation_count(), 0);
    assert!(
        scheduler
            .state()
            .nodes()
            .values()
            .all(|node| node.allocatable.slots == 1)
    );
    scheduler.state().check_invariants().unwrap();

    let rejected = scheduler
        .schedule_gang(
            scheduler.state().revision(),
            vec![first, second],
            PermitDecision::Reject {
                reason: "policy denied".to_owned(),
            },
            11,
        )
        .unwrap();
    assert!(matches!(rejected.outcome, CycleOutcome::Rejected { .. }));
    assert_eq!(scheduler.state().reservation_count(), 0);
    assert_eq!(scheduler.state().bindings().len(), 0);
    scheduler.state().check_invariants().unwrap();

    let _ = reservation_id;
}

struct RejectPreBind;

impl CyclePlugin for RejectPreBind {
    fn descriptor(&self) -> PluginDescriptor {
        PluginDescriptor {
            name: "reject-pre-bind",
            version: "v1",
            phase: CyclePhase::PreBind,
            timeout_steps: 1,
            failure_posture: FailurePosture::Failed,
        }
    }

    fn run(&self, _context: &mut PluginContext) -> Result<(), PluginError> {
        Err(PluginError::Rejected(
            "injected pre-bind failure".to_owned(),
        ))
    }
}

struct PanicScore;

impl CyclePlugin for PanicScore {
    fn descriptor(&self) -> PluginDescriptor {
        PluginDescriptor {
            name: "panic-score",
            version: "v1",
            phase: CyclePhase::Score,
            timeout_steps: 1,
            failure_posture: FailurePosture::Pending,
        }
    }

    fn run(&self, _context: &mut PluginContext) -> Result<(), PluginError> {
        panic!("injected plugin panic")
    }
}

#[test]
fn plugin_failure_or_panic_fails_closed_without_leaked_reservation() {
    let capacity = resources(4, 4, 0, 2);
    let mut scheduler = one_node_scheduler(capacity.clone());
    scheduler.register_plugin(Box::new(RejectPreBind)).unwrap();
    let result = scheduler.schedule_one(
        1,
        work(30, "red", resources(2, 2, 0, 1)),
        PermitDecision::Approve,
        0,
    );
    assert!(matches!(result, Err(SchedulerFailure::PluginFailed { .. })));
    assert_eq!(scheduler.state().revision(), 1);
    assert_eq!(scheduler.state().reservation_count(), 0);
    assert_eq!(scheduler.state().nodes()["node-a"].allocatable, capacity);
    scheduler.state().check_invariants().unwrap();

    let mut scheduler = one_node_scheduler(resources(4, 4, 0, 2));
    scheduler.register_plugin(Box::new(PanicScore)).unwrap();
    let result = scheduler.schedule_one(
        1,
        work(31, "red", resources(1, 1, 0, 1)),
        PermitDecision::Approve,
        0,
    );
    assert!(matches!(
        result,
        Err(SchedulerFailure::PluginPanicked { .. })
    ));
    assert_eq!(scheduler.state().reservation_count(), 0);
    assert_eq!(scheduler.state().bindings().len(), 0);
    scheduler.state().check_invariants().unwrap();
}

#[test]
fn weighted_drf_guarantees_priority_and_starvation_bound_queue_order() {
    let mut scheduler = one_node_scheduler(resources(16, 16, 0, 8));
    let mut red_existing = work(40, "red", resources(8, 2, 0, 1));
    red_existing.priority = 1;
    scheduler
        .schedule_one(1, red_existing, PermitDecision::Approve, 0)
        .unwrap();

    let mut red = work(41, "red", resources(1, 1, 0, 1));
    red.priority = 100;
    let blue = work(42, "blue", resources(1, 1, 0, 1));
    let ordered = scheduler.order_queue(&[red.clone(), blue.clone()]).unwrap();
    assert_eq!(ordered[0].tenant, "blue", "lower weighted DRF share wins");

    red.waiting_cycles = STARVATION_BOUND_CYCLES;
    let ordered = scheduler.order_queue(&[blue, red.clone()]).unwrap();
    assert_eq!(
        ordered[0].identity, red.identity,
        "feasible starved work is boosted"
    );

    red.priority_authorized = false;
    assert!(matches!(
        scheduler.order_queue(&[red]),
        Err(SchedulerFailure::UnauthorizedPriority)
    ));
}

#[test]
fn feasible_work_is_selected_within_the_declared_starvation_bound() {
    let mut scheduler = one_node_scheduler(resources(1, 1, 0, 1));
    let mut waits = BTreeMap::from([("red".to_owned(), 0u64), ("blue".to_owned(), 0u64)]);
    let mut max_wait = 0u64;
    for cycle in 0..160u64 {
        let mut red = work(1_000 + cycle * 2, "red", resources(1, 1, 0, 1));
        red.waiting_cycles = waits["red"];
        red.enqueue_sequence = cycle * 2;
        let mut blue = work(1_001 + cycle * 2, "blue", resources(1, 1, 0, 1));
        blue.waiting_cycles = waits["blue"];
        blue.enqueue_sequence = cycle * 2 + 1;
        let selected = scheduler.order_queue(&[red, blue]).unwrap().remove(0);
        let other = if selected.tenant == "red" {
            "blue"
        } else {
            "red"
        };
        waits.insert(selected.tenant.clone(), 0);
        let next_wait = waits[other].saturating_add(1);
        waits.insert(other.to_owned(), next_wait);
        max_wait = max_wait.max(next_wait);

        let revision = scheduler.state().revision();
        let identity = selected.identity.clone();
        assert!(matches!(
            scheduler
                .schedule_one(revision, selected, PermitDecision::Approve, cycle)
                .unwrap()
                .outcome,
            CycleOutcome::Bound(_)
        ));
        scheduler
            .release_binding(scheduler.state().revision(), &identity)
            .unwrap();
    }
    assert!(max_wait <= STARVATION_BOUND_CYCLES);
    scheduler.state().check_invariants().unwrap();
}

#[test]
fn accelerator_topology_locality_spread_and_authoritative_roi_drive_selection() {
    let mut scheduler = ProfessionalScheduler::new(base_state(vec![
        node(
            "nvlink",
            1,
            Classification::Secret,
            &["red"],
            resources(8, 16, 4, 4),
            "zone-a",
            "nv-a",
            Some(950),
            Some(10),
        ),
        node(
            "pcie",
            1,
            Classification::Secret,
            &["red"],
            resources(8, 16, 4, 4),
            "zone-b",
            "pcie-b",
            Some(450),
            Some(1),
        ),
    ]))
    .unwrap();
    let mut candidate = work(50, "red", resources(2, 2, 2, 1));
    candidate.preferred_accelerator_domain = Some("nv-a".to_owned());
    candidate.minimum_interconnect_score = Some(800);
    candidate.required_topology_key = Some("accelerator-island".to_owned());
    candidate.estimated_value_cents = 20;
    let result = scheduler
        .schedule_one(1, candidate, PermitDecision::Approve, 0)
        .unwrap();
    let CycleOutcome::Bound(bindings) = result.outcome else {
        panic!("topology-feasible work should bind")
    };
    assert_eq!(bindings[0].node, "nvlink");
    assert!(
        result.receipt.filter_reasons["pcie"]
            .iter()
            .any(|reason| reason.contains("interconnect"))
    );
    assert!(result.receipt.scores["nvlink"].topology > 0);
    assert!(result.receipt.scores["nvlink"].roi > 0);
}

#[test]
fn deterministic_multi_victim_preemption_respects_trust_and_disruption() {
    let mut scheduler = ProfessionalScheduler::new(base_state(vec![
        node(
            "eligible",
            1,
            Classification::Secret,
            &["red"],
            resources(4, 8, 0, 2),
            "zone-a",
            "nv-a",
            Some(900),
            Some(5),
        ),
        node(
            "wrong-ring-roomy",
            2,
            Classification::Public,
            &["red"],
            resources(64, 64, 0, 16),
            "zone-b",
            "pcie-b",
            Some(400),
            Some(1),
        ),
    ]))
    .unwrap();
    for id in [60u64, 61] {
        let mut low = work(id, "red", resources(2, 2, 0, 1));
        low.priority = 1;
        low.wasted_work_units = id;
        let revision = scheduler.state().revision();
        scheduler
            .schedule_one(revision, low, PermitDecision::Approve, id)
            .unwrap();
    }
    let mut incoming = work(62, "red", resources(3, 2, 0, 1));
    incoming.priority = 10;
    let plan = scheduler
        .plan_preemption(&incoming)
        .unwrap()
        .expect("two lower-priority victims make fit");
    assert_eq!(plan.node, "eligible");
    assert_eq!(plan.victims.len(), 2);
    assert!(plan.reclaimed.cpu_millis >= 3);

    let mut peer = incoming;
    peer.priority = 1;
    assert!(scheduler.plan_preemption(&peer).unwrap().is_none());
}

#[test]
fn bounded_queue_classes_require_explicit_wake_events() {
    let mut queues = BoundedQueues::new(2);
    let first = work(70, "red", resources(1, 1, 0, 1));
    let second = work(71, "blue", resources(1, 1, 0, 1));
    queues
        .enqueue(QueueClass::Unschedulable, first.clone())
        .unwrap();
    queues
        .enqueue(QueueClass::PermitWait, second.clone())
        .unwrap();
    assert_eq!(queues.len(), 2);
    assert!(
        queues
            .enqueue(QueueClass::Active, work(72, "red", resources(1, 1, 0, 1)))
            .is_err()
    );
    assert_eq!(queues.wake(QueueClass::Unschedulable), 1);
    assert_eq!(queues.class_of(&first.identity), Some(QueueClass::Active));
    assert_eq!(
        queues.class_of(&second.identity),
        Some(QueueClass::PermitWait)
    );
}

#[test]
fn deterministic_adversarial_multi_tenant_histories_preserve_all_invariants() {
    let mut bound = 0usize;
    let mut pending = 0usize;
    let mut waiting = 0usize;
    let mut rejected = 0usize;

    for history in 0..HISTORIES {
        let mut seed = 0x5ad4_3000_c0de_f17eu64 ^ u64::try_from(history).unwrap();
        let mut scheduler = ProfessionalScheduler::new(base_state(vec![
            node(
                "shared-a",
                1,
                Classification::Secret,
                &["red", "blue"],
                resources(8, 16, 2, 8),
                "zone-a",
                "nv-a",
                Some(900),
                Some(5),
            ),
            node(
                "green-only",
                1,
                Classification::Internal,
                &["green"],
                resources(8, 16, 0, 8),
                "zone-b",
                "cpu-b",
                None,
                Some(1),
            ),
            node(
                "wrong-estate",
                1,
                Classification::Secret,
                &["red", "blue", "green"],
                resources(128, 128, 8, 64),
                "zone-c",
                "nv-c",
                Some(1_000),
                Some(0),
            ),
        ]))
        .unwrap();
        // A cloned node with the wrong estate is permanently ineligible even
        // though it is the roomiest and cheapest candidate.
        let mut nodes = scheduler
            .state()
            .nodes()
            .values()
            .cloned()
            .collect::<Vec<_>>();
        nodes
            .iter_mut()
            .find(|node| node.snapshot.name == "wrong-estate")
            .unwrap()
            .estate = "estate-b".to_owned();
        scheduler = ProfessionalScheduler::new(SchedulingState::new(
            1,
            nodes,
            scheduler.state().tenants().clone(),
        ))
        .unwrap();

        for step in 0..STEPS_PER_HISTORY {
            seed = seed
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            let tenant_name = match seed % 3 {
                0 => "red",
                1 => "blue",
                _ => "green",
            };
            let cpu = 1 + ((seed >> 8) % 3);
            let mut candidate = work(
                u64::try_from(history * STEPS_PER_HISTORY + step).unwrap() + 10_000,
                tenant_name,
                resources(cpu, 1, 0, 1),
            );
            if seed & 0x20 != 0 {
                candidate.priority = i32::try_from((seed >> 16) % 8).unwrap();
            }
            if seed & 0x40 != 0 {
                candidate.waiting_cycles = (seed >> 24) % 40;
            }
            if tenant_name == "green" && seed & 0x80 != 0 {
                candidate.request.classification_ceiling = Classification::Secret;
            }
            let permit = match (seed >> 32) % 8 {
                0 => PermitDecision::Wait {
                    until_tick: u64::try_from(step).unwrap() + 2,
                },
                1 => PermitDecision::Reject {
                    reason: "deterministic policy rejection".to_owned(),
                },
                _ => PermitDecision::Approve,
            };
            let revision = scheduler.state().revision();
            let outcome = scheduler
                .schedule_one(revision, candidate, permit, u64::try_from(step).unwrap())
                .unwrap()
                .outcome;
            match outcome {
                CycleOutcome::Bound(_) => bound += 1,
                CycleOutcome::Pending { .. } => pending += 1,
                CycleOutcome::Waiting { .. } => waiting += 1,
                CycleOutcome::Rejected { .. } => rejected += 1,
            }
            if step % 3 == 0 {
                scheduler
                    .expire_permits(u64::try_from(step).unwrap())
                    .unwrap();
            }
            scheduler.state().check_invariants().unwrap();
            for binding in scheduler.state().bindings().values() {
                let placed = &scheduler.state().nodes()[&binding.node];
                assert_eq!(placed.estate, "estate-a");
                assert!(placed.allowed_tenants.contains(&binding.tenant));
                assert_eq!(placed.snapshot.ring, 1);
            }
        }
        scheduler.expire_permits(u64::MAX).unwrap();
        assert_eq!(scheduler.state().reservation_count(), 0);
        scheduler.state().check_invariants().unwrap();
    }

    assert!(bound > 0);
    assert!(pending > 0);
    assert!(waiting > 0);
    assert!(rejected > 0);
}
