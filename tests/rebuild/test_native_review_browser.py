"""Real browser/HTTP entry with a labeled synthetic native transport (L1)."""
import shutil

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import native_review
from deck_master.web import WorkbenchServer
from test_content_preproduction_review import _deck
from test_native_review import FixtureSession


@pytest.mark.browser
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_native_review_action_uses_real_http_and_updates_normal_state(tmp_path, monkeypatch, width, height):
    project, store = _deck(tmp_path)
    FixtureSession.calls = []
    FixtureSession.status = 'pass'
    FixtureSession.corrupt = False
    FixtureSession.before_finish = None
    monkeypatch.setattr(native_review, 'CodexReviewSession', FixtureSession)
    server = WorkbenchServer(project)
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(server.start())
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            page.get_by_role('button', name='独立审阅当前内容', exact=True).click()
            dialog = page.get_by_role('dialog', name='独立审阅当前内容')
            expect(dialog).to_contain_text('实际审阅结束后保存判断')
            start = dialog.get_by_role('button', name='开始独立审阅', exact=True)
            start.click()
            expect(start).to_be_disabled()
            expect(dialog).to_contain_text('当前内容前审已通过')
            assert len(FixtureSession.calls) == 1
            assert store.load_document()['reviews']
            dialog.get_by_role('button', name='重新读取当前状态', exact=True).click()
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            expect(page.get_by_role('button', name='独立审阅当前内容', exact=True)).to_have_count(0)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert errors == []
        finally:
            browser.close()
            server.stop()
