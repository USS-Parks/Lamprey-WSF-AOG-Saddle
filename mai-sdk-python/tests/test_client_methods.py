"""Sync client method coverage via httpx.MockTransport.

Tests every public method, retry behavior, error mapping, streaming
decode, and namespace dispatch. No real network is involved.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from mai._namespaces import TrustNotProvisionedError
from mai.client import MaiClient
from mai.config import MaiClientConfig
from mai.errors import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from mai.retry import RetryPolicy
from mai.types import ChatMessage, PowerState, PowerTransitionRequest


def _client(handler: Callable[[httpx.Request], httpx.Response],
            *, retry: RetryPolicy | None = None) -> MaiClient:
    cfg = MaiClientConfig(
        base_url="http://test/v1",
        retry=retry or RetryPolicy(max_retries=2, base_delay=0.0,
                                    max_delay=0.01, jitter=0.0),
    )
    client = MaiClient(cfg)
    client._http = httpx.Client(  # swap transport
        base_url=cfg.base_url,
        headers=cfg.headers(),
        timeout=cfg.timeout,
        transport=httpx.MockTransport(handler),
    )
    return client


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def test_chat_returns_completion_response() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/chat/completions"
        body = json.loads(req.content.decode())
        assert body["model"] == "qwen3-14b:Q4_K_M"
        assert body["stream"] is False
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

    with _client(handler) as client:
        r = client.chat("qwen3-14b:Q4_K_M",
                        [ChatMessage(role="user", content="hello")])
        assert r.choices[0].message.content == "hi"
        assert r.usage.total_tokens == 2


def test_chat_stream_yields_chunks_and_stops_on_done() -> None:
    chunks = [
        {"id": "1", "object": "chat.completion.chunk", "created": 1,
         "model": "m", "choices": [{"index": 0, "delta": {"content": "Hel"}}]},
        {"id": "1", "object": "chat.completion.chunk", "created": 1,
         "model": "m", "choices": [{"index": 0, "delta": {"content": "lo"}}]},
    ]
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse.encode(),
                              headers={"Content-Type": "text/event-stream"})

    with _client(handler) as client:
        collected = list(client.chat_stream(
            "m", [ChatMessage(role="user", content="hi")],
        ))
        assert len(collected) == 2
        assert collected[0].choices[0]["delta"]["content"] == "Hel"
        assert collected[1].choices[0]["delta"]["content"] == "lo"


def test_complete_alias_is_completions() -> None:
    assert MaiClient.complete is MaiClient.completions


def test_embed_alias_is_embeddings() -> None:
    assert MaiClient.embed is MaiClient.embeddings


def test_embed_returns_typed_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "object": "list",
            "model": "embed-1",
            "data": [{"object": "embedding", "index": 0,
                      "embedding": [0.1, 0.2], "input_tokens": 3}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 0, "total_tokens": 3},
        })

    with _client(handler) as client:
        r = client.embed("embed-1", ["hi"])
        assert len(r.data) == 1
        assert r.data[0].embedding == [0.1, 0.2]


# ---------------------------------------------------------------------------
# Models namespace
# ---------------------------------------------------------------------------

def test_models_list_filters_passed_as_query() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json={"data": []})

    with _client(handler) as client:
        client.models.list(family="qwen3")
        assert "family=qwen3" in captured["url"]


def test_models_load_returns_typed_response() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/models/foo/load"
        assert req.method == "POST"
        return httpx.Response(200, json={
            "model_id": "foo", "status": "loaded",
            "adapter_id": "ad-1", "gpu_id": "gpu-0",
            "vram_allocated_bytes": 1234, "load_time_ms": 50,
        })

    with _client(handler) as client:
        r = client.models.load("foo")
        assert r.model_id == "foo"
        assert r.load_time_ms == 50


def test_models_benchmark_includes_kwargs_body() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content.decode())
        return httpx.Response(200, json={
            "model_id": "foo", "completed": True, "tokens_per_second": 42.0,
        })

    with _client(handler) as client:
        client.models.benchmark("foo", warmup=5)
        assert captured["body"] == {"warmup": 5}


# ---------------------------------------------------------------------------
# System / power / scheduler / updates
# ---------------------------------------------------------------------------

def test_power_get_state() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/power/state"
        return httpx.Response(200, json={
            "state": "full_inference",
            "estimated_power_watts": 220.0,
            "auto_demotion": {"enabled": False},
            "promotion_available": True,
            "promotion_latency_target_ms": 5000,
        })

    with _client(handler) as client:
        p = client.power.get_state()
        assert p.state == PowerState.FULL_INFERENCE


def test_power_transition_sends_request_body() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content.decode())
        return httpx.Response(200, json={
            "from_state": "sentinel",
            "to_state": "full_inference",
            "accepted": True,
            "estimated_latency_ms": 100,
        })

    with _client(handler) as client:
        r = client.power.transition(PowerTransitionRequest(
            target_state=PowerState.FULL_INFERENCE,
            reason="user request",
        ))
        assert r.accepted
        assert captured["body"]["target_state"] == "full_inference"


def test_scheduler_metrics_round_trip() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "queue_depth": 3, "active_requests": 2,
            "scheduled_total": 100, "rejected_total": 1,
            "avg_wait_ms": 12.0, "p95_wait_ms": 50.0,
            "instances": ["i1", "i2"],
        })

    with _client(handler) as client:
        m = client.scheduler.metrics()
        assert m.queue_depth == 3
        assert m.instances == ["i1", "i2"]


def test_system_airgap_status() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/system/airgap"
        return httpx.Response(200, json={
            "air_gap_enabled": True, "air_gap_verified": True,
            "network_state": "air_gap_compliant",
            "last_check_unix": 1700000000,
        })

    with _client(handler) as client:
        s = client.system.airgap()
        assert s.air_gap_verified


def test_updates_check_returns_list() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "updates_available": True,
            "updates": [{
                "component": "mai-server", "current_version": "1.0",
                "target_version": "1.1", "size_bytes": 1024, "signed": True,
            }],
            "checked_at_unix": 1700000000,
        })

    with _client(handler) as client:
        r = client.updates.check()
        assert r.updates_available
        assert r.updates[0].component == "mai-server"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

def test_401_maps_to_authentication_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {
            "code": "MAI-A001", "message": "bad key",
            "type": "authentication_failed",
        }})

    with _client(handler) as client:
        with pytest.raises(AuthenticationError) as ei:
            client.health()
        assert ei.value.status_code == 401


def test_404_maps_to_not_found() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {
            "code": "MAI-N001", "message": "no model",
            "type": "internal_error",
        }})

    with _client(handler) as client:
        with pytest.raises(NotFoundError):
            client.models.get("nope")


def test_500_maps_to_server_error_and_retries() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": {
            "code": "MAI-S001", "message": "boom",
            "type": "internal_error",
        }})

    # 5xx is retryable per the standard policy; exhausts max_retries=2 -> 3 calls
    with _client(handler, retry=RetryPolicy(max_retries=2, base_delay=0.0,
                                             max_delay=0.0, jitter=0.0)) as client:
        with pytest.raises(ServerError):
            client.models.list()
    assert calls["n"] == 3


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------

def test_429_retries_then_succeeds() -> None:
    counts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        counts["n"] += 1
        if counts["n"] < 3:
            return httpx.Response(429, json={"error": {
                "code": "MAI-R001", "message": "slow down",
                "type": "rate_limited", "retry_after_seconds": 0,
            }})
        return httpx.Response(200, json={"data": []})

    with _client(handler) as client:
        models = client.models.list()
        assert models == []
        assert counts["n"] == 3


def test_429_exhausts_retries_and_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {
            "code": "MAI-R001", "message": "limited",
            "type": "rate_limited", "retry_after_seconds": 0,
        }})

    with _client(handler) as client:
        with pytest.raises(RateLimitError):
            client.models.list()


def test_401_not_retried() -> None:
    counts = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        counts["n"] += 1
        return httpx.Response(401, json={"error": {
            "code": "MAI-A001", "message": "bad",
            "type": "authentication_failed",
        }})

    with _client(handler) as client:
        with pytest.raises(AuthenticationError):
            client.models.list()
    assert counts["n"] == 1


# ---------------------------------------------------------------------------
# Health and reachability
# ---------------------------------------------------------------------------

def test_health_check_returns_false_on_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    with _client(handler) as client:
        assert client.health_check() is False


# ---------------------------------------------------------------------------
# Trust stubs (BF-6 deferred)
# ---------------------------------------------------------------------------

def test_trust_namespace_methods_all_raise_stub() -> None:
    with _client(lambda _r: httpx.Response(200, json={})) as client:
        with pytest.raises(TrustNotProvisionedError):
            client.trust.claims()
        with pytest.raises(TrustNotProvisionedError):
            client.trust.bundle_status()
        with pytest.raises(TrustNotProvisionedError):
            client.trust.revocation_status("hash")


def test_compliance_namespace_raises_until_lamprey() -> None:
    with _client(lambda _r: httpx.Response(200, json={})) as client:
        with pytest.raises(NotImplementedError):
            _ = client.compliance.hipaa


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def test_from_env_constructs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAI_BASE_URL", "http://env:1234/v1")
    c = MaiClient.from_env()
    assert c._config.base_url == "http://env:1234/v1"
    c.close()


def test_namespaces_attached() -> None:
    with _client(lambda _r: httpx.Response(200)) as client:
        for ns in ("models", "power", "system", "scheduler",
                   "updates", "admin", "auth", "trust", "compliance"):
            assert hasattr(client, ns), f"missing namespace: {ns}"


def test_legacy_top_level_methods_still_work() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    with _client(handler) as client:
        assert client.list_models() == []


def test_streaming_error_raises_built_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {
            "code": "MAI-A001", "message": "bad key",
            "type": "authentication_failed",
        }})

    with _client(handler) as client:
        with pytest.raises(AuthenticationError):
            list(client.chat_stream("m", [ChatMessage(role="user", content="hi")]))
