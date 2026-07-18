"""Cross-file contract for the Debian package metadata."""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]
DEBIAN = REPO_ROOT / "packaging" / "debian"


def read(name: str) -> str:
    return (DEBIAN / name).read_text(encoding="utf-8")


def test_control_identifies_saddle() -> None:
    control = read("control")
    assert re.search(r"^Source:\s*saddle$", control, re.MULTILINE)
    assert re.search(r"^Package:\s*saddle$", control, re.MULTILINE)
    for field in ("Maintainer:", "Build-Depends:", "Architecture:", "Depends:", "Description:"):
        assert field in control


def test_changelog_and_rules_identify_saddle() -> None:
    assert re.match(r"^saddle \(\d+\.\d+\.\d+-\d+\)", read("changelog"))
    rules = read("rules")
    assert rules.startswith("#!/usr/bin/make -f")
    assert "export PKG_NAME = saddle" in rules
    assert "dh_installsystemd" not in rules


def test_install_map_matches_current_layout() -> None:
    install = read("install")
    for path in ("usr/bin/*", "usr/share/doc/saddle", "etc/saddle/config", "etc/saddle/saddle.yaml"):
        assert path in install
    assert "mai" not in install


def test_conffiles_are_part_of_the_install_map() -> None:
    install = read("install")
    for path in read("conffiles").splitlines():
        path = path.strip().lstrip("/")
        if path.endswith("auth_keys.toml"):
            assert "etc/saddle/config" in install
        elif path:
            assert path in install


def test_debhelper_compatibility_is_consistent() -> None:
    match = re.search(r"debhelper-compat\s*\(=\s*(\d+)\)", read("control"))
    assert match
    assert int(read("compat").strip()) == int(match.group(1))
