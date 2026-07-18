#!/usr/bin/env python3
"""Exercise and record the SAD-22 versioned legacy-state migration gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the SAD-22 migration gate cannot prove its contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument("--binary", default=Path("target/debug/saddlectl.exe"), type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def canonical(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def versioned(value: bytes, create: int, modified: int, version: int) -> dict[str, Any]:
    return {
        "value": list(value),
        "create_revision": create,
        "mod_revision": modified,
        "version": version,
    }


def representative_snapshot() -> dict[str, Any]:
    resource = {
        "api_version": "aog.islandmountain.io/v1",
        "kind": "Tenant",
        "metadata": {
            "name": "elk-river",
            "uid": "estate-uid-7",
            "tenant": "elk-river",
            "generation": 4,
            "resource_version": 17,
            "labels": {
                "loom.io/unschedulable": "true",
                "user.example/loom-note": "retained",
            },
            "annotations": {"operator-note": "loom is opaque here"},
            "token_ref": {"token_id": "loom-era-token-must-not-change"},
            "receipt_ref": {
                "receipt_id": "receipt-9",
                "chain": "loom-era-chain-must-not-change",
            },
            "finalizers": ["loom.aog/tenant-teardown", "user.example/retain"],
        },
        "spec": {
            "display_name": "Elk River",
            "ring": 2,
            "classification_ceiling": "restricted",
            "opaque_authority": "loom-era-policy-must-not-change",
        },
        "status": {"openbao_path": "kv/data/loom-era/retain"},
    }
    return {
        "schema_version": "saddle-versioned-estate/v1",
        "entries": [
            {
                "key": "Tenant/elk-river",
                "versioned": versioned(canonical(resource), 7, 17, 4),
            },
            {
                "key": "ZOpaque/raw",
                "versioned": versioned(b"not-json-loom-era-bytes", 18, 18, 1),
            },
        ],
    }


def run_json(binary: Path, *args: str, expect_success: bool = True) -> dict[str, Any]:
    result = subprocess.run(
        [str(binary), *args],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if expect_success and result.returncode != 0:
        raise VerificationError(result.stderr.strip() or "migration command failed")
    if not expect_success:
        if result.returncode == 0:
            raise VerificationError("tampered migration state was accepted")
        return {"rejected": True, "exit_code": result.returncode}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("migration command did not emit JSON") from error


def value_json(snapshot: dict[str, Any], index: int = 0) -> dict[str, Any]:
    raw = bytes(snapshot["entries"][index]["versioned"]["value"])
    return json.loads(raw)


def preservation_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = value_json(snapshot)
    return {
        "key": snapshot["entries"][0]["key"],
        "uid": value["metadata"]["uid"],
        "tenant": value["metadata"]["tenant"],
        "token_ref": value["metadata"]["token_ref"],
        "receipt_ref": value["metadata"]["receipt_ref"],
        "annotations": value["metadata"]["annotations"],
        "spec": value["spec"],
        "openbao_path": value["status"]["openbao_path"],
        "versions": [entry["versioned"] | {"value": None} for entry in snapshot["entries"]],
        "opaque_entry": snapshot["entries"][1],
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evidence_for(binary: Path) -> dict[str, Any]:
    original = representative_snapshot()
    with tempfile.TemporaryDirectory(prefix="saddle-sad22-") as directory:
        work = Path(directory)
        source = work / "source.json"
        migrated_path = work / "migrated.json"
        journal_path = work / "journal.json"
        restored_path = work / "restored.json"
        tampered_path = work / "tampered.json"
        write_json(source, original)

        inspect_report = run_json(binary, "migrate", "inspect", "-f", str(source))
        dry_run_report = run_json(binary, "migrate", "dry-run", "-f", str(source))
        apply_report = run_json(
            binary,
            "migrate",
            "apply",
            "-f",
            str(source),
            "--out",
            str(migrated_path),
            "--journal",
            str(journal_path),
        )
        migrated = json.loads(migrated_path.read_text(encoding="utf-8"))
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        verification = run_json(
            binary,
            "migrate",
            "verify",
            "-f",
            str(migrated_path),
            "--journal",
            str(journal_path),
        )
        rollback_report = run_json(
            binary,
            "migrate",
            "rollback",
            "-f",
            str(migrated_path),
            "--journal",
            str(journal_path),
            "--out",
            str(restored_path),
        )
        restored = json.loads(restored_path.read_text(encoding="utf-8"))

        if inspect_report != dry_run_report or apply_report != inspect_report:
            raise VerificationError("inspect, dry-run, and apply reports diverged")
        if len(apply_report.get("changes", [])) != 3:
            raise VerificationError("representative estate did not produce three structural rewrites")
        if preservation_view(original) != preservation_view(migrated):
            raise VerificationError("authority, receipt, opaque payload, or versions changed")
        if restored != original:
            raise VerificationError("rollback did not restore the exact versioned estate")
        if verification != rollback_report:
            raise VerificationError("verify and rollback verification reports diverged")
        if not all(
            verification.get(field) is True
            for field in (
                "authority_and_payload_preserved",
                "receipt_chain_preserved",
                "version_metadata_preserved",
                "rollback_ready",
            )
        ):
            raise VerificationError("verification did not prove every preservation invariant")

        tampered = json.loads(json.dumps(migrated))
        tampered_value = value_json(tampered)
        tampered_value["metadata"]["receipt_ref"]["chain"] = "tampered"
        tampered["entries"][0]["versioned"]["value"] = list(canonical(tampered_value))
        write_json(tampered_path, tampered)
        rejection = run_json(
            binary,
            "migrate",
            "verify",
            "-f",
            str(tampered_path),
            "--journal",
            str(journal_path),
            expect_success=False,
        )

    return {
        "schema_version": 1,
        "status": "PASS",
        "modes": ["inspect", "dry-run", "apply", "verify", "rollback"],
        "representative_entries": len(original["entries"]),
        "structural_rewrites": len(apply_report["changes"]),
        "rewritten_paths": [change["path"] for change in apply_report["changes"]],
        "authority_and_payload_preserved": True,
        "receipt_chain_preserved": True,
        "version_metadata_preserved": True,
        "opaque_non_json_entry_preserved": True,
        "rollback_exact": True,
        "tampered_receipt_rejected": rejection["rejected"],
        "tamper_rejection_exit_code": rejection["exit_code"],
        "source_sha256": digest(original),
        "migrated_sha256": digest(migrated),
        "journal_sha256": digest(journal),
        "restored_sha256": digest(restored),
    }


def write_or_verify(destination: Path, expected: bytes, verify_only: bool) -> None:
    if destination.exists():
        if not destination.is_file():
            raise VerificationError(f"evidence destination is not a file: {destination}")
        if destination.read_bytes() != expected:
            if verify_only:
                raise VerificationError("existing evidence differs from deterministic output")
            destination.write_bytes(expected)
        return
    if verify_only:
        raise VerificationError("required evidence output is missing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(expected)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    binary = args.binary if args.binary.is_absolute() else root / args.binary
    output = args.evidence_output if args.evidence_output.is_absolute() else root / args.evidence_output
    if not binary.is_file():
        raise VerificationError(f"saddlectl binary not found: {binary}")
    evidence = evidence_for(binary)
    expected = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_or_verify(output, expected, args.verify)
    print("SAD-22 legacy-state migration gate: PASS (5 modes, 3 rewrites, exact rollback)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"SAD-22 legacy-state migration gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
