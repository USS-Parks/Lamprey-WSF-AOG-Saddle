#!/usr/bin/env python3
"""Verify the SAD-21 active runtime identity cutover to Saddle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    """Raised when the runtime identity gate cannot prove the required map."""


ACTIVE_ROOTS = (
    ".github/workflows",
    "crates",
    "deployment",
)
ACTIVE_FILES = (
    "docs/SADDLE-DR-RUNBOOK.md",
    "docs/operations/SADDLE-CONTROL-PLANE-TLS.md",
)
TEXT_SUFFIXES = {"", ".md", ".rs", ".sh", ".toml", ".yaml", ".yml"}
REQUIRED_PATHS = (
    "crates/wsf-hardening/tests/saddle_guard.rs",
    "deployment/saddle-harness/docker-compose.yml",
    "deployment/saddle-harness/k3s/saddle.yaml",
    "docs/SADDLE-DR-RUNBOOK.md",
    "docs/operations/SADDLE-CONTROL-PLANE-TLS.md",
)
FORBIDDEN_PATHS = (
    "crates/wsf-hardening/tests/loom_guard.rs",
    "deployment/loom-harness",
    "docs" + "/LOOM-DR-RUNBOOK.md",
    "docs" + "/operations/AOG-CONTROL-PLANE-TLS.md",
)
REQUIRED_MARKERS = {
    "api_group": "saddle.islandmountain.io/v1",
    "cli_env": "SADDLECTL_SERVER",
    "cordon_label": "saddle.islandmountain.io/unschedulable",
    "daemon_env": "SADDLED_NODE_ID",
    "deployment": "deployment/saddle-harness",
    "forwarded_header": "x-saddle-forwarded",
    "node_env": "SADDLE_NODE_NAME",
    "openbao_default": "kv/data/saddle/trust",
    "spiffe_prefix": "spiffe://saddle/node/",
    "trust_role": "saddle-admin",
}
FORBIDDEN_PATTERNS = {
    "old_api_group": re.compile(r"aog\.islandmountain\.io"),
    "old_cli_env": re.compile(r"\bAOGCTL_[A-Z0-9_]+\b"),
    "old_cordon_or_finalizer": re.compile(r"loom\.(?:aog|io)/", re.IGNORECASE),
    "old_daemon_env": re.compile(r"\bAOGD_[A-Z0-9_]+\b"),
    "old_deployment": re.compile(r"(?:deployment/)?loom-harness", re.IGNORECASE),
    "old_forwarded_header": re.compile(r"x-loom-forwarded", re.IGNORECASE),
    "old_node_env": re.compile(r"\bAOG_NODE_[A-Z0-9_]+\b"),
    "old_openbao_path": re.compile(r"kv/data/loom(?:/|[-_])", re.IGNORECASE),
    "old_spiffe": re.compile(r"spiffe://loom/", re.IGNORECASE),
    "old_trust_role": re.compile(r"\baog-admin\b", re.IGNORECASE),
    "old_loom_env": re.compile(r"\bLOOM_[A-Z0-9_]+\b"),
}

# These two negative authorization assertions intentionally carry retired caller
# inputs. They are executable proof that compatibility cannot become authority.
NEGATIVE_AUTH_FIXTURE = "crates/saddled/tests/admin_auth.rs"
ALLOWED_NEGATIVE_TOKENS = {"x-loom-forwarded", "aog-admin"}


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


def scan_active_files(root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    findings: list[dict[str, Any]] = []
    marker_counts = {name: 0 for name in REQUIRED_MARKERS}
    for path in iter_active_files(root):
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        if b"\x00" in content:
            continue
        text = content.decode("utf-8", errors="replace")
        for name, marker in REQUIRED_MARKERS.items():
            marker_counts[name] += text.count(marker)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in FORBIDDEN_PATTERNS.items():
                matches = sorted(set(pattern.findall(line)))
                if not matches:
                    continue
                normalized = {
                    match.lower() if isinstance(match, str) else str(match).lower()
                    for match in matches
                }
                if relative == NEGATIVE_AUTH_FIXTURE and normalized <= ALLOWED_NEGATIVE_TOKENS:
                    continue
                findings.append(
                    {
                        "identity": name,
                        "line": line_number,
                        "matches": matches,
                        "path": relative,
                    }
                )
    return findings, marker_counts


def evidence_for(root: Path) -> dict[str, Any]:
    findings, marker_counts = scan_active_files(root)
    missing_paths = sorted(path for path in REQUIRED_PATHS if not (root / path).is_file())
    retained_paths = sorted(path for path in FORBIDDEN_PATHS if (root / path).exists())
    missing_markers = sorted(name for name, count in marker_counts.items() if count == 0)

    fixture = root / NEGATIVE_AUTH_FIXTURE
    fixture_text = fixture.read_text(encoding="utf-8") if fixture.is_file() else ""
    missing_negative_auth_assertions = sorted(
        token for token in ALLOWED_NEGATIVE_TOKENS if token not in fixture_text
    )

    evidence: dict[str, Any] = {
        "active_old_runtime_identity_findings": findings,
        "forbidden_paths_retained": retained_paths,
        "missing_negative_authorization_assertions": missing_negative_auth_assertions,
        "missing_required_markers": missing_markers,
        "missing_required_paths": missing_paths,
        "negative_authorization_fixture": NEGATIVE_AUTH_FIXTURE,
        "required_marker_counts": dict(sorted(marker_counts.items())),
        "schema_version": 1,
    }
    failure_count = sum(
        len(items)
        for items in (
            findings,
            retained_paths,
            missing_negative_auth_assertions,
            missing_markers,
            missing_paths,
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
        raise VerificationError("runtime identity gate found an incomplete or ambiguous cutover")
    expected = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_or_verify(output, expected, args.verify)
    print(
        "SAD-21 runtime identity gate: PASS "
        f"({len(REQUIRED_MARKERS)} markers, {len(REQUIRED_PATHS)} paths, "
        f"{len(ALLOWED_NEGATIVE_TOKENS)} negative authorization assertions)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as error:
        print(f"SAD-21 runtime identity gate failed: {error}", file=sys.stderr)
        raise SystemExit(1)
