"""TensorRT-LLM HTTP client.

Communicates with NVIDIA Triton Inference Server running the TensorRT-LLM
backend over Triton's KFServing-style HTTP API. Stdlib-only; air-gapped
local-loopback by default.

Refactored under DOUGHERTY J-22 to satisfy
``docs/ADAPTER-SHARED-CONTRACT.md``:

- one urllib opener per client instance, reused across every request
  (proves pooling in unit tests and avoids per-request connection setup)
- streaming requests use the same opener
- typed error mapping for every backend failure path:
  * connect refused / DNS / socket  -> BackendUnavailableError
  * read/connect timeout            -> AdapterTimeoutError
  * HTTP 404                        -> ModelNotFoundError(<model>)
  * HTTP 408 / 504                  -> AdapterTimeoutError
  * HTTP 413 / "context"/"too long" -> ContextExceededError
  * HTTP 429                        -> RateLimitedError
  * "out of memory" / "OOM"         -> OutOfMemoryError
  * "broken pipe" / 502 after init  -> BackendCrashedError
  * everything 5xx                  -> BackendUnavailableError
  * malformed JSON                  -> BackendCrashedError
- ``close()`` releases the opener (idempotent)
- streaming yields chunks lazily and closes the underlying response in
  ``finally`` so cancellation does not leak file descriptors
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
    BackendCrashedError,
    BackendUnavailableError,
    ContextExceededError,
    ModelNotFoundError,
    OutOfMemoryError,
    RateLimitedError,
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

    Triton exposes ``/v2/models/<model>/generate`` and
    ``/v2/models/<model>/generate_stream`` for the TensorRT-LLM backend.
    Streaming is SSE-framed (``data: {...}`` lines, terminated by
    ``[DONE]`` or by the backend's ``is_final`` flag).

    The client holds one ``urllib`` opener for its entire lifetime; every
    request -- streaming or non-streaming -- routes through that opener.
    Adapters call :meth:`close` on shutdown.
    """

    def __init__(
        self,
        base_url: str,
        timeout_ms: int,
        stream_timeout_ms: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_ms / 1000.0
        self._stream_timeout = stream_timeout_ms / 1000.0
        self._opener: urllib.request.OpenerDirector | None = (
            urllib.request.build_opener()
        )
        self._closed: bool = False

    # ─── Lifecycle ────────────────────────────────────────────────────────

    @property
    def opener(self) -> urllib.request.OpenerDirector:
        """The pooled urllib opener. Stable across the client's lifetime."""
        if self._opener is None or self._closed:
            raise BackendUnavailableError(detail="client is closed")
        return self._opener

    def close(self) -> None:
        """Release the opener. Idempotent."""
        self._opener = None
        self._closed = True

    # ─── Internals ────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        model_hint: str | None = None,
        timeout: float | None = None,
    ) -> TritonResponse:
        """Execute a non-streaming HTTP request against Triton."""
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers: dict[str, str] = (
            {"Content-Type": "application/json"} if data is not None else {}
        )

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        effective_timeout = timeout if timeout is not None else self._timeout

        t0 = time.monotonic()
        try:
            with self.opener.open(req, timeout=effective_timeout) as resp:
                raw = resp.read().decode("utf-8")
                elapsed = (time.monotonic() - t0) * 1000.0
                try:
                    parsed = json.loads(raw) if raw else {}
                except json.JSONDecodeError as exc:
                    raise BackendCrashedError(
                        detail=f"malformed JSON from Triton ({path}): {exc}",
                    ) from exc
                if not isinstance(parsed, dict):
                    raise BackendCrashedError(
                        detail=f"Triton response was not an object ({path})",
                    )
                return TritonResponse(
                    status_code=resp.status,
                    body=parsed,
                    elapsed_ms=elapsed,
                )
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
            _map_http_error(e.code, body_text, model_hint, effective_timeout)
            raise BackendUnavailableError() from e
        except urllib.error.URLError as e:
            reason = str(e.reason)
            if "timed out" in reason or "timeout" in reason.lower():
                raise AdapterTimeoutError(
                    timeout_ms=int(effective_timeout * 1000),
                ) from e
            raise BackendUnavailableError(detail=reason) from e
        except TimeoutError as e:
            raise AdapterTimeoutError(
                timeout_ms=int(effective_timeout * 1000),
            ) from e

    def _stream_request(
        self,
        path: str,
        body: dict[str, Any],
        *,
        model_hint: str | None = None,
    ) -> Iterator[TritonStreamChunk]:
        """Execute a streaming POST against Triton's ``generate_stream``."""
        url = f"{self._base_url}{path}"
        body = {**body, "stream": True}
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            resp = self.opener.open(req, timeout=self._stream_timeout)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
            _map_http_error(e.code, body_text, model_hint, self._stream_timeout)
            raise BackendUnavailableError() from e
        except urllib.error.URLError as e:
            reason = str(e.reason)
            if "timed out" in reason or "timeout" in reason.lower():
                raise AdapterTimeoutError(
                    timeout_ms=int(self._stream_timeout * 1000),
                ) from e
            raise BackendUnavailableError(detail=reason) from e
        except TimeoutError as e:
            raise AdapterTimeoutError(
                timeout_ms=int(self._stream_timeout * 1000),
            ) from e

        try:
            yield from _iter_sse_chunks(resp)
        finally:
            resp.close()

    # ─── Public API ───────────────────────────────────────────────────────

    def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: list[str] | None = None,
        *,
        stream: bool = False,
    ) -> TritonResponse | Iterator[TritonStreamChunk]:
        """Generate via Triton's TensorRT-LLM generate endpoint."""
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
            return self._stream_request(
                f"/v2/models/{model}/generate_stream",
                body,
                model_hint=model,
            )
        return self._request(
            "POST",
            f"/v2/models/{model}/generate",
            body,
            model_hint=model,
        )

    def health(self) -> bool:
        """Probe Triton's readiness endpoint. False on any failure."""
        try:
            self._request("GET", "/v2/health/ready", timeout=self._timeout)
            return True
        except (AdapterTimeoutError, BackendUnavailableError, BackendCrashedError):
            return False

    def model_ready(self, model: str) -> bool:
        """Whether a specific model is ready to serve."""
        try:
            self._request(
                "GET",
                f"/v2/models/{model}/ready",
                model_hint=model,
                timeout=self._timeout,
            )
            return True
        except ModelNotFoundError:
            return False
        except (AdapterTimeoutError, BackendUnavailableError, BackendCrashedError):
            return False

    def model_metadata(self, model: str) -> dict[str, Any]:
        """Get a Triton model's metadata, or {} on any backend failure."""
        try:
            resp = self._request(
                "GET",
                f"/v2/models/{model}",
                model_hint=model,
                timeout=self._timeout,
            )
            return resp.body
        except (
            ModelNotFoundError,
            AdapterTimeoutError,
            BackendUnavailableError,
            BackendCrashedError,
        ):
            return {}

    def server_metadata(self) -> dict[str, Any]:
        """Triton server-level metadata, or {} on any backend failure."""
        try:
            resp = self._request("GET", "/v2", timeout=self._timeout)
            return resp.body
        except (AdapterTimeoutError, BackendUnavailableError, BackendCrashedError):
            return {}


# ─── Helpers ───────────────────────────────────────────────────────────────


def _map_http_error(
    status: int,
    body_text: str,
    model_hint: str | None,
    timeout: float,
) -> None:
    """Map a Triton HTTP error to the right typed MAI adapter error.

    Always raises. Caller's ``raise BackendUnavailableError`` after a call
    here is unreachable, but mypy needs it.
    """
    detail = _extract_error_detail(body_text)
    lower = detail.lower()

    if status == 404:
        raise ModelNotFoundError(model=model_hint or "unknown")
    if status in (408, 504):
        raise AdapterTimeoutError(timeout_ms=int(timeout * 1000))
    if status == 429:
        raise RateLimitedError()
    if status == 413 or "context" in lower or "too long" in lower or "exceed" in lower:
        # 413 Payload Too Large or backend-reported context overflow.
        raise ContextExceededError(max_context=0)
    if "out of memory" in lower or "oom" in lower or ("cuda" in lower and "memory" in lower):
        raise OutOfMemoryError()
    if status == 502 or "broken pipe" in lower or "reset by peer" in lower:
        raise BackendCrashedError(detail=detail or f"HTTP {status}")
    if status >= 500:
        raise BackendUnavailableError(detail=detail or f"HTTP {status}")
    # 4xx that didn't match anything specific -> unavailable rather than
    # a silent BackendUnavailableError with no detail.
    raise BackendUnavailableError(detail=detail or f"HTTP {status}")


def _extract_error_detail(body_text: str) -> str:
    """Pull a useful detail string out of a Triton error body."""
    if not body_text:
        return ""
    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError:
        return body_text[:200]
    if isinstance(parsed, dict):
        for key in ("error", "message", "detail"):
            value = parsed.get(key)
            if isinstance(value, str) and value:
                return value
    return body_text[:200]


def _iter_sse_chunks(resp: Any) -> Iterator[TritonStreamChunk]:
    """Parse Triton's SSE stream into TritonStreamChunk objects.

    Each event is a ``data: <json>`` line. ``[DONE]`` terminates. Lines
    that aren't valid JSON are surfaced as :class:`BackendCrashedError`
    so the adapter can map the malformed frame into a typed adapter
    error (per the shared contract).
    """
    for raw_line in resp:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        if not line.startswith("data:"):
            # Comments / heartbeats; ignore.
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            return
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise BackendCrashedError(
                detail=f"malformed SSE frame from Triton: {exc}",
            ) from exc
        text, finished = _extract_stream_text(data)
        yield TritonStreamChunk(text=text, finished=finished)
        if finished:
            return


def _extract_stream_text(data: dict[str, Any]) -> tuple[str, bool]:
    """Normalize the two SSE frame shapes Triton/TensorRT-LLM can emit."""
    if "choices" in data:
        choices = data["choices"]
        if isinstance(choices, list) and choices:
            choice = choices[0]
            delta = choice.get("delta") if isinstance(choice, dict) else None
            if isinstance(delta, dict):
                text = delta.get("content", "")
            else:
                text = choice.get("text", "") if isinstance(choice, dict) else ""
            finished = bool(
                isinstance(choice, dict) and choice.get("finish_reason") is not None,
            )
            return text or "", finished
    if "text_output" in data:
        text = data.get("text_output", "")
        finished = bool(data.get("is_final", False))
        return text or "", finished
    # Unknown shape: emit empty text but DON'T raise -- some backends
    # send keepalive frames that we should tolerate. Adapter sees no text
    # for these and they don't end the stream.
    return "", bool(data.get("is_final", False))
