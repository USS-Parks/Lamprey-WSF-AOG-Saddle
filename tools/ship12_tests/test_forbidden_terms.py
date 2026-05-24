"""SHIP-12 forbidden-term scanner behavior tests.

Exercises `scripts/ci_forbidden_terms.py` end-to-end via subprocess against
synthetic fixture trees, plus runs the real scanner against the live repo
to assert it stays green on main.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "scripts" / "ci_forbidden_terms.py"
LIVE_CONFIG = REPO_ROOT / "config" / "forbidden-terms.toml"


def run_scanner(config: Path, json_mode: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCANNER), "--config", str(config)]
    if json_mode:
        cmd.append("--json")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


def make_fixture(tmp_path: Path, *, fake_root: str, files: dict[str, str], terms: list[dict]) -> Path:
    """Write a tree of source files plus a config that points at them."""
    root_dir = tmp_path / fake_root
    root_dir.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        target = root_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    cfg = tmp_path / "forbidden-terms.toml"
    # Use an absolute path for the root so the scanner (which resolves
    # relative roots against the real REPO_ROOT) walks the fixture tree.
    root_abs = root_dir.resolve().as_posix()
    lines = [
        "[scan]",
        f'roots = ["{root_abs}"]',
        'extensions = [".rs"]',
        "",
    ]
    for t in terms:
        lines.append("[[term]]")
        lines.append(f'name = "{t["name"]}"')
        lines.append(f'description = "{t.get("description", "")}"')
        lines.append(f'carried_forward = "{t.get("carried_forward", "SHIP-16")}"')
        allowed = t.get("allowed_paths", [])
        if allowed:
            lines.append("allowed_paths = [")
            for p in allowed:
                # Allowlist entries are "<fake_root>/<rel>". Convert to the
                # absolute path the scanner will produce for fixture files
                # outside REPO_ROOT.
                rel_under_root = p.split("/", 1)[1] if "/" in p else ""
                abs_path = (root_dir / rel_under_root).resolve().as_posix()
                lines.append(f'  "{abs_path}",')
            lines.append("]")
        else:
            lines.append("allowed_paths = []")
        lines.append("")
    cfg.write_text("\n".join(lines), encoding="utf-8")
    return cfg


# Override the conftest-injected tmp_path so subprocess.cwd=REPO_ROOT still
# sees an absolute path inside the temp dir.
@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    return tmp_path


def test_scanner_exists() -> None:
    assert SCANNER.exists(), "scripts/ci_forbidden_terms.py is required"


def test_live_repo_passes() -> None:
    result = run_scanner(LIVE_CONFIG)
    assert result.returncode == 0, (
        f"forbidden-term scan is failing on main:\n{result.stdout}\n{result.stderr}"
    )
    assert "PASS" in result.stdout


def test_live_repo_json_well_formed() -> None:
    result = run_scanner(LIVE_CONFIG, json_mode=True)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["hits"] == []
    assert payload["files_scanned"] > 0
    assert payload["terms"] > 0


def test_disallowed_hit_fails(scratch: Path) -> None:
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={"foo.rs": "let x = StubVault::new();\n"},
        terms=[
            {
                "name": "StubVault",
                "description": "demo only",
                "allowed_paths": [],
            }
        ],
    )
    result = run_scanner(cfg)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "StubVault" in result.stdout
    assert "FAIL" in result.stdout


def test_allowlisted_hit_passes(scratch: Path) -> None:
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={"foo.rs": "let x = StubVault::new();\n"},
        terms=[
            {
                "name": "StubVault",
                "allowed_paths": ["src/foo.rs"],
            }
        ],
    )
    result = run_scanner(cfg)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_unrelated_file_passes(scratch: Path) -> None:
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={"foo.rs": "let x = ZfsVault::new();\n"},
        terms=[
            {
                "name": "StubVault",
                "allowed_paths": [],
            }
        ],
    )
    result = run_scanner(cfg)
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_one_disallowed_in_a_mixed_tree_fails(scratch: Path) -> None:
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={
            "ok.rs": "// nothing here\n",
            "blessed.rs": "fn use_stub() { StubVault::new(); }\n",
            "violation.rs": "fn smuggle() { StubVault::new(); }\n",
        },
        terms=[
            {
                "name": "StubVault",
                "allowed_paths": ["src/blessed.rs"],
            }
        ],
    )
    result = run_scanner(cfg)
    assert result.returncode == 1
    assert "violation.rs" in result.stdout
    assert "blessed.rs" not in result.stdout
    payload = json.loads(run_scanner(cfg, json_mode=True).stdout)
    assert len(payload["hits"]) == 1
    assert payload["hits"][0]["file"].endswith("violation.rs")


def test_case_sensitive_match(scratch: Path) -> None:
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={"foo.rs": "let x = stubvault::new();\n"},
        terms=[{"name": "StubVault", "allowed_paths": []}],
    )
    result = run_scanner(cfg)
    assert result.returncode == 0, "scanner must be case-sensitive"


def test_extensions_filter_skips_other_suffixes(scratch: Path) -> None:
    # Default fixture allows only .rs. A .md file with the term must be ignored.
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={"notes.md": "We used StubVault here\n"},
        terms=[{"name": "StubVault", "allowed_paths": []}],
    )
    result = run_scanner(cfg)
    assert result.returncode == 0, result.stdout


def test_missing_config_exits_2(scratch: Path) -> None:
    result = run_scanner(scratch / "nope.toml")
    assert result.returncode == 2, result.stdout + result.stderr


def test_bad_config_exits_2(scratch: Path) -> None:
    bad = scratch / "bad.toml"
    bad.write_text("this is = not valid toml [[[", encoding="utf-8")
    result = run_scanner(bad)
    assert result.returncode == 2


def test_empty_terms_list_exits_2(scratch: Path) -> None:
    bad = scratch / "empty.toml"
    bad.write_text(
        textwrap.dedent(
            """\
            [scan]
            roots = ["src"]
            extensions = [".rs"]
            """
        ),
        encoding="utf-8",
    )
    result = run_scanner(bad)
    assert result.returncode == 2


def test_duplicate_term_name_exits_2(scratch: Path) -> None:
    bad = scratch / "dup.toml"
    bad.write_text(
        textwrap.dedent(
            """\
            [scan]
            roots = ["src"]
            extensions = [".rs"]

            [[term]]
            name = "StubVault"
            allowed_paths = []

            [[term]]
            name = "StubVault"
            allowed_paths = []
            """
        ),
        encoding="utf-8",
    )
    result = run_scanner(bad)
    assert result.returncode == 2
    assert "duplicate" in result.stderr.lower()


def test_json_hit_payload_carries_carried_forward(scratch: Path) -> None:
    cfg = make_fixture(
        scratch,
        fake_root="src",
        files={"foo.rs": "let x = MemoryAuditWriter::new();\n"},
        terms=[
            {
                "name": "MemoryAuditWriter",
                "carried_forward": "SHIP-16",
                "allowed_paths": [],
            }
        ],
    )
    result = run_scanner(cfg, json_mode=True)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["hits"][0]["carried_forward"] == "SHIP-16"
    assert payload["hits"][0]["term"] == "MemoryAuditWriter"
