#!/usr/bin/env python3
"""Materialize the SAD-11 support, documentation, and evidence surfaces.

This tool continues the SAD-10 blob-verified source cut.  It imports every
remaining manifest ``import`` path and all ``historical-evidence`` paths from
the approved seed, while retaining Saddle's existing canonical README instead
of replacing it with superseded MAI claims.  Three source-excluded or
out-of-scope documentation references are replaced with concise Saddle-owned
records so imported source commentary remains link-complete without importing
unsafe or irrelevant seed content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from materialize_saddle_workspace import (
    MaterializationError,
    TARGET_ATTRIBUTES,
    blob_bytes,
    entries_by_path,
    is_within,
    load_manifest,
    sha256_bytes,
    verify_seed,
    write_or_verify,
)


README_PATH = "README.md"
SAD10_CARGO_PATH = "Cargo.toml"
HISTORICAL_NOTICE_PATH = "docs/HISTORICAL-EVIDENCE-STATUS.md"
ATTRIBUTES_PATH = ".gitattributes"
SANITIZED_DOCUMENTS = {
    "docs/compliance/INDEPENDENT-EVIDENCE-DEFERRALS.md": (
        "# Saddle source-import deferrals\n\n"
        "This Saddle-owned record replaces a seed historical capture that is deliberately "
        "excluded from the independent repository because it contains token-shaped fixture "
        "material. It is not a completion claim.\n\n"
        "The source ledger records the excluded seed path, object, and hash. Any future "
        "Saddle evidence must be generated from a clean, non-secret execution and must state "
        "its own scope and verification result.\n"
    ).encode("utf-8"),
    "docs/compliance/LOCAL-TRUST-CACHE.md": (
        "# Local trust-cache boundary\n\n"
        "This Saddle-owned boundary note preserves link integrity for imported source commentary. "
        "The seed document was outside the approved source closure and is not imported here.\n\n"
        "Saddle does not claim a local trust-cache implementation from this note. Any such feature "
        "requires an explicit future prompt, implementation, and verification evidence.\n"
    ).encode("utf-8"),
    "docs/compliance/TRUST-BUNDLE-SPEC.md": (
        "# Trust-bundle specification boundary\n\n"
        "This Saddle-owned boundary note preserves link integrity for imported source commentary. "
        "The seed document was outside the approved source closure and is not imported here.\n\n"
        "The authoritative runtime behavior remains the imported code and its later Saddle-specific "
        "contracts and conformance evidence; this note makes no independent protocol-completion claim.\n"
    ).encode("utf-8"),
    "docs/ADAPTER-COMPLETION-MATRIX.md": (
        "# Adapter-completion boundary\n\n"
        "This Saddle-owned boundary note preserves link integrity for imported source commentary. "
        "The referenced source document is absent from the approved seed manifest.\n\n"
        "Saddle does not claim adapter completion from this note. Any completion matrix requires a "
        "future explicit prompt, implementation evidence, and verification result.\n"
    ).encode("utf-8"),
    "docs/SHIP-PROFILE.md": (
        "# Ship-profile boundary\n\n"
        "This Saddle-owned boundary note preserves link integrity for imported source commentary. "
        "The referenced source document is absent from the approved seed manifest.\n\n"
        "This note does not establish a Saddle ship profile, release state, or production readiness. "
        "Those claims require a future explicit prompt and independently generated evidence.\n"
    ).encode("utf-8"),
    "docs/TRUST-BRIDGE-PRODUCTION.md": (
        "# Trust-bridge production boundary\n\n"
        "This Saddle-owned boundary note preserves link integrity for imported source commentary. "
        "The referenced source document is absent from the approved seed manifest.\n\n"
        "Saddle makes no production trust-bridge claim from this note. Any production bridge requires "
        "a future explicit prompt, implementation, live-system evidence, and verification result.\n"
    ).encode("utf-8"),
}
HISTORICAL_NOTICE = (
    "# Historical source evidence status\n\n"
    "The documentation and evidence copied under this notice are preserved from the approved Mighty "
    "Eel OS seed as historical records. They may describe completed work, environments, identities, "
    "or claims from that source repository. They do not by themselves establish equivalent Saddle "
    "completion, release, deployment, or security status.\n\n"
    "Saddle status is controlled by the canonical PSPR, the Saddle DEVLOG, and the verification ledger. "
    "The source manifest and SAD-11 proof identify the exact seed blobs retained for provenance.\n"
).encode("utf-8")
WHITESPACE_POLICY_HEADER = b"\n# Preserve verified SAD-11 seed blobs with source-native whitespace.\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize and verify the SAD-11 support and historical-evidence surfaces."
    )
    parser.add_argument("--seed-repo", required=True, type=Path)
    parser.add_argument("--seed-sha", required=True)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--sad10-evidence", required=True, type=Path)
    parser.add_argument("--target-root", default=Path("."), type=Path)
    parser.add_argument("--target-readme-sha256", required=True)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def load_sad10_paths(path: Path) -> set[str]:
    try:
        evidence = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise MaterializationError(f"cannot read SAD-10 evidence: {error}") from error
    if evidence.get("status") != "PASS":
        raise MaterializationError("SAD-10 evidence is not passing")
    paths: set[str] = {SAD10_CARGO_PATH}
    for record in evidence.get("verified_raw_blobs", []):
        candidate = record.get("path") if isinstance(record, dict) else None
        if not isinstance(candidate, str):
            raise MaterializationError("SAD-10 evidence has an invalid raw-blob path")
        paths.add(candidate)
    return paths


def destination_for(target_root: Path, source_path: str) -> Path:
    destination = (target_root / Path(*Path(source_path).parts)).resolve()
    if not is_within(destination, target_root):
        raise MaterializationError(f"destination escapes target root: {source_path}")
    return destination


def requires_whitespace_preservation(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    if b"\r\n" in content or content.endswith(b"\n\n"):
        return True
    return any(line.rstrip(b"\r\n").endswith((b" ", b"\t")) for line in content.splitlines(True))


def whitespace_policy_paths(raw_contents: dict[str, bytes]) -> list[str]:
    return sorted(path for path, content in raw_contents.items() if requires_whitespace_preservation(content))


def whitespace_policy(paths: list[str]) -> bytes:
    return WHITESPACE_POLICY_HEADER + b"".join(
        f"{path} whitespace=-trailing-space\n".encode("utf-8") for path in paths
    )


def write_or_verify_attribute_policy(
    target_root: Path, whitespace_paths: list[str], verify_only: bool
) -> bytes:
    destination = destination_for(target_root, ATTRIBUTES_PATH)
    expected = TARGET_ATTRIBUTES + whitespace_policy(whitespace_paths)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise MaterializationError(f"attribute policy collision is not a regular file: {destination}")
        try:
            actual = destination.read_bytes()
        except OSError as error:
            raise MaterializationError(f"cannot read attribute policy: {destination}: {error}") from error
        if actual == expected:
            return actual
        if not actual.startswith(TARGET_ATTRIBUTES):
            raise MaterializationError(f"attribute policy does not match the SAD-11 preservation policy: {destination}")
        if verify_only:
            raise MaterializationError(f"required SAD-11 attribute policy is missing: {destination}")
        destination.write_bytes(expected)
        return expected
    if verify_only:
        raise MaterializationError(f"required attribute policy is missing: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(expected)
    return expected


def selected_entries(
    manifest_entries: dict[str, dict[str, Any]], sad10_paths: set[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    direct_imports: dict[str, dict[str, Any]] = {}
    historical: dict[str, dict[str, Any]] = {}
    for path, entry in manifest_entries.items():
        disposition = entry.get("disposition")
        if disposition == "import" and path not in sad10_paths:
            direct_imports[path] = entry
        elif disposition == "historical-evidence":
            historical[path] = entry
    if README_PATH not in direct_imports:
        raise MaterializationError("SAD-11 expected the seed README collision")
    return direct_imports, historical


def validate_target_readme(target_root: Path, expected_sha: str) -> bytes:
    readme = target_root / README_PATH
    if not readme.is_file() or readme.is_symlink():
        raise MaterializationError("target canonical README is absent or unsafe")
    data = readme.read_bytes()
    if sha256_bytes(data) != expected_sha.lower():
        raise MaterializationError("target canonical README hash does not match the declared Saddle identity")
    return data


def resolve_evidence_path(target_root: Path, supplied: Path) -> Path:
    evidence_path = supplied if supplied.is_absolute() else target_root / supplied
    evidence_path = evidence_path.resolve()
    if not is_within(evidence_path, target_root):
        raise MaterializationError("evidence output escapes target root")
    return evidence_path


def raw_record(path: str, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "byte_size": entry["byte_size"],
        "disposition": entry["disposition"],
        "git_object": entry["git_object"],
        "mode": entry["mode"],
        "path": path,
        "sha256": entry["sha256"],
    }


def build_evidence(
    manifest_bytes: bytes,
    seed_sha: str,
    direct_imports: dict[str, dict[str, Any]],
    historical: dict[str, dict[str, Any]],
    source_readme: dict[str, Any],
    target_readme: bytes,
    attribute_policy: bytes,
    whitespace_paths: list[str],
) -> bytes:
    imported_records = [
        raw_record(path, entry)
        for path, entry in sorted({**direct_imports, **historical}.items())
        if path != README_PATH
    ]
    sanitized_records = [
        {"path": path, "sha256": sha256_bytes(content)}
        for path, content in sorted(SANITIZED_DOCUMENTS.items())
    ]
    evidence = {
        "canonical_readme_adaptation": {
            "reason": "retains Saddle identity and avoids carrying superseded MAI completion claims",
            "seed_git_object": source_readme["git_object"],
            "seed_sha256": source_readme["sha256"],
            "source_path": README_PATH,
            "target_sha256": sha256_bytes(target_readme),
        },
        "historical_evidence_notice": {
            "path": HISTORICAL_NOTICE_PATH,
            "sha256": sha256_bytes(HISTORICAL_NOTICE),
        },
        "imported_raw_blob_count": len(imported_records),
        "imported_raw_blobs": imported_records,
        "sanitized_saddle_documents": sanitized_records,
        "schema_version": 1,
        "seed": {"sha": seed_sha},
        "source_whitespace_preservation": {
            "affected_path_count": len(whitespace_paths),
            "path": ATTRIBUTES_PATH,
            "policy_sha256": sha256_bytes(attribute_policy),
            "paths": whitespace_paths,
            "reason": "path-scoped rules preserve source-native whitespace in verified SAD-11 raw blobs",
        },
        "source_manifest_sha256": sha256_bytes(manifest_bytes),
        "status": "PASS",
    }
    return (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    args = parse_args()
    seed_repo = args.seed_repo.resolve()
    target_root = args.target_root.resolve()
    if not target_root.is_dir():
        raise MaterializationError(f"target root does not exist: {target_root}")
    verify_seed(seed_repo, args.seed_sha)
    manifest, manifest_bytes = load_manifest(args.source_manifest.resolve(), args.seed_sha)
    manifest_entries = entries_by_path(manifest)
    sad10_paths = load_sad10_paths(args.sad10_evidence.resolve())
    direct_imports, historical = selected_entries(manifest_entries, sad10_paths)
    source_readme = direct_imports.pop(README_PATH)
    blob_bytes(seed_repo, args.seed_sha, source_readme)
    target_readme = validate_target_readme(target_root, args.target_readme_sha256)

    raw_contents: dict[str, bytes] = {}
    for path, entry in sorted({**direct_imports, **historical}.items()):
        content = blob_bytes(seed_repo, args.seed_sha, entry)
        raw_contents[path] = content
        write_or_verify(destination_for(target_root, path), content, args.verify)
    for path, content in SANITIZED_DOCUMENTS.items():
        write_or_verify(destination_for(target_root, path), content, args.verify)
    write_or_verify(destination_for(target_root, HISTORICAL_NOTICE_PATH), HISTORICAL_NOTICE, args.verify)
    whitespace_paths = whitespace_policy_paths(raw_contents)
    attribute_policy = write_or_verify_attribute_policy(target_root, whitespace_paths, args.verify)

    evidence = build_evidence(
        manifest_bytes,
        args.seed_sha,
        direct_imports | {README_PATH: source_readme},
        historical,
        source_readme,
        target_readme,
        attribute_policy,
        whitespace_paths,
    )
    write_or_verify(
        resolve_evidence_path(target_root, args.evidence_output),
        evidence,
        args.verify,
        replace_existing=True,
    )
    print(
        "SAD-11 support-surface materialization: PASS "
        f"({len(direct_imports)} direct imports, {len(historical)} historical records, "
        f"{len(SANITIZED_DOCUMENTS)} sanitized documents)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MaterializationError as error:
        print(f"SAD-11 support-surface materialization failed: {error}", file=sys.stderr)
        raise SystemExit(1)
