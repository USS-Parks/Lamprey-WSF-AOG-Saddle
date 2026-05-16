//! HIL trait definitions.
//!
//! These traits define the complete hardware interface. No code outside
//! of `mai-hil` can access hardware. The Rust type system enforces this
//! at compile time.

pub mod hardware_probe;
pub mod memory_manager;
pub mod power_state;
pub mod secure_load;
