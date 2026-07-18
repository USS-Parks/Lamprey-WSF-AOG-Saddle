#!/usr/bin/env python3
"""Generate a deterministic, tracked-only Saddle source-coverage manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any


ROOT_PACKAGE_EXACT = {"aogctl", "aogd", "hipaa-pack"}
ROOT_PACKAGE_PREFIXES = ("aog-", "fabric-", "wsf-")

SOURCE_LIKE_SUFFIXES = {
    ".c",
    ".cc",
    ".conf",
    ".css",
    ".dockerfile",
    ".go",
    ".h",
    ".html",
    ".java",
    ".js",
    ".json",
    ".lock",
    ".lua",
    ".md",
    ".mjs",
    ".proto",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SOURCE_LIKE_NAMES = {
    ".dockerignore",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "cargo.lock",
    "cargo.toml",
    "dockerfile",
    "makefile",
    "readme.md",
}

REQUIRED_IMPORT_FILES = {
    ".dockerignore",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".gitleaks.toml",
    ".secrets.baseline",
    "cargo.lock",
    "cargo.toml",
    "conftest.py",
    "deny.toml",
    "dockerfile",
    "license",
    "notice",
    "pyproject.toml",
    "pytest.ini",
    "readme.md",
    "requirements-lock.txt",
    "requirements.txt",
}
REQUIRED_IMPORT_PREFIXES = (
    ".cargo/",
    ".github/",
    ".githooks/",
    ".integrity/",
    "config/",
    "configs/",
    "console/",
    "contracts/",
    "deployment/",
    "scripts/",
    "tests/",
    "tools/burnin_tests/",
    "tools/gpu_release_tests/",
    "tools/packaging_tests/",
    "tools/ship12_tests/",
    "tools/simulator/",
    "tools/smoke/",
    "tools/trace-tools/",
)
HISTORICAL_PREFIXES = ("docs/", "PLANNING/", "test-evidence/")

RELEVANCE_PATTERN = re.compile(
    rb"(?i)(?:\bwsf\b|\baog\b|\bloom\b|\bsaddle\b|fabric-|"
    rb"woven sovereignty|agentic orchestration|orchestrat(?:e|ion)|scheduler)"
)
SENSITIVE_PATH_PATTERN = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\.|$)|[^/]+\.(?:key|pem|p12|pfx)$|id_rsa(?:\.pub)?$|id_ed25519(?:\.pub)?$)"
)

SCHEDULER_EXTRACT_PREFIXES = (
    "mai-scheduler/src/topology/",
)
SCHEDULER_EXTRACT_PATHS = {
    "mai-scheduler/src/power.rs",
    "mai-scheduler/src/scoring/topology_score.rs",
    "mai-scheduler/src/types.rs",
    "mai-scheduler/tests/fixtures/topo_2gpu_nvlink.txt",
    "mai-scheduler/tests/fixtures/topo_4gpu_mixed.txt",
    "mai-scheduler/tests/fixtures/topo_8gpu_dgx.txt",
    "mai-scheduler/tests/fixtures/topo_single_gpu.txt",
    "mai-scheduler/tests/topology_integration.rs",
}

SECRET_BEARING_HISTORICAL_PATHS = {
    "docs/" "compliance/INDEPENDENT-EVIDENCE-DEFERRALS.md": (
        "Historical evidence carries a token-shaped synthetic literal; preserve its "
        "provenance in the ledger but regenerate a sanitized Saddle-owned record."
    ),
    "docs/" "scans/LOCAL-GITDOCTOR-EVIDENCE-2026-05-26.md": (
        "Historical detector output contains finding-shaped material; retain its "
        "provenance hash but do not import raw scan output into the new project."
    ),
    "docs/" "sessions/LAMPREY-SADDLE-HARDENING-DEVLOG.md": (
        "Historical DEVLOG contains a token-shaped fixture; preserve the execution "
        "status through Saddle records without importing the raw fixture literal."
    ),
    "test-evidence/rc-06/bundle-first-boot-stdout.log": (
        "Captured bootstrap stdout includes a raw test credential; regenerate only "
        "with ephemeral Saddle test material."
    ),
    "test-evidence/security-remediation/PSPR-01/00-BEFORE-effective-compose.txt": (
        "Captured compose evidence includes a secret-ID fixture; recreate a sanitized "
        "Saddle evidence view with ephemeral values when needed."
    ),
    "test-evidence/security-remediation/PSPR-01/05-AFTER-compose-config-demo.txt": (
        "Captured compose evidence includes a secret-ID fixture; recreate a sanitized "
        "Saddle evidence view with ephemeral values when needed."
    ),
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        fail(
            f"git {' '.join(args)} failed with {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout


def cargo_metadata(repo: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["cargo", "metadata", "--format-version", "1", "--locked"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        fail(
            "cargo metadata failed with "
            f"{completed.returncode}: {completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return json.loads(completed.stdout)


def relative_manifest_path(repo: Path, manifest_path: str) -> str:
    manifest = Path(manifest_path).resolve()
    try:
        return manifest.parent.relative_to(repo.resolve()).as_posix()
    except ValueError as error:
        fail(f"package manifest escapes seed repository: {manifest_path}")
        raise AssertionError from error


def package_is_root(package: dict[str, Any]) -> bool:
    name = package["name"]
    return name in ROOT_PACKAGE_EXACT or name.startswith(ROOT_PACKAGE_PREFIXES)


def closure_from_metadata(repo: Path) -> tuple[list[dict[str, str]], list[str]]:
    metadata = cargo_metadata(repo)
    packages = metadata["packages"]
    packages_by_id = {package["id"]: package for package in packages}
    nodes_by_id = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    roots = [
        package["id"]
        for package in packages
        if package.get("source") is None and package_is_root(package)
    ]
    if not roots:
        fail("no local WSF/AOG/fabric root packages were found")

    closure: set[str] = set(roots)
    queue: deque[str] = deque(roots)
    while queue:
        package_id = queue.popleft()
        node = nodes_by_id.get(package_id)
        if node is None:
            fail(f"Cargo metadata has no resolve node for {package_id}")
        for dependency in node["deps"]:
            dependency_id = dependency["pkg"]
            package = packages_by_id[dependency_id]
            if package.get("source") is None and dependency_id not in closure:
                closure.add(dependency_id)
                queue.append(dependency_id)

    resolved = [
        {
            "name": packages_by_id[package_id]["name"],
            "path": relative_manifest_path(
                repo, packages_by_id[package_id]["manifest_path"]
            ),
        }
        for package_id in closure
    ]
    return sorted(resolved, key=lambda package: package["name"]), sorted(
        packages_by_id[package_id]["name"] for package_id in roots
    )


def parse_tree(repo: Path, seed_sha: str) -> list[dict[str, str]]:
    payload = git(repo, "ls-tree", "-r", "-z", "--full-tree", seed_sha)
    entries: list[dict[str, str]] = []
    for record in payload.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        entries.append(
            {
                "mode": mode,
                "object_type": object_type,
                "object_id": object_id,
                "path": raw_path.decode("utf-8", "surrogateescape"),
            }
        )
    return sorted(entries, key=lambda entry: entry["path"])


def blob_contents(repo: Path, object_ids: list[str]) -> dict[str, bytes]:
    unique_ids = list(dict.fromkeys(object_ids))
    if not unique_ids:
        return {}
    payload = "".join(f"{object_id}\n" for object_id in unique_ids).encode("ascii")
    output = git(repo, "cat-file", "--batch", input_bytes=payload)
    result: dict[str, bytes] = {}
    cursor = 0
    for requested_id in unique_ids:
        header_end = output.find(b"\n", cursor)
        if header_end < 0:
            fail(f"truncated git cat-file header for {requested_id}")
        header = output[cursor:header_end].split()
        cursor = header_end + 1
        if len(header) != 3 or header[1] != b"blob":
            fail(f"expected blob for {requested_id}, got {header!r}")
        object_id = header[0].decode("ascii")
        size = int(header[2])
        content = output[cursor : cursor + size]
        if len(content) != size:
            fail(f"truncated git cat-file body for {requested_id}")
        cursor += size
        if output[cursor : cursor + 1] != b"\n":
            fail(f"missing git cat-file delimiter for {requested_id}")
        cursor += 1
        result[object_id] = content
    if cursor != len(output):
        fail("unexpected trailing bytes from git cat-file --batch")
    return result


def is_source_like(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    suffix = Path(name).suffix.lower()
    return name in SOURCE_LIKE_NAMES or suffix in SOURCE_LIKE_SUFFIXES


def starts_with_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return path.startswith(prefixes)


def scheduler_disposition(path: str) -> tuple[str, str]:
    if path in SCHEDULER_EXTRACT_PATHS or starts_with_any(
        path, SCHEDULER_EXTRACT_PREFIXES
    ):
        return (
            "extract",
            "GPU topology, hardware locality, power, and characterization input "
            "for Saddle SAD-43; rework under the Saddle grant and snapshot contract.",
        )
    return (
        "exclude-with-reason",
        "Inference request routing, batching, KV-cache, or model-serving behavior "
        "stays in the AOG workload domain rather than the Saddle estate scheduler.",
    )


def is_env_placeholder(path: str) -> bool:
    return path.rsplit("/", 1)[-1].lower() == ".env.example"


def classify(
    path: str,
    closure_paths: set[str],
    relevance_reasons: list[str],
) -> tuple[str, str]:
    if path in SECRET_BEARING_HISTORICAL_PATHS:
        return "exclude-with-reason", SECRET_BEARING_HISTORICAL_PATHS[path]
    if is_env_placeholder(path):
        return (
            "import",
            "Tracked environment placeholder only; it may enter the allowlist only "
            "after SAD-03 proves it contains no live credential or private material.",
        )
    if SENSITIVE_PATH_PATTERN.search(path):
        return (
            "exclude-with-reason",
            "Credential or private-key-shaped path is prohibited from the import; "
            "runtime trust material must be generated ephemerally under SAD-03.",
        )
    if path.startswith("deployment/appliance/fixtures/unsafe-"):
        return (
            "exclude-with-reason",
            "Deliberately unsafe negative deployment fixture; recreate only with "
            "ephemeral generated values under the SAD-03 no-secret test procedure.",
        )
    if path.startswith("deployment/openbao-staging/bundle-cache/"):
        return (
            "exclude-with-reason",
            "Generated staging bundle-cache material is prohibited from import; "
            "regenerate an ephemeral Saddle test bundle under SAD-03 instead.",
        )
    if path.startswith("mai-scheduler/"):
        return scheduler_disposition(path)
    if any(path == package_path or path.startswith(f"{package_path}/") for package_path in closure_paths):
        return (
            "import",
            "Member of the Cargo dependency closure rooted in complete WSF, AOG, "
            "fabric, and orchestration packages.",
        )
    lower_path = path.lower()
    if lower_path in REQUIRED_IMPORT_FILES or starts_with_any(
        path, REQUIRED_IMPORT_PREFIXES
    ):
        return (
            "import",
            "Required root build, contract, integrity, deployment, or policy surface "
            "for the independent repository.",
        )
    if relevance_reasons:
        if starts_with_any(path, HISTORICAL_PREFIXES):
            return (
                "historical-evidence",
                "Relevant executed history, claim evidence, or source inventory preserved "
                "without converting the seed claim into a Saddle completion claim.",
            )
        return (
            "exclude-with-reason",
            "Relevant text outside the independent source closure; retain a provenance "
            "record but do not import unrelated MAI product surface by textual match alone.",
        )
    return (
        "out-of-scope-no-match",
        "No WSF/AOG/Saddle/fabric/orchestration relevance and outside the defined import closure.",
    )


def manifest_for(repo: Path, seed_sha: str, generator: Path) -> dict[str, Any]:
    head = git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    if head != seed_sha:
        fail(f"seed checkout is {head}, not requested immutable SHA {seed_sha}")
    if git(repo, "status", "--porcelain=v1"):
        fail("seed checkout is dirty; use a clean detached or worktree checkout at the pin")
    resolved_sha = git(repo, "rev-parse", f"{seed_sha}^{{commit}}").decode("ascii").strip()
    if resolved_sha != seed_sha:
        fail(f"seed SHA did not resolve exactly: {resolved_sha}")

    closure_packages, root_packages = closure_from_metadata(repo)
    closure_paths = {package["path"] for package in closure_packages}
    tree_entries = parse_tree(repo, seed_sha)
    blobs = blob_contents(
        repo,
        [entry["object_id"] for entry in tree_entries if entry["object_type"] == "blob"],
    )
    entries: list[dict[str, Any]] = []
    for entry in tree_entries:
        path = entry["path"]
        content = blobs.get(entry["object_id"], b"")
        relevance_reasons: list[str] = []
        if any(path == package_path or path.startswith(f"{package_path}/") for package_path in closure_paths):
            relevance_reasons.append("cargo-closure")
        if path.startswith("mai-scheduler/"):
            relevance_reasons.append("mai-scheduler-review")
        if path.lower() in REQUIRED_IMPORT_FILES or starts_with_any(
            path, REQUIRED_IMPORT_PREFIXES
        ):
            relevance_reasons.append("required-import-surface")
        if RELEVANCE_PATTERN.search(path.encode("utf-8", "surrogateescape")):
            relevance_reasons.append("path-pattern")
        if content and RELEVANCE_PATTERN.search(content):
            relevance_reasons.append("content-pattern")
        if SENSITIVE_PATH_PATTERN.search(path):
            relevance_reasons.append("secret-path-review")

        disposition, reason = classify(path, closure_paths, relevance_reasons)
        entries.append(
            {
                "byte_size": len(content) if entry["object_type"] == "blob" else None,
                "disposition": disposition,
                "disposition_reason": reason,
                "git_object": entry["object_id"],
                "git_object_type": entry["object_type"],
                "mode": entry["mode"],
                "path": path,
                "relevance_reasons": relevance_reasons,
                "sha256": hashlib.sha256(content).hexdigest()
                if entry["object_type"] == "blob"
                else None,
                "source_like": is_source_like(path),
            }
        )

    candidate_entries = [entry for entry in entries if entry["relevance_reasons"]]
    undispositioned = [
        entry["path"] for entry in candidate_entries if not entry["disposition"]
    ]
    submodules = [entry["path"] for entry in entries if entry["mode"] == "160000"]
    symlinks = [entry["path"] for entry in entries if entry["mode"] == "120000"]
    return {
        "cargo_dependency_closure": {
            "package_count": len(closure_packages),
            "packages": closure_packages,
            "root_packages": root_packages,
        },
        "entries": entries,
        "generator": {
            "path": "tools/generate_saddle_source_manifest.py",
            "sha256": hashlib.sha256(generator.read_bytes()).hexdigest(),
        },
        "schema_version": 1,
        "seed": {
            "remote_url": git(repo, "remote", "get-url", "origin")
            .decode("utf-8")
            .strip(),
            "sha": seed_sha,
        },
        "totals": {
            "candidate_path_count": len(candidate_entries),
            "disposition_counts": dict(
                sorted(Counter(entry["disposition"] for entry in entries).items())
            ),
            "source_like_path_count": sum(
                1 for entry in entries if entry["source_like"]
            ),
            "submodule_paths": submodules,
            "symlink_paths": symlinks,
            "tracked_path_count": len(entries),
            "undispositioned_matching_paths": undispositioned,
        },
    }


def encoded_manifest(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-repo", required=True, type=Path)
    parser.add_argument("--seed-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="compare a regenerated manifest to --output without writing it",
    )
    args = parser.parse_args()
    seed_sha = args.seed_sha.lower()
    if not re.fullmatch(r"[0-9a-f]{40}", seed_sha):
        fail("--seed-sha must be one full 40-character lowercase Git SHA")
    repo = args.seed_repo.resolve()
    if not repo.is_dir():
        fail(f"seed repository is not a directory: {repo}")

    manifest = manifest_for(repo, seed_sha, Path(__file__).resolve())
    output = encoded_manifest(manifest)
    if args.verify:
        if not args.output.is_file():
            fail(f"manifest does not exist for verification: {args.output}")
        if args.output.read_bytes() != output:
            fail("manifest differs from deterministic regeneration")
        print(
            "SAD-02 manifest verification: PASS "
            f"({manifest['totals']['tracked_path_count']} tracked paths, "
            f"{manifest['totals']['candidate_path_count']} candidates)"
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print(
        "SAD-02 manifest generated: "
        f"{manifest['totals']['tracked_path_count']} tracked paths, "
        f"{manifest['totals']['candidate_path_count']} candidates, "
        f"{manifest['cargo_dependency_closure']['package_count']} closure packages"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"SAD-02 manifest generation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
