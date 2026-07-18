#!/usr/bin/env python3
"""Verify the SAD-20 orchestration package and binary identity cutover."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the package identity gate cannot prove the required map."""


PACKAGE_MAP = {
    "aog-apiserver": "saddle-apiserver",
    "aog-conformance": "saddle-conformance",
    "aog-controller": "saddle-controller",
    "aog-estate": "saddle-estate",
    "aog-federation": "saddle-federation",
    "aog-node": "saddle-node",
    "aog-noded": "saddle-noded",
    "aog-scheduler": "saddle-scheduler",
    "aog-store": "saddle-store",
    "aog-wire": "saddle-wire",
    "aogctl": "saddlectl",
    "aogd": "saddled",
}
RETAINED_AOG_PACKAGES = {
    "aog-approvals",
    "aog-gateway",
    "aog-toolproxy",
    "aog-tool-runtime",
}
BINARY_MAP = {
    "aog-noded": "saddle-noded",
    "aogctl": "saddlectl",
    "aogd": "saddled",
}
ACTIVE_ROOTS = (
    ".cargo",
    ".github",
    "config",
    "configs",
    "console",
    "contracts",
    "crates",
    "deployment",
    "packaging",
    "scripts",
    "tests",
)
ACTIVE_FILES = ("Cargo.lock", "Cargo.toml", "Dockerfile", "README.md")
TEXT_SUFFIXES = {
    "",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
}


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


def cargo_metadata(root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "metadata", "--format-version=1", "--no-deps", "--locked"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise VerificationError(f"cargo metadata failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def iter_active_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in ACTIVE_FILES:
        path = root / relative
        if path.is_file():
            paths.append(path)
    for relative in ACTIVE_ROOTS:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in {"node_modules", "target"} for part in path.parts):
                continue
            paths.append(path)
    return sorted(set(paths))


def old_identity_findings(root: Path) -> list[dict[str, Any]]:
    old_tokens = sorted(
        set(PACKAGE_MAP) | {name.replace("-", "_") for name in PACKAGE_MAP},
        key=lambda value: (-len(value), value),
    )
    findings: list[dict[str, Any]] = []
    for path in iter_active_files(root):
        content = path.read_bytes()
        if b"\x00" in content:
            continue
        text = content.decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            matches = [token for token in old_tokens if token in line]
            if matches:
                findings.append(
                    {
                        "line": line_number,
                        "path": path.relative_to(root).as_posix(),
                        "tokens": matches,
                    }
                )
    return findings


def evidence_for(root: Path) -> dict[str, Any]:
    metadata = cargo_metadata(root)
    packages = {package["name"]: package for package in metadata["packages"]}
    package_names = set(packages)
    expected_packages = set(PACKAGE_MAP.values())
    old_packages = set(PACKAGE_MAP)

    missing_packages = sorted(expected_packages - package_names)
    unexpected_old_packages = sorted(old_packages & package_names)
    missing_retained_aog_packages = sorted(RETAINED_AOG_PACKAGES - package_names)

    target_names = {
        target["name"]
        for package in metadata["packages"]
        for target in package["targets"]
        if "bin" in target["kind"]
    }
    missing_binaries = sorted(set(BINARY_MAP.values()) - target_names)
    unexpected_old_binaries = sorted(set(BINARY_MAP) & target_names)

    missing_directories = sorted(
        destination
        for destination in PACKAGE_MAP.values()
        if not (root / "crates" / destination).is_dir()
    )
    old_directories = sorted(
        source for source in PACKAGE_MAP if (root / "crates" / source).exists()
    )
    cargo_manifest_loom_references = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "crates").glob("*/Cargo.toml")
        if path.parent.name in expected_packages
        and "Loom" in path.read_text(encoding="utf-8")
    )
    active_findings = old_identity_findings(root)

    evidence: dict[str, Any] = {
        "active_old_identity_findings": active_findings,
        "binary_map": dict(sorted(BINARY_MAP.items())),
        "cargo_manifest_loom_references": cargo_manifest_loom_references,
        "expected_package_map": dict(sorted(PACKAGE_MAP.items())),
        "missing_binaries": missing_binaries,
        "missing_directories": missing_directories,
        "missing_packages": missing_packages,
        "missing_retained_aog_packages": missing_retained_aog_packages,
        "old_directories": old_directories,
        "retained_aog_packages": sorted(RETAINED_AOG_PACKAGES),
        "schema_version": 1,
        "unexpected_old_binaries": unexpected_old_binaries,
        "unexpected_old_packages": unexpected_old_packages,
        "workspace_package_count": len(package_names),
    }
    failure_count = sum(
        len(items)
        for items in (
            active_findings,
            cargo_manifest_loom_references,
            missing_binaries,
            missing_directories,
            missing_packages,
            missing_retained_aog_packages,
            old_directories,
            unexpected_old_binaries,
            unexpected_old_packages,
        )
    )
    evidence["status"] = "PASS" if failure_count == 0 else "FAIL"
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
        raise VerificationError("package identity gate found an incomplete or duplicate active identity")
    expected = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_or_verify(output, expected, args.verify)
    print(
        "SAD-20 package identity gate: PASS "
        f"({len(PACKAGE_MAP)} packages, {len(BINARY_MAP)} binaries, "
        f"{len(RETAINED_AOG_PACKAGES)} retained AOG packages)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"SAD-20 package identity gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
