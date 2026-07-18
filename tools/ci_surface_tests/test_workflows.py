"""Fail when active workflows drift back to excluded parent-repository surfaces."""

from pathlib import Path
import json
import re
import subprocess

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOWS = sorted(WORKFLOW_DIR.glob("*.yml"))

FORBIDDEN_ACTIVE_REFERENCES = (
    "mai-api",
    "mai-admin",
    "mai-adapters",
    "mai-sdk-python",
    "adapters/",
    "lamprey-mai",
    "compliance-dashboard",
    "gpu-release",
)


def load(path: Path) -> dict[str, object]:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_workflow_names_and_required_jobs() -> None:
    expected = {
        "ci.yml": ("Saddle CI", {"config-check", "rust-check", "advisories", "wsf-live", "saddle-live", "repository-tools", "integration-ci", "conformance-ci"}),
        "ship-validation.yml": ("Saddle Validation", {"package-build-validate", "compose-trust-validation", "repository-boundary", "nightly-integration"}),
        "saddle-validation.yml": ("Saddle Workspace Validation", {"windows-validation"}),
        "supply-chain.yml": ("Saddle Supply Chain", {"phone-home", "sbom-sign"}),
    }
    for filename, (name, jobs) in expected.items():
        workflow = load(WORKFLOW_DIR / filename)
        assert workflow["name"] == name
        assert jobs <= set(workflow["jobs"])


def test_active_workflows_do_not_reference_excluded_surfaces() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in WORKFLOWS)
    for token in FORBIDDEN_ACTIVE_REFERENCES:
        assert token not in combined, f"active workflow still references excluded surface: {token}"


def test_every_workflow_cargo_package_exists() -> None:
    metadata = json.loads(
        subprocess.check_output(
            ["cargo", "metadata", "--no-deps", "--format-version", "1"],
            cwd=REPO_ROOT,
            text=True,
        )
    )
    packages = {package["name"] for package in metadata["packages"]}
    missing: set[str] = set()
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8").replace("\\\n", " ")
        for line in text.splitlines():
            if "cargo " not in line:
                continue
            missing.update(
                package
                for package in re.findall(r"(?:^|\s)-p\s+([A-Za-z0-9_-]+)", line)
                if package not in packages
            )
    assert not missing, f"workflow references unknown Cargo packages: {sorted(missing)}"


def test_nightly_depends_on_all_fast_validation_jobs() -> None:
    workflow = load(WORKFLOW_DIR / "ship-validation.yml")
    needs = set(workflow["jobs"]["nightly-integration"]["needs"])
    assert needs == {
        "package-build-validate",
        "compose-trust-validation",
        "repository-boundary",
    }
