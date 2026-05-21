//! The KvCacheManager trait: single authority for GPU VRAM KV cache management.
//!
//! # Design Principles
//!
//! 1. **Object-safe**: Uses `&self` with interior mutability so it can be
//!    stored as `Arc<dyn KvCacheManager>` in the scheduler.
//!
//! 2. **Concurrent**: Multiple scheduler tasks call `can_fit()` and `touch()`
//!    in parallel. The implementation must not hold a global write lock during
//!    reads. DashMap + atomics internally.
//!
//! 3. **Single authority**: Only the KV cache manager tracks VRAM used for
//!    KV caches. The scheduler consults it before placement decisions.
//!
//! 4. **Eviction-aware**: The manager provides scored eviction candidates
//!    so the scheduler can factor eviction cost into placement decisions.

use crate::kv::sequence::SequenceMeta;
use crate::types::{SchedulerError, SequenceId};

/// The KV cache manager trait. Implemented by `HeuristicKvCacheManager`
/// (this crate) and potentially by test doubles.
///
/// All methods take `&self`. Implementations must provide interior mutability
/// (e.g., via `DashMap`, `RwLock`, atomics) to handle concurrent access from
/// multiple tokio tasks.
pub trait KvCacheManager: Send + Sync {
    /// Allocate KV cache space for a new sequence.
    ///
    /// Records the sequence metadata and reserves the estimated memory.
    /// Returns an error if the sequence is already tracked (duplicate ID).
    fn allocate(&self, seq: SequenceMeta) -> Result<(), SchedulerError>;

    /// Deallocate KV cache space for a completed sequence.
    ///
    /// Removes the sequence from tracking and frees its memory budget.
    /// No-op if the sequence is not tracked (idempotent for crash paths).
    fn deallocate(&self, seq_id: SequenceId);

    /// Check whether a new sequence with the estimated token count can fit
    /// in the remaining VRAM budget.
    ///
    /// `estimated_tokens` is the expected context length. `model_factor` is
    /// the per-token byte cost (from `ModelMemoryFactor::bytes_per_token()`).
    /// Returns true if the estimated bytes fit within free capacity.
    fn can_fit(&self, estimated_tokens: usize, model_factor: f64) -> bool;

    /// Compute eviction candidates to free at least `needed_bytes` of VRAM.
    ///
    /// Returns a vec of (seq_id, bytes_freed, eviction_score) sorted by
    /// score descending (highest score = most evictable). The caller picks
    /// from the top of this list until enough bytes are freed.
    ///
    /// Does NOT actually evict anything. Call `evict()` to perform eviction.
    fn eviction_candidates(&self, needed_bytes: u64) -> Vec<(SequenceId, u64, f64)>;

    /// Evict the specified sequences, freeing their KV cache memory.
    ///
    /// Returns total bytes actually freed. Sequences not found are skipped.
    fn evict(&self, sequences: &[SequenceId]) -> u64;

    /// Update last access time for a sequence. Called on each token
    /// generation to keep the idle timer fresh.
    fn touch(&self, seq_id: SequenceId);

    /// Current free bytes in the VRAM budget.
    fn free_bytes(&self) -> u64;

    /// Total VRAM budget for KV caches.
    fn total_bytes(&self) -> u64;

    /// Number of sequences currently tracked.
    fn active_sequences(&self) -> usize;

    /// Get a snapshot of a sequence's metadata. Returns None if not tracked.
    fn sequence_meta(&self, seq_id: SequenceId) -> Option<SequenceMeta>;
}
