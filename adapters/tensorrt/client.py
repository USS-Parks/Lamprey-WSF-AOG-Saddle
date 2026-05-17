"""TensorRT-LLM HTTP client.

Communicates with NVIDIA Triton Inference Server running TensorRT-LLM backend.
Uses stdlib urllib only. All connections localhost-only.

Session 09 deliverable.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from adapters.base import (
    AdapterTimeoutError,
    BackendUnavailableError,
    ModelNotFoundError,
    OutOfMemoryError,
)

logger = logging.getLogger("mai.adapters.tensorrt.client")


@dataclass
class TritonResponse:
    """Parsed Triton API response."""

    status_code: int
    body: dict[str, Any]
    elapsed_ms: float


@dataclass
class TritonStreamChunk:
    """Single chunk from Triton streaming response."""

    text: str
    finished: bool = False
    cum_log_prob: float | None = None


class TensorRtClient:
    """HTTP client for Triton Inference Server with TensorRT-LLM backend.

    Uses Triton's generate endpoint which provides an OpenAI-like interface
    when configured with the TensorRT-LLM backend.
    """

    def __init__(self, base_url: str, timeout_ms: int, stream_timeout_ms: int):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_ms / 1000.0
        self._stream_timeout = stream_timeout_ms / 1000.0

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> TritonResponse:
        """Execute HTTP request against Triton."""
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if data else {}

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout or self._timeout) as resp:
                raw = resp.read().decode()
                elapsed = (time.monotonic() - t0) * 1000
                return TritonResponse(
                    status_code=resp.status,
                    body=json.loads(raw) if raw else {},
                    elapsed_ms=elapsed,
                )
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

    def _stream_request(self, path: str, body: dict[str, Any]) -> Iterator[TritonStreamChunk]:
        """Execute streaming request via Triton's SSE generate_stream endpoint."""
        url = f"{self._base_url}{path}"
        body["stream"] = True
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
                if payload == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                # Triton TensorRT-LLM returns text_output or choices
                text = ""
                finished = False
                if "choices" in chunk_data:
                    choice = chunk_data["choices"][0]
                    delta = choice.get("delta", {})
                    text = delta.get("content", "")
                    finished = choice.get("finish_reason") is not None
                elif "text_output" in chunk_data:
                    text = chunk_data["text_output"]
                    finished = chunk_data.get("is_final", False)
                yield TritonStreamChunk(text=text, finished=finished)
        finally:
            resp.close()

    def _handle_http_error(self, status: int, body_text: str) -> None:
        """Map HTTP errors to MAI error types."""
        if status == 404:
            raise ModelNotFoundError(model="unknown")
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
        if status >= 500:
            raise BackendUnavailableError()

    # ─── Public API ───────────────────────────────────────────────────────

    def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: list[str] | None = None,
        stream: bool = False,
    ) -> TritonResponse | Iterator[TritonStreamChunk]:
        """Generate via Triton's generate endpoint."""
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        if stop:
            body["stop"] = stop

        if stream:
            return self._stream_request(f"/v2/models/{model}/generate_stream", body)
        return self._request("POST", f"/v2/models/{model}/generate", body)

    def health(self) -> bool:
        """Check Triton server health (ready endpoint)."""
        try:
            self._request("GET", "/v2/health/ready", timeout=10.0)
            return True
        except (AdapterTimeoutError, BackendUnavailableError):
            return False

    def model_ready(self, model: str) -> bool:
        """Check if a specific model is ready to serve."""
        try:
            self._request("GET", f"/v2/models/{model}/ready", timeout=10.0)
            return True
        except (AdapterTimeoutError, BackendUnavailableError):
            return False

    def model_metadata(self, model: str) -> dict[str, Any]:
        """Get model metadata from Triton."""
        try:
            resp = self._request("GET", f"/v2/models/{model}", timeout=10.0)
            return resp.body
        except (AdapterTimeoutError, BackendUnavailableError):
            return {}

    def server_metadata(self) -> dict[str, Any]:
        """Get Triton server metadata."""
        try:
            resp = self._request("GET", "/v2", timeout=10.0)
            return resp.body
        except (AdapterTimeoutError, BackendUnavailableError):
            return {}
