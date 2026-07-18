#!/usr/bin/env python3
"""Prove every retired orchestrator-name match is explicitly classified."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the SAD-23 active-name gate cannot prove eradication."""


RETIRED_NAME = re.compile("lo" + "om", re.IGNORECASE)
ALLOWED_CATEGORIES = {
    "historical_provenance",
    "migration_fixture",
    "verification_input",
}
REQUIRED_SURFACES = (
    ".github/workflows",
    "Cargo.toml",
    "PLANNING",
    "README.md",
    "console",
    "crates",
    "deployment",
    "docs",
    "docs/api/openapi.yaml",
    "crates/wsf-api/src/openapi.json",
    "packaging",
    "scripts",
)
GENERATED_SCHEMAS = (
    "crates/wsf-api/src/openapi.json",
    "docs/api/openapi.yaml",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument(
        "--classifications",
        default=Path("tools/saddle_active_name_classifications.json"),
        type=Path,
    )
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "-C",
            str(root),
            "ls-files",
            "-z",
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise VerificationError("cannot enumerate tracked repository paths")
    return sorted(
        path.decode("utf-8")
        for path in result.stdout.split(b"\0")
        if path
    )


def load_registry(path: Path) -> tuple[str, dict[str, int], list[dict[str, str]]]:
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read classification registry: {error}") from error
    if registry.get("schema_version") != 1:
        raise VerificationError("unsupported classification registry schema")
    evidence_output = registry.get("evidence_output")
    expected = registry.get("expected_occurrences_by_rule")
    rules = registry.get("classifications")
    if (
        not isinstance(evidence_output, str)
        or not isinstance(expected, dict)
        or not isinstance(rules, list)
    ):
        raise VerificationError("classification registry has an invalid shape")

    ids: set[str] = set()
    normalized: list[dict[str, str]] = []
    for raw in rules:
        if not isinstance(raw, dict):
            raise VerificationError("classification rule is not an object")
        rule = {key: raw.get(key) for key in ("id", "kind", "path", "category", "reason")}
        if not all(isinstance(value, str) and value for value in rule.values()):
            raise VerificationError("classification rule contains an empty field")
        if rule["id"] in ids:
            raise VerificationError(f"duplicate classification id {rule['id']!r}")
        ids.add(rule["id"])
        if rule["kind"] not in {"exact", "prefix"}:
            raise VerificationError(f"invalid classification kind for {rule['id']!r}")
        if rule["category"] not in ALLOWED_CATEGORIES:
            raise VerificationError(f"invalid category for {rule['id']!r}")
        if rule["path"].startswith("/") or "\\" in rule["path"] or ".." in Path(rule["path"]).parts:
            raise VerificationError(f"unsafe classification path for {rule['id']!r}")
        normalized.append(rule)  # type: ignore[arg-type]
    if set(expected) != ids or not all(
        isinstance(count, int) and count >= 0 for count in expected.values()
    ):
        raise VerificationError("expected occurrence counts do not exactly match rule ids")
    return evidence_output, expected, normalized


def matching_rules(path: str, rules: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        rule
        for rule in rules
        if (rule["kind"] == "exact" and path == rule["path"])
        or (rule["kind"] == "prefix" and path.startswith(rule["path"]))
    ]


def validate_rule_targets(paths: list[str], rules: list[dict[str, str]]) -> None:
    tracked = set(paths)
    for rule in rules:
        exists = (
            rule["path"] in tracked
            if rule["kind"] == "exact"
            else any(path.startswith(rule["path"]) for path in paths)
        )
        if not exists:
            raise VerificationError(f"classification target is missing: {rule['id']}")


def metadata_gate(root: Path) -> dict[str, int]:
    result = subprocess.run(
        ["cargo", "metadata", "--no-deps", "--locked", "--format-version", "1"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise VerificationError("cargo metadata identity surface could not be generated")
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("cargo metadata did not emit JSON") from error
    identities = [
        text
        for package in metadata.get("packages", [])
        for text in (
            package.get("name", ""),
            package.get("description", ""),
            *(target.get("name", "") for target in package.get("targets", [])),
        )
        if isinstance(text, str)
    ]
    occurrences = sum(len(RETIRED_NAME.findall(text)) for text in identities)
    if occurrences:
        raise VerificationError("generated Cargo metadata retains an active retired identity")
    return {
        "packages": len(metadata.get("packages", [])),
        "identity_strings": len(identities),
        "retired_name_occurrences": occurrences,
    }


def help_gate(root: Path) -> dict[str, Any]:
    candidates = (root / "target/debug/saddlectl.exe", root / "target/debug/saddlectl")
    binary = next((path for path in candidates if path.is_file()), None)
    if binary is None:
        raise VerificationError("saddlectl help artifact is missing; build the binary before this gate")
    result = subprocess.run(
        [str(binary), "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = result.stdout + result.stderr
    occurrences = len(RETIRED_NAME.findall(output))
    if result.returncode not in {0, 2} or "usage: saddlectl" not in output or occurrences:
        raise VerificationError("saddlectl help surface retains an invalid or retired identity")
    return {
        "artifact": "target/debug/saddlectl",
        "exit_code": result.returncode,
        "retired_name_occurrences": occurrences,
    }


def explicit_surface_counts(root: Path, paths: list[str]) -> dict[str, Any]:
    schemas = []
    for relative in GENERATED_SCHEMAS:
        text = (root / relative).read_text(encoding="utf-8")
        occurrences = len(RETIRED_NAME.findall(text))
        if occurrences:
            raise VerificationError(f"generated schema retains a retired identity: {relative}")
        schemas.append({"path": relative, "retired_name_occurrences": occurrences})
    return {
        "cargo_manifests": sum(path.endswith("Cargo.toml") for path in paths),
        "console_ui_files": sum(path.startswith("console/") for path in paths),
        "deployment_artifact_files": sum(path.startswith("deployment/") for path in paths),
        "packaging_artifact_files": sum(path.startswith("packaging/") for path in paths),
        "script_files": sum(path.startswith("scripts/") for path in paths),
        "generated_schemas": schemas,
    }


def generated_console_gate(root: Path) -> dict[str, int]:
    output = root / "console/dist"
    if not output.is_dir():
        raise VerificationError("generated console artifact is missing; build the UI before this gate")
    files = sorted(path for path in output.rglob("*") if path.is_file())
    text_files = 0
    binary_files = 0
    occurrences = 0
    for path in files:
        content = path.read_bytes()
        if b"\0" in content:
            binary_files += 1
            continue
        text_files += 1
        occurrences += len(RETIRED_NAME.findall(content.decode("utf-8", errors="replace")))
    if occurrences:
        raise VerificationError("generated console artifact retains a retired identity")
    return {
        "files": len(files),
        "text_files": text_files,
        "binary_files": binary_files,
        "retired_name_occurrences": occurrences,
    }


def evidence_for(
    root: Path,
    paths: list[str],
    rules: list[dict[str, str]],
    expected_occurrences: dict[str, int],
    excluded_output: str,
) -> dict[str, Any]:
    missing_surfaces = [surface for surface in REQUIRED_SURFACES if not (root / surface).exists()]
    if missing_surfaces:
        raise VerificationError(f"required active surfaces are missing: {missing_surfaces}")
    validate_rule_targets(paths, rules)

    text_files = 0
    binary_files = 0
    classifications: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    total_occurrences = 0

    for relative in paths:
        if relative == excluded_output:
            continue
        path_matches = len(RETIRED_NAME.findall(relative))
        content = (root / relative).read_bytes()
        if b"\0" in content:
            binary_files += 1
            content_matches = 0
        else:
            text_files += 1
            content_matches = len(RETIRED_NAME.findall(content.decode("utf-8", errors="replace")))
        occurrences = path_matches + content_matches
        if occurrences == 0:
            continue
        total_occurrences += occurrences
        matches = matching_rules(relative, rules)
        record = {
            "content_occurrences": content_matches,
            "path": relative,
            "path_occurrences": path_matches,
            "total_occurrences": occurrences,
        }
        if len(matches) != 1:
            record["matching_rule_ids"] = [rule["id"] for rule in matches]
            unexplained.append(record)
            continue
        rule = matches[0]
        record.update(
            {
                "category": rule["category"],
                "reason": rule["reason"],
                "rule_id": rule["id"],
            }
        )
        classifications.append(record)
        category_counts[rule["category"]] += occurrences
        rule_counts[rule["id"]] += occurrences

    classifications.sort(key=lambda item: item["path"])
    unexplained.sort(key=lambda item: item["path"])
    count_mismatches = [
        {
            "expected": expected_occurrences[rule_id],
            "observed": rule_counts[rule_id],
            "rule_id": rule_id,
        }
        for rule_id in sorted(expected_occurrences)
        if rule_counts[rule_id] != expected_occurrences[rule_id]
    ]
    return {
        "schema_version": 1,
        "status": "PASS" if not unexplained and not count_mismatches else "FAIL",
        "tracked_files_scanned": len(paths) - int(excluded_output in paths),
        "text_files_scanned": text_files,
        "binary_files_skipped": binary_files,
        "classified_files": len(classifications),
        "classified_occurrences_by_category": dict(sorted(category_counts.items())),
        "classification_count_mismatches": count_mismatches,
        "cargo_metadata_surface": metadata_gate(root),
        "help_surface": help_gate(root),
        "explicit_surface_counts": explicit_surface_counts(root, paths),
        "generated_console_artifact": generated_console_gate(root),
        "total_retired_name_occurrences": total_occurrences,
        "classifications": classifications,
        "unexplained_matches": unexplained,
    }


def write_or_verify(destination: Path, expected: bytes, verify_only: bool) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise VerificationError(f"evidence destination is not a regular file: {destination}")
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
    if not root.is_dir():
        raise VerificationError("repository root does not exist")
    registry_path = args.classifications
    if not registry_path.is_absolute():
        registry_path = root / registry_path
    configured_output, expected_occurrences, rules = load_registry(registry_path)
    output = args.evidence_output
    if not output.is_absolute():
        output = root / output
    try:
        output_relative = output.resolve().relative_to(root).as_posix()
    except ValueError as error:
        raise VerificationError("evidence output escapes repository root") from error
    if output_relative != configured_output:
        raise VerificationError("evidence output does not match the reviewed registry")

    paths = tracked_paths(root)
    evidence = evidence_for(root, paths, rules, expected_occurrences, configured_output)
    if evidence["status"] != "PASS":
        raise VerificationError("unexplained or ambiguously classified active-name matches remain")
    expected = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_or_verify(output, expected, args.verify)
    print(
        "SAD-23 active-name eradication gate: PASS "
        f"({evidence['classified_files']} classified files, "
        f"{evidence['total_retired_name_occurrences']} explained occurrences)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"SAD-23 active-name eradication gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
