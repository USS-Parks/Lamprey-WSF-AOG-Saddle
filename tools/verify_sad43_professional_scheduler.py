#!/usr/bin/env python3
"""Exercise and record the SAD-43 professional scheduler gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when a SAD-43 invariant cannot be proven."""


SAD43_TESTS = (
    "ordered_queue_to_post_bind_cycle_is_replayable_and_cas_guarded",
    "hard_sovereignty_quota_and_capacity_filters_never_relax_under_pressure",
    "gang_reservation_wait_reject_and_expiry_are_all_or_nothing",
    "plugin_failure_or_panic_fails_closed_without_leaked_reservation",
    "weighted_drf_guarantees_priority_and_starvation_bound_queue_order",
    "feasible_work_is_selected_within_the_declared_starvation_bound",
    "accelerator_topology_locality_spread_and_authoritative_roi_drive_selection",
    "deterministic_multi_victim_preemption_respects_trust_and_disruption",
    "bounded_queue_classes_require_explicit_wake_events",
    "deterministic_adversarial_multi_tenant_histories_preserve_all_invariants",
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
    detail = result.stdout + result.stderr
    if result.returncode != 0:
        raise VerificationError(f"{' '.join(command)} failed: {detail[-12000:]}")
    return detail


def require_tests(output: str) -> None:
    missing = [name for name in SAD43_TESTS if f"{name} ... ok" not in output]
    if missing:
        raise VerificationError(f"tests did not report PASS: {missing}")


def sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical_text = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise VerificationError(f"{path} is missing required markers: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    artifacts = {
        "professional_scheduler": root
        / "crates/saddle-scheduler/src/professional.rs",
        "legacy_filter_framework": root
        / "crates/saddle-scheduler/src/framework.rs",
        "scheduler_exports": root / "crates/saddle-scheduler/src/lib.rs",
        "sad43_tests": root
        / "crates/saddle-scheduler/tests/sad43_professional_scheduler.rs",
        "validation_workflow": root / ".github/workflows/ship-validation.yml",
        "conformance_workflow": root / ".github/workflows/ci.yml",
        "local_validation_driver": root / "scripts/saddle-validation.ps1",
    }
    for path in artifacts.values():
        if not path.is_file():
            raise VerificationError(f"missing SAD-43 artifact: {path.relative_to(root)}")

    require_markers(
        artifacts["professional_scheduler"],
        (
            "pub enum CyclePhase",
            "QueueSort",
            "NormalizeScore",
            "Unreserve",
            "PostBind",
            "dominant_share_bps",
            "reservation_id",
            "bind_reservation",
            "plan_preemption",
            "minimum_interconnect_score",
            "estimated_value_cents",
            "starvation_bound_cycles",
            "check_invariants",
        ),
    )
    require_markers(
        artifacts["legacy_filter_framework"],
        ("evaluate_nodes", "Deny-wins", "score_node"),
    )
    require_markers(
        artifacts["sad43_tests"],
        (
            "const HISTORIES: usize = 256",
            "const STEPS_PER_HISTORY: usize = 64",
            "const STARVATION_BOUND_CYCLES: u64 = 32",
            "wrong-estate",
            "PermitDecision::Wait",
            "PluginPanicked",
        ),
    )
    require_markers(
        artifacts["validation_workflow"],
        ("Verify SAD-43 professional scheduler", "verify_sad43_professional_scheduler.py"),
    )
    require_markers(
        artifacts["conformance_workflow"],
        ("SAD-43 professional scheduler", "sad43_professional_scheduler"),
    )
    require_markers(
        artifacts["local_validation_driver"],
        ("sad43-professional-scheduler", "verify_sad43_professional_scheduler.py"),
    )

    test_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-scheduler",
        "--test",
        "sad43_professional_scheduler",
        "--locked",
    )
    require_tests(test_output)

    return {
        "schema_version": "saddle-sad43-professional-scheduler-gate/v1",
        "prompt": "SAD-43",
        "status": "pass",
        "artifact_digest": "sha256_utf8_lf_normalized",
        "profile": {
            "deterministic_seed": "0x5ad43000c0def17e",
            "adversarial_histories": 256,
            "steps_per_history": 64,
            "adversarial_operations": 256 * 64,
            "starvation_bound_cycles": 32,
            "focused_tests": len(SAD43_TESTS),
        },
        "properties": {
            "plugin_cycle": "queue_sort_through_post_bind_ordered",
            "coherent_snapshot": "global_revision_cas",
            "hard_sovereignty": "estate_tenant_ring_attestation_deny_wins",
            "resource_safety": "node_and_tenant_accounting_recomputed_after_each_step",
            "fairness": "weighted_drf_guarantees_priority_and_bounded_starvation",
            "quota": "hard_ceiling_atomic_with_node_reservation",
            "reservation": "clone_before_commit_and_complete_unreserve",
            "permit": "approve_wait_reject_and_bounded_expiry",
            "gang": "all_members_or_none_with_topology_domain",
            "binding": "one_uid_generation_replica_under_revision_cas",
            "preemption": "deterministic_multi_victim_disruption_aware",
            "topology": "accelerator_interconnect_locality_and_spread",
            "budget_roi": "authoritative_metered_cost_only",
            "test_names": list(SAD43_TESTS),
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
        print(f"SAD-43 professional scheduler gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-43 professional scheduler gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
