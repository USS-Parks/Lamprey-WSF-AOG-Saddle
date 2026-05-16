//! Hardware driver implementations.
//!
//! Each driver implements the four HIL traits for a specific hardware target.
//! Driver code is the ONLY location where `unsafe` is permitted in the MAI.

pub mod amd;
pub mod cpu;
pub mod nvidia;
pub mod tetramem_stub;
