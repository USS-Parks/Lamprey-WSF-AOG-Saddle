//! Weighted GPU interconnect graph.
//!
//! Nodes are GPUs, edges are interconnect links with bandwidth and latency
//! scores. Edge weight is a composite cost: higher cost = worse for
//! tensor-parallel workloads. The graph is constructed once from nvidia-smi
//! data and is immutable; only node metrics (VRAM, utilization, thermal)
//! are updated at runtime.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use super::LinkWeightConfig;
use super::collector::{LinkType, ParsedTopology};
use crate::types::GpuId;

// ---------------------------------------------------------------------------
// Graph types
// ---------------------------------------------------------------------------

/// Per-GPU node in the topology graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuNode {
    /// GPU ordinal.
    pub gpu_id: GpuId,
    /// Total VRAM in bytes (0 until first metrics refresh).
    pub total_vram: u64,
    /// Free VRAM in bytes (updated by refresh loop).
    pub free_vram: u64,
    /// GPU utilization 0-100 (updated by refresh loop).
    pub utilization: u32,
    /// Thermal state in Celsius (updated by refresh loop).
    pub temperature_celsius: u32,
    /// PCIe generation (3/4/5), if known.
    pub pcie_gen: Option<u32>,
    /// PCIe width (8/16), if known.
    pub pcie_width: Option<u32>,
    /// NUMA node ID (from CPU affinity parsing).
    pub numa_node: Option<u32>,
}

impl GpuNode {
    /// Create a new node with default (unknown) metrics.
    pub fn new(gpu_id: GpuId) -> Self {
        Self {
            gpu_id,
            total_vram: 0,
            free_vram: 0,
            utilization: 0,
            temperature_celsius: 0,
            pcie_gen: None,
            pcie_width: None,
            numa_node: None,
        }
    }

    /// Create a node with known NUMA affinity.
    pub fn with_numa(gpu_id: GpuId, numa_node: u32) -> Self {
        let mut node = Self::new(gpu_id);
        node.numa_node = Some(numa_node);
        node
    }
}

/// An edge in the topology graph: a link between two GPUs.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuLink {
    /// Link type (NV4, NV2, NV1, PXB, PHB, SYS).
    pub link_type: LinkType,
    /// Bandwidth in GB/s (from link type normalization table).
    pub bandwidth_gbps: f64,
    /// Latency score (unitless, lower = better).
    pub latency_score: u32,
    /// Composite edge cost: higher = worse for co-placement.
    pub cost: f64,
}

// ---------------------------------------------------------------------------
// GpuGraph
// ---------------------------------------------------------------------------

/// The weighted GPU interconnect graph.
///
/// Nodes are GPUs, edges are interconnect links. The graph is directed
/// (each nvidia-smi link is stored as two directed edges A->B and B->A)
/// but in practice the links are symmetric.
pub struct GpuGraph {
    /// GPU nodes indexed by GpuId.
    nodes: HashMap<GpuId, GpuNode>,
    /// Directed edges indexed by (from, to).
    edges: HashMap<(GpuId, GpuId), GpuLink>,
}

impl GpuGraph {
    /// Create an empty graph.
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            edges: HashMap::new(),
        }
    }

    /// Create a degenerate single-GPU graph (flat topology fallback).
    pub fn single_gpu() -> Self {
        let mut nodes = HashMap::new();
        nodes.insert(GpuId(0), GpuNode::new(GpuId(0)));
        Self {
            nodes,
            edges: HashMap::new(),
        }
    }

    /// Build a graph from parsed nvidia-smi topology data.
    ///
    /// `latency_weight` and `bw_weight` are the global cost weights from
    /// `TopologyConfig` that control the relative importance of latency vs
    /// bandwidth in edge cost computation.
    pub fn from_parsed(
        parsed: &ParsedTopology,
        weights: &LinkWeightConfig,
        latency_weight: f64,
        bw_weight: f64,
    ) -> Self {
        let mut nodes = HashMap::new();
        let mut edges = HashMap::new();

        for gpu in &parsed.gpus {
            let numa = parsed.cpu_affinity.get(&gpu.gpu_id).copied();
            let mut node = GpuNode::new(gpu.gpu_id);
            node.numa_node = numa;
            nodes.insert(gpu.gpu_id, node);
        }

        for link in &parsed.links {
            let bandwidth = link_bandwidth(link.link_type, weights);
            let latency = link.link_type.latency_score();
            let cost = compute_edge_cost(latency, bandwidth, latency_weight, bw_weight);

            edges.insert(
                (link.from, link.to),
                GpuLink {
                    link_type: link.link_type,
                    bandwidth_gbps: bandwidth,
                    latency_score: latency,
                    cost,
                },
            );
        }

        Self { nodes, edges }
    }

    /// Number of GPU nodes.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Number of directed edges.
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    /// Get a node by GPU ID.
    pub fn node(&self, id: GpuId) -> Option<&GpuNode> {
        self.nodes.get(&id)
    }

    /// Get a mutable node by GPU ID (for metrics refresh).
    pub fn node_mut(&mut self, id: GpuId) -> Option<&mut GpuNode> {
        self.nodes.get_mut(&id)
    }

    /// Get an edge between two GPUs.
    pub fn edge(&self, from: GpuId, to: GpuId) -> Option<&GpuLink> {
        self.edges.get(&(from, to))
    }

    /// Get the cost of the link between two GPUs, or f64::INFINITY if
    /// no direct link exists.
    pub fn link_cost(&self, from: GpuId, to: GpuId) -> f64 {
        self.edges
            .get(&(from, to))
            .map_or(f64::INFINITY, |link| link.cost)
    }

    /// Get all GPU IDs in the graph.
    pub fn gpu_ids(&self) -> Vec<GpuId> {
        let mut ids: Vec<GpuId> = self.nodes.keys().copied().collect();
        ids.sort_by_key(|id| id.0);
        ids
    }

    /// Get all nodes.
    pub fn nodes(&self) -> &HashMap<GpuId, GpuNode> {
        &self.nodes
    }

    /// Get all edges.
    pub fn edges(&self) -> &HashMap<(GpuId, GpuId), GpuLink> {
        &self.edges
    }

    /// Check if a link between two GPUs is NVLink.
    pub fn is_nvlink(&self, from: GpuId, to: GpuId) -> bool {
        self.edges
            .get(&(from, to))
            .is_some_and(|link| link.link_type.is_nvlink())
    }
}

impl Default for GpuGraph {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Cost computation
// ---------------------------------------------------------------------------

/// Map a link type to its bandwidth in GB/s using the config.
fn link_bandwidth(link_type: LinkType, weights: &LinkWeightConfig) -> f64 {
    match link_type {
        LinkType::NV4 => weights.nv4_bandwidth_gbps,
        LinkType::NV2 => weights.nv2_bandwidth_gbps,
        LinkType::NV1 => weights.nv1_bandwidth_gbps,
        LinkType::PXB => weights.pxb_bandwidth_gbps,
        LinkType::PHB => weights.phb_bandwidth_gbps,
        LinkType::SYS => weights.sys_bandwidth_gbps,
        LinkType::SelfLink => f64::INFINITY,
    }
}

/// Compute edge cost from latency and bandwidth.
///
/// `cost = latency_score * latency_weight + (1.0 / bandwidth_gbps) * bw_weight`
///
/// Lower cost = better link.
fn compute_edge_cost(
    latency_score: u32,
    bandwidth_gbps: f64,
    latency_weight: f64,
    bw_weight: f64,
) -> f64 {
    let latency_term = f64::from(latency_score) * latency_weight;
    let bw_term = if bandwidth_gbps > 0.0 {
        (1.0 / bandwidth_gbps) * bw_weight
    } else {
        f64::INFINITY
    };
    latency_term + bw_term
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::topology::collector::{ParsedGpu, ParsedLink};

    fn default_weights() -> LinkWeightConfig {
        LinkWeightConfig::default()
    }

    fn make_two_gpu_nvlink() -> ParsedTopology {
        ParsedTopology {
            gpus: vec![
                ParsedGpu {
                    gpu_id: GpuId(0),
                    name: "GPU0".to_string(),
                    cpu_affinity: Some(0),
                },
                ParsedGpu {
                    gpu_id: GpuId(1),
                    name: "GPU1".to_string(),
                    cpu_affinity: Some(0),
                },
            ],
            links: vec![
                ParsedLink {
                    from: GpuId(0),
                    to: GpuId(1),
                    link_type: LinkType::NV4,
                },
                ParsedLink {
                    from: GpuId(1),
                    to: GpuId(0),
                    link_type: LinkType::NV4,
                },
            ],
            cpu_affinity: [(GpuId(0), 0), (GpuId(1), 0)].into_iter().collect(),
        }
    }

    fn make_four_gpu_mixed() -> ParsedTopology {
        ParsedTopology {
            gpus: vec![
                ParsedGpu {
                    gpu_id: GpuId(0),
                    name: "GPU0".to_string(),
                    cpu_affinity: Some(0),
                },
                ParsedGpu {
                    gpu_id: GpuId(1),
                    name: "GPU1".to_string(),
                    cpu_affinity: Some(0),
                },
                ParsedGpu {
                    gpu_id: GpuId(2),
                    name: "GPU2".to_string(),
                    cpu_affinity: Some(32),
                },
                ParsedGpu {
                    gpu_id: GpuId(3),
                    name: "GPU3".to_string(),
                    cpu_affinity: Some(32),
                },
            ],
            links: vec![
                ParsedLink {
                    from: GpuId(0),
                    to: GpuId(1),
                    link_type: LinkType::NV4,
                },
                ParsedLink {
                    from: GpuId(1),
                    to: GpuId(0),
                    link_type: LinkType::NV4,
                },
                ParsedLink {
                    from: GpuId(0),
                    to: GpuId(2),
                    link_type: LinkType::PHB,
                },
                ParsedLink {
                    from: GpuId(2),
                    to: GpuId(0),
                    link_type: LinkType::PHB,
                },
                ParsedLink {
                    from: GpuId(0),
                    to: GpuId(3),
                    link_type: LinkType::SYS,
                },
                ParsedLink {
                    from: GpuId(3),
                    to: GpuId(0),
                    link_type: LinkType::SYS,
                },
                ParsedLink {
                    from: GpuId(1),
                    to: GpuId(2),
                    link_type: LinkType::SYS,
                },
                ParsedLink {
                    from: GpuId(2),
                    to: GpuId(1),
                    link_type: LinkType::SYS,
                },
                ParsedLink {
                    from: GpuId(1),
                    to: GpuId(3),
                    link_type: LinkType::PHB,
                },
                ParsedLink {
                    from: GpuId(3),
                    to: GpuId(1),
                    link_type: LinkType::PHB,
                },
                ParsedLink {
                    from: GpuId(2),
                    to: GpuId(3),
                    link_type: LinkType::NV4,
                },
                ParsedLink {
                    from: GpuId(3),
                    to: GpuId(2),
                    link_type: LinkType::NV4,
                },
            ],
            cpu_affinity: [(GpuId(0), 0), (GpuId(1), 0), (GpuId(2), 32), (GpuId(3), 32)]
                .into_iter()
                .collect(),
        }
    }

    #[test]
    fn test_single_gpu_graph() {
        let graph = GpuGraph::single_gpu();
        assert_eq!(graph.node_count(), 1);
        assert_eq!(graph.edge_count(), 0);
        assert!(graph.node(GpuId(0)).is_some());
    }

    #[test]
    fn test_two_gpu_nvlink_graph() {
        let parsed = make_two_gpu_nvlink();
        let graph = GpuGraph::from_parsed(&parsed, &default_weights(), 1.0, 1.0);

        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.edge_count(), 2);
        assert!(graph.is_nvlink(GpuId(0), GpuId(1)));
        assert!(graph.is_nvlink(GpuId(1), GpuId(0)));
    }

    #[test]
    fn test_nvlink_cost_lower_than_pcie() {
        let parsed = make_four_gpu_mixed();
        let graph = GpuGraph::from_parsed(&parsed, &default_weights(), 1.0, 1.0);

        let nv4_cost = graph.link_cost(GpuId(0), GpuId(1)); // NV4
        let phb_cost = graph.link_cost(GpuId(0), GpuId(2)); // PHB
        let sys_cost = graph.link_cost(GpuId(0), GpuId(3)); // SYS

        assert!(
            nv4_cost < phb_cost,
            "NV4 ({nv4_cost}) should be cheaper than PHB ({phb_cost})"
        );
        assert!(
            phb_cost < sys_cost,
            "PHB ({phb_cost}) should be cheaper than SYS ({sys_cost})"
        );
    }

    #[test]
    fn test_edge_cost_formula() {
        // NV4: latency 1, bandwidth 900
        let cost = compute_edge_cost(1, 900.0, 1.0, 1.0);
        // Expected: 1.0 * 1.0 + (1.0 / 900.0) * 1.0 = 1.001111...
        assert!((cost - 1.001_111_111_111_111).abs() < 0.001);

        // SYS: latency 8, bandwidth 16
        let cost_sys = compute_edge_cost(8, 16.0, 1.0, 1.0);
        // Expected: 8.0 + 1/16 = 8.0625
        assert!((cost_sys - 8.0625).abs() < 0.001);

        assert!(cost < cost_sys);
    }

    #[test]
    fn test_no_direct_link_returns_infinity() {
        let graph = GpuGraph::single_gpu();
        assert_eq!(graph.link_cost(GpuId(0), GpuId(1)), f64::INFINITY);
    }

    #[test]
    fn test_numa_affinity_preserved() {
        let parsed = make_four_gpu_mixed();
        let graph = GpuGraph::from_parsed(&parsed, &default_weights(), 1.0, 1.0);

        assert_eq!(graph.node(GpuId(0)).unwrap().numa_node, Some(0));
        assert_eq!(graph.node(GpuId(2)).unwrap().numa_node, Some(32));
    }

    #[test]
    fn test_gpu_ids_sorted() {
        let parsed = make_four_gpu_mixed();
        let graph = GpuGraph::from_parsed(&parsed, &default_weights(), 1.0, 1.0);
        let ids = graph.gpu_ids();
        assert_eq!(ids, vec![GpuId(0), GpuId(1), GpuId(2), GpuId(3)]);
    }

    #[test]
    fn test_node_mut_metrics_update() {
        let mut graph = GpuGraph::single_gpu();
        let node = graph.node_mut(GpuId(0)).unwrap();
        node.free_vram = 40_000_000_000;
        node.utilization = 50;
        node.temperature_celsius = 72;

        let node = graph.node(GpuId(0)).unwrap();
        assert_eq!(node.free_vram, 40_000_000_000);
        assert_eq!(node.utilization, 50);
        assert_eq!(node.temperature_celsius, 72);
    }
}
