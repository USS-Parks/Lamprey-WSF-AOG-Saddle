"""Contract tests for the SAD-HIST-03 non-main reconciliation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "reconcile_saddle_history_non_main",
    REPO_ROOT / "tools" / "reconcile_saddle_history_non_main.py",
)
assert SPEC is not None and SPEC.loader is not None
reconciliation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconciliation)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decisions_exactly_cover_the_frozen_review_queue() -> None:
    inventory = load_json(
        REPO_ROOT
        / "test-evidence"
        / "saddle"
        / "SAD-HIST-01"
        / "history-inventory.json"
    )
    queue = {
        record["sha"]
        for record in inventory["commits"]
        if record["migration_disposition"] == "review-required"
    }

    assert queue == set(reconciliation.DECISIONS)
    assert all(
        decision["disposition"] in reconciliation.ALLOWED_DISPOSITIONS
        for decision in reconciliation.DECISIONS.values()
    )
    transplants = [
        decision
        for decision in reconciliation.DECISIONS.values()
        if decision["disposition"] == "transplant"
    ]
    assert len(transplants) == 1
    assert transplants[0]["saddle_commits"]


def test_committed_evidence_is_complete_and_anchored_to_current_files() -> None:
    result = load_json(
        REPO_ROOT
        / "test-evidence"
        / "saddle"
        / "SAD-HIST-03"
        / "non-main-reconciliation.json"
    )

    assert result["schema_version"] == reconciliation.SCHEMA
    assert result["status"] == "pass"
    assert result["summary"] == {
        "disposition_counts": {
            "archive": 1,
            "exclusion": 1,
            "superseded": 9,
            "transplant": 1,
        },
        "review_required_commit_count": 12,
        "transplant_commit_count": 1,
        "unreviewed_commit_count": 0,
    }
    assert len({review["source"]["sha"] for review in result["reviews"]}) == 12

    for review in result["reviews"]:
        assert review["rationale"]
        assert review["behavior"]
        assert review["published_refs"]
        if review["disposition"] == "superseded":
            assert review["source_main_commits"] or review["saddle_commits"]
            assert review["verification"]
        for item in review["evidence"]:
            path = REPO_ROOT / item["path"]
            content = path.read_text(encoding="utf-8")
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
            assert all(anchor in content for anchor in item["anchors"])


def test_no_candidate_object_or_archive_ref_was_imported() -> None:
    result = load_json(
        REPO_ROOT
        / "test-evidence"
        / "saddle"
        / "SAD-HIST-03"
        / "non-main-reconciliation.json"
    )
    source_shas = {review["source"]["sha"] for review in result["reviews"]}

    assert sum(review["disposition"] == "transplant" for review in result["reviews"]) == 1
    archive_refs = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={REPO_ROOT.resolve()}",
            "-C",
            str(REPO_ROOT),
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads/history/mighty-eel/",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert not archive_refs
    # A source SHA may be cited only as data; it must never be a Saddle commit.
    assert source_shas.isdisjoint(
        commit["sha"]
        for review in result["reviews"]
        for commit in review["saddle_commits"]
    )


if __name__ == "__main__":
    test_decisions_exactly_cover_the_frozen_review_queue()
    test_committed_evidence_is_complete_and_anchored_to_current_files()
    test_no_candidate_object_or_archive_ref_was_imported()
    print("SAD-HIST-03 reconciliation contract tests: PASS")
