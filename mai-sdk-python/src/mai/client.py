"""MAI SDK client implementations.

Provides sync and async HTTP clients for the MAI API. Uses httpx
for HTTP transport and Pydantic for request/response serialization.

Session 05 deliverable: client skeleton with method signatures.
Session 14c: streaming, auth token, retry logic, endpoint fixes.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import httpx

from mai.types import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ErrorResponse,
    FunctionCallRequest,
    FunctionCallResponse,
    HardwareHealthResponse,
    HealthResponse,
    MaiError,
    ModelDetail,
    ModelObject,
    PowerStateResponse,
    RequestPriority,
    StructuredRequest,
    StructuredResponse,
)

_HTTP_ERROR_STATUS = 400

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class MaiClientConfig:
    """Client configuration.

    Args:
        base_url: MAI API base URL (default: http://localhost:8420/v1).
        api_key: API key for X-IM-Auth-Token authentication (Session 14c).
        profile_id: Legacy profile header (only used when server allows
            internal profile headers). Prefer api_key.
        priority: Default request priority.
        timeout: Request timeout in seconds.
        stream_timeout: Streaming request timeout in seconds.
        max_retries: Maximum number of retries for retryable errors.
        retry_base_delay: Base delay in seconds between retries (exponential).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8420/v1",
        api_key: str | None = None,
        profile_id: UUID | str | None = None,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: float = 60.0,
        stream_timeout: float = 300.0,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.profile_id = str(profile_id) if profile_id else None
        self.priority = priority
        self.timeout = timeout
        self.stream_timeout = stream_timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    def headers(self) -> dict[str, str]:
        """Build common request headers."""
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-IM-Auth-Token"] = self.api_key
        elif self.profile_id:
            h["X-IM-Profile"] = self.profile_id
        h["X-IM-Priority"] = self.priority.value
        return h


# ---------------------------------------------------------------------------
# SSE parsing helpers
# ---------------------------------------------------------------------------

def _parse_sse_line(line: str) -> str | None:
    """Parse a single SSE data line, returning the data payload or None."""
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("data: "):
        data = line[6:]
        if data == "[DONE]":
            return None
        return data
    return None


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def _should_retry(error: MaiError, attempt: int, max_retries: int) -> float | None:
    """Return delay in seconds if the request should be retried, else None."""
    if attempt >= max_retries:
        return None
    if not error.is_retryable:
        return None
    # Use server-provided retry_after if available, otherwise exponential
    if error.retry_after is not None:
        return float(error.retry_after)
    return min(2 ** attempt, 30.0)


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------

class MaiClient:
    """Synchronous MAI API client.

    Usage::

        client = MaiClient(MaiClientConfig(api_key="im-..."))
        response = client.chat("qwen3-14b:Q4_K_M", [
            ChatMessage(role="user", content="Hello"),
        ])
        print(response.choices[0].message.content)

    For streaming::

        for chunk in client.chat_stream("qwen3-14b:Q4_K_M", messages):
            print(chunk.choices[0].get("delta", {}).get("content", ""), end="")
    """

    def __init__(self, config: MaiClientConfig | None = None) -> None:
        self._config = config or MaiClientConfig()
        self._http = httpx.Client(
            base_url=self._config.base_url,
            headers=self._config.headers(),
            timeout=self._config.timeout,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> MaiClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # --- Inference ---

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatCompletionResponse:
        """Non-streaming chat completion."""
        req = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=False,
            **kwargs,
        )
        resp = self._request_with_retry("POST", "/chat/completions", json=req.model_dump())
        return ChatCompletionResponse.model_validate(resp.json())

    def chat_stream(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> Iterator[ChatCompletionChunk]:
        """Streaming chat completion via SSE.

        Yields ChatCompletionChunk objects as they arrive from the server.
        The stream ends when the server sends ``data: [DONE]``.
        """
        req = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )
        with self._http.stream(
            "POST",
            "/chat/completions",
            json=req.model_dump(),
            timeout=self._config.stream_timeout,
        ) as response:
            if response.status_code >= _HTTP_ERROR_STATUS:
                # Read the full error body
                response.read()
                self._check_error(response)

            for line in response.iter_lines():
                data = _parse_sse_line(line)
                if data is not None:
                    chunk = ChatCompletionChunk.model_validate(json.loads(data))
                    yield chunk

    def stream_completions(
        self,
        model: str,
        prompt: str,
        **kwargs: Any,
    ) -> Iterator[ChatCompletionChunk]:
        """Streaming text completion via SSE (aliases to /chat/completions).

        Wraps the prompt in a user message for the chat completions
        endpoint, which serves both /v1/chat/completions and
        /v1/completions on the server side.
        """
        messages = [ChatMessage(role="user", content=prompt)]
        yield from self.chat_stream(model, messages, **kwargs)

    def complete(self, model: str, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Text completion."""
        req = CompletionRequest(model=model, prompt=prompt, stream=False, **kwargs)
        resp = self._request_with_retry("POST", "/completions", json=req.model_dump())
        return CompletionResponse.model_validate(resp.json())

    def embed(self, model: str, input_: str | list[str]) -> EmbeddingResponse:
        """Text embedding."""
        req = EmbeddingRequest(model=model, input=input_)
        resp = self._request_with_retry("POST", "/embeddings", json=req.model_dump())
        return EmbeddingResponse.model_validate(resp.json())

    def structured(
        self, model: str, prompt: str, schema: dict[str, Any], **kwargs: Any,
    ) -> StructuredResponse:
        """JSON schema-constrained generation."""
        req = StructuredRequest(model=model, prompt=prompt, schema=schema, **kwargs)
        resp = self._request_with_retry(
            "POST", "/generate/structured", json=req.model_dump(by_alias=True),
        )
        return StructuredResponse.model_validate(resp.json())

    def function_call(
        self,
        model: str,
        messages: list[ChatMessage],
        functions: list[dict[str, Any]],
    ) -> FunctionCallResponse:
        """Function/tool calling."""
        req = FunctionCallRequest(model=model, messages=messages, functions=functions)
        resp = self._request_with_retry("POST", "/generate/function_call", json=req.model_dump())
        return FunctionCallResponse.model_validate(resp.json())

    # --- Models ---

    def list_models(self, **filters: Any) -> list[ModelObject]:
        """List available models."""
        resp = self._request_with_retry("GET", "/models", params=filters)
        data = resp.json()
        return [ModelObject.model_validate(m) for m in data.get("data", [])]

    def get_model(self, model_id: str) -> ModelDetail:
        """Get model detail."""
        resp = self._request_with_retry("GET", f"/models/{model_id}")
        return ModelDetail.model_validate(resp.json())

    # --- Health ---

    def health(self) -> HealthResponse:
        """System health (no auth required)."""
        resp = self._http.get("/health")
        self._check_error(resp)
        return HealthResponse.model_validate(resp.json())

    def health_check(self) -> bool:
        """Quick health check. Returns True if the server is reachable
        and reports healthy, False otherwise. Never raises."""
        try:
            resp = self._http.get("/health")
            return resp.status_code < _HTTP_ERROR_STATUS
        except Exception:
            return False

    def hardware_health(self) -> HardwareHealthResponse:
        """Hardware health."""
        resp = self._http.get("/health/hardware")
        self._check_error(resp)
        return HardwareHealthResponse.model_validate(resp.json())

    # --- Power ---

    def power_state(self) -> PowerStateResponse:
        """Current power state.

        Uses /power/state which is aliased on the server to the same
        handler as /power (Session 14c route alignment).
        """
        resp = self._request_with_retry("GET", "/power/state")
        return PowerStateResponse.model_validate(resp.json())

    # --- Retry logic ---

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with automatic retry on retryable errors."""
        last_error: MaiError | None = None
        for attempt in range(self._config.max_retries + 1):
            resp = self._http.request(method, url, **kwargs)
            if resp.status_code < _HTTP_ERROR_STATUS:
                return resp

            try:
                err_resp = ErrorResponse.model_validate(resp.json())
            except Exception:
                err_resp = ErrorResponse(error={
                    "code": f"MAI-{resp.status_code}0",
                    "message": resp.text,
                    "type": "internal_error",
                })
            last_error = MaiError(err_resp)

            delay = _should_retry(last_error, attempt, self._config.max_retries)
            if delay is None:
                raise last_error

            time.sleep(delay)

        # Should not reach here, but safety net
        if last_error is not None:
            raise last_error
        raise RuntimeError("Retry loop exited without result")

    # --- Error handling ---

    @staticmethod
    def _check_error(resp: httpx.Response) -> None:
        """Raise MaiError on non-2xx responses."""
        if resp.status_code >= _HTTP_ERROR_STATUS:
            try:
                err = ErrorResponse.model_validate(resp.json())
            except Exception:
                raise MaiError(ErrorResponse(error={
                    "code": f"MAI-{resp.status_code}0",
                    "message": resp.text,
                    "type": "internal_error",
                })) from None
            raise MaiError(err)


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------

class AsyncMaiClient:
    """Asynchronous MAI API client.

    Usage::

        async with AsyncMaiClient(MaiClientConfig(api_key="im-...")) as client:
            response = await client.chat("qwen3-14b:Q4_K_M", messages)

    For streaming::

        async for chunk in client.chat_stream("qwen3-14b:Q4_K_M", messages):
            print(chunk)
    """

    def __init__(self, config: MaiClientConfig | None = None) -> None:
        self._config = config or MaiClientConfig()
        self._http = httpx.AsyncClient(
            base_url=self._config.base_url,
            headers=self._config.headers(),
            timeout=self._config.timeout,
        )

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> AsyncMaiClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # --- Inference ---

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatCompletionResponse:
        """Non-streaming chat completion."""
        req = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=False,
            **kwargs,
        )
        resp = await self._request_with_retry("POST", "/chat/completions", json=req.model_dump())
        return ChatCompletionResponse.model_validate(resp.json())

    async def chat_stream(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Streaming chat completion via SSE.

        Yields ChatCompletionChunk objects as they arrive from the server.
        The stream ends when the server sends ``data: [DONE]``.
        """
        req = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )
        async with self._http.stream(
            "POST",
            "/chat/completions",
            json=req.model_dump(),
            timeout=self._config.stream_timeout,
        ) as response:
            if response.status_code >= _HTTP_ERROR_STATUS:
                await response.aread()
                self._check_error(response)

            async for line in response.aiter_lines():
                data = _parse_sse_line(line)
                if data is not None:
                    chunk = ChatCompletionChunk.model_validate(json.loads(data))
                    yield chunk

    async def stream_completions(
        self,
        model: str,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Streaming text completion via SSE (aliases to /chat/completions)."""
        messages = [ChatMessage(role="user", content=prompt)]
        async for chunk in self.chat_stream(model, messages, **kwargs):
            yield chunk

    async def complete(
        self, model: str, prompt: str, **kwargs: Any,
    ) -> CompletionResponse:
        """Text completion."""
        req = CompletionRequest(model=model, prompt=prompt, stream=False, **kwargs)
        resp = await self._request_with_retry("POST", "/completions", json=req.model_dump())
        return CompletionResponse.model_validate(resp.json())

    async def embed(self, model: str, input_: str | list[str]) -> EmbeddingResponse:
        """Text embedding."""
        req = EmbeddingRequest(model=model, input=input_)
        resp = await self._request_with_retry("POST", "/embeddings", json=req.model_dump())
        return EmbeddingResponse.model_validate(resp.json())

    async def structured(
        self, model: str, prompt: str, schema: dict[str, Any], **kwargs: Any,
    ) -> StructuredResponse:
        """JSON schema-constrained generation."""
        req = StructuredRequest(model=model, prompt=prompt, schema=schema, **kwargs)
        resp = await self._request_with_retry(
            "POST", "/generate/structured", json=req.model_dump(by_alias=True),
        )
        return StructuredResponse.model_validate(resp.json())

    async def function_call(
        self,
        model: str,
        messages: list[ChatMessage],
        functions: list[dict[str, Any]],
    ) -> FunctionCallResponse:
        """Function/tool calling."""
        req = FunctionCallRequest(model=model, messages=messages, functions=functions)
        resp = await self._request_with_retry(
            "POST", "/generate/function_call", json=req.model_dump(),
        )
        return FunctionCallResponse.model_validate(resp.json())

    # --- Models ---

    async def list_models(self, **filters: Any) -> list[ModelObject]:
        """List available models."""
        resp = await self._request_with_retry("GET", "/models", params=filters)
        data = resp.json()
        return [ModelObject.model_validate(m) for m in data.get("data", [])]

    async def get_model(self, model_id: str) -> ModelDetail:
        """Get model detail."""
        resp = await self._request_with_retry("GET", f"/models/{model_id}")
        return ModelDetail.model_validate(resp.json())

    # --- Health ---

    async def health(self) -> HealthResponse:
        """System health."""
        resp = await self._http.get("/health")
        self._check_error(resp)
        return HealthResponse.model_validate(resp.json())

    async def health_check(self) -> bool:
        """Quick health check. Returns True if reachable, False otherwise."""
        try:
            resp = await self._http.get("/health")
            return resp.status_code < _HTTP_ERROR_STATUS
        except Exception:
            return False

    async def hardware_health(self) -> HardwareHealthResponse:
        """Hardware health."""
        resp = await self._http.get("/health/hardware")
        self._check_error(resp)
        return HardwareHealthResponse.model_validate(resp.json())

    # --- Power ---

    async def power_state(self) -> PowerStateResponse:
        """Current power state."""
        resp = await self._request_with_retry("GET", "/power/state")
        return PowerStateResponse.model_validate(resp.json())

    # --- Retry logic ---

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with automatic retry on retryable errors."""
        import asyncio

        last_error: MaiError | None = None
        for attempt in range(self._config.max_retries + 1):
            resp = await self._http.request(method, url, **kwargs)
            if resp.status_code < _HTTP_ERROR_STATUS:
                return resp

            try:
                err_resp = ErrorResponse.model_validate(resp.json())
            except Exception:
                err_resp = ErrorResponse(error={
                    "code": f"MAI-{resp.status_code}0",
                    "message": resp.text,
                    "type": "internal_error",
                })
            last_error = MaiError(err_resp)

            delay = _should_retry(last_error, attempt, self._config.max_retries)
            if delay is None:
                raise last_error

            await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Retry loop exited without result")

    # --- Error handling ---

    @staticmethod
    def _check_error(resp: httpx.Response) -> None:
        """Raise MaiError on non-2xx responses."""
        if resp.status_code >= _HTTP_ERROR_STATUS:
            try:
                err = ErrorResponse.model_validate(resp.json())
            except Exception:
                raise MaiError(ErrorResponse(error={
                    "code": f"MAI-{resp.status_code}0",
                    "message": resp.text,
                    "type": "internal_error",
                })) from None
            raise MaiError(err)
