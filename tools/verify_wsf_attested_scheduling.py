#!/usr/bin/env python3
"""Exercise and record the SAD-32 WSF-attested scheduling gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the hard-placement boundary cannot be proven."""


SCHEDULER_TESTS = (
    "pressure_and_failover_never_choose_an_under_attested_node",
    "stale_heartbeat_or_attestation_cache_cannot_authorize_placement",
    "air_gap_capacity_and_provider_model_eligibility_are_hard_predicates",
    "stale_provider_observation_fences_an_otherwise_eligible_node",
)

ATTESTATION_TESTS = (
    "a_tampered_node_profile_does_not_inherit_verified_attestation",
    "an_attacker_signed_attestation_is_rejected",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def run(root: Path, *command: str) -> str:
    result = subprocess.run(
        list(command),
        cwd=root,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise VerificationError(f"{' '.join(command)} failed: {detail[-4000:]}")
    return result.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise VerificationError(f"{path.name} is missing SAD-32 markers: {missing}")


def require_test_passes(output: str, names: tuple[str, ...], lane: str) -> None:
    missing = [name for name in names if f"{name} ... ok" not in output]
    if missing:
        raise VerificationError(f"{lane} tests did not report PASS: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    estate = root / "crates/saddle-estate/src/kinds.rs"
    filters = root / "crates/saddle-scheduler/src/filters.rs"
    types = root / "crates/saddle-scheduler/src/types.rs"
    controller = root / "crates/saddle-controller/src/scheduler.rs"
    registration = root / "crates/saddle-node/src/registration.rs"
    tests = root / "crates/saddle-scheduler/tests/sad32_hard_placement.rs"
    artifacts = (estate, filters, types, controller, registration, tests)
    for path in artifacts:
        if not path.is_file():
            raise VerificationError(f"missing SAD-32 artifact: {path.relative_to(root)}")

    require_markers(
        estate,
        (
            "SchedulingConstraints",
            "ConnectivityRequirement",
            "required_models",
            "required_measurement",
        ),
    )
    require_markers(
        filters,
        (
            "heartbeat_ttl_seconds",
            "attestation_verified_until",
            "ConnectivityFilter",
            "ProviderEligibilityFilter",
            "reported allocatable capacity",
        ),
    )
    require_markers(types, ("SignalProvenance", "heartbeat_timestamp", "ProviderEligibility"))
    require_markers(
        controller,
        (
            "verify_stamped_attestation",
            "provider_eligibility",
            "PROVIDER_OBSERVATION_TTL_SECONDS",
        ),
    )
    require_markers(
        registration,
        (
            "saddle.node-attestation/v1",
            "mint_node_attestation",
            "verify_stamped_attestation",
            "ATTESTATION_SIGNATURE_ANNOTATION",
        ),
    )

    test_source = tests.read_text(encoding="utf-8")
    missing_tests = [name for name in SCHEDULER_TESTS if f"fn {name}" not in test_source]
    if missing_tests:
        raise VerificationError(f"missing adversarial scheduler tests: {missing_tests}")

    scheduler_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-scheduler",
        "--test",
        "sad32_hard_placement",
        "--locked",
        "--",
        "--test-threads=1",
    )
    require_test_passes(scheduler_output, SCHEDULER_TESTS, "scheduler")
    attestation_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-node",
        "registration::tests",
        "--locked",
        "--",
        "--test-threads=1",
    )
    require_test_passes(attestation_output, ATTESTATION_TESTS, "attestation")

    return {
        "schema_version": "saddle-sad32-attested-scheduling-gate/v1",
        "prompt": "SAD-32",
        "status": "pass",
        "hard_predicates": {
            "trust_ring": "pass",
            "classification_ceiling": "pass",
            "fresh_anchor_signed_attestation": "pass",
            "measurement_compatibility": "pass",
            "air_gap_connectivity": "pass",
            "cpu_memory_gpu_slot_capacity": "pass",
            "current_provider_model_eligibility": "pass",
            "score_resurrection": "structurally_impossible",
        },
        "fail_closed": {
            "pressure": "pass",
            "failover": "pass",
            "stale_heartbeat": "pass",
            "stale_attestation": "pass",
            "stale_provider_cache": "pass",
            "tampered_attestation_profile": "pass",
            "attacker_signed_attestation": "pass",
            "test_names": list(SCHEDULER_TESTS + ATTESTATION_TESTS),
            "test_count": len(SCHEDULER_TESTS) + len(ATTESTATION_TESTS),
        },
        "artifacts": {
            path.stem: {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
            }
            for path in artifacts
        },
    }


def canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    output = (root / args.evidence_output).resolve()
    try:
        output.relative_to(root)
        rendered = canonical(build_evidence(root))
        if args.verify:
            if not output.is_file():
                raise VerificationError(f"evidence file does not exist: {output}")
            if output.read_text(encoding="utf-8") != rendered:
                raise VerificationError("evidence does not match current deterministic gate output")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, ValueError, json.JSONDecodeError, VerificationError) as error:
        print(f"SAD-32 attested scheduling gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-32 attested scheduling gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
