"""Unit tests for MAI ExLlamaV2 adapter."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from adapters.exllamav2.adapter import ExLlamaV2Adapter
from adapters.exllamav2.config import ExLlamaV2Config
from adapters.base import GenerationParams, UnsupportedOperationError


@pytest.fixture
def config():
    return {"host": "127.0.0.1", "port": 5000, "quantization": "exl2"}


@pytest.fixture
def adapter(config):
    return ExLlamaV2Adapter(config)


class TestExLlamaV2Config:
    def test_defaults(self):
        cfg = ExLlamaV2Config.from_dict({})
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 5000
        assert cfg.quantization == "exl2"
        assert cfg.cache_mode == "Q4"

    def test_custom(self):
        cfg = ExLlamaV2Config.from_dict({"cache_mode": "FP16", "max_loaded_models": 3})
        assert cfg.cache_mode == "FP16"
        assert cfg.max_loaded_models == 3


class TestExLlamaV2Adapter:
    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        adapter._client = AsyncMock()
        adapter._client.health = AsyncMock(return_value=True)
        adapter._client.models = AsyncMock(return_value={
            "data": [{"id": "TheBloke/Llama-2-70B-EXL2"}]
        })
        adapter._cfg = ExLlamaV2Config.from_dict({})
        await adapter.initialize()
        assert adapter._initialized is True

    @pytest.mark.asyncio
    async def test_generate(self, adapter):
        adapter._initialized = True
        adapter._cfg = ExLlamaV2Config.from_dict({})
        adapter._client = AsyncMock()
        adapter._model_id = "test-model"
        adapter._client.chat_completions = AsyncMock(return_value={
            "choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3},
        })
        result = await adapter.generate("Question", GenerationParams())
        assert result.text == "Answer"

    @pytest.mark.asyncio
    async def test_embed_raises(self, adapter):
        adapter._initialized = True
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["hello"])

    def test_capabilities(self, adapter):
        adapter._cfg = ExLlamaV2Config.from_dict({})
        caps = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_embeddings is False
        assert caps.extra["multi_model"] is True

    @pytest.mark.asyncio
    async def test_load_model(self, adapter):
        adapter._initialized = True
        adapter._client = AsyncMock()
        adapter._client.model_load = AsyncMock(return_value=True)
        result = await adapter.load_model("new-model", {})
        assert result is True
