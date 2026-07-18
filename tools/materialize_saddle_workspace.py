#!/usr/bin/env python3
"""Materialize and verify the SAD-10 native Saddle workspace cut.

The import is intentionally blob-based rather than a working-tree copy.  Every
selected file is read from the approved seed Git object recorded in the SAD-02
manifest, checked against its recorded mode, size, and SHA-256, and then
written byte-for-byte into Saddle.  The only adapted file is the root workspace
manifest: its member list is narrowed to the recorded 37-package closure so
that Cargo never resolves omitted parent-repository members.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT_RAW_PATHS = frozenset({".cargo/audit.toml", "Cargo.lock", "deny.toml"})
ROOT_WORKSPACE_MANIFEST = "Cargo.toml"
TARGET_ATTRIBUTES_PATH = ".gitattributes"
TARGET_ATTRIBUTES = (
    b"# Preserve the approved seed blob's intentional mixed line endings.\n"
    b"mai-core/src/power/demotion.rs whitespace=-trailing-space\n"
)
SAFE_MODES = frozenset({"100644", "100755"})


class MaterializationError(RuntimeError):
    """Raised when the seed, ledger, destination, or metadata gate disagrees."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def checked_relative_path(path: str) -> Path:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or path.startswith("/"):
        raise MaterializationError(f"unsafe manifest path: {path}")
    return Path(*pure.parts)


def run_git(seed_repo: Path, *arguments: str, text: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(seed_repo), *arguments],
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() if text else completed.stderr.decode("utf-8", "replace").strip()
        raise MaterializationError(f"seed Git command failed ({' '.join(arguments)}): {stderr}")
    return completed.stdout


def verify_seed(seed_repo: Path, seed_sha: str) -> None:
    if not seed_repo.is_dir():
        raise MaterializationError(f"seed repository does not exist: {seed_repo}")
    head = str(run_git(seed_repo, "rev-parse", "HEAD", text=True)).strip()
    if head != seed_sha:
        raise MaterializationError(f"seed HEAD mismatch: expected {seed_sha}, found {head}")
    status = str(run_git(seed_repo, "status", "--porcelain", text=True)).strip()
    if status:
        raise MaterializationError("seed worktree is not clean")


def load_manifest(path: Path, seed_sha: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise MaterializationError(f"cannot read source manifest: {error}") from error
    if manifest.get("seed", {}).get("sha") != seed_sha:
        raise MaterializationError("source manifest seed SHA does not match the requested seed")
    if manifest.get("schema_version") != 1:
        raise MaterializationError("unsupported source manifest schema")
    return manifest, raw


def entries_by_path(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("entries", []):
        path = entry.get("path")
        if not isinstance(path, str) or path in entries:
            raise MaterializationError("source manifest has a missing or duplicate path")
        entries[path] = entry
    return entries


def closure_members(manifest: dict[str, Any]) -> tuple[list[str], list[str]]:
    packages = manifest.get("cargo_dependency_closure", {}).get("packages")
    if not isinstance(packages, list) or not packages:
        raise MaterializationError("source manifest has no Cargo dependency closure")
    members: list[str] = []
    package_names: list[str] = []
    for package in packages:
        member = package.get("path") if isinstance(package, dict) else None
        name = package.get("name") if isinstance(package, dict) else None
        if (
            not isinstance(member, str)
            or not member
            or member in members
            or not isinstance(name, str)
            or not name
            or name in package_names
        ):
            raise MaterializationError("source manifest has an invalid Cargo closure package")
        checked_relative_path(member)
        members.append(member)
        package_names.append(name)
    expected_count = manifest.get("cargo_dependency_closure", {}).get("package_count")
    if expected_count != len(members):
        raise MaterializationError("Cargo dependency closure count does not match its package list")
    return members, package_names


def selected_entries(
    manifest_entries: dict[str, dict[str, Any]], members: list[str]
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    required_roots = set(ROOT_RAW_PATHS) | {ROOT_WORKSPACE_MANIFEST}
    for path in required_roots:
        entry = manifest_entries.get(path)
        if entry is None or entry.get("disposition") != "import":
            raise MaterializationError(f"required SAD-10 root path is not an approved import: {path}")
        selected[path] = entry
    for member in members:
        prefix = f"{member}/"
        member_entries = [
            (path, entry)
            for path, entry in manifest_entries.items()
            if path.startswith(prefix)
        ]
        if not member_entries:
            raise MaterializationError(f"Cargo closure member has no tracked files: {member}")
        for path, entry in member_entries:
            if entry.get("disposition") != "import":
                raise MaterializationError(
                    f"Cargo closure member includes a non-import disposition: {path}"
                )
            selected[path] = entry
    return selected


def blob_bytes(seed_repo: Path, seed_sha: str, entry: dict[str, Any]) -> bytes:
    path = entry.get("path")
    mode = entry.get("mode")
    object_id = entry.get("git_object")
    expected_size = entry.get("byte_size")
    expected_hash = entry.get("sha256")
    if not isinstance(path, str) or not isinstance(object_id, str):
        raise MaterializationError("manifest entry has no path or Git object")
    checked_relative_path(path)
    if mode not in SAFE_MODES:
        raise MaterializationError(f"unsupported SAD-10 import mode for {path}: {mode}")
    tree_record = str(run_git(seed_repo, "ls-tree", seed_sha, "--", path, text=True)).strip()
    if "\t" not in tree_record:
        raise MaterializationError(f"seed tree has no tracked blob for {path}")
    tree_metadata, tree_path = tree_record.split("\t", maxsplit=1)
    tree_mode, tree_type, tree_object = tree_metadata.split(maxsplit=2)
    if tree_path != path or tree_mode != mode or tree_type != "blob" or tree_object != object_id:
        raise MaterializationError(f"seed tree provenance mismatch for {path}")
    object_type = str(run_git(seed_repo, "cat-file", "-t", object_id, text=True)).strip()
    if object_type != "blob":
        raise MaterializationError(f"manifest object is not a blob for {path}")
    data = bytes(run_git(seed_repo, "cat-file", "blob", object_id))
    if len(data) != expected_size:
        raise MaterializationError(f"byte-size mismatch for {path}")
    if sha256_bytes(data) != expected_hash:
        raise MaterializationError(f"SHA-256 mismatch for {path}")
    return data


def source_workspace_members(cargo_toml: bytes) -> list[str]:
    try:
        text = cargo_toml.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError("root Cargo.toml is not UTF-8") from error
    match = re.search(r"(?ms)^members = \[\n(?P<body>.*?)^\]", text)
    if match is None:
        raise MaterializationError("root Cargo.toml has no parseable workspace member list")
    members = re.findall(r'^\s*"(?P<member>[^"]+)",\s*$', match.group("body"), re.MULTILINE)
    if not members or len(members) != len(set(members)):
        raise MaterializationError("root Cargo.toml has an invalid workspace member list")
    return members


def adapted_workspace_manifest(cargo_toml: bytes, closure: list[str]) -> tuple[bytes, list[str]]:
    try:
        text = cargo_toml.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError("root Cargo.toml is not UTF-8") from error
    match = re.search(r"(?ms)^members = \[\n(?P<body>.*?)^\]", text)
    if match is None:
        raise MaterializationError("root Cargo.toml has no replaceable workspace member list")
    source_members = source_workspace_members(cargo_toml)
    closure_set = set(closure)
    selected = [member for member in source_members if member in closure_set]
    if set(selected) != closure_set:
        missing = ", ".join(sorted(closure_set - set(selected)))
        raise MaterializationError(f"Cargo closure members are absent from root Cargo.toml: {missing}")
    newline = "\r\n" if "\r\n" in text else "\n"
    replacement = "members = [" + newline
    replacement += "".join(f'    "{member}",{newline}' for member in selected)
    replacement += "]"
    adapted = text[: match.start()] + replacement + text[match.end() :]
    return adapted.encode("utf-8"), selected


def write_or_verify(
    destination: Path, expected: bytes, verify_only: bool, replace_existing: bool = False
) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise MaterializationError(f"destination collision is not a regular file: {destination}")
        try:
            actual = destination.read_bytes()
        except OSError as error:
            raise MaterializationError(f"cannot read destination {destination}: {error}") from error
        if actual != expected:
            if verify_only or not replace_existing:
                raise MaterializationError(f"destination bytes do not match expected content: {destination}")
            destination.write_bytes(expected)
        return
    if verify_only:
        raise MaterializationError(f"required materialized path is missing: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(expected)


def write_or_verify_attribute_prefix(destination: Path, required_prefix: bytes, verify_only: bool) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise MaterializationError(f"attribute policy collision is not a regular file: {destination}")
        try:
            actual = destination.read_bytes()
        except OSError as error:
            raise MaterializationError(f"cannot read attribute policy: {destination}: {error}") from error
        if not actual.startswith(required_prefix):
            raise MaterializationError(f"attribute policy is missing the SAD-10 required prefix: {destination}")
        return
    if verify_only:
        raise MaterializationError(f"required attribute policy is missing: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(required_prefix)


def safe_destination(target_root: Path, relative_path: str) -> Path:
    destination = (target_root / checked_relative_path(relative_path)).resolve()
    if not is_within(destination, target_root):
        raise MaterializationError(f"destination escapes target root: {relative_path}")
    return destination


def root_license_or_toolchain_paths(seed_repo: Path, seed_sha: str) -> list[str]:
    tracked = str(run_git(seed_repo, "ls-tree", "-r", "--name-only", seed_sha, text=True)).splitlines()
    candidates: list[str] = []
    for path in tracked:
        if "/" in path:
            continue
        lowered = path.lower()
        if lowered.startswith(("license", "notice", "copying", "rust-toolchain")):
            candidates.append(path)
    return sorted(candidates)


def cargo_metadata_gate(
    target_root: Path, cargo: str, closure: list[str], expected_package_names: list[str]
) -> dict[str, Any]:
    command = [
        cargo,
        "metadata",
        "--format-version=1",
        "--no-deps",
        "--locked",
        "--manifest-path",
        str(target_root / ROOT_WORKSPACE_MANIFEST),
    ]
    completed = subprocess.run(command, cwd=target_root, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip().replace("\r", " ").replace("\n", " ")
        raise MaterializationError(f"cargo metadata failed: {diagnostic[-1200:]}")
    try:
        metadata = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MaterializationError(f"cargo metadata returned invalid JSON: {error}") from error
    packages = metadata.get("packages")
    workspace_members = metadata.get("workspace_members")
    if not isinstance(packages, list) or not isinstance(workspace_members, list):
        raise MaterializationError("cargo metadata does not describe a workspace")
    expected_names = set(expected_package_names)
    for member in closure:
        manifest_path = target_root / member / "Cargo.toml"
        if not manifest_path.is_file():
            raise MaterializationError(f"closure member has no materialized Cargo.toml: {member}")
    external_local_paths: list[str] = []
    package_names: list[str] = []
    for package in packages:
        name = package.get("name")
        manifest_path = package.get("manifest_path")
        if not isinstance(name, str) or not isinstance(manifest_path, str):
            raise MaterializationError("cargo metadata package record is incomplete")
        package_names.append(name)
        if not is_within(Path(manifest_path), target_root):
            external_local_paths.append("package manifest outside target root")
        for dependency in package.get("dependencies", []):
            dependency_path = dependency.get("path") if isinstance(dependency, dict) else None
            if dependency_path and not is_within(Path(dependency_path), target_root):
                external_local_paths.append(f"dependency path outside target root: {name}")
    if external_local_paths:
        raise MaterializationError("cargo metadata resolved external local paths")
    if len(packages) != len(closure) or len(workspace_members) != len(closure):
        raise MaterializationError("cargo metadata workspace size does not match the recorded closure")
    if set(package_names) != expected_names:
        raise MaterializationError("cargo metadata package names do not match the recorded closure")
    return {
        "command": "cargo metadata --format-version=1 --no-deps --locked",
        "workspace_member_count": len(workspace_members),
        "package_count": len(packages),
        "package_names": sorted(package_names),
        "external_local_path_count": 0,
    }


def build_evidence(
    manifest_bytes: bytes,
    seed_sha: str,
    closure: list[str],
    selected_members: list[str],
    selected: dict[str, dict[str, Any]],
    source_cargo: bytes,
    target_cargo: bytes,
    target_attributes: bytes,
    source_members: list[str],
    license_or_toolchain_paths: list[str],
    metadata_gate: dict[str, Any],
) -> bytes:
    raw_paths = sorted(path for path in selected if path != ROOT_WORKSPACE_MANIFEST)
    raw_records = [
        {
            "byte_size": selected[path]["byte_size"],
            "git_object": selected[path]["git_object"],
            "mode": selected[path]["mode"],
            "path": path,
            "sha256": selected[path]["sha256"],
        }
        for path in raw_paths
    ]
    evidence = {
        "cargo_metadata_gate": metadata_gate,
        "root_workspace_adaptation": {
            "adaptation": "workspace member list narrowed to the recorded internal closure",
            "omitted_seed_members": [member for member in source_members if member not in selected_members],
            "selected_members": selected_members,
            "source_sha256": sha256_bytes(source_cargo),
            "target_sha256": sha256_bytes(target_cargo),
        },
        "schema_version": 1,
        "seed": {"sha": seed_sha},
        "source_manifest_sha256": sha256_bytes(manifest_bytes),
        "source_root_license_or_toolchain_files": license_or_toolchain_paths,
        "status": "PASS",
        "target_source_preservation_policy": {
            "path": TARGET_ATTRIBUTES_PATH,
            "reason": "preserves the approved seed blob's intentional mixed line endings",
            "sha256": sha256_bytes(target_attributes),
        },
        "verified_raw_blobs": raw_records,
        "verified_raw_blob_count": len(raw_records),
    }
    return (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize and verify the SAD-10 independent native workspace."
    )
    parser.add_argument("--seed-repo", required=True, type=Path)
    parser.add_argument("--seed-sha", required=True)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--target-root", default=Path("."), type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seed_repo = args.seed_repo.resolve()
    target_root = args.target_root.resolve()
    if not target_root.is_dir():
        raise MaterializationError(f"target root does not exist: {target_root}")
    verify_seed(seed_repo, args.seed_sha)
    manifest, manifest_bytes = load_manifest(args.source_manifest.resolve(), args.seed_sha)
    ledger_entries = entries_by_path(manifest)
    closure, closure_package_names = closure_members(manifest)
    selected = selected_entries(ledger_entries, closure)

    blobs: dict[str, bytes] = {}
    for path in sorted(selected):
        blobs[path] = blob_bytes(seed_repo, args.seed_sha, selected[path])
    source_cargo = blobs[ROOT_WORKSPACE_MANIFEST]
    target_cargo, selected_members = adapted_workspace_manifest(source_cargo, closure)
    source_members = source_workspace_members(source_cargo)

    for path in sorted(selected):
        expected = target_cargo if path == ROOT_WORKSPACE_MANIFEST else blobs[path]
        write_or_verify(safe_destination(target_root, path), expected, args.verify)
    write_or_verify_attribute_prefix(
        safe_destination(target_root, TARGET_ATTRIBUTES_PATH), TARGET_ATTRIBUTES, args.verify
    )

    metadata_gate = cargo_metadata_gate(target_root, args.cargo, closure, closure_package_names)
    evidence = build_evidence(
        manifest_bytes,
        args.seed_sha,
        closure,
        selected_members,
        selected,
        source_cargo,
        target_cargo,
        TARGET_ATTRIBUTES,
        source_members,
        root_license_or_toolchain_paths(seed_repo, args.seed_sha),
        metadata_gate,
    )
    evidence_path = args.evidence_output
    if not evidence_path.is_absolute():
        evidence_path = target_root / evidence_path
    evidence_path = evidence_path.resolve()
    if not is_within(evidence_path, target_root):
        raise MaterializationError("evidence output escapes target root")
    write_or_verify(evidence_path, evidence, args.verify, replace_existing=True)

    print(
        "SAD-10 workspace materialization: PASS "
        f"({len(selected) + 1} paths, {len(closure)} Cargo packages, no external local paths)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MaterializationError as error:
        print(f"SAD-10 workspace materialization failed: {error}", file=sys.stderr)
        raise SystemExit(1)
