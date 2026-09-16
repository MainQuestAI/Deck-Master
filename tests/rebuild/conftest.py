"""Shared fixtures for tests/rebuild.

Adds ``src/`` to sys.path so tests import the new package without touching the
user's installed version (isolated until T05 restructures packaging).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from deck_master.models import new_document  # noqa: E402
from deck_master.store import Store  # noqa: E402


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    st = Store(tmp_path / "project")
    st.ensure_layout()
    return st


@pytest.fixture()
def created_store(tmp_path: Path) -> Store:
    st = Store(tmp_path / "project")
    st.ensure_layout()
    document = new_document(
        project_id="demo",
        task={"title": "Demo deck", "brief": "Build a demo deck."},
    )
    st.init_project(document, operation_id="op-create-1")
    return st
