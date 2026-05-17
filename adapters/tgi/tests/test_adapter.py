"""Unit tests for MAI TGI adapter."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from adapters.tgi.adapter import TgiAdapter
from adapters.tgi.config import TgiConfig
from adapters.base import GenerationParams, UnsupportedOperationError


@pytest.fixture
def config():
    return {"host": "127.0.0.1", "port": 8080}


@pytest.fixture
def adapter(config):
    return TgiAdapter(config)


class TestTgiConfig:
    def test_defaults(self):
        cfg = TgiConfig.from_dict({})
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8080
        assert cfg.quantize is None

    def test_custom(self):
        cfg = TgiConfig.from_dict({"quantize": "bitsandbytes-nf4", "speculate": 3})
        assert cfg.quantize == "bitsandbytes-nf4"
        assert cfg.speculate == 3


class TestTgiAdapter:
    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        adapter._client = AsyncMock()
        adapter._client.health = AsyncMock(return_value=True)
        adapter._client.info = AsyncMock(return_value={
            "model_id": "mistralai/Mistral-7B"
        })
        adapter._cfg = TgiConfig.from_dict({})
        await adapter.initialize()
        assert adapter._initialized is True
        assert adapter._model_id == "mistralai/Mistral-7B"

    @pytest.mark.asyncio
    async def test_generate(self, adapter):
        adapter._initialized = True
        adapter._cfg = TgiConfig.from_dict({})
        adapter._client = AsyncMock()
        adapter._model_id = "test-model"
        adapter._client.generate = AsyncMock(return_value={
            "generated_text": "Hello world",
            "details": {
                "generated_tokens": 3,
                "finish_reason": "length",
            },
        })
        result = await adapter.generate("Hi", GenerationParams(max_tokens=10))
        assert result.text == "Hello world"
        assert result.tokens_generated == 3

    @pytest.mark.asyncio
    async def test_embed_raises(self, adapter):
        adapter._initialized = True
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["hello"])

    def test_capabilities(self, adapter):
        adapter._cfg = TgiConfig.from_dict({})
        caps = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_embeddings is False
        assert caps.supports_structured_output is False

    @pytest.mark.asyncio
    async def test_health_not_initialized(self, adapter):
        status = await adapter.health_check()
        assert status.healthy is False
