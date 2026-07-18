"""Every configuration copied into the package must parse as TOML."""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_packaged_toml_parses() -> None:
    files = sorted((REPO_ROOT / "config").rglob("*.toml"))
    assert files
    for path in files:
        with path.open("rb") as handle:
            tomllib.load(handle)


def test_kubernetes_manifest_is_packaged() -> None:
    manifest = REPO_ROOT / "deployment" / "saddle-harness" / "k3s" / "saddle.yaml"
    assert manifest.is_file()
    assert "kind:" in manifest.read_text(encoding="utf-8")
