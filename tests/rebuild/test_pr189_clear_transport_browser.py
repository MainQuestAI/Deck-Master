"""Real HTTP clear with deliberately lost transport; no business mutations."""
import json
import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import ui_journal
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('transport', ['lost_response', 'not_sent', 'malformed_response'])
def test_clear_unknown_survives_refresh_and_replays_exact_request(project, store, transport):
    sent = transport != 'not_sent'
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    requests = []
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.goto(server.start() + 'studio/')
            def panel():
                page.get_by_role('button', name='项目菜单', exact=True).click()
                page.get_by_role('button', name='个人状态与恢复', exact=True).click()
                return page.get_by_role('dialog', name='个人状态与恢复', exact=True)
            current = panel()
            current.get_by_role('button', name='生成清理计划', exact=True).click()
            def lose_response(route):
                requests.append(json.loads(route.request.post_data))
                if sent:
                    assert route.fetch().ok
                if transport == 'malformed_response':
                    route.fulfill(status=200, content_type='application/json', body='{invalid')
                else:
                    route.abort('failed')
            page.route('**/api/ui-state/commit-clear', lose_response)
            current.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(current).to_contain_text('清理结果待核实')
            assert '未清理任何对象' not in current.inner_text()
            expect(current.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            if sent:
                save_draft(store, project, 'after-clear', text='must survive replay')
            page.unroute('**/api/ui-state/commit-clear')
            page.on('request', lambda r: requests.append(json.loads(r.post_data))
                    if '/api/ui-state/commit-clear' in r.url else None)
            page.reload()
            current = panel()
            expect(current).to_contain_text('清理结果待核实')
            current.get_by_role('button', name='核实并重试原清理', exact=True).click()
            expect(current).to_contain_text('已清理')
            assert len(requests) == 2 and requests[0] == requests[1]
            assert [r['draft']['draft_id'] for r in ui_journal.list_drafts(project)['records']] == (['after-clear'] if sent else [])
            assert store.load_document() == before
            assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('deck-master:v3:personal-clear:')).length") == 0
            browser.close()
    finally:
        server.stop()


def test_first_clear_cas_refusal_keeps_all_drafts_and_allows_replanning(project, store):
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.goto(server.start() + 'studio/')
            page.get_by_role('button', name='项目菜单', exact=True).click()
            page.get_by_role('button', name='个人状态与恢复', exact=True).click()
            panel = page.get_by_role('dialog', name='个人状态与恢复', exact=True)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
            save_draft(store, project, 'changed-after-plan')
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('本次清理被拒绝')
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_enabled()
            assert len(ui_journal.list_drafts(project)['records']) == 2
            assert store.load_document() == before
            assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('deck-master:v3:personal-clear:')).length") == 0
            browser.close()
    finally:
        server.stop()
