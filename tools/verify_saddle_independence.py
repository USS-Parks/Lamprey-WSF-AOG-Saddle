#!/usr/bin/env python3
"""Verify that Saddle's tracked executable surface has no parent-repository coupling."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the independence gate cannot establish a required property."""


PARENT_REPOSITORIES = ("Mighty" + "-Eel-OS", "im-" + "mighty-eel-mai", "lamprey")
PARENT_DIRECTORIES = ("Mighty" + " Eel OS", "Lamprey" + " Harness")
NARRATIVE_PREFIXES = ("PLANNING/", "docs/", "test-evidence/")
NARRATIVE_FILENAMES = frozenset({".secrets.baseline"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root}", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise VerificationError(f"Git command failed: {' '.join(args)}: {completed.stderr.strip()}")
    return completed.stdout


def tracked_entries(root: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in run_git(root, "ls-files", "-s").splitlines():
        metadata, path = line.split("\t", 1)
        entries.append((metadata.split()[0], path))
    return entries


def is_narrative(path: str) -> bool:
    return path.startswith(NARRATIVE_PREFIXES) or path.endswith(".md") or path in NARRATIVE_FILENAMES


def reference_patterns() -> list[tuple[str, re.Pattern[str]]]:
    repositories = "|".join(re.escape(name) for name in PARENT_REPOSITORIES)
    directories = "|".join(re.escape(name) for name in PARENT_DIRECTORIES)
    return [
        (
            "parent GitHub repository",
            re.compile(r"https?://github\\.com/USS-Parks/(?:" + repositories + r")(?:[/?#]|$)", re.I),
        ),
        (
            "parent local checkout",
            re.compile(
                r"C:[\\/]+Users[\\/]+[^\\/]+[\\/]Documents[\\/]Claude[\\/]+(?:"
                + directories
                + r")(?:[\\/]|$)",
                re.I,
            ),
        ),
        (
            "parent relative checkout",
            re.compile(r"\\.\\.[\\/]+(?:" + directories + r")(?:[\\/]|$)", re.I),
        ),
    ]


def forbidden_references(root: Path, entries: list[tuple[str, str]]) -> tuple[int, list[dict[str, Any]]]:
    narrative_count = 0
    findings: list[dict[str, Any]] = []
    patterns = reference_patterns()
    for mode, path in entries:
        if mode not in {"100644", "100755"}:
            continue
        if is_narrative(path):
            narrative_count += 1
            continue
        content = (root / path).read_bytes()
        if b"\x00" in content:
            continue
        text = content.decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in patterns:
                if pattern.search(line):
                    findings.append({"kind": label, "line": line_number, "path": path})
    return narrative_count, findings


def external_cargo_paths(root: Path, entries: list[tuple[str, str]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    pattern = re.compile(r"\bpath\s*=\s*\"([^\"]+)\"")
    for mode, path in entries:
        if mode not in {"100644", "100755"} or Path(path).name != "Cargo.toml":
            continue
        manifest = root / path
        for relative in pattern.findall(manifest.read_text(encoding="utf-8")):
            resolved = (manifest.parent / relative).resolve()
            if not is_within(resolved, root):
                findings.append({"manifest": path, "path": relative})
    return findings


def evidence_for(root: Path) -> dict[str, Any]:
    entries = tracked_entries(root)
    symlinks = [path for mode, path in entries if mode == "120000"]
    submodules = [path for mode, path in entries if mode == "160000"]
    submodule_status = [line for line in run_git(root, "submodule", "status").splitlines() if line]
    narrative_count, references = forbidden_references(root, entries)
    cargo_paths = external_cargo_paths(root, entries)
    active_count = len(entries) - narrative_count
    evidence = {
        "active_tracked_path_count": active_count,
        "external_cargo_path_dependencies": cargo_paths,
        "forbidden_parent_references": references,
        "historical_exclusion_policy": {
            "excluded": ["PLANNING/", "docs/", "test-evidence/", "Markdown narrative files", ".secrets.baseline"],
            "reason": "preserved provenance and executed history are non-executable and do not establish a build dependency",
        },
        "historical_or_narrative_path_count": narrative_count,
        "schema_version": 1,
        "submodule_status_entries": submodule_status,
        "submodule_tree_paths": submodules,
        "symlink_tree_paths": symlinks,
        "tracked_path_count": len(entries),
    }
    failures = len(references) + len(cargo_paths) + len(symlinks) + len(submodules) + len(submodule_status)
    evidence["status"] = "PASS" if failures == 0 else "FAIL"
    return evidence


def write_or_verify(destination: Path, expected: bytes, verify_only: bool) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise VerificationError(f"evidence destination is not a regular file: {destination}")
        actual = destination.read_bytes()
        if actual != expected:
            if verify_only:
                raise VerificationError("existing evidence does not match the deterministic gate output")
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
        raise VerificationError("root does not exist")
    output = args.evidence_output if args.evidence_output.is_absolute() else root / args.evidence_output
    output = output.resolve()
    if not is_within(output, root):
        raise VerificationError("evidence output escapes root")
    evidence = evidence_for(root)
    if evidence["status"] != "PASS":
        raise VerificationError(
            "independence gate found parent references, external Cargo paths, submodules, or symlinks"
        )
    expected = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_or_verify(output, expected, args.verify)
    print(
        "SAD-12 independence gate: PASS "
        f"({evidence['active_tracked_path_count']} active paths, no external Cargo paths, submodules, or symlinks)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"SAD-12 independence gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
