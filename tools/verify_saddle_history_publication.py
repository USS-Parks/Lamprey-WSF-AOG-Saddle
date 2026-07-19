#!/usr/bin/env python3
"""Verify the protected publication of Saddle's sanitized Mighty Eel archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, NoReturn

SCHEMA = "saddle-history-publication/v1"
REMOTE_URL = "https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle.git"
REPOSITORY = "USS-Parks/Lamprey-WSF-AOG-Saddle"
ARCHIVE_PREFIX = "refs/heads/history/mighty-eel/"
RULESET_NAME = "Immutable Mighty Eel history archive"
RULESET_PATTERN = "refs/heads/history/mighty-eel/**"
REQUIRED_RULES = {"deletion", "non_fast_forward", "update"}
BASE_COMMIT = "f66134ef4b3b36c1506f277dbbb9bf61c7d82d7c"
REVIEWED_LANE_COMMIT = "8c38d9d47ffe714932c61616c1d236c60159a716"
SECRET_OBJECTS = {
    "ffb2ea027f2a965cdad277c1ebbde291d3314a36",
    "c75e95f15256b929e382ec58658348502e6a5f83",
}
ACTIVE_PRODUCT_CHANGES = {
    "crates/wsf-api/src/openapi.json": "reviewed-sad-hist-03-transplant",
    "deployment/supply-chain/no-phone-home.sh": "reviewed-static-gate-repair",
}
ALLOWED_SUPPORT_CHANGES = {
    "PLANNING/SADDLE-HISTORY-RECONCILIATION-ADDENDUM.md",
    "PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md",
    "docs/sessions/SADDLE-DEVLOG.md",
    "test-evidence/saddle/SAD-12/independence-gate.json",
    "test-evidence/saddle/SAD-23/active-name-eradication-gate.json",
    "tools/ci_surface_tests/test_no_phone_home.py",
    "tools/ci_surface_tests/test_wsf_openapi.py",
}
ALLOWED_PREFIXES = (
    "docs/history/",
    "test-evidence/saddle/SAD-HIST-",
    "tools/ci_surface_tests/test_history_",
)
ALLOWED_HISTORY_TOOLS = {
    "tools/generate_saddle_history_inventory.py",
    "tools/prove_saddle_history_archive_safety.py",
    "tools/reconcile_saddle_history_non_main.py",
    "tools/verify_saddle_history_publication.py",
}


class PublicationError(RuntimeError):
    """Raised when archive publication cannot be proved exactly."""


def fail(message: str) -> NoReturn:
    raise PublicationError(message)


def run(command: list[str], *, cwd: Path | None = None) -> bytes:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        fail(f"{' '.join(command)} failed with {completed.returncode}: {stderr}")
    return completed.stdout


def git(repo: Path, *args: str) -> bytes:
    return run(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve()}",
            "-c",
            "core.longpaths=true",
            "-C",
            str(repo.resolve()),
            *args,
        ]
    )


def git_object_exists(repo: Path, object_id: str) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve()}",
            "-C",
            str(repo.resolve()),
            "cat-file",
            "-e",
            f"{object_id}^{{commit}}",
        ],
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {label} {path}: {error}")


def canonical(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_ls_remote(payload: bytes) -> dict[str, str]:
    refs: dict[str, str] = {}
    for raw_line in payload.decode("ascii").splitlines():
        object_id, separator, ref = raw_line.partition("\t")
        if not separator or not ref.startswith(ARCHIVE_PREFIX):
            fail(f"unexpected archive ls-remote record: {raw_line}")
        if ref in refs:
            fail(f"duplicate remote archive ref: {ref}")
        refs[ref] = object_id
    return refs


def validate_ruleset(payload: dict[str, Any], ruleset_id: int | None = None) -> dict[str, Any]:
    if ruleset_id is not None and payload.get("id") != ruleset_id:
        fail("archive ruleset ID changed")
    if payload.get("name") != RULESET_NAME:
        fail("archive ruleset name changed")
    if payload.get("target") != "branch" or payload.get("enforcement") != "active":
        fail("archive ruleset is not an active branch ruleset")
    ref_name = payload.get("conditions", {}).get("ref_name", {})
    if ref_name.get("include") != [RULESET_PATTERN] or ref_name.get("exclude") != []:
        fail("archive ruleset ref boundary changed")
    rule_types = {str(rule.get("type")) for rule in payload.get("rules", [])}
    if rule_types != REQUIRED_RULES:
        fail("archive ruleset must prohibit deletion, update, and non-fast-forward changes")
    if payload.get("bypass_actors") != []:
        fail("archive ruleset unexpectedly has a bypass actor")
    if payload.get("current_user_can_bypass") not in (None, "never"):
        fail("archive ruleset unexpectedly permits current-user bypass")
    return {
        "bypass_actor_count": 0,
        "enforcement": "active",
        "id": int(payload["id"]),
        "name": RULESET_NAME,
        "ref_pattern": RULESET_PATTERN,
        "rules": sorted(REQUIRED_RULES),
        "target": "branch",
    }


def expected_ref_map(archive_safety: dict[str, Any]) -> dict[str, str]:
    records = archive_safety.get("archive", {}).get("ref_map", [])
    expected: dict[str, str] = {}
    for record in records:
        ref = str(record["archive_ref"])
        if not ref.startswith(ARCHIVE_PREFIX) or ref in expected:
            fail(f"invalid or duplicate approved archive ref: {ref}")
        expected[ref] = str(record["sanitized_commit_sha"])
    if len(expected) != 38:
        fail(f"expected 38 approved archive refs, found {len(expected)}")
    return expected


def archive_graph(archive_repo: Path, expected: dict[str, str]) -> dict[str, Any]:
    actual_lines = git(
        archive_repo,
        "for-each-ref",
        "--format=%(refname) %(objectname)",
        ARCHIVE_PREFIX,
    ).decode("ascii").splitlines()
    actual = dict(line.split(" ", 1) for line in actual_lines)
    if actual != expected:
        fail("local sanitized archive refs do not equal the approved ref map")
    git(archive_repo, "fsck", "--full", "--no-dangling")
    for object_id in SECRET_OBJECTS:
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={archive_repo.resolve()}",
                "-C",
                str(archive_repo.resolve()),
                "cat-file",
                "-e",
                object_id,
            ],
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            fail(f"original secret-bearing object survives in sanitized archive: {object_id}")
        if completed.returncode != 1:
            fail(f"could not prove secret-bearing object absent: {object_id}")
    tips = sorted(set(expected.values()))
    commits = git(archive_repo, "rev-list", *tips).decode("ascii").splitlines()
    object_ids = sorted(
        {
            line.partition(" ")[0]
            for line in git(archive_repo, "rev-list", "--objects", *tips)
            .decode("utf-8", "surrogateescape")
            .splitlines()
        }
    )
    batch = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={archive_repo.resolve()}",
            "-C",
            str(archive_repo.resolve()),
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        ],
        input=("\n".join(object_ids) + "\n").encode("ascii"),
        capture_output=True,
        check=False,
    )
    if batch.returncode != 0:
        fail("could not enumerate sanitized archive object metadata")
    metadata_lines = sorted(batch.stdout.decode("ascii").splitlines())
    object_types = Counter(line.split()[1] for line in metadata_lines)
    if len(set(commits)) != 762 or len(object_ids) != 10444:
        fail("sanitized archive graph counts changed")
    return {
        "commit_count": 762,
        "object_count": 10444,
        "object_metadata_sha256": sha256_bytes(
            ("\n".join(metadata_lines) + "\n").encode("ascii")
        ),
        "object_type_counts": dict(sorted(object_types.items())),
        "ref_count": 38,
    }


def repository_change_gate(root: Path) -> dict[str, Any]:
    if git(root, "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD") != b"":
        fail("unexpected merge-base output")
    if git(root, "merge-base", "--is-ancestor", REVIEWED_LANE_COMMIT, "HEAD") != b"":
        fail("reviewed SAD-HIST-03 checkpoint is not an ancestor")
    changed = set(
        git(root, "diff", "--name-only", BASE_COMMIT, "--")
        .decode("utf-8")
        .splitlines()
    )
    untracked = set(
        git(root, "ls-files", "--others", "--exclude-standard")
        .decode("utf-8")
        .splitlines()
    )
    changed.update(untracked)
    for path in sorted(changed):
        allowed = (
            path in ACTIVE_PRODUCT_CHANGES
            or path in ALLOWED_SUPPORT_CHANGES
            or path in ALLOWED_HISTORY_TOOLS
            or path.startswith(ALLOWED_PREFIXES)
        )
        if not allowed:
            fail(f"unreviewed path changed from the reconciled main base: {path}")
    dependency_files: dict[str, dict[str, str]] = {}
    for path in ("Cargo.toml", "Cargo.lock"):
        base = git(root, "show", f"{BASE_COMMIT}:{path}")
        current = (root / path).read_bytes()
        if current != base:
            fail(f"active dependency graph changed during history reconciliation: {path}")
        dependency_files[path] = {
            "base_sha256": sha256_bytes(base),
            "current_sha256": sha256_bytes(current),
        }
    product_changes = []
    for path, disposition in sorted(ACTIVE_PRODUCT_CHANGES.items()):
        if path not in changed:
            fail(f"reviewed active change is missing: {path}")
        product_changes.append(
            {
                "disposition": disposition,
                "path": path,
                "sha256": sha256_file(root / path),
            }
        )
    return {
        "active_product_changes": product_changes,
        "base_commit": BASE_COMMIT,
        "dependency_files": dependency_files,
        "reviewed_lane_commit": REVIEWED_LANE_COMMIT,
    }


def verify_recorded_repository_gate(root: Path, recorded: dict[str, Any]) -> None:
    if recorded.get("base_commit") != BASE_COMMIT:
        fail("recorded active-tree base commit changed")
    if recorded.get("reviewed_lane_commit") != REVIEWED_LANE_COMMIT:
        fail("recorded reviewed-lane commit changed")

    for path in ("Cargo.toml", "Cargo.lock"):
        expected = recorded.get("dependency_files", {}).get(path, {})
        current = sha256_file(root / path)
        if expected.get("base_sha256") != current:
            fail(f"recorded base dependency digest changed: {path}")
        if expected.get("current_sha256") != current:
            fail(f"active dependency digest changed: {path}")

    product_changes = recorded.get("active_product_changes")
    if not isinstance(product_changes, list):
        fail("recorded active product changes are malformed")
    expected_changes = {
        path: disposition for path, disposition in ACTIVE_PRODUCT_CHANGES.items()
    }
    recorded_changes: dict[str, str] = {}
    for item in product_changes:
        path = item.get("path")
        disposition = item.get("disposition")
        if not isinstance(path, str) or not isinstance(disposition, str):
            fail("recorded active product change is malformed")
        if sha256_file(root / path) != item.get("sha256"):
            fail(f"reviewed active product digest changed: {path}")
        recorded_changes[path] = disposition
    if recorded_changes != expected_changes:
        fail("recorded active product change set changed")

    full_history = git_object_exists(root, BASE_COMMIT) and git_object_exists(
        root, REVIEWED_LANE_COMMIT
    )
    if full_history:
        if repository_change_gate(root) != recorded:
            fail("recorded active-tree gate changed")
        return
    if git(root, "rev-parse", "--is-shallow-repository").strip() != b"true":
        fail("required history commits are missing from a non-shallow checkout")


def object_map_summary(path: Path) -> dict[str, Any]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(records) != 10444:
        fail("SAD-HIST-02 object map entry count changed")
    changed = Counter(
        str(record["object_type"]) for record in records if bool(record["changed"])
    )
    stripped = sum(bool(record.get("signature_stripped")) for record in records)
    if dict(sorted(changed.items())) != {"blob": 1, "commit": 456, "tree": 10}:
        fail("SAD-HIST-02 changed-object counts changed")
    if stripped != 235:
        fail("SAD-HIST-02 stripped-signature count changed")
    return {
        "changed_object_type_counts": dict(sorted(changed.items())),
        "entry_count": len(records),
        "sha256": sha256_file(path),
        "signature_stripped_commit_count": stripped,
    }


def build_evidence(root: Path, archive_repo: Path, ruleset_id: int) -> dict[str, Any]:
    safety_path = root / "test-evidence/saddle/SAD-HIST-02/archive-safety.json"
    object_map_path = root / "test-evidence/saddle/SAD-HIST-02/object-map.jsonl"
    findings_path = root / "test-evidence/saddle/SAD-HIST-02/scanner-findings.json"
    reconciliation_path = root / "test-evidence/saddle/SAD-HIST-03/non-main-reconciliation.json"
    safety = read_json(safety_path, "SAD-HIST-02 archive safety evidence")
    expected = expected_ref_map(safety)
    graph = archive_graph(archive_repo, expected)
    remote = parse_ls_remote(
        run(["git", "ls-remote", "--heads", REMOTE_URL, f"{ARCHIVE_PREFIX}*"])
    )
    if remote != expected:
        fail("published remote archive refs do not equal the approved ref map")
    ruleset = validate_ruleset(
        json.loads(
            run(
                [
                    "gh",
                    "api",
                    f"repos/{REPOSITORY}/rulesets/{ruleset_id}",
                ]
            )
        ),
        ruleset_id,
    )
    ref_records = []
    safety_records = {record["archive_ref"]: record for record in safety["archive"]["ref_map"]}
    for ref, remote_sha in sorted(remote.items()):
        source = safety_records[ref]
        ref_records.append(
            {
                "archive_ref": ref,
                "changed": bool(source["changed"]),
                "original_commit_sha": source["original_commit_sha"],
                "remote_commit_sha": remote_sha,
                "sanitized_commit_sha": source["sanitized_commit_sha"],
                "source_ref": source["source_ref"],
            }
        )
    return {
        "active_tree": repository_change_gate(root),
        "archive": {
            "graph": graph,
            "ref_map": ref_records,
            "remote_ref_digest": sha256_bytes(
                "".join(f"{sha}\t{ref}\n" for ref, sha in sorted(remote.items())).encode("ascii")
            ),
            "remote_url": REMOTE_URL,
        },
        "inputs": {
            "archive_safety": {"path": safety_path.relative_to(root).as_posix(), "sha256": sha256_file(safety_path)},
            "non_main_reconciliation": {"path": reconciliation_path.relative_to(root).as_posix(), "sha256": sha256_file(reconciliation_path)},
            "scanner_findings": {"path": findings_path.relative_to(root).as_posix(), "sha256": sha256_file(findings_path)},
        },
        "object_map": object_map_summary(object_map_path),
        "prompt": "SAD-HIST-04",
        "protection": ruleset,
        "schema_version": SCHEMA,
    }


def verify_recorded(root: Path, output: Path) -> None:
    payload = read_json(output, "SAD-HIST-04 publication evidence")
    if payload.get("schema_version") != SCHEMA or payload.get("prompt") != "SAD-HIST-04":
        fail("unsupported SAD-HIST-04 publication evidence")
    safety = read_json(
        root / payload["inputs"]["archive_safety"]["path"], "archive safety input"
    )
    expected = expected_ref_map(safety)
    recorded = {
        item["archive_ref"]: item["remote_commit_sha"]
        for item in payload["archive"]["ref_map"]
    }
    if recorded != expected:
        fail("recorded remote refs do not equal the approved ref map")
    for record in payload["inputs"].values():
        if sha256_file(root / record["path"]) != record["sha256"]:
            fail(f"recorded input digest changed: {record['path']}")
    object_map_path = root / "test-evidence/saddle/SAD-HIST-02/object-map.jsonl"
    if object_map_summary(object_map_path) != payload["object_map"]:
        fail("recorded object-map summary changed")
    normalized_ruleset = dict(payload["protection"])
    if normalized_ruleset.get("rules") != sorted(REQUIRED_RULES):
        fail("recorded archive protection rules changed")
    verify_recorded_repository_gate(root, payload["active_tree"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("test-evidence/saddle/SAD-HIST-04/archive-publication.json"),
    )
    parser.add_argument("--archive-repo", type=Path)
    parser.add_argument("--ruleset-id", type=int)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-recorded", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    output = args.output.resolve() if args.output.is_absolute() else (root / args.output).resolve()
    try:
        output.relative_to(root)
        if args.verify_recorded:
            verify_recorded(root, output)
        else:
            if args.archive_repo is None or args.ruleset_id is None:
                fail("live verification requires --archive-repo and --ruleset-id")
            expected = output.read_text(encoding="utf-8") if args.verify else None
            evidence = build_evidence(root, args.archive_repo.resolve(), args.ruleset_id)
            rendered = canonical(evidence)
            if expected is not None and rendered != expected:
                fail("publication evidence is not byte-for-byte reproducible")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
    except (PublicationError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"SAD-HIST-04 publication verification failed: {error}", file=sys.stderr)
        return 1
    print("SAD-HIST-04 publication verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
