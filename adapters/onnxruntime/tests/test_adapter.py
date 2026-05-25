"""Unit + integration-mock tests for the ONNX Runtime adapter (J-24).

Coverage targets the minimums from ``docs/ADAPTER-TEST-HARNESS-LOCK.md``:
construction without I/O, initialize happy + unavailable + validation,
generate non-streaming, generate streaming, timeout mapping, model-not-
found mapping, OOM mapping, malformed response mapping, batch ordering,
empty batch, embedding success + unsupported, health states, capability
truth, shutdown idempotence, post-shutdown determinism, mock integration
for backend readiness / unavailable / malformed / native-error /
streaming / client reuse / shutdown cleanup.

Tests use mocks at two layers:
  * adapter ↔ OnnxRuntimeClient   — the high-volume unit tests
  * OnnxRuntimeClient ↔ onnxruntime — narrow integration-style tests
                                      that inject fakes into ``sys.modules``

Neither layer touches the real ``onnxruntime`` wheel, so this suite
runs on machines without ONNX Runtime installed.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.base import (
    AdapterError,
    AdapterTimeoutError,
    BackendCrashedError,
    BackendUnavailableError,
    Embedding,
    FinishReason,
    GenerationParams,
    GenerationResult,
    HealthStatusKind,
    ModelNotFoundError,
    OutOfMemoryError,
    Token,
    UnsupportedOperationError,
    ValidationError,
)
from adapters.onnxruntime.adapter import OnnxRuntimeAdapter
from adapters.onnxruntime.client import (
    OnnxRuntimeClient,
    OnnxRuntimeClientError,
    OnnxStreamChunk,
)
from adapters.onnxruntime.config import OnnxRuntimeConfig

# ─── Helpers ────────────────────────────────────────────────────────────────


def _fake_info(*, gen: bool = True, emb: bool = False) -> Any:
    """Mimic _LoadedModelInfo without importing the private name."""
    return types.SimpleNamespace(
        supports_generation=gen,
        supports_embedding=emb,
        backend="genai" if gen else "session",
        backend_version="ort-test",
        model_id="test-model",
    )


async def _init_with_fake_client(
    adapter: OnnxRuntimeAdapter,
    *,
    gen: bool = True,
    emb: bool = False,
    client: Any | None = None,
) -> Any:
    """Initialize the adapter against a fake OnnxRuntimeClient."""
    fake_client = client or MagicMock(spec=OnnxRuntimeClient)
    fake_client.load = MagicMock(return_value=_fake_info(gen=gen, emb=emb))
    fake_client.is_ready = MagicMock(return_value=True)
    fake_client.close = MagicMock()
    with patch(
        "adapters.onnxruntime.adapter.OnnxRuntimeClient",
        return_value=fake_client,
    ):
        await adapter.initialize(
            {"model_path": "/fake/model", "context_window": 4096},
        )
    return fake_client


# ─── Config ─────────────────────────────────────────────────────────────────


class TestOnnxRuntimeConfig:
    def test_defaults(self) -> None:
        cfg = OnnxRuntimeConfig()
        assert cfg.model_path == ""
        assert cfg.providers == ["CPUExecutionProvider"]
        assert cfg.embedding_only is False
        assert cfg.timeout_ms == 60_000

    def test_from_dict_appends_cpu_fallback(self) -> None:
        cfg = OnnxRuntimeConfig.from_dict(
            {"model_path": "/m", "providers": ["DmlExecutionProvider"]},
        )
        assert cfg.providers[-1] == "CPUExecutionProvider"
        assert "DmlExecutionProvider" in cfg.providers

    def test_from_dict_extra_collected(self) -> None:
        cfg = OnnxRuntimeConfig.from_dict({"model_path": "/m", "unknown_x": 1})
        assert cfg.extra == {"unknown_x": 1}

    def test_from_dict_keeps_existing_cpu(self) -> None:
        cfg = OnnxRuntimeConfig.from_dict(
            {"model_path": "/m", "providers": ["CPUExecutionProvider"]},
        )
        assert cfg.providers == ["CPUExecutionProvider"]


# ─── Adapter construction & lifecycle ───────────────────────────────────────


class TestAdapterLifecycle:
    def test_construction_does_no_io(self) -> None:
        """__init__ stores config only — no client, no thread, no I/O."""
        adapter = OnnxRuntimeAdapter()
        assert adapter._client is None
        assert adapter._initialized is False
        assert adapter._supports_generation is False
        assert adapter._supports_embedding is False

    async def test_initialize_happy_path(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True, emb=False)
        assert adapter._initialized is True
        assert adapter._supports_generation is True
        client.load.assert_called_once_with(embedding_only=False)

    async def test_initialize_validation_error_when_path_missing(self) -> None:
        adapter = OnnxRuntimeAdapter()
        with pytest.raises(ValidationError):
            await adapter.initialize({})  # no model_path

    async def test_initialize_backend_unavailable(self) -> None:
        """OnnxRuntimeClientError(BackendUnavailable) → BackendUnavailableError."""
        adapter = OnnxRuntimeAdapter()
        fake = MagicMock(spec=OnnxRuntimeClient)
        fake.load = MagicMock(
            side_effect=OnnxRuntimeClientError(
                "BackendUnavailable", "onnxruntime is not installed",
            ),
        )
        with patch(
            "adapters.onnxruntime.adapter.OnnxRuntimeClient",
            return_value=fake,
        ):
            with pytest.raises(BackendUnavailableError):
                await adapter.initialize({"model_path": "/x"})

    async def test_initialize_model_not_found(self) -> None:
        adapter = OnnxRuntimeAdapter()
        fake = MagicMock(spec=OnnxRuntimeClient)
        fake.load = MagicMock(
            side_effect=OnnxRuntimeClientError(
                "ModelNotFound", "path does not exist",
            ),
        )
        with patch(
            "adapters.onnxruntime.adapter.OnnxRuntimeClient",
            return_value=fake,
        ):
            with pytest.raises(ModelNotFoundError):
                await adapter.initialize({"model_path": "/no/such"})

    async def test_initialize_oom(self) -> None:
        adapter = OnnxRuntimeAdapter()
        fake = MagicMock(spec=OnnxRuntimeClient)
        fake.load = MagicMock(
            side_effect=OnnxRuntimeClientError(
                "OutOfMemory", "VRAM exhausted while loading weights",
            ),
        )
        with patch(
            "adapters.onnxruntime.adapter.OnnxRuntimeClient",
            return_value=fake,
        ):
            with pytest.raises(OutOfMemoryError):
                await adapter.initialize({"model_path": "/x"})

    async def test_shutdown_closes_client(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter)
        await adapter.shutdown()
        client.close.assert_called_once()
        assert adapter._client is None
        assert adapter._initialized is False

    async def test_shutdown_is_idempotent(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter)
        await adapter.shutdown()
        # Second call must not raise and must keep state stable.
        await adapter.shutdown()
        assert adapter._initialized is False

    async def test_post_shutdown_calls_fail_deterministically(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=True)
        await adapter.shutdown()
        with pytest.raises(BackendUnavailableError):
            await adapter.generate("hi", GenerationParams())


# ─── Generation ─────────────────────────────────────────────────────────────


class TestAdapterGenerate:
    async def test_generate_non_streaming_returns_result(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        client.generate_once = MagicMock(return_value=("hello world", 5))
        result = await adapter.generate(
            "say hi", GenerationParams(max_tokens=10),
        )
        assert isinstance(result, GenerationResult)
        assert result.text == "hello world"
        assert result.tokens_generated == 5
        assert result.finish_reason is FinishReason.STOP

    async def test_generate_max_tokens_finish_reason(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        client.generate_once = MagicMock(return_value=("abc", 10))
        result = await adapter.generate(
            "p", GenerationParams(max_tokens=10),
        )
        assert isinstance(result, GenerationResult)
        assert result.finish_reason is FinishReason.MAX_TOKENS

    async def test_generate_streaming_yields_ordered_tokens(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        chunks = [
            OnnxStreamChunk(text="Hel", is_final=False),
            OnnxStreamChunk(text="lo", is_final=False),
            OnnxStreamChunk(text="", is_final=True),
        ]
        client.generate_stream = MagicMock(return_value=iter(chunks))
        stream = await adapter.generate(
            "p", GenerationParams(max_tokens=8), stream=True,
        )
        tokens: list[Token] = []
        async for t in stream:
            tokens.append(t)
        # Two content tokens + one EOT.
        assert [t.text for t in tokens] == ["Hel", "lo", ""]
        assert [t.is_end_of_text for t in tokens] == [False, False, True]
        indices = [t.index for t in tokens]
        assert indices == sorted(indices)

    async def test_generate_timeout_maps_to_adapter_timeout(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        adapter._cfg.timeout_ms = 50

        def slow(*_: Any, **__: Any) -> tuple[str, int]:
            import time

            time.sleep(0.5)
            return "x", 1

        client.generate_once = MagicMock(side_effect=slow)
        with pytest.raises(AdapterTimeoutError):
            await adapter.generate("p", GenerationParams())

    async def test_generate_oom_maps_to_oom(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        client.generate_once = MagicMock(
            side_effect=OnnxRuntimeClientError("OutOfMemory", "VRAM gone"),
        )
        with pytest.raises(OutOfMemoryError):
            await adapter.generate("p", GenerationParams())

    async def test_generate_backend_crash_maps_to_typed_error(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        client.generate_once = MagicMock(
            side_effect=OnnxRuntimeClientError(
                "BackendCrashed", "session lost during run",
            ),
        )
        with pytest.raises(BackendCrashedError):
            await adapter.generate("p", GenerationParams())

    async def test_generate_unsupported_when_no_generation(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=False, emb=True)
        with pytest.raises(UnsupportedOperationError):
            await adapter.generate("p", GenerationParams())

    async def test_generate_streaming_unknown_kind_maps_to_adapter_error(
        self,
    ) -> None:
        """Unknown client-error kind must still translate via _raise_typed
        into the AdapterError fallback (no raw client exception leak)."""
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        client.generate_once = MagicMock(
            side_effect=OnnxRuntimeClientError("WeirdKind", "??"),
        )
        with pytest.raises(AdapterError) as exc_info:
            await adapter.generate("p", GenerationParams())
        assert exc_info.value.code == "WeirdKind"


# ─── generate_batch ─────────────────────────────────────────────────────────


class TestAdapterBatch:
    async def test_batch_preserves_order(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=True)
        responses = iter(
            [
                ("first", 1),
                ("second", 2),
                ("third", 3),
            ],
        )
        client.generate_once = MagicMock(
            side_effect=lambda *_args, **_kwargs: next(responses),
        )
        results = await adapter.generate_batch(
            ["a", "b", "c"], GenerationParams(max_tokens=10),
        )
        assert [r.text for r in results] == ["first", "second", "third"]
        assert [r.tokens_generated for r in results] == [1, 2, 3]

    async def test_batch_empty_input_returns_empty(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=True)
        results = await adapter.generate_batch([], GenerationParams())
        assert results == []

    async def test_batch_unsupported_when_no_generation(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=False, emb=True)
        with pytest.raises(UnsupportedOperationError):
            await adapter.generate_batch(["a"], GenerationParams())


# ─── Embeddings ─────────────────────────────────────────────────────────────


class TestAdapterEmbed:
    async def test_embed_returns_typed_embeddings(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=False, emb=True)
        client.embed = MagicMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        embeddings = await adapter.embed(["alpha beta", "gamma"])
        assert all(isinstance(e, Embedding) for e in embeddings)
        assert embeddings[0].vector == [0.1, 0.2]
        assert embeddings[0].input_tokens == 2

    async def test_embed_empty_input(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=False, emb=True)
        assert await adapter.embed([]) == []

    async def test_embed_unsupported(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=True, emb=False)
        with pytest.raises(UnsupportedOperationError):
            await adapter.embed(["x"])

    async def test_embed_oom_maps(self) -> None:
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=False, emb=True)
        client.embed = MagicMock(
            side_effect=OnnxRuntimeClientError("OutOfMemory", "RAM gone"),
        )
        with pytest.raises(OutOfMemoryError):
            await adapter.embed(["x"])


# ─── Health & capabilities ──────────────────────────────────────────────────


class TestAdapterHealth:
    async def test_health_unavailable_before_initialize(self) -> None:
        adapter = OnnxRuntimeAdapter()
        status = await adapter.health_check()
        assert status.kind is HealthStatusKind.UNAVAILABLE

    async def test_health_healthy_after_initialize(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=True)
        status = await adapter.health_check()
        assert status.kind is HealthStatusKind.HEALTHY

    async def test_health_degraded_when_neither_supported(self) -> None:
        """A loaded but unusable model — both flags false — degrades, not unavailable."""
        adapter = OnnxRuntimeAdapter()
        client = await _init_with_fake_client(adapter, gen=False, emb=False)
        client.is_ready = MagicMock(return_value=True)
        status = await adapter.health_check()
        assert status.kind is HealthStatusKind.DEGRADED


class TestAdapterCapabilities:
    async def test_capabilities_truthful_for_generation_only(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=True, emb=False)
        caps = adapter.capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_embedding is False
        assert caps.supports_batching is False
        assert caps.supports_vision is False
        assert caps.backend_version == "ort-test"
        assert caps.extra["providers"] == ["CPUExecutionProvider"]

    async def test_capabilities_truthful_for_embedding_only(self) -> None:
        adapter = OnnxRuntimeAdapter()
        await _init_with_fake_client(adapter, gen=False, emb=True)
        caps = adapter.capabilities()
        assert caps.supports_streaming is False
        assert caps.supports_embedding is True


# ─── Integration-mock layer: OnnxRuntimeClient ↔ onnxruntime module ─────────


class _FakeInferenceSession:
    """Minimal stand-in for onnxruntime.InferenceSession."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.run_calls: list[tuple[Any, dict[str, Any]]] = []

    def run(self, outputs: Any, feeds: dict[str, Any]) -> list[Any]:
        self.run_calls.append((outputs, feeds))
        # Return one row per text (rectangular).
        texts = feeds.get("input_text", [])
        return [[[0.1 * (i + 1), 0.2 * (i + 1)] for i in range(len(texts))]]


def _install_fake_onnxruntime(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Inject a fake ``onnxruntime`` module into ``sys.modules``."""
    fake_ort = types.ModuleType("onnxruntime")
    fake_ort.__version__ = "1.99.0-fake"
    fake_ort.InferenceSession = _FakeInferenceSession
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    # Force the genai path to be absent so embedding_only mode is taken.
    monkeypatch.setitem(sys.modules, "onnxruntime_genai", None)
    return fake_ort


class TestClientIntegrationMocked:
    def test_load_validation_error_no_path(self) -> None:
        client = OnnxRuntimeClient(
            model_path="", tokenizer_path="", providers=["CPUExecutionProvider"],
        )
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            client.load(embedding_only=True)
        assert exc_info.value.kind == "ValidationError"

    def test_load_model_not_found(self) -> None:
        client = OnnxRuntimeClient(
            model_path="/definitely/not/here.onnx",
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            client.load(embedding_only=True)
        assert exc_info.value.kind == "ModelNotFound"

    def test_load_backend_unavailable_when_module_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        model = tmp_path / "m.onnx"
        model.write_bytes(b"\x00\x01")  # presence is enough — never opened.
        # Block onnxruntime import.
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            client.load(embedding_only=True)
        assert exc_info.value.kind == "BackendUnavailable"

    def test_embedding_session_load_and_run(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """Embedding-only path uses InferenceSession; embed() returns vectors."""
        _install_fake_onnxruntime(monkeypatch)
        model = tmp_path / "encoder.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        info = client.load(embedding_only=True)
        assert info.supports_embedding is True
        assert info.supports_generation is False
        assert info.backend == "session"
        assert info.backend_version == "1.99.0-fake"
        # Same client instance used across two embed() calls — proves
        # pool reuse (see ADAPTER-SHARED-CONTRACT.md §HTTP And Session
        # Pooling: the in-process equivalent is session reuse).
        a = client.embed(["hello world", "test"])
        b = client.embed(["another"])
        assert len(a) == 2
        assert len(b) == 1
        # Confirm session reuse: same InferenceSession seen across calls.
        sess = client._ort_session
        assert isinstance(sess, _FakeInferenceSession)
        assert len(sess.run_calls) == 2

    def test_embed_unsupported_when_generation_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """Generation-mode client raises UnsupportedOperation on embed()."""
        _install_fake_onnxruntime(monkeypatch)
        model = tmp_path / "encoder.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        # Force the info into generation-only via load(embedding_only=False)
        # with no genai module available → backend stays "session" but
        # supports_embedding is False; embed must raise Unsupported.
        info = client.load(embedding_only=False)
        assert info.supports_embedding is False
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            client.embed(["x"])
        assert exc_info.value.kind == "UnsupportedOperation"

    def test_embed_malformed_session_output_maps_to_validation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """Non-numeric session output is a typed ValidationError, not a raw TypeError."""
        fake_ort = _install_fake_onnxruntime(monkeypatch)

        class _BadSession(_FakeInferenceSession):
            def run(self, outputs: Any, feeds: dict[str, Any]) -> list[Any]:
                return [[["not", "a", "number"]]]

        fake_ort.InferenceSession = _BadSession
        model = tmp_path / "encoder.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        client.load(embedding_only=True)
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            client.embed(["x"])
        assert exc_info.value.kind == "ValidationError"

    def test_session_native_error_maps_to_backend_crashed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """A backend-native exception during run() must map to BackendCrashed."""
        fake_ort = _install_fake_onnxruntime(monkeypatch)

        class _ExplodingSession(_FakeInferenceSession):
            def run(self, outputs: Any, feeds: dict[str, Any]) -> list[Any]:
                raise RuntimeError("CUDA error: device-side assert triggered")

        fake_ort.InferenceSession = _ExplodingSession
        model = tmp_path / "encoder.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        client.load(embedding_only=True)
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            client.embed(["x"])
        assert exc_info.value.kind == "BackendCrashed"

    def test_close_is_idempotent_and_clears_ready(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        _install_fake_onnxruntime(monkeypatch)
        model = tmp_path / "encoder.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        client.load(embedding_only=True)
        assert client.is_ready() is True
        client.close()
        client.close()  # second call must not raise
        assert client.is_ready() is False

    def test_generate_stream_unsupported_without_genai(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """When onnxruntime-genai is unavailable, generate_stream raises
        UnsupportedOperation — not a placeholder, not a fake stream."""
        _install_fake_onnxruntime(monkeypatch)
        model = tmp_path / "m.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        client.load(embedding_only=False)  # genai missing → session backend
        with pytest.raises(OnnxRuntimeClientError) as exc_info:
            list(
                client.generate_stream(
                    "hi", max_tokens=4, temperature=0.0, top_p=1.0,
                ),
            )
        assert exc_info.value.kind == "UnsupportedOperation"


# ─── Streaming frame sequence with genai fake ───────────────────────────────


def _install_fake_genai(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Inject a minimal fake onnxruntime_genai that drives generate_stream."""
    fake_genai = types.ModuleType("onnxruntime_genai")
    fake_genai.__version__ = "0.5.0-fake"

    class _Params:
        def __init__(self, model: Any) -> None:
            self.model = model
            self.input_ids: list[int] = []

        def set_search_options(self, **kwargs: Any) -> None:
            self.opts = kwargs

    class _Generator:
        def __init__(self, model: Any, params: _Params) -> None:
            self.model = model
            self.params = params
            self._steps = 0

        def is_done(self) -> bool:
            return self._steps >= 3

        def compute_logits(self) -> None:
            pass

        def generate_next_token(self) -> None:
            self._steps += 1

        def get_next_tokens(self) -> list[int]:
            return [100 + self._steps]

    class _Stream:
        def __init__(self) -> None:
            self._frames = iter(["Hel", "lo", "!"])

        def decode(self, _token_id: int) -> str:
            try:
                return next(self._frames)
            except StopIteration:
                return ""

    class _Tokenizer:
        def __init__(self, model: Any) -> None:
            self.model = model

        def encode(self, text: str) -> list[int]:
            return [ord(c) for c in text]

        def create_stream(self) -> _Stream:
            return _Stream()

    class _Model:
        def __init__(self, path: str) -> None:
            self.path = path

    fake_genai.GeneratorParams = _Params
    fake_genai.Generator = _Generator
    fake_genai.Tokenizer = _Tokenizer
    fake_genai.Model = _Model
    monkeypatch.setitem(sys.modules, "onnxruntime_genai", fake_genai)
    return fake_genai


class TestClientIntegrationGenai:
    def test_generate_stream_emits_terminator(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """Streaming yields content chunks then exactly one is_final=True chunk."""
        _install_fake_onnxruntime(monkeypatch)
        _install_fake_genai(monkeypatch)
        model = tmp_path / "m.onnx"
        model.write_bytes(b"onnx")
        client = OnnxRuntimeClient(
            model_path=str(model),
            tokenizer_path="",
            providers=["CPUExecutionProvider"],
        )
        info = client.load(embedding_only=False)
        assert info.supports_generation is True
        assert info.backend == "genai"

        chunks = list(
            client.generate_stream(
                "hi", max_tokens=8, temperature=0.0, top_p=1.0,
            ),
        )
        # Three content chunks + one terminator.
        content = [c for c in chunks if not c.is_final]
        terminators = [c for c in chunks if c.is_final]
        assert [c.text for c in content] == ["Hel", "lo", "!"]
        assert len(terminators) == 1


# ─── Smoke: registry wiring ─────────────────────────────────────────────────


class TestRegistry:
    def test_adapter_is_in_registry(self) -> None:
        """@mai_adapter must register the class so runner.py can resolve it."""
        from adapters.base import get_adapter

        cls = get_adapter("onnxruntime")
        assert cls is OnnxRuntimeAdapter

    def test_runner_load_adapter(self) -> None:
        """runner.load_adapter resolves the package by module/class path."""
        from adapters.runner import load_adapter

        instance = load_adapter(
            "adapters.onnxruntime.adapter", "OnnxRuntimeAdapter",
        )
        assert isinstance(instance, OnnxRuntimeAdapter)


# ─── Ensure asyncio mode is active for plain async tests ────────────────────


# pytest-asyncio asyncio_mode=auto (per pyproject.toml) handles `async def`
# tests without an explicit marker. The helper below exists only for
# debugging — running this file directly should still skip cleanly.
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(
        "Run with `python -m pytest adapters/onnxruntime/tests -q` instead.",
    )

# Unused import silencer for AsyncMock — kept for future test additions
# that need awaitable side-effect drivers without restructuring imports.
_ASYNC_MOCK_SHIM: AsyncMock | None = None
_TODO_NOOP_LOOP: asyncio.AbstractEventLoop | None = None


# ─── J-12: async context manager smoke ───────────────────────────────────────


@pytest.mark.asyncio
async def test_async_context_manager_lifecycle_j12() -> None:
    """J-12: ``async with`` calls initialize on enter, shutdown on exit."""
    from adapters.base import ValidationError

    adapter = OnnxRuntimeAdapter()
    adapter.initialize = AsyncMock(return_value=None)  # type: ignore[method-assign]
    adapter.shutdown = AsyncMock(return_value=None)  # type: ignore[method-assign]
    adapter.set_config({"host": "127.0.0.1"}, hil_handle=None)
    async with adapter as bound:
        assert bound is adapter
    adapter.initialize.assert_awaited_once_with(
        {"host": "127.0.0.1"}, hil_handle=None,
    )
    adapter.shutdown.assert_awaited_once()

    fresh = OnnxRuntimeAdapter()
    with pytest.raises(ValidationError, match="config not set"):
        async with fresh:
            pass
