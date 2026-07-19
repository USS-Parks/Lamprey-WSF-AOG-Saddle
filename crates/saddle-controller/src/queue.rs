//! The controller workqueue: dedup, per-key exponential backoff, delayed
//! requeue. K8s-workqueue shaped, level-triggered: a queued key means
//! "reconcile this key at least once more", so adding a key that is already
//! queued coalesces into the one pending run (a duplicate event costs
//! nothing), and a key re-added *while it is being processed* is marked dirty
//! and re-queued when its run completes (no update lost between a
//! reconciler's read and its write).
//!
//! Time is always passed in by the caller (`now: Instant`) — the queue never
//! reads a clock — so retry and delay behavior is deterministic under test.

use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::time::{Duration, Instant};

const DEFAULT_MAX_RETRIES: u32 = 8;

/// Per-key exponential backoff: `base * 2^(n-1)` before the `n`-th
/// consecutive retry, capped at `max`. This is the rate limit on a failing
/// key — a broken object retries ever more slowly instead of hot-looping the
/// controller, while one success ([`WorkQueue::forget`]) resets it.
#[derive(Debug, Clone, Copy)]
pub struct Backoff {
    pub base: Duration,
    pub max: Duration,
}

impl Default for Backoff {
    fn default() -> Self {
        Self {
            base: Duration::from_millis(200),
            max: Duration::from_secs(60),
        }
    }
}

impl Backoff {
    /// The delay before retry number `failures` (1-based). Zero means no delay.
    #[must_use]
    pub fn delay(&self, failures: u32) -> Duration {
        if failures == 0 {
            return Duration::ZERO;
        }
        let factor = 1u32.checked_shl(failures - 1).unwrap_or(u32::MAX);
        self.backoff_mul(factor)
    }

    /// Deterministic per-key jitter in the inclusive range 75%-100% of the
    /// exponential ceiling. A stable hash keeps fault-history tests exactly
    /// reproducible while preventing a controller fleet from retrying every
    /// failed key in lockstep.
    #[must_use]
    pub fn delay_for(&self, key: &str, failures: u32) -> Duration {
        let ceiling = self.delay(failures);
        if ceiling.is_zero() {
            return ceiling;
        }

        // FNV-1a is deliberate: `DefaultHasher` output is not a cross-version
        // contract and would make generated fault evidence unstable.
        let mut hash = 0xcbf2_9ce4_8422_2325_u64;
        for byte in key.as_bytes().iter().copied().chain(failures.to_le_bytes()) {
            hash ^= u64::from(byte);
            hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        }
        let permille = 750_u128 + u128::from(hash % 251);
        let nanos = ceiling.as_nanos().saturating_mul(permille) / 1_000;
        let seconds = nanos / 1_000_000_000;
        let subsec_nanos = u32::try_from(nanos % 1_000_000_000).unwrap_or(u32::MAX);
        Duration::new(u64::try_from(seconds).unwrap_or(u64::MAX), subsec_nanos)
            .max(Duration::from_nanos(1))
    }

    fn backoff_mul(&self, factor: u32) -> Duration {
        self.base
            .checked_mul(factor)
            .map_or(self.max, |d| d.min(self.max))
    }
}

/// A key whose consecutive reconciles exhausted the automatic retry budget.
/// It remains visible and can be redriven by a new event, resync, or explicit
/// enqueue.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeadLetter {
    /// Store key that could not be reconciled.
    pub key: String,
    /// Consecutive failures in the exhausted retry cycle.
    pub failures: u32,
    /// Most recent reconcile error or deadline diagnostic.
    pub last_error: String,
}

/// Result of recording one failed reconcile.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RetryResult {
    /// Consecutive failures including this attempt.
    pub failures: u32,
    /// Jittered delay when another automatic retry was scheduled.
    pub delay: Option<Duration>,
    /// Whether this attempt exhausted the retry cycle.
    pub dead_lettered: bool,
}

/// The dedup-ing, backoff-aware work queue driving one controller.
///
/// Lifecycle of a key: [`add`](WorkQueue::add) →
/// [`take`](WorkQueue::take) (caller reconciles) → exactly one of
/// [`forget`](WorkQueue::forget) (success),
/// [`retry`](WorkQueue::retry) (failure → delayed re-add with backoff), or
/// [`requeue_after`](WorkQueue::requeue_after) (voluntary re-run) → then
/// [`done`](WorkQueue::done). Delayed re-adds become due via
/// [`drain_ready`](WorkQueue::drain_ready).
#[derive(Debug)]
pub struct WorkQueue {
    fifo: VecDeque<String>,
    queued: HashSet<String>,
    processing: HashSet<String>,
    dirty: HashSet<String>,
    failures: HashMap<String, u32>,
    delayed: HashMap<String, Instant>,
    dead_letters: BTreeMap<String, DeadLetter>,
    backoff: Backoff,
    max_retries: u32,
}

impl Default for WorkQueue {
    fn default() -> Self {
        Self {
            fifo: VecDeque::new(),
            queued: HashSet::new(),
            processing: HashSet::new(),
            dirty: HashSet::new(),
            failures: HashMap::new(),
            delayed: HashMap::new(),
            dead_letters: BTreeMap::new(),
            backoff: Backoff::default(),
            max_retries: DEFAULT_MAX_RETRIES,
        }
    }
}

impl WorkQueue {
    #[must_use]
    pub fn new(backoff: Backoff) -> Self {
        Self {
            backoff,
            ..Self::default()
        }
    }

    /// Replace the retry backoff without discarding queued work or failure
    /// visibility.
    pub fn set_backoff(&mut self, backoff: Backoff) {
        self.backoff = backoff;
    }

    /// Set the consecutive-failure limit before a key becomes a visible dead
    /// letter. At least one attempt is always allowed.
    pub fn set_max_retries(&mut self, max_retries: u32) {
        self.max_retries = max_retries.max(1);
    }

    /// Enqueue `key` for reconciliation. Coalesces: a key already queued is
    /// not queued twice; a key currently being processed is marked dirty and
    /// re-queued when [`done`](WorkQueue::done) is called for it.
    pub fn add(&mut self, key: &str) {
        // A genuinely new observation or explicit operator kick supersedes an
        // old retry delay. Keep an existing dead-letter diagnostic visible
        // until the redriven key actually succeeds (`forget`).
        if self.delayed.remove(key).is_some() || self.dead_letters.contains_key(key) {
            self.failures.remove(key);
        }
        self.enqueue(key);
    }

    /// Periodic level-triggered re-enqueue. An ordinary delayed retry keeps
    /// its backoff, while a dead letter is explicitly redriven.
    pub fn add_resync(&mut self, key: &str) -> bool {
        if self.dead_letters.contains_key(key) {
            self.failures.remove(key);
            self.delayed.remove(key);
            return self.enqueue(key);
        }
        if self.delayed.contains_key(key) {
            return false;
        }
        self.enqueue(key)
    }

    fn enqueue(&mut self, key: &str) -> bool {
        if self.processing.contains(key) {
            self.dirty.insert(key.to_owned());
            return false;
        }
        if self.queued.insert(key.to_owned()) {
            self.fifo.push_back(key.to_owned());
            return true;
        }
        false
    }

    /// Pop the next key to reconcile, marking it in-processing.
    pub fn take(&mut self) -> Option<String> {
        let key = self.fifo.pop_front()?;
        self.queued.remove(&key);
        self.processing.insert(key.clone());
        Some(key)
    }

    /// Mark a key's reconcile finished. If the key went dirty while it was
    /// being processed (a change landed mid-reconcile), it is re-queued so the
    /// newer state is observed — the no-lost-update half of level-triggering.
    pub fn done(&mut self, key: &str) {
        self.processing.remove(key);
        if self.dirty.remove(key) {
            self.add(key);
        }
    }

    /// Record a failed reconcile and schedule the delayed retry under the
    /// backoff policy. Returns the consecutive-failure count.
    pub fn retry(&mut self, key: &str, now: Instant) -> u32 {
        self.retry_with_error(key, "reconcile failed", now).failures
    }

    /// Record a failed reconcile with its diagnostic. Retries use deterministic
    /// keyed jitter. Once `max_retries` is reached, the key is retained in the
    /// dead-letter map instead of being silently dropped.
    pub fn retry_with_error(
        &mut self,
        key: &str,
        error: impl Into<String>,
        now: Instant,
    ) -> RetryResult {
        let error = error.into();
        let n = self.failures.entry(key.to_owned()).or_insert(0);
        *n = n.saturating_add(1);
        let failures = *n;
        self.delayed.remove(key);
        if let Some(dead_letter) = self.dead_letters.get_mut(key) {
            dead_letter.failures = failures;
            dead_letter.last_error.clone_from(&error);
        }
        if failures >= self.max_retries {
            self.dead_letters.insert(
                key.to_owned(),
                DeadLetter {
                    key: key.to_owned(),
                    failures,
                    last_error: error,
                },
            );
            return RetryResult {
                failures,
                delay: None,
                dead_lettered: true,
            };
        }

        let delay = self.backoff.delay_for(key, failures);
        self.delayed.insert(key.to_owned(), now + delay);
        RetryResult {
            failures,
            delay: Some(delay),
            dead_lettered: false,
        }
    }

    /// Schedule a voluntary re-run of `key` after `delay` (no failure counted).
    pub fn requeue_after(&mut self, key: &str, delay: Duration, now: Instant) {
        let due = now + delay;
        self.delayed
            .entry(key.to_owned())
            .and_modify(|existing| *existing = (*existing).min(due))
            .or_insert(due);
    }

    /// Reset the failure count for `key` (call on success).
    pub fn forget(&mut self, key: &str) {
        self.failures.remove(key);
        self.delayed.remove(key);
        self.dead_letters.remove(key);
    }

    /// Move every delayed key whose due time has arrived back into the queue.
    /// Returns how many came due (dedup may coalesce them into fewer entries).
    pub fn drain_ready(&mut self, now: Instant) -> usize {
        let mut ready = Vec::new();
        self.delayed.retain(|key, due| {
            if *due <= now {
                ready.push(key.clone());
                false
            } else {
                true
            }
        });
        for key in &ready {
            self.enqueue(key);
        }
        ready.len()
    }

    /// Requeue every dead letter without erasing its diagnostic. A successful
    /// reconcile clears it; another exhausted retry cycle updates it.
    pub fn redrive_dead_letters(&mut self) -> usize {
        let keys: Vec<String> = self.dead_letters.keys().cloned().collect();
        let mut enqueued = 0;
        for key in keys {
            self.failures.remove(&key);
            self.delayed.remove(&key);
            enqueued += usize::from(self.enqueue(&key));
        }
        enqueued
    }

    /// Deterministically ordered dead-letter diagnostics.
    #[must_use]
    pub fn dead_letters(&self) -> Vec<DeadLetter> {
        self.dead_letters.values().cloned().collect()
    }

    /// Consecutive failures recorded for `key`.
    #[must_use]
    pub fn failures(&self, key: &str) -> u32 {
        self.failures.get(key).copied().unwrap_or(0)
    }

    /// Keys currently queued (excludes delayed and in-processing keys).
    #[must_use]
    pub fn len(&self) -> usize {
        self.fifo.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.fifo.is_empty()
    }

    /// Keys scheduled for a future re-add.
    #[must_use]
    pub fn delayed_len(&self) -> usize {
        self.delayed.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn duplicate_adds_coalesce() {
        let mut q = WorkQueue::default();
        q.add("a");
        q.add("a");
        q.add("a");
        assert_eq!(q.len(), 1);
        assert_eq!(q.take().as_deref(), Some("a"));
        assert_eq!(q.take(), None);
    }

    #[test]
    fn add_during_processing_marks_dirty_and_requeues_on_done() {
        let mut q = WorkQueue::default();
        q.add("a");
        let key = q.take().unwrap();
        // A change lands while "a" is being reconciled…
        q.add("a");
        assert!(q.is_empty(), "dirty key must not re-enter the queue early");
        // …so finishing the run re-queues it for the newer state.
        q.done(&key);
        assert_eq!(q.take().as_deref(), Some("a"));
    }

    #[test]
    fn backoff_doubles_and_caps() {
        let b = Backoff {
            base: Duration::from_millis(10),
            max: Duration::from_millis(100),
        };
        assert_eq!(b.delay(0), Duration::ZERO);
        assert_eq!(b.delay(1), Duration::from_millis(10));
        assert_eq!(b.delay(2), Duration::from_millis(20));
        assert_eq!(b.delay(3), Duration::from_millis(40));
        assert_eq!(b.delay(5), Duration::from_millis(100), "capped at max");
        assert_eq!(b.delay(31), Duration::from_millis(100), "no overflow");
        assert_eq!(b.delay(u32::MAX), Duration::from_millis(100), "no overflow");
        let jittered = b.delay_for("tenant/acme", 3);
        assert!(jittered >= Duration::from_millis(30));
        assert!(jittered <= Duration::from_millis(40));
        assert_eq!(jittered, b.delay_for("tenant/acme", 3));
    }

    #[test]
    fn retry_schedules_delayed_and_drain_respects_due_time() {
        let mut q = WorkQueue::new(Backoff {
            base: Duration::from_millis(10),
            max: Duration::from_secs(1),
        });
        let now = Instant::now();
        q.add("a");
        let key = q.take().unwrap();
        assert_eq!(q.retry(&key, now), 1);
        q.done(&key);
        // Not due yet: nothing drains at `now`.
        assert_eq!(q.drain_ready(now), 0);
        assert!(q.is_empty());
        assert_eq!(q.delayed_len(), 1);
        // Due once the backoff delay has passed.
        assert_eq!(q.drain_ready(now + Duration::from_millis(10)), 1);
        assert_eq!(q.take().as_deref(), Some("a"));
    }

    #[test]
    fn failures_accumulate_and_forget_resets() {
        let mut q = WorkQueue::default();
        let now = Instant::now();
        q.add("a");
        let key = q.take().unwrap();
        assert_eq!(q.retry(&key, now), 1);
        assert_eq!(q.retry(&key, now), 2);
        assert_eq!(q.failures("a"), 2);
        q.forget(&key);
        assert_eq!(q.failures("a"), 0);
    }

    #[test]
    fn delayed_duplicates_coalesce_before_drain() {
        let mut q = WorkQueue::default();
        let now = Instant::now();
        // The same key scheduled twice (two failed replicas of one event)…
        q.requeue_after("a", Duration::ZERO, now);
        q.requeue_after("a", Duration::ZERO, now);
        // …is retained as one delayed entry and one queued run.
        assert_eq!(q.delayed_len(), 1);
        assert_eq!(q.drain_ready(now), 1);
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn exhausted_retry_is_visible_and_redrives_until_success() {
        let mut q = WorkQueue::new(Backoff {
            base: Duration::from_millis(10),
            max: Duration::from_secs(1),
        });
        q.set_max_retries(2);
        let now = Instant::now();

        let first = q.retry_with_error("a", "transient", now);
        assert!(!first.dead_lettered);
        assert!(first.delay.is_some());
        let second = q.retry_with_error("a", "still broken", now);
        assert!(second.dead_lettered);
        assert_eq!(q.delayed_len(), 0);
        assert_eq!(
            q.dead_letters(),
            vec![DeadLetter {
                key: "a".to_owned(),
                failures: 2,
                last_error: "still broken".to_owned(),
            }]
        );

        assert_eq!(q.redrive_dead_letters(), 1);
        assert_eq!(q.take().as_deref(), Some("a"));
        q.forget("a");
        q.done("a");
        assert!(q.dead_letters().is_empty());
    }

    #[test]
    fn resync_respects_backoff_and_redrives_dead_letters() {
        let mut q = WorkQueue::default();
        q.set_max_retries(2);
        let now = Instant::now();

        q.retry_with_error("a", "transient", now);
        assert!(!q.add_resync("a"), "resync must not bypass backoff");
        assert_eq!(q.delayed_len(), 1);

        q.retry_with_error("a", "persistent", now);
        assert_eq!(q.dead_letters().len(), 1);
        assert!(q.add_resync("a"), "resync redrives a visible dead letter");
        assert_eq!(q.take().as_deref(), Some("a"));
    }
}
