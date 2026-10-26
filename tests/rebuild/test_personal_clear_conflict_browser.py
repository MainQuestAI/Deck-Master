"""Regression: QA-001 — clear conflicts must not claim a draft-save conflict.
Found by /qa on 2026-10-26. Report: output/pr189-capacity/qa/qa-report.md.
Value: protects=uncertain-clear recovery guidance; fails_when=draft conflict copy is reused;
why_new=prior recovery tests checked pending/fences but not the stated cause;
seam=none; no_claim=filesystem faults beyond synthetic fixtures.
"""
import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401
from test_pr189_clear_end_browser import open_panel

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('action', ['commit', 'end'])
def test_clear_conflict_directs_to_original_result_inspection(project, store, action):
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(); page = browser.new_page()
            page.goto(server.start()+'studio/'); panel = open_panel(page)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            page.route('**/api/ui-state/commit-clear', lambda route: route.abort('failed'))
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('清理结果待核实')
            page.unroute('**/api/ui-state/commit-clear')
            if action == 'end':
                panel.get_by_role('button', name='核实原清理结果', exact=True).click()
                expect(panel).to_contain_text('未发现执行证据')
            save_draft(store, project, 'later')
            with page.expect_response(f'**/api/ui-state/{action}-clear') as response:
                panel.get_by_role('button', name='核实并重试原清理' if action=='commit' else '结束旧操作并重新计划', exact=True).click()
            assert response.value.status == 409
            expect(panel).to_contain_text('请先核实原清理结果')
            expect(panel).not_to_contain_text('另一个窗口已保存不同内容')
            expect(panel).not_to_contain_text('比较两稿')
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            panel.get_by_role('button', name='核实原清理结果', exact=True).click()
            expect(panel).to_contain_text('未发现执行证据')
            panel.get_by_role('button', name='结束旧操作并重新计划', exact=True).click()
            expect(panel).to_contain_text('旧清理操作已结束')
            assert store.load_document() == before
            browser.close()
    finally: server.stop()
