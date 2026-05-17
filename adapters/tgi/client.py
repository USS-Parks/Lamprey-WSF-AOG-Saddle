"""TGI HTTP client.

Communicates with HuggingFace Text Generation Inference REST API.
Uses stdlib urllib only (no external dependencies).

Session 09 deliverable.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator

from adapters.base import (
    AdapterTimeoutError,
    BackendUnavailableError,
    ContextExceededError,
    OutOfMemoryError,
    RateLimitedError,
)

logger = logging.getLogger("mai.adapters.tgi.client")


@dataclass
class TgiResponse:
    """Parsed TGI API response."""

    status_code: int
    body: dict[str, Any] | list[Any]
    elapsed_ms: float


@dataclass
class TgiStreamChunk:
    """Single chunk from TGI streaming response."""

    token_text: str
    token_id: int | None = None
    finish_reason: str | None = None
    generated_text: str | None = None


class TgiClient:
    """HTTP client for HuggingFace Text Generation Inference.

    TGI has its own API format (not OpenAI-compatible by default),
    with endpoints: /generate, /generate_stream, /info, /health.
    """

    def __init__(self, base_url: str, timeout_ms: int, stream_timeout_ms: int):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_ms / 1000.0
        self._stream_timeout = stream_timeout_ms / 1000.0

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> TgiResponse:
        """Execute HTTP request against TGI server."""
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if data else {}

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout or self._timeout) as resp:
                raw = resp.read().decode()
                elapsed = (time.monotonic() - t0) * 1000
                parsed = json.loads(raw) if raw else {}
                return TgiResponse(status_code=resp.status, body=parsed, elapsed_ms=elapsed)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            self._handle_http_error(e.code, body_text)
            raise BackendUnavailableError() from e
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason):
                raise AdapterTimeoutError(timeout_ms=int((timeout or self._timeout) * 1000)) from e
            raise BackendUnavailableError() from e
        except TimeoutError as e:
            raise AdapterTimeoutError(timeout_ms=int((timeout or self._timeout) * 1000)) from e

    def _stream_request(self, path: str, body: dict[str, Any]) -> Iterator[TgiStreamChunk]:
        """Execute streaming request. TGI uses SSE with token objects."""
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self._stream_timeout)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            self._handle_http_error(e.code, body_text)
            raise BackendUnavailableError() from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise BackendUnavailableError() from e

        try:
            for line in resp:
                line_str = line.decode().strip()
                if not line_str or not line_str.startswith("data:"):
                    continue
                payload = line_str[5:].strip()
                if not payload:
                    continue
                try:
                    chunk_data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                token = chunk_data.get("token", {})
                yield TgiStreamChunk(
                    token_text=token.get("text", ""),
                    token_id=token.get("id"),
                    finish_reason=chunk_data.get("details", {}).get("finish_reason")
                        if chunk_data.get("details") else None,
                    generated_text=chunk_data.get("generated_text"),
                )
        finally:
            resp.close()

    def _handle_http_error(self, status: int, body_text: str) -> None:
        """Map HTTP errors to MAI error types."""
        if status == 429:
            raise RateLimitedError()
        if status in (408, 504):
            raise AdapterTimeoutError(timeout_ms=int(self._timeout * 1000))
        detail = ""
        try:
            err_body = json.loads(body_text)
            detail = err_body.get("error", "")
        except (json.JSONDecodeError, KeyError):
            detail = body_text[:200]
        if "memory" in detail.lower() or "oom" in detail.lower():
            raise OutOfMemoryError()
        if "input" in detail.lower() and "too long" in detail.lower():
            raise ContextExceededError(max_context=0)
        if status >= 500:
            raise BackendUnavailableError()

    # ─── Public API ───────────────────────────────────────────────────────

    def generate(
        self,
        inputs: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: list[str] | None = None,
        watermark: bool = False,
        stream: bool = False,
    ) -> TgiResponse | Iterator[TgiStreamChunk]:
        """TGI generate endpoint."""
        parameters: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "watermark": watermark,
        }
        if stop:
            parameters["stop"] = stop

        body = {"inputs": inputs, "parameters": parameters}

        if stream:
            return self._stream_request("/generate_stream", body)
        return self._request("POST", "/generate", body)

    def info(self) -> dict[str, Any]:
        """Get model info (model_id, max_tokens, quantization, etc.)."""
        try:
            resp = self._request("GET", "/info", timeout=5.0)
            return resp.body if isinstance(resp.body, dict) else {}
        except (AdapterTimeoutError, BackendUnavailableError):
            return {}

    def health(self) -> bool:
        """Check TGI server health."""
        try:
            self._request("GET", "/health", timeout=5.0)
            return True
        except (AdapterTimeoutError, BackendUnavailableError):
            return False

    def metrics(self) -> str:
        """Fetch Prometheus metrics endpoint (raw text)."""
        try:
            resp = self._request("GET", "/metrics", timeout=5.0)
            return str(resp.body)
        except (AdapterTimeoutError, BackendUnavailableError):
            return ""
