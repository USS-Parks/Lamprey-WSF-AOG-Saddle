"""Live-backend integration tests for the TensorRT-LLM adapter.

These tests hit a REAL Triton Inference Server running the TensorRT-LLM
backend. They SKIP cleanly when no backend is provisioned, so
``pytest adapters/tensorrt/`` on a machine without GPUs still runs the
unit and mock-integration suites without error.

Opt-in:
    export TENSORRT_HOST=http://127.0.0.1:8000
    export TENSORRT_MODEL=ensemble   # optional, default is "ensemble"
    pytest -m live_backend adapters/tensorrt/tests/test_integration_live.py -v

The harness lock (``docs/ADAPTER-TEST-HARNESS-LOCK.md``) requires each
live test to be small and deterministic: tiny prompt, tiny token
budget, one health probe, one generation, one streaming request, plus
truthful-capabilities and unsupported-embedding assertions. We honour
that here.

DOUGHERTY lane J-22. The fixture lives in
``adapters/tensorrt/tests/conftest.py`` -- the shared ``mai/conftest.py``
is off-limits during the parallel J-18..J-26 wave.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.base import (
    AdapterCapabilities,
    GenerationParams,
    GenerationResult,
    HealthStatus,
    HealthStatusKind,
    Token,
    UnsupportedOperationError,
)
from adapters.tensorrt.adapter import TensorRtAdapter

pytestmark = pytest.mark.live_backend


def _host_to_parts(host: str) -> tuple[str, int]:
    """Split a ``http://h:p`` URL into ``(host, port)``. Default port 8000."""
    stripped = host.replace("http://", "").replace("https://", "").rstrip("/")
    if ":" in stripped:
        h, p = stripped.split(":", 1)
        return h, int(p)
    return stripped, 8000


async def _adapter_for(target: dict[str, Any]) -> TensorRtAdapter:
    h, p = _host_to_parts(target["host"])
    adapter = TensorRtAdapter(
        {
            "host": h,
            "port": p,
            "default_model": target["model"],
            "timeout_ms": 30000,
            "stream_timeout_ms": 60000,
        },
    )
    await adapter.initialize()
    return adapter


@pytest.fixture(autouse=True)
def require_live_tensorrt(
    tensorrt_available: dict[str, Any] | None,
) -> dict[str, Any]:
    if tensorrt_available is None:
        pytest.skip(
            "TENSORRT_HOST (or TRITON_TENSORRT_HOST) not set or Triton "
            "TRT-LLM backend unreachable -- "
            "export TENSORRT_HOST=http://127.0.0.1:8000 to enable live tests.",
        )
    return tensorrt_available


# ─── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initialize_and_health_against_real_triton(
    require_live_tensorrt: dict[str, Any],
) -> None:
    """Init reaches /v2/health/ready and the model becomes ready."""
    adapter = await _adapter_for(require_live_tensorrt)
    try:
        status: HealthStatus = await adapter.health_check()
        # Healthy or Degraded both accept the call as initialized;
        # the gate fixture proved /ready already returned 200 so we
        # expect HEALTHY here.
        assert status.kind == HealthStatusKind.HEALTHY, (
            f"health_check returned {status.kind.value} "
            f"(reason={status.reason!r}) against a Triton that passed "
            "the gate. Live backend regressed or is mid-shutdown."
        )
        assert status.uptime_ms >= 0
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_generate_one_short_prompt(
    require_live_tensorrt: dict[str, Any],
) -> None:
    """One small prompt, tiny token budget, non-empty text returned."""
    adapter = await _adapter_for(require_live_tensorrt)
    try:
        result = await adapter.generate(
            "Say OK.",
            GenerationParams(temperature=0.0, max_tokens=8),
        )
        assert isinstance(result, GenerationResult)
        assert isinstance(result.text, str)
        assert result.text.strip() != ""
        assert result.tokens_generated >= 0
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_streaming_against_real_triton(
    require_live_tensorrt: dict[str, Any],
) -> None:
    """Adapter claims streaming -- prove the live wire delivers ordered tokens."""
    adapter = await _adapter_for(require_live_tensorrt)
    try:
        tokens: list[Token] = []
        result = await adapter.generate(
            "Say OK.",
            GenerationParams(temperature=0.0, max_tokens=8),
            stream=True,
        )
        async for tok in result:
            tokens.append(tok)
        # Non-empty content arrived AND ended cleanly with the EOT marker.
        non_empty = [t for t in tokens if t.text]
        assert non_empty, "no non-empty streaming tokens arrived"
        assert tokens[-1].is_end_of_text is True
        # Indices are monotonically non-decreasing.
        indices = [t.index for t in tokens]
        assert indices == sorted(indices)
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_embedding_unsupported_on_live_backend(
    require_live_tensorrt: dict[str, Any],
) -> None:
    """Adapter advertises supports_embedding=False; the live call must
    raise UnsupportedOperationError, never a silent empty list."""
    adapter = await _adapter_for(require_live_tensorrt)
    try:
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["hello"])
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_capabilities_are_truthful_for_live_backend(
    require_live_tensorrt: dict[str, Any],
) -> None:
    """Capability flags must match what the adapter actually does
    against the live backend."""
    adapter = await _adapter_for(require_live_tensorrt)
    try:
        caps: AdapterCapabilities = adapter.capabilities()
        # Streaming is exercised above -- this is a wire-truth check.
        assert caps.supports_streaming is True
        # Adapter implements bounded-parallel batch dispatch.
        assert caps.supports_batching is True
        # Triton TRT-LLM backend has no embedding endpoint -- the
        # adapter must report this honestly.
        assert caps.supports_embedding is False
        # Hardware/precision details show up in `extra`, never in the
        # top-level capability flags (per the shared contract).
        assert "tensor_parallel_size" in caps.extra
        assert "precision" in caps.extra
    finally:
        await adapter.shutdown()
