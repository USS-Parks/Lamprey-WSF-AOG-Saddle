#!/usr/bin/env python3
"""Prove and reproduce the sanitized Mighty Eel archival object graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

SCHEMA = "saddle-history-archive-safety/v1"
OBJECT_MAP_SCHEMA = "saddle-history-object-map/v1"
EXPECTED_GITLEAKS_VERSION = "8.30.1"
EXPECTED_TRUFFLEHOG_VERSION = "3.95.9"
SOURCE_URL = "https://github.com/USS-Parks/Mighty-Eel-OS.git"
REDACTED_SOURCE_BLOB = "ffb2ea027f2a965cdad277c1ebbde291d3314a36"
REDACTED_SOURCE_COMMIT = "c75e95f15256b929e382ec58658348502e6a5f83"
WRAPPED_TOKEN_LINE = re.compile(
    rb"(?m)^# secret_id delivered via response-wrapped token: s\.[A-Za-z0-9]+\r?$"
)
WRAPPED_TOKEN_VALUE = re.compile(rb"s\.[A-Za-z0-9]+")
REDACTED_TOKEN_LINE = (
    b"# secret_id removed by SAD-HIST-02; inject a wrapped token at runtime"
)
SHA_PATTERN = re.compile(r"(?<![0-9a-f])([0-9a-f]{40})(?![0-9a-f])")


class ArchiveSafetyError(RuntimeError):
    """Raised when the archive-safety proof cannot be established exactly."""


def fail(message: str) -> NoReturn:
    raise ArchiveSafetyError(message)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    allowed: set[int] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    accepted = {0} if allowed is None else allowed
    if completed.returncode not in accepted:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"{' '.join(command)} failed with {completed.returncode}: {stderr}")
    return completed


def git_command(repo: Path, *args: str) -> list[str]:
    return [
        "git",
        "-c",
        f"safe.directory={repo.resolve()}",
        "-c",
        "core.longpaths=true",
        "-c",
        "core.quotePath=false",
        "-C",
        str(repo.resolve()),
        *args,
    ]


def git(
    repo: Path,
    *args: str,
    input_bytes: bytes | None = None,
    allowed: set[int] | None = None,
) -> bytes:
    return run(
        git_command(repo, *args), input_bytes=input_bytes, allowed=allowed
    ).stdout


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {label} {path}: {error}")


def read_object(repo: Path, object_type: str, object_id: str) -> bytes:
    return git(repo, "cat-file", object_type, object_id)


def batch_read_objects(repo: Path, object_ids: list[str]) -> dict[str, bytes]:
    ordered = sorted(set(object_ids))
    output = git(
        repo,
        "cat-file",
        "--batch",
        input_bytes=("\n".join(ordered) + "\n").encode("ascii"),
    )
    records: dict[str, bytes] = {}
    cursor = 0
    for expected_id in ordered:
        header_end = output.find(b"\n", cursor)
        if header_end < 0:
            fail("truncated cat-file batch header")
        header = output[cursor:header_end].decode("ascii").split()
        if len(header) != 3 or header[0] != expected_id:
            fail(f"unexpected cat-file batch record for {expected_id}")
        size = int(header[2])
        object_start = header_end + 1
        object_end = object_start + size
        if object_end >= len(output) or output[object_end : object_end + 1] != b"\n":
            fail(f"truncated cat-file batch object for {expected_id}")
        records[expected_id] = output[object_start:object_end]
        cursor = object_end + 1
    if cursor != len(output):
        fail("cat-file batch returned trailing data")
    return records


def write_object(repo: Path, object_type: str, payload: bytes) -> str:
    return git(
        repo,
        "hash-object",
        "-w",
        "-t",
        object_type,
        "--stdin",
        input_bytes=payload,
    ).decode("ascii").strip()


def inventory_context(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = read_json(path, "SAD-HIST-01 inventory")
    if payload.get("schema_version") != "saddle-published-history-inventory/v1":
        fail("unsupported SAD-HIST-01 inventory schema")
    refs = payload.get("published_refs")
    commits = payload.get("commits")
    if not isinstance(refs, list) or not isinstance(commits, list):
        fail("SAD-HIST-01 inventory is missing refs or commits")
    if payload.get("summary", {}).get("tag_count") != 0:
        fail("annotated tag rewriting is not authorized by the frozen inventory")
    return payload, refs


def candidate_tips(refs: list[dict[str, Any]]) -> list[str]:
    tips = sorted({str(record["commit_sha"]) for record in refs})
    if not tips:
        fail("candidate ref set has no commit tips")
    return tips


def rev_list(repo: Path, tips: list[str], *extra: str) -> list[str]:
    return git(repo, "rev-list", *extra, *tips).decode("ascii").splitlines()


def object_inventory(
    repo: Path, tips: list[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
    lines = git(repo, "rev-list", "--objects", *tips).decode(
        "utf-8", "surrogateescape"
    ).splitlines()
    paths: dict[str, str] = {}
    object_ids: list[str] = []
    for line in lines:
        object_id, separator, path = line.partition(" ")
        object_ids.append(object_id)
        if separator and object_id not in paths:
            paths[object_id] = path
    unique_ids = sorted(set(object_ids))
    batch_input = ("\n".join(unique_ids) + "\n").encode("ascii")
    metadata = git(
        repo,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        input_bytes=batch_input,
    ).decode("ascii")
    types: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for line in metadata.splitlines():
        object_id, object_type, raw_size = line.split()
        if object_type == "missing":
            fail(f"candidate object is missing: {object_id}")
        types[object_id] = object_type
        sizes[object_id] = int(raw_size)
    if set(types) != set(unique_ids):
        fail("object metadata did not exactly cover the candidate closure")
    return types, paths, sizes


def parse_tree(payload: bytes) -> list[tuple[bytes, bytes, str]]:
    entries: list[tuple[bytes, bytes, str]] = []
    cursor = 0
    while cursor < len(payload):
        space = payload.find(b" ", cursor)
        nul = payload.find(b"\0", space + 1)
        if space < 0 or nul < 0 or nul + 21 > len(payload):
            fail("malformed tree object")
        mode = payload[cursor:space]
        name = payload[space + 1 : nul]
        object_id = payload[nul + 1 : nul + 21].hex()
        entries.append((mode, name, object_id))
        cursor = nul + 21
    return entries


def render_tree(entries: list[tuple[bytes, bytes, str]]) -> bytes:
    return b"".join(
        mode + b" " + name + b"\0" + bytes.fromhex(object_id)
        for mode, name, object_id in entries
    )


def commit_fields(payload: bytes) -> tuple[list[list[bytes]], bytes]:
    try:
        header, message = payload.split(b"\n\n", 1)
    except ValueError:
        fail("commit object has no header separator")
    blocks: list[list[bytes]] = []
    for line in header.splitlines():
        if line.startswith(b" "):
            if not blocks:
                fail("commit header begins with a continuation line")
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return blocks, message


def field_name(block: list[bytes]) -> bytes:
    return block[0].split(b" ", 1)[0]


def field_value(block: list[bytes]) -> bytes:
    try:
        return block[0].split(b" ", 1)[1]
    except IndexError:
        fail("malformed commit header field")


def commit_message(payload: bytes) -> bytes:
    return commit_fields(payload)[1]


def rewrite_history(
    *,
    source_repo: Path,
    archive_repo: Path,
    refs: list[dict[str, Any]],
    original_types: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    git(archive_repo.parent, "init", "--bare", str(archive_repo))
    alternates = archive_repo / "objects" / "info" / "alternates"
    alternates.parent.mkdir(parents=True, exist_ok=True)
    source_objects = git(source_repo, "rev-parse", "--git-path", "objects").decode().strip()
    source_objects_path = Path(source_objects)
    if not source_objects_path.is_absolute():
        source_objects_path = source_repo / source_objects_path
    alternates.write_bytes(source_objects_path.resolve().as_posix().encode("utf-8") + b"\n")

    mapping: dict[str, dict[str, Any]] = {}
    source_payloads = batch_read_objects(source_repo, list(original_types))

    def map_blob(object_id: str) -> str:
        existing = mapping.get(object_id)
        if existing is not None:
            return str(existing["new_sha"])
        payload = source_payloads[object_id]
        changed = object_id == REDACTED_SOURCE_BLOB
        if changed:
            rewritten, count = WRAPPED_TOKEN_LINE.subn(REDACTED_TOKEN_LINE, payload)
            if count != 1:
                fail("the reviewed secret blob no longer has exactly one wrapped-token line")
            new_id = write_object(archive_repo, "blob", rewritten)
            reason = "wrapped-token-redaction"
        else:
            new_id = object_id
            reason = "unchanged"
        mapping[object_id] = {
            "changed": changed,
            "new_sha": new_id,
            "object_type": "blob",
            "old_sha": object_id,
            "reason": reason,
        }
        return new_id

    def map_tree(object_id: str) -> str:
        existing = mapping.get(object_id)
        if existing is not None:
            return str(existing["new_sha"])
        payload = source_payloads[object_id]
        entries = parse_tree(payload)
        rewritten_entries: list[tuple[bytes, bytes, str]] = []
        changed = False
        for mode, name, child_id in entries:
            if mode in {b"40000", b"040000"}:
                new_child = map_tree(child_id)
            elif mode == b"160000":
                new_child = child_id
            else:
                new_child = map_blob(child_id)
            rewritten_entries.append((mode, name, new_child))
            changed = changed or new_child != child_id
        new_id = (
            write_object(archive_repo, "tree", render_tree(rewritten_entries))
            if changed
            else object_id
        )
        mapping[object_id] = {
            "changed": changed,
            "new_sha": new_id,
            "object_type": "tree",
            "old_sha": object_id,
            "reason": "descendant-object-rewrite" if changed else "unchanged",
        }
        return new_id

    tips = candidate_tips(refs)
    ordered_commits = rev_list(source_repo, tips, "--reverse", "--topo-order")
    for object_id in ordered_commits:
        payload = source_payloads[object_id]
        blocks, message = commit_fields(payload)
        message_changed = object_id == REDACTED_SOURCE_COMMIT
        if message_changed:
            message, count = WRAPPED_TOKEN_VALUE.subn(b"<redacted-wrapped-token>", message)
            if count != 1:
                fail("the reviewed secret commit no longer has exactly one wrapped token")
        tree_id = field_value(next(block for block in blocks if field_name(block) == b"tree")).decode()
        new_tree = map_tree(tree_id)
        new_blocks: list[list[bytes]] = []
        changed = new_tree != tree_id or message_changed
        signature_stripped = False
        for block in blocks:
            name = field_name(block)
            if name == b"tree":
                new_blocks.append([b"tree " + new_tree.encode("ascii")])
            elif name == b"parent":
                old_parent = field_value(block).decode("ascii")
                parent_record = mapping.get(old_parent)
                if parent_record is None:
                    fail(f"parent was not rewritten before child: {old_parent}")
                new_parent = str(parent_record["new_sha"])
                changed = changed or new_parent != old_parent
                new_blocks.append([b"parent " + new_parent.encode("ascii")])
            else:
                new_blocks.append(block)
        if changed:
            kept_blocks: list[list[bytes]] = []
            for block in new_blocks:
                name = field_name(block)
                if name in {b"gpgsig", b"gpgsig-sha256"}:
                    signature_stripped = True
                    continue
                if name == b"mergetag":
                    fail("changed commit contains an unsupported mergetag")
                kept_blocks.append(block)
            rewritten = (
                b"\n".join(line for block in kept_blocks for line in block)
                + b"\n\n"
                + message
            )
            new_id = write_object(archive_repo, "commit", rewritten)
        else:
            new_id = object_id
        mapping[object_id] = {
            "changed": changed,
            "new_sha": new_id,
            "object_type": "commit",
            "old_sha": object_id,
            "reason": (
                "commit-message-redaction"
                if message_changed
                else "tree-or-parent-rewrite" if changed else "unchanged"
            ),
            "signature_stripped": signature_stripped,
        }

    if set(mapping) != set(original_types):
        missing = sorted(set(original_types) - set(mapping))
        extra = sorted(set(mapping) - set(original_types))
        fail(f"object map does not cover closure exactly: missing={missing[:3]} extra={extra[:3]}")

    ref_map: list[dict[str, Any]] = []
    sanitized_tips: list[str] = []
    for record in sorted(refs, key=lambda item: str(item["ref"])):
        source_ref = str(record["ref"])
        old_tip = str(record["commit_sha"])
        new_tip = str(mapping[old_tip]["new_sha"])
        if not source_ref.startswith("refs/heads/"):
            fail(f"unexpected frozen ref type: {source_ref}")
        archive_ref = "refs/heads/history/mighty-eel/" + source_ref.removeprefix(
            "refs/heads/"
        )
        git(archive_repo, "update-ref", archive_ref, new_tip)
        ref_map.append(
            {
                "archive_ref": archive_ref,
                "changed": old_tip != new_tip,
                "original_commit_sha": old_tip,
                "original_object_sha": str(record["object_sha"]),
                "source_ref": source_ref,
                "sanitized_commit_sha": new_tip,
            }
        )
        sanitized_tips.append(new_tip)

    git(archive_repo, "repack", "-a", "-d")
    alternates.unlink()
    git(archive_repo, "fsck", "--full", "--no-dangling")
    missing_secret = run(
        git_command(archive_repo, "cat-file", "-e", REDACTED_SOURCE_BLOB), allowed={0, 1}
    )
    if missing_secret.returncode == 0:
        fail("sanitized archive still contains the original secret-bearing blob")
    sanitized_commits = set(rev_list(archive_repo, sorted(set(sanitized_tips))))
    if len(sanitized_commits) != len(ordered_commits):
        fail("sanitized archive commit count changed")
    return mapping, ref_map, sorted(set(sanitized_tips))


def path_suffix(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix) else ".blob"


def materialize_scan_input(
    *,
    repo: Path,
    tips: list[str],
    root: Path,
    paths: dict[str, str],
) -> dict[str, Any]:
    types, discovered_paths, _sizes = object_inventory(repo, tips)
    payloads = batch_read_objects(repo, list(types))
    root.mkdir(parents=True, exist_ok=False)
    blob_count = 0
    message_count = 0
    byte_count = 0
    tip_blobs: set[str] = set()
    for tip in tips:
        tree_lines = git(repo, "ls-tree", "-r", "-z", tip).split(b"\0")
        for line in tree_lines:
            if not line:
                continue
            metadata, _separator, _name = line.partition(b"\t")
            _mode, object_type, object_id = metadata.decode("ascii").split()
            if object_type == "blob":
                tip_blobs.add(object_id)
    all_blobs = {object_id for object_id, kind in types.items() if kind == "blob"}
    for object_id in sorted(all_blobs):
        original_path = paths.get(object_id) or discovered_paths.get(object_id, "")
        destination = root / f"blob-{object_id}{path_suffix(original_path)}"
        payload = payloads[object_id]
        destination.write_bytes(payload)
        blob_count += 1
        byte_count += len(payload)
    commits = sorted(object_id for object_id, kind in types.items() if kind == "commit")
    for object_id in commits:
        destination = root / f"message-{object_id}.txt"
        payload = commit_message(payloads[object_id])
        destination.write_bytes(payload)
        message_count += 1
        byte_count += len(payload)
    return {
        "blob_count": blob_count,
        "commit_message_count": message_count,
        "deleted_blob_count": len(all_blobs - tip_blobs),
        "input_byte_count": byte_count,
        "input_file_count": blob_count + message_count,
        "object_type_counts": dict(sorted(Counter(types.values()).items())),
    }


def scanner_version(binary: Path, engine: str) -> str:
    output = run([str(binary), "--version"]).stdout.decode("utf-8", "replace").strip()
    match = re.search(r"\d+\.\d+\.\d+", output)
    if match is None:
        fail(f"cannot parse {engine} version: {output}")
    return match.group(0)


def object_from_scanner_path(value: str) -> tuple[str, str]:
    match = SHA_PATTERN.search(value.replace("\\", "/"))
    if match is None:
        fail(f"scanner finding path has no object SHA: {value}")
    object_id = match.group(1)
    kind = "commit-message" if Path(value).name.startswith("message-") else "blob"
    return object_id, kind


def gitleaks_classification(
    *, phase: str, rule: str, object_id: str, historical_path: str
) -> tuple[str, str]:
    if phase == "original" and object_id in {
        REDACTED_SOURCE_BLOB,
        REDACTED_SOURCE_COMMIT,
    }:
        return "confirmed-secret", "historical-wrapped-token"
    normalized = historical_path.replace("\\", "/")
    if rule == "generic-api-key" and normalized == ".secrets.baseline":
        return "reviewed-non-secret", "detect-secrets-hash"
    if normalized == ".gitleaks.toml" and rule in {
        "aws-access-token",
        "generic-api-key",
        "vault-service-token",
    }:
        return "reviewed-non-secret", "scanner-policy-test-fixture"
    if rule == "generic-api-key" and re.fullmatch(
        r"docs/(?:scans/)?LOCAL-GITDOCTOR-(?:EVIDENCE|REPORT)(?:-[0-9-]+)?\.(?:md|json)",
        normalized,
    ):
        return "reviewed-non-secret", "scanner-hash-evidence"
    docs_root = "docs"
    reviewed: set[tuple[str, str]] = {
        ("aws-access-token", "crates/aog-toolproxy/src/scan.rs"),
        ("generic-api-key", "mai-api/src/auth.rs"),
        ("generic-api-key", "mai-api/src/metrics.rs"),
        ("generic-api-key", "crates/aogd/tests/live_openbao_anchor.rs"),
        ("generic-api-key", "crates/wsf-broker/src/gcp.rs"),
        ("generic-api-key", "crates/fabric-contracts/tests/contracts.rs"),
        ("generic-api-key", "contracts/trust-token.md"),
        ("generic-api-key", "contracts/receipt.md"),
        ("generic-api-key", f"{docs_root}/THREE-LAYER-MANIFOLD-PLAN.md"),
        ("generic-api-key", f"{docs_root}/sessions/THREE-LAYER-MANIFOLD-PLAN.md"),
        (
            "generic-api-key",
            f"{docs_root}/sessions/LAMPREY-SADDLE-HARDENING-DEVLOG.md",
        ),
        ("generic-api-key", "test-evidence/rc-06/bundle-first-boot-stdout.log"),
    }
    if (rule, normalized) in reviewed:
        return "reviewed-non-secret", "documented-test-or-contract-fixture"
    fail(f"unreviewed Gitleaks finding: phase={phase} rule={rule} path={normalized}")


def trufflehog_classification(
    *,
    detector: str,
    raw: str,
    historical_path: str,
    source_kind: str,
    object_id: str,
) -> tuple[str, str]:
    normalized = historical_path.replace("\\", "/")
    if detector == "Lob" and raw.startswith("test_"):
        return "reviewed-non-secret", "vendor-defined-lob-test-key"
    google_paths = {
        "crates/wsf-broker/src/gcp.rs",
        "crates/wsf-broker/tests/live_gcp.rs",
    }
    if detector == "GoogleOauth2" and raw.startswith("ya29."):
        if normalized in google_paths or (
            source_kind == "commit-message"
            and re.fullmatch(r"ya29\.[A-Za-z0-9_-]*material", raw) is not None
        ):
            return "reviewed-non-secret", "documented-placeholder-gcp-bearer"
    uri_paths = {
        "crates/aog-wire/src/lib.rs",
        "crates/aog-wire/tests/mtls.rs",
        "crates/aogd/tests/daemon_mtls.rs",
    }
    if detector == "URI" and normalized in uri_paths:
        parsed = urlsplit(raw.strip("\"'"))
        local_test_uri = re.search(
            r"[a-z]+://(?:test|user|client):[^@\s]+@(?:cp1|127\.0\.0\.1)(?::[0-9]+)?",
            raw,
        )
        if (
            parsed.username in {"test", "user", "client"}
            and parsed.hostname in {"cp1", "127.0.0.1"}
        ) or local_test_uri is not None:
            return "reviewed-non-secret", "local-test-uri"
    fail(
        "unreviewed TruffleHog finding: "
        f"detector={detector} path={normalized} object={object_id}"
    )


def normalized_finding(payload: dict[str, Any]) -> dict[str, Any]:
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"finding_id": sha256_bytes(stable), **payload}


def run_gitleaks(
    *,
    binary: Path,
    corpus: Path,
    report: Path,
    phase: str,
    historical_paths: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    completed = run(
        [
            str(binary),
            "dir",
            str(corpus),
            "--redact=100",
            "--no-banner",
            "--no-color",
            "--report-format=json",
            f"--report-path={report}",
        ],
        allowed={0, 1},
    )
    raw = read_json(report, "Gitleaks report") if report.stat().st_size else []
    if not isinstance(raw, list):
        fail("Gitleaks report is not a JSON array")
    findings: list[dict[str, Any]] = []
    unreviewed: list[str] = []
    for record in raw:
        object_id, source_kind = object_from_scanner_path(str(record["File"]))
        path = historical_paths.get(object_id, "") if source_kind == "blob" else ""
        try:
            disposition, reason = gitleaks_classification(
                phase=phase,
                rule=str(record["RuleID"]),
                object_id=object_id,
                historical_path=path,
            )
        except ArchiveSafetyError:
            unreviewed.append(f"{phase}:{record['RuleID']}:{path}:{object_id}")
            continue
        findings.append(
            normalized_finding(
                {
                    "disposition": disposition,
                    "engine": "gitleaks",
                    "historical_path": path,
                    "line": int(record.get("StartLine", 0)),
                    "object_sha": object_id,
                    "reason": reason,
                    "rule": str(record["RuleID"]),
                    "source_kind": source_kind,
                }
            )
        )
    if unreviewed:
        fail("unreviewed Gitleaks findings: " + "; ".join(sorted(set(unreviewed))))
    return sorted(findings, key=lambda item: item["finding_id"]), {
        "exit_code": completed.returncode,
        "raw_finding_count": len(raw),
    }


def run_trufflehog(
    *,
    binary: Path,
    corpus: Path,
    report: Path,
    phase: str,
    historical_paths: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = sorted(path.name for path in corpus.iterdir() if path.is_file())
    outputs: list[bytes] = []
    batch_count = 0
    base_command = [
        str(binary),
        "filesystem",
        "--json",
        "--no-update",
        "--no-verification",
        "--results=verified,unknown,unverified,filtered_unverified",
        "--fail-on-scan-errors",
        "--concurrency=4",
    ]

    def scan_batch(batch: list[str]) -> None:
        nonlocal batch_count
        completed = subprocess.run(
            [*base_command, *batch],
            cwd=corpus,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0 and len(batch) > 1:
            midpoint = len(batch) // 2
            scan_batch(batch[:midpoint])
            scan_batch(batch[midpoint:])
            return
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", "replace").strip()
            fail(f"TruffleHog could not scan exact object file {batch[0]}: {stderr}")
        outputs.append(completed.stdout)
        batch_count += 1

    for offset in range(0, len(files), 300):
        scan_batch(files[offset : offset + 300])
    combined_output = b"".join(outputs)
    report.write_bytes(combined_output)
    findings: list[dict[str, Any]] = []
    unreviewed: list[str] = []
    for line in combined_output.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        file_value = str(record["SourceMetadata"]["Data"]["Filesystem"]["file"])
        object_id, source_kind = object_from_scanner_path(file_value)
        path = historical_paths.get(object_id, "") if source_kind == "blob" else ""
        raw = str(record.get("Raw", ""))
        try:
            disposition, reason = trufflehog_classification(
                detector=str(record["DetectorName"]),
                raw=raw,
                historical_path=path,
                source_kind=source_kind,
                object_id=object_id,
            )
        except ArchiveSafetyError:
            unreviewed.append(
                f"{record['DetectorName']}:{path}:{source_kind}:{object_id}"
            )
            continue
        findings.append(
            normalized_finding(
                {
                    "detector": str(record["DetectorName"]),
                    "disposition": disposition,
                    "engine": "trufflehog",
                    "historical_path": path,
                    "line": int(
                        record["SourceMetadata"]["Data"]["Filesystem"].get("line", 0)
                    ),
                    "object_sha": object_id,
                    "reason": reason,
                    "source_kind": source_kind,
                    "verified": bool(record.get("Verified", False)),
                }
            )
        )
    if unreviewed:
        fail("unreviewed TruffleHog findings: " + "; ".join(sorted(set(unreviewed))))
    unique_findings = {item["finding_id"]: item for item in findings}
    return sorted(unique_findings.values(), key=lambda item: item["finding_id"]), {
        "batch_count": batch_count,
        "duplicate_finding_count": len(findings) - len(unique_findings),
        "exit_code": 0,
        "raw_finding_count": len(findings),
    }


def scan_phase(
    *,
    phase: str,
    repo: Path,
    tips: list[str],
    scratch: Path,
    historical_paths: dict[str, str],
    gitleaks_binary: Path,
    trufflehog_binary: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    corpus = scratch / f"{phase}-scan-input"
    coverage = materialize_scan_input(
        repo=repo, tips=tips, root=corpus, paths=historical_paths
    )
    gitleaks_findings, gitleaks_run = run_gitleaks(
        binary=gitleaks_binary,
        corpus=corpus,
        report=scratch / f"{phase}-gitleaks.json",
        phase=phase,
        historical_paths=historical_paths,
    )
    trufflehog_findings, trufflehog_run = run_trufflehog(
        binary=trufflehog_binary,
        corpus=corpus,
        report=scratch / f"{phase}-trufflehog.jsonl",
        phase=phase,
        historical_paths=historical_paths,
    )
    findings = sorted(
        [*gitleaks_findings, *trufflehog_findings],
        key=lambda item: (item["engine"], item["finding_id"]),
    )
    disposition_counts = Counter(item["disposition"] for item in findings)
    return findings, {
        "coverage": coverage,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "gitleaks": gitleaks_run,
        "normalized_finding_count": len(findings),
        "trufflehog": trufflehog_run,
    }


def build_evidence(
    *,
    root: Path,
    source_repo: Path,
    inventory_path: Path,
    scratch: Path,
    object_map_output: Path,
    findings_output: Path,
    gitleaks_binary: Path,
    trufflehog_binary: Path,
) -> dict[str, Any]:
    inventory, refs = inventory_context(inventory_path)
    tips = candidate_tips(refs)
    original_types, historical_paths, original_sizes = object_inventory(source_repo, tips)
    inventory_commits = {str(record["sha"]) for record in inventory["commits"]}
    actual_commits = set(rev_list(source_repo, tips))
    if actual_commits != inventory_commits:
        fail("source object graph does not match the frozen SAD-HIST-01 commits")
    for record in refs:
        resolved = git(source_repo, "rev-parse", f"{record['commit_sha']}^{{commit}}").decode().strip()
        if resolved != record["commit_sha"]:
            fail(f"candidate ref commit is unavailable: {record['ref']}")

    gitleaks_version = scanner_version(gitleaks_binary, "Gitleaks")
    trufflehog_version = scanner_version(trufflehog_binary, "TruffleHog")
    if gitleaks_version != EXPECTED_GITLEAKS_VERSION:
        fail(
            f"Gitleaks version drift: expected {EXPECTED_GITLEAKS_VERSION}, found {gitleaks_version}"
        )
    if trufflehog_version != EXPECTED_TRUFFLEHOG_VERSION:
        fail(
            "TruffleHog version drift: "
            f"expected {EXPECTED_TRUFFLEHOG_VERSION}, found {trufflehog_version}"
        )

    archive_repo = scratch / "sanitized-archive.git"
    mapping, ref_map, sanitized_tips = rewrite_history(
        source_repo=source_repo,
        archive_repo=archive_repo,
        refs=refs,
        original_types=original_types,
    )
    map_records = [mapping[object_id] for object_id in sorted(mapping)]
    object_map_text = "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in map_records
    )
    object_map_output.parent.mkdir(parents=True, exist_ok=True)
    object_map_output.write_text(object_map_text, encoding="utf-8", newline="\n")

    original_findings, original_scan = scan_phase(
        phase="original",
        repo=source_repo,
        tips=tips,
        scratch=scratch,
        historical_paths=historical_paths,
        gitleaks_binary=gitleaks_binary,
        trufflehog_binary=trufflehog_binary,
    )
    sanitized_paths = {
        str(mapping[object_id]["new_sha"]): path
        for object_id, path in historical_paths.items()
        if object_id in mapping
    }
    sanitized_findings, sanitized_scan = scan_phase(
        phase="sanitized",
        repo=archive_repo,
        tips=sanitized_tips,
        scratch=scratch,
        historical_paths=sanitized_paths,
        gitleaks_binary=gitleaks_binary,
        trufflehog_binary=trufflehog_binary,
    )
    if original_scan["disposition_counts"].get("confirmed-secret") != 2:
        fail("original history did not produce the two reviewed secret findings")
    if sanitized_scan["disposition_counts"].get("confirmed-secret", 0) != 0:
        fail("sanitized history still has a confirmed secret finding")

    findings_payload = {
        "original": original_findings,
        "sanitized": sanitized_findings,
        "schema_version": "saddle-history-scanner-findings/v1",
    }
    findings_output.parent.mkdir(parents=True, exist_ok=True)
    findings_output.write_text(canonical(findings_payload), encoding="utf-8", newline="\n")

    changed_counts = Counter(
        record["object_type"] for record in map_records if record["changed"]
    )
    signature_stripped = sum(
        bool(record.get("signature_stripped")) for record in map_records
    )
    generator = root / "tools" / "prove_saddle_history_archive_safety.py"
    return {
        "archive": {
            "publication_authorized": False,
            "publication_command_policy": "push exact archive refs only; never mirror",
            "ref_map": ref_map,
            "rewrite_required": True,
            "sanitization": {
                "changed_object_type_counts": dict(sorted(changed_counts.items())),
                "original_secret_object_shas": [
                    REDACTED_SOURCE_BLOB,
                    REDACTED_SOURCE_COMMIT,
                ],
                "replacement": "remove the historical wrapped-token value and require runtime injection",
                "signature_stripped_commit_count": signature_stripped,
            },
        },
        "generator": {
            "path": generator.relative_to(root).as_posix(),
            "sha256": sha256_file(generator),
        },
        "inventory": {
            "path": inventory_path.relative_to(root).as_posix(),
            "published_ref_digest": inventory["source"]["published_ref_digest"],
            "sha256": sha256_file(inventory_path),
        },
        "object_map": {
            "changed_object_count": sum(record["changed"] for record in map_records),
            "entry_count": len(map_records),
            "original_object_byte_count": sum(original_sizes.values()),
            "path": object_map_output.relative_to(root).as_posix(),
            "schema_version": OBJECT_MAP_SCHEMA,
            "sha256": sha256_file(object_map_output),
            "unchanged_object_count": sum(not record["changed"] for record in map_records),
        },
        "prompt": "SAD-HIST-02",
        "scanners": {
            "findings": {
                "path": findings_output.relative_to(root).as_posix(),
                "sha256": sha256_file(findings_output),
            },
            "gitleaks": {
                "binary_sha256": sha256_file(gitleaks_binary),
                "mode": "filesystem over exact reachable blob and commit-message closure",
                "version": gitleaks_version,
            },
            "original": original_scan,
            "sanitized": sanitized_scan,
            "trufflehog": {
                "binary_sha256": sha256_file(trufflehog_binary),
                "mode": "filesystem over exact reachable blob and commit-message closure; verification disabled",
                "version": trufflehog_version,
            },
        },
        "schema_version": SCHEMA,
        "source": {
            "candidate_commit_count": len(actual_commits),
            "candidate_ref_count": len(refs),
            "remote_url": SOURCE_URL,
        },
        "status": "pass",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-01/history-inventory.json"),
    )
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-02/archive-safety.json"),
    )
    parser.add_argument(
        "--object-map-output",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-02/object-map.jsonl"),
    )
    parser.add_argument(
        "--findings-output",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-02/scanner-findings.json"),
    )
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--gitleaks", type=Path, required=True)
    parser.add_argument("--trufflehog", type=Path, required=True)
    parser.add_argument("--keep-scratch", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def resolve_under(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def remove_readonly(function: Any, path: str, _error: BaseException) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    inventory_path = resolve_under(root, args.inventory)
    evidence_output = resolve_under(root, args.evidence_output)
    object_map_output = resolve_under(root, args.object_map_output)
    findings_output = resolve_under(root, args.findings_output)
    scratch = args.scratch.resolve()
    try:
        for output in (evidence_output, object_map_output, findings_output):
            output.relative_to(root)
        if scratch.exists():
            fail(f"scratch path already exists: {scratch}")
        scratch.mkdir(parents=True)
        if args.verify:
            if not all(path.is_file() for path in (evidence_output, object_map_output, findings_output)):
                fail("verification outputs do not all exist")
            expected_evidence = evidence_output.read_text(encoding="utf-8")
            expected_map = object_map_output.read_text(encoding="utf-8")
            expected_findings = findings_output.read_text(encoding="utf-8")
        evidence = build_evidence(
            root=root,
            source_repo=args.source_repo.resolve(),
            inventory_path=inventory_path,
            scratch=scratch,
            object_map_output=object_map_output,
            findings_output=findings_output,
            gitleaks_binary=args.gitleaks.resolve(),
            trufflehog_binary=args.trufflehog.resolve(),
        )
        rendered = canonical(evidence)
        if args.verify:
            if object_map_output.read_text(encoding="utf-8") != expected_map:
                fail("object map is not byte-for-byte reproducible")
            if findings_output.read_text(encoding="utf-8") != expected_findings:
                fail("normalized scanner findings are not byte-for-byte reproducible")
            if rendered != expected_evidence:
                fail("archive-safety evidence is not byte-for-byte reproducible")
        else:
            evidence_output.parent.mkdir(parents=True, exist_ok=True)
            evidence_output.write_text(rendered, encoding="utf-8", newline="\n")
    except (ArchiveSafetyError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"SAD-HIST-02 archive-safety proof failed: {error}", file=sys.stderr)
        return 1
    finally:
        if scratch.exists() and not args.keep_scratch:
            shutil.rmtree(scratch, onexc=remove_readonly)
    print("SAD-HIST-02 archive-safety proof: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
