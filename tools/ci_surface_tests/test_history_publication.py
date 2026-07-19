import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "verify_saddle_history_publication.py"
SPEC = importlib.util.spec_from_file_location("history_publication", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_archive_ref_parser_rejects_non_archive_refs() -> None:
    payload = b"0" * 40 + b"\trefs/heads/main\n"
    try:
        MODULE.parse_ls_remote(payload)
    except MODULE.PublicationError as error:
        assert "unexpected archive" in str(error)
    else:
        raise AssertionError("non-archive ref was accepted")


def test_recorded_publication_matches_approved_map() -> None:
    evidence = ROOT / "test-evidence" / "saddle" / "SAD-HIST-04" / "archive-publication.json"
    if not evidence.is_file():
        return
    MODULE.verify_recorded(ROOT, evidence)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["archive"]["graph"]["commit_count"] == 762
    assert payload["archive"]["graph"]["object_count"] == 10444
    assert payload["archive"]["graph"]["ref_count"] == 38
    assert payload["protection"]["rules"] == [
        "deletion",
        "non_fast_forward",
        "update",
    ]
