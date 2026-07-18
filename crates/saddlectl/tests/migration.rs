use std::sync::Arc;

use fabric_crypto::Signer;
use fabric_crypto::providers::RustCryptoMlDsa87;
use saddle_store::{MemBackend, Store, Versioned};
use saddlectl::migration::{
    EstateSnapshot, SnapshotEntry, apply, dry_run, inspect, rollback, verify,
};
use serde_json::{Value, json};
use wsf_ledger::Ledger;

const OLD_API: &str = concat!("aog", ".islandmountain.io/v1");
const OLD_FINALIZER: &str = concat!("loom", ".aog/tenant-teardown");
const OLD_CORDON: &str = concat!("loom", ".io/unschedulable");

fn entry(key: &str, value: Value, create: u64, modified: u64, version: u64) -> SnapshotEntry {
    SnapshotEntry {
        key: key.to_owned(),
        versioned: Versioned {
            value: serde_json::to_vec_pretty(&value).unwrap(),
            create_revision: create,
            mod_revision: modified,
            version,
        },
    }
}

fn representative() -> EstateSnapshot {
    EstateSnapshot::new(vec![
        entry(
            "Tenant/elk-river",
            json!({
                "api_version": OLD_API,
                "kind": "Tenant",
                "metadata": {
                    "name": "elk-river",
                    "uid": "estate-uid-7",
                    "tenant": "elk-river",
                    "generation": 4,
                    "resource_version": 17,
                    "labels": { OLD_CORDON: "true", "user.example/loom-note": "retained" },
                    "annotations": { "operator-note": "loom is opaque here" },
                    "token_ref": { "token_id": "loom-era-token-must-not-change" },
                    "receipt_ref": {
                        "receipt_id": "receipt-9",
                        "chain": "loom-era-chain-must-not-change"
                    },
                    "finalizers": [OLD_FINALIZER, "user.example/retain"]
                },
                "spec": {
                    "display_name": "Elk River",
                    "ring": 2,
                    "classification_ceiling": "restricted",
                    "opaque_authority": "loom-era-policy-must-not-change"
                },
                "status": { "openbao_path": concat!("kv/data/", "loom-era/retain") }
            }),
            7,
            17,
            4,
        ),
        SnapshotEntry {
            key: "ZOpaque/raw".to_owned(),
            versioned: Versioned {
                value: b"not-json-loom-era-bytes".to_vec(),
                create_revision: 18,
                mod_revision: 18,
                version: 1,
            },
        },
    ])
}

#[test]
fn inspect_and_dry_run_are_non_mutating_and_deterministic() {
    let original = representative();
    let report = inspect(&original).unwrap();
    let (preview, preview_report) = dry_run(&original).unwrap();

    assert_eq!(report, preview_report);
    assert_eq!(report.entries, 2);
    assert_eq!(report.json_entries, 1);
    assert_eq!(report.non_json_entries, 1);
    assert_eq!(report.changes.len(), 3);
    assert_ne!(preview, original);
    assert_eq!(original, representative());
}

#[test]
fn apply_verify_and_rollback_preserve_authority_receipts_and_versions() {
    let original = representative();
    let original_value: Value =
        serde_json::from_slice(&original.entries[0].versioned.value).unwrap();
    let (migrated, journal, report) = apply(&original).unwrap();
    let verification = verify(&migrated, &journal).unwrap();
    let migrated_value: Value =
        serde_json::from_slice(&migrated.entries[0].versioned.value).unwrap();

    assert_eq!(report.changes.len(), 3);
    assert_eq!(verification.changes_verified, 3);
    assert!(verification.authority_and_payload_preserved);
    assert!(verification.receipt_chain_preserved);
    assert!(verification.version_metadata_preserved);
    assert!(verification.rollback_ready);
    assert_eq!(
        migrated_value
            .pointer("/api_version")
            .and_then(Value::as_str),
        Some("saddle.islandmountain.io/v1")
    );
    assert_eq!(
        migrated_value
            .pointer("/metadata/finalizers/0")
            .and_then(Value::as_str),
        Some("saddle.islandmountain.io/tenant-teardown")
    );
    assert_eq!(
        migrated_value
            .pointer("/metadata/labels/saddle.islandmountain.io~1unschedulable")
            .and_then(Value::as_str),
        Some("true")
    );
    for pointer in [
        "/metadata/uid",
        "/metadata/tenant",
        "/metadata/token_ref",
        "/metadata/receipt_ref",
        "/metadata/annotations",
        "/spec",
        "/status/openbao_path",
    ] {
        assert_eq!(
            migrated_value.pointer(pointer),
            original_value.pointer(pointer)
        );
    }
    assert_eq!(migrated.entries[0].versioned.create_revision, 7);
    assert_eq!(migrated.entries[0].versioned.mod_revision, 17);
    assert_eq!(migrated.entries[0].versioned.version, 4);
    assert_eq!(migrated.entries[1], original.entries[1]);

    let restored = rollback(&migrated, &journal).unwrap();
    assert_eq!(restored, original);
    assert_eq!(
        restored.entries[0].versioned.value,
        original.entries[0].versioned.value
    );
}

#[test]
fn verify_and_rollback_reject_post_apply_drift() {
    let original = representative();
    let (mut migrated, journal, _) = apply(&original).unwrap();
    let mut value: Value = serde_json::from_slice(&migrated.entries[0].versioned.value).unwrap();
    value["metadata"]["receipt_ref"]["chain"] = json!("tampered");
    migrated.entries[0].versioned.value = serde_json::to_vec(&value).unwrap();

    assert!(verify(&migrated, &journal).is_err());
    assert!(rollback(&migrated, &journal).is_err());
}

#[test]
fn apply_fails_closed_on_label_collision() {
    let mut snapshot = representative();
    let mut value: Value = serde_json::from_slice(&snapshot.entries[0].versioned.value).unwrap();
    value["metadata"]["labels"]["saddle.islandmountain.io/unschedulable"] = json!("false");
    snapshot.entries[0].versioned.value = serde_json::to_vec(&value).unwrap();

    assert!(apply(&snapshot).is_err());
}

#[test]
fn native_store_range_and_restore_preserve_versioned_state() {
    let signer: Arc<dyn Signer> = Arc::new(RustCryptoMlDsa87::generate("sad-22-receipts").unwrap());
    let mut ledger = Ledger::new(signer);
    ledger
        .ingest("admission", json!({ "receipt_id": "receipt-8" }))
        .unwrap();
    ledger
        .ingest("admission", json!({ "receipt_id": "receipt-9" }))
        .unwrap();
    let receipt_head = ledger.verify().unwrap();

    let original = representative();
    let original_entries = original.clone().into_versioned_entries();
    let mut store = Store::open(MemBackend::new()).unwrap();
    store.restore(&original_entries).unwrap();

    let snapshot = EstateSnapshot::from_versioned_entries(store.range("").unwrap());
    let (migrated, journal, _) = apply(&snapshot).unwrap();
    store
        .restore(&migrated.clone().into_versioned_entries())
        .unwrap();
    assert_eq!(
        EstateSnapshot::from_versioned_entries(store.range("").unwrap()),
        migrated
    );

    let restored = rollback(&migrated, &journal).unwrap();
    store
        .restore(&restored.clone().into_versioned_entries())
        .unwrap();
    assert_eq!(
        EstateSnapshot::from_versioned_entries(store.range("").unwrap()),
        original
    );
    assert_eq!(ledger.verify().unwrap(), receipt_head);
    let extended_head = ledger
        .ingest("admission", json!({ "receipt_id": "receipt-10" }))
        .unwrap();
    assert_ne!(extended_head, receipt_head);
    assert_eq!(ledger.verify().unwrap(), extended_head);
}
