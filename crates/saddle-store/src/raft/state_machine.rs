//! redb-backed Raft state machine. The applied desired state is the
//! [`Store`] (durable KV + revision); `last_applied_log_id` and membership are
//! persisted alongside it, so `applied_state` recovers after a restart — the
//! guarantee the gate checks. The state sits behind an `Arc<RwLock>` so the
//! committed KV is readable outside openraft (which owns the machine).
//!
//! An application-level rejection (a failed CAS) is returned as a `RaftResponse`
//! value, never a `StorageError`: consensus commits, the store refuses the write
//! (fail-closed, D7). A `StorageError` here would fault the whole node.

// openraft's `StorageError` is large by design and the storage traits must
// return it unboxed; boxing our internal helpers would just fight the API.
#![allow(clippy::result_large_err)]

use std::fmt;
use std::io::{Cursor, Error as IoError, ErrorKind};
use std::path::Path;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use openraft::storage::{RaftStateMachine, Snapshot};
use openraft::{
    AnyError, BasicNode, Entry, EntryPayload, ErrorSubject, ErrorVerb, LogId, OptionalSend,
    RaftSnapshotBuilder, SnapshotMeta, StorageError, StorageIOError, StoredMembership,
};
use redb::{Database, TableDefinition};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use tokio::sync::{RwLock, broadcast};

use crate::raft::types::{NodeId, RaftResponse, TypeConfig};
use crate::raft::watch::{EventKind, WatchEvent};
use crate::{Applied, Op, RedbBackend, Store, Versioned};

const SM_META: TableDefinition<&str, &[u8]> = TableDefinition::new("sm_meta");

type StorageResult<T> = Result<T, StorageError<NodeId>>;

/// Change-event fan-out buffer. Small on purpose: the informer recovers from
/// overflow by re-listing, so its correctness is resync, not buffering.
const WATCH_CAPACITY: usize = 64;

fn op_key(op: &Op) -> String {
    match op {
        Op::Put { key, .. } | Op::Delete { key, .. } => key.clone(),
    }
}

fn io_sm<E: std::error::Error + 'static>(verb: ErrorVerb, err: E) -> StorageError<NodeId> {
    StorageError::IO {
        source: StorageIOError::new(ErrorSubject::StateMachine, verb, AnyError::new(&err)),
    }
}

/// A snapshot payload — the full KV dump plus applied metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct SnapshotPayload {
    revision: crate::Revision,
    kvs: Vec<(String, Versioned)>,
    last_applied: Option<LogId<NodeId>>,
    last_membership: StoredMembership<NodeId, BasicNode>,
}

const SNAPSHOT_FORMAT_VERSION: u32 = 1;

/// Versioned, checksummed wire envelope. Sensitive resource fields are already
/// envelope-sealed before reaching this store; the digest detects corruption
/// before any snapshot state replaces the active estate.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct SnapshotEnvelope {
    format_version: u32,
    payload_checksum: String,
    payload: SnapshotPayload,
}

/// A persisted snapshot (meta + bytes).
#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredSnapshot {
    meta: SnapshotMeta<NodeId, BasicNode>,
    data: Vec<u8>,
}

/// The mutable applied state, guarded for external reads.
struct SmData {
    store: Store<RedbBackend>,
    last_applied: Option<LogId<NodeId>>,
    last_membership: StoredMembership<NodeId, BasicNode>,
}

/// redb-backed Raft state machine. Cloneable (Arc-shared) so a read handle can
/// be kept while openraft owns the machine.
#[derive(Clone)]
pub struct RedbStateMachine {
    data: Arc<RwLock<SmData>>,
    meta_db: Arc<Database>,
    snapshot_idx: Arc<AtomicU64>,
    events: broadcast::Sender<WatchEvent>,
}

impl fmt::Debug for RedbStateMachine {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("RedbStateMachine")
    }
}

fn sm_read<T: DeserializeOwned>(db: &Database, key: &str) -> StorageResult<Option<T>> {
    let rtx = db.begin_read().map_err(|e| io_sm(ErrorVerb::Read, e))?;
    let table = rtx
        .open_table(SM_META)
        .map_err(|e| io_sm(ErrorVerb::Read, e))?;
    match table.get(key).map_err(|e| io_sm(ErrorVerb::Read, e))? {
        Some(guard) => Ok(Some(
            serde_json::from_slice(guard.value()).map_err(|e| io_sm(ErrorVerb::Read, e))?,
        )),
        None => Ok(None),
    }
}

fn sm_write<T: Serialize>(db: &Database, key: &str, value: &T) -> StorageResult<()> {
    let bytes = serde_json::to_vec(value).map_err(|e| io_sm(ErrorVerb::Write, e))?;
    let wtx = db.begin_write().map_err(|e| io_sm(ErrorVerb::Write, e))?;
    {
        let mut table = wtx
            .open_table(SM_META)
            .map_err(|e| io_sm(ErrorVerb::Write, e))?;
        table
            .insert(key, bytes.as_slice())
            .map_err(|e| io_sm(ErrorVerb::Write, e))?;
    }
    wtx.commit().map_err(|e| io_sm(ErrorVerb::Write, e))?;
    Ok(())
}

fn persist_meta(db: &Database, data: &SmData) -> StorageResult<()> {
    sm_write(db, "last_applied", &data.last_applied)?;
    sm_write(db, "last_membership", &data.last_membership)
}

fn snapshot_bytes(payload: SnapshotPayload) -> StorageResult<Vec<u8>> {
    let payload_bytes = serde_json::to_vec(&payload).map_err(|e| io_sm(ErrorVerb::Write, e))?;
    let envelope = SnapshotEnvelope {
        format_version: SNAPSHOT_FORMAT_VERSION,
        payload_checksum: blake3::hash(&payload_bytes).to_hex().to_string(),
        payload,
    };
    serde_json::to_vec(&envelope).map_err(|e| io_sm(ErrorVerb::Write, e))
}

fn decode_snapshot(bytes: &[u8]) -> StorageResult<SnapshotPayload> {
    let envelope: SnapshotEnvelope =
        serde_json::from_slice(bytes).map_err(|e| io_sm(ErrorVerb::Read, e))?;
    if envelope.format_version != SNAPSHOT_FORMAT_VERSION {
        return Err(io_sm(
            ErrorVerb::Read,
            IoError::new(
                ErrorKind::InvalidData,
                format!(
                    "unsupported snapshot format version {}",
                    envelope.format_version
                ),
            ),
        ));
    }
    let payload_bytes =
        serde_json::to_vec(&envelope.payload).map_err(|e| io_sm(ErrorVerb::Read, e))?;
    let actual = blake3::hash(&payload_bytes).to_hex().to_string();
    if actual != envelope.payload_checksum {
        return Err(io_sm(
            ErrorVerb::Read,
            IoError::new(ErrorKind::InvalidData, "snapshot checksum mismatch"),
        ));
    }
    Ok(envelope.payload)
}

impl RedbStateMachine {
    /// Open the state machine under `dir` (creates `sm-kv.redb` + `sm-meta.redb`),
    /// recovering `last_applied` and membership from prior state.
    ///
    /// # Errors
    /// [`StorageError`] on redb/store failure.
    pub fn open(dir: &Path) -> StorageResult<Self> {
        let backend =
            RedbBackend::open(dir.join("sm-kv.redb")).map_err(|e| io_sm(ErrorVerb::Write, e))?;
        let store = Store::open(backend).map_err(|e| io_sm(ErrorVerb::Write, e))?;

        let meta_db = Arc::new(
            Database::create(dir.join("sm-meta.redb")).map_err(|e| io_sm(ErrorVerb::Write, e))?,
        );
        {
            let wtx = meta_db
                .begin_write()
                .map_err(|e| io_sm(ErrorVerb::Write, e))?;
            {
                wtx.open_table(SM_META)
                    .map_err(|e| io_sm(ErrorVerb::Write, e))?;
            }
            wtx.commit().map_err(|e| io_sm(ErrorVerb::Write, e))?;
        }

        let last_applied = sm_read(&meta_db, "last_applied")?;
        let last_membership = sm_read(&meta_db, "last_membership")?.unwrap_or_default();

        let (events, _) = broadcast::channel(WATCH_CAPACITY);

        Ok(Self {
            data: Arc::new(RwLock::new(SmData {
                store,
                last_applied,
                last_membership,
            })),
            meta_db,
            snapshot_idx: Arc::new(AtomicU64::new(0)),
            events,
        })
    }

    /// Read one applied key (external, linearizable-after-`client_write` read).
    ///
    /// # Errors
    /// Store backend failure.
    pub async fn get(&self, key: &str) -> Result<Option<Versioned>, crate::StoreError> {
        self.data.read().await.store.get(key)
    }

    /// The applied global revision.
    pub async fn revision(&self) -> crate::Revision {
        self.data.read().await.store.revision()
    }

    /// Range the applied state by key prefix (ascending).
    ///
    /// # Errors
    /// Store backend failure.
    pub async fn range(&self, prefix: &str) -> Result<Vec<(String, Versioned)>, crate::StoreError> {
        self.data.read().await.store.range(prefix)
    }

    /// Range plus its exact global revision under one state-machine read lock.
    /// This prevents an informer re-list from labeling an older keyset with a
    /// revision that committed between two separate reads.
    pub async fn range_with_revision(
        &self,
        prefix: &str,
    ) -> Result<(crate::Revision, Vec<(String, Versioned)>), crate::StoreError> {
        let data = self.data.read().await;
        Ok((data.store.revision(), data.store.range(prefix)?))
    }

    /// Subscribe to the change-event stream (watch).
    #[must_use]
    pub fn subscribe(&self) -> broadcast::Receiver<WatchEvent> {
        self.events.subscribe()
    }
}

impl RaftSnapshotBuilder<TypeConfig> for RedbStateMachine {
    async fn build_snapshot(&mut self) -> StorageResult<Snapshot<TypeConfig>> {
        let (revision, kvs, last_applied, last_membership) = {
            let data = self.data.read().await;
            let revision = data.store.revision();
            let kvs = data
                .store
                .range("")
                .map_err(|e| io_sm(ErrorVerb::Read, e))?;
            (
                revision,
                kvs,
                data.last_applied,
                data.last_membership.clone(),
            )
        };

        let payload = SnapshotPayload {
            revision,
            kvs,
            last_applied,
            last_membership: last_membership.clone(),
        };
        let bytes = snapshot_bytes(payload)?;

        let idx = self.snapshot_idx.fetch_add(1, Ordering::Relaxed);
        let snapshot_id = match last_applied {
            Some(log_id) => format!("{}-{}-{}", log_id.leader_id, log_id.index, idx),
            None => format!("--{idx}"),
        };
        let meta = SnapshotMeta {
            last_log_id: last_applied,
            last_membership,
            snapshot_id,
        };

        let stored = StoredSnapshot {
            meta: meta.clone(),
            data: bytes.clone(),
        };
        sm_write(&self.meta_db, "snapshot", &stored)?;

        Ok(Snapshot {
            meta,
            snapshot: Box::new(Cursor::new(bytes)),
        })
    }
}

impl RaftStateMachine<TypeConfig> for RedbStateMachine {
    type SnapshotBuilder = Self;

    async fn applied_state(
        &mut self,
    ) -> StorageResult<(Option<LogId<NodeId>>, StoredMembership<NodeId, BasicNode>)> {
        let data = self.data.read().await;
        Ok((data.last_applied, data.last_membership.clone()))
    }

    async fn apply<I>(&mut self, entries: I) -> StorageResult<Vec<RaftResponse>>
    where
        I: IntoIterator<Item = Entry<TypeConfig>> + OptionalSend,
        I::IntoIter: OptionalSend,
    {
        let meta_db = self.meta_db.clone();
        let events_tx = self.events.clone();
        let mut data = self.data.write().await;
        let mut responses = Vec::new();
        let mut pending: Vec<WatchEvent> = Vec::new();

        for entry in entries {
            data.last_applied = Some(entry.log_id);
            let response = match entry.payload {
                EntryPayload::Blank => RaftResponse::Noop,
                EntryPayload::Normal(request) => match data.store.apply(&request.op) {
                    Ok(Applied::Put { revision, created }) => {
                        pending.push(WatchEvent {
                            revision,
                            key: op_key(&request.op),
                            kind: EventKind::Put,
                        });
                        RaftResponse::Applied { revision, created }
                    }
                    Ok(Applied::Deleted { revision }) => {
                        pending.push(WatchEvent {
                            revision,
                            key: op_key(&request.op),
                            kind: EventKind::Delete,
                        });
                        RaftResponse::Deleted { revision }
                    }
                    Err(err) => RaftResponse::Rejected {
                        reason: err.to_string(),
                    },
                },
                EntryPayload::Membership(membership) => {
                    data.last_membership = StoredMembership::new(Some(entry.log_id), membership);
                    RaftResponse::Noop
                }
            };
            responses.push(response);
        }

        persist_meta(&meta_db, &data)?;
        drop(data);

        for event in pending {
            let _ = events_tx.send(event);
        }
        Ok(responses)
    }

    async fn get_snapshot_builder(&mut self) -> Self::SnapshotBuilder {
        self.clone()
    }

    async fn begin_receiving_snapshot(&mut self) -> StorageResult<Box<Cursor<Vec<u8>>>> {
        Ok(Box::new(Cursor::new(Vec::new())))
    }

    async fn install_snapshot(
        &mut self,
        meta: &SnapshotMeta<NodeId, BasicNode>,
        snapshot: Box<Cursor<Vec<u8>>>,
    ) -> StorageResult<()> {
        let bytes = snapshot.into_inner();
        let payload = decode_snapshot(&bytes)?;
        if payload.last_applied != meta.last_log_id
            || payload.last_membership != meta.last_membership
        {
            return Err(io_sm(
                ErrorVerb::Read,
                IoError::new(
                    ErrorKind::InvalidData,
                    "snapshot payload metadata does not match Raft metadata",
                ),
            ));
        }

        let meta_db = self.meta_db.clone();
        {
            let mut data = self.data.write().await;
            data.store
                .restore_exact(&payload.kvs, payload.revision)
                .map_err(|e| io_sm(ErrorVerb::Write, e))?;
            data.last_applied = meta.last_log_id;
            data.last_membership = meta.last_membership.clone();
            persist_meta(&meta_db, &data)?;
        }

        let stored = StoredSnapshot {
            meta: meta.clone(),
            data: bytes,
        };
        sm_write(&meta_db, "snapshot", &stored)
    }

    async fn get_current_snapshot(&mut self) -> StorageResult<Option<Snapshot<TypeConfig>>> {
        let stored: Option<StoredSnapshot> = sm_read(&self.meta_db, "snapshot")?;
        Ok(stored.map(|s| Snapshot {
            meta: s.meta,
            snapshot: Box::new(Cursor::new(s.data)),
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn versioned_snapshot_checksum_rejects_tampering() {
        let payload = SnapshotPayload {
            revision: 1,
            kvs: vec![(
                "Workload/checksum".to_owned(),
                Versioned {
                    value: b"sealed".to_vec(),
                    create_revision: 1,
                    mod_revision: 1,
                    version: 1,
                },
            )],
            last_applied: None,
            last_membership: StoredMembership::default(),
        };
        let bytes = snapshot_bytes(payload).unwrap();
        let mut envelope: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        envelope["payload"]["kvs"][0][1]["value"] =
            serde_json::json!([102, 111, 114, 103, 101, 100]);
        let tampered = serde_json::to_vec(&envelope).unwrap();

        assert!(decode_snapshot(&tampered).is_err());
    }
}
