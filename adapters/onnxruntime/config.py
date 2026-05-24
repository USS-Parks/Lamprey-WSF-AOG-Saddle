"""ONNX Runtime adapter configuration.

The ONNX Runtime adapter is an in-process backend, not an HTTP server,
so this config is almost entirely about local files and provider
selection. Defaults assume:

  * CPU execution provider only (works on any host).
  * No tokenizer auto-download (air-gap policy).
  * onnxruntime-genai is the preferred generation wrapper. When the
    model is a plain encoder ONNX file, generation is unsupported and
    the adapter must raise UnsupportedOperationError.

DOUGHERTY J-24 deliverable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OnnxRuntimeConfig:
    """Configuration for the ONNX Runtime adapter."""

    # Required: directory or .onnx file the adapter loads at initialize().
    model_path: str = ""

    # Optional path to a local tokenizer.json / tokenizer dir. When the
    # path is empty and the model directory contains tokenizer files
    # (onnxruntime-genai convention), those are used automatically.
    tokenizer_path: str = ""

    # Comma-tolerant ordered provider list. Order matters: ONNX Runtime
    # tries each in turn and falls back to the next when unavailable.
    # CPUExecutionProvider is always appended as the last fallback so
    # adapter behavior stays deterministic on machines without GPUs.
    providers: list[str] = field(
        default_factory=lambda: ["CPUExecutionProvider"],
    )

    # Generation defaults. Honored when the model class supports
    # autoregressive decoding via onnxruntime-genai.
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    context_window: int = 4096

    # Per-request and per-stream timeouts. Generation runs in a worker
    # thread; these guard against runaway models.
    timeout_ms: int = 60_000
    stream_timeout_ms: int = 120_000

    # Set true to allow the adapter to load a plain encoder model and
    # serve embeddings only. Generation remains unsupported in that
    # mode and the adapter reports it honestly via capabilities().
    embedding_only: bool = False

    # Extra options pass-through (not interpreted by the adapter).
    extra: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OnnxRuntimeConfig:
        """Create config from a dict (TOML / JSON section)."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        accepted: dict[str, Any] = {k: v for k, v in data.items() if k in known}
        rest = {k: v for k, v in data.items() if k not in known}
        cfg = cls(**accepted)
        cfg.extra.update(rest)
        # Defensive: normalize comma-separated provider strings.
        if isinstance(cfg.providers, str):
            cfg.providers = [
                p.strip() for p in cfg.providers.split(",") if p.strip()
            ]
        if "CPUExecutionProvider" not in cfg.providers:
            cfg.providers.append("CPUExecutionProvider")
        return cfg
