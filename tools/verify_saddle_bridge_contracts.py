#!/usr/bin/env python3
"""Exercise and record the SAD-30 cross-plane contract compatibility gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the Saddle bridge contract cannot be proven."""


REQUIRED_TYPES = (
    "VerifiedSaddleRequest",
    "AdmissionGrant",
    "PlacementGrant",
    "RuntimeGrant",
    "ActionGrant",
    "BridgeError",
)
REQUIRED_TESTS = (
    "exact_grant_chain_is_serialize_only_and_preserves_lineage",
    "property_every_authority_axis_only_narrows",
    "tenant_and_nonce_properties_isolate_authority_and_resist_replay",
    "deny_wins_and_missing_policy_modules_fence_every_grant_stage",
    "absent_expired_and_revoked_state_fail_closed",
)
REQUIRED_REUSE = (
    "verify_in_context",
    "MonotonicRevocationStore",
    "AggregateDecision",
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


def assert_source_contract(source: str) -> dict[str, Any]:
    missing = [name for name in REQUIRED_TYPES if f"pub struct {name}" not in source and f"pub enum {name}" not in source]
    if missing:
        raise VerificationError(f"missing frozen contract types: {missing}")
    deserializable_grants = [
        name
        for name in REQUIRED_TYPES[:-1]
        if f"Serialize, Deserialize)]\npub struct {name}" in source
    ]
    if deserializable_grants:
        raise VerificationError(f"authority grants unexpectedly deserialize: {deserializable_grants}")
    missing_reuse = [marker for marker in REQUIRED_REUSE if marker not in source]
    if missing_reuse:
        raise VerificationError(f"missing reused authority seams: {missing_reuse}")
    if 'pub const CONTRACT_VERSION: &str = "saddle.bridge/v1"' not in source:
        raise VerificationError("cross-plane contract version is not frozen")
    return {
        "contract_version": "saddle.bridge/v1",
        "frozen_types": list(REQUIRED_TYPES),
        "deserialize_authority_types": [],
        "reused_seams": list(REQUIRED_REUSE),
    }


def build_evidence(root: Path) -> dict[str, Any]:
    source_path = root / "crates/saddle-bridge/src/lib.rs"
    tests_path = root / "crates/saddle-bridge/tests/contract_properties.rs"
    matrix_path = root / "docs/contracts/SADDLE-BRIDGE-COMPATIBILITY-MATRIX.md"
    for path in (source_path, tests_path, matrix_path):
        if not path.is_file():
            raise VerificationError(f"missing SAD-30 artifact: {path.relative_to(root)}")

    source = source_path.read_text(encoding="utf-8")
    tests = tests_path.read_text(encoding="utf-8")
    matrix = matrix_path.read_text(encoding="utf-8")
    contract = assert_source_contract(source)
    missing_tests = [name for name in REQUIRED_TESTS if f"fn {name}" not in tests]
    if missing_tests:
        raise VerificationError(f"missing contract property tests: {missing_tests}")
    for name in REQUIRED_TYPES:
        if name not in matrix:
            raise VerificationError(f"compatibility matrix omits {name}")

    test_output = run(root, "cargo", "test", "-p", "saddle-bridge", "--all-targets", "--locked")
    missing_passes = [name for name in REQUIRED_TESTS if f"test {name} ... ok" not in test_output]
    if missing_passes:
        raise VerificationError(f"property tests did not report PASS: {missing_passes}")
    doc_output = run(root, "cargo", "test", "-p", "saddle-bridge", "--doc", "--locked")
    if "2 passed" not in doc_output:
        raise VerificationError("compile-fail non-constructibility doctests did not both pass")

    metadata = json.loads(run(root, "cargo", "metadata", "--no-deps", "--locked", "--format-version", "1"))
    package = next((item for item in metadata["packages"] if item["name"] == "saddle-bridge"), None)
    if package is None:
        raise VerificationError("saddle-bridge is not a workspace package")

    return {
        "schema_version": "saddle-sad30-bridge-gate/v1",
        "prompt": "SAD-30",
        "status": "pass",
        "contract": contract,
        "properties": {
            "non_constructibility_from_wire_json": "pass",
            "authority_narrowing": "pass",
            "tenant_isolation": "pass",
            "request_and_action_replay_resistance": "pass",
            "revocation_fail_closed": "pass",
            "deny_wins_and_no_module_fence": "pass",
            "test_names": list(REQUIRED_TESTS),
            "property_test_count": len(REQUIRED_TESTS),
            "compile_fail_doctest_count": 2,
        },
        "workspace": {
            "package_count": len(metadata["packages"]),
            "saddle_bridge_manifest": Path(package["manifest_path"]).relative_to(root).as_posix(),
        },
        "artifacts": {
            "bridge_source": {
                "path": source_path.relative_to(root).as_posix(),
                "sha256": sha256(source_path),
            },
            "property_tests": {
                "path": tests_path.relative_to(root).as_posix(),
                "sha256": sha256(tests_path),
            },
            "compatibility_matrix": {
                "path": matrix_path.relative_to(root).as_posix(),
                "sha256": sha256(matrix_path),
            },
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
        evidence = build_evidence(root)
        rendered = canonical(evidence)
        if args.verify:
            if not output.is_file():
                raise VerificationError(f"evidence file does not exist: {output}")
            if output.read_text(encoding="utf-8") != rendered:
                raise VerificationError("evidence does not match current deterministic gate output")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, ValueError, json.JSONDecodeError, VerificationError) as error:
        print(f"SAD-30 bridge contract gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-30 bridge contract gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
