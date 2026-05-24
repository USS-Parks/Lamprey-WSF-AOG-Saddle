"""Adapter-local conftest for SGLang tests.

Defines the `sglang_available` fixture used by `test_integration_live.py`.
Kept here (not in the root `conftest.py`) so the J-18..J-26 parallel
adapter sessions never collide on a shared fixtures file.

J-20 (DOUGHERTY lane).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest


def _http_get_json(url: str, timeout_s: float) -> dict[str, Any] | None:
    """Single-shot GET that returns parsed JSON or None on any failure.
    Stdlib-only so the fixture has no third-party dependency."""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _http_get_ok(url: str, timeout_s: float) -> bool:
    """SGLang's /health may return 200 with an empty body or a JSON
    object — we just need to know the endpoint is reachable."""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@pytest.fixture(scope="session")
def sglang_available() -> dict[str, Any] | None:
    """Session-scoped probe for a reachable SGLang backend.

    Returns a dict with `host` (str), `models` (list[str]), and `model`
    (str — first model id from /v1/models) when reachable; None
    otherwise. Tests use it to skip cleanly when SGLang is not running.

    Honoured env vars:
      SGLANG_HOST       — base URL of the SGLang server (e.g.
                          `http://127.0.0.1:30000`). When unset,
                          this fixture returns None and live tests skip.
      SGLANG_LIVE_MODEL — specific model id to use in tests. When
                          unset, the first id returned by /v1/models wins.
    """
    host = os.environ.get("SGLANG_HOST")
    if not host:
        return None

    if not _http_get_ok(f"{host.rstrip('/')}/health", timeout_s=2.0):
        return None

    models_body = _http_get_json(f"{host.rstrip('/')}/v1/models", timeout_s=2.0)
    if models_body is None or not isinstance(models_body.get("data"), list):
        return None

    models = [
        m.get("id", "") for m in models_body["data"] if isinstance(m, dict)
    ]
    models = [m for m in models if m]
    if not models:
        return None

    preferred = os.environ.get("SGLANG_LIVE_MODEL")
    model = preferred if preferred in models else models[0]
    return {"host": host, "models": models, "model": model}
