//! SAD-32 adversarial gate: every WSF placement predicate is hard and deny-wins.

use chrono::{DateTime, Duration, Utc};
use fabric_contracts::Classification;
use saddle_estate::{
    AttestationPlatform, AttestationProfile, Capacity, ConnectivityRequirement,
    SchedulingConstraints, Workload, WorkloadKind, WorkloadSpec,
};
use saddle_scheduler::{NodeSnapshot, ProviderEligibility, ScheduleRequest, attested_scheduler};

fn capacity(cpu: u64, memory: u64, gpu: u32, slots: u32) -> Capacity {
    Capacity {
        cpu_millis: cpu,
        memory_mb: memory,
        gpu,
        max_workloads: slots,
    }
}

#[allow(clippy::too_many_arguments)] // adversarial fixture names every independent hard axis
fn node(
    name: &str,
    now: DateTime<Utc>,
    ready: bool,
    heartbeat_age: i64,
    floor: Classification,
    platform: AttestationPlatform,
    air_gapped: bool,
    available: Capacity,
) -> NodeSnapshot {
    NodeSnapshot {
        name: name.to_owned(),
        ring: 3,
        attestation_floor: floor,
        attestation: AttestationProfile {
            platform,
            air_gapped,
            pcr: (platform != AttestationPlatform::None).then(|| "pcr-approved".to_owned()),
        },
        attestation_verified_until: Some((now + Duration::minutes(5)).to_rfc3339()),
        ready,
        capacity: capacity(8_000, 16_384, 2, 8),
        allocatable: available,
        last_heartbeat: Some((now - Duration::seconds(heartbeat_age)).to_rfc3339()),
        resource_version: 7,
    }
}

fn request(now: DateTime<Utc>, constraints: SchedulingConstraints) -> ScheduleRequest {
    let workload = Workload::new(
        "classified",
        WorkloadSpec {
            workload_kind: WorkloadKind::Inference,
            replicas: 1,
            ring: 3,
            classification_ceiling: Classification::Secret,
            image: None,
            command: Vec::new(),
            capability: None,
            scheduling: constraints,
        },
    );
    ScheduleRequest::from_workload_at(&workload, now)
}

#[test]
fn pressure_and_failover_never_choose_an_under_attested_node() {
    let now = Utc::now();
    let full_attested = node(
        "attested-full",
        now,
        true,
        0,
        Classification::Secret,
        AttestationPlatform::Tpm,
        true,
        Capacity::default(),
    );
    let roomy_under_attested = node(
        "roomy-under-attested",
        now,
        true,
        0,
        Classification::Internal,
        AttestationPlatform::None,
        true,
        capacity(8_000, 16_384, 2, 8),
    );
    let req = request(now, SchedulingConstraints::default());
    let pressure =
        attested_scheduler().schedule(&req, &[full_attested.clone(), roomy_under_attested.clone()]);
    assert!(pressure.is_pending(), "pressure cannot relax attestation");

    let mut failed_over = full_attested;
    failed_over.ready = false;
    let failover = attested_scheduler().schedule(&req, &[failed_over, roomy_under_attested]);
    assert!(failover.is_pending(), "failover cannot relax attestation");
}

#[test]
fn stale_heartbeat_or_attestation_cache_cannot_authorize_placement() {
    let now = Utc::now();
    let mut stale_heartbeat = node(
        "stale-heartbeat",
        now,
        true,
        31,
        Classification::Secret,
        AttestationPlatform::Tpm,
        true,
        capacity(8_000, 16_384, 2, 8),
    );
    let req = request(now, SchedulingConstraints::default());
    assert!(
        attested_scheduler()
            .schedule(&req, std::slice::from_ref(&stale_heartbeat))
            .is_pending()
    );

    stale_heartbeat.last_heartbeat = Some(now.to_rfc3339());
    stale_heartbeat.attestation_verified_until = Some((now - Duration::seconds(1)).to_rfc3339());
    assert!(
        attested_scheduler()
            .schedule(&req, &[stale_heartbeat])
            .is_pending()
    );
}

#[test]
fn air_gap_capacity_and_provider_model_eligibility_are_hard_predicates() {
    let now = Utc::now();
    let constraints = SchedulingConstraints {
        resources: capacity(2_000, 4_096, 1, 1),
        connectivity: ConnectivityRequirement::AirGapped,
        required_models: vec!["governed-model".to_owned()],
        required_measurement: Some("pcr-approved".to_owned()),
    };
    let mut req = request(now, constraints);
    let eligible = node(
        "eligible",
        now,
        true,
        0,
        Classification::Secret,
        AttestationPlatform::Tpm,
        true,
        capacity(4_000, 8_192, 1, 4),
    );
    assert!(
        attested_scheduler()
            .schedule(&req, std::slice::from_ref(&eligible))
            .is_pending(),
        "missing provider state must fence every node"
    );

    req.provider_eligibility = ProviderEligibility::Eligible;
    let connected = node(
        "connected",
        now,
        true,
        0,
        Classification::Secret,
        AttestationPlatform::Tpm,
        false,
        capacity(4_000, 8_192, 1, 4),
    );
    let undersized = node(
        "undersized",
        now,
        true,
        0,
        Classification::Secret,
        AttestationPlatform::Tpm,
        true,
        capacity(1_000, 8_192, 1, 4),
    );
    let decision = attested_scheduler().schedule(&req, &[connected, undersized, eligible]);
    assert_eq!(decision.scheduled_node(), Some("eligible"));
}

#[test]
fn stale_provider_observation_fences_an_otherwise_eligible_node() {
    let now = Utc::now();
    let mut req = request(
        now,
        SchedulingConstraints {
            required_models: vec!["governed-model".to_owned()],
            ..SchedulingConstraints::default()
        },
    );
    req.provider_eligibility = ProviderEligibility::Stale;
    let eligible = node(
        "eligible",
        now,
        true,
        0,
        Classification::Secret,
        AttestationPlatform::Tpm,
        false,
        capacity(8_000, 16_384, 2, 8),
    );
    assert!(
        attested_scheduler()
            .schedule(&req, &[eligible])
            .is_pending()
    );
}
