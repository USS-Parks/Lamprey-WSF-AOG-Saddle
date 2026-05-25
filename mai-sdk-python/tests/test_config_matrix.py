"""Additional configuration parsing matrix tests.

These tests intentionally expand coverage for:
  - env parsing failures (invalid numeric inputs)
  - base_url normalization behavior
  - retry env partial-key handling
"""

from __future__ import annotations

import os

import pytest

from mai.config import DEFAULT_BASE_URL, MaiClientConfig


def _clear_mai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(os.environ):
        if k.startswith("MAI_"):
            monkeypatch.delenv(k, raising=False)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:8420/v1", "http://localhost:8420/v1"),
        ("http://localhost:8420/v1/", "http://localhost:8420/v1"),
        ("http://localhost:8420/", "http://localhost:8420"),
        ("http://localhost:8420", "http://localhost:8420"),
        ("http://127.0.0.1:8420/v1///", "http://127.0.0.1:8420/v1"),
    ],
)
def test_base_url_is_rstripped(raw: str, expected: str) -> None:
    cfg = MaiClientConfig(base_url=raw, api_key="k")
    assert cfg.base_url == expected


@pytest.mark.parametrize(
    "env_value",
    ["", " ", "abc", "1,0", "NaNish", "1.0.0"],
)
def test_timeout_from_env_invalid_raises(
    env_value: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mai_env(monkeypatch)
    monkeypatch.setenv("MAI_TIMEOUT", env_value)
    with pytest.raises(ValueError):
        MaiClientConfig.from_env()


@pytest.mark.parametrize(
    "env_value",
    ["", " ", "abc", "1,0", "NaNish", "1.0.0"],
)
def test_stream_timeout_from_env_invalid_raises(
    env_value: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mai_env(monkeypatch)
    monkeypatch.setenv("MAI_STREAM_TIMEOUT", env_value)
    with pytest.raises(ValueError):
        MaiClientConfig.from_env()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MAI_MAX_RETRIES", "not-an-int"),
        ("MAI_MAX_RETRIES", "1.5"),
        ("MAI_RETRY_BASE_DELAY", "nope"),
        ("MAI_RETRY_MAX_DELAY", "nope"),
        ("MAI_RETRY_JITTER", "nope"),
    ],
)
def test_retry_env_invalid_values_raise(
    key: str, value: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mai_env(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        MaiClientConfig.from_env()


@pytest.mark.parametrize(
    "set_key",
    ["MAI_MAX_RETRIES", "MAI_RETRY_BASE_DELAY", "MAI_RETRY_MAX_DELAY", "MAI_RETRY_JITTER"],
)
def test_retry_env_partial_keys_use_defaults(
    set_key: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_mai_env(monkeypatch)
    monkeypatch.setenv(set_key, "2" if "RETRIES" in set_key else "2.0")
    cfg = MaiClientConfig.from_env()
    # Should be a concrete retry policy object (not None) and values should be numeric.
    assert isinstance(cfg.retry.max_retries, int)
    assert isinstance(cfg.retry.base_delay, float)
    assert isinstance(cfg.retry.max_delay, float)
    assert isinstance(cfg.retry.jitter, float)


def test_from_env_does_not_require_any_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mai_env(monkeypatch)
    cfg = MaiClientConfig.from_env()
    assert cfg.base_url == DEFAULT_BASE_URL.rstrip("/")

