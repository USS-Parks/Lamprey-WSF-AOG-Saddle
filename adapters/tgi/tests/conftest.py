"""Adapter-local pytest fixtures for the TGI adapter.

Kept inside ``adapters/tgi/tests/`` per the parallel-session ownership
rule in ``docs/ADAPTER-SHARED-CONTRACT.md``: J-19 does not touch the
root ``mai/conftest.py`` to avoid merge collisions with J-18..J-26.

The ``tgi_available`` fixture probes ``$TGI_HOST/health`` and returns a
dict with the resolved host when TGI is reachable; ``None`` otherwise.
``test_integration_live.py`` consumes it through an ``autouse`` guard.

DOUGHERTY J-19.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest


def _http_get_text(url: str, timeout_s: float) -> str | None:
    """Single-shot GET that returns the response body as text, or ``None``
    on any failure (refused connection, timeout, non-2xx).

    Stdlib-only (no httpx) to keep the fixture air-gap-policy compliant.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


@pytest.fixture(scope="session")
def tgi_available() -> dict[str, Any] | None:
    """Session-scoped reachability check for an HF TGI backend.

    Returns ``{"host": ..., "model_id": ...}`` when ``$TGI_HOST/health``
    answers 200; returns ``None`` when ``TGI_HOST`` is unset or the
    backend is unreachable, in which case the live tests skip cleanly.

    Honoured env vars:
      ``TGI_HOST``       - base URL of the TGI server, e.g.
                          ``http://127.0.0.1:8080``. When unset, this
                          fixture returns ``None`` and live tests skip.
      ``TGI_LIVE_MODEL`` - informational override for the model id used
                          in test logs. The TGI server itself serves a
                          single model per process; this string does not
                          select it.
    """
    host = os.environ.get("TGI_HOST")
    if not host:
        return None

    base = host.rstrip("/")
    if _http_get_text(f"{base}/health", timeout_s=2.0) is None:
        return None

    info_text = _http_get_text(f"{base}/info", timeout_s=2.0) or "{}"
    try:
        info = json.loads(info_text)
    except json.JSONDecodeError:
        info = {}
    if not isinstance(info, dict):
        info = {}

    model_id = (
        os.environ.get("TGI_LIVE_MODEL")
        or info.get("model_id")
        or "unknown"
    )

    return {"host": host, "model_id": model_id, "info": info}
