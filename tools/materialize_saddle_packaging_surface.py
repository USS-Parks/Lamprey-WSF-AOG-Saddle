#!/usr/bin/env python3
"""Materialize the bounded SAD-14 packaging surface from the pinned seed.

SAD-02 correctly excluded the general MAI packaging subtree because it was not
part of the initial native source closure.  SAD-14 establishes that the copied
package-build script and packaging test suite require a small, explicit
closure.  This tool preserves the original SAD-02 record and writes a separate
addendum proof for exactly that closure.  Three active package-metadata links
are adapted to Saddle's independent repository identity; every other selected
blob is byte-for-byte verified against the approved seed object.
"""

from __future__ import annotations

import argparse
import json
import stat
from pathlib import Path
from typing import Any

from materialize_saddle_workspace import (
    MaterializationError,
    blob_bytes,
    checked_relative_path,
    entries_by_path,
    is_within,
    load_manifest,
    sha256_bytes,
    verify_seed,
    write_or_verify,
)


PACKAGING_GATE_PATHS = (
    "packaging/README.md",
    "packaging/debian/changelog",
    "packaging/debian/compat",
    "packaging/debian/conffiles",
    "packaging/debian/control",
    "packaging/debian/copyright",
    "packaging/debian/install",
    "packaging/debian/rules",
    "packaging/debian/source/format",
    "packaging/scripts/mai-healthcheck.sh",
    "packaging/scripts/mai-ship-validate.sh",
    "packaging/scripts/postinstall.sh",
    "packaging/scripts/postremove.sh",
    "packaging/scripts/preinstall.sh",
    "packaging/scripts/preremove.sh",
    "packaging/systemd/mai-adapter-manager.service",
    "packaging/systemd/mai-api.service",
    "packaging/systemd/mai-dashboard.service",
    "packaging/systemd/mai-healthcheck.service",
    "packaging/systemd/mai-healthcheck.timer",
)
ADAPTED_IDENTITY_PATHS = frozenset(
    {
        "packaging/debian/control",
        "packaging/debian/copyright",
        "packaging/systemd/mai-api.service",
    }
)
SOURCE_REPOSITORY = b"https://github.com/USS-Parks/" + b"Mighty-Eel-OS"
SADDLE_REPOSITORY = b"https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-repo", required=True, type=Path)
    parser.add_argument("--seed-sha", required=True)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--target-root", default=Path("."), type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def selected_entries(entries: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for path in PACKAGING_GATE_PATHS:
        entry = entries.get(path)
        if entry is None:
            raise MaterializationError(f"SAD-02 manifest has no packaging gate entry: {path}")
        if entry.get("disposition") != "out-of-scope-no-match":
            raise MaterializationError(
                f"SAD-14 expected the original out-of-scope disposition for {path}"
            )
        selected[path] = entry
    return selected


def adapt_identity(path: str, source: bytes) -> tuple[bytes, bool]:
    if path not in ADAPTED_IDENTITY_PATHS:
        return source, False
    occurrences = source.count(SOURCE_REPOSITORY)
    if occurrences != 1:
        raise MaterializationError(
            f"expected exactly one source repository identity in {path}, found {occurrences}"
        )
    target = source.replace(SOURCE_REPOSITORY, SADDLE_REPOSITORY)
    if SOURCE_REPOSITORY in target or SADDLE_REPOSITORY not in target:
        raise MaterializationError(f"repository identity adaptation failed for {path}")
    return target, True


def evidence_bytes(
    manifest_bytes: bytes,
    seed_sha: str,
    records: list[dict[str, Any]],
) -> bytes:
    evidence = {
        "adaptation": {
            "count": sum(1 for record in records if record["repository_identity_adapted"]),
            "reason": "active package metadata must point to Saddle's independent repository",
            "target_repository": SADDLE_REPOSITORY.decode("ascii"),
        },
        "original_manifest_disposition": "out-of-scope-no-match",
        "reason": (
            "SAD-14 packaging validation requires the bounded closure consumed by the "
            "already imported package-build script and packaging tests; SAD-02 evidence remains unchanged."
        ),
        "schema_version": 1,
        "seed": {"sha": seed_sha},
        "source_manifest_sha256": sha256_bytes(manifest_bytes),
        "status": "PASS",
        "target_path_count": len(records),
        "target_paths": records,
    }
    return (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")


def resolve_within(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not is_within(resolved, root):
        raise MaterializationError(f"path escapes target root: {resolved}")
    return resolved


def apply_mode(destination: Path, entry: dict[str, Any], verify_only: bool) -> None:
    if entry["mode"] == "100755" and not verify_only:
        destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    args = parse_args()
    seed_repo = args.seed_repo.resolve()
    target_root = args.target_root.resolve()
    if not target_root.is_dir():
        raise MaterializationError(f"target root does not exist: {target_root}")
    verify_seed(seed_repo, args.seed_sha)
    manifest, manifest_bytes = load_manifest(args.source_manifest.resolve(), args.seed_sha)
    selected = selected_entries(entries_by_path(manifest))
    records: list[dict[str, Any]] = []
    for path, entry in sorted(selected.items()):
        source = blob_bytes(seed_repo, args.seed_sha, entry)
        target, adapted = adapt_identity(path, source)
        destination = resolve_within(target_root, target_root / checked_relative_path(path))
        write_or_verify(destination, target, args.verify)
        apply_mode(destination, entry, args.verify)
        records.append(
            {
                "mode": entry["mode"],
                "path": path,
                "repository_identity_adapted": adapted,
                "seed_git_object": entry["git_object"],
                "seed_sha256": entry["sha256"],
                "source_byte_size": entry["byte_size"],
                "target_sha256": sha256_bytes(target),
            }
        )
    evidence_path = args.evidence_output
    if not evidence_path.is_absolute():
        evidence_path = target_root / evidence_path
    evidence_path = resolve_within(target_root, evidence_path)
    write_or_verify(
        evidence_path,
        evidence_bytes(manifest_bytes, args.seed_sha, records),
        args.verify,
        replace_existing=True,
    )
    print(
        "SAD-14 packaging-surface materialization: PASS "
        f"({len(records)} paths, {sum(record['repository_identity_adapted'] for record in records)} identity adaptations)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MaterializationError as error:
        print(f"SAD-14 packaging-surface materialization failed: {error}")
        raise SystemExit(2)
