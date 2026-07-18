#!/usr/bin/env python3
"""Exercise and record the SAD-35 live two-tenant bridge gate."""

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
    """Raised when the live bridge boundary cannot be proven."""


LIVE_TEST = "live_two_tenant_bridge_isolated_restartable_and_off_host_verifiable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def run(root: Path, *command: str) -> str:
    environment = os.environ.copy()
    if "SADDLE_LIVE_OPENBAO_ADDR" not in environment and "WSF_OPENBAO_ADDR" in environment:
        environment["SADDLE_LIVE_OPENBAO_ADDR"] = environment["WSF_OPENBAO_ADDR"]
    if "SADDLE_LIVE_OPENBAO_TOKEN" not in environment and "WSF_OPENBAO_TOKEN" in environment:
        environment["SADDLE_LIVE_OPENBAO_TOKEN"] = environment["WSF_OPENBAO_TOKEN"]
    result = subprocess.run(
        list(command),
        cwd=root,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise VerificationError(f"{' '.join(command)} failed: {output[-8000:]}")
    return output


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise VerificationError(f"{path.name} is missing SAD-35 markers: {missing}")


def build_evidence(root: Path) -> dict[str, Any]:
    if not (os.environ.get("SADDLE_LIVE_OPENBAO_ADDR") or os.environ.get("WSF_OPENBAO_ADDR")):
        raise VerificationError("SADDLE_LIVE_OPENBAO_ADDR or WSF_OPENBAO_ADDR is required")

    artifacts = (
        root / "crates/saddle-bridge/src/lib.rs",
        root / "crates/saddle-node/src/runtime.rs",
        root / "crates/aog-gateway/src/app.rs",
        root / "crates/aog-toolproxy/src/lib.rs",
        root / "crates/saddle-controller/tests/sad35_two_tenant_bridge.rs",
        root / ".github/workflows/ci.yml",
    )
    for path in artifacts:
        if not path.is_file():
            raise VerificationError(f"missing SAD-35 artifact: {path.relative_to(root)}")

    require_markers(
        artifacts[0],
        (
            "PersistedGrantHandoff",
            "verify_grant_handoff",
            "RuntimeActionSession",
            "ActionSessionRegistry",
            "WsfLedgerActionSink",
            "AuthorityUnavailable",
        ),
    )
    require_markers(
        artifacts[1],
        ("start_bridged_authorized", "typed runtime grant does not exactly bind"),
    )
    require_markers(artifacts[2], ("with_saddle_bridge", "bridge_spec", ".execute("))
    require_markers(artifacts[3], ("with_saddle_bridge", "ActionKind::Tool", "execute_bounded"))
    require_markers(
        artifacts[4],
        (
            LIVE_TEST,
            "RedbBackend",
            "set_available(false)",
            "advance_revocation",
            "verify_pack",
            "start_bridged_authorized",
        ),
    )
    require_markers(artifacts[5], ("sad35_two_tenant_bridge",))

    output = run(
        root,
        "cargo",
        "test",
        "-p",
        "saddle-controller",
        "--test",
        "sad35_two_tenant_bridge",
        "--locked",
        "--",
        "--nocapture",
        "--test-threads=1",
    )
    if f"{LIVE_TEST} ... ok" not in output:
        raise VerificationError("SAD-35 live test did not report PASS")
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
    run(root, "cargo", "check", "-p", "saddle-controller", "--release", "--locked")

    return {
        "schema_version": "saddle-sad35-two-tenant-bridge-gate/v1",
        "prompt": "SAD-35",
        "status": "pass",
        "tenants": 2,
        "runtime_classes": ["aog-gateway", "aog-toolproxy", "saddle-control"],
        "persisted_handoff": {
            "placement_and_runtime_signed": "pass",
            "redb_restart_recovery": "pass",
            "tamper_and_revocation_rejected": "pass",
            "node_requires_typed_handoff_and_child_capability": "pass",
        },
        "live_consumers": {
            "openbao_virtual_key_resolution": "pass",
            "gateway_provider_effect_via_action_gate": "pass",
            "toolproxy_executor_effect_via_action_gate": "pass",
            "control_effect_via_action_gate": "pass",
        },
        "fail_closed": {
            "cross_tenant_lineage_theft": "denied",
            "consumer_connectivity_loss": "isolated_and_denied",
            "signed_revocation_model_tool_control": "denied",
            "sibling_tenant_remains_live": "pass",
        },
        "receipts": {
            "shared_wsf_ledger": "pass",
            "metadata_only_before_effect": "pass",
            "serialized_evidence_pack_off_host_verification": "pass",
        },
        "artifacts": {
            path.relative_to(root).as_posix(): {"sha256": sha256(path)} for path in artifacts
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
        print(f"SAD-35 two-tenant bridge gate FAILED: {error}", file=sys.stderr)
        return 1
    print("SAD-35 two-tenant bridge gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
