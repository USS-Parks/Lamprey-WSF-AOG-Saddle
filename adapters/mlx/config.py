"""MLX adapter configuration.

MLX is an in-process Apple Silicon inference library (Apple's mlx-lm). It
runs entirely on local hardware — no host/port, no HTTP. The "endpoint"
in this adapter is a local model directory path on the operator's disk.

Session J-25 (DOUGHERTY lane) deliverable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MLXConfig:
    """Configuration for the MLX adapter.

    All fields are local-only. The trust boundary is the operator's
    filesystem: `model_path` must point at a model directory already
    present on disk; the adapter never downloads.
    """

    # Model — required at initialize() time
    model_path: str = ""
    tokenizer_path: str = ""  # defaults to model_path when empty

    # Generation knobs (mirror GenerationParams defaults but allow
    # adapter-level overrides for environments that pin model behavior)
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9

    # Timeouts (milliseconds). MLX is in-process so these are
    # asyncio-level wall-clock bounds, not HTTP socket timeouts.
    timeout_ms: int = 60_000
    stream_timeout_ms: int = 300_000

    # Context window reported via capabilities(); MLX itself does not
    # expose a stable context-window query, so this is operator-set.
    max_context_window: int = 8192

    # Bounded batch fan-out for generate_batch (no native batch in mlx-lm)
    max_batch_size: int = 4

    # Extra options for forward-compat with mlx-lm flags
    extra_options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MLXConfig:
        """Create config from a dictionary (TOML section)."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        known = {k: v for k, v in data.items() if k in known_fields}
        extra = {k: v for k, v in data.items() if k not in known_fields}
        config = cls(**known)
        config.extra_options.update(extra)
        return config
