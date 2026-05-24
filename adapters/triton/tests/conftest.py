"""Adapter-local conftest for the generic Triton tests.

The ``triton_available`` fixture is intentionally local to this adapter
(not in the root ``conftest.py``) to keep parallel J-18..J-26 sessions
from racing on the shared file. Convergence may roll it up later.

Honoured env vars:
  TRITON_HOST          base URL of a live Triton server, e.g.
                       ``http://127.0.0.1:8000``. When unset, this
                       fixture returns ``None`` and live tests skip.
  TRITON_MODEL_NAME    a model loaded by that server. Required when
                       ``TRITON_HOST`` is set.
  TRITON_MODEL_VERSION optional explicit version. Defaults to empty
                       (Triton picks the latest).
  TRITON_INPUT_TENSOR  required to exercise the text generate path;
                       leave unset to skip the text-IO live cases.
  TRITON_OUTPUT_TENSOR required alongside TRITON_INPUT_TENSOR.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest


def _http_get_json(url: str, timeout_s: float) -> dict[str, Any] | None:
    """Single-shot GET that returns parsed JSON or ``None`` on any failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return None
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


@pytest.fixture(scope="session")
def triton_available() -> dict[str, Any] | None:
    """Session-scoped reachability check for a live Triton server.

    Returns a dict with ``host``, ``model``, ``version``,
    ``input_tensor`` (str | None), ``output_tensor`` (str | None) when
    Triton is reachable; otherwise ``None``.
    """
    host = os.environ.get("TRITON_HOST")
    if not host:
        return None

    model = os.environ.get("TRITON_MODEL_NAME")
    if not model:
        return None

    ready = _http_get_json(f"{host.rstrip('/')}/v2/health/ready", timeout_s=2.0)
    if ready is None:
        # /v2/health/ready may return an empty 200 body. Treat that as ready.
        # If the URL itself failed, retry with /v2 metadata to disambiguate.
        meta = _http_get_json(f"{host.rstrip('/')}/v2", timeout_s=2.0)
        if meta is None:
            return None

    return {
        "host": host,
        "model": model,
        "version": os.environ.get("TRITON_MODEL_VERSION", ""),
        "input_tensor": os.environ.get("TRITON_INPUT_TENSOR"),
        "output_tensor": os.environ.get("TRITON_OUTPUT_TENSOR"),
    }
