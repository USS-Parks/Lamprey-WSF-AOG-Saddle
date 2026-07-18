"""POSIX entrypoints must retain executable Git modes from Windows checkouts."""

from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[2]


def tracked_modes() -> dict[str, str]:
    output = subprocess.check_output(
        ["git", "ls-files", "--stage"], cwd=REPO_ROOT, text=True
    )
    modes: dict[str, str] = {}
    for line in output.splitlines():
        metadata, path = line.split("\t", 1)
        modes[path.replace("\\", "/")] = metadata.split()[0]
    return modes


def test_all_tracked_shebang_entrypoints_are_executable() -> None:
    modes = tracked_modes()
    failures = []
    for path, mode in modes.items():
        absolute = REPO_ROOT / path
        if not absolute.is_file():
            continue
        if absolute.read_bytes().startswith(b"#!") and mode != "100755":
            failures.append((path, mode))
    assert not failures, f"shell entrypoints missing executable mode: {failures}"


def test_debian_rules_is_executable() -> None:
    assert tracked_modes()["packaging/debian/rules"] == "100755"
