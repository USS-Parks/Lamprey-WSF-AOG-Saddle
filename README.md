# MAI: Model Abstraction Interface

The core inference abstraction layer for IM-OS, Island Mountain's sovereign data and identity operating system.

The inference engine is a plugin. The data sovereignty layer is the product.

## Architecture

The MAI adapts the Tock microcontroller kernel's layered trust model for AI inference abstraction:

- **Trusted core kernel** (Rust): scheduler, registry, power state machine, health monitor
- **Untrusted adapters** (Python via PyO3): Ollama, vLLM, llama.cpp, TGI, TensorRT-LLM, ExLlamaV2, SGLang
- **Stable API boundary** (REST + gRPC + Streaming): never breaks backward compatibility
- **Hardware Interface Layer**: typed traits that abstract GPU, memristor, and future compute targets

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
  apps/           L4-L5 application integration scaffolds
  configs/        Product tier configurations
  tests/          Integration tests and benchmarks
  docs/           Architecture and specification documents
```

## Build

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

## License

Proprietary. Island Mountain AI. All rights reserved.
