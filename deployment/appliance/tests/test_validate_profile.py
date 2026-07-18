"""Regression tests for the appliance trust-plane profile validator (PSPR-01, AF-12).

Each unsafe fixture must be rejected with a specific rule; the secure fixture and
the hardened appliance demo must pass their intended profile; and the appliance
demo must still be rejected as production (it runs dev mode by design).
"""

from pathlib import Path

import pytest
import validate_profile as vp

_APPLIANCE = Path(__file__).resolve().parent.parent
FIXTURES = _APPLIANCE / "fixtures"
APPLIANCE_COMPOSE = _APPLIANCE / "docker-compose.yml"


def _rules(path: Path, profile: str) -> set[str]:
    return {v.rule for v in vp.validate(vp.load_compose(path), profile)}


def _unsafe_profile(case: str) -> dict:
    """Create each excluded negative profile in memory with no fixture file.

    The original YAML fixtures were deliberately excluded by SAD-03 because
    they contain unsafe credential-shaped values. These test-only profiles
    recreate the validator condition without materializing a runtime file.
    """
    injected = "${SADDLE_EPHEMERAL_TEST_TOKEN:?generated at test runtime}"
    if case == "prod-dev-mode":
        return {
            "services": {
                "openbao": {
                    "image": "openbao/openbao:latest",
                    "command": ["server", "-dev", "-dev-listen-address=0.0.0.0:8200"],
                }
            }
        }
    if case == "prod-known-token":
        return {
            "services": {
                "openbao": {"image": "openbao/openbao:2.1.0", "command": ["server"]},
                "seed": {"environment": {"WSF_OPENBAO_TOKEN": "root"}},
            }
        }
    if case == "prod-host-published":
        return {
            "services": {
                "openbao": {
                    "image": "openbao/openbao:2.1.0",
                    "command": ["server"],
                    "environment": {"BAO_ROOT_TOKEN": injected},
                    "ports": ["8200:8200"],
                }
            }
        }
    if case == "demo-nonloopback":
        return {
            "services": {
                "openbao": {
                    "image": "openbao/openbao:latest",
                    "profiles": ["demo"],
                    "command": ["server", "-dev", f"-dev-root-token-id={injected}"],
                    "ports": ["8200:8200"],
                }
            }
        }
    if case == "demo-baked-token":
        return {
            "services": {
                "openbao": {
                    "image": "openbao/openbao:latest",
                    "profiles": ["demo"],
                    "command": ["server", "-dev", "-dev-root-token-id=root"],
                    "ports": ["127.0.0.1:8200:8200"],
                }
            }
        }
    if case == "demo-not-gated":
        return {
            "services": {
                "openbao": {
                    "image": "openbao/openbao:latest",
                    "command": ["server", "-dev", f"-dev-root-token-id={injected}"],
                    "ports": ["127.0.0.1:8200:8200"],
                }
            }
        }
    raise ValueError(f"unknown unsafe profile case: {case}")


@pytest.mark.parametrize(
    ("case", "profile", "expected_rule"),
    [
        ("prod-dev-mode", "production", "dev-mode"),
        ("prod-known-token", "production", "weak-credential"),
        ("prod-host-published", "production", "host-published-trust"),
        ("demo-nonloopback", "demo", "trust-exposed-nonloopback"),
        ("demo-baked-token", "demo", "weak-token"),
        ("demo-not-gated", "demo", "demo-not-gated"),
    ],
)
def test_unsafe_fixture_is_rejected(case: str, profile: str, expected_rule: str) -> None:
    rules = {violation.rule for violation in vp.validate(_unsafe_profile(case), profile)}
    assert expected_rule in rules, f"{case} ({profile}): expected {expected_rule}, got {rules}"


def test_secure_production_fixture_passes() -> None:
    assert _rules(FIXTURES / "secure-production.yml", "production") == set()


def _rules_inline(compose: dict, profile: str) -> set[str]:
    return {v.rule for v in vp.validate(compose, profile)}


def test_trust_core_detected_via_entrypoint() -> None:
    # A retagged image whose only tell is the entrypoint must not evade
    # dev-mode detection.
    compose = {
        "services": {
            "kv": {
                "image": "registry.internal/kv-store:1",
                "entrypoint": ["/usr/local/bin/bao", "server", "-dev"],
            }
        }
    }
    assert "dev-mode" in _rules_inline(compose, "production")


def test_trust_core_detected_via_server_env_marker() -> None:
    compose = {
        "services": {
            "kv": {
                "image": "registry.internal/kv-store:1",
                "environment": {"BAO_LOCAL_CONFIG": "{}"},
                "ports": ["8200:8200"],
            }
        }
    }
    assert "host-published-trust" in _rules_inline(compose, "production")


def test_production_rejects_any_host_published_trust_port() -> None:
    # The cluster port (8201) is as much an exposure as the API port.
    compose = {
        "services": {
            "openbao": {
                "image": "openbao/openbao:latest",
                "command": "server",
                "ports": ["8201:8201"],
            }
        }
    }
    assert "host-published-trust" in _rules_inline(compose, "production")


def test_demo_rejects_nonloopback_on_any_trust_port() -> None:
    compose = {
        "services": {
            "openbao": {
                "image": "openbao/openbao:latest",
                "profiles": ["demo"],
                "command": "server -dev -dev-root-token-id=${TOKEN:?required}",
                "ports": ["0.0.0.0:8201:8201"],
            }
        }
    }
    assert "trust-exposed-nonloopback" in _rules_inline(compose, "demo")


def test_appliance_demo_passes_demo_profile() -> None:
    assert _rules(APPLIANCE_COMPOSE, "demo") == set()


def test_appliance_demo_is_rejected_as_production() -> None:
    assert "dev-mode" in _rules(APPLIANCE_COMPOSE, "production")


# The real shipped compositions — the same assertions CI runs
# (ship-validation.yml, compose-trust-validation job).

def test_wsf_ha_passes_production_profile() -> None:
    assert _rules(_APPLIANCE.parent / "wsf-ha" / "docker-compose.yml", "production") == set()


def test_shadow_passes_demo_and_is_rejected_as_production() -> None:
    shadow = _APPLIANCE.parent / "shadow" / "docker-compose.yml"
    assert _rules(shadow, "demo") == set()
    assert "dev-mode" in _rules(shadow, "production")


def test_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        vp.validate({"services": {}}, "staging")
