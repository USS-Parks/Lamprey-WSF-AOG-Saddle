"""Unit tests for MAI vLLM adapter."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from adapters.vllm.adapter import VllmAdapter
from adapters.vllm.config import VllmConfig
from adapters.base import GenerationParams, AdapterCapabilities


@pytest.fixture
def config():
    return {
        "host": "127.0.0.1",
        "port": 8000,
        "tensor_parallel_size": 2,
        "enable_lora": True,
    }


@pytest.fixture
def adapter(config):
    return VllmAdapter(config)


class TestVllmConfig:
    def test_defaults(self):
        cfg = VllmConfig.from_dict({})
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8000
        assert cfg.tensor_parallel_size == 1
        assert cfg.enable_lora is False

    def test_custom(self):
        cfg = VllmConfig.from_dict({"port": 9000, "quantization": "awq"})
        assert cfg.port == 9000
        assert cfg.quantization == "awq"


class TestVllmAdapter:
    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        mock_resp = {"data": [{"id": "meta-llama/Llama-3-70B"}]}
        with patch.object(adapter, "_client") as _:
            adapter._client = AsyncMock()
            adapter._client.health = AsyncMock(return_value=True)
            adapter._client.models = AsyncMock(return_value=mock_resp)
            adapter._cfg = VllmConfig.from_dict({})
            await adapter.initialize()
            assert adapter._initialized is True

    @pytest.mark.asyncio
    async def test_generate(self, adapter):
        adapter._initialized = True
        adapter._cfg = VllmConfig.from_dict({})
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
    async def test_health_check_healthy(self, adapter):
        adapter._initialized = True
        adapter._client = AsyncMock()
        adapter._model_id = "test-model"
        adapter._client.health = AsyncMock(return_value=True)
        status = await adapter.health_check()
        assert status.healthy is True

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, adapter):
        status = await adapter.health_check()
        assert status.healthy is False

    def test_capabilities(self, adapter):
        adapter._cfg = VllmConfig.from_dict({"enable_lora": True})
        caps = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_embeddings is True
        assert caps.extra["lora"] is True

    @pytest.mark.asyncio
    async def test_embed(self, adapter):
        adapter._initialized = True
        adapter._cfg = VllmConfig.from_dict({})
        adapter._client = AsyncMock()
        adapter._client.embeddings = AsyncMock(return_value={
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        })
        result = await adapter.embed(["hello"])
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
