//! PowerStateController: coordinates power state transitions with the scheduler.
//!
//! Owns a `PowerStateMachine` (pure state + transition logic) and a
//! `DemotionTracker` (per-GPU-group idle timers) from `mai-core`, and
//! bridges them with the `Scheduler` trait for instance-aware power
//! management.
//!
//! # Architecture
//!
//! ```text
//!   PowerStateController
//!     ├── state_machine: PowerStateMachine  (mai-core)
//!     ├── demotion_tracker: DemotionTracker (mai-core)
//!     └── scheduler: Arc<dyn Scheduler>     (this crate)
//! ```
//!
//! The controller owns the power state machine and demotion tracker, but
//! delegates instance-level operations (drain, wake, GPU query) to the
//! scheduler. This keeps the state machine pure and testable in mai-core
//! while the controller handles the orchestration.

use std::sync::Arc;
use std::sync::RwLock;

use mai_core::power::demotion::{DemotionTracker, GpuGroupDemotionConfig};
use mai_core::power::{
    PowerConfig, PowerError, PowerState, PowerStateMachine, TransitionRecord, TransitionResult,
    TransitionTrigger,
};
use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use crate::scheduler::Scheduler;
use crate::types::GpuId;

/// Configuration for the PowerStateController.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PowerControllerConfig {
    pub power_config: PowerConfig,
    pub demotion_config: GpuGroupDemotionConfig,
    /// Interval at which to check auto-demotion conditions.
    pub poll_interval_secs: u64,
}

impl Default for PowerControllerConfig {
    fn default() -> Self {
        Self {
            power_config: PowerConfig::default(),
            demotion_config: GpuGroupDemotionConfig::default(),
            poll_interval_secs: 30,
        }
    }
}

/// High-level power state controller that coordinates the power state machine,
/// demotion tracker, and scheduler for GPU-level power management.
pub struct PowerStateController {
    state_machine: RwLock<PowerStateMachine>,
    demotion_tracker: RwLock<DemotionTracker>,
    scheduler: Arc<dyn Scheduler>,
    _config: PowerControllerConfig,
}

impl PowerStateController {
    /// Create a new PowerStateController.
    pub fn new(config: PowerControllerConfig, scheduler: Arc<dyn Scheduler>) -> Self {
        let state_machine = PowerStateMachine::new(config.power_config.clone());
        let demotion_tracker =
            DemotionTracker::new(config.demotion_config.clone());

        info!("PowerStateController initialized");

        Self {
            state_machine: RwLock::new(state_machine),
            demotion_tracker: RwLock::new(demotion_tracker),
            scheduler,
            _config: config,
        }
    }

    /// Current system-wide power state.
    pub fn current_state(&self) -> PowerState {
        self.state_machine.read().unwrap().current_state()
    }

    /// The power config (timeouts, thermal thresholds, etc.).
    pub fn power_config(&self) -> PowerConfig {
        self.state_machine.read().unwrap().config().clone()
    }

    /// Estimated system-wide power draw in watts.
    pub fn estimated_power_draw(&self) -> u32 {
        self.state_machine.read().unwrap().estimated_power_draw()
    }

    /// Request a power state transition.
    ///
    /// Before executing sleep/demotion transitions, the controller checks
    /// that all instances are drainable via the scheduler. After wake/promotion
    /// transitions, it notifies the scheduler so instances are marked healthy.
    pub fn request_transition(
        &self,
        trigger: TransitionTrigger,
    ) -> Result<TransitionResult, PowerError> {
        let from_state = self.current_state();

        // Determine target state via the state machine's own resolution logic
        let resolved = self
            .state_machine
            .read()
            .unwrap()
            .resolve_target_state(&trigger);

        let target_state = resolved?;

        // Pre-transition: verify all instances can be drained for demotion
        if Self::is_demotion(from_state, target_state) {
            let affected_gpus: Vec<GpuId> = self.scheduler.all_gpu_set();
            for gpu in &affected_gpus {
                let instances = self.scheduler.instances_on_gpu(*gpu);
                for instance in &instances {
                    if !self.scheduler.can_demote(instance) {
                        warn!(
                            instance = %instance,
                            gpu = %gpu,
                            "Cannot demote: instance has active sequences"
                        );
                        return Err(PowerError::GuardFailed(format!(
                            "Instance {instance} has active sequences, cannot demote GPU {gpu}"
                        )));
                    }
                }
            }
            info!(
                from = %from_state.as_str(),
                to = %target_state.as_str(),
                gpu_count = affected_gpus.len(),
                "All instances drainable, proceeding with demotion"
            );
        }

        // Execute the transition on the state machine
        let result = self
            .state_machine
            .write()
            .unwrap()
            .request_transition(trigger)?;

        // Post-transition: notify scheduler for wake/promotion
        if Self::is_promotion(from_state, target_state) {
            let affected_gpus: Vec<GpuId> = self.scheduler.all_gpu_set();
            for gpu in affected_gpus {
                if let Err(e) = self.scheduler.on_wake_gpu(gpu) {
                    warn!(gpu = %gpu, error = %e, "GPU wake notification failed");
                }
            }
            info!(
                from = %from_state.as_str(),
                to = %target_state.as_str(),
                "GPU wake notifications sent"
            );
        }

        Ok(result)
    }

    /// Handle a thermal event. If the temperature exceeds the throttle
    /// threshold or drops below recovery, triggers the appropriate transition.
    pub fn handle_thermal_event(
        &self,
        temperature_celsius: f32,
    ) -> Result<Option<TransitionResult>, PowerError> {
        self.state_machine
            .write()
            .unwrap()
            .handle_thermal_event(temperature_celsius)
    }

    /// Register a GPU group for per-group demotion tracking.
    pub fn register_gpu_group(&self, group_id: String, initial_state: PowerState) {
        self.demotion_tracker
            .write()
            .unwrap()
            .register_group(group_id, initial_state);
    }

    /// Record activity on a GPU group, resetting its demotion timer.
    pub fn record_gpu_activity(&self, group_id: &str) {
        self.demotion_tracker
            .write()
            .unwrap()
            .record_activity(group_id);
    }

    /// Update the power state for a GPU group.
    pub fn update_gpu_group_state(&self, group_id: &str, new_state: PowerState) {
        self.demotion_tracker
            .write()
            .unwrap()
            .update_state(group_id, new_state);
    }

    /// Check both the system-wide auto-demotion and per-group timers.
    /// Returns triggers that are due for demotion.
    pub fn check_auto_demotions(&self) -> Vec<(String, TransitionTrigger)> {
        let mut results = Vec::new();

        // System-wide auto-demotion
        if let Some(trigger) = self.state_machine.read().unwrap().check_auto_demotion() {
            results.push(("system".to_string(), trigger));
        }

        // Per-group demotion
        results.extend(self.demotion_tracker.read().unwrap().check_all());

        results
    }

    /// Reset the system-wide demotion timer (called on any activity).
    pub fn reset_demotion_timer(&self) {
        self.state_machine.write().unwrap().reset_demotion_timer();
    }

    /// Access the transition log for auditing.
    pub fn transition_log(&self) -> Vec<TransitionRecord> {
        self.state_machine
            .read()
            .unwrap()
            .transition_log()
            .to_vec()
    }

    /// Number of registered GPU groups.
    pub fn gpu_group_count(&self) -> usize {
        self.demotion_tracker.read().unwrap().group_count()
    }

    /// Whether the system-wide state machine thinks it should promote
    /// from Sentinel to FullInference based on expected workload.
    pub fn should_promote_to_full(&self, estimated_tokens: u32, is_complex: bool) -> bool {
        self.state_machine
            .read()
            .unwrap()
            .should_promote_to_full(estimated_tokens, is_complex)
    }

    fn is_demotion(from: PowerState, to: PowerState) -> bool {
        matches!(
            (from, to),
            (PowerState::FullInference, PowerState::Sentinel)
                | (PowerState::FullInference, PowerState::ThermalThrottle)
                | (PowerState::Sentinel, PowerState::DeepVaultSleep)
                | (_, PowerState::Off)
        )
    }

    fn is_promotion(from: PowerState, to: PowerState) -> bool {
        matches!(
            (from, to),
            (PowerState::DeepVaultSleep, PowerState::Sentinel)
                | (PowerState::DeepVaultSleep, PowerState::FullInference)
                | (PowerState::Sentinel, PowerState::FullInference)
                | (PowerState::ThermalThrottle, PowerState::FullInference)
                | (PowerState::Off, PowerState::DeepVaultSleep)
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::default::DefaultScheduler;
    use crate::types::{InstanceCapabilities, InstanceConfig, InstanceId, Priority, ScheduleRequest, SchedulerConfig};

    fn make_scheduler() -> Arc<dyn Scheduler> {
        let config = SchedulerConfig::default();
        Arc::new(DefaultScheduler::new(config))
    }

    fn make_controller(scheduler: Arc<dyn Scheduler>) -> PowerStateController {
        PowerStateController::new(PowerControllerConfig::default(), scheduler)
    }

    fn register_instance(sched: &Arc<dyn Scheduler>, id: &str, model: &str, gpu: u32) {
        let config = InstanceConfig {
            id: InstanceId::new(id),
            model_name: model.to_string(),
            adapter_type: "test".to_string(),
            gpu_ids: vec![GpuId::new(gpu)],
            max_batch_size: 4,
            vram_allocated: 1_000_000,
            capabilities: InstanceCapabilities::default(),
        };
        sched.register_instance(config).unwrap();
    }

    #[test]
    fn test_initial_state_off() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        assert_eq!(ctrl.current_state(), PowerState::Off);
    }

    #[test]
    fn test_boot_transition() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        let result = ctrl.request_transition(TransitionTrigger::SystemBoot);
        assert!(result.is_ok());
        assert_eq!(ctrl.current_state(), PowerState::DeepVaultSleep);
    }

    #[test]
    fn test_wake_to_sentinel() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        ctrl.request_transition(TransitionTrigger::SystemBoot).unwrap();
        let result = ctrl.request_transition(TransitionTrigger::WakeTrigger(
            mai_core::power::WakeSource::ApiRequest,
        ));
        assert!(result.is_ok());
        assert_eq!(ctrl.current_state(), PowerState::Sentinel);
    }

    #[test]
    fn test_demotion_blocks_busy_instance() {
        let sched = make_scheduler();
        register_instance(&sched, "test:0", "model-a", 0);
        let ctrl = make_controller(sched.clone());

        // Boot and promote to FullInference
        ctrl.request_transition(TransitionTrigger::SystemBoot).unwrap();
        ctrl.request_transition(TransitionTrigger::UrgentWake(
            mai_core::power::WakeSource::Manual,
        ))
        .unwrap();
        assert_eq!(ctrl.current_state(), PowerState::FullInference);

        // Start a request on the instance (simulate active work)
        let req = ScheduleRequest::new("model-a", Priority::Normal);
        sched.schedule(&req).unwrap();

        // Attempt demotion should fail because instance has active sequences
        let result = ctrl.request_transition(TransitionTrigger::InactivityTimeout);
        assert!(result.is_err());
    }

    #[test]
    fn test_demotion_succeeds_when_idle() {
        let sched = make_scheduler();
        register_instance(&sched, "test:0", "model-a", 0);
        let ctrl = make_controller(sched);

        ctrl.request_transition(TransitionTrigger::SystemBoot).unwrap();
        ctrl.request_transition(TransitionTrigger::UrgentWake(
            mai_core::power::WakeSource::Manual,
        ))
        .unwrap();

        // Instance is idle (no active sequences), demotion should succeed
        let result = ctrl.request_transition(TransitionTrigger::InactivityTimeout);
        assert!(result.is_ok());
        assert_eq!(ctrl.current_state(), PowerState::Sentinel);
    }

    #[test]
    fn test_thermal_throttle() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        ctrl.request_transition(TransitionTrigger::SystemBoot).unwrap();
        ctrl.request_transition(TransitionTrigger::UrgentWake(
            mai_core::power::WakeSource::Manual,
        ))
        .unwrap();
        assert_eq!(ctrl.current_state(), PowerState::FullInference);

        let result = ctrl.handle_thermal_event(85.0).unwrap();
        assert!(result.is_some());
        assert_eq!(ctrl.current_state(), PowerState::ThermalThrottle);
    }

    #[test]
    fn test_gpu_group_tracking() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);

        ctrl.register_gpu_group("gpu-0".to_string(), PowerState::FullInference);
        ctrl.register_gpu_group("gpu-1".to_string(), PowerState::Sentinel);
        assert_eq!(ctrl.gpu_group_count(), 2);
    }

    #[test]
    fn test_check_auto_demotions() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        // No demotions due immediately
        assert!(ctrl.check_auto_demotions().is_empty());
    }

    #[test]
    fn test_promotion_notifies_scheduler() {
        let sched = make_scheduler();
        register_instance(&sched, "test:0", "model-a", 0);
        let ctrl = make_controller(sched.clone());

        ctrl.request_transition(TransitionTrigger::SystemBoot).unwrap();
        // Before promotion, verify GPU set includes GPU 0
        let gpus = sched.all_gpu_set();
        assert!(!gpus.is_empty());

        // Promote to Sentinel (wake notification sent to scheduler)
        let result = ctrl.request_transition(TransitionTrigger::WakeTrigger(
            mai_core::power::WakeSource::ApiRequest,
        ));
        assert!(result.is_ok());
        assert_eq!(ctrl.current_state(), PowerState::Sentinel);
    }

    #[test]
    fn test_transition_log_accessible() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        ctrl.request_transition(TransitionTrigger::SystemBoot).unwrap();
        let log = ctrl.transition_log();
        assert_eq!(log.len(), 1);
    }

    #[test]
    fn test_power_draw_estimate() {
        let sched = make_scheduler();
        let ctrl = make_controller(sched);
        assert_eq!(ctrl.estimated_power_draw(), 0); // Off state
    }
}
