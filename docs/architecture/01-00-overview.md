# 01-00: MAI Master Architecture Overview

## System Context

The Model Abstraction Interface (MAI) is the sovereign inference abstraction layer for IM-OS. It sits at Layer 3, separating all application/agent logic (L4-L6) from all hardware acceleration (L1-L2). The MAI is inference-engine agnostic from line one. It treats the inference backend as a hot-swappable plugin.

## Six-Layer Stack (Tock-Mapped)

```
┌─────────────────────────────────────────────────────────────┐
│ L6  UI (React Dashboard)                       OUT OF SCOPE │
├─────────────────────────────────────────────────────────────┤
│ L5-L6  APPLICATIONS (Tock: Processes)           UNTRUSTED   │
│ Summit Chat, FamilyVault AI, Scribe, MedRecord, HomeBase    │
├─────────────────────────── MAI API ─────────────────────────┤
│ L3-L4  SYSCALL INTERFACE (Tock: Syscall)        BOUNDARY    │
│ REST + gRPC + SSE/WebSocket + Python/Rust SDK               │
├─────────────────────────────────────────────────────────────┤
│ L3     BACKEND ADAPTERS (Tock: Capsules)        UNTRUSTED   │
│ Ollama, vLLM, llama.cpp, TGI, TensorRT-LLM, ExLlamaV2,    │
│ SGLang                                                      │
├─────────────── HIL (Capability Layer) ──────────────────────┤
│ L3     MAI CORE KERNEL (Tock: Core Kernel)      TRUSTED     │
│ Scheduler, Power State Machine, Registry, Health, HotSwap   │
├─────────────── HIL (Hardware Interface) ────────────────────┤
│ L1-L2  HARDWARE DRIVERS (Tock: Periph Drivers)  TRUSTED     │
│ CUDA/ROCm/Metal detection, GPU memory, TPM, Air-gap, Therm │
├─────────────────────────────────────────────────────────────┤
│ L1     HARDWARE (Tock: Hardware)                PHYSICAL    │
│ NVIDIA/AMD GPUs, Air-gap switch, TPM 2.0, ZFS Vault        │
└─────────────────────────────────────────────────────────────┘
```
