//! # Model Registry
//!
//! Tracks all known models, their lifecycle state, requirements, and
//! capabilities. Parses TOML model manifests and enforces the model
//! state machine.
//!
//! ## Model State Machine
//!
//! ```text
//! Unknown -> Downloaded -> Loading -> Loaded -> Active -> Unloading -> Downloaded
//!                             |                              ^
//!                             +-- Error (rollback) ----------+
//! ```
//!
//! ## Responsibilities
//!
//! - Parse model manifests (TOML)
//! - Track model lifecycle state
//! - Version management and compatibility checking
//! - Air-gap aware update detection (USB packages, no network)
//! - VRAM budget tracking across loaded models
//! - Dependency resolution (model X requires adapter Y at version >= Z)

// Stub: implementation in Session 07
