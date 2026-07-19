"""Contract tests for the SAD-HIST-02 archive-safety proof."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prove_saddle_history_archive_safety",
    REPO_ROOT / "tools" / "prove_saddle_history_archive_safety.py",
)
assert SPEC is not None and SPEC.loader is not None
safety = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(safety)


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve()}", "-C", str(repo), *args],
        input=input_bytes,
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    return completed.stdout.decode("utf-8", "replace").strip()


def commit(repo: Path, subject: str, body: str, when: str) -> str:
    environment = os.environ.copy()
    environment.update({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve()}",
            "-C",
            str(repo),
            "add",
            "--all",
        ],
        env=environment,
        check=True,
        capture_output=True,
    )
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve()}",
            "-C",
            str(repo),
            "commit",
            "-m",
            subject,
            "-m",
            body,
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return git(repo, "rev-parse", "HEAD")


def fixture_history(tmp_path: Path) -> tuple[Path, list[dict[str, str]], str, str]:
    source = tmp_path / "source"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(source)],
        check=True,
        capture_output=True,
    )
    git(source, "config", "user.name", "Basho Parks")
    git(source, "config", "user.email", "basho@example.test")
    connection = source / "deployment" / "openbao-staging" / "openbao-connection.toml"
    connection.parent.mkdir(parents=True)
    connection.write_text(
        "[auth.approle]\n"
        "# secret_id delivered via response-wrapped token: s.FixtureValue123\n",
        encoding="utf-8",
    )
    first = commit(
        source,
        "add staging reference",
        "fixture history",
        "2026-01-01T00:00:00+00:00",
    )
    secret_blob = git(source, "rev-parse", f"{first}:deployment/openbao-staging/openbao-connection.toml")
    git(source, "branch", "legacy", first)
    connection.write_text(
        "[auth.approle]\n# secret_id is injected at runtime\n", encoding="utf-8"
    )
    transient = source / "records" / "transient.txt"
    transient.parent.mkdir(parents=True)
    transient.write_text("deleted historical blob\n", encoding="utf-8")
    commit(
        source,
        "stage cleaned reference",
        "fixture transition",
        "2026-01-02T00:00:00+00:00",
    )
    transient.unlink()
    secret_commit = commit(
        source,
        "remove staging token",
        "The wrapped token s.FixtureValue123 was removed.",
        "2026-01-03T00:00:00+00:00",
    )
    refs = [
        {
            "commit_sha": secret_commit,
            "object_sha": secret_commit,
            "ref": "refs/heads/main",
        },
        {
            "commit_sha": first,
            "object_sha": first,
            "ref": "refs/heads/legacy",
        },
    ]
    return source, refs, secret_blob, secret_commit


def test_rewrite_removes_secret_objects_and_maps_complete_closure(
    tmp_path: Path, monkeypatch
) -> None:
    source, refs, secret_blob, secret_commit = fixture_history(tmp_path)
    monkeypatch.setattr(safety, "REDACTED_SOURCE_BLOB", secret_blob)
    monkeypatch.setattr(safety, "REDACTED_SOURCE_COMMIT", secret_commit)
    tips = safety.candidate_tips(refs)
    original_types, _, _ = safety.object_inventory(source, tips)
    archive = tmp_path / "archive.git"

    mapping, ref_map, sanitized_tips = safety.rewrite_history(
        source_repo=source,
        archive_repo=archive,
        refs=refs,
        original_types=original_types,
    )

    assert set(mapping) == set(original_types)
    assert mapping[secret_blob]["changed"] is True
    assert mapping[secret_commit]["changed"] is True
    assert mapping[secret_blob]["new_sha"] != secret_blob
    assert mapping[secret_commit]["new_sha"] != secret_commit
    assert len(ref_map) == 2
    assert all(
        record["archive_ref"].startswith("refs/heads/history/mighty-eel/")
        for record in ref_map
    )
    assert len(safety.rev_list(archive, sanitized_tips)) == 3
    missing = subprocess.run(
        safety.git_command(archive, "cat-file", "-e", secret_blob),
        check=False,
        capture_output=True,
    )
    assert missing.returncode != 0
    rewritten_message = safety.commit_message(
        safety.read_object(archive, "commit", mapping[secret_commit]["new_sha"])
    )
    assert b"s.FixtureValue123" not in rewritten_message
    assert b"<redacted-wrapped-token>" in rewritten_message


def test_materialized_closure_includes_deleted_blobs_and_messages(
    tmp_path: Path,
) -> None:
    source, refs, _, _ = fixture_history(tmp_path)
    types, paths, _ = safety.object_inventory(source, safety.candidate_tips(refs))
    destination = tmp_path / "scan-input"

    coverage = safety.materialize_scan_input(
        repo=source,
        tips=safety.candidate_tips(refs),
        root=destination,
        paths=paths,
    )

    assert coverage["commit_message_count"] == 3
    assert coverage["deleted_blob_count"] >= 1
    assert coverage["input_file_count"] == (
        coverage["blob_count"] + coverage["commit_message_count"]
    )
    assert len(list(destination.iterdir())) == coverage["input_file_count"]
    assert coverage["object_type_counts"]["commit"] == 3
    assert len(types) == sum(coverage["object_type_counts"].values())


def test_reviewed_scanner_classifications_are_narrow() -> None:
    assert safety.trufflehog_classification(
        detector="Lob",
        raw="test_01234567890123456789012345678901234",
        historical_path="any/test/path.py",
        source_kind="blob",
        object_id="0" * 40,
    ) == ("reviewed-non-secret", "vendor-defined-lob-test-key")
    assert safety.trufflehog_classification(
        detector="GoogleOauth2",
        raw="ya29.gcp-bearer-material",
        historical_path="",
        source_kind="commit-message",
        object_id="1" * 40,
    ) == ("reviewed-non-secret", "documented-placeholder-gcp-bearer")
    assert safety.trufflehog_classification(
        detector="URI",
        raw="https://user:fixture@cp1:4600",
        historical_path="crates/aog-wire/src/lib.rs",
        source_kind="blob",
        object_id="2" * 40,
    ) == ("reviewed-non-secret", "local-test-uri")


def test_committed_evidence_has_complete_ref_object_and_scan_contracts() -> None:
    evidence_path = (
        REPO_ROOT / "test-evidence" / "saddle" / "SAD-HIST-02" / "archive-safety.json"
    )
    object_map_path = evidence_path.with_name("object-map.jsonl")
    findings_path = evidence_path.with_name("scanner-findings.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    object_records = [
        json.loads(line)
        for line in object_map_path.read_text(encoding="utf-8").splitlines()
    ]
    findings = json.loads(findings_path.read_text(encoding="utf-8"))

    assert evidence["status"] == "pass"
    assert evidence["source"] == {
        "candidate_commit_count": 762,
        "candidate_ref_count": 38,
        "remote_url": "https://github.com/USS-Parks/Mighty-Eel-OS.git",
    }
    assert len(evidence["archive"]["ref_map"]) == 38
    assert len({record["archive_ref"] for record in evidence["archive"]["ref_map"]}) == 38
    assert evidence["object_map"]["entry_count"] == len(object_records)
    assert len({record["old_sha"] for record in object_records}) == len(object_records)
    assert evidence["scanners"]["original"]["coverage"]["deleted_blob_count"] > 0
    assert evidence["scanners"]["original"]["disposition_counts"][
        "confirmed-secret"
    ] == 2
    assert "confirmed-secret" not in evidence["scanners"]["sanitized"][
        "disposition_counts"
    ]
    assert all(
        finding["disposition"] == "reviewed-non-secret"
        for finding in findings["sanitized"]
    )
    assert len({finding["finding_id"] for finding in findings["original"]}) == len(
        findings["original"]
    )
    assert len({finding["finding_id"] for finding in findings["sanitized"]}) == len(
        findings["sanitized"]
    )
    assert evidence["scanners"]["original"]["trufflehog"][
        "raw_finding_count"
    ] == (
        evidence["scanners"]["original"]["trufflehog"][
            "duplicate_finding_count"
        ]
        + sum(
            finding["engine"] == "trufflehog" for finding in findings["original"]
        )
    )
