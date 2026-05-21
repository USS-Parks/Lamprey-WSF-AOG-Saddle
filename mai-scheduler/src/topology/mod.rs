//! GPU Topology Discovery + Weighted Graph
//!
//! This module discovers and models the GPU interconnect topology of the
//! local system. It parses nvidia-smi output to build a weighted graph
//! where nodes are GPUs and edges represent interconnect links (NVLink,
//! PCIe, CPU bridge, cross-socket). The graph enables hardware-aware
//! placement decisions: tensor-parallel workloads prefer GPUs connected
//! by high-bandwidth NVLink, while KV cache migration costs are estimated
//! from edge weights.
//!
//! # Module Structure
//!
//! - `collector`: parses nvidia-smi topo -m output and adapter handshake data
//! - `graph`: weighted graph representation with link normalization
//! - `analysis`: precomputed structures (best pairs, clusters, path costs)
//! - `refresh`: periodic live metrics refresh loop
//!
//! # Usage
//!
//! ```ignore
//! let config = TopologyConfig::load("config/topology.toml")?;
//! let topo = GpuTopology::discover(&config)?;
//! let penalty = topo.topology_penalty(&[GpuId(0), GpuId(1)]);
//! ```

pub mod analysis;
pub mod collector;
pub mod graph;
pub mod refresh;

use std::sync::Arc;

use analysis::PrecomputedTopology;
use graph::GpuGraph;
use refresh::MetricsRefresher;

use crate::types::GpuId;

/// Top-level topology handle. Wraps the static graph and precomputed
/// analysis structures. Shared via `Arc<GpuTopology>` across the scheduler.
pub struct GpuTopology {
    /// The weighted interconnect graph.
    graph: GpuGraph,
    /// Precomputed analysis (best pairs, clusters, path cost matrix).
    analysis: PrecomputedTopology,
    /// Configuration used to build this topology.
    config: TopologyConfig,
}

impl GpuTopology {
    /// Build a topology from a parsed graph and configuration.
    pub fn from_graph(graph: GpuGraph, config: TopologyConfig) -> Self {
        let analysis = PrecomputedTopology::compute(&graph, &config);
        Self {
            graph,
            analysis,
            config,
        }
    }

    /// Discover topology by running nvidia-smi and parsing its output.
    /// Falls back to flat topology if nvidia-smi is unavailable.
    pub fn discover(config: &TopologyConfig) -> Result<Self, TopologyError> {
        let raw = if let Some(ref manual) = config.manual_topology {
            manual.clone()
        } else {
            match collector::collect_nvidia_smi() {
                Ok(output) => output,
                Err(_) => {
                    tracing::warn!("nvidia-smi unavailable, using flat topology");
                    return Ok(Self::flat(config));
                }
            }
        };

        let parsed = collector::parse_topo_matrix(&raw)?;
        let graph = GpuGraph::from_parsed(
            parsed,
            &config.link_weights,
            config.latency_weight,
            config.bw_weight,
        );
        Ok(Self::from_graph(graph, config.clone()))
    }

    /// Create a flat (single-GPU or all-PCIe) topology fallback.
    pub fn flat(config: &TopologyConfig) -> Self {
        let graph = GpuGraph::single_gpu();
        Self::from_graph(graph, config.clone())
    }

    /// Compute a topology penalty for a set of GPUs. Higher penalty means
    /// worse interconnect quality for tensor-parallel workloads.
    ///
    /// The penalty is the maximum edge cost among all pairs of assigned GPUs.
    /// A single-GPU assignment returns 0.0.
    pub fn topology_penalty(&self, gpu_ids: &[GpuId]) -> f64 {
        if gpu_ids.len() <= 1 {
            return 0.0;
        }
        self.analysis.worst_pair_cost(gpu_ids)
    }

    /// Get the best GPU pairs for 2-way tensor parallelism.
    pub fn best_pairs(&self) -> &[(GpuId, GpuId, f64)] {
        &self.analysis.best_pairs
    }

    /// Get the best GPU quads for 4-way tensor parallelism.
    pub fn best_quads(&self) -> &[([GpuId; 4], f64)] {
        &self.analysis.best_quads
    }

    /// Get NVLink cliques (groups of GPUs all connected by NVLink).
    pub fn nvlink_cliques(&self) -> &[Vec<GpuId>] {
        &self.analysis.nvlink_cliques
    }

    /// Get the path cost between two GPUs from the precomputed matrix.
    pub fn path_cost(&self, a: GpuId, b: GpuId) -> f64 {
        self.analysis.path_cost(a, b)
    }

    /// Get CPU affinity groups (GPUs sharing the same NUMA node).
    pub fn cpu_affinity_groups(&self) -> &[Vec<GpuId>] {
        &self.analysis.cpu_affinity_groups
    }

    /// Access the underlying graph.
    pub fn graph(&self) -> &GpuGraph {
        &self.graph
    }

    /// Number of GPUs in the topology.
    pub fn gpu_count(&self) -> usize {
        self.graph.node_count()
    }

    /// Create a metrics refresher that periodically updates live GPU metrics.
    pub fn create_refresher(self: &Arc<Self>) -> MetricsRefresher {
        MetricsRefresher::new(
            Arc::clone(self) as Arc<GpuTopology>,
            self.config.refresh_interval_ms,
        )
    }
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// Topology configuration, loaded from config/topology.toml.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TopologyConfig {
    /// Weight for latency in edge cost calculation (default 1.0).
    #[serde(default = "default_latency_weight")]
    pub latency_weight: f64,
    /// Weight for bandwidth in edge cost calculation (default 1.0).
    #[serde(default = "default_bw_weight")]
    pub bw_weight: f64,
    /// Metrics refresh interval in milliseconds (default 500).
    #[serde(default = "default_refresh_interval")]
    pub refresh_interval_ms: u64,
    /// VRAM usage threshold (fraction 0.0-1.0) for anomaly flagging.
    #[serde(default = "default_vram_threshold")]
    pub vram_anomaly_threshold: f64,
    /// Utilization threshold for "stuck at 100%" anomaly (seconds).
    #[serde(default = "default_util_stuck_seconds")]
    pub utilization_stuck_seconds: u64,
    /// Thermal throttle temperature in Celsius for anomaly flag.
    #[serde(default = "default_thermal_throttle_c")]
    pub thermal_throttle_celsius: u32,
    /// Manual topology specification for environments where nvidia-smi
    /// is unavailable (dev machines, CI). If set, overrides nvidia-smi.
    #[serde(default)]
    pub manual_topology: Option<String>,
    /// Link cost weight overrides per link type.
    #[serde(default)]
    pub link_weights: LinkWeightConfig,
}

/// Per-link-type weight overrides for edge cost calculation.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LinkWeightConfig {
    /// Bandwidth for NV4 links in GB/s (default 900).
    #[serde(default = "default_nv4_bw")]
    pub nv4_bandwidth_gbps: f64,
    /// Bandwidth for NV2 links in GB/s (default 600).
    #[serde(default = "default_nv2_bw")]
    pub nv2_bandwidth_gbps: f64,
    /// Bandwidth for NV1 links in GB/s (default 300).
    #[serde(default = "default_nv1_bw")]
    pub nv1_bandwidth_gbps: f64,
    /// Bandwidth for PXB links in GB/s (default 64).
    #[serde(default = "default_pxb_bw")]
    pub pxb_bandwidth_gbps: f64,
    /// Bandwidth for PHB links in GB/s (default 32).
    #[serde(default = "default_phb_bw")]
    pub phb_bandwidth_gbps: f64,
    /// Bandwidth for SYS links in GB/s (default 16).
    #[serde(default = "default_sys_bw")]
    pub sys_bandwidth_gbps: f64,
}

impl Default for LinkWeightConfig {
    fn default() -> Self {
        Self {
            nv4_bandwidth_gbps: default_nv4_bw(),
            nv2_bandwidth_gbps: default_nv2_bw(),
            nv1_bandwidth_gbps: default_nv1_bw(),
            pxb_bandwidth_gbps: default_pxb_bw(),
            phb_bandwidth_gbps: default_phb_bw(),
            sys_bandwidth_gbps: default_sys_bw(),
        }
    }
}

impl Default for TopologyConfig {
    fn default() -> Self {
        Self {
            latency_weight: default_latency_weight(),
            bw_weight: default_bw_weight(),
            refresh_interval_ms: default_refresh_interval(),
            vram_anomaly_threshold: default_vram_threshold(),
            utilization_stuck_seconds: default_util_stuck_seconds(),
            thermal_throttle_celsius: default_thermal_throttle_c(),
            manual_topology: None,
            link_weights: LinkWeightConfig::default(),
        }
    }
}

fn default_latency_weight() -> f64 {
    1.0
}
fn default_bw_weight() -> f64 {
    1.0
}
fn default_refresh_interval() -> u64 {
    500
}
fn default_vram_threshold() -> f64 {
    0.9
}
fn default_util_stuck_seconds() -> u64 {
    60
}
fn default_thermal_throttle_c() -> u32 {
    83
}
fn default_nv4_bw() -> f64 {
    900.0
}
fn default_nv2_bw() -> f64 {
    600.0
}
fn default_nv1_bw() -> f64 {
    300.0
}
fn default_pxb_bw() -> f64 {
    64.0
}
fn default_phb_bw() -> f64 {
    32.0
}
fn default_sys_bw() -> f64 {
    16.0
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/// Topology-specific errors.
#[derive(Debug, thiserror::Error)]
pub enum TopologyError {
    /// nvidia-smi execution failed.
    #[error("nvidia-smi failed: {0}")]
    NvidiaSmiError(String),

    /// Failed to parse nvidia-smi topo output.
    #[error("topology parse error: {0}")]
    ParseError(String),

    /// Configuration error.
    #[error("topology config error: {0}")]
    ConfigError(String),

    /// I/O error.
    #[error("topology I/O error: {0}")]
    IoError(#[from] std::io::Error),
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = TopologyConfig::default();
        assert!((config.latency_weight - 1.0).abs() < f64::EPSILON);
        assert!((config.bw_weight - 1.0).abs() < f64::EPSILON);
        assert_eq!(config.refresh_interval_ms, 500);
        assert_eq!(config.thermal_throttle_celsius, 83);
        assert!(config.manual_topology.is_none());
    }

    #[test]
    fn test_flat_topology() {
        let config = TopologyConfig::default();
        let topo = GpuTopology::flat(&config);
        assert_eq!(topo.gpu_count(), 1);
        assert_eq!(topo.topology_penalty(&[GpuId(0)]), 0.0);
    }

    #[test]
    fn test_single_gpu_penalty_zero() {
        let config = TopologyConfig::default();
        let topo = GpuTopology::flat(&config);
        assert_eq!(topo.topology_penalty(&[]), 0.0);
        assert_eq!(topo.topology_penalty(&[GpuId(0)]), 0.0);
    }
}
