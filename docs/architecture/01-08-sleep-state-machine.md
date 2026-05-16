# 01-08: Sleep Mode State Machine

## States & Power Targets (GPU Era)

| State | Power | Purpose | Wake Latency |
|-------|-------|---------|--------------|
| `Off` | 0W | Hard shutdown | Boot sequence |
| `DeepVaultSleep` | 2W | Vault locked, GPU powered down, WoL active | <8s to Sentinel |
| `Sentinel` | 8W | Configured small model (ref: Phi-4-mini), handles simple commands | <2s to Full |
| `FullInference` | 350W | Primary models active, all apps live | N/A |
| `ThermalThrottle` | 200W | Reduced clocks, limited concurrency | Auto-recover |

## Transition Matrix

```
Off -> DeepVaultSleep             (boot)
DeepVaultSleep -> Sentinel        (WoL, API request, schedule)
DeepVaultSleep -> FullInference   (urgent wake, bypass)
Sentinel -> FullInference         (capability exceed, <8s target)
FullInference -> Sentinel         (12min idle auto-demote)
Sentinel -> DeepVaultSleep        (2hr extended idle)
Any -> ThermalThrottle            (GPU > 95C)
ThermalThrottle -> FullInference  (temp < 85C)
Any -> Off                        (shutdown command)
```

## QM-Era Targets (2028+)

DeepVault 1W, Sentinel 3W, Full 15W. Interface identical.
