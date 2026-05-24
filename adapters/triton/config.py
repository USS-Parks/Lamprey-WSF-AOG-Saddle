"""Generic Triton (KServe v2) adapter configuration.

Distinct from the TensorRT-LLM adapter (``adapters/tensorrt/``). This
config drives generic Triton inference for non-LLM, multimodal,
embedding, classifier, and custom-model workloads where the operator
declares the tensor I/O convention up front.

J-26 deliverable per ``docs/JOHN-REMEDIATION-ROSTER.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TritonConfig:
    """Configuration for the generic Triton adapter (KServe v2 protocol).

    The defaults reflect Triton Inference Server's standard HTTP port
    (8000) and KServe v2 paths. ``model_name`` is required; the
    optional tensor-I/O fields enable the high-level ``generate`` /
    ``generate_batch`` surface when both sides are wired as BYTES.
    """

    # Connection
    host: str = "127.0.0.1"
    port: int = 8000           # Triton HTTP / KServe v2
    grpc_port: int = 8001      # advisory; this adapter is HTTP-only
    use_ssl: bool = False
    timeout_ms: int = 60000
    stream_timeout_ms: int = 300000
    health_check_timeout_ms: int = 5000

    # Model selection
    model_name: str = "model"
    model_version: str = ""    # empty -> Triton picks the latest

    # Tensor I/O convention (operator-declared).
    # When ``input_tensor_name`` and ``output_tensor_name`` are non-empty
    # and both datatypes are BYTES, the adapter exposes a text
    # ``generate()`` that maps prompt -> input -> /infer -> output. With
    # any other convention, ``generate()`` raises
    # ``UnsupportedOperationError`` and only the raw ``infer()`` surface
    # is available.
    input_tensor_name: str = ""
    input_datatype: str = "BYTES"
    output_tensor_name: str = ""
    output_datatype: str = "BYTES"

    # Advisory hint for ``capabilities().max_context_window``.
    max_input_len: int = 4096

    # Readiness polling during initialize().
    readiness_poll_attempts: int = 1
    readiness_poll_interval_ms: int = 500

    # Capability flags. Truthful only when the operator wired the right
    # tensors -- the adapter cross-checks before reporting them.
    declares_batching: bool = True
    declares_embedding: bool = False

    extra_options: dict[str, object] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def supports_text_io(self) -> bool:
        """True iff the operator wired BYTES text tensors on both sides."""
        return bool(
            self.input_tensor_name
            and self.output_tensor_name
            and self.input_datatype.upper() == "BYTES"
            and self.output_datatype.upper() == "BYTES"
        )

    def model_path(self) -> str:
        """KServe v2 path prefix, with optional explicit version."""
        if self.model_version:
            return f"/v2/models/{self.model_name}/versions/{self.model_version}"
        return f"/v2/models/{self.model_name}"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TritonConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        extras = {k: v for k, v in data.items() if k not in known}
        config = cls(**kwargs)  # type: ignore[arg-type]
        config.extra_options.update(extras)
        return config
