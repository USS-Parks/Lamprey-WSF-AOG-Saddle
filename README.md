# MAI: Model Abstraction Interface

MAI is the local inference and governance layer for IM-OS, Island
Mountain's sovereign data and identity operating system. It lets a
regulated organization run AI close to the data, prove who was allowed
to use it, route each request through policy, and verify the audit
trail afterward.

The inference engine is a plugin. The data sovereignty layer is the
product.

## What This Proves

- **Local-first inference:** REST, gRPC, streaming, SDKs, and backend
  adapters route through one stable MAI boundary.
- **Hardware-aware scheduling:** placement considers topology, KV cache
  residency, batching opportunity, memory pressure, and power state.
- **Trust without payload leakage:** OpenBao-backed claims and signed
  policy bundles cross the trust boundary; prompts, completions,
  embeddings, PHI, ITAR/EAR-controlled content, and OCAP-governed data
  do not.
- **Compliance before inference:** Lamprey policy modules compose HIPAA,
  ITAR/EAR, and OCAP decisions before the request is placed.
- **Audit as proof:** policy decisions, credential events, route
  outcomes, and report certification are tied to tamper-evident records.

## Start Here

| If you are... | Start with |
|---|---|
| Reviewing the product thesis | `docs/ACQUISITION-PACKAGE.md` |
| Running demos | `docs/DEMO-SUITE.md` |
| Integrating trust / identity | `docs/BUYER-INTEGRATION-GUIDE.md` |
| Understanding the architecture | `docs/MAI-MASTER-ARCHITECTURE.md` |
| Building against the SDK | `mai-sdk-python/docs/quickstart.md` |
| Operating a local node | `docs/DEPLOYMENT.md` |

## Architecture

MAI adapts the Tock microcontroller kernel's layered trust model for AI
inference:

- **Trusted core kernel (Rust):** scheduler, registry, power state
  machine, health monitor
- **Untrusted adapters (Python via PyO3):** Ollama, vLLM, llama.cpp,
  TGI, TensorRT-LLM, ExLlamaV2, SGLang
- **Stable API boundary:** REST, gRPC, Server-Sent Events, and WebSocket
  streaming
- **Hardware Interface Layer:** typed traits that abstract GPU,
  memristor, and future compute targets
- **Lamprey governance layer:** router, policy runtime, audit log,
  compliance reports, and dashboard

See `docs/MAI-MASTER-ARCHITECTURE.md` for the full specification.

## Project Structure

```
mai/
  mai-core/       Trusted core kernel (Rust)
  mai-hil/        Hardware Interface Layer (Rust)
  mai-adapters/   Adapter framework + PyO3 bridge (Rust)
  mai-api/        REST + gRPC API server (Rust)
  mai-sdk-rs/     Rust SDK
  mai-sdk-python/ Python SDK
  adapters/       Backend adapter implementations (Python)
  apps/           Demo and integration applications
  configs/        Product tier configurations
  tests/          Integration tests and benchmarks
  docs/           Architecture and specification documents
```

## Build And Test

```bash
# Rust components
cargo check --workspace
cargo clippy --workspace
cargo test --workspace

# Python components
cd mai-sdk-python && pip install -e ".[dev]"
ruff check adapters/
mypy --strict adapters/
pytest adapters/
```

For demo validation, start with `docs/DEMO-SUITE.md`. For known
hardware-dependent deferrals and open questions, see
`docs/KNOWN-ISSUES.md`.

## License

Proprietary. Island Mountain AI. All rights reserved.
