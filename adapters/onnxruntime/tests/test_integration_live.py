"""Live-backend integration tests for the ONNX Runtime adapter.

These tests are opt-in. They run only when ``ONNXRUNTIME_MODEL_PATH``
points at a real ONNX model file (or onnxruntime-genai model directory)
that the host can load. Without that env var, every test in this module
skips cleanly — so ``pytest adapters/onnxruntime/`` on a machine
without ONNX Runtime still runs the mocked unit tests in
``test_adapter.py`` without error.

Opt-in:
    set ONNXRUNTIME_MODEL_PATH=C:\\models\\phi-3-onnx
    python -m pytest -m live_backend adapters/onnxruntime/tests/test_integration_live.py -v

DOUGHERTY lane J-24. Live-test gate documented in
``docs/ADAPTER-TEST-HARNESS-LOCK.md`` §Live Backend Environment Variables.
"""

from __future__ import annotations

import importlib
import os
from typing import Any

import pytest

from adapters.base import (
    AdapterCapabilities,
    Embedding,
    GenerationParams,
    GenerationResult,
    HealthStatusKind,
    Token,
    UnsupportedOperationError,
)
from adapters.onnxruntime.adapter import OnnxRuntimeAdapter

pytestmark = pytest.mark.live_backend


# ─── Gate ───────────────────────────────────────────────────────────────────


def _gate_reason() -> str | None:
    """Return the skip reason, or None when the live test is ready to run."""
    path = os.environ.get("ONNXRUNTIME_MODEL_PATH")
    if not path:
        return (
            "ONNXRUNTIME_MODEL_PATH not set — point this at a local ONNX "
            "model directory (onnxruntime-genai layout) or .onnx file to "
            "enable live tests."
        )
    if not os.path.exists(path):
        return f"ONNXRUNTIME_MODEL_PATH={path!r} does not exist on this host."
    try:
        importlib.import_module("onnxruntime")
    except ImportError:
        return "onnxruntime wheel is not installed in this Python environment."
    return None


@pytest.fixture(scope="module")
def live_model_path() -> str:
    """Resolved model path. Skips the whole module when the gate is unmet."""
    reason = _gate_reason()
    if reason is not None:
        pytest.skip(reason)
    return os.environ["ONNXRUNTIME_MODEL_PATH"]


@pytest.fixture
def embedding_only_flag() -> bool:
    """ONNXRUNTIME_EMBEDDING_ONLY=1 forces the embedding-only branch."""
    return os.environ.get("ONNXRUNTIME_EMBEDDING_ONLY", "0") == "1"


async def _adapter_for(
    model_path: str, embedding_only: bool,
) -> OnnxRuntimeAdapter:
    """Construct and initialize an adapter against the live backend."""
    adapter = OnnxRuntimeAdapter()
    config: dict[str, Any] = {
        "model_path": model_path,
        "embedding_only": embedding_only,
        "context_window": int(
            os.environ.get("ONNXRUNTIME_CONTEXT_WINDOW", "4096"),
        ),
        "max_tokens": int(os.environ.get("ONNXRUNTIME_MAX_TOKENS", "16")),
    }
    providers = os.environ.get("ONNXRUNTIME_PROVIDERS")
    if providers:
        config["providers"] = [p.strip() for p in providers.split(",") if p.strip()]
    await adapter.initialize(config)
    return adapter


# ─── Tests ──────────────────────────────────────────────────────────────────


async def test_initialize_against_real_runtime(
    live_model_path: str, embedding_only_flag: bool,
) -> None:
    """Adapter initializes against a real ONNX Runtime install and reports
    honest capability state."""
    adapter = await _adapter_for(live_model_path, embedding_only_flag)
    try:
        caps = adapter.capabilities()
        assert isinstance(caps, AdapterCapabilities)
        # At least ONE of generation/embedding must be true; otherwise the
        # adapter loaded a model nobody can use.
        assert caps.supports_streaming or caps.supports_embedding, (
            "loaded ONNX model exposes neither generation nor embedding — "
            "adapter cannot serve any request"
        )
        assert caps.backend_version != "unknown"
    finally:
        await adapter.shutdown()


async def test_health_against_real_runtime(
    live_model_path: str, embedding_only_flag: bool,
) -> None:
    """health_check returns HEALTHY after a successful initialize()."""
    adapter = await _adapter_for(live_model_path, embedding_only_flag)
    try:
        status = await adapter.health_check()
        assert status.kind is HealthStatusKind.HEALTHY
        assert status.uptime_ms >= 0
    finally:
        await adapter.shutdown()


async def test_generate_against_real_runtime(
    live_model_path: str, embedding_only_flag: bool,
) -> None:
    """One small generation request. Skipped automatically when the loaded
    model is embedding-only (which is the honest capability state)."""
    adapter = await _adapter_for(live_model_path, embedding_only_flag)
    try:
        caps = adapter.capabilities()
        if not caps.supports_streaming:
            pytest.skip(
                "loaded model does not support generation — capability "
                "flags report supports_streaming=False; generation test "
                "intentionally skipped",
            )
        params = GenerationParams(
            temperature=0.0, top_p=1.0, max_tokens=16,
        )
        result = await adapter.generate("Say OK.", params)
        assert isinstance(result, GenerationResult)
        assert isinstance(result.text, str)
        assert result.tokens_generated >= 0
    finally:
        await adapter.shutdown()


async def test_generate_streaming_against_real_runtime(
    live_model_path: str, embedding_only_flag: bool,
) -> None:
    """Streaming yields tokens in order and terminates cleanly."""
    adapter = await _adapter_for(live_model_path, embedding_only_flag)
    try:
        caps = adapter.capabilities()
        if not caps.supports_streaming:
            pytest.skip(
                "loaded model does not support streaming generation",
            )
        params = GenerationParams(
            temperature=0.0, top_p=1.0, max_tokens=16,
        )
        stream = await adapter.generate("Say OK.", params, stream=True)
        tokens: list[Token] = []
        async for tok in stream:
            tokens.append(tok)
        assert tokens, "no tokens streamed from real ONNX Runtime"
        indices = [t.index for t in tokens]
        assert indices == sorted(indices), "tokens out of order"
        assert tokens[-1].is_end_of_text or tokens[-1].text == "", (
            "stream did not terminate with an EOT sentinel"
        )
    finally:
        await adapter.shutdown()


async def test_embed_against_real_runtime_when_supported(
    live_model_path: str, embedding_only_flag: bool,
) -> None:
    """Run one embed() when capabilities say it's supported; otherwise
    confirm UnsupportedOperationError is raised (honest capability flag)."""
    adapter = await _adapter_for(live_model_path, embedding_only_flag)
    try:
        caps = adapter.capabilities()
        if caps.supports_embedding:
            vectors = await adapter.embed(["hello world"])
            assert len(vectors) == 1
            assert isinstance(vectors[0], Embedding)
            assert vectors[0].vector  # non-empty
            assert vectors[0].input_tokens >= 1
        else:
            with pytest.raises(UnsupportedOperationError):
                await adapter.embed(["hello world"])
    finally:
        await adapter.shutdown()


async def test_shutdown_idempotent_against_real_runtime(
    live_model_path: str, embedding_only_flag: bool,
) -> None:
    """Calling shutdown twice is safe and leaves the adapter unusable."""
    adapter = await _adapter_for(live_model_path, embedding_only_flag)
    await adapter.shutdown()
    await adapter.shutdown()  # second call must not raise
    assert adapter._initialized is False
    assert adapter._client is None
