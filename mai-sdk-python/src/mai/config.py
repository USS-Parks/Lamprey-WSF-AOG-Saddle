"""MAI SDK configuration loader.

Three precedence layers (highest wins):

    1. Constructor kwargs / explicit overrides
    2. Environment variables (``MAI_BASE_URL``, ``MAI_API_KEY``, ...)
    3. TOML config file (``$MAI_CONFIG`` or ``~/.config/mai/config.toml``)
    4. Built-in defaults

Environment variables recognized:

    MAI_BASE_URL           base URL (e.g. http://localhost:8420/v1)
    MAI_API_KEY            bearer token sent as X-IM-Auth-Token
    MAI_PROFILE_ID         legacy profile id
    MAI_PRIORITY           low|normal|high|critical
    MAI_TIMEOUT            request timeout, seconds
    MAI_STREAM_TIMEOUT     streaming timeout, seconds
    MAI_MAX_RETRIES        integer
    MAI_RETRY_BASE_DELAY   seconds
    MAI_CONFIG             explicit path to TOML config
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from mai.retry import DEFAULT_RETRY_POLICY, RetryPolicy

DEFAULT_BASE_URL = "http://localhost:8420/v1"
DEFAULT_TIMEOUT = 60.0
DEFAULT_STREAM_TIMEOUT = 300.0
DEFAULT_PRIORITY = "normal"


class MaiClientConfig:
    """Client configuration (preferred construction via classmethods).

    Use :meth:`from_env`, :meth:`from_file`, or :meth:`load` for the
    standard precedence chain. Direct construction is fine when you
    have all values to hand.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        profile_id: str | None = None,
        priority: str = DEFAULT_PRIORITY,
        timeout: float = DEFAULT_TIMEOUT,
        stream_timeout: float = DEFAULT_STREAM_TIMEOUT,
        retry: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.profile_id = profile_id
        self.priority = priority
        self.timeout = timeout
        self.stream_timeout = stream_timeout
        self.retry = retry

    def headers(self) -> dict[str, str]:
        """Build common request headers."""
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-IM-Auth-Token"] = self.api_key
        elif self.profile_id:
            h["X-IM-Profile"] = self.profile_id
        h["X-IM-Priority"] = self.priority
        return h

    @property
    def max_retries(self) -> int:
        """Backwards-compatible accessor for retry.max_retries."""
        return self.retry.max_retries

    @property
    def retry_base_delay(self) -> float:
        """Backwards-compatible accessor for retry.base_delay."""
        return self.retry.base_delay

    # --- Factories -----------------------------------------------------

    @classmethod
    def from_env(cls, **overrides: Any) -> MaiClientConfig:
        """Build config from environment variables and optional overrides."""
        kwargs = _kwargs_from_env()
        kwargs.update(overrides)
        return cls(**kwargs)

    @classmethod
    def from_file(cls, path: str | Path, **overrides: Any) -> MaiClientConfig:
        """Build config from a TOML file plus optional overrides.

        File layout::

            base_url = "http://localhost:8420/v1"
            api_key  = "im-..."
            priority = "normal"
            timeout  = 60.0

            [retry]
            max_retries = 3
            base_delay  = 1.0
            max_delay   = 30.0
            jitter      = 0.25
        """
        p = Path(path).expanduser()
        with p.open("rb") as fh:
            raw = tomllib.load(fh)
        kwargs = _kwargs_from_toml(raw)
        kwargs.update(overrides)
        return cls(**kwargs)

    @classmethod
    def load(cls, path: str | Path | None = None, **overrides: Any) -> MaiClientConfig:
        """Full precedence chain: overrides > env > file > defaults.

        If ``path`` is ``None``, the loader checks ``$MAI_CONFIG`` and
        then ``~/.config/mai/config.toml``; if neither exists, the file
        layer is skipped.
        """
        candidate = _resolve_config_path(path)

        file_kwargs: dict[str, Any] = {}
        if candidate is not None:
            with candidate.open("rb") as fh:
                file_kwargs = _kwargs_from_toml(tomllib.load(fh))

        env_kwargs = _kwargs_from_env()

        # Layer with explicit precedence (each layer only sets keys it provides)
        merged: dict[str, Any] = dict(file_kwargs)
        merged.update(env_kwargs)
        merged.update(overrides)
        return cls(**merged)


def _kwargs_from_env() -> dict[str, Any]:
    """Pull only the keys actually present in the environment."""
    kwargs: dict[str, Any] = {}
    env = os.environ
    if "MAI_BASE_URL" in env:
        kwargs["base_url"] = env["MAI_BASE_URL"]
    if "MAI_API_KEY" in env:
        kwargs["api_key"] = env["MAI_API_KEY"]
    if "MAI_PROFILE_ID" in env:
        kwargs["profile_id"] = env["MAI_PROFILE_ID"]
    if "MAI_PRIORITY" in env:
        kwargs["priority"] = env["MAI_PRIORITY"]
    if "MAI_TIMEOUT" in env:
        kwargs["timeout"] = float(env["MAI_TIMEOUT"])
    if "MAI_STREAM_TIMEOUT" in env:
        kwargs["stream_timeout"] = float(env["MAI_STREAM_TIMEOUT"])
    retry = _retry_from_env()
    if retry is not None:
        kwargs["retry"] = retry
    return kwargs


def _retry_from_env() -> RetryPolicy | None:
    env = os.environ
    keys = ("MAI_MAX_RETRIES", "MAI_RETRY_BASE_DELAY",
            "MAI_RETRY_MAX_DELAY", "MAI_RETRY_JITTER")
    if not any(k in env for k in keys):
        return None
    return RetryPolicy(
        max_retries=int(env.get("MAI_MAX_RETRIES", DEFAULT_RETRY_POLICY.max_retries)),
        base_delay=float(env.get("MAI_RETRY_BASE_DELAY", DEFAULT_RETRY_POLICY.base_delay)),
        max_delay=float(env.get("MAI_RETRY_MAX_DELAY", DEFAULT_RETRY_POLICY.max_delay)),
        jitter=float(env.get("MAI_RETRY_JITTER", DEFAULT_RETRY_POLICY.jitter)),
    )


def _kwargs_from_toml(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("base_url", "api_key", "profile_id", "priority"):
        if key in data:
            out[key] = data[key]
    for key in ("timeout", "stream_timeout"):
        if key in data:
            out[key] = float(data[key])
    if "retry" in data and isinstance(data["retry"], dict):
        r = data["retry"]
        out["retry"] = RetryPolicy(
            max_retries=int(r.get("max_retries", DEFAULT_RETRY_POLICY.max_retries)),
            base_delay=float(r.get("base_delay", DEFAULT_RETRY_POLICY.base_delay)),
            max_delay=float(r.get("max_delay", DEFAULT_RETRY_POLICY.max_delay)),
            jitter=float(r.get("jitter", DEFAULT_RETRY_POLICY.jitter)),
        )
    return out


def _resolve_config_path(explicit: str | Path | None) -> Path | None:
    if explicit is not None:
        p = Path(explicit).expanduser()
        return p if p.exists() else None
    if "MAI_CONFIG" in os.environ:
        p = Path(os.environ["MAI_CONFIG"]).expanduser()
        if p.exists():
            return p
    default = Path.home() / ".config" / "mai" / "config.toml"
    return default if default.exists() else None


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_PRIORITY",
    "DEFAULT_STREAM_TIMEOUT",
    "DEFAULT_TIMEOUT",
    "MaiClientConfig",
]
