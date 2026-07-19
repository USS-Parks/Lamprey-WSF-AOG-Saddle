#!/usr/bin/env python3
"""Inventory published Mighty Eel history without importing any Git object."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SOURCE_URL = "https://github.com/USS-Parks/Mighty-Eel-OS.git"
APPROVED_MAIN = "fedf005a30ad388ab156dc8bd693a3aa3f0702ea"
CANONICAL_FOOTER = "Authored and reviewed by Basho Parks, copyright 2026"
SELECTED_DISPOSITIONS = {"extract", "historical-evidence", "import"}
RELEVANT_PATH = re.compile(
    r"(?i)(?:^|[/_.-])(?:aog|wsf|fabric|saddle|loom)(?:$|[/_.-])|"
    r"orchestrat|scheduler|trust|revocation|receipt|openbao"
)
FIELD_SEPARATOR = "\x1f"
RECORD_SEPARATOR = "\x1e"


class InventoryError(RuntimeError):
    """Raised when published history cannot be inventoried exactly."""


def fail(message: str) -> None:
    raise InventoryError(message)


def git_command(repo: Path, *args: str) -> list[str]:
    resolved = repo.resolve()
    return [
        "git",
        "-c",
        f"safe.directory={resolved}",
        "-c",
        "core.quotePath=false",
        "-c",
        "i18n.logOutputEncoding=UTF-8",
        "-c",
        "log.showSignature=false",
        "-C",
        str(resolved),
        *args,
    ]


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
) -> bytes:
    completed = subprocess.run(
        command,
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        fail(
            f"{' '.join(command)} failed with {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout


def git(repo: Path, *args: str) -> bytes:
    return run(git_command(repo, *args))


def text(payload: bytes) -> str:
    return payload.decode("utf-8", "replace")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def scrub_url(value: str) -> str:
    """Remove credentials without changing the repository identity."""
    parsed = urlsplit(value)
    if not parsed.scheme or "@" not in parsed.netloc:
        return value
    host = parsed.netloc.rsplit("@", 1)[1]
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def parse_remote_refs(payload: bytes) -> list[dict[str, str]]:
    objects: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in text(payload).splitlines():
        object_id, ref = line.split("\t", 1)
        if ref.endswith("^{}"):
            peeled[ref[:-3]] = object_id
        elif ref.startswith(("refs/heads/", "refs/tags/")):
            objects[ref] = object_id
    if not objects:
        fail("source remote advertises no heads or tags")
    refs: list[dict[str, str]] = []
    for ref, object_id in sorted(objects.items()):
        kind = "branch" if ref.startswith("refs/heads/") else "tag"
        record = {"kind": kind, "object_sha": object_id, "ref": ref}
        if ref in peeled:
            record["peeled_sha"] = peeled[ref]
        refs.append(record)
    return refs


def resolve_ref_commits(repo: Path, refs: list[dict[str, str]]) -> None:
    expressions = [f"{record['object_sha']}^{{commit}}" for record in refs]
    commit_ids = text(git(repo, "rev-parse", *expressions)).splitlines()
    if len(commit_ids) != len(refs):
        fail("published refs did not resolve one-to-one to commits")
    for record, commit_id in zip(refs, commit_ids, strict=True):
        advertised_peeled = record.get("peeled_sha")
        if advertised_peeled is not None and advertised_peeled != commit_id:
            fail(f"peeled tag mismatch for {record['ref']}")
        record["commit_sha"] = commit_id


def published_membership(
    repo: Path, refs: list[dict[str, str]]
) -> tuple[dict[str, set[str]], set[str]]:
    membership: dict[str, set[str]] = defaultdict(set)
    commits: set[str] = set()

    def reachable_from(record: dict[str, str]) -> set[str]:
        return set(text(git(repo, "rev-list", record["commit_sha"])).splitlines())

    worker_count = min(8, len(refs))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        reachable_sets = executor.map(reachable_from, refs)
        ref_reachability = zip(refs, reachable_sets, strict=True)
        for record, reachable in ref_reachability:
            record["reachable_commit_count"] = len(reachable)
            commits.update(reachable)
            for commit_id in reachable:
                membership[commit_id].add(record["ref"])
    return membership, commits


def parse_commit_log(repo: Path, tips: list[str]) -> dict[str, dict[str, Any]]:
    format_string = FIELD_SEPARATOR.join(
        (
            "%H",
            "%P",
            "%T",
            "%an",
            "%ae",
            "%aI",
            "%cn",
            "%ce",
            "%cI",
            "%s",
        )
    )
    payload = text(
        git(
            repo,
            "log",
            "--topo-order",
            "--no-renames",
            f"--format={RECORD_SEPARATOR}{format_string}",
            "--name-only",
            *tips,
        )
    )
    commits: dict[str, dict[str, Any]] = {}
    for raw_record in payload.split(RECORD_SEPARATOR)[1:]:
        lines = raw_record.lstrip("\n").splitlines()
        if not lines:
            continue
        fields = lines[0].split(FIELD_SEPARATOR)
        if len(fields) != 10:
            fail(f"unexpected metadata field count for commit record: {len(fields)}")
        (
            commit_id,
            parents,
            tree,
            author_name,
            author_email,
            author_date,
            committer_name,
            committer_email,
            committer_date,
            subject,
        ) = fields
        if commit_id in commits:
            fail(f"duplicate commit metadata record: {commit_id}")
        commits[commit_id] = {
            "author": {
                "date": author_date,
                "email": author_email,
                "name": author_name,
            },
            "changed_paths": sorted({line for line in lines[1:] if line}),
            "committer": {
                "date": committer_date,
                "email": committer_email,
                "name": committer_name,
            },
            "parents": parents.split() if parents else [],
            "sha": commit_id,
            "subject": subject,
            "tree": tree,
        }
    return commits


def signature_record(commit_object: bytes) -> dict[str, Any]:
    headers = commit_object.split(b"\n\n", 1)[0]
    match = re.search(rb"(?:^|\n)(gpgsig(?:-sha256)? [^\n]*(?:\n [^\n]*)*)", headers)
    if match is None:
        return {"format": None, "present": False, "sha256": None}
    signature = match.group(1)
    if b"BEGIN SSH SIGNATURE" in signature:
        signature_format = "ssh"
    elif b"BEGIN PGP SIGNATURE" in signature:
        signature_format = "openpgp"
    elif b"BEGIN SIGNED MESSAGE" in signature:
        signature_format = "x509"
    else:
        signature_format = "unknown"
    return {
        "format": signature_format,
        "present": True,
        "sha256": sha256_bytes(signature),
    }


def commit_signatures(repo: Path, commit_ids: set[str]) -> dict[str, dict[str, Any]]:
    ordered = sorted(commit_ids)
    payload = b"\n".join(commit_id.encode("ascii") for commit_id in ordered) + b"\n"
    output = run(git_command(repo, "cat-file", "--batch"), input_bytes=payload)
    cursor = 0
    records: dict[str, dict[str, Any]] = {}
    for expected_id in ordered:
        header_end = output.find(b"\n", cursor)
        if header_end < 0:
            fail("truncated cat-file batch header")
        header = output[cursor:header_end].decode("ascii", "replace").split()
        if len(header) != 3 or header[0] != expected_id or header[1] != "commit":
            fail(f"unexpected cat-file batch record for {expected_id}")
        size = int(header[2])
        object_start = header_end + 1
        object_end = object_start + size
        if object_end >= len(output) or output[object_end : object_end + 1] != b"\n":
            fail(f"truncated cat-file batch object for {expected_id}")
        records[expected_id] = signature_record(output[object_start:object_end])
        cursor = object_end + 1
    if cursor != len(output):
        fail("cat-file batch returned trailing data")
    return records


def commit_messages(repo: Path, tips: list[str]) -> dict[str, str]:
    payload = text(
        git(
            repo,
            "log",
            f"--format={RECORD_SEPARATOR}%H{FIELD_SEPARATOR}%B",
            *tips,
        )
    )
    messages: dict[str, str] = {}
    for raw_record in payload.split(RECORD_SEPARATOR)[1:]:
        record = raw_record.lstrip("\n")
        if FIELD_SEPARATOR not in record:
            fail("commit-message record is missing its field separator")
        commit_id, body = record.split(FIELD_SEPARATOR, 1)
        messages[commit_id] = body.rstrip("\n")
    return messages


def patch_ids(repo: Path, tips: list[str]) -> dict[str, str]:
    log_process = subprocess.Popen(
        git_command(
            repo,
            "log",
            "-p",
            "--no-merges",
            "--no-ext-diff",
            "--binary",
            *tips,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert log_process.stdout is not None
    patch_process = subprocess.Popen(
        ["git", "patch-id", "--stable"],
        stdin=log_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    log_process.stdout.close()
    patch_output, patch_error = patch_process.communicate()
    assert log_process.stderr is not None
    log_error = log_process.stderr.read()
    log_return = log_process.wait()
    if log_return != 0:
        fail(f"git log for patch IDs failed: {text(log_error).strip()}")
    if patch_process.returncode != 0:
        fail(f"git patch-id failed: {text(patch_error).strip()}")
    result: dict[str, str] = {}
    for line in text(patch_output).splitlines():
        patch_id, commit_id = line.split()
        result[commit_id] = patch_id
    return result


def manifest_context(path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        fail("source manifest has no entries array")
    dispositions = {entry["path"]: entry["disposition"] for entry in entries}
    return dispositions, {
        "entry_count": len(entries),
        "seed_sha": payload["seed"]["sha"],
        "sha256": sha256_bytes(raw),
    }


def annotate_commit(
    record: dict[str, Any],
    *,
    refs: set[str],
    main_commits: set[str],
    main_patch_ids: dict[str, list[str]],
    patch_id: str | None,
    tree_equivalent_parents: list[str],
    dispositions: dict[str, str],
    message: str,
) -> None:
    paths = record["changed_paths"]
    disposition_counts = Counter(dispositions.get(path, "absent-at-seed") for path in paths)
    selected_paths = sorted(
        path for path in paths if dispositions.get(path) in SELECTED_DISPOSITIONS
    )
    relevant_absent_paths = sorted(
        path
        for path in paths
        if path not in dispositions and RELEVANT_PATH.search(path) is not None
    )
    relevance: list[str] = []
    if selected_paths:
        relevance.append("seed-selected-path-history")
    if any(RELEVANT_PATH.search(path) is not None for path in paths):
        relevance.append("wsf-aog-saddle-path")
    if relevant_absent_paths:
        relevance.append("relevant-path-absent-at-seed")
    if len(record["parents"]) > 1 and not paths:
        relevance.append("merge-requires-parent-analysis")
    if not relevance:
        relevance.append("other-mighty-eel-history")

    equivalent_main = sorted(main_patch_ids.get(patch_id, [])) if patch_id else []
    if record["sha"] in main_commits:
        disposition = "archive-mainline-ancestry"
        requires_review = False
    elif equivalent_main:
        disposition = "archive-patch-equivalent"
        requires_review = False
    elif tree_equivalent_parents:
        disposition = "archive-tree-equivalent"
        requires_review = False
    else:
        disposition = "review-required"
        requires_review = True

    nonempty_lines = [line for line in message.splitlines() if line.strip()]
    record.update(
        {
            "canonical_footer": bool(
                nonempty_lines and nonempty_lines[-1] == CANONICAL_FOOTER
            ),
            "equivalent_main_commits": equivalent_main,
            "manifest_disposition_counts": dict(sorted(disposition_counts.items())),
            "migration_disposition": disposition,
            "patch_id": patch_id,
            "published_refs": sorted(refs),
            "relevance": relevance,
            "relevant_paths_absent_at_seed": relevant_absent_paths,
            "requires_human_review": requires_review,
            "selected_paths": selected_paths,
            "tree_equivalent_parents": tree_equivalent_parents,
        }
    )


def build_inventory(
    *,
    root: Path,
    source_repo: Path,
    source_url: str,
    source_manifest: Path,
    expected_main: str,
) -> dict[str, Any]:
    if not source_repo.is_dir():
        fail(f"source repository does not exist: {source_repo}")
    if not source_manifest.is_file():
        fail(f"source manifest does not exist: {source_manifest}")

    refs = parse_remote_refs(run(["git", "ls-remote", "--heads", "--tags", source_url]))
    resolve_ref_commits(source_repo, refs)
    refs_by_name = {record["ref"]: record for record in refs}
    main_ref = refs_by_name.get("refs/heads/main")
    if main_ref is None:
        fail("published source has no refs/heads/main")
    if main_ref["commit_sha"] != expected_main:
        fail(
            "published source main moved: "
            f"expected {expected_main}, found {main_ref['commit_sha']}"
        )

    membership, published_commits = published_membership(source_repo, refs)
    main_commits = set(text(git(source_repo, "rev-list", expected_main)).splitlines())
    tips = sorted({record["commit_sha"] for record in refs})
    metadata = parse_commit_log(source_repo, tips)
    messages = commit_messages(source_repo, tips)
    signatures = commit_signatures(source_repo, published_commits)
    if set(metadata) != published_commits:
        fail("commit metadata does not exactly cover the published object graph")
    if set(messages) != published_commits:
        fail("commit messages do not exactly cover the published object graph")
    if set(signatures) != published_commits:
        fail("commit signatures do not exactly cover the published object graph")

    commit_patch_ids = patch_ids(source_repo, tips)
    main_patch_ids: dict[str, list[str]] = defaultdict(list)
    for commit_id in main_commits:
        patch_id = commit_patch_ids.get(commit_id)
        if patch_id is not None:
            main_patch_ids[patch_id].append(commit_id)

    path_dispositions, manifest = manifest_context(source_manifest)
    for commit_id, record in metadata.items():
        record["signature"] = signatures[commit_id]
        tree_equivalent_parents = sorted(
            parent
            for parent in record["parents"]
            if parent in metadata and metadata[parent]["tree"] == record["tree"]
        )
        annotate_commit(
            record,
            refs=membership[commit_id],
            main_commits=main_commits,
            main_patch_ids=main_patch_ids,
            patch_id=commit_patch_ids.get(commit_id),
            tree_equivalent_parents=tree_equivalent_parents,
            dispositions=path_dispositions,
            message=messages[commit_id],
        )

    ordered_commits = [metadata[commit_id] for commit_id in sorted(metadata)]
    disposition_counts = Counter(record["migration_disposition"] for record in ordered_commits)
    signature_counts = Counter(
        record["signature"]["format"] or "unsigned" for record in ordered_commits
    )
    ref_payload = json.dumps(refs, sort_keys=True, separators=(",", ":")).encode()
    generator = root / "tools" / "generate_saddle_history_inventory.py"
    return {
        "commits": ordered_commits,
        "generator": {
            "path": generator.relative_to(root).as_posix(),
            "sha256": sha256_file(generator),
        },
        "prompt": "SAD-HIST-01",
        "published_refs": refs,
        "schema_version": "saddle-published-history-inventory/v1",
        "source": {
            "approved_main_sha": expected_main,
            "manifest": manifest,
            "published_ref_digest": sha256_bytes(ref_payload),
            "remote_url": scrub_url(source_url),
        },
        "status": "pass",
        "summary": {
            "branch_count": sum(record["kind"] == "branch" for record in refs),
            "canonical_footer_commit_count": sum(
                record["canonical_footer"] for record in ordered_commits
            ),
            "commit_count": len(ordered_commits),
            "mainline_commit_count": len(main_commits),
            "migration_disposition_counts": dict(sorted(disposition_counts.items())),
            "published_ref_count": len(refs),
            "remote_only_commit_count": len(published_commits - main_commits),
            "signature_format_counts": dict(sorted(signature_counts.items())),
            "tag_count": sum(record["kind"] == "tag" for record in refs),
        },
    }


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("test-evidence/saddle/SAD-02/source-manifest.json"),
    )
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-01/history-inventory.json"),
    )
    parser.add_argument("--expected-main", default=APPROVED_MAIN)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    source_manifest = (
        args.source_manifest
        if args.source_manifest.is_absolute()
        else root / args.source_manifest
    ).resolve()
    evidence_output = (
        args.evidence_output
        if args.evidence_output.is_absolute()
        else root / args.evidence_output
    ).resolve()
    try:
        evidence_output.relative_to(root)
        rendered = canonical(
            build_inventory(
                root=root,
                source_repo=args.source_repo.resolve(),
                source_url=args.source_url,
                source_manifest=source_manifest,
                expected_main=args.expected_main,
            )
        )
        if args.verify:
            if not evidence_output.is_file():
                fail(f"evidence file does not exist: {evidence_output}")
            if evidence_output.read_text(encoding="utf-8") != rendered:
                fail("history evidence does not match the published ref inventory")
        else:
            evidence_output.parent.mkdir(parents=True, exist_ok=True)
            evidence_output.write_text(rendered, encoding="utf-8", newline="\n")
    except (InventoryError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"SAD-HIST-01 inventory failed: {error}", file=sys.stderr)
        return 1
    print("SAD-HIST-01 published-history inventory: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
