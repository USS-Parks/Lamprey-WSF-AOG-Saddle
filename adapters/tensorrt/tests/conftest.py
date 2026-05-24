"""Local conftest for TensorRT adapter tests.

Provides the ``tensorrt_available`` session-scoped fixture used by
``test_integration_live.py``. Kept in the adapter-owned tree per
``docs/ADAPTER-SHARED-CONTRACT.md`` (J-22 must not edit the shared
``mai/conftest.py`` -- parallel adapter sessions cannot all touch it).

The fixture honours both ``TENSORRT_HOST`` (preferred, matches the
harness lock) and ``TRITON_TENSORRT_HOST`` (alias for operators who
already have a Triton-shaped env var).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest


def _http_get_json(url: str, timeout_s: float) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


@pytest.fixture(scope="session")
def tensorrt_available() -> dict[str, Any] | None:
    """Session-scoped readiness check for a live Triton + TensorRT-LLM backend.

    Returns ``{"host": <url>, "model": <model>}`` if the backend is
    reachable and the requested model is ready; ``None`` otherwise.
    Live tests use this fixture to skip cleanly when no backend is
    provisioned.

    Honoured env vars (in order of precedence):
        TENSORRT_HOST          -- base URL, e.g. ``http://127.0.0.1:8000``
        TRITON_TENSORRT_HOST   -- alias for operator parity with Triton docs
        TENSORRT_MODEL         -- Triton model name (default: ``ensemble``)
    """
    host = os.environ.get("TENSORRT_HOST") or os.environ.get("TRITON_TENSORRT_HOST")
    if not host:
        return None
    host = host.rstrip("/")

    if _http_get_json(f"{host}/v2/health/ready", timeout_s=2.0) is None:
        return None

    model = os.environ.get("TENSORRT_MODEL", "ensemble")
    if _http_get_json(f"{host}/v2/models/{model}/ready", timeout_s=2.0) is None:
        return None

    return {"host": host, "model": model}
