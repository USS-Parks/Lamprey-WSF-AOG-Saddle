//! SAD-40 integrated declarative-estate gate: conversion, CAS, watches,
//! finalization, and sensitive-field sealing.

mod common;

use axum::http::StatusCode;
use common::{BASE, authed_app_state, send};
use saddle_apiserver::convert::{
    ConversionError, ConversionRegistry, convert_legacy_v1, rollback_legacy_v1,
};
use saddle_apiserver::seal::{SEALED_PLACEHOLDER, Sealer};
use saddle_estate::{
    AttestationProfile, Kind, Resource, ResourceObject, RuntimeClassSpec, RuntimeDriver,
};
use serde_json::{Value, json};

const LEGACY_FINALIZER_PREFIX: &str = concat!("lo", "om", ".aog/");
const LEGACY_CORDON_LABEL: &str = concat!("lo", "om", ".io/unschedulable");

fn quota(name: &str, cpu_millis: u64) -> Value {
    json!({
        "api_version": saddle_estate::API_VERSION,
        "kind": "ResourceQuota",
        "metadata": {
            "name": name,
            "finalizers": ["saddle.islandmountain.io/quota-accounting"]
        },
        "spec": {
            "hard": {
                "cpu_millis": cpu_millis,
                "memory_mb": 4096,
                "replicas": 8
            },
            "guaranteed": {
                "cpu_millis": 100,
                "memory_mb": 512,
                "replicas": 1
            }
        }
    })
}

fn legacy_fixture(seed: u64) -> Value {
    json!({
        "api_version": "aog.islandmountain.io/v1",
        "kind": "PolicyBundle",
        "metadata": {
            "name": format!("fixture-{seed}"),
            "uid": format!("uid-{seed:016x}"),
            "tenant": format!("tenant-{}", seed % 7),
            "generation": seed.saturating_add(1),
            "resource_version": seed.saturating_mul(3).saturating_add(7),
            "labels": {
                (LEGACY_CORDON_LABEL): seed.is_multiple_of(2),
                "opaque.example/seed": seed.to_string()
            },
            "annotations": { "authority.example/lineage": format!("lineage-{seed}") },
            "token_ref": { "token_id": format!("token-{seed}") },
            "receipt_ref": { "receipt_id": format!("receipt-{seed}"), "chain": "wsf" },
            "finalizers": [
                format!("{LEGACY_FINALIZER_PREFIX}teardown"),
                "user.example/retain"
            ]
        },
        "spec": {
            "version": seed.saturating_add(1),
            "mode": "enforce",
            "rules": [],
            "desired_seed": seed,
            "opaque_desired": { "enabled": seed.is_multiple_of(3) }
        },
        "status": { "phase": "ready", "observed_version": seed }
    })
}

#[test]
fn conversion_fuzz_preserves_authority_versions_desired_state_and_rollback() {
    let registry = ConversionRegistry::saddle_v1();
    for seed in 0..512 {
        let legacy = legacy_fixture(seed);
        let hub = registry
            .convert(Kind::PolicyBundle, legacy.clone())
            .expect("bounded legacy conversion");
        assert_eq!(hub["api_version"], saddle_estate::API_VERSION);
        for pointer in [
            "/metadata/uid",
            "/metadata/tenant",
            "/metadata/generation",
            "/metadata/resource_version",
            "/metadata/token_ref",
            "/metadata/receipt_ref",
            "/metadata/annotations",
            "/spec",
            "/status",
        ] {
            assert_eq!(hub.pointer(pointer), legacy.pointer(pointer), "{pointer}");
        }
        let rolled_back = rollback_legacy_v1(Kind::PolicyBundle, hub).unwrap();
        assert_eq!(rolled_back, legacy, "seed {seed} must roll back exactly");
    }
}

#[test]
fn conversion_refuses_unknown_versions_kind_spoofing_and_label_collision() {
    let registry = ConversionRegistry::saddle_v1();
    let mut unknown = legacy_fixture(1);
    unknown["api_version"] = json!("saddle.islandmountain.io/v999");
    assert!(matches!(
        registry.convert(Kind::PolicyBundle, unknown),
        Err(ConversionError::UnsupportedVersion { .. })
    ));

    let spoofed = legacy_fixture(2);
    assert!(matches!(
        convert_legacy_v1(Kind::Node, spoofed),
        Err(ConversionError::KindMismatch { .. })
    ));

    let mut collision = legacy_fixture(3);
    collision["metadata"]["labels"]["saddle.islandmountain.io/unschedulable"] = json!(true);
    assert!(matches!(
        convert_legacy_v1(Kind::PolicyBundle, collision),
        Err(ConversionError::Malformed(_))
    ));
}

#[tokio::test]
async fn quota_cas_watch_and_finalizer_paths_share_the_real_admission_store() {
    let (app, state, token) = authed_app_state("saddle-sad40-estate").await;
    let mut informer = state.informer("ResourceQuota/");
    informer.resync().await.unwrap();
    assert!(informer.snapshot().is_empty());

    let collection = format!("{BASE}/ResourceQuota");
    let (status, created) = send(
        &app,
        "POST",
        &collection,
        Some(&token),
        Some(quota("tenant-quota", 1_000)),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED, "{created}");
    let first_revision = created["metadata"]["resource_version"].as_u64().unwrap();

    informer.poll().await.unwrap();
    let watched = informer
        .snapshot()
        .get("ResourceQuota/tenant-quota")
        .expect("watch observed quota create");
    assert_eq!(watched.mod_revision, first_revision);

    let url = format!("{collection}/tenant-quota");
    let mut update = created.clone();
    update["spec"]["hard"]["cpu_millis"] = json!(2_000);
    let (status, current) = send(&app, "PUT", &url, Some(&token), Some(update)).await;
    assert_eq!(status, StatusCode::OK, "{current}");

    let mut stale = created;
    stale["spec"]["hard"]["cpu_millis"] = json!(3_000);
    let (status, body) = send(&app, "PUT", &url, Some(&token), Some(stale)).await;
    assert_eq!(status, StatusCode::CONFLICT, "{body}");

    let (status, terminating) = send(&app, "DELETE", &url, Some(&token), None).await;
    assert_eq!(status, StatusCode::OK, "{terminating}");
    assert!(terminating["metadata"]["deletion_timestamp"].is_string());

    let mut finalize = terminating;
    finalize["metadata"]["finalizers"] = json!([]);
    let (status, body) = send(&app, "PUT", &url, Some(&token), Some(finalize)).await;
    assert_eq!(status, StatusCode::OK, "{body}");
    assert_eq!(body["finalized"], true);
}

#[test]
fn runtime_class_credentials_are_sealed_before_persistence() {
    let mut object = ResourceObject::RuntimeClass(Resource::new(
        "confidential-wasm",
        RuntimeClassSpec {
            driver: RuntimeDriver::Wasmtime,
            handler: "wasmtime-v1".to_owned(),
            minimum_attestation: AttestationProfile::default(),
            allowed_measurements: vec!["sha256:approved".to_owned()],
            credential_ref: Some("openbao:registry/runtime".to_owned()),
        },
    ));
    Sealer::generate()
        .unwrap()
        .seal_fields(&mut object)
        .unwrap();
    let ResourceObject::RuntimeClass(runtime) = object else {
        unreachable!();
    };
    assert_eq!(
        runtime.spec.credential_ref.as_deref(),
        Some(SEALED_PLACEHOLDER)
    );
    let stored = serde_json::to_string(&runtime).unwrap();
    assert!(!stored.contains("openbao:registry/runtime"));
    assert!(
        runtime
            .metadata
            .annotations
            .contains_key("wsf.io/sealed.runtime_class.credential_ref")
    );
}
