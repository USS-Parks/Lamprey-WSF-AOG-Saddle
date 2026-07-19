"""Contract tests for the deterministic published-history inventory."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_saddle_history_inventory",
    REPO_ROOT / "tools" / "generate_saddle_history_inventory.py",
)
assert SPEC is not None and SPEC.loader is not None
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo.resolve()}", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def commit(repo: Path, message: str, when: str) -> str:
    environment = os.environ.copy()
    environment.update({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    git(repo, "add", "--all", env=environment)
    git(
        repo,
        "commit",
        "-m",
        message,
        "-m",
        inventory.CANONICAL_FOOTER,
        env=environment,
    )
    return git(repo, "rev-parse", "HEAD")


def fixture_history(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    remote = tmp_path / "published.git"
    source = tmp_path / "source"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(source)],
        check=True,
        capture_output=True,
    )
    git(source, "config", "user.name", "Basho Parks")
    git(source, "config", "user.email", "basho@example.test")
    git(source, "remote", "add", "origin", str(remote))

    wsf_path = source / "crates" / "wsf-core" / "src" / "lib.rs"
    wsf_path.parent.mkdir(parents=True)
    wsf_path.write_text("pub const ROOT: bool = true;\n", encoding="utf-8")
    root_sha = commit(source, "establish WSF root", "2026-01-01T00:00:00+00:00")

    history_path = source / "records" / "history.txt"
    history_path.parent.mkdir(parents=True)
    history_path.write_text("published history\n", encoding="utf-8")
    main_sha = commit(source, "record history", "2026-01-02T00:00:00+00:00")
    git(source, "push", "--set-upstream", "origin", "main")

    git(source, "checkout", "-b", "equivalent", root_sha)
    history_path.parent.mkdir(parents=True)
    history_path.write_text("published history\n", encoding="utf-8")
    commit(source, "equivalent history change", "2026-01-03T00:00:00+00:00")
    git(source, "push", "--set-upstream", "origin", "equivalent")

    git(source, "checkout", "main")
    git(source, "checkout", "-b", "distinct")
    aog_path = source / "crates" / "aog-new" / "src" / "lib.rs"
    aog_path.parent.mkdir(parents=True)
    aog_path.write_text("pub const DISTINCT: bool = true;\n", encoding="utf-8")
    commit(source, "add distinct AOG work", "2026-01-04T00:00:00+00:00")
    git(source, "push", "--set-upstream", "origin", "distinct")

    git(source, "checkout", "main")
    git(source, "checkout", "-b", "empty")
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_DATE": "2026-01-05T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-05T00:00:00+00:00",
        }
    )
    git(
        source,
        "commit",
        "--allow-empty",
        "-m",
        "record empty checkpoint",
        "-m",
        inventory.CANONICAL_FOOTER,
        env=environment,
    )
    git(source, "push", "--set-upstream", "origin", "empty")
    git(source, "tag", "contracts-v1", root_sha)
    git(source, "push", "origin", "contracts-v1")

    manifest = tmp_path / "source-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "disposition": "import",
                        "path": "crates/wsf-core/src/lib.rs",
                    },
                    {
                        "disposition": "historical-evidence",
                        "path": "records/history.txt",
                    },
                ],
                "seed": {"sha": main_sha},
            }
        ),
        encoding="utf-8",
    )
    return source, remote, manifest, main_sha


def test_inventory_accounts_for_refs_and_patch_equivalence(tmp_path: Path) -> None:
    source, remote, manifest, main_sha = fixture_history(tmp_path)
    result = inventory.build_inventory(
        root=REPO_ROOT,
        source_repo=source,
        source_url=str(remote),
        source_manifest=manifest,
        expected_main=main_sha,
    )

    assert result["summary"]["branch_count"] == 4
    assert result["summary"]["tag_count"] == 1
    assert result["summary"]["commit_count"] == 5
    assert result["summary"]["mainline_commit_count"] == 2
    assert result["summary"]["remote_only_commit_count"] == 3
    assert result["summary"]["migration_disposition_counts"] == {
        "archive-mainline-ancestry": 2,
        "archive-patch-equivalent": 1,
        "archive-tree-equivalent": 1,
        "review-required": 1,
    }
    review = next(
        commit
        for commit in result["commits"]
        if commit["migration_disposition"] == "review-required"
    )
    assert review["relevant_paths_absent_at_seed"] == ["crates/aog-new/src/lib.rs"]
    assert inventory.canonical(result) == inventory.canonical(
        inventory.build_inventory(
            root=REPO_ROOT,
            source_repo=source,
            source_url=str(remote),
            source_manifest=manifest,
            expected_main=main_sha,
        )
    )


def test_inventory_fails_if_published_main_moves(tmp_path: Path) -> None:
    source, remote, manifest, _main_sha = fixture_history(tmp_path)
    with pytest.raises(inventory.InventoryError, match="published source main moved"):
        inventory.build_inventory(
            root=REPO_ROOT,
            source_repo=source,
            source_url=str(remote),
            source_manifest=manifest,
            expected_main="0" * 40,
        )


def test_signature_record_uses_object_intrinsic_data() -> None:
    unsigned = b"tree " + (b"0" * 40) + b"\n\nmessage\n"
    signed = (
        b"tree "
        + (b"0" * 40)
        + b"\ngpgsig -----BEGIN SSH SIGNATURE-----\n abc\n -----END SSH SIGNATURE-----"
        + b"\n\nmessage\n"
    )

    assert inventory.signature_record(unsigned) == {
        "format": None,
        "present": False,
        "sha256": None,
    }
    signature = inventory.signature_record(signed)
    assert signature["format"] == "ssh"
    assert signature["present"] is True
    assert len(signature["sha256"]) == 64
