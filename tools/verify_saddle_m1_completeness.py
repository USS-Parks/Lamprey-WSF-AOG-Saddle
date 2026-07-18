#!/usr/bin/env python3
"""Verify the final M1 Saddle source surface against approved provenance.

The immutable SAD-02 manifest describes the pinned seed.  This verifier proves
the final independent tree is complete while accounting for the small set of
approved later transformations: the narrowed workspace manifest, the
independent lockfile, identity-only metadata changes, the canonical README,
and the ephemeral negative-profile test rewrite.  It also records the ten
seed paths deliberately kept out of Saddle because they are stale staging
state or historical captures rather than portable, non-secret source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


TRANSFORMED_PATHS = {
    "Cargo.lock": {
        "source_sha256": "a9fc8be80efb729495018ce36851aea2e11cfa9e211625d5cd0b87619039b70c",
        "target_sha256": "39ffb3dce2112c287be0f7d7d2f020d1d6a3d10c3d3eddf231c548c767d48701",
        "reason": "SAD-12 offline regeneration for the independent 37-package closure.",
    },
    "Cargo.toml": {
        "source_sha256": "98b7061cb2778dddeda10f43ebeff67e28d3d23440310b6b40ae889c5006556e",
        "target_sha256": "c1b264839615aca7ef66ebb95e15d2ab62b84c154c44729e93ff41f532b596d7",
        "reason": "SAD-10 closure narrowing plus SAD-12 independent repository identity.",
    },
    "README.md": {
        "source_sha256": "61fca36cfcb678b9b7f88b8fa55272f843776158bd9e77dc161245881f09730d",
        "target_sha256": "0dedfce5d927f507fd532c7e63155d14bcdb0af9d4020c06192f446b8c6e46ed",
        "reason": "Saddle canonical README retained and parent-coupling guidance removed.",
    },
    "deployment/appliance/tests/test_validate_profile.py": {
        "source_sha256": "d8c1c9ee4b539d73977b102de33814f81fba4499b06c4902bc2f52d5b02bb1ef",
        "target_sha256": "7abd28ba37b9ac5a0e5644a49aa9974f77594416c5decdeb1ba5e11bf27a1a9d",
        "reason": "SAD-14 recreates excluded unsafe profiles in memory with ephemeral values.",
    },
    "deployment/supply-chain/sign.sh": {
        "source_sha256": "41e71eeb6f539cd2e0f79fd8bf30ddc58ee3193944ca42be2b07749503c1334b",
        "target_sha256": "92ee4bd54324c6da7edef6cb4d9b1fa11b9d8a73240625f10daaa795c7ce2e86",
        "reason": "SAD-12 keyless signing identity points to Saddle's independent repository.",
    },
}

EXCLUDED_SOURCE_PATHS = {
    "deployment/openbao-staging/anchors/bundle-signer-staging.pub": {
        "source_sha256": "25c1d9bd10b0563a7db3dde72f4f1542fc1c300fe3ccb7abfb0575e4e8e30363",
        "reason": "Seed-specific static staging anchor; fresh trust material is generated at runtime.",
    },
    "deployment/openbao-staging/auth_keys.toml": {
        "source_sha256": "93c728a86a02b9c61fb003f7efebb4db6976c423fe8602f8bbcd07380e58b436",
        "reason": "Seed staging key-hash configuration is not portable Saddle runtime source.",
    },
    "deployment/openbao-staging/ir-respond.ps1": {
        "source_sha256": "57cea2d1ff96e956ae1bedb06c860ad3b301a89cf88a33542fc62bf8d8949e74",
        "reason": "Legacy staging automation is not an independent Saddle deployment interface.",
    },
    "deployment/openbao-staging/openbao-connection.toml": {
        "source_sha256": "f5f6ff40415dc3d6b38ae89b90e1ca84d9eb6ab0dc03e4f4ce5f48da177b651a",
        "reason": "Seed-specific static AppRole configuration is replaced by ephemeral runtime material.",
    },
    "deployment/openbao-staging/profile-production.toml": {
        "source_sha256": "f5f119f5c63928d6e437148a6a53e1f6cbc8c6ffe44aa0fab96bafbc40b4ac1f",
        "reason": "Legacy MAI staging profile is outside Saddle's declared deployment surface.",
    },
    "deployment/openbao-staging/profile.toml": {
        "source_sha256": "e94d2dbc98b58708d2dae50214389547f74642aaf198231e615fddeb3d8acf99",
        "reason": "Legacy MAI staging profile is outside Saddle's declared deployment surface.",
    },
    "deployment/openbao-staging/start-openbao.ps1": {
        "source_sha256": "44fe15d05c5170264ec18d0e4219d0368a2eec64ec918c1be140ab0dc32980c9",
        "reason": "Legacy staging bootstrap is replaced by the disposable Saddle material generator.",
    },
    "deployment/openbao-staging/trust-anchors.toml": {
        "source_sha256": "de55e18a901c1b8a41b7074c8998b81c07c3199e035e24dd2b33fee5e4859c6b",
        "reason": "Seed-specific static trust anchors must not become Saddle runtime authority.",
    },
    "test-evidence/rc-05/cargo-test-workspace.log": {
        "source_sha256": "28efafd740e12ec0736d3515734ba42ceb55ed4c38e3dd9b33dfaa87c0e0f70b",
        "reason": "Historical capture contains parent-local build-path provenance; Saddle records fresh evidence instead.",
    },
    "test-evidence/rc-05/python-sdk-tests.log": {
        "source_sha256": "d87b1d27595aa8b65bb39ce048a8fa8e4e0766c5015b5dfb06a56aec40b86ef8",
        "reason": "Historical capture contains parent-local environment provenance; Saddle records fresh evidence instead.",
    },
}

STAGING_BOUNDARY = "deployment/openbao-staging/README.md"
EXPECTED_SELECTED_SOURCE_PATH_COUNT = 885
EXPECTED_SAD14_PATH_COUNT = 20


class CompletenessError(RuntimeError):
    """Raised when the current source tree differs from approved M1 provenance."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise CompletenessError(f"unsafe relative path: {relative}")
    path = (root / Path(*pure.parts)).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise CompletenessError(f"path escapes target root: {relative}") from error
    return path


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise CompletenessError(f"cannot read JSON evidence {path}: {error}") from error
    if not isinstance(value, dict):
        raise CompletenessError(f"JSON evidence is not an object: {path}")
    return value, raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-root", default=Path("."), type=Path)
    parser.add_argument(
        "--source-manifest",
        default=Path("test-evidence/saddle/SAD-02/source-manifest.json"),
        type=Path,
    )
    parser.add_argument(
        "--sad14-evidence",
        default=Path("test-evidence/saddle/SAD-14/packaging-surface-import-proof.json"),
        type=Path,
    )
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def write_or_verify(path: Path, expected: bytes, verify_only: bool) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise CompletenessError(f"evidence destination is not a regular file: {path}")
        if path.read_bytes() != expected:
            if verify_only:
                raise CompletenessError("existing evidence does not match M1 completeness output")
            path.write_bytes(expected)
        return
    if verify_only:
        raise CompletenessError("M1 completeness evidence is missing")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)


def main() -> int:
    args = parse_args()
    root = args.target_root.resolve()
    if not root.is_dir():
        raise CompletenessError(f"target root does not exist: {root}")
    manifest_path = args.source_manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    manifest, manifest_bytes = read_json(manifest_path.resolve())
    if manifest.get("schema_version") != 1:
        raise CompletenessError("unsupported source manifest schema")
    selected = [
        entry
        for entry in manifest.get("entries", [])
        if entry.get("disposition") in {"import", "historical-evidence"}
    ]
    if len(selected) != EXPECTED_SELECTED_SOURCE_PATH_COUNT:
        raise CompletenessError(f"unexpected selected source path count: {len(selected)}")
    selected_by_path = {entry.get("path"): entry for entry in selected}
    if len(selected_by_path) != len(selected) or None in selected_by_path:
        raise CompletenessError("selected source manifest paths are invalid")
    policy_paths = set(TRANSFORMED_PATHS) | set(EXCLUDED_SOURCE_PATHS)
    if not policy_paths.issubset(selected_by_path):
        raise CompletenessError("M1 provenance policy references a path outside SAD-02 selection")

    raw_matches: list[dict[str, str]] = []
    transforms: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    for path, entry in sorted(selected_by_path.items()):
        source_sha = entry.get("sha256")
        if not isinstance(source_sha, str):
            raise CompletenessError(f"source hash missing for {path}")
        destination = checked_path(root, path)
        if path in EXCLUDED_SOURCE_PATHS:
            policy = EXCLUDED_SOURCE_PATHS[path]
            if source_sha != policy["source_sha256"]:
                raise CompletenessError(f"source hash policy mismatch for excluded {path}")
            if destination.exists() or destination.is_symlink():
                raise CompletenessError(f"excluded seed path is present in Saddle: {path}")
            exclusions.append({"path": path, "reason": policy["reason"], "source_sha256": source_sha})
            continue
        if destination.is_symlink() or not destination.is_file():
            raise CompletenessError(f"selected source path is missing: {path}")
        actual_sha = sha256(destination)
        if path in TRANSFORMED_PATHS:
            policy = TRANSFORMED_PATHS[path]
            if source_sha != policy["source_sha256"] or actual_sha != policy["target_sha256"]:
                raise CompletenessError(f"approved transformation hash mismatch for {path}")
            transforms.append(
                {
                    "path": path,
                    "reason": policy["reason"],
                    "source_sha256": source_sha,
                    "target_sha256": actual_sha,
                }
            )
            continue
        if actual_sha != source_sha:
            raise CompletenessError(f"unapproved source hash divergence for {path}")
        raw_matches.append({"path": path, "sha256": actual_sha})

    boundary = checked_path(root, STAGING_BOUNDARY)
    if boundary.is_symlink() or not boundary.is_file():
        raise CompletenessError("missing OpenBao staging boundary record")

    sad14_path = args.sad14_evidence
    if not sad14_path.is_absolute():
        sad14_path = root / sad14_path
    sad14, sad14_bytes = read_json(sad14_path.resolve())
    if sad14.get("status") != "PASS":
        raise CompletenessError("SAD-14 packaging evidence is not PASS")
    if sad14.get("source_manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest():
        raise CompletenessError("SAD-14 packaging proof does not bind this source manifest")
    package_records = sad14.get("target_paths")
    if not isinstance(package_records, list) or len(package_records) != EXPECTED_SAD14_PATH_COUNT:
        raise CompletenessError("unexpected SAD-14 packaging proof path count")
    packaging: list[dict[str, str]] = []
    for record in package_records:
        path = record.get("path")
        expected_sha = record.get("target_sha256")
        if not isinstance(path, str) or not isinstance(expected_sha, str):
            raise CompletenessError("invalid SAD-14 packaging proof record")
        destination = checked_path(root, path)
        if destination.is_symlink() or not destination.is_file() or sha256(destination) != expected_sha:
            raise CompletenessError(f"SAD-14 packaging provenance mismatch for {path}")
        packaging.append({"path": path, "sha256": expected_sha})

    evidence = {
        "m1_policy": {
            "approved_exclusion_count": len(exclusions),
            "approved_transformation_count": len(transforms),
            "raw_source_match_count": len(raw_matches),
            "selected_source_path_count": len(selected),
        },
        "openbao_staging_boundary": {"path": STAGING_BOUNDARY, "sha256": sha256(boundary)},
        "package_addendum": {"path_count": len(packaging), "proof_sha256": hashlib.sha256(sad14_bytes).hexdigest()},
        "schema_version": 1,
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_reconciliation": {
            "approved_exclusions": exclusions,
            "approved_transformations": transforms,
        },
        "status": "PASS",
    }
    output = args.evidence_output
    if not output.is_absolute():
        output = root / output
    output = checked_path(root, output.relative_to(root) if output.is_absolute() else output)
    rendered = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_or_verify(output, rendered, args.verify)
    print(
        "SAD-15 M1 completeness: PASS "
        f"({len(selected)} selected, {len(raw_matches)} raw, {len(transforms)} transformed, "
        f"{len(exclusions)} excluded, {len(packaging)} package-addendum paths)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompletenessError as error:
        print(f"SAD-15 M1 completeness failed: {error}")
        raise SystemExit(2)
