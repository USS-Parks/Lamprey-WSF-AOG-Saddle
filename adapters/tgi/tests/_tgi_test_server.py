"""Real HTTP test server for the TGI adapter integration tests.

Spins up ``http.server.ThreadingHTTPServer`` on a free localhost port
in a daemon thread and speaks the subset of the HF Text Generation
Inference protocol the adapter actually consumes:

  * ``GET  /health``           -> 200 OK (configurable)
  * ``GET  /info``             -> JSON model metadata (configurable)
  * ``GET  /metrics``          -> Prometheus text (configurable)
  * ``POST /generate``         -> JSON ``{"generated_text", "details"}``
  * ``POST /generate_stream``  -> SSE with ``{"token": {...}}`` per line

This file lives under ``adapters/tgi/tests/`` rather than the shared
``adapters/tests/_streaming_server.py`` because TGI is not OpenAI-
compatible and the J-19 prompt does not grant shared-file ownership.

Stdlib only. No new dependencies. Air-gap-policy compliant.

DOUGHERTY J-19.
"""
from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class TgiRecipe:
    """Programmable response shape for one test-server lifetime.

    Attributes:
        health_status: HTTP code returned by ``GET /health``. ``200``
            keeps the adapter healthy; ``503`` simulates the
            still-loading state.
        info_body: payload returned by ``GET /info``. None falls back
            to a minimal ``{"model_id": "test-model"}`` shape.
        metrics_body: text returned by ``GET /metrics``.
        generate_body: dict returned by ``POST /generate``. Used in
            non-streaming requests. ``error_status`` and ``error_body``
            override this.
        error_status: when set, both ``/generate`` and
            ``/generate_stream`` return this HTTP status with
            ``error_body`` as the JSON payload.
        error_body: structured error body. TGI's native shape is
            ``{"error": "...", "error_type": "..."}``.
        stream_chunks: list of ``(token_text, finish_reason,
            generated_text)`` tuples rendered as SSE ``data:`` frames.
        stream_raw_payloads: optional override. When set, the handler
            emits one ``data: <payload>\\n\\n`` line per entry verbatim
            (used for malformed-frame and error-frame tests).
    """

    health_status: int = 200
    info_body: dict[str, Any] | None = None
    metrics_body: str = "# HELP tgi_test\n"
    generate_body: dict[str, Any] | None = None
    error_status: int | None = None
    error_body: dict[str, Any] | None = None
    stream_chunks: list[tuple[str, str | None, str | None]] = field(default_factory=list)
    stream_raw_payloads: list[str] | None = None


def _sse_for_token(text: str, finish_reason: str | None, generated_text: str | None) -> bytes:
    """Render one streaming frame in TGI's native shape."""
    payload: dict[str, Any] = {
        "token": {"text": text, "id": 0, "logprob": -0.5, "special": False},
    }
    if finish_reason is not None or generated_text is not None:
        payload["details"] = {"finish_reason": finish_reason or "length"}
        if generated_text is not None:
            payload["generated_text"] = generated_text
    return f"data: {json.dumps(payload)}\n\n".encode()


def _render_stream_body(recipe: TgiRecipe) -> bytes:
    """Pre-render the full SSE body so Content-Length can be set."""
    parts: list[bytes] = []
    if recipe.stream_raw_payloads is not None:
        for payload in recipe.stream_raw_payloads:
            parts.append(f"data: {payload}\n\n".encode())
    else:
        for text, fr, gen_text in recipe.stream_chunks:
            parts.append(_sse_for_token(text, fr, gen_text))
    return b"".join(parts)


class _Handler(BaseHTTPRequestHandler):
    """Per-server handler. ``recipe`` is injected by ``streaming_server``."""

    recipe: TgiRecipe = TgiRecipe()

    def log_message(self, *_args: Any) -> None:
        return  # Silence per-request stderr noise.

    def do_GET(self) -> None:
        if self.path == "/health":
            if self.recipe.health_status == 200:
                self._respond_json(200, {"status": "ok"})
            else:
                self.send_error(self.recipe.health_status)
            return
        if self.path == "/info":
            self._respond_json(
                200,
                self.recipe.info_body
                or {
                    "model_id": "test-model",
                    "max_input_length": 2048,
                    "max_total_tokens": 4096,
                },
            )
            return
        if self.path == "/metrics":
            data = self.recipe.metrics_body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length) if length else b""

        if self.recipe.error_status is not None:
            self._respond_json(
                self.recipe.error_status,
                self.recipe.error_body or {"error": "synthetic", "error_type": "unknown"},
            )
            return

        if self.path == "/generate":
            self._respond_json(
                200,
                self.recipe.generate_body
                or {
                    "generated_text": "fallback",
                    "details": {"generated_tokens": 1, "finish_reason": "length"},
                },
            )
            return

        if self.path == "/generate_stream":
            body_bytes = _render_stream_body(self.recipe)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            try:
                self.wfile.write(body_bytes)
                self.wfile.flush()
            except BrokenPipeError:
                pass
            return

        self.send_error(404)

    def _respond_json(self, code: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@contextmanager
def tgi_server(recipe: TgiRecipe) -> Iterator[str]:
    """Run a real TGI-shaped HTTP server on a free localhost port.

    Yields the base URL. Cleans up on context exit so tests can run in
    parallel without sharing state. Each invocation creates its own
    ``_Handler`` subclass so the recipe is bound per server instance.
    """
    handler_cls = type("BoundHandler", (_Handler,), {"recipe": recipe})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
