//! Topology data collection from nvidia-smi and adapter handshakes.
//!
//! Primary source: `nvidia-smi topo -m` output, which produces a matrix
//! of GPU-to-GPU link types (NV1, NV2, NV4, PXB, PHB, SYS) plus CPU
//! affinity per GPU.
//!
//! Fallback: if nvidia-smi is unavailable, the caller constructs a flat
//! topology (all PCIe) via `GpuGraph::single_gpu()`.

use std::collections::HashMap;
use std::process::Command;

use super::TopologyError;
use crate::types::GpuId;

// ---------------------------------------------------------------------------
// Link types parsed from nvidia-smi
// ---------------------------------------------------------------------------

/// GPU interconnect link type as reported by nvidia-smi topo -m.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
pub enum LinkType {
    /// NVLink x4 (highest bandwidth, ~900 GB/s).
    NV4,
    /// NVLink x2 (~600 GB/s).
    NV2,
    /// NVLink x1 (~300 GB/s).
    NV1,
    /// PCIe switch (same PCIe switch, ~64 GB/s).
    PXB,
    /// CPU/host bridge (same CPU socket, ~32 GB/s).
    PHB,
    /// Cross-socket / system interconnect (~16 GB/s).
    SYS,
    /// Self-link (GPU to itself).
    SelfLink,
}

impl LinkType {
    /// Parse a link type string from nvidia-smi output.
    pub fn parse_label(s: &str) -> Option<Self> {
        match s.trim() {
            "NV4" => Some(Self::NV4),
            "NV3" | "NV2" => Some(Self::NV2),
            "NV1" => Some(Self::NV1),
            "PXB" | "PIX" => Some(Self::PXB),
            "PHB" => Some(Self::PHB),
            "SYS" | "SOC" => Some(Self::SYS),
            "X" => Some(Self::SelfLink),
            _ => None,
        }
    }

    /// Whether this is an NVLink type (any variant).
    pub fn is_nvlink(self) -> bool {
        matches!(self, Self::NV4 | Self::NV2 | Self::NV1)
    }

    /// Latency score (lower is better). Used in edge cost calculation.
    #[allow(clippy::match_same_arms)] // NV4 and NV2 intentionally share the same score
    pub fn latency_score(self) -> u32 {
        match self {
            Self::NV4 => 1,
            Self::NV2 => 1,
            Self::NV1 => 2,
            Self::PXB => 3,
            Self::PHB => 5,
            Self::SYS => 8,
            Self::SelfLink => 0,
        }
    }
}

// ---------------------------------------------------------------------------
// Parsed topology structures
// ---------------------------------------------------------------------------

/// A parsed GPU entry from nvidia-smi topo output.
#[derive(Debug, Clone)]
pub struct ParsedGpu {
    /// GPU ordinal index.
    pub gpu_id: GpuId,
    /// GPU name/model (e.g., "NVIDIA H100 80GB HBM3").
    pub name: String,
    /// CPU affinity bitmask (NUMA node info).
    pub cpu_affinity: Option<u32>,
}

/// A parsed link between two GPUs.
#[derive(Debug, Clone)]
pub struct ParsedLink {
    pub from: GpuId,
    pub to: GpuId,
    pub link_type: LinkType,
}

/// Complete parsed topology from nvidia-smi topo -m.
#[derive(Debug, Clone)]
pub struct ParsedTopology {
    pub gpus: Vec<ParsedGpu>,
    pub links: Vec<ParsedLink>,
    /// CPU affinity mapping: GPU ordinal -> NUMA node ID.
    pub cpu_affinity: HashMap<GpuId, u32>,
}

// ---------------------------------------------------------------------------
// nvidia-smi execution
// ---------------------------------------------------------------------------

/// Execute nvidia-smi topo -m and return its stdout.
pub fn collect_nvidia_smi() -> Result<String, TopologyError> {
    let output = Command::new("nvidia-smi")
        .args(["topo", "-m"])
        .output()
        .map_err(|e| TopologyError::NvidiaSmiError(format!("failed to execute: {e}")))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(TopologyError::NvidiaSmiError(format!(
            "exit code {}: {}",
            output.status.code().unwrap_or(-1),
            stderr.trim()
        )));
    }

    String::from_utf8(output.stdout)
        .map_err(|e| TopologyError::NvidiaSmiError(format!("invalid UTF-8: {e}")))
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

/// Parse the output of `nvidia-smi topo -m` into a structured topology.
///
/// The output format is a matrix like:
/// ```text
///         GPU0    GPU1    GPU2    GPU3    CPU Affinity    NUMA Affinity
/// GPU0     X      NV4     NV4     PHB     0-31            N/A
/// GPU1    NV4      X      PHB     NV4     0-31            N/A
/// GPU2    NV4     PHB      X      NV4     32-63           N/A
/// GPU3    PHB     NV4     NV4      X      32-63           N/A
/// ```
#[allow(clippy::similar_names)] // row_gpu_id vs col_gpu_id are intentionally parallel
pub fn parse_topo_matrix(output: &str) -> Result<ParsedTopology, TopologyError> {
    let lines: Vec<&str> = output.lines().collect();

    // Find the header line containing GPU column labels
    let header_idx = lines
        .iter()
        .position(|line| {
            let trimmed = line.trim();
            trimmed.starts_with("GPU0") || trimmed.contains("\tGPU0")
        })
        .ok_or_else(|| TopologyError::ParseError("no GPU header row found".to_string()))?;

    let header = lines[header_idx];

    // Parse header to find GPU column positions
    let gpu_columns: Vec<usize> = header
        .split_whitespace()
        .enumerate()
        .filter_map(|(i, col)| {
            if col.starts_with("GPU") && col[3..].parse::<u32>().is_ok() {
                Some(i)
            } else {
                None
            }
        })
        .collect();

    let gpu_count = gpu_columns.len();
    if gpu_count == 0 {
        return Err(TopologyError::ParseError(
            "no GPU columns found in header".to_string(),
        ));
    }

    let mut gpus = Vec::with_capacity(gpu_count);
    let mut links = Vec::new();
    let mut cpu_affinity = HashMap::new();

    // Parse each GPU row
    for row_idx in 0..gpu_count {
        let line_idx = header_idx + 1 + row_idx;
        if line_idx >= lines.len() {
            return Err(TopologyError::ParseError(format!(
                "expected GPU{row_idx} row at line {line_idx}, but file ended"
            )));
        }

        let line = lines[line_idx];
        let tokens: Vec<&str> = line.split_whitespace().collect();

        // First token should be GPUn
        let row_label = tokens
            .first()
            .ok_or_else(|| TopologyError::ParseError(format!("empty row at line {line_idx}")))?;

        let row_gpu_id = parse_gpu_label(row_label)
            .ok_or_else(|| TopologyError::ParseError(format!("invalid GPU label: {row_label}")))?;

        // Parse CPU affinity (comes after the link type columns)
        let cpu_aff = if tokens.len() > gpu_count + 1 {
            parse_cpu_affinity(tokens[gpu_count + 1])
        } else {
            None
        };

        gpus.push(ParsedGpu {
            gpu_id: GpuId(row_gpu_id),
            name: format!("GPU{row_gpu_id}"),
            cpu_affinity: cpu_aff,
        });

        if let Some(aff) = cpu_aff {
            cpu_affinity.insert(GpuId(row_gpu_id), aff);
        }

        // Parse link types to other GPUs
        for (col_offset, _) in gpu_columns.iter().enumerate() {
            #[allow(clippy::cast_possible_truncation)] // GPU count fits in u32
            let col_gpu_id = col_offset as u32;
            if col_gpu_id == row_gpu_id {
                continue; // Skip self-link
            }

            // Token index: GPU label (1 token) + link columns
            let token_idx = 1 + col_offset;
            if token_idx >= tokens.len() {
                continue;
            }

            if let Some(link_type) = LinkType::parse_label(tokens[token_idx]) {
                if link_type != LinkType::SelfLink {
                    links.push(ParsedLink {
                        from: GpuId(row_gpu_id),
                        to: GpuId(col_gpu_id),
                        link_type,
                    });
                }
            }
        }
    }

    Ok(ParsedTopology {
        gpus,
        links,
        cpu_affinity,
    })
}

/// Parse "GPUn" label to extract the GPU ordinal.
fn parse_gpu_label(s: &str) -> Option<u32> {
    if let Some(stripped) = s.strip_prefix("GPU") {
        stripped.parse().ok()
    } else {
        None
    }
}

/// Parse CPU affinity string like "0-31" to extract the NUMA node.
/// Returns the starting CPU as a proxy for NUMA node identification.
fn parse_cpu_affinity(s: &str) -> Option<u32> {
    // Format: "0-31" or "32-63" etc.
    let first = s.split('-').next()?;
    first.parse().ok()
}

// ---------------------------------------------------------------------------
// Adapter handshake extension types
// ---------------------------------------------------------------------------

/// GPU metrics reported by adapter processes during handshake or refresh.
/// These are the dynamic (non-topology) fields that change at runtime.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AdapterGpuMetrics {
    /// GPU ordinal index.
    pub gpu_id: u32,
    /// Total VRAM in bytes.
    pub total_vram_bytes: u64,
    /// Free VRAM in bytes.
    pub free_vram_bytes: u64,
    /// GPU utilization percentage (0-100).
    pub utilization_percent: u32,
    /// GPU temperature in Celsius.
    pub temperature_celsius: u32,
    /// PCIe generation (3, 4, 5).
    pub pcie_gen: Option<u32>,
    /// PCIe width (x8, x16).
    pub pcie_width: Option<u32>,
    /// Number of active NVLink lanes.
    pub nvlink_active_lanes: Option<u32>,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    const SINGLE_GPU: &str = "\
\tGPU0\tCPU Affinity\tNUMA Affinity
GPU0\t X \t0-15\t\tN/A
";

    const TWO_GPU_NVLINK: &str = "\
\tGPU0\tGPU1\tCPU Affinity\tNUMA Affinity
GPU0\t X \tNV4\t0-31\t\tN/A
GPU1\tNV4\t X \t0-31\t\tN/A
";

    const FOUR_GPU_MIXED: &str = "\
\tGPU0\tGPU1\tGPU2\tGPU3\tCPU Affinity\tNUMA Affinity
GPU0\t X \tNV4\tPHB\tSYS\t0-31\t\tN/A
GPU1\tNV4\t X \tSYS\tPHB\t0-31\t\tN/A
GPU2\tPHB\tSYS\t X \tNV4\t32-63\t\tN/A
GPU3\tSYS\tPHB\tNV4\t X \t32-63\t\tN/A
";

    const EIGHT_GPU_DGX: &str = "\
\tGPU0\tGPU1\tGPU2\tGPU3\tGPU4\tGPU5\tGPU6\tGPU7\tCPU Affinity\tNUMA Affinity
GPU0\t X \tNV4\tNV4\tNV4\tNV4\tPHB\tPHB\tPHB\t0-31\t\tN/A
GPU1\tNV4\t X \tNV4\tNV4\tPHB\tNV4\tPHB\tPHB\t0-31\t\tN/A
GPU2\tNV4\tNV4\t X \tNV4\tPHB\tPHB\tNV4\tPHB\t0-31\t\tN/A
GPU3\tNV4\tNV4\tNV4\t X \tPHB\tPHB\tPHB\tNV4\t0-31\t\tN/A
GPU4\tNV4\tPHB\tPHB\tPHB\t X \tNV4\tNV4\tNV4\t32-63\t\tN/A
GPU5\tPHB\tNV4\tPHB\tPHB\tNV4\t X \tNV4\tNV4\t32-63\t\tN/A
GPU6\tPHB\tPHB\tNV4\tPHB\tNV4\tNV4\t X \tNV4\t32-63\t\tN/A
GPU7\tPHB\tPHB\tPHB\tNV4\tNV4\tNV4\tNV4\t X \t32-63\t\tN/A
";

    #[test]
    fn test_link_type_parse() {
        assert_eq!(LinkType::parse_label("NV4"), Some(LinkType::NV4));
        assert_eq!(LinkType::parse_label("NV2"), Some(LinkType::NV2));
        assert_eq!(LinkType::parse_label("NV1"), Some(LinkType::NV1));
        assert_eq!(LinkType::parse_label("PXB"), Some(LinkType::PXB));
        assert_eq!(LinkType::parse_label("PIX"), Some(LinkType::PXB));
        assert_eq!(LinkType::parse_label("PHB"), Some(LinkType::PHB));
        assert_eq!(LinkType::parse_label("SYS"), Some(LinkType::SYS));
        assert_eq!(LinkType::parse_label("X"), Some(LinkType::SelfLink));
        assert_eq!(LinkType::parse_label("BOGUS"), None);
    }

    #[test]
    fn test_link_type_nvlink() {
        assert!(LinkType::NV4.is_nvlink());
        assert!(LinkType::NV2.is_nvlink());
        assert!(LinkType::NV1.is_nvlink());
        assert!(!LinkType::PXB.is_nvlink());
        assert!(!LinkType::PHB.is_nvlink());
        assert!(!LinkType::SYS.is_nvlink());
    }

    #[test]
    fn test_latency_ordering() {
        assert!(LinkType::NV4.latency_score() <= LinkType::NV2.latency_score());
        assert!(LinkType::NV2.latency_score() <= LinkType::NV1.latency_score());
        assert!(LinkType::NV1.latency_score() <= LinkType::PXB.latency_score());
        assert!(LinkType::PXB.latency_score() <= LinkType::PHB.latency_score());
        assert!(LinkType::PHB.latency_score() <= LinkType::SYS.latency_score());
    }

    #[test]
    fn test_parse_single_gpu() {
        let parsed = parse_topo_matrix(SINGLE_GPU).unwrap();
        assert_eq!(parsed.gpus.len(), 1);
        assert_eq!(parsed.gpus[0].gpu_id, GpuId(0));
        assert!(parsed.links.is_empty());
        assert_eq!(parsed.cpu_affinity.get(&GpuId(0)), Some(&0));
    }

    #[test]
    fn test_parse_two_gpu_nvlink() {
        let parsed = parse_topo_matrix(TWO_GPU_NVLINK).unwrap();
        assert_eq!(parsed.gpus.len(), 2);
        assert_eq!(parsed.links.len(), 2); // bidirectional

        let nv4_links: Vec<_> = parsed
            .links
            .iter()
            .filter(|l| l.link_type == LinkType::NV4)
            .collect();
        assert_eq!(nv4_links.len(), 2);
    }

    #[test]
    fn test_parse_four_gpu_mixed() {
        let parsed = parse_topo_matrix(FOUR_GPU_MIXED).unwrap();
        assert_eq!(parsed.gpus.len(), 4);
        // 4 GPUs, each has 3 links = 12 total directed links
        assert_eq!(parsed.links.len(), 12);

        // GPU0-GPU1 should be NV4
        let link_0_1: Vec<_> = parsed
            .links
            .iter()
            .filter(|l| l.from == GpuId(0) && l.to == GpuId(1))
            .collect();
        assert_eq!(link_0_1.len(), 1);
        assert_eq!(link_0_1[0].link_type, LinkType::NV4);

        // GPU0-GPU3 should be SYS (cross-socket)
        let link_0_3: Vec<_> = parsed
            .links
            .iter()
            .filter(|l| l.from == GpuId(0) && l.to == GpuId(3))
            .collect();
        assert_eq!(link_0_3.len(), 1);
        assert_eq!(link_0_3[0].link_type, LinkType::SYS);

        // CPU affinity: GPU0,1 on socket 0, GPU2,3 on socket 1
        assert_eq!(parsed.cpu_affinity.get(&GpuId(0)), Some(&0));
        assert_eq!(parsed.cpu_affinity.get(&GpuId(2)), Some(&32));
    }

    #[test]
    fn test_parse_eight_gpu_dgx() {
        let parsed = parse_topo_matrix(EIGHT_GPU_DGX).unwrap();
        assert_eq!(parsed.gpus.len(), 8);
        // 8 GPUs, each has 7 links = 56 total directed links
        assert_eq!(parsed.links.len(), 56);

        // All GPU0-GPU{1,2,3} should be NV4 (same NVLink domain)
        for target in [1u32, 2, 3] {
            let link: Vec<_> = parsed
                .links
                .iter()
                .filter(|l| l.from == GpuId(0) && l.to == GpuId(target))
                .collect();
            assert_eq!(link.len(), 1);
            assert_eq!(link[0].link_type, LinkType::NV4, "GPU0->GPU{target}");
        }

        // GPU0-GPU5 should be PHB (cross-NVLink-domain but same socket)
        let link_0_5: Vec<_> = parsed
            .links
            .iter()
            .filter(|l| l.from == GpuId(0) && l.to == GpuId(5))
            .collect();
        assert_eq!(link_0_5[0].link_type, LinkType::PHB);
    }

    #[test]
    fn test_parse_empty_input() {
        let result = parse_topo_matrix("");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_gpu_label() {
        assert_eq!(parse_gpu_label("GPU0"), Some(0));
        assert_eq!(parse_gpu_label("GPU7"), Some(7));
        assert_eq!(parse_gpu_label("GPU15"), Some(15));
        assert_eq!(parse_gpu_label("CPU0"), None);
        assert_eq!(parse_gpu_label(""), None);
    }

    #[test]
    fn test_cpu_affinity_parse() {
        assert_eq!(parse_cpu_affinity("0-31"), Some(0));
        assert_eq!(parse_cpu_affinity("32-63"), Some(32));
        assert_eq!(parse_cpu_affinity("N/A"), None);
    }
}
