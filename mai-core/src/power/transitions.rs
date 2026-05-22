//! Transition execution with phases, hooks, timeout, and rollback.
//!
//! Each transition moves through discrete phases:
//!   1. Requested - guard check passed, transition initiated
//!   2. PreHook - scheduler prepares (drain, evict KV cache)
//!   3. Waiting - hardware responds (GPU wakes, model loads)
//!   4. PostHook - finalize (register instances, update state)
//!   5. Completed - new state is active
//!
//! If any phase exceeds the timeout, the transition rolls back.

use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use super::{PowerState, TransitionRecord, TransitionTrigger};

/// Phases of a power state transition.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransitionPhase {
    /// Guard check passed, transition initiated
    Requested,
    /// Pre-hook: scheduler drains, evicts, etc.
    PreHook,
    /// Waiting: hardware responds (GPU wake, model load)
    Waiting,
    /// Post-hook: register instances, update state
    PostHook,
    /// Transition completed successfully
    Completed,
    /// Transition failed and rolled back
    RolledBack,
}

impl TransitionPhase {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Requested => "requested",
            Self::PreHook => "pre_hook",
            Self::Waiting => "waiting",
            Self::PostHook => "post_hook",
            Self::Completed => "completed",
            Self::RolledBack => "rolled_back",
        }
    }
}

/// Executes a power state transition through its phases.
///
/// The executor manages the phase machine and timeout. The actual
/// pre-hook and post-hook actions are provided by the caller via
/// callbacks or by the PowerStateController.
pub struct TransitionExecutor {
    from: PowerState,
    to: PowerState,
    trigger: TransitionTrigger,
    phase: TransitionPhase,
    started_at: Instant,
    phase_started_at: Instant,
    timeout: Duration,
    timed_out: bool,
}

impl TransitionExecutor {
    /// Create a new transition executor for a given transition.
    pub fn new(
        from: PowerState,
        to: PowerState,
        trigger: TransitionTrigger,
        timeout: Duration,
    ) -> Self {
        Self {
            from,
            to,
            trigger,
            phase: TransitionPhase::Requested,
            started_at: Instant::now(),
            phase_started_at: Instant::now(),
            timeout,
            timed_out: false,
        }
    }

    pub fn from_state(&self) -> PowerState { self.from }
    pub fn to_state(&self) -> PowerState { self.to }
    pub fn trigger(&self) -> &TransitionTrigger { &self.trigger }
    pub fn phase(&self) -> TransitionPhase { self.phase }
    pub fn elapsed(&self) -> Duration { self.started_at.elapsed() }
    pub fn phase_elapsed(&self) -> Duration { self.phase_started_at.elapsed() }
    pub fn has_timed_out(&self) -> bool { self.timed_out }

    /// Advance to the next phase. Returns false if already completed.
    pub fn advance(&mut self) -> bool {
        match self.phase {
            TransitionPhase::Requested => {
                self.phase = TransitionPhase::PreHook;
                self.phase_started_at = Instant::now();
                info!(from = ?self.from, to = ?self.to, phase = ?self.phase, "Transition advancing");
                true
            }
            TransitionPhase::PreHook => {
                self.phase = TransitionPhase::Waiting;
                self.phase_started_at = Instant::now();
                true
            }
            TransitionPhase::Waiting => {
                self.phase = TransitionPhase::PostHook;
                self.phase_started_at = Instant::now();
                true
            }
            TransitionPhase::PostHook => {
                self.phase = TransitionPhase::Completed;
                self.phase_started_at = Instant::now();
                info!(from = ?self.from, to = ?self.to, elapsed_ms = self.elapsed().as_millis(), "Transition completed");
                true
            }
            TransitionPhase::Completed | TransitionPhase::RolledBack => false,
        }
    }

    /// Check if the current phase has exceeded the timeout.
    pub fn check_timeout(&mut self) -> bool {
        if self.timed_out { return true; }
        if self.phase == TransitionPhase::Completed || self.phase == TransitionPhase::RolledBack {
            return false;
        }
        if self.phase_elapsed() >= self.timeout {
            self.timed_out = true;
            warn!(from = ?self.from, to = ?self.to, phase = ?self.phase, timeout_ms = self.timeout.as_millis(), "Transition phase timed out");
            true
        } else {
            false
        }
    }

    /// Mark the transition as rolled back (recovery from timeout/failure).
    pub fn rollback(&mut self) {
        self.phase = TransitionPhase::RolledBack;
        self.phase_started_at = Instant::now();
        warn!(from = ?self.from, to = ?self.to, elapsed_ms = self.elapsed().as_millis(), "Transition rolled back");
    }

    /// Whether the transition is in a terminal state.
    pub fn is_terminal(&self) -> bool {
        matches!(self.phase, TransitionPhase::Completed | TransitionPhase::RolledBack)
    }

    /// Build a TransitionRecord for the audit log.
    pub fn to_record(&self) -> TransitionRecord {
        #[allow(clippy::cast_possible_truncation)]
        let epoch_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;
        #[allow(clippy::cast_possible_truncation)]
        let dur_ms = self.elapsed().as_millis() as u64;
        TransitionRecord {
            id: uuid::Uuid::new_v4(),
            from: self.from,
            to: self.to,
            trigger: self.trigger.clone(),
            timestamp_epoch_ms: epoch_ms,
            duration_ms: Some(dur_ms),
            success: self.phase == TransitionPhase::Completed,
            phase: Some(self.phase.as_str().to_string()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_phase_is_requested() {
        let ex = TransitionExecutor::new(PowerState::Off, PowerState::DeepVaultSleep, TransitionTrigger::SystemBoot, Duration::from_secs(30));
        assert_eq!(ex.phase(), TransitionPhase::Requested);
    }

    #[test]
    fn test_advance_through_phases() {
        let mut ex = TransitionExecutor::new(PowerState::Sentinel, PowerState::FullInference, TransitionTrigger::SentinelPromotion, Duration::from_secs(30));
        assert!(ex.advance()); assert_eq!(ex.phase(), TransitionPhase::PreHook);
        assert!(ex.advance()); assert_eq!(ex.phase(), TransitionPhase::Waiting);
        assert!(ex.advance()); assert_eq!(ex.phase(), TransitionPhase::PostHook);
        assert!(ex.advance()); assert_eq!(ex.phase(), TransitionPhase::Completed);
        assert!(!ex.advance()); // terminal
    }

    #[test]
    fn test_timeout_detection() {
        let mut ex = TransitionExecutor::new(PowerState::FullInference, PowerState::Sentinel, TransitionTrigger::InactivityTimeout, Duration::from_millis(1));
        std::thread::sleep(Duration::from_millis(5));
        assert!(ex.check_timeout());
        assert!(ex.has_timed_out());
    }

    #[test]
    fn test_no_timeout_when_completed() {
        let mut ex = TransitionExecutor::new(PowerState::FullInference, PowerState::Sentinel, TransitionTrigger::InactivityTimeout, Duration::from_millis(1));
        ex.advance(); ex.advance(); ex.advance(); ex.advance();
        assert!(!ex.check_timeout()); // completed doesn't timeout
    }

    #[test]
    fn test_rollback() {
        let mut ex = TransitionExecutor::new(PowerState::FullInference, PowerState::ThermalThrottle, TransitionTrigger::ThermalLimitExceeded { temperature_celsius: 90.0 }, Duration::from_secs(30));
        ex.rollback();
        assert_eq!(ex.phase(), TransitionPhase::RolledBack);
    }

    #[test]
    fn test_record() {
        let ex = TransitionExecutor::new(PowerState::Off, PowerState::DeepVaultSleep, TransitionTrigger::SystemBoot, Duration::from_secs(30));
        let record = ex.to_record();
        assert_eq!(record.from, PowerState::Off);
        assert_eq!(record.to, PowerState::DeepVaultSleep);
        assert!(!record.success); // not completed
    }
}
