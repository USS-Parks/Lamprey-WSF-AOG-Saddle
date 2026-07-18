# 01-07: Hardware Capability Negotiation Protocol

## Discovery Phase

`HardwareProbe::enumerate()` returns `Vec<CapabilityDescriptor>`:

```rust
struct CapabilityDescriptor {
    device_id: String,
    vendor: Vendor,
    compute_type: Vec<ComputeFormat>, // FP16, INT8, INT4
    memory_bytes: u64,
    bandwidth_gbps: f32,
    tdp_watts: u16,
    driver_version: String,
    thermal_state: ThermalState,
    supported_quantizations: Vec<String>,
}
```

## Matching Phase

Scheduler matches request requirements against `CapabilityDescriptor` pool:

1. Filter by required compute format (e.g., INT4 for EXL2)
2. Filter by VRAM margin (required + 15% buffer)
3. Score by thermal headroom & power efficiency
4. Select highest-scoring available device

## Degradation & Fallback

- Primary unavailable -> downgrade to next capability tier
- VRAM OOM -> split across devices (if supported) or evict LRU model
- Hardware fault -> route to CPU fallback (AVX-512)
- Hot-plug detected -> re-run negotiation, rebalance workloads without dropping active streams
