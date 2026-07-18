#!/usr/bin/env python3
"""Build and prove Saddle's tracked-only, no-secret import path.

The tool never reads the seed working tree for product files.  It validates the
SAD-02 ledger against immutable Git blobs, builds a deterministic temporary
archive, stages that archive in an isolated temporary Git repository, and runs
two independent scanners before emitting only non-secret metadata as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SEED_SHA = "fedf005a30ad388ab156dc8bd693a3aa3f0702ea"
SCHEMA_VERSION = 1
ALLOWED_DISPOSITIONS = {"import", "extract", "historical-evidence"}
PRIVATE_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
FORBIDDEN_COMPONENTS = {".git", "target", "node_modules", "__pycache__"}


class ProofError(RuntimeError):
    """Raised when the import path cannot prove its security invariant."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-repo", required=True, type=Path)
    parser.add_argument("--seed-sha", default=SEED_SHA)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--allowlist-output", required=True, type=Path)
    parser.add_argument("--evidence-output", required=True, type=Path)
    parser.add_argument("--scratch-root", required=True, type=Path)
    parser.add_argument("--runtime-generator", required=True, type=Path)
    parser.add_argument("--gitleaks", default="gitleaks")
    parser.add_argument("--gitleaks-exceptions", type=Path)
    parser.add_argument("--static-exceptions", type=Path)
    return parser.parse_args(argv)


def fail(message: str) -> None:
    raise ProofError(message)


def run(command: list[str], *, cwd: Path | None = None, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def checked(command: list[str], *, cwd: Path | None = None, input_bytes: bytes | None = None) -> bytes:
    completed = run(command, cwd=cwd, input_bytes=input_bytes)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        stdout_note = (
            f"command emitted {len(completed.stdout)} bytes on stdout; suppressed to avoid disclosing scanned content"
            if completed.stdout
            else ""
        )
        rendered = "\n".join(value for value in (stderr, stdout_note) if value)
        fail(f"command failed ({completed.returncode}): {' '.join(command)}: {rendered}")
    return completed.stdout


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return checked(
        ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args],
        input_bytes=input_bytes,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encoded(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        fail(f"cannot read {label} {path}: {error}")
    except json.JSONDecodeError as error:
        fail(f"{label} is not valid JSON: {error}")
    if not isinstance(payload, dict):
        fail(f"{label} must contain a JSON object")
    return payload


def validate_seed(repo: Path, seed_sha: str) -> None:
    if len(seed_sha) != 40 or any(character not in "0123456789abcdef" for character in seed_sha):
        fail("seed SHA must be a lowercase full 40-character Git SHA")
    if not repo.is_dir():
        fail(f"seed repository is not a directory: {repo}")
    head = git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    if head != seed_sha:
        fail(f"seed checkout is {head}, not required SHA {seed_sha}")
    if git(repo, "status", "--porcelain=v1"):
        fail("seed checkout is dirty; import must use a clean immutable checkout")
    resolved = git(repo, "rev-parse", f"{seed_sha}^{{commit}}").decode("ascii").strip()
    if resolved != seed_sha:
        fail(f"seed SHA did not resolve exactly: {resolved}")


def parse_tree(repo: Path, seed_sha: str) -> dict[str, dict[str, str]]:
    output = git(repo, "ls-tree", "-r", "-z", "--full-tree", seed_sha)
    entries: dict[str, dict[str, str]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        path = raw_path.decode("utf-8", "surrogateescape")
        if path in entries:
            fail(f"duplicate seed tree path: {path}")
        entries[path] = {"git_object": object_id, "git_object_type": object_type, "mode": mode}
    return entries


def blob_contents(repo: Path, object_ids: Iterable[str]) -> dict[str, bytes]:
    unique_ids = list(dict.fromkeys(object_ids))
    if not unique_ids:
        return {}
    request = "".join(f"{object_id}\n" for object_id in unique_ids).encode("ascii")
    output = git(repo, "cat-file", "--batch", input_bytes=request)
    values: dict[str, bytes] = {}
    cursor = 0
    for requested_id in unique_ids:
        header_end = output.find(b"\n", cursor)
        if header_end < 0:
            fail(f"truncated Git blob header for {requested_id}")
        header = output[cursor:header_end].split()
        cursor = header_end + 1
        if len(header) != 3 or header[1] != b"blob":
            fail(f"expected blob for {requested_id}, got {header!r}")
        object_id = header[0].decode("ascii")
        size = int(header[2])
        content = output[cursor : cursor + size]
        if len(content) != size:
            fail(f"truncated Git blob body for {requested_id}")
        cursor += size
        if output[cursor : cursor + 1] != b"\n":
            fail(f"missing Git blob delimiter for {requested_id}")
        cursor += 1
        values[object_id] = content
    if cursor != len(output):
        fail("unexpected trailing data from git cat-file --batch")
    return values


def forbidden_path(path: str) -> str | None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or not path or path.startswith("./"):
        return "path is not a safe relative POSIX path"
    lowered_parts = {part.lower() for part in pure.parts}
    if lowered_parts & FORBIDDEN_COMPONENTS:
        return "contains generated or Git-owned directory material"
    filename = pure.name.lower()
    if filename.startswith(".env") and filename != ".env.example":
        return "is an environment file rather than a verified placeholder"
    if pure.suffix.lower() in PRIVATE_SUFFIXES:
        return "has a private-key-shaped extension"
    if filename in {"id_rsa", "id_ed25519"}:
        return "has a private identity filename"
    if path.startswith("deployment/openbao-staging/bundle-cache/"):
        return "is generated staging bundle-cache material"
    if "/openbao-state/" in f"/{path}" or "/openbao-data/" in f"/{path}":
        return "contains OpenBao runtime state"
    return None


def load_allowed_entries(manifest: dict[str, Any], seed_sha: str) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1:
        fail("source manifest has an unsupported schema version")
    if manifest.get("seed", {}).get("sha") != seed_sha:
        fail("source manifest is not pinned to the requested seed SHA")
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        fail("source manifest has no entries list")
    allowed: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for item in raw_entries:
        if not isinstance(item, dict):
            fail("source manifest contains a non-object entry")
        if item.get("disposition") not in ALLOWED_DISPOSITIONS:
            continue
        try:
            path = str(item["path"])
            object_id = str(item["git_object"])
            object_type = str(item["git_object_type"])
            mode = str(item["mode"])
            digest = str(item["sha256"])
            byte_size = int(item["byte_size"])
        except (KeyError, TypeError, ValueError) as error:
            fail(f"source manifest entry is incomplete: {error}")
        if path in seen_paths:
            fail(f"source manifest has duplicate allowed path: {path}")
        seen_paths.add(path)
        reason = forbidden_path(path)
        if reason:
            fail(f"forbidden allowlist path {path}: {reason}")
        if object_type != "blob" or mode in {"120000", "160000"}:
            fail(f"allowlist path is not a regular tracked blob: {path}")
        allowed.append(
            {
                "byte_size": byte_size,
                "disposition": str(item["disposition"]),
                "git_object": object_id,
                "git_object_type": object_type,
                "mode": mode,
                "path": path,
                "sha256": digest,
            }
        )
    if not allowed:
        fail("source manifest yielded an empty import allowlist")
    return sorted(allowed, key=lambda entry: entry["path"])


def verify_allowed_blobs(
    repo: Path, seed_sha: str, allowed: list[dict[str, Any]]
) -> dict[str, bytes]:
    tree = parse_tree(repo, seed_sha)
    blobs = blob_contents(repo, (entry["git_object"] for entry in allowed))
    for entry in allowed:
        tree_entry = tree.get(entry["path"])
        if tree_entry is None:
            fail(f"allowlist path is absent from source tree: {entry['path']}")
        if tree_entry != {
            "git_object": entry["git_object"],
            "git_object_type": entry["git_object_type"],
            "mode": entry["mode"],
        }:
            fail(f"source tree metadata mismatch for {entry['path']}")
        content = blobs.get(entry["git_object"])
        if content is None:
            fail(f"missing blob body for {entry['path']}")
        if len(content) != entry["byte_size"]:
            fail(f"byte-size mismatch for {entry['path']}")
        if sha256_bytes(content) != entry["sha256"]:
            fail(f"SHA-256 mismatch for {entry['path']}")
    return blobs


def write_archive(archive_path: Path, allowed: list[dict[str, Any]], blobs: dict[str, bytes]) -> None:
    with tarfile.open(archive_path, mode="w") as archive:
        for entry in allowed:
            content = blobs[entry["git_object"]]
            tar_info = tarfile.TarInfo(entry["path"])
            tar_info.gid = 0
            tar_info.uid = 0
            tar_info.gname = ""
            tar_info.uname = ""
            tar_info.mtime = 0
            tar_info.mode = int(entry["mode"], 8) & 0o777
            tar_info.size = len(content)
            archive.addfile(tar_info, io.BytesIO(content))


def extract_archive(archive_path: Path, destination: Path, allowed_paths: set[str]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    destination_root = destination.resolve()
    with tarfile.open(archive_path, mode="r") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        if names != allowed_paths:
            fail("archive contents do not exactly match the verified allowlist")
        for member in members:
            if not member.isfile() or forbidden_path(member.name):
                fail(f"archive contains forbidden member: {member.name}")
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            try:
                target.resolve().relative_to(destination_root)
            except ValueError as error:
                fail(f"archive member escapes destination: {member.name}")
                raise AssertionError from error
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                fail(f"archive member cannot be read: {member.name}")
            target.write_bytes(source.read())
            target.chmod(member.mode)


def stage_simulation(
    root: Path, allowed: list[dict[str, Any]], blobs: dict[str, bytes]
) -> dict[str, Any]:
    allowed_paths = {entry["path"] for entry in allowed}
    expected = {
        entry["path"]: (entry["mode"], entry["git_object"])
        for entry in allowed
    }
    checked(["git", "init", "--quiet", str(root)])
    checked(["git", "-C", str(root), "config", "core.autocrlf", "false"])
    checked(["git", "-C", str(root), "config", "core.eol", "lf"])
    for entry in allowed:
        object_id = checked(
            ["git", "-C", str(root), "hash-object", "-w", "--stdin"],
            input_bytes=blobs[entry["git_object"]],
        ).decode("ascii").strip()
        if object_id != entry["git_object"]:
            fail(f"simulation could not preserve raw source blob for {entry['path']}")
        checked(
            [
                "git",
                "-C",
                str(root),
                "update-index",
                "--add",
                "--cacheinfo",
                f"{entry['mode']},{object_id},{entry['path']}",
            ]
        )
    staged_paths = {
        line.decode("utf-8", "surrogateescape")
        for line in checked(["git", "-C", str(root), "ls-files", "--cached", "-z"]).split(b"\0")
        if line
    }
    if staged_paths != allowed_paths:
        fail("staged simulation differs from the verified allowlist")
    index_rows = checked(["git", "-C", str(root), "ls-files", "--stage", "-z"]).split(b"\0")
    for row in index_rows:
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if mode in {"120000", "160000"}:
            fail("staged simulation contains a symlink or submodule")
        if stage != "0" or expected.get(path) != (mode, object_id):
            fail(f"staged simulation blob does not match verified source object: {path}")
    return {
        "index_matches_verified_blobs": "PASS",
        "path_count": len(staged_paths),
        "tree": checked(["git", "-C", str(root), "write-tree"]).decode("ascii").strip(),
    }


def load_exception_map(path: Path | None, label: str) -> dict[tuple[str, str, int, str], str]:
    if path is None:
        return {}
    payload = read_json(path, label)
    if payload.get("schema_version") != SCHEMA_VERSION:
        fail(f"{label} has an unsupported schema version")
    exceptions: dict[tuple[str, str, int, str], str] = {}
    for item in payload.get("suppressed_findings", []):
        if not isinstance(item, dict):
            fail(f"{label} contains a non-object finding")
        try:
            key = (
                str(item["rule_id"]),
                str(item["path"]),
                int(item["line"]),
                str(item["fingerprint"]),
            )
            reason = str(item["reason"])
        except (KeyError, TypeError, ValueError) as error:
            fail(f"{label} contains an invalid finding: {error}")
        if not reason.strip() or key in exceptions:
            fail(f"{label} contains an invalid or duplicate suppression")
        exceptions[key] = reason
    return exceptions


def gitleaks_fingerprint(rule_id: str, path: str, line: int, matched: str) -> str:
    payload = "\0".join((rule_id, path, str(line), matched)).encode("utf-8", "surrogateescape")
    return sha256_bytes(payload)


def gitleaks_match_metadata(matched: str) -> dict[str, Any]:
    raw = matched.encode("utf-8", "surrogateescape")
    return {
        "matched_is_lowercase_hex": bool(re.fullmatch(r"[0-9a-f]{40,}", matched)),
        "matched_length": len(raw),
        "matched_sha256": sha256_bytes(raw),
    }


def normalize_gitleaks_findings(raw: list[Any], root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    root_resolved = root.resolve()
    for item in raw:
        if not isinstance(item, dict):
            fail("Gitleaks report contains a non-object finding")
        candidate = Path(str(item.get("File", "")))
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            path = candidate.resolve().relative_to(root_resolved).as_posix()
        except ValueError as error:
            fail("Gitleaks reported a path outside the staged simulation")
            raise AssertionError from error
        rule_id = str(item.get("RuleID", ""))
        line = int(item.get("StartLine", 0))
        matched = str(item.get("Match", ""))
        if not rule_id or line < 1 or not matched:
            fail("Gitleaks report has incomplete finding metadata")
        findings.append(
            {
                "fingerprint": gitleaks_fingerprint(rule_id, path, line, matched),
                "line": line,
                **gitleaks_match_metadata(matched),
                "path": path,
                "rule_id": rule_id,
            }
        )
    return sorted(findings, key=lambda item: (item["path"], item["line"], item["rule_id"], item["fingerprint"]))


def classify_findings(
    findings: list[dict[str, Any]], exceptions: dict[tuple[str, str, int, str], str]
) -> tuple[list[dict[str, Any]], int]:
    suppressed = 0
    classified: list[dict[str, Any]] = []
    matched_exception_keys: set[tuple[str, str, int, str]] = set()
    for finding in findings:
        key = (
            finding["rule_id"],
            finding["path"],
            finding["line"],
            finding["fingerprint"],
        )
        copy = dict(finding)
        reason = exceptions.get(key)
        copy["suppressed"] = reason is not None
        if reason is not None:
            copy["suppression_reason"] = reason
            suppressed += 1
            matched_exception_keys.add(key)
        classified.append(copy)
    unused_exceptions = set(exceptions) - matched_exception_keys
    if unused_exceptions:
        fail("exception file contains a stale finding that no longer matches the staged import")
    return classified, suppressed


def validate_detect_secrets_baseline(root: Path) -> dict[str, Any]:
    """Verify that the imported baseline stores detector hashes, not raw secrets."""
    baseline_path = root / ".secrets.baseline"
    payload = read_json(baseline_path, "detect-secrets baseline")
    hashes: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key == "hashed_secret":
                    if not isinstance(nested, str) or not re.fullmatch(r"[0-9a-f]{40}", nested):
                        fail("detect-secrets baseline contains a non-SHA-1 hashed_secret")
                    hashes.append(nested)
                else:
                    walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)
    if not hashes:
        fail("detect-secrets baseline has no hashed_secret records to validate")
    return {
        "hashed_secret_count": len(hashes),
        "path": ".secrets.baseline",
        "sha256": sha256_bytes(baseline_path.read_bytes()),
        "validation": "PASS",
    }


def run_gitleaks(
    binary: str,
    root: Path,
    scratch: Path,
    exceptions: dict[tuple[str, str, int, str], str],
    baseline_validation: dict[str, Any],
) -> dict[str, Any]:
    strict_config = scratch / "strict-gitleaks.toml"
    strict_config.write_text(
        'title = "Saddle strict import scan"\n\n[extend]\nuseDefault = true\n\n'
        '[allowlist]\npaths = [\'\'\'(^|/)\\.secrets\\.baseline$\'\'\']\n',
        encoding="utf-8",
    )
    report = scratch / "strict-gitleaks-report.json"
    completed = run(
        [
            binary,
            "dir",
            "--no-banner",
            "--config",
            str(strict_config),
            "--report-format",
            "json",
            "--report-path",
            str(report),
            str(root),
        ]
    )
    if not report.is_file():
        rendered = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"Gitleaks did not produce a report: {rendered}")
    try:
        raw = json.loads(report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"Gitleaks report is not JSON: {error}")
    if not isinstance(raw, list):
        fail("Gitleaks report must contain a list")
    if completed.returncode not in {0, 1}:
        rendered = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"Gitleaks failed with {completed.returncode}: {rendered}")
    findings, suppressed = classify_findings(normalize_gitleaks_findings(raw, root), exceptions)
    return {
        "baseline_validation": baseline_validation,
        "detector": "gitleaks-strict-default-rules",
        "findings": findings,
        "totals": {
            "raw_finding_count": len(findings),
            "suppressed_finding_count": suppressed,
            "unsuppressed_finding_count": len(findings) - suppressed,
        },
    }


def run_secondary_scanner(
    scanner: Path, root: Path, scratch: Path, exceptions_path: Path | None
) -> dict[str, Any]:
    report = scratch / "secondary-secret-report.json"
    command = [sys.executable, str(scanner), "--root", str(root), "--output", str(report), "--fail-on-findings"]
    if exceptions_path is not None:
        command.extend(("--exceptions", str(exceptions_path)))
    completed = run(command)
    if completed.returncode not in {0, 1} or not report.is_file():
        rendered = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"secondary scanner failed with {completed.returncode}: {rendered}")
    payload = read_json(report, "secondary scanner report")
    if payload.get("schema_version") != SCHEMA_VERSION:
        fail("secondary scanner report has an unsupported schema version")
    return payload


def write_outputs(
    allowlist_output: Path,
    evidence_output: Path,
    allowlist: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    allowlist_output.parent.mkdir(parents=True, exist_ok=True)
    evidence_output.parent.mkdir(parents=True, exist_ok=True)
    allowlist_output.write_bytes(encoded(allowlist))
    evidence_output.write_bytes(encoded(evidence))


def validate_scratch_path_budget(scratch_root: Path, allowed: list[dict[str, Any]]) -> None:
    """Fail before materialization when a Windows simulation would exceed MAX_PATH."""
    if sys.platform != "win32":
        return
    temporary_component = "saddle-sad03-xxxxxxxx"
    longest_path = max(entry["path"] for entry in allowed)
    prospective = scratch_root / temporary_component / "staged-import" / PurePosixPath(longest_path)
    if len(str(prospective)) > 240:
        fail(
            "scratch root is too deep for a Windows staged-import simulation; "
            f"choose a shorter --scratch-root (longest path would be {len(str(prospective))} characters)"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    seed_repo = args.seed_repo.resolve()
    seed_sha = args.seed_sha.lower()
    source_manifest_path = args.source_manifest.resolve()
    validate_seed(seed_repo, seed_sha)
    source_manifest_bytes = source_manifest_path.read_bytes()
    source_manifest = read_json(source_manifest_path, "source manifest")
    allowed = load_allowed_entries(source_manifest, seed_sha)
    blobs = verify_allowed_blobs(seed_repo, seed_sha, allowed)
    generator = args.runtime_generator.resolve()
    if not generator.is_file():
        fail(f"runtime material generator is absent: {generator}")
    scanner = Path(__file__).with_name("saddle_import_secret_scan.py").resolve()
    if not scanner.is_file():
        fail(f"secondary scanner is absent: {scanner}")

    allowlist = {
        "allowed_dispositions": sorted(ALLOWED_DISPOSITIONS),
        "paths": allowed,
        "schema_version": SCHEMA_VERSION,
        "seed": {"sha": seed_sha, "remote_url": git(seed_repo, "remote", "get-url", "origin").decode("utf-8").strip()},
        "source_manifest_sha256": sha256_bytes(source_manifest_bytes),
        "totals": {"path_count": len(allowed), "byte_count": sum(entry["byte_size"] for entry in allowed)},
    }
    gitleaks_exceptions = load_exception_map(args.gitleaks_exceptions, "Gitleaks exceptions")
    scratch_root = args.scratch_root.resolve()
    validate_scratch_path_budget(scratch_root, allowed)
    scratch_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="saddle-sad03-", dir=scratch_root) as temporary:
            scratch = Path(temporary)
            archive_path = scratch / "saddle-tracked-import.tar"
            write_archive(archive_path, allowed, blobs)
            staged_root = scratch / "staged-import"
            allowed_paths = {entry["path"] for entry in allowed}
            extract_archive(archive_path, staged_root, allowed_paths)
            staged = stage_simulation(staged_root, allowed, blobs)
            baseline_validation = validate_detect_secrets_baseline(staged_root)
            gitleaks = run_gitleaks(
                args.gitleaks,
                staged_root,
                scratch,
                gitleaks_exceptions,
                baseline_validation,
            )
            secondary = run_secondary_scanner(scanner, staged_root, scratch, args.static_exceptions)
            evidence = {
                "archive": {
                    "byte_count": archive_path.stat().st_size,
                    "sha256": sha256_bytes(archive_path.read_bytes()),
                    "tracked_path_count": len(allowed),
                },
                "gitleaks": gitleaks,
                "runtime_replacements": {
                    "generator_path": "tools/generate_saddle_ephemeral_test_material.py",
                    "generator_sha256": sha256_bytes(generator.read_bytes()),
                    "generated_at_runtime_only": [
                        "test CA, server, and client certificates and private keys",
                        "OpenBao, Saddle store, Raft, audit, and receipt runtime state directories",
                    ],
                },
                "schema_version": SCHEMA_VERSION,
                "secondary_static_scan": secondary,
                "seed": allowlist["seed"],
                "source_manifest_sha256": allowlist["source_manifest_sha256"],
                "staged_import": staged,
                "status": "PASS"
                if gitleaks["totals"]["unsuppressed_finding_count"] == 0
                and secondary["totals"]["unsuppressed_finding_count"] == 0
                else "FAIL",
            }
    except FileNotFoundError as error:
        fail(f"required executable is unavailable: {error.filename}")

    write_outputs(args.allowlist_output, args.evidence_output, allowlist, evidence)
    gitleaks_open = evidence["gitleaks"]["totals"]["unsuppressed_finding_count"]
    static_open = evidence["secondary_static_scan"]["totals"]["unsuppressed_finding_count"]
    print(
        "SAD-03 staged import simulation: "
        f"{evidence['status']} ({allowlist['totals']['path_count']} paths, "
        f"{gitleaks_open} Gitleaks and {static_open} secondary unsuppressed finding(s))"
    )
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProofError as error:
        print(f"SAD-03 no-secret import proof failed: {error}", file=sys.stderr)
        raise SystemExit(2)
