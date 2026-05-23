"""Pytest fixtures shared by MAI tool suites.

The Windows/Python 3.14 combination used in local validation can create
`tmp_path` directories with unreadable ACLs through pytest's built-in
fixture. These tool tests only need an ordinary scratch directory, so keep
the override scoped to `tools/` rather than changing product code.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path() -> Path:
    root = Path(os.environ.get("MAI_PYTEST_TMP", os.environ.get("TEMP", ".")))
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"mai-tools-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
