"""RP-25 real Chromium image leases, real loopback images; synthetic inputs only."""

import shutil

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


def test_same_turn_remount_shares_read_but_departure_cancels(tmp_path):
    from playwright.sync_api import sync_playwright

    project = tmp_path / "project"
    create_sample(project, page_count=1)
    store = Store(project)
    ref = store.read_object_json(store.load_document()["pages"][0]["blueprint"])["file"]
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(server.start() + "studio/")
            result = page.evaluate(
                """async ref => {
              const {ImagePool} = await import('/v2/images.js');
              const pool = new ImagePool();
              const first = pool.acquire('synthetic', ref);
              first.release();
              const second = pool.acquire('synthetic', ref);
              const shared = first.ready === second.ready;
              await second.ready;
              second.release();
              const warm = pool.acquire('synthetic', ref);
              const reused = warm.ready === second.ready;
              warm.release();
              const before = pool.snapshot();
              const leaving = new ImagePool();
              const pending = leaving.acquire('synthetic', ref);
              const rejection = pending.ready.catch(e => e.name);
              pending.release();
              await Promise.resolve();
              const empty = leaving.entries.size === 0;
              const cancelled = await rejection;
              return {shared, reused, before, empty, cancelled};
            }""",
                ref,
            )
            assert result["shared"] and result["reused"]
            assert result["before"]["hits"] == 2
            assert result["before"]["evictions"] == 0
            assert result["before"]["pinned"] == 0
            assert result["empty"] and result["cancelled"] == "AbortError"
            browser.close()
    finally:
        server.stop()
