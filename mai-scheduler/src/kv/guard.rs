//! Anti-thrashing guard for KV cache eviction.
//!
//! Prevents pathological evict-then-immediately-readmit cycles that waste
//! GPU bandwidth and destroy throughput. Three mechanisms:
//!
//! 1. **Minimum residency**: a sequence cannot be evicted within N seconds
//!    of its creation (configurable, default 30s).
//!
//! 2. **Recently-evicted penalty**: if a sequence was evicted and re-admitted
//!    within M seconds, its eviction score gets a penalty reduction that makes
//!    it harder to evict again (prevents ping-pong).
//!
//! 3. **Eviction rate limiter**: at most N evictions per second to prevent
//!    cascade failures when VRAM pressure spikes.
//!
//! The guard also tracks the last 100 evictions for diagnostic telemetry.

use std::collections::VecDeque;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};

use crate::kv::sequence::SequenceMeta;
use crate::types::SequenceId;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// Anti-thrashing configuration. Loaded from config/kv.toml.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AntiThrashConfig {
    /// Minimum time a sequence must exist before it can be evicted.
    /// Default: 30 seconds.
    #[serde(default = "default_min_residency_secs")]
    pub min_residency_secs: f64,

    /// Time window for recently-evicted detection. If a sequence was evicted
    /// and re-admitted within this many seconds, apply the re-eviction penalty.
    /// Default: 120 seconds (2 minutes).
    #[serde(default = "default_readmit_window_secs")]
    pub readmit_window_secs: f64,

    /// Penalty reduction applied to recently re-admitted sequences' eviction
    /// scores. A negative value makes the sequence harder to evict.
    /// Default: -100.0
    #[serde(default = "default_readmit_penalty")]
    pub readmit_penalty: f64,

    /// Maximum evictions per second. Prevents cascade eviction under sudden
    /// VRAM pressure. Default: 10.
    #[serde(default = "default_max_evictions_per_sec")]
    pub max_evictions_per_sec: u32,

    /// Maximum eviction history entries to retain. Default: 100.
    #[serde(default = "default_max_history")]
    pub max_history: usize,
}

fn default_min_residency_secs() -> f64 {
    30.0
}
fn default_readmit_window_secs() -> f64 {
    120.0
}
fn default_readmit_penalty() -> f64 {
    -100.0
}
fn default_max_evictions_per_sec() -> u32 {
    10
}
fn default_max_history() -> usize {
    100
}

impl Default for AntiThrashConfig {
    fn default() -> Self {
        Self {
            min_residency_secs: default_min_residency_secs(),
            readmit_window_secs: default_readmit_window_secs(),
            readmit_penalty: default_readmit_penalty(),
            max_evictions_per_sec: default_max_evictions_per_sec(),
            max_history: default_max_history(),
        }
    }
}

// ---------------------------------------------------------------------------
// Eviction history record
// ---------------------------------------------------------------------------

/// Record of a single eviction event.
#[derive(Debug, Clone)]
pub struct EvictionRecord {
    /// Which sequence was evicted.
    pub seq_id: SequenceId,
    /// When the eviction occurred.
    pub evicted_at: Instant,
    /// How many bytes were freed.
    pub bytes_freed: u64,
    /// The eviction score at the time.
    pub score: f64,
}

// ---------------------------------------------------------------------------
// ThrashGuard
// ---------------------------------------------------------------------------

/// The anti-thrashing guard. Enforces minimum residency, penalizes
/// re-admitted sequences, and rate-limits evictions.
///
/// This struct is NOT thread-safe by itself. It is wrapped in a Mutex
/// inside the `HeuristicKvCacheManager` since eviction decisions are
/// inherently sequential (you don't want two threads evicting the same
/// sequence simultaneously).
#[derive(Debug)]
pub struct ThrashGuard {
    config: AntiThrashConfig,
    /// Timestamps of recent evictions (for rate limiting).
    recent_eviction_times: VecDeque<Instant>,
    /// History of eviction events (for telemetry).
    eviction_history: VecDeque<EvictionRecord>,
}

impl ThrashGuard {
    /// Create a new guard with the given configuration.
    pub fn new(config: AntiThrashConfig) -> Self {
        Self {
            config,
            recent_eviction_times: VecDeque::new(),
            eviction_history: VecDeque::new(),
        }
    }

    /// Check whether a sequence is protected from eviction by the minimum
    /// residency rule.
    ///
    /// Returns true if the sequence has existed for less than
    /// `min_residency_secs` and should NOT be evicted.
    pub fn is_protected(&self, meta: &SequenceMeta) -> bool {
        let age = meta.age().as_secs_f64();
        age < self.config.min_residency_secs
    }

    /// Compute the score adjustment for a sequence based on anti-thrashing
    /// rules. Negative values reduce the eviction score (making the sequence
    /// harder to evict).
    ///
    /// Currently only applies the re-admission penalty. Returns 0.0 if the
    /// sequence has never been evicted or was evicted outside the readmit
    /// window.
    pub fn score_adjustment(&self, meta: &SequenceMeta) -> f64 {
        if !meta.was_readmitted {
            return 0.0;
        }

        // Check if the re-admission was recent enough to warrant the penalty
        if let Some(evicted_at) = meta.last_eviction_at {
            let since_eviction = evicted_at.elapsed().as_secs_f64();
            if since_eviction < self.config.readmit_window_secs {
                return self.config.readmit_penalty;
            }
        }

        0.0
    }

    /// Check whether the eviction rate limit allows another eviction right now.
    ///
    /// Returns true if we can evict, false if the rate limit is exceeded.
    pub fn can_evict_now(&mut self) -> bool {
        let now = Instant::now();
        let window = Duration::from_secs(1);

        // Purge entries older than 1 second
        while let Some(front) = self.recent_eviction_times.front() {
            if now.duration_since(*front) > window {
                self.recent_eviction_times.pop_front();
            } else {
                break;
            }
        }

        #[allow(clippy::cast_possible_truncation)] // u32 max_evictions fits in usize
        let limit = self.config.max_evictions_per_sec as usize;
        self.recent_eviction_times.len() < limit
    }

    /// Record that an eviction just occurred. Updates rate limiter state
    /// and eviction history.
    pub fn record_eviction(&mut self, record: EvictionRecord) {
        let now = Instant::now();
        self.recent_eviction_times.push_back(now);

        self.eviction_history.push_back(record);
        while self.eviction_history.len() > self.config.max_history {
            self.eviction_history.pop_front();
        }
    }

    /// Get the eviction history (for telemetry/debugging).
    pub fn history(&self) -> &VecDeque<EvictionRecord> {
        &self.eviction_history
    }

    /// Current eviction rate (evictions in the last second).
    #[allow(clippy::cast_possible_truncation)] // eviction count won't exceed u32::MAX
    pub fn current_rate(&mut self) -> u32 {
        let now = Instant::now();
        let window = Duration::from_secs(1);

        // Purge stale entries
        while let Some(front) = self.recent_eviction_times.front() {
            if now.duration_since(*front) > window {
                self.recent_eviction_times.pop_front();
            } else {
                break;
            }
        }

        self.recent_eviction_times.len() as u32
    }

    /// Update configuration at runtime.
    pub fn update_config(&mut self, config: AntiThrashConfig) {
        self.config = config;
    }

    /// Current configuration (for introspection).
    pub fn config(&self) -> &AntiThrashConfig {
        &self.config
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::kv::sequence::{ModelMemoryFactor, SequenceMeta};
    use crate::types::{InstanceId, Priority, SequenceId};
    use std::thread;

    fn test_factor() -> ModelMemoryFactor {
        ModelMemoryFactor {
            layers: 32,
            kv_heads: 8,
            head_dim: 128,
            dtype_size: 2,
        }
    }

    fn make_meta(priority: Priority) -> SequenceMeta {
        SequenceMeta::new(
            SequenceId::new(),
            InstanceId::new("test:0"),
            "llama3-8b".to_string(),
            512,
            priority,
            &test_factor(),
        )
    }

    #[test]
    fn test_recently_created_is_protected() {
        let guard = ThrashGuard::new(AntiThrashConfig {
            min_residency_secs: 30.0,
            ..AntiThrashConfig::default()
        });

        let meta = make_meta(Priority::Normal);
        // Just created, should be protected
        assert!(guard.is_protected(&meta));
    }

    #[test]
    fn test_old_sequence_not_protected() {
        let guard = ThrashGuard::new(AntiThrashConfig {
            min_residency_secs: 0.01, // 10ms
            ..AntiThrashConfig::default()
        });

        let meta = make_meta(Priority::Normal);
        thread::sleep(Duration::from_millis(15));
        assert!(!guard.is_protected(&meta));
    }

    #[test]
    fn test_readmitted_sequence_gets_penalty() {
        let guard = ThrashGuard::new(AntiThrashConfig::default());

        let mut meta = make_meta(Priority::Normal);
        // Not readmitted: no penalty
        assert!((guard.score_adjustment(&meta) - 0.0).abs() < f64::EPSILON);

        // Mark as readmitted recently
        meta.mark_evicted();
        meta.mark_readmitted();
        let adjustment = guard.score_adjustment(&meta);
        assert!(
            adjustment < 0.0,
            "readmitted penalty should be negative: {adjustment}"
        );
        assert!((adjustment - (-100.0)).abs() < f64::EPSILON);
    }

    #[test]
    fn test_old_readmission_no_penalty() {
        let guard = ThrashGuard::new(AntiThrashConfig {
            readmit_window_secs: 0.01, // 10ms
            ..AntiThrashConfig::default()
        });

        let mut meta = make_meta(Priority::Normal);
        meta.mark_evicted();
        meta.mark_readmitted();

        thread::sleep(Duration::from_millis(15));
        // Eviction was too long ago, no penalty
        assert!((guard.score_adjustment(&meta) - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_rate_limiter_allows_within_limit() {
        let mut guard = ThrashGuard::new(AntiThrashConfig {
            max_evictions_per_sec: 5,
            ..AntiThrashConfig::default()
        });

        for _ in 0..5 {
            assert!(guard.can_evict_now());
            guard.record_eviction(EvictionRecord {
                seq_id: SequenceId::new(),
                evicted_at: Instant::now(),
                bytes_freed: 1000,
                score: 1.0,
            });
        }

        // 6th should be blocked
        assert!(!guard.can_evict_now());
    }

    #[test]
    fn test_rate_limiter_resets_after_window() {
        let mut guard = ThrashGuard::new(AntiThrashConfig {
            max_evictions_per_sec: 2,
            ..AntiThrashConfig::default()
        });

        // Fill the rate limiter
        for _ in 0..2 {
            guard.record_eviction(EvictionRecord {
                seq_id: SequenceId::new(),
                evicted_at: Instant::now(),
                bytes_freed: 1000,
                score: 1.0,
            });
        }
        assert!(!guard.can_evict_now());

        // Wait for window to expire
        thread::sleep(Duration::from_millis(1050));
        assert!(guard.can_evict_now());
    }

    #[test]
    fn test_eviction_history_capped() {
        let mut guard = ThrashGuard::new(AntiThrashConfig {
            max_history: 3,
            ..AntiThrashConfig::default()
        });

        for _ in 0..5 {
            guard.record_eviction(EvictionRecord {
                seq_id: SequenceId::new(),
                evicted_at: Instant::now(),
                bytes_freed: 1000,
                score: 1.0,
            });
        }

        assert_eq!(guard.history().len(), 3);
    }

    #[test]
    fn test_current_rate() {
        let mut guard = ThrashGuard::new(AntiThrashConfig::default());
        assert_eq!(guard.current_rate(), 0);

        guard.record_eviction(EvictionRecord {
            seq_id: SequenceId::new(),
            evicted_at: Instant::now(),
            bytes_freed: 1000,
            score: 1.0,
        });
        assert_eq!(guard.current_rate(), 1);
    }
}
