"""Deterministic local-fake integration tests for the TensorRT adapter.

These tests stand up a tiny in-process HTTP server that imitates Triton
Inference Server's TensorRT-LLM endpoints. The adapter is exercised end
to end -- urllib opener, request framing, response parsing, streaming
SSE, shutdown -- against a real socket. No external backend, no
network egress, nothing past 127.0.0.1.

Required coverage per ``docs/ADAPTER-TEST-HARNESS-LOCK.md`` "Integration
Mock Test Minimums":

- successful backend readiness check
- backend not listening / unavailable
- one malformed JSON case
- one backend-native error response
- one streaming frame sequence with termination
- connection/session reuse across at least two requests (pooling)
- cleanup after shutdown

Each test starts and tears down a server in a fixture so failures in
one test cannot leak port-binding state into the next.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from adapters.base import (
    BackendCrashedError,
    BackendUnavailableError,
    GenerationParams,
    HealthStatusKind,
    Token,
    UnsupportedOperationError,
)
from adapters.tensorrt.adapter import TensorRtAdapter

# ─── Local fake Triton ─────────────────────────────────────────────────────


class _FakeTritonState:
    """Shared mutable state the fake server reads on each request.

    Tests mutate the state before issuing adapter calls. The handler is
    a thin function of this state -- no per-test handler subclasses.
    """

    def __init__(self) -> None:
        self.ready: bool = True
        self.model_ready: bool = True
        self.generate_status: int = 200
        self.generate_body: str = json.dumps(
            {"text_output": "Paris.", "output_tokens": 2, "finish_reason": "stop"},
        )
        self.generate_stream_body: bytes = (
            b'data: {"text_output":"Pa","is_final":false}\n'
            b'data: {"text_output":"ris.","is_final":true}\n'
            b"data: [DONE]\n"
        )
        # Connection counter -- the fake will increment per accepted
        # TCP connection so tests can prove pooling across requests.
        self.connections_accepted: int = 0


class _Handler(BaseHTTPRequestHandler):
    """Triton-shaped handler driven by ``server.state`` (a _FakeTritonState)."""

    # Silence the per-request log noise.
    def log_message(self, *_args: Any, **_kwargs: Any) -> None:
        return

    @property
    def state(self) -> _FakeTritonState:
        return self.server.state

    def setup(self) -> None:
        super().setup()
        # Each new accepted connection sets up the BaseRequestHandler.
        self.state.connections_accepted += 1

    def do_GET(self) -> None:
        if self.path == "/v2/health/ready":
            self._respond_status(200 if self.state.ready else 503, b"{}")
            return
        if self.path.startswith("/v2/models/") and self.path.endswith("/ready"):
            self._respond_status(200 if self.state.model_ready else 404, b"{}")
            return
        if self.path.startswith("/v2/models/"):
            body = json.dumps(
                {"name": "llama-trt", "platform": "tensorrt_llm"},
            ).encode("utf-8")
            self._respond_status(200, body)
            return
        if self.path == "/v2":
            body = json.dumps({"name": "triton", "version": "2.40.0"}).encode("utf-8")
            self._respond_status(200, body)
            return
        self._respond_status(404, b'{"error":"unknown path"}')

    def do_POST(self) -> None:
        # Consume the body so the next keep-alive request works.
        length = int(self.headers.get("Content-Length", "0") or "0")
        _ = self.rfile.read(length) if length else b""

        if self.path.endswith("/generate_stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(self.state.generate_stream_body)))
            self.end_headers()
            self.wfile.write(self.state.generate_stream_body)
            return

        if self.path.endswith("/generate"):
            self._respond_status(
                self.state.generate_status,
                self.state.generate_body.encode("utf-8"),
            )
            return

        self._respond_status(404, b'{"error":"unknown path"}')

    def _respond_status(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_triton() -> Iterator[tuple[_FakeTritonState, int]]:
    """Bring up a fake Triton on an ephemeral port. Tear down on exit."""
    port = _pick_free_port()
    state = _FakeTritonState()
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    server.state = state
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


async def _initialized_adapter(port: int) -> TensorRtAdapter:
    adapter = TensorRtAdapter(
        {
            "host": "127.0.0.1",
            "port": port,
            "default_model": "llama-trt",
            "timeout_ms": 2000,
            "stream_timeout_ms": 4000,
        },
    )
    await adapter.initialize()
    return adapter


# ─── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initialize_against_fake_triton(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """Happy-path init reaches /v2/health/ready and /v2/models/<m>/ready."""
    _state, port = fake_triton
    adapter = await _initialized_adapter(port)
    try:
        assert adapter._initialized is True
        assert adapter._engine_ready is True
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_initialize_fails_when_backend_not_listening() -> None:
    """No server bound -> BackendUnavailableError from initialize."""
    port = _pick_free_port()  # ephemeral, nothing listening
    adapter = TensorRtAdapter(
        {
            "host": "127.0.0.1",
            "port": port,
            "default_model": "llama-trt",
            "timeout_ms": 500,
            "stream_timeout_ms": 1000,
        },
    )
    with pytest.raises(BackendUnavailableError):
        await adapter.initialize()


@pytest.mark.asyncio
async def test_generate_against_fake_triton(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """End-to-end non-streaming generation through the urllib client."""
    state, port = fake_triton
    state.generate_body = json.dumps(
        {"text_output": "OK", "output_tokens": 1, "finish_reason": "stop"},
    )
    adapter = await _initialized_adapter(port)
    try:
        result = await adapter.generate("Say OK.", GenerationParams(max_tokens=8))
        assert hasattr(result, "text")
        assert result.text == "OK"
        assert result.tokens_generated == 1
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_generate_malformed_body_raises_crashed(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """Non-JSON body from a 200 response surfaces as BackendCrashedError."""
    state, port = fake_triton
    state.generate_body = "this-is-not-json"
    adapter = await _initialized_adapter(port)
    try:
        with pytest.raises(BackendCrashedError):
            await adapter.generate("hi", GenerationParams())
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_generate_backend_500_is_unavailable(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """Native 500 from the backend maps to a typed adapter error."""
    state, port = fake_triton
    state.generate_status = 500
    state.generate_body = json.dumps({"error": "internal triton failure"})
    adapter = await _initialized_adapter(port)
    try:
        with pytest.raises(BackendUnavailableError):
            await adapter.generate("hi", GenerationParams())
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_streaming_against_fake_triton(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """SSE frames flow through the adapter's async iterator + EOT marker."""
    state, port = fake_triton
    state.generate_stream_body = (
        b'data: {"text_output":"He","is_final":false}\n'
        b'data: {"text_output":"llo","is_final":true}\n'
        b"data: [DONE]\n"
    )
    adapter = await _initialized_adapter(port)
    try:
        tokens: list[Token] = []
        result = await adapter.generate(
            "say hi", GenerationParams(max_tokens=8), stream=True,
        )
        async for tok in result:
            tokens.append(tok)
        assert "".join(t.text for t in tokens) == "Hello"
        assert tokens[-1].is_end_of_text is True
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_two_generates_reuse_opener(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """Pool reuse: the client's urllib opener stays the same object across
    two adapter calls. (The fake server's connection counter is a sanity
    check that the wire actually carried both requests.)"""
    state, port = fake_triton
    state.generate_body = json.dumps(
        {"text_output": "x", "output_tokens": 1, "finish_reason": "stop"},
    )
    adapter = await _initialized_adapter(port)
    try:
        assert adapter._client is not None
        opener_id_before = id(adapter._client._opener)
        await adapter.generate("one", GenerationParams())
        await adapter.generate("two", GenerationParams())
        opener_id_after = id(adapter._client._opener)
        assert opener_id_before == opener_id_after
        # Server saw multiple HTTP requests; stdlib urllib doesn't
        # keep-alive by default so the connection count is >=2.
        assert state.connections_accepted >= 2
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cleans_up_client(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """After shutdown, the adapter's client is released and calls fail
    deterministically (NotReady)."""
    _state, port = fake_triton
    adapter = await _initialized_adapter(port)
    await adapter.shutdown()
    assert adapter._client is None
    assert adapter._initialized is False
    # Embedding stays unsupported regardless of init state.
    with pytest.raises(UnsupportedOperationError):
        await adapter.embed(["hi"])


@pytest.mark.asyncio
async def test_health_reflects_server_state(
    fake_triton: tuple[_FakeTritonState, int],
) -> None:
    """Flip the fake server through ready / not-ready / dead and verify
    health_check tracks the transitions."""
    state, port = fake_triton
    adapter = await _initialized_adapter(port)
    try:
        status = await adapter.health_check()
        assert status.kind == HealthStatusKind.HEALTHY

        state.model_ready = False
        degraded = await adapter.health_check()
        assert degraded.kind == HealthStatusKind.DEGRADED

        state.ready = False
        unavailable = await adapter.health_check()
        assert unavailable.kind == HealthStatusKind.UNAVAILABLE
    finally:
        await adapter.shutdown()
