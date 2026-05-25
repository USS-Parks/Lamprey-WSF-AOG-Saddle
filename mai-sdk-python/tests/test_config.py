"""Configuration loader precedence and parsing."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from mai.config import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    MaiClientConfig,
)
from mai.retry import RetryPolicy


@pytest.fixture()
def tmp_dir() -> Path:
    base = Path("py_tmp_dir")
    base.mkdir(exist_ok=True)
    p = base / f"mai-sdk-python-tests-{uuid.uuid4().hex}"
    p.mkdir(parents=True, exist_ok=False)
    yield p


def test_defaults_when_nothing_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(os.environ):
        if k.startswith("MAI_"):
            monkeypatch.delenv(k, raising=False)
    cfg = MaiClientConfig()
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.timeout == DEFAULT_TIMEOUT
    assert cfg.api_key is None


def test_headers_with_api_key() -> None:
    cfg = MaiClientConfig(api_key="im-secret")
    h = cfg.headers()
    assert h["X-IM-Auth-Token"] == "im-secret"
    assert "X-IM-Profile" not in h


def test_headers_fallback_to_profile() -> None:
    cfg = MaiClientConfig(profile_id="11111111-1111-1111-1111-111111111111")
    h = cfg.headers()
    assert h["X-IM-Profile"].startswith("11111111")


def test_from_env_reads_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAI_BASE_URL", "http://example:9000/v1")
    monkeypatch.setenv("MAI_API_KEY", "im-env")
    monkeypatch.setenv("MAI_TIMEOUT", "12.5")
    monkeypatch.setenv("MAI_MAX_RETRIES", "7")
    cfg = MaiClientConfig.from_env()
    assert cfg.base_url == "http://example:9000/v1"
    assert cfg.api_key == "im-env"
    assert cfg.timeout == 12.5
    assert cfg.retry.max_retries == 7


def test_from_env_overrides_take_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAI_API_KEY", "im-env")
    cfg = MaiClientConfig.from_env(api_key="im-override")
    assert cfg.api_key == "im-override"


def test_from_file_reads_toml(tmp_dir: Path) -> None:
    p = tmp_dir / "cfg.toml"
    p.write_text(
        'base_url = "http://file:8000/v1"\n'
        'api_key = "im-file"\n'
        'timeout = 45.0\n'
        '[retry]\n'
        'max_retries = 5\n'
        'base_delay = 2.0\n'
    )
    cfg = MaiClientConfig.from_file(p)
    assert cfg.base_url == "http://file:8000/v1"
    assert cfg.api_key == "im-file"
    assert cfg.timeout == 45.0
    assert cfg.retry.max_retries == 5
    assert cfg.retry.base_delay == 2.0


def test_load_precedence_overrides_beat_env_beat_file(
    tmp_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = tmp_dir / "cfg.toml"
    p.write_text('base_url = "http://file/v1"\napi_key = "im-file"\n')
    monkeypatch.setenv("MAI_API_KEY", "im-env")
    cfg = MaiClientConfig.load(p, api_key="im-override")
    assert cfg.api_key == "im-override"
    # base_url not in env, comes from file
    assert cfg.base_url == "http://file/v1"


def test_load_handles_missing_file_gracefully(
    monkeypatch: pytest.MonkeyPatch, tmp_dir: Path,
) -> None:
    for k in list(os.environ):
        if k.startswith("MAI_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HOME", str(tmp_dir))  # no default file there
    cfg = MaiClientConfig.load()
    assert cfg.base_url == DEFAULT_BASE_URL


def test_legacy_max_retries_accessor() -> None:
    cfg = MaiClientConfig(retry=RetryPolicy(max_retries=9))
    assert cfg.max_retries == 9
