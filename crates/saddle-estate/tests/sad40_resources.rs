//! SAD-40 declarative scheduler-resource schema and round-trip gate.

use saddle_estate::{
    AttestationProfile, DisruptionBudget, DisruptionBudgetSpec, Kind, NodeLease, NodeLeaseSpec,
    PlacementGroup, PlacementGroupSpec, PreemptionPolicy, PriorityClass, PriorityClassSpec,
    QuotaResources, ResourceObject, ResourceQuota, ResourceQuotaSpec, RuntimeClass,
    RuntimeClassSpec, RuntimeDriver,
};

macro_rules! roundtrip {
    ($name:ident, $resource:expr, $kind:expr) => {
        #[test]
        fn $name() {
            let resource = $resource;
            resource.validate().expect("valid SAD-40 fixture");
            let value = serde_json::to_value(&resource).expect("serialize fixture");
            let object = ResourceObject::from_value(value.clone()).expect("erase fixture");
            object.validate().expect("validate erased fixture");
            assert_eq!(object.kind(), $kind);
            assert_eq!(object.to_value().unwrap(), value);
        }
    };
}

roundtrip!(
    resource_quota_roundtrip,
    ResourceQuota::new(
        "tenant-quota",
        ResourceQuotaSpec {
            hard: QuotaResources {
                cpu_millis: 8_000,
                memory_mb: 32_768,
                gpu: 4,
                replicas: 100,
                spend_cents: 50_000,
                model_actions: 10_000,
                tool_actions: 2_000,
                ..QuotaResources::default()
            },
            guaranteed: QuotaResources {
                cpu_millis: 1_000,
                memory_mb: 4_096,
                replicas: 4,
                ..QuotaResources::default()
            },
        },
    ),
    Kind::ResourceQuota
);

roundtrip!(
    priority_class_roundtrip,
    PriorityClass::new(
        "interactive",
        PriorityClassSpec {
            value: 10_000,
            preemption: PreemptionPolicy::LowerPriority,
            protected: false,
            description: "interactive governed work".to_owned(),
        },
    ),
    Kind::PriorityClass
);

roundtrip!(
    placement_group_roundtrip,
    PlacementGroup::new(
        "tensor-gang",
        PlacementGroupSpec {
            workloads: vec!["rank-zero".to_owned(), "rank-one".to_owned()],
            min_members: 2,
            topology_key: Some("accelerator-island".to_owned()),
        },
    ),
    Kind::PlacementGroup
);

roundtrip!(
    disruption_budget_roundtrip,
    DisruptionBudget::new(
        "gateway-budget",
        DisruptionBudgetSpec {
            workload: "gateway".to_owned(),
            min_available: Some(2),
            max_unavailable: None,
        },
    ),
    Kind::DisruptionBudget
);

roundtrip!(
    runtime_class_roundtrip,
    RuntimeClass::new(
        "confidential-wasm",
        RuntimeClassSpec {
            driver: RuntimeDriver::Wasmtime,
            handler: "wasmtime-v1".to_owned(),
            minimum_attestation: AttestationProfile::default(),
            allowed_measurements: vec!["sha256:approved".to_owned()],
            credential_ref: Some("openbao:runtime-pull".to_owned()),
        },
    ),
    Kind::RuntimeClass
);

roundtrip!(
    node_lease_roundtrip,
    NodeLease::new(
        "node-a-lease",
        NodeLeaseSpec {
            node: "node-a".to_owned(),
            holder_identity: "spiffe://saddle/node/node-a".to_owned(),
            renew_time: "2026-07-18T12:00:00Z".to_owned(),
            lease_duration_seconds: 30,
            epoch: 7,
        },
    ),
    Kind::NodeLease
);

#[test]
fn scheduler_resources_fail_closed_on_invalid_or_unknown_state() {
    let overcommitted = ResourceQuota::new(
        "bad-quota",
        ResourceQuotaSpec {
            hard: QuotaResources {
                cpu_millis: 100,
                ..QuotaResources::default()
            },
            guaranteed: QuotaResources {
                cpu_millis: 101,
                ..QuotaResources::default()
            },
        },
    );
    assert!(overcommitted.validate().is_err());

    let both_budget_modes = DisruptionBudget::new(
        "bad-budget",
        DisruptionBudgetSpec {
            workload: "gateway".to_owned(),
            min_available: Some(1),
            max_unavailable: Some(1),
        },
    );
    assert!(both_budget_modes.validate().is_err());

    let unknown_runtime_field = serde_json::json!({
        "api_version": saddle_estate::API_VERSION,
        "kind": "RuntimeClass",
        "metadata": { "name": "unknown-field" },
        "spec": {
            "driver": "process",
            "handler": "native",
            "authority_override": true
        }
    });
    assert!(ResourceObject::from_value(unknown_runtime_field).is_err());
}
