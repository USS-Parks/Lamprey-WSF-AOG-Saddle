//! Auto-demotion timer with per-GPU-group tracking.
//!
//! Tracks idle time per GPU group and determines when auto-demotion
//! should fire. A GPU group is a set of GPUs that share a power state
//! (e.g., all GPUs on the same PCIe switch, or individual GPUs for
//! fine-grained control).

use std::collections::HashMap;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tracing::debug;

use super::{PowerState, TransitionTrigger};

/// Identifier for a GPU group that shares a power state.
pub type GpuGroupId = String;

/// Per-GPU-group demotion tracking.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuGroupDemotionConfig {
    /// Time before Full Inference demotes to Sentinel for this group.
    pub full_to_sentinel: Duration,
    /// Time before Sentinel demotes to Deep Vault Sleep for this group.
    pub sentinel_to_sleep: Duration,
}

impl Default for GpuGroupDemotionConfig {
    fn default() -> Self {
        Self {
            full_to_sentinel: Duration::from_secs(12 * 60),
            sentinel_to_sleep: Duration::from_secs(2 * 60 * 60),
        }
    }
}

/// Tracks auto-demotion state for multiple GPU groups.
///
/// Each GPU group has:
/// - Last activity time (reset when a request hits the scheduler for that group)
/// - Current power state for the group
///
/// The tracker can report which groups are due for demotion.
pub struct DemotionTracker {
    groups: HashMap<GpuGroupId, GpuGroupState>,
    default_config: GpuGroupDemotionConfig,
}

struct GpuGroupState {
    last_activity: Instant,
    current_state: PowerState,
    config: GpuGroupDemotionConfig,
}

impl DemotionTracker {
    /// Create a new empty tracker with the given default config.
    pub fn new(default_config: GpuGroupDemotionConfig) -> Self {
        Self {
            groups: HashMap::new(),
            default_config,
        }
    }

    /// Register a GPU group with its initial power state.
    pub fn register_group(&mut self, group_id: GpuGroupId, initial_state: PowerState) {
        self.groups.entry(group_id).or_insert_with(|| {
            let now = Instant::now();
            GpuGroupState {
                last_activity: now,
                current_state: initial_state,
                config: self.default_config.clone(),
            }
        });
    }

    /// Remove a GPU group.
    pub fn remove_group(&mut self, group_id: &str) {
        self.groups.remove(group_id);
    }

    /// Record activity on a GPU group (resets its demotion timer).
    pub fn record_activity(&mut self, group_id: &str) {
        if let Some(state) = self.groups.get_mut(group_id) {
            state.last_activity = Instant::now();
        }
    }

    /// Update the power state for a GPU group.
    pub fn update_state(&mut self, group_id: &str, new_state: PowerState) {
        if let Some(state) = self.groups.get_mut(group_id) {
            state.current_state = new_state;
            state.last_activity = Instant::now();
        }
    }

    /// Get the current power state for a GPU group.
    pub fn group_state(&self, group_id: &str) -> Option<PowerState> {
        self.groups.get(group_id).map(|s| s.current_state)
    }

    /// Get the idle duration for a GPU group.
    pub fn group_idle(&self, group_id: &str) -> Option<Duration> {
        self.groups.get(group_id).map(|s| s.last_activity.elapsed())
    }

    /// Check all groups and return those due for demotion.
    ///
    /// Returns a list of (group_id, trigger) pairs where demotion is due.
    pub fn check_all(&self) -> Vec<(String, TransitionTrigger)> {
        let mut due = Vec::new();
        for (group_id, state) in &self.groups {
            let idle = state.last_activity.elapsed();
            match state.current_state {
                PowerState::FullInference if idle >= state.config.full_to_sentinel => {
                    debug!(group = %group_id, idle_secs = idle.as_secs(), "Auto-demotion due: FullInference -> Sentinel");
                    due.push((group_id.clone(), TransitionTrigger::InactivityTimeout));
                }
                PowerState::Sentinel if idle >= state.config.sentinel_to_sleep => {
                    debug!(group = %group_id, idle_secs = idle.as_secs(), "Auto-demotion due: Sentinel -> DeepVaultSleep");
                    due.push((group_id.clone(), TransitionTrigger::ExtendedInactivity));
                }
                _ => {}
            }
        }
        due
    }

    /// Number of registered groups.
    pub fn group_count(&self) -> usize {
        self.groups.len()
    }

    /// Set a custom config for a specific group.
    pub fn set_group_config(&mut self, group_id: &str, config: GpuGroupDemotionConfig) {
        if let Some(state) = self.groups.get_mut(group_id) {
            state.config = config;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_check() {
        let mut tracker = DemotionTracker::new(GpuGroupDemotionConfig::default());
        tracker.register_group("gpu-0".to_string(), PowerState::FullInference);
        assert_eq!(tracker.group_count(), 1);
        // Immediately after registration, no demotion due
        assert!(tracker.check_all().is_empty());
    }

    #[test]
    fn test_activity_resets_timer() {
        let mut tracker = DemotionTracker::new(GpuGroupDemotionConfig {
            full_to_sentinel: Duration::from_millis(5),
            sentinel_to_sleep: Duration::from_secs(3600),
        });
        tracker.register_group("gpu-0".to_string(), PowerState::FullInference);
        std::thread::sleep(Duration::from_millis(10));
        // Demotion should be due
        let due = tracker.check_all();
        assert!(!due.is_empty(), "Expected demotion due after idle timeout");
        assert_eq!(due[0].1, TransitionTrigger::InactivityTimeout);

        // Record activity, timer resets
        tracker.record_activity("gpu-0");
        assert!(tracker.check_all().is_empty());
    }

    #[test]
    fn test_update_state_clears_demotion() {
        let mut tracker = DemotionTracker::new(GpuGroupDemotionConfig {
            full_to_sentinel: Duration::from_millis(5),
            sentinel_to_sleep: Duration::from_secs(3600),
        });
        tracker.register_group("gpu-0".to_string(), PowerState::FullInference);
        std::thread::sleep(Duration::from_millis(10));
        assert!(!tracker.check_all().is_empty());

        // Changing to Sentinel clears FullInference demotion check
        tracker.update_state("gpu-0", PowerState::Sentinel);
        // Now should be not due (Sentinel threshold is 3600s)
        assert!(tracker.check_all().is_empty());
    }

    #[test]
    fn test_multiple_groups_independent() {
        let mut tracker = DemotionTracker::new(GpuGroupDemotionConfig {
            full_to_sentinel: Duration::from_millis(5),
            sentinel_to_sleep: Duration::from_secs(3600),
        });
        tracker.register_group("gpu-0".to_string(), PowerState::FullInference);
        tracker.register_group("gpu-1".to_string(), PowerState::FullInference);
        std::thread::sleep(Duration::from_millis(10));
        // Record activity on gpu-1 *after* the wait, so its timer is fresh
        tracker.record_activity("gpu-1");
        let due = tracker.check_all();
        assert_eq!(due.len(), 1);
        assert_eq!(due[0].0, "gpu-0");
    }

    #[test]
    fn test_group_state_query() {
        let mut tracker = DemotionTracker::new(GpuGroupDemotionConfig::default());
        tracker.register_group("gpu-0".to_string(), PowerState::Sentinel);
        assert_eq!(tracker.group_state("gpu-0"), Some(PowerState::Sentinel));
        assert_eq!(tracker.group_state("unknown"), None);
    }
}
