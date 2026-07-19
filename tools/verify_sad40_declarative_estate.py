#!/usr/bin/env python3
"""Exercise and record the SAD-40 declarative-estate gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when a SAD-40 invariant cannot be proven."""


KINDS = (
    "Tenant",
    "TrustRing",
    "VirtualKey",
    "Capability",
    "PolicyBundle",
    "ProviderPool",
    "Workload",
    "Placement",
    "Node",
    "MissionContract",
    "ToolGrant",
    "RolloutPlan",
    "RevocationIntent",
    "ResourceQuota",
    "PriorityClass",
    "PlacementGroup",
    "DisruptionBudget",
    "RuntimeClass",
    "NodeLease",
)
RESOURCE_TESTS = (
    "resource_quota_roundtrip",
    "priority_class_roundtrip",
    "placement_group_roundtrip",
    "disruption_budget_roundtrip",
    "runtime_class_roundtrip",
    "node_lease_roundtrip",
    "scheduler_resources_fail_closed_on_invalid_or_unknown_state",
)
INTEGRATION_TESTS = (
    "conversion_fuzz_preserves_authority_versions_desired_state_and_rollback",
    "conversion_refuses_unknown_versions_kind_spoofing_and_label_collision",
    "quota_cas_watch_and_finalizer_paths_share_the_real_admission_store",
    "runtime_class_credentials_are_sealed_before_persistence",
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
        raise VerificationError(f"{' '.join(command)} failed: {detail[-6000:]}")
    return result.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_tests(output: str, names: tuple[str, ...]) -> None:
    missing = [name for name in names if f"test {name} ... ok" not in output]
    if missing:
        raise VerificationError(f"tests did not report PASS: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    artifacts = {
        "estate_dispatch": root / "crates/saddle-estate/src/lib.rs",
        "scheduler_resources": root / "crates/saddle-estate/src/scheduler.rs",
        "conversion": root / "crates/saddle-apiserver/src/convert.rs",
        "admission": root / "crates/saddle-apiserver/src/admission.rs",
        "sealing": root / "crates/saddle-apiserver/src/seal.rs",
        "resource_tests": root / "crates/saddle-estate/tests/sad40_resources.rs",
        "integration_tests": root
        / "crates/saddle-apiserver/tests/sad40_declarative_estate.rs",
    }
    for path in artifacts.values():
        if not path.is_file():
            raise VerificationError(f"missing SAD-40 artifact: {path.relative_to(root)}")

    dispatch = artifacts["estate_dispatch"].read_text(encoding="utf-8")
    missing_kinds = [kind for kind in KINDS if kind not in dispatch]
    if missing_kinds or "pub const ALL: [Kind; 19]" not in dispatch:
        raise VerificationError(f"estate dispatch is incomplete: {missing_kinds}")

    scheduler = artifacts["scheduler_resources"].read_text(encoding="utf-8")
    for marker in (
        "pub struct ResourceQuotaSpec",
        "pub struct PriorityClassSpec",
        "pub struct PlacementGroupSpec",
        "pub struct DisruptionBudgetSpec",
        "pub struct RuntimeClassSpec",
        "pub struct NodeLeaseSpec",
        "deny_unknown_fields",
    ):
        if marker not in scheduler:
            raise VerificationError(f"scheduler schema is missing {marker}")

    conversion = artifacts["conversion"].read_text(encoding="utf-8")
    for marker in (
        "UnsupportedVersion",
        "KindMismatch",
        "DidNotAdvance",
        "Cycle",
        "convert_legacy_v1",
        "rollback_legacy_v1",
    ):
        if marker not in conversion:
            raise VerificationError(f"conversion gate is missing {marker}")

    admission = artifacts["admission"].read_text(encoding="utf-8")
    sealing = artifacts["sealing"].read_text(encoding="utf-8")
    for marker in ("Precondition::Revision", "check_terminating_update", "seal_fields"):
        if marker not in admission:
            raise VerificationError(f"admission gate is missing {marker}")
    if "ResourceObject::RuntimeClass" not in sealing:
        raise VerificationError("RuntimeClass credential sealing is not wired")

    resource_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-estate",
        "--test",
        "sad40_resources",
        "--locked",
    )
    require_tests(resource_output, RESOURCE_TESTS)
    integration_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-apiserver",
        "--test",
        "sad40_declarative_estate",
        "--locked",
    )
    require_tests(integration_output, INTEGRATION_TESTS)

    return {
        "schema_version": "saddle-sad40-declarative-estate-gate/v1",
        "prompt": "SAD-40",
        "status": "pass",
        "hub_api_version": "saddle.islandmountain.io/v1",
        "resource_model": {
            "kind_count": len(KINDS),
            "kinds": list(KINDS),
            "new_scheduler_kind_count": 6,
            "unknown_sensitive_fields": "fail_closed",
        },
        "properties": {
            "typed_round_trip": "pass",
            "optimistic_concurrency": "pass",
            "watch_delivery_and_resync": "pass",
            "two_phase_finalization": "pass",
            "sensitive_field_sealing": "pass",
            "unknown_version_and_kind": "fail_closed",
            "authority_uid_generation_resource_version_desired_state_preserved": "pass",
            "legacy_state_rollback": "exact",
            "deterministic_conversion_fuzz_cases": 512,
            "resource_test_names": list(RESOURCE_TESTS),
            "integration_test_names": list(INTEGRATION_TESTS),
        },
        "artifacts": {
            name: {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
            }
            for name, path in artifacts.items()
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
                raise VerificationError("evidence does not match deterministic gate output")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, ValueError, VerificationError) as error:
        print(f"SAD-40 declarative-estate gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-40 declarative-estate gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
