"""Regression coverage for the static zero-phone-home scanner."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "deployment" / "supply-chain" / "no-phone-home.sh"


def _bash() -> str:
    if os.name == "nt":
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if git_bash.is_file():
            return str(git_bash)
    found = shutil.which("bash")
    if found is None:
        raise unittest.SkipTest("bash is required for the supply-chain scanner")
    return found


def _scan(source: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source_dir = root / "crates" / "fixture" / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "lib.rs").write_text(source, encoding="utf-8")
        return subprocess.run(
            [_bash(), "-l", str(SCANNER), "."],
            check=False,
            capture_output=True,
            cwd=root,
            text=True,
        )


class NoPhoneHomeTests(unittest.TestCase):
    def test_schema_names_and_local_test_hosts_are_not_phone_home(self) -> None:
        result = _scan(
            r'''
const FINALIZER: &str = "saddle.islandmountain.io/tenant-teardown";
const LEGACY_API: &str = concat!("aog", ".islandmountain.io/v1");
const CASE_FIXTURE: &str = "https://EXAMPLE.com:443";
const PRIVATE_FIXTURE: &str = "https://10.10.0.8:8443";
const LINK_LOCAL_FIXTURE: &str = "https://169.254.169.254/latest/meta-data";
const LAN_FIXTURE: &str = "https://model.lan:8443";
'''
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_unknown_public_and_vendor_hosts_fail_closed(self) -> None:
        result = _scan(
            r'''
const VENDOR: &str = "https://control.islandmountain.io/telemetry";
const UNKNOWN: &str = "https://collector.vendor.net/collect";
'''
        )
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("FAIL: unexpected phone-home surface", result.stderr)


if __name__ == "__main__":
    unittest.main()
