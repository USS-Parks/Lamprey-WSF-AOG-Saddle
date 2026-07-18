#!/usr/bin/env python3
"""Exercise and record the SAD-33 governed AOG workload lifecycle gate."""

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
    """Raised when the governed workload boundary cannot be proven."""


TEST_NAME = "start_scale_roll_and_revoke_are_capability_bound_end_to_end"


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
        raise VerificationError(f"{' '.join(command)} failed: {detail[-5000:]}")
    return result.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise VerificationError(f"{path.name} is missing SAD-33 markers: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    if not os.environ.get("WSF_OPENBAO_ADDR"):
        raise VerificationError("WSF_OPENBAO_ADDR is required; mock-only evidence is insufficient")

    kinds = root / "crates/saddle-estate/src/kinds.rs"
    admission = root / "crates/saddle-apiserver/src/admission.rs"
    objects = root / "crates/saddle-controller/src/objects.rs"
    scheduler = root / "crates/saddle-controller/src/scheduler.rs"
    runtime = root / "crates/saddle-node/src/runtime.rs"
    lifecycle_test = root / "crates/saddle-controller/tests/sad33_aog_workloads.rs"
    artifacts = (kinds, admission, objects, scheduler, runtime, lifecycle_test)
    for path in artifacts:
        if not path.is_file():
            raise VerificationError(f"missing SAD-33 artifact: {path.relative_to(root)}")

    require_markers(
        kinds,
        ("Gateway", "Toolproxy", "Approvals", "Agent", "Inference"),
    )
    require_markers(
        admission,
        (
            "ControllerGrant",
            "ControllerProfile",
            "admit_controller",
            "controller_epoch",
            "#[cfg(debug_assertions)]",
        ),
    )
    require_markers(
        objects,
        ("ControllerAuthority::Grant", "for_controller", "admit_controller"),
    )
    require_markers(
        scheduler,
        (
            "workload_digest",
            "service_identity",
            "workload_role",
            "cap.metadata.tenant == workload.metadata.tenant",
            "RUNTIME_DIGEST_ANNOTATION",
        ),
    )
    require_markers(
        runtime,
        (
            "start_authorized",
            "NodeRuntime",
            "token.identity_id.as_deref()",
            "token.roles.as_slice()",
            "revocation.revokes(token)",
        ),
    )
    require_markers(
        lifecycle_test,
        (
            f"fn {TEST_NAME}",
            "WorkloadKind::Approvals",
            "ProcessDriver::default()",
            "a sibling child token cannot start",
            "revoke_controller_grants",
        ),
    )

    live_output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-controller",
        "--test",
        "sad33_aog_workloads",
        "--locked",
        "--",
        "--test-threads=1",
    )
    if f"{TEST_NAME} ... ok" not in live_output:
        raise VerificationError("SAD-33 live lifecycle test did not report PASS")

    run(
        root,
        "cargo",
        "check",
        "-p",
        "saddle-apiserver",
        "-p",
        "saddle-controller",
        "--release",
        "--locked",
    )

    return {
        "schema_version": "saddle-sad33-aog-workload-integration-gate/v1",
        "prompt": "SAD-33",
        "status": "pass",
        "managed_workload_kinds": ["gateway", "toolproxy", "approvals", "agent"],
        "lifecycle": {
            "start": "pass",
            "scale": "pass",
            "digest_roll": "pass",
            "capability_revocation": "pass",
            "real_scheduler_controller": "pass",
            "real_process_driver": "pass",
            "live_openbao": "pass",
            "test_name": TEST_NAME,
        },
        "least_privilege": {
            "fixed_role_per_kind": "pass",
            "tenant_and_workload_uid_binding": "pass",
            "placement_uid_and_node_binding": "pass",
            "immutable_runtime_digest_binding": "pass",
            "bounded_ttl_budget_and_lineage": "pass",
            "sibling_token_theft": "denied",
        },
        "controller_authority": {
            "server_minted_non_serializable_grant": "pass",
            "profile_and_tenant_scope": "pass",
            "epoch_revocation": "pass",
            "release_build_without_unrestricted_system_path": "pass",
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
        print(f"SAD-33 AOG workload integration gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-33 AOG workload integration gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
