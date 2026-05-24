"""Opt-in live-backend tests for the MAI MLX adapter (J-25).

These tests run only when:

  1. `MLX_MODEL_PATH` is set to a directory containing a usable mlx-lm
     model on disk, AND
  2. the runtime is macOS on arm64 (Apple Silicon), AND
  3. the `mlx_lm` package is actually importable.

Anything else is a clean skip per ADAPTER-TEST-HARNESS-LOCK.md. The
operator supplies the backend and model; we never download.
"""
from __future__ import annotations

import os

import pytest

from adapters.base import (
    FinishReason,
    GenerationParams,
    HealthStatusKind,
    UnsupportedOperationError,
)
from adapters.mlx.adapter import MLXAdapter
from adapters.mlx.client import is_apple_silicon

pytestmark = pytest.mark.live_backend


def _live_gate() -> str | None:
    """Return the model path if every live precondition holds, else None."""
    model_path = os.environ.get("MLX_MODEL_PATH")
    if not model_path:
        return None
    if not is_apple_silicon():
        return None
    try:
        import mlx_lm  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return None
    return model_path


@pytest.fixture(scope="module")
def mlx_model_path() -> str:
    path = _live_gate()
    if path is None:
        pytest.skip(
            "MLX live test gate not satisfied (need MLX_MODEL_PATH, "
            "Apple Silicon, and mlx_lm installed)",
        )
    return path


@pytest.mark.asyncio
async def test_live_initialize_and_health(mlx_model_path: str):
    adapter = MLXAdapter({"model_path": mlx_model_path})
    handle = await adapter.initialize()
    try:
        assert isinstance(handle, str)
        assert handle.startswith("mlx-")
        h = await adapter.health_check()
        assert h.kind == HealthStatusKind.HEALTHY
        assert h.healthy is True
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_live_generate(mlx_model_path: str):
    adapter = MLXAdapter({"model_path": mlx_model_path})
    await adapter.initialize()
    try:
        result = await adapter.generate(
            "Say OK.", GenerationParams(max_tokens=16, temperature=0.0),
        )
        assert result.text != ""
        assert result.tokens_generated > 0
        assert result.finish_reason in {FinishReason.STOP, FinishReason.MAX_TOKENS}
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_live_streaming(mlx_model_path: str):
    adapter = MLXAdapter({"model_path": mlx_model_path})
    await adapter.initialize()
    try:
        agen = await adapter.generate(
            "Say OK.", GenerationParams(max_tokens=16, temperature=0.0), stream=True,
        )
        chunks: list[str] = []
        async for token in agen:
            chunks.append(token.text)
        # At least one non-empty content chunk + the terminal sentinel.
        assert any(c != "" for c in chunks)
        assert chunks[-1] == ""
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_live_embed_is_unsupported(mlx_model_path: str):
    adapter = MLXAdapter({"model_path": mlx_model_path})
    await adapter.initialize()
    try:
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["hello"])
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_live_capabilities_reflect_runtime(mlx_model_path: str):
    adapter = MLXAdapter({"model_path": mlx_model_path})
    await adapter.initialize()
    try:
        caps = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_embedding is False
        assert caps.backend_version != "unknown"
        assert caps.extra.get("platform_ok") is True
    finally:
        await adapter.shutdown()
