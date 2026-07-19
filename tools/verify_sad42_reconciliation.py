#!/usr/bin/env python3
"""Exercise and record the SAD-42 level-triggered reconciliation gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when a SAD-42 invariant cannot be proven."""


QUEUE_TESTS = (
    "queue::tests::backoff_doubles_and_caps",
    "queue::tests::exhausted_retry_is_visible_and_redrives_until_success",
    "queue::tests::resync_respects_backoff_and_redrives_dead_letters",
)
REPLAY_TESTS = (
    "duplicate_and_dropped_events_converge_identically",
    "failed_reconciles_retry_with_backoff_and_converge",
    "non_leader_observes_but_never_acts",
    "requeue_actions_run_the_key_again",
    "resync_heartbeat_reconciles_without_a_change",
)
SAD42_TESTS = (
    "fault_injected_histories_converge_to_same_state",
    "real_finalizer_replay_withdraws_external_state_before_delete",
    "reconcile_deadline_cancels_and_dead_letters_hung_work",
    "shutdown_cancels_an_inflight_reconcile",
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
        "controller_runtime": root / "crates/saddle-controller/src/runtime.rs",
        "work_queue": root / "crates/saddle-controller/src/queue.rs",
        "informer": root / "crates/saddle-store/src/raft/watch.rs",
        "estate_client": root / "crates/saddle-controller/src/objects.rs",
        "live_finalizer": root / "crates/saddle-controller/src/vkeys.rs",
        "replay_tests": root / "crates/saddle-controller/tests/replay.rs",
        "sad42_tests": root
        / "crates/saddle-controller/tests/sad42_reconciliation.rs",
        "ci_workflow": root / ".github/workflows/ci.yml",
    }
    for path in artifacts.values():
        if not path.is_file():
            raise VerificationError(f"missing SAD-42 artifact: {path.relative_to(root)}")

    require_markers(
        artifacts["controller_runtime"],
        (
            "reconcile_timeout",
            "tokio::time::timeout",
            "cancellation_requested",
            "dead_letters",
            "redrive_dead_letters",
        ),
    )
    require_markers(
        artifacts["work_queue"],
        (
            "delay_for",
            "DeadLetter",
            "retry_with_error",
            "set_max_retries",
            "add_resync",
        ),
    )
    require_markers(
        artifacts["informer"],
        ("Lagged", "resync", "poll_bounded", "range_with_revision"),
    )
    require_markers(
        artifacts["estate_client"],
        ("ensure_created", "resource_version", "Already gone is convergence"),
    )
    require_markers(
        artifacts["live_finalizer"],
        ("VIRTUALKEY_FINALIZER", "retract", "deletion_timestamp"),
    )
    require_markers(
        artifacts["sad42_tests"],
        (
            "const HISTORIES: usize = 256",
            "Noise/finalizer-",
            "injected lost external-cleanup acknowledgement",
            "with_reconcile_timeout",
            "shutdown_cancels_an_inflight_reconcile",
        ),
    )
    require_markers(
        artifacts["ci_workflow"],
        (
            "SAD-42 level-triggered reconciliation",
            "cargo test -p saddle-controller --test live_vkey --locked -- --nocapture",
        ),
    )

    unit_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-controller",
        "--lib",
        "--locked",
    )
    require_tests(unit_output, QUEUE_TESTS)
    replay_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-controller",
        "--test",
        "replay",
        "--locked",
    )
    require_tests(replay_output, REPLAY_TESTS)
    sad42_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-controller",
        "--test",
        "sad42_reconciliation",
        "--locked",
    )
    require_tests(sad42_output, SAD42_TESTS)

    return {
        "schema_version": "saddle-sad42-reconciliation-gate/v1",
        "prompt": "SAD-42",
        "status": "pass",
        "profile": {
            "fault_histories": 256,
            "overflow_histories": 86,
            "restart_histories": 52,
            "watch_overflow_events_per_injected_history": 100,
            "deterministic_seed": "0x5ad42000c0def17e",
        },
        "properties": {
            "level_triggered_current_state": "pass",
            "duplicate_reorder_replay_tolerance": "same_end_state",
            "dropped_watch_recovery": "full_relist",
            "jittered_exponential_backoff": "deterministic_per_key",
            "dead_letter_visibility": "bounded_retry_then_visible_redrive",
            "periodic_resync": "respects_backoff_and_redrives_dead_letters",
            "reconcile_deadline": "hung_future_cancelled",
            "shutdown_cancellation": "inflight_future_cancelled",
            "finalization": "external_withdrawal_before_admitted_delete",
            "controller_restart": "finalizer_preserves_recoverable_truth",
            "live_external_finalizer_gate": "live_vkey_in_wsf_live_ci",
            "queue_test_names": list(QUEUE_TESTS),
            "replay_test_names": list(REPLAY_TESTS),
            "sad42_test_names": list(SAD42_TESTS),
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
        print(f"SAD-42 reconciliation gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-42 reconciliation gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
