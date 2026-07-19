#!/usr/bin/env python3
"""Exercise and record the SAD-41 consensus-truth and fencing gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when a SAD-41 invariant cannot be proven."""


STORE_TESTS = (
    "exact_snapshot_restore_replaces_keyspace_and_preserves_delete_revision",
    "versioned_snapshot_checksum_rejects_tampering",
)
CONSENSUS_TESTS = (
    "concurrent_writes_remain_linearizable_across_leader_transition",
    "snapshot_install_and_membership_rotation_preserve_exact_truth_and_fence_removed_member",
    "bounded_stale_watch_fails_closed_and_recovers_from_lag",
    "membership_validation_rejects_unknown_and_non_quorum_rotations",
    "minority_partition_closes_confirmed_gate_and_serves_no_authoritative_write",
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
        raise VerificationError(f"{' '.join(command)} failed: {detail[-8000:]}")
    return result.stdout


def require_tests(output: str, names: tuple[str, ...]) -> None:
    missing = [name for name in names if f"{name} ... ok" not in output]
    if missing:
        raise VerificationError(f"tests did not report PASS: {missing}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise VerificationError(f"{path} is missing required markers: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    artifacts = {
        "raft_node": root / "crates/saddle-store/src/raft/mod.rs",
        "snapshot_state_machine": root
        / "crates/saddle-store/src/raft/state_machine.rs",
        "watch_cache": root / "crates/saddle-store/src/raft/watch.rs",
        "store": root / "crates/saddle-store/src/lib.rs",
        "controller_runtime": root / "crates/saddle-controller/src/runtime.rs",
        "admin_membership": root / "crates/saddled/src/admin.rs",
        "consensus_tests": root
        / "crates/saddle-controller/tests/sad41_consensus_truth.rs",
        "store_tests": root / "crates/saddle-store/tests/store.rs",
    }
    for path in artifacts.values():
        if not path.is_file():
            raise VerificationError(f"missing SAD-41 artifact: {path.relative_to(root)}")

    require_markers(
        artifacts["raft_node"],
        (
            "ensure_linearizable",
            "validate_membership_change",
            "MembershipError::InsufficientOverlap",
            "max_in_snapshot_log_to_keep: 0",
        ),
    )
    require_markers(
        artifacts["snapshot_state_machine"],
        (
            "SNAPSHOT_FORMAT_VERSION",
            "payload_checksum",
            "restore_exact",
        ),
    )
    require_markers(
        artifacts["watch_cache"],
        ("poll_bounded", "snapshot_if_fresh", "freshness_age", "range_with_revision"),
    )
    require_markers(
        artifacts["controller_runtime"],
        ("watch_staleness", "poll_bounded"),
    )
    require_markers(
        artifacts["admin_membership"],
        ("validate_membership_change", "StatusCode::BAD_REQUEST"),
    )

    store_output = run(root, "cargo", "test", "-p", "saddle-store", "--locked")
    require_tests(store_output, STORE_TESTS)
    consensus_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-controller",
        "--test",
        "sad41_consensus_truth",
        "--locked",
    )
    require_tests(consensus_output, CONSENSUS_TESTS)

    return {
        "schema_version": "saddle-sad41-consensus-truth-gate/v1",
        "prompt": "SAD-41",
        "status": "pass",
        "profile": {
            "control_plane_voters": 3,
            "membership_rotation_nodes": 4,
            "concurrent_clients": 6,
            "attempts_per_client": 32,
            "watch_buffer_overflow_events": 100,
        },
        "properties": {
            "linearizable_acknowledged_writes": "no_lost_acknowledgement",
            "leader_transition_under_partition": "pass",
            "quorum_confirmed_controller_gate": "fail_closed",
            "snapshot_format": "versioned_blake3_checksummed",
            "snapshot_install": "late_learner_exact_state_and_revision",
            "membership_change": "known_members_safe_count_quorum_overlap",
            "removed_member_authority": "fenced",
            "bounded_stale_watch": "fail_closed_then_resync",
            "lagged_watch": "full_relist_exact_revision",
            "minority_partition": "no_authoritative_write",
            "store_test_names": list(STORE_TESTS),
            "consensus_test_names": list(CONSENSUS_TESTS),
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
        print(f"SAD-41 consensus-truth gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-41 consensus-truth gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
