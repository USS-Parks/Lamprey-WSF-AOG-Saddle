"""Static contract for the Saddle package builders."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SH = REPO_ROOT / "scripts" / "build-package.sh"
PS = REPO_ROOT / "scripts" / "build-package.ps1"

BINARIES = ("saddled", "saddle-noded", "saddlectl", "wsf-api", "wsf-seed", "aog-gateway")
FORBIDDEN = ("mai-api", "mai-admin", "mai-adapters", "mai-sdk-python", "compliance-dashboard")


def test_builders_exist_and_are_strict() -> None:
    assert SH.is_file()
    assert PS.is_file()
    assert "set -euo pipefail" in SH.read_text(encoding="utf-8")
    assert '$ErrorActionPreference = "Stop"' in PS.read_text(encoding="utf-8")


def test_builders_stage_the_owned_binaries() -> None:
    for body in (SH.read_text(encoding="utf-8"), PS.read_text(encoding="utf-8")):
        for binary in BINARIES:
            assert binary in body
        for path in ("usr/bin", "usr/share/doc/saddle", "etc/saddle/config"):
            assert path in body
        for field in ("name=saddle", "git_commit", "build_time", "validation_only"):
            assert field in body


def test_package_builders_do_not_reference_excluded_surfaces() -> None:
    combined = SH.read_text(encoding="utf-8") + PS.read_text(encoding="utf-8")
    for token in FORBIDDEN:
        assert token not in combined


def test_validation_mode_is_explicitly_non_release() -> None:
    shell = SH.read_text(encoding="utf-8")
    assert "--validate-only" in shell
    assert "--deb cannot be combined with --validate-only" in shell
