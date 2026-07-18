//! Offline migration for versioned estate snapshots created before Saddle's
//! runtime-identity cutover.
//!
//! Migration is deliberately narrower than string replacement. Only the
//! retired estate API group, controller-finalizer namespace, and cordon label
//! key are structural identities. Capability references, receipt chains,
//! ownership, object keys, OpenBao references, and store revisions are opaque
//! and remain unchanged. The rollback journal retains the complete original
//! versioned snapshot.

use std::collections::BTreeSet;

use saddle_store::Versioned;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

const SNAPSHOT_SCHEMA: &str = "saddle-versioned-estate/v1";
const JOURNAL_SCHEMA: &str = "saddle-legacy-state-migration/v1";
const LEGACY_API_VERSION: &str = concat!("aog", ".islandmountain.io/v1");
const SADDLE_API_VERSION: &str = "saddle.islandmountain.io/v1";
const LEGACY_FINALIZER_PREFIX: &str = concat!("loom", ".aog/");
const SADDLE_FINALIZER_PREFIX: &str = "saddle.islandmountain.io/";
const LEGACY_CORDON_LABEL: &str = concat!("loom", ".io/unschedulable");
const SADDLE_CORDON_LABEL: &str = "saddle.islandmountain.io/unschedulable";

/// A full desired-state snapshot with exact store version metadata.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EstateSnapshot {
    pub schema_version: String,
    pub entries: Vec<SnapshotEntry>,
}

impl EstateSnapshot {
    /// Construct a snapshot using the supported interchange schema.
    #[must_use]
    pub fn new(mut entries: Vec<SnapshotEntry>) -> Self {
        entries.sort_by(|left, right| left.key.cmp(&right.key));
        Self {
            schema_version: SNAPSHOT_SCHEMA.to_owned(),
            entries,
        }
    }

    /// Adapt the native [`saddle_store::Store::range`] result without changing
    /// keys, values, or revision metadata.
    #[must_use]
    pub fn from_versioned_entries(entries: Vec<(String, Versioned)>) -> Self {
        Self::new(
            entries
                .into_iter()
                .map(|(key, versioned)| SnapshotEntry { key, versioned })
                .collect(),
        )
    }

    /// Convert this envelope back to the native [`saddle_store::Store::restore`]
    /// input shape.
    #[must_use]
    pub fn into_versioned_entries(self) -> Vec<(String, Versioned)> {
        self.entries
            .into_iter()
            .map(|entry| (entry.key, entry.versioned))
            .collect()
    }

    /// Validate the envelope and version metadata before any transformation.
    ///
    /// # Errors
    /// Returns [`MigrationError`] for unsupported schemas, duplicate keys, or
    /// invalid revision metadata.
    pub fn validate(&self) -> Result<(), MigrationError> {
        if self.schema_version != SNAPSHOT_SCHEMA {
            return Err(MigrationError::Schema(self.schema_version.clone()));
        }
        let mut keys = BTreeSet::new();
        let mut previous = None;
        for entry in &self.entries {
            if entry.key.is_empty() {
                return Err(MigrationError::InvalidSnapshot(
                    "snapshot contains an empty key".to_owned(),
                ));
            }
            if !keys.insert(&entry.key) {
                return Err(MigrationError::InvalidSnapshot(format!(
                    "snapshot contains duplicate key {:?}",
                    entry.key
                )));
            }
            if previous.is_some_and(|key: &str| key >= entry.key.as_str()) {
                return Err(MigrationError::InvalidSnapshot(
                    "snapshot keys are not in strict ascending order".to_owned(),
                ));
            }
            previous = Some(entry.key.as_str());
            let versioned = &entry.versioned;
            if versioned.version == 0
                || versioned.create_revision == 0
                || versioned.create_revision > versioned.mod_revision
            {
                return Err(MigrationError::InvalidSnapshot(format!(
                    "invalid version metadata for {:?}",
                    entry.key
                )));
            }
        }
        Ok(())
    }
}

/// One key and its exact stored value/revision tuple.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SnapshotEntry {
    pub key: String,
    pub versioned: Versioned,
}

/// One deterministic structural identity rewrite.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MigrationChange {
    pub key: String,
    pub path: String,
    pub from: String,
    pub to: String,
}

/// Inspect/dry-run result. Digests cover the exact input envelope and the
/// protected semantic payload respectively.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MigrationReport {
    pub entries: usize,
    pub json_entries: usize,
    pub non_json_entries: usize,
    pub changes: Vec<MigrationChange>,
    pub input_digest: String,
    pub protected_payload_digest: String,
    pub receipt_chain_digest: String,
    pub version_metadata_digest: String,
}

/// Apply output and lossless rollback material.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MigrationJournal {
    pub schema_version: String,
    pub original_digest: String,
    pub migrated_digest: String,
    pub protected_payload_digest: String,
    pub receipt_chain_digest: String,
    pub version_metadata_digest: String,
    pub changes: Vec<MigrationChange>,
    pub original: EstateSnapshot,
}

/// Verify result emitted after checking the journal, migrated snapshot, and
/// all protected invariants.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerificationReport {
    pub entries: usize,
    pub migrated_digest: String,
    pub changes_verified: usize,
    pub authority_and_payload_preserved: bool,
    pub receipt_chain_preserved: bool,
    pub version_metadata_preserved: bool,
    pub rollback_ready: bool,
}

/// Fail-closed migration errors.
#[derive(Debug, thiserror::Error)]
pub enum MigrationError {
    #[error("unsupported snapshot schema {0:?}")]
    Schema(String),
    #[error("unsupported migration journal schema {0:?}")]
    JournalSchema(String),
    #[error("invalid snapshot: {0}")]
    InvalidSnapshot(String),
    #[error("resource {key:?} contains conflicting legacy and Saddle cordon labels")]
    LabelCollision { key: String },
    #[error("cannot encode migration material: {0}")]
    Encode(String),
    #[error("migration journal does not match the supplied snapshot: {0}")]
    JournalMismatch(String),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct ProtectedEntry {
    key: String,
    value: Value,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct VersionTuple<'a> {
    key: &'a str,
    create_revision: u64,
    mod_revision: u64,
    version: u64,
}

/// Inspect a snapshot without changing it.
///
/// # Errors
/// Fails on an invalid envelope, a label collision, or digest encoding.
pub fn inspect(snapshot: &EstateSnapshot) -> Result<MigrationReport, MigrationError> {
    snapshot.validate()?;
    let (_, report) = migrate_snapshot(snapshot)?;
    Ok(report)
}

/// Compute the exact apply result without constructing rollback material.
///
/// # Errors
/// Fails under the same conditions as [`inspect`].
pub fn dry_run(
    snapshot: &EstateSnapshot,
) -> Result<(EstateSnapshot, MigrationReport), MigrationError> {
    snapshot.validate()?;
    migrate_snapshot(snapshot)
}

/// Apply the structural migration and issue a journal containing the complete
/// original snapshot.
///
/// # Errors
/// Fails if input validation or any preservation invariant fails.
pub fn apply(
    snapshot: &EstateSnapshot,
) -> Result<(EstateSnapshot, MigrationJournal, MigrationReport), MigrationError> {
    snapshot.validate()?;
    let (migrated, report) = migrate_snapshot(snapshot)?;
    let after = invariant_digests(&migrated)?;
    if after != invariant_digests(snapshot)? {
        return Err(MigrationError::JournalMismatch(
            "a protected authority, receipt, payload, or version field changed".to_owned(),
        ));
    }
    let journal = MigrationJournal {
        schema_version: JOURNAL_SCHEMA.to_owned(),
        original_digest: digest(snapshot)?,
        migrated_digest: digest(&migrated)?,
        protected_payload_digest: after.0,
        receipt_chain_digest: after.1,
        version_metadata_digest: after.2,
        changes: report.changes.clone(),
        original: snapshot.clone(),
    };
    Ok((migrated, journal, report))
}

/// Verify a migrated snapshot against its apply journal.
///
/// # Errors
/// Fails if either document changed, any expected rewrite is missing, or any
/// protected invariant differs.
pub fn verify(
    snapshot: &EstateSnapshot,
    journal: &MigrationJournal,
) -> Result<VerificationReport, MigrationError> {
    snapshot.validate()?;
    if journal.schema_version != JOURNAL_SCHEMA {
        return Err(MigrationError::JournalSchema(
            journal.schema_version.clone(),
        ));
    }
    journal.original.validate()?;
    require_digest(
        "journal original",
        &digest(&journal.original)?,
        &journal.original_digest,
    )?;
    require_digest(
        "migrated snapshot",
        &digest(snapshot)?,
        &journal.migrated_digest,
    )?;

    let (expected, report) = migrate_snapshot(&journal.original)?;
    if expected != *snapshot || report.changes != journal.changes {
        return Err(MigrationError::JournalMismatch(
            "deterministic replay differs from the supplied migrated snapshot".to_owned(),
        ));
    }
    let invariants = invariant_digests(snapshot)?;
    require_digest(
        "protected authority and payload",
        &invariants.0,
        &journal.protected_payload_digest,
    )?;
    require_digest(
        "receipt chain",
        &invariants.1,
        &journal.receipt_chain_digest,
    )?;
    require_digest(
        "version metadata",
        &invariants.2,
        &journal.version_metadata_digest,
    )?;
    let remaining = inspect(snapshot)?;
    if !remaining.changes.is_empty() {
        return Err(MigrationError::JournalMismatch(
            "migrated snapshot still contains recognized legacy structural identities".to_owned(),
        ));
    }

    Ok(VerificationReport {
        entries: snapshot.entries.len(),
        migrated_digest: journal.migrated_digest.clone(),
        changes_verified: journal.changes.len(),
        authority_and_payload_preserved: true,
        receipt_chain_preserved: true,
        version_metadata_preserved: true,
        rollback_ready: true,
    })
}

/// Restore the complete original versioned snapshot after verifying that the
/// supplied current state is exactly the migration result bound to the journal.
///
/// # Errors
/// Fails closed if verification detects drift or a mismatched journal.
pub fn rollback(
    current: &EstateSnapshot,
    journal: &MigrationJournal,
) -> Result<EstateSnapshot, MigrationError> {
    verify(current, journal)?;
    Ok(journal.original.clone())
}

fn migrate_snapshot(
    snapshot: &EstateSnapshot,
) -> Result<(EstateSnapshot, MigrationReport), MigrationError> {
    let mut migrated = snapshot.clone();
    let mut changes = Vec::new();
    let mut json_entries = 0;

    for entry in &mut migrated.entries {
        let Ok(mut value) = serde_json::from_slice::<Value>(&entry.versioned.value) else {
            continue;
        };
        json_entries += 1;
        let before = changes.len();
        migrate_value(&entry.key, &mut value, &mut changes)?;
        if changes.len() != before {
            entry.versioned.value = serde_json::to_vec(&value)
                .map_err(|error| MigrationError::Encode(error.to_string()))?;
        }
    }

    let invariants = invariant_digests(snapshot)?;
    let report = MigrationReport {
        entries: snapshot.entries.len(),
        json_entries,
        non_json_entries: snapshot.entries.len() - json_entries,
        changes,
        input_digest: digest(snapshot)?,
        protected_payload_digest: invariants.0,
        receipt_chain_digest: invariants.1,
        version_metadata_digest: invariants.2,
    };
    Ok((migrated, report))
}

fn migrate_value(
    key: &str,
    value: &mut Value,
    changes: &mut Vec<MigrationChange>,
) -> Result<(), MigrationError> {
    let Some(root) = value.as_object_mut() else {
        return Ok(());
    };
    replace_string(
        key,
        root.get_mut("api_version"),
        "/api_version",
        LEGACY_API_VERSION,
        SADDLE_API_VERSION,
        changes,
    );
    let Some(metadata) = root.get_mut("metadata").and_then(Value::as_object_mut) else {
        return Ok(());
    };
    if let Some(finalizers) = metadata.get_mut("finalizers").and_then(Value::as_array_mut) {
        for (index, finalizer) in finalizers.iter_mut().enumerate() {
            let Some(old) = finalizer.as_str() else {
                continue;
            };
            let Some(suffix) = old.strip_prefix(LEGACY_FINALIZER_PREFIX) else {
                continue;
            };
            let new = format!("{SADDLE_FINALIZER_PREFIX}{suffix}");
            changes.push(MigrationChange {
                key: key.to_owned(),
                path: format!("/metadata/finalizers/{index}"),
                from: old.to_owned(),
                to: new.clone(),
            });
            *finalizer = Value::String(new);
        }
    }
    if let Some(labels) = metadata.get_mut("labels").and_then(Value::as_object_mut) {
        migrate_cordon_label(key, labels, changes)?;
    }
    Ok(())
}

fn replace_string(
    key: &str,
    value: Option<&mut Value>,
    path: &str,
    old: &str,
    new: &str,
    changes: &mut Vec<MigrationChange>,
) {
    let Some(value) = value else { return };
    if value.as_str() != Some(old) {
        return;
    }
    changes.push(MigrationChange {
        key: key.to_owned(),
        path: path.to_owned(),
        from: old.to_owned(),
        to: new.to_owned(),
    });
    *value = Value::String(new.to_owned());
}

fn migrate_cordon_label(
    key: &str,
    labels: &mut Map<String, Value>,
    changes: &mut Vec<MigrationChange>,
) -> Result<(), MigrationError> {
    let Some(value) = labels.remove(LEGACY_CORDON_LABEL) else {
        return Ok(());
    };
    if let Some(current) = labels.get(SADDLE_CORDON_LABEL)
        && current != &value
    {
        return Err(MigrationError::LabelCollision {
            key: key.to_owned(),
        });
    }
    changes.push(MigrationChange {
        key: key.to_owned(),
        path: "/metadata/labels/loom.io~1unschedulable".to_owned(),
        from: LEGACY_CORDON_LABEL.to_owned(),
        to: SADDLE_CORDON_LABEL.to_owned(),
    });
    labels.insert(SADDLE_CORDON_LABEL.to_owned(), value);
    Ok(())
}

fn invariant_digests(
    snapshot: &EstateSnapshot,
) -> Result<(String, String, String), MigrationError> {
    let mut protected = Vec::with_capacity(snapshot.entries.len());
    let mut receipts = Vec::with_capacity(snapshot.entries.len());
    let versions = snapshot
        .entries
        .iter()
        .map(|entry| VersionTuple {
            key: &entry.key,
            create_revision: entry.versioned.create_revision,
            mod_revision: entry.versioned.mod_revision,
            version: entry.versioned.version,
        })
        .collect::<Vec<_>>();

    for entry in &snapshot.entries {
        let mut value =
            serde_json::from_slice::<Value>(&entry.versioned.value).unwrap_or_else(|_| {
                Value::Array(
                    entry
                        .versioned
                        .value
                        .iter()
                        .copied()
                        .map(Value::from)
                        .collect(),
                )
            });
        normalize_structural_identities(&mut value)?;
        let receipt = value
            .pointer("/metadata/receipt_ref")
            .cloned()
            .unwrap_or(Value::Null);
        receipts.push((entry.key.clone(), receipt));
        protected.push(ProtectedEntry {
            key: entry.key.clone(),
            value,
        });
    }
    Ok((digest(&protected)?, digest(&receipts)?, digest(&versions)?))
}

fn normalize_structural_identities(value: &mut Value) -> Result<(), MigrationError> {
    let Some(root) = value.as_object_mut() else {
        return Ok(());
    };
    if matches!(
        root.get("api_version").and_then(Value::as_str),
        Some(LEGACY_API_VERSION | SADDLE_API_VERSION)
    ) {
        root.insert(
            "api_version".to_owned(),
            Value::String("<estate-api>".to_owned()),
        );
    }
    let Some(metadata) = root.get_mut("metadata").and_then(Value::as_object_mut) else {
        return Ok(());
    };
    if let Some(finalizers) = metadata.get_mut("finalizers").and_then(Value::as_array_mut) {
        for finalizer in finalizers {
            let Some(text) = finalizer.as_str() else {
                continue;
            };
            let suffix = text
                .strip_prefix(LEGACY_FINALIZER_PREFIX)
                .or_else(|| text.strip_prefix(SADDLE_FINALIZER_PREFIX));
            if let Some(suffix) = suffix {
                *finalizer = Value::String(format!("<estate-finalizer>/{suffix}"));
            }
        }
    }
    if let Some(labels) = metadata.get_mut("labels").and_then(Value::as_object_mut) {
        let old = labels.remove(LEGACY_CORDON_LABEL);
        let new = labels.remove(SADDLE_CORDON_LABEL);
        if old.is_some() && new.is_some() && old != new {
            return Err(MigrationError::InvalidSnapshot(
                "conflicting cordon labels cannot be normalized".to_owned(),
            ));
        }
        if let Some(value) = old.or(new) {
            labels.insert("<estate-cordon-label>".to_owned(), value);
        }
    }
    Ok(())
}

fn require_digest(label: &str, actual: &str, expected: &str) -> Result<(), MigrationError> {
    if actual == expected {
        Ok(())
    } else {
        Err(MigrationError::JournalMismatch(format!(
            "{label} digest differs"
        )))
    }
}

fn digest<T: Serialize + ?Sized>(value: &T) -> Result<String, MigrationError> {
    let encoded =
        serde_json::to_vec(value).map_err(|error| MigrationError::Encode(error.to_string()))?;
    Ok(blake3::hash(&encoded).to_hex().to_string())
}
