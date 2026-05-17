"""Unit tests for MAI SGLang adapter."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from adapters.sglang.adapter import SglangAdapter
from adapters.sglang.config import SglangConfig
from adapters.base import GenerationParams, UnsupportedOperationError


@pytest.fixture
def config():
    return {"host": "127.0.0.1", "port": 30000, "enable_radix_attention": True}


@pytest.fixture
def adapter(config):
    return SglangAdapter(config)


class TestSglangConfig:
    def test_defaults(self):
        cfg = SglangConfig.from_dict({})
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 30000
        assert cfg.enable_radix_attention is True

    def test_custom(self):
        cfg = SglangConfig.from_dict({"enable_vision": True, "max_forks": 16})
        assert cfg.enable_vision is True
        assert cfg.max_forks == 16


class TestSglangAdapter:
    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        adapter._client = AsyncMock()
        adapter._client.health = AsyncMock(return_value={"status": "ok"})
        adapter._client.models = AsyncMock(return_value=["meta-llama/Llama-3-8B"])
        adapter._cfg = SglangConfig.from_dict({})
        await adapter.initialize()
        assert adapter._initialized is True
        assert adapter._model_id == "meta-llama/Llama-3-8B"

    @pytest.mark.asyncio
    async def test_generate(self, adapter):
        adapter._initialized = True
        adapter._cfg = SglangConfig.from_dict({})
        adapter._client = AsyncMock()
        adapter._model_id = "test-model"
        adapter._client.chat_completions = AsyncMock(return_value={
            "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        })
        result = await adapter.generate("Hi", GenerationParams())
        assert result.text == "Hello!"
        assert result.tokens_generated == 2

    @pytest.mark.asyncio
    async def test_generate_with_constrained(self, adapter):
        adapter._initialized = True
        adapter._cfg = SglangConfig.from_dict({})
        adapter._client = AsyncMock()
        adapter._model_id = "test-model"
        adapter._client.chat_completions = AsyncMock(return_value={
            "choices": [{"message": {"content": '{"name":"test"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })
        params = GenerationParams(extra={"json_schema": '{"type":"object"}'})
        result = await adapter.generate("Generate JSON", params)
        assert "name" in result.text

    @pytest.mark.asyncio
    async def test_embed_raises(self, adapter):
        adapter._initialized = True
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["hello"])

    def test_capabilities(self, adapter):
        adapter._cfg = SglangConfig.from_dict({})
        caps = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_embeddings is False
        assert caps.supports_structured_output is True
        assert caps.extra["radix_attention"] is True
        assert caps.extra["constrained_decoding"] is True

    @pytest.mark.asyncio
    async def test_flush_cache(self, adapter):
        adapter._initialized = True
        adapter._client = AsyncMock()
        adapter._client.flush_cache = AsyncMock(return_value=True)
        result = await adapter.flush_cache()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_not_initialized(self, adapter):
        status = await adapter.health_check()
        assert status.healthy is False
