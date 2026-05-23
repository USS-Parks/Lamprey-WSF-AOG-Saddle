"""Shared dashboard helpers.

Centralises environment-driven config (API base URL, admin token) and
the SDK client factory so every dashboard page constructs a client
the same way.
"""

from __future__ import annotations

import os
from typing import Any

from mai.client import MaiClient
from mai.config import MaiClientConfig

# Headers documented in mai-api ``src/auth.rs``.
AUTH_TOKEN_HEADER = "X-IM-Auth-Token"

# Environment knobs (operator-configurable).
ENV_BASE_URL = "MAI_DASHBOARD_API_BASE_URL"
ENV_API_TOKEN = "MAI_DASHBOARD_API_TOKEN"
ENV_ADMIN_TOKEN = "MAI_DASHBOARD_ADMIN_TOKEN"

DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"


def api_base_url() -> str:
    """Return the mai-api base URL the dashboard talks to."""
    return os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)


def api_token() -> str | None:
    """Return the API key the dashboard uses to call mai-api."""
    return os.environ.get(ENV_API_TOKEN)


def admin_token() -> str:
    """Return the token the dashboard requires from operators.

    Defaults to ``dashboard-dev`` so local-dev "just works" without
    extra setup; production deployments must set
    ``MAI_DASHBOARD_ADMIN_TOKEN``.
    """
    return os.environ.get(ENV_ADMIN_TOKEN, "dashboard-dev")


def auth_headers(token: str | None = None) -> dict[str, str]:
    """Build the auth header dict for raw HTTP calls."""
    resolved = token or api_token()
    if not resolved:
        return {}
    return {AUTH_TOKEN_HEADER: resolved}


def build_client(
    *,
    base_url: str | None = None,
    api_token_override: str | None = None,
) -> MaiClient:
    """Construct a :class:`MaiClient` aimed at the configured mai-api."""
    cfg = MaiClientConfig(
        base_url=base_url or api_base_url(),
        api_token=api_token_override or api_token(),
    )
    return MaiClient(cfg)


def is_admin(headers: dict[str, str] | Any) -> bool:
    """Cheap admin gate for the dashboard.

    The dashboard is a thin operator console — the SDK still calls
    mai-api with its own API token, which the server validates against
    its own permissions table. This gate only protects the dashboard
    HTTP surface from drive-by visitors.
    """
    incoming = headers.get(AUTH_TOKEN_HEADER) if hasattr(headers, "get") else None
    return bool(incoming) and incoming == admin_token()


__all__ = [
    "AUTH_TOKEN_HEADER",
    "DEFAULT_BASE_URL",
    "ENV_ADMIN_TOKEN",
    "ENV_API_TOKEN",
    "ENV_BASE_URL",
    "admin_token",
    "api_base_url",
    "api_token",
    "auth_headers",
    "build_client",
    "is_admin",
]
