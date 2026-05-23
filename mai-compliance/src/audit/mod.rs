//! Compliance audit log (Session 42 + BF-5).
//!
//! The audit log is the tamper-evident record of every policy
//! decision the compliance runtime makes. Submodules:
//!
//! - [`entry`] — [`AuditEntry`] schema with embedded BF-5
//!   correlation block ([`CorrelationFields`]).
//! - [`chain`] — append-only [`HashChainManager`] with optional
//!   periodic ML-DSA-87 signatures via [`ChainSigner`] /
//!   [`MlDsaChainSigner`].
//! - [`store`] — in-memory tail + optional JSON-lines WAL with
//!   pluggable [`StoreSealer`] for at-rest encryption; also owns the
//!   BF-5 offline correlation queue.
//! - [`triggers`] — [`TriggerManager`] for sliding-window violation
//!   escalation, policy-change events, chain-break alerts, and
//!   storage-quota watermarks.
//! - [`api`] — [`AuditLog`] façade that composes chain + store +
//!   triggers and backs the S42 HTTP endpoints.
//!
//! The signing path uses the same ML-DSA-87 primitives as the BF-3
//! bundle verifier (see [`crate::bundle::MlDsaBundleVerifier`]) so
//! external auditors can verify periodic chain signatures with the
//! same tooling they use for signed policy bundles.

pub mod api;
pub mod chain;
pub mod entry;
pub mod store;
pub mod triggers;

pub use api::{
    AuditLog, AuditLogBuilder, AuditQuery, AuditQueryRow, AuditRecordInput, IntegrityStatus,
    VerificationStatus,
};
pub use chain::{
    ChainConfig, ChainError, ChainSigner, DEFAULT_SIGNATURE_INTERVAL, HashChainManager,
    MlDsaChainSigner, NullSigner, verify_chain,
};
pub use entry::{
    AuditEntry, CHAIN_HASH_LEN, CorrelationFields, EntriesById, RoutingDecision, RuleMatch,
    SIGNATURE_LEN, masked_request_hash,
};
pub use store::{
    AuditStore, AuditStoreConfig, DEFAULT_RETENTION_DAYS, NullSealer, StoreDropCounters,
    StoreError, StoreSealer,
};
pub use triggers::{Escalation, Severity, TriggerManager, TriggersConfig};
