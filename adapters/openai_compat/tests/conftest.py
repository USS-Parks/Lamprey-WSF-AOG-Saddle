"""Adapter-local fixtures for the OpenAI-compatible local adapter.

Kept inside the adapter tree (not in the root ``conftest.py``) so the
J-23 session does not touch shared fixtures — see
``docs/ADAPTER-SHARED-CONTRACT.md`` §Ownership Rules For Parallel
Sessions and ``docs/ADAPTER-TEST-HARNESS-LOCK.md`` §Parallel Merge
Rules.

The ``live_backend`` mark itself is registered by the root conftest
(see ``mai/conftest.py``); this file only adds the per-backend
availability fixture used by the opt-in live tests.

DOUGHERTY J-23.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest


def _http_get_json(url: str, timeout_s: float) -> dict[str, Any] | None:
    """Single-shot GET that returns parsed JSON or None on any failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


@pytest.fixture(scope="session")
def openai_compat_available() -> dict[str, Any] | None:
    """Session-scoped check for a reachable OpenAI-compatible backend.

    Returns a dict with ``host`` (str — base URL), ``models``
    (list[str]), and ``model`` (str — the chat-capable model to use in
    live tests) when the backend is reachable; returns ``None``
    otherwise.

    Honoured env vars:
      OPENAI_COMPAT_HOST  — base URL of the backend (e.g.
                            ``http://127.0.0.1:1234``). Required.
      OPENAI_COMPAT_MODEL — specific chat model to use. When unset,
                            the first model returned by
                            ``GET /v1/models`` wins.
      OPENAI_COMPAT_EMBEDDING_MODEL
                          — specific embedding model id. When unset,
                            embedding live tests fall back to
                            ``OPENAI_COMPAT_MODEL`` and the adapter's
                            ``supports_embeddings`` flag.
    """
    host = os.environ.get("OPENAI_COMPAT_HOST")
    if not host:
        return None
    payload = _http_get_json(f"{host.rstrip('/')}/v1/models", timeout_s=3.0)
    if payload is None:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    models: list[str] = []
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and entry.get("id"):
                models.append(str(entry["id"]))
    if not models:
        return None
    preferred = os.environ.get("OPENAI_COMPAT_MODEL")
    model = preferred if preferred in models else models[0]
    return {"host": host, "models": models, "model": model}
