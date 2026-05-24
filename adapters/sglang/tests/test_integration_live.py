"""Live-backend integration tests for the SGLang adapter.

These tests hit a REAL SGLang server. They SKIP cleanly when the
backend is unavailable, so the default `pytest adapters/sglang/`
invocation on a machine without SGLang still runs the mocked unit
tests in `test_adapter.py` and the local HTTP fake in
`test_integration_mock.py` without error.

Opt-in:
    SGLANG_HOST=http://127.0.0.1:30000 \
    python -m pytest adapters/sglang/tests/test_integration_live.py -v

To pin the model used:
    SGLANG_LIVE_MODEL=meta-llama/Llama-3.1-8B-Instruct

DOUGHERTY lane J-20. Satisfies the live-backend minimums in
`docs/ADAPTER-TEST-HARNESS-LOCK.md` §"Live Backend Test Minimums".
"""
from __future__ import annotations

from typing import Any

import pytest

from adapters.base import (
    AdapterCapabilities,
    GenerationParams,
    HealthStatus,
    HealthStatusKind,
    Token,
    UnsupportedOperationError,
)
from adapters.sglang.adapter import SglangAdapter

# Every test in this module is opt-in and skips when the backend is
# unreachable. The session-scoped probe lives in the adapter-local
# conftest.py alongside this file.
pytestmark = pytest.mark.live_backend


def _host_to_parts(host: str) -> tuple[str, int]:
    stripped = host.replace("http://", "").replace("https://", "").rstrip("/")
    if ":" in stripped:
        h, p = stripped.split(":", 1)
        return h, int(p)
    return stripped, 30000


async def _adapter_for(target: dict[str, Any]) -> SglangAdapter:
    h, p = _host_to_parts(target["host"])
    adapter = SglangAdapter()
    config = {
        "host": h,
        "port": p,
        "default_model": target["model"],
        "timeout_ms": 15000,
        "stream_timeout_ms": 60000,
    }
    await adapter.initialize(config, hil_handle=None)
    return adapter


@pytest.fixture(autouse=True)
def require_live_sglang(sglang_available: dict[str, Any] | None) -> dict[str, Any]:
    if sglang_available is None:
        pytest.skip(
            "SGLANG_HOST not set or SGLang server unreachable — "
            "set SGLANG_HOST=http://127.0.0.1:30000 to enable live tests.",
        )
    return sglang_available


@pytest.mark.asyncio
async def test_initialize_against_real_server(
    require_live_sglang: dict[str, Any],
) -> None:
    adapter = await _adapter_for(require_live_sglang)
    try:
        caps: AdapterCapabilities = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_structured_output is True
        assert caps.supports_embedding is False
        assert adapter._model_id == require_live_sglang["model"]
        assert adapter._initialized is True
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_health_against_real_server(
    require_live_sglang: dict[str, Any],
) -> None:
    adapter = await _adapter_for(require_live_sglang)
    try:
        status: HealthStatus = await adapter.health_check()
        assert status.kind in (HealthStatusKind.HEALTHY, HealthStatusKind.DEGRADED)
        assert status.healthy is True
        assert status.uptime_ms is not None
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_generate_non_streaming_against_real_server(
    require_live_sglang: dict[str, Any],
) -> None:
    adapter = await _adapter_for(require_live_sglang)
    try:
        params = GenerationParams(temperature=0.0, max_tokens=8)
        result = await adapter.generate("Say OK.", params)
        assert isinstance(result.text, str)
        assert len(result.text.strip()) > 0
        assert result.tokens_generated >= 1
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_generate_streaming_against_real_server(
    require_live_sglang: dict[str, Any],
) -> None:
    """Capability claim: supports_streaming=True. Prove it."""
    adapter = await _adapter_for(require_live_sglang)
    try:
        params = GenerationParams(temperature=0.0, max_tokens=16)
        tokens: list[Token] = []
        stream = await adapter.generate("Say OK.", params, stream=True)
        async for tok in stream:
            tokens.append(tok)
        # At least one non-empty token chunk arrived.
        assert any(t.text for t in tokens)
        # Indices are monotonically non-decreasing.
        indices = [t.index for t in tokens]
        assert indices == sorted(indices)
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_embed_raises_unsupported_against_real_server(
    require_live_sglang: dict[str, Any],
) -> None:
    """Capability claim: supports_embedding=False. Prove the error
    taxonomy actually fires against a real backend, not just a mock."""
    adapter = await _adapter_for(require_live_sglang)
    try:
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["hello"])
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_shutdown_idempotent_against_real_server(
    require_live_sglang: dict[str, Any],
) -> None:
    adapter = await _adapter_for(require_live_sglang)
    await adapter.shutdown()
    assert adapter._initialized is False
    assert adapter._client is None
    # Second call must not raise.
    await adapter.shutdown()
    assert adapter._initialized is False
