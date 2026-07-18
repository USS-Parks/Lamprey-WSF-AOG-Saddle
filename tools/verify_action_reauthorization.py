#!/usr/bin/env python3
"""Exercise and record the SAD-34 per-action authorization and receipt gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the action boundary cannot be proven."""


TESTS = (
    "model_tool_and_control_effects_require_a_precommitted_receipt",
    "replay_and_cross_tenant_token_theft_fail_closed",
    "revocation_between_receipt_and_effect_still_blocks_the_effect",
    "action_expiry_between_receipt_and_effect_still_blocks_the_effect",
    "concurrent_budget_reservations_and_audit_failure_cannot_reach_effect_authority",
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
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise VerificationError(f"{' '.join(command)} failed: {detail[-6000:]}")
    return result.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise VerificationError(f"{path.name} is missing SAD-34 markers: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    bridge = root / "crates/saddle-bridge/src/lib.rs"
    action_test = root / "crates/saddle-bridge/tests/sad34_action_gate.rs"
    artifacts = (bridge, action_test)
    for path in artifacts:
        if not path.is_file():
            raise VerificationError(f"missing SAD-34 artifact: {path.relative_to(root)}")

    require_markers(
        bridge,
        (
            "ActionAuthorizationReceipt",
            "ActionReceiptSink",
            "ActionGate",
            "PreparedAction",
            "ensure_current_authority(request, now, revocation)?",
            "self.reservation.commit()?",
            'phase: "authorized_before_effect"',
            "ReceiptMismatch",
            "ActionExpired",
        ),
    )
    require_markers(
        action_test,
        (
            "wsf_ledger::Ledger",
            "RustCryptoMlDsa87",
            "ActionKind::Model",
            "ActionKind::Tool",
            "ActionKind::Control",
            *TESTS,
        ),
    )

    output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-bridge",
        "--test",
        "sad34_action_gate",
        "--locked",
        "--",
        "--test-threads=1",
    )
    for test in TESTS:
        if f"{test} ... ok" not in output:
            raise VerificationError(f"SAD-34 adversarial test did not report PASS: {test}")

    run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-bridge",
        "--test",
        "contract_properties",
        "--locked",
    )
    run(root, "cargo", "check", "-p", "saddle-bridge", "--release", "--locked")

    return {
        "schema_version": "saddle-sad34-action-reauthorization-gate/v1",
        "prompt": "SAD-34",
        "status": "pass",
        "action_kinds": ["model", "tool", "control"],
        "last_responsible_moment": {
            "current_wsf_authority_rechecked_before_effect": "pass",
            "cross_tenant_token_theft": "denied",
            "lineage_scoped_nonce_replay": "denied",
            "receipt_request_digest_mismatch": "denied",
            "expired_prepared_action": "denied",
        },
        "proof_before_effect": {
            "metadata_only_authorization_receipt": "pass",
            "real_wsf_ledger_chain": "pass",
            "real_ml_dsa_signer": "pass",
            "empty_or_failed_receipt_proof": "denied",
            "receipt_committed_before_effect_observation": "pass",
        },
        "budget": {
            "shared_atomic_reservation": "pass",
            "concurrent_over_reservation": "denied",
            "conservative_charge_before_uncertain_effect": "pass",
        },
        "revocation_race": {
            "newer_signed_snapshot_after_receipt": "denied_before_effect",
            "effect_observed": False,
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
        print(f"SAD-34 action reauthorization gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-34 action reauthorization gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
