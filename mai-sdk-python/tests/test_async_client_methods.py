"""Async client method coverage via httpx.MockTransport."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from mai._namespaces import TrustNotProvisionedError
from mai.async_client import AsyncMaiClient
from mai.config import MaiClientConfig
from mai.errors import AuthenticationError, NotFoundError, RateLimitError
from mai.retry import RetryPolicy
from mai.types import ChatMessage, PowerState


def _async_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *, retry: RetryPolicy | None = None,
) -> AsyncMaiClient:
    cfg = MaiClientConfig(
        base_url="http://test/v1",
        retry=retry or RetryPolicy(max_retries=2, base_delay=0.0,
                                    max_delay=0.01, jitter=0.0),
    )
    client = AsyncMaiClient(cfg)
    client._http = httpx.AsyncClient(
        base_url=cfg.base_url,
        headers=cfg.headers(),
        timeout=cfg.timeout,
        transport=httpx.MockTransport(handler),
    )
    return client


async def test_async_chat_round_trip() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode())
        return httpx.Response(200, json={
            "id": "abc", "object": "chat.completion", "created": 1,
            "model": body["model"],
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "hi"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    async with _async_client(handler) as client:
        r = await client.chat("m", [ChatMessage(role="user", content="hi")])
        assert r.choices[0].message.content == "hi"


async def test_async_chat_stream_yields_chunks() -> None:
    chunks = [
        {"id": "1", "object": "chat.completion.chunk", "created": 1,
         "model": "m", "choices": [{"index": 0, "delta": {"content": "A"}}]},
        {"id": "1", "object": "chat.completion.chunk", "created": 1,
         "model": "m", "choices": [{"index": 0, "delta": {"content": "B"}}]},
    ]
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse.encode(),
                              headers={"Content-Type": "text/event-stream"})

    async with _async_client(handler) as client:
        collected = [
            c.choices[0]["delta"]["content"]
            async for c in client.chat_stream(
                "m", [ChatMessage(role="user", content="hi")],
            )
        ]
        assert collected == ["A", "B"]


async def test_async_namespaces_attached() -> None:
    async with _async_client(lambda _r: httpx.Response(200, json={})) as client:
        for ns in ("models", "power", "system", "scheduler",
                   "updates", "admin", "auth", "trust", "compliance"):
            assert hasattr(client, ns)


async def test_async_models_load() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/models/foo/load"
        return httpx.Response(200, json={
            "model_id": "foo", "status": "loaded",
            "adapter_id": "a1", "gpu_id": "g0",
            "vram_allocated_bytes": 1, "load_time_ms": 10,
        })

    async with _async_client(handler) as client:
        r = await client.models.load("foo")
        assert r.model_id == "foo"


async def test_async_power_state() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "state": "sentinel",
            "estimated_power_watts": 50.0,
            "auto_demotion": {"enabled": True, "idle_minutes_remaining": 10,
                              "next_state": "deep_vault_sleep"},
            "promotion_available": True,
            "promotion_latency_target_ms": 1000,
        })

    async with _async_client(handler) as client:
        p = await client.power.get_state()
        assert p.state == PowerState.SENTINEL


async def test_async_401_not_retried() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {
            "code": "MAI-A001", "message": "bad",
            "type": "authentication_failed",
        }})

    async with _async_client(handler) as client:
        with pytest.raises(AuthenticationError):
            await client.models.list()
    assert calls["n"] == 1


async def test_async_429_retries_then_succeeds() -> None:
    counts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        counts["n"] += 1
        if counts["n"] < 3:
            return httpx.Response(429, json={"error": {
                "code": "MAI-R001", "message": "limited",
                "type": "rate_limited", "retry_after_seconds": 0,
            }})
        return httpx.Response(200, json={"data": []})

    async with _async_client(handler) as client:
        r = await client.models.list()
        assert r == []
    assert counts["n"] == 3


async def test_async_404_maps_to_not_found() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {
            "code": "MAI-N001", "message": "no",
            "type": "internal_error",
        }})

    async with _async_client(handler) as client:
        with pytest.raises(NotFoundError):
            await client.models.get("ghost")


async def test_async_trust_bundle_status_decodes_envelope() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "bundle_version": "v1",
            "last_refresh_secs": 12345,
            "age_secs": 60,
            "connectivity": "connected",
            "is_emergency_only": False,
        })

    async with _async_client(handler) as client:
        bs = await client.trust.bundle_status()
        assert bs.connectivity == "connected"


async def test_async_compliance_status_decodes_envelope() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "modules": [{"module": "hipaa", "enabled": True, "priority": 0}],
            "priority": ["hipaa"],
            "reload_count": 0,
            "audit_integrity": {
                "entry_count": 0, "chain_count": 0,
                "head_hash": "00" * 32, "last_verify": "unknown",
                "last_verify_error": None,
            },
            "subscribers": 0,
        })

    async with _async_client(handler) as client:
        s = await client.compliance.get_status()
        assert s.modules[0].module == "hipaa"


# `TrustNotProvisionedError` is still exported for application code that
# wants to detect missing backends.
def test_trust_not_provisioned_error_still_exported() -> None:
    assert issubclass(TrustNotProvisionedError, Exception)


async def test_async_health_check_returns_false_on_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    async with _async_client(handler) as client:
        assert await client.health_check() is False


async def test_async_factories_construct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAI_BASE_URL", "http://env:1/v1")
    c = AsyncMaiClient.from_env()
    assert c._config.base_url == "http://env:1/v1"
    await c.close()


async def test_async_429_exhausts_retries() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {
            "code": "MAI-R", "message": "limited",
            "type": "rate_limited", "retry_after_seconds": 0,
        }})

    async with _async_client(handler) as client:
        with pytest.raises(RateLimitError):
            await client.models.list()
