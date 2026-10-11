"""Shared fixtures for tests/rebuild.

Adds ``src/`` to sys.path so tests import the new package without touching the
user's installed version (isolated until T05 restructures packaging).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from deck_master.models import new_document  # noqa: E402
from deck_master.store import Store  # noqa: E402


# Regression: ISSUE-003 — ambient HTTP_PROXY/HTTPS_PROXY (common on developer
# machines) routed the tests' loopback requests through the proxy, so host
# boundary tests received the proxy's 502 instead of the server's 403.
# Found by /qa on 2026-10-10
# Report: .gstack/qa-reports/run-20261010T025115Z/
@pytest.fixture(autouse=True, scope="session")
def _bypass_ambient_proxy_for_loopback_tests():
    proxy_vars = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                  "http_proxy", "https_proxy", "all_proxy")
    saved = {name: os.environ.pop(name, None) for name in proxy_vars}
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    os.environ.pop("NO_PROXY", None)
    os.environ.pop("no_proxy", None)


def pytest_addoption(parser):
    parser.addoption(
        "--require-browser", action="store_true",
        help="Require selected browser tests to execute; missing tools or skips fail the gate.",
    )


def pytest_collection_finish(session):
    if session.config.getoption("--require-browser") and not any(
        item.get_closest_marker("browser") for item in session.items
    ):
        raise pytest.UsageError("--require-browser selected no browser tests")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if (item.config.getoption("--require-browser")
            and item.get_closest_marker("browser") and report.skipped):
        report.outcome = "failed"
        report.longrepr = f"Required browser gate did not execute: {report.longrepr}"


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


@pytest.fixture(scope="session")
def resolvable_font_family():
    """A font family that fc-match resolves exactly (cross-host for CI)."""
    import shutil
    import subprocess

    if not shutil.which("fc-match"):
        pytest.fail("fc-match unavailable; cannot resolve a real font family")
    for candidate in ("Hiragino Sans GB", "Noto Sans CJK SC", "Noto Sans CJK JP",
                      "DejaVu Sans", "Helvetica", "Arial"):
        result = subprocess.run(["fc-match", "-f", "%{family}", candidate],
                                capture_output=True, text=True, check=True)
        if candidate.lower() in result.stdout.lower():
            return candidate
    pytest.fail("no resolvable font family on this host")
