#!/usr/bin/env python3
"""Exercise and record the SAD-31 WSF-authenticated admission gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the real Saddle admission boundary cannot be proven."""


REQUIRED_TESTS = (
    "missing_nonce_and_replayed_authority_fail_closed",
    "stale_bundle_and_stale_revocation_fail_closed_on_mutation",
    "spoofed_anchor_and_out_of_scope_resource_fail_closed",
    "cross_tenant_authority_cannot_mutate_the_final_resource",
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
        raise VerificationError(f"{path.name} is missing admission markers: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    auth = root / "crates/saddle-apiserver/src/auth.rs"
    admission = root / "crates/saddle-apiserver/src/admission.rs"
    handlers = root / "crates/saddle-apiserver/src/handlers.rs"
    policy = root / "crates/saddle-apiserver/src/policy.rs"
    tests = root / "crates/saddle-apiserver/tests/saddle_admission.rs"
    client = root / "crates/saddlectl/src/lib.rs"
    artifacts = (auth, admission, handlers, policy, tests, client)
    for path in artifacts:
        if not path.is_file():
            raise VerificationError(f"missing SAD-31 artifact: {path.relative_to(root)}")

    require_markers(
        auth,
        (
            "MonotonicRevocationStore",
            "NONCE_HEADER",
            "verify_saddle_request",
            "RequestOperation::SaddleAdmission",
            "issue_admission_grant",
            "budget_exhausted",
        ),
    )
    require_markers(
        admission,
        (
            "admit_verified",
            "AdmissionSpec",
            "admission_grant",
            "persist_audit_intent",
            "self.commit(&req, staged).await?",
        ),
    )
    require_markers(handlers, ("verify_saddle_request", "admit_verified"))
    require_markers(policy, ("AggregateDecision", "self.composer.compose"))
    require_markers(client, ("x-saddle-nonce", "REQUEST_NONCE"))

    test_source = tests.read_text(encoding="utf-8")
    missing_tests = [name for name in REQUIRED_TESTS if f"fn {name}" not in test_source]
    if missing_tests:
        raise VerificationError(f"missing real-API adversarial tests: {missing_tests}")
    output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-apiserver",
        "--test",
        "saddle_admission",
        "--locked",
        "--",
        "--test-threads=1",
    )
    missing_passes = [name for name in REQUIRED_TESTS if f"test {name} ... ok" not in output]
    if missing_passes:
        raise VerificationError(f"real-API tests did not report PASS: {missing_passes}")

    return {
        "schema_version": "saddle-sad31-admission-gate/v1",
        "prompt": "SAD-31",
        "status": "pass",
        "boundary": {
            "request_operation": "saddle_admission",
            "token_header": "x-wsf-token",
            "nonce_header": "x-saddle-nonce",
            "current_bundle": "2026.07.saddle",
            "audit_before_mutation": "pass",
            "deny_wins_policy_reuse": "pass",
            "final_resource_binding": "pass",
        },
        "fail_closed": {
            "missing_authority": "pass",
            "stale_bundle": "pass",
            "stale_revocation": "pass",
            "spoofed_anchor": "pass",
            "resource_caveat": "pass",
            "cross_tenant": "pass",
            "replay": "pass",
            "test_names": list(REQUIRED_TESTS),
            "test_count": len(REQUIRED_TESTS),
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
        print(f"SAD-31 admission gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-31 admission gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
