# 01-09: Model Registry Schema

## Manifest Format (`model.toml`)

```toml
[manifest]
name = "qwen3-14b"
version = "1.2.0"
format = "GGUF"
quantization = "Q5_K_M"
size_bytes = 9845120000
required_vram_gb = 18.5
license = "Apache-2.0"
min_mai_version = "1.0.0"

[capabilities]
chat = true
embed = true
vision = false
code = true
structured_output = true

[backend_compatibility]
ollama = { min_version = "0.3.0" }
vllm = { min_version = "0.4.0" }
llamacpp = { min_version = "3800" }
```

## State Machine

`cold_storage` -> `loading` -> `loaded` -> `active` -> `evicting` -> `evicted`

## Integrity

SHA-256 hash tree in manifest. PQC signature (`manifest.sig`) verified before any load. Air-gap updates via USB `.mai-pkg` bundles.
