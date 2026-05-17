//! Framework-level errors for the adapter management layer.
//!
//! These are DISTINCT from `mai_hil::traits::adapter::AdapterError` which
//! represents errors FROM an adapter. These represent errors in the
//! framework's management of adapter processes.

use thiserror::Error;

/// Errors that occur in the adapter management framework itself.
#[derive(Error, Debug)]
pub enum FrameworkError {
    /// Adapter process failed to start.
    #[error("Failed to spawn adapter process '{name}': {reason}")]
    SpawnFailed { name: String, reason: String },

    /// Adapter process exited unexpectedly.
    #[error("Adapter '{name}' crashed (exit code: {exit_code:?})")]
    ProcessCrashed {
        name: String,
        exit_code: Option<i32>,
    },

    /// Adapter did not respond to heartbeat within deadline.
    #[error("Adapter '{name}' missed {missed_count} heartbeats")]
    HeartbeatTimeout { name: String, missed_count: u32 },

    /// IPC protocol error (malformed JSON, unexpected message type).
    #[error("IPC protocol error with adapter '{name}': {detail}")]
    ProtocolError { name: String, detail: String },

    /// Adapter initialization failed.
    #[error("Adapter '{name}' failed to initialize: {reason}")]
    InitFailed { name: String, reason: String },

    /// Maximum restart attempts exceeded.
    #[error("Adapter '{name}' exceeded max restarts ({attempts} attempts)")]
    MaxRestartsExceeded { name: String, attempts: u32 },

    /// Configuration error.
    #[error("Configuration error for adapter '{name}': {reason}")]
    ConfigError { name: String, reason: String },

    /// Adapter not found in registry.
    #[error("Adapter '{name}' not found")]
    AdapterNotFound { name: String },

    /// Adapter is not in a ready state.
    #[error("Adapter '{name}' is not ready (state: {state})")]
    NotReady { name: String, state: String },

    /// IO error during IPC.
    #[error("IO error communicating with adapter '{name}': {source}")]
    Io {
        name: String,
        #[source]
        source: std::io::Error,
    },

    /// Serialization/deserialization error.
    #[error("Serialization error: {0}")]
    Serde(#[from] serde_json::Error),

    /// Timeout waiting for adapter response.
    #[error("Timeout waiting for adapter '{name}' response ({timeout_ms}ms)")]
    ResponseTimeout { name: String, timeout_ms: u64 },
}
