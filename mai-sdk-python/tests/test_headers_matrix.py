"""Header construction matrix tests (robust assertions, many cases)."""

from __future__ import annotations

import pytest
from mai.config import MaiClientConfig


@pytest.mark.parametrize(
    ("api_key", "profile_id", "priority", "expect_auth_token", "expect_profile"),
    [
        ("k", None, "normal", True, False),
        # When api_key is set, profile header is intentionally omitted in the Python SDK.
        ("k", "admin:Admin", "normal", True, False),
        ("k", "kid:Child", "low", True, False),
        ("k", "", "high", True, False),
        (None, "admin:Admin", "critical", False, True),
        (None, "guest:Guest", "normal", False, True),
        (None, "", "normal", False, False),
        ("", "admin:Admin", "normal", False, True),  # empty api key should not count
        (
            "  ",
            "admin:Admin",
            "normal",
            True,
            False,
        ),  # whitespace is still a value (caller mistake)
    ],
)
def test_headers_matrix(
    api_key: str | None,
    profile_id: str | None,
    priority: str,
    expect_auth_token: bool,
    expect_profile: bool,
) -> None:
    cfg = MaiClientConfig(
        api_key=api_key if api_key else None,
        profile_id=profile_id,
        priority=priority,
    )
    headers = cfg.headers()
    assert headers["Content-Type"] == "application/json"
    assert headers["X-IM-Priority"] == priority

    if expect_auth_token:
        assert "X-IM-Auth-Token" in headers
    else:
        assert "X-IM-Auth-Token" not in headers

    if expect_profile:
        assert "X-IM-Profile" in headers
        assert isinstance(headers["X-IM-Profile"], str)
        assert headers["X-IM-Profile"] != ""
    else:
        assert "X-IM-Profile" not in headers


@pytest.mark.parametrize("priority", ["low", "normal", "high", "critical"])
def test_headers_always_include_priority(priority: str) -> None:
    cfg = MaiClientConfig(api_key="k", priority=priority)
    headers = cfg.headers()
    assert headers["X-IM-Priority"] == priority


def test_headers_do_not_mutate_config() -> None:
    cfg = MaiClientConfig(api_key="k", priority="high")
    before = (cfg.api_key, cfg.profile_id, cfg.priority, cfg.base_url)
    _ = cfg.headers()
    after = (cfg.api_key, cfg.profile_id, cfg.priority, cfg.base_url)
    assert before == after
