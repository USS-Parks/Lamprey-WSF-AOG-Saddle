"""Smoke tests: each pipeline step in isolation + BF-6 stub fallbacks."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from mai import MaiClient, MaiClientConfig
from mai.retry import RetryPolicy

APP_ROOT = Path(__file__).resolve().parents[1]


def _load_main():
    spec = importlib.util.spec_from_file_location(
        "openbao_trust_demo_main", APP_ROOT / "main.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _mk_client(handler: Callable[[httpx.Request], httpx.Response]) -> MaiClient:
    cfg = MaiClientConfig(
        base_url="http://test/v1",
        retry=RetryPolicy(max_retries=0, base_delay=0.0, jitter=0.0),
    )
    c = MaiClient(cfg)
    c._http = httpx.Client(
        base_url=cfg.base_url, headers=cfg.headers(),
        timeout=cfg.timeout, transport=httpx.MockTransport(handler),
    )
    return c


# --- step 1: bridge authentication ----------------------------------------

def test_simulate_bridge_authentication_shape() -> None:
    main = _load_main()
    bridge_cfg = {
        "service_identity": "openbao-trust-bridge",
        "trust_bundle_version": "local-dev-v1",
        "claim_ttl_seconds": 300,
    }
    claim_cfg = {
        "tenant_id": "im-demo", "subject_id": "alice@example.com",
        "roles": ["operator"], "compliance_scopes": ["pii"],
        "allowed_routes": ["local_only"], "allowed_models": [],
        "max_data_classification": "confidential",
    }
    result = main.simulate_bridge_authentication(
        bridge_cfg, claim_cfg, now=1_700_000_000,
    )
    assert result.issued_at == 1_700_000_000
    assert result.expires_at == 1_700_000_300
    claim = result.claim
    assert claim.tenant_id == "im-demo"
    assert claim.allowed_routes == ["local_only"]
    assert claim.service_identity == "openbao-trust-bridge"
    assert claim.trust_bundle_version == "local-dev-v1"
    assert claim.subject_hash.startswith("sha256:")
    assert claim.claim_id.startswith("claim-")
    # subject_hash must NOT echo the raw subject_id
    assert "alice@example.com" not in claim.subject_hash


def test_subject_hash_is_stable_and_collision_aware() -> None:
    main = _load_main()
    a = main._subject_hash("tenant-a", "alice@example.com")
    a2 = main._subject_hash("tenant-a", "alice@example.com")
    b = main._subject_hash("tenant-b", "alice@example.com")
    assert a == a2  # deterministic
    assert a != b  # tenant scopes the hash


# --- step 2: audit correlation --------------------------------------------

def test_audit_correlation_id_format() -> None:
    main = _load_main()
    result = main.simulate_bridge_authentication(
        {"claim_ttl_seconds": 60}, {"tenant_id": "t", "subject_id": "s"},
    )
    cid = main.audit_correlation_id(result.claim, "openbao-demo")
    assert cid.startswith("openbao-demo-claim-")
    assert result.claim.claim_id in cid


# --- step 3: trust bundle stub fallback -----------------------------------

def test_check_local_trust_bundle_falls_back_on_bf6_stub() -> None:
    main = _load_main()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})  # not called — SDK raises

    with _mk_client(handler) as client:
        snap = main.check_local_trust_bundle(client, "local-dev-v1")
    assert snap.state == "stub"
    assert snap.bundle_version == "local-dev-v1"
    assert snap.connectivity == "air_gapped"
    assert snap.signature_verified is False
    assert "not yet provisioned" in snap.detail.lower() or snap.detail


# --- step 4: token exchange stub fallback ---------------------------------

def test_exchange_for_session_token_falls_back_on_bf6_stub() -> None:
    main = _load_main()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    result = main.simulate_bridge_authentication(
        {"claim_ttl_seconds": 60}, {"tenant_id": "t", "subject_id": "s"},
    )
    with _mk_client(handler) as client:
        token = main.exchange_for_session_token(client, result.claim)
    assert token.startswith("bf6-pending:")
    assert result.claim.claim_id in token


# --- step 5: lamprey metadata payload -------------------------------------

def test_build_lamprey_metadata_carries_all_audit_fields() -> None:
    main = _load_main()
    result = main.simulate_bridge_authentication(
        {"service_identity": "openbao-trust-bridge",
         "trust_bundle_version": "v9", "claim_ttl_seconds": 60},
        {"tenant_id": "im-demo", "subject_id": "s",
         "allowed_routes": ["local_only"]},
    )
    bundle = main.BundleSnapshot(
        state="stub", bundle_version="v9", connectivity="air_gapped",
        signature_verified=False,
    )
    cid = main.audit_correlation_id(result.claim, "openbao-demo")
    md = main.build_lamprey_metadata(
        result.claim, bundle=bundle, correlation_id=cid,
        route_decision="local_only",
    )
    assert md.claim_id == result.claim.claim_id
    assert md.tenant_id == "im-demo"
    assert md.service_identity == "openbao-trust-bridge"
    assert md.trust_bundle_version == "v9"
    assert md.route_decision == "local_only"
    assert md.correlation_id == cid
    assert md.bundle_state == "stub"


# --- step 7: audit summary JSON shape -------------------------------------

def test_print_audit_summary_emits_valid_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main = _load_main()
    result = main.simulate_bridge_authentication(
        {"claim_ttl_seconds": 60}, {"tenant_id": "t", "subject_id": "s"},
    )
    bundle = main.BundleSnapshot(
        state="stub", bundle_version="v1", connectivity="air_gapped",
        signature_verified=False,
    )
    cid = main.audit_correlation_id(result.claim, "p")
    md = main.build_lamprey_metadata(result.claim, bundle=bundle,
                                     correlation_id=cid)
    main.print_audit_summary(md)
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["claim_id"] == result.claim.claim_id
    assert parsed["bundle_state"] == "stub"
    assert parsed["correlation_id"] == cid


# --- end-to-end dry-run via run() ----------------------------------------

def test_run_dry_run_skips_inference(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    main = _load_main()
    chat_calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        chat_calls.append(req.url.path)
        return httpx.Response(500, json={"error": {
            "code": "MAI-X", "message": "should not be called",
            "type": "internal_error",
        }})

    monkeypatch.setattr(main, "_make_client",
                        lambda _cfg: _mk_client(handler))

    rc = main.run(config_path=APP_ROOT / "config.toml", dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    # No chat completion should have been sent in dry-run.
    assert "/v1/chat/completions" not in chat_calls
    parsed = json.loads(out)
    assert parsed["bundle_state"] == "stub"
    assert parsed["route_decision"] == "local_only"
    assert parsed["service_identity"] == "openbao-trust-bridge"


def test_config_loader_handles_missing_file() -> None:
    main = _load_main()
    data = main.load_app_config(APP_ROOT / "does-not-exist.toml")
    assert data == {}


def test_config_loader_reads_real_file() -> None:
    main = _load_main()
    data = main.load_app_config(APP_ROOT / "config.toml")
    assert "bridge" in data
    assert "claim" in data
    assert "audit" in data
    assert data["claim"]["tenant_id"] == "im-demo"
    assert data["bridge"]["service_identity"] == "openbao-trust-bridge"
