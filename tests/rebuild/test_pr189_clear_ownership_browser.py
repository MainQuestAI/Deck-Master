"""Late clear responses must never release another operation's recovery request."""
import json
import time
import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master import ui_journal as journal
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401
from test_pr189_clear_end_browser import open_panel

pytestmark = pytest.mark.browser


def retained(page):
    return page.evaluate("JSON.parse(Object.entries(localStorage).find(([k])=>k.startsWith('deck-master:v3:personal-clear:'))?.[1] || 'null')")


def click(panel, name):
    panel.get_by_role('button', name=name, exact=True).click()


def lose_success(route):
    assert route.fetch().ok
    route.abort('failed')


@pytest.mark.parametrize('late', ['first_conflict', 'commit_success', 'inspect_success', 'inspect_pending', 'end_success'])
def test_late_response_preserves_next_operation_and_refresh_recovery(project, store, late):
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            context = browser.new_context()
            a = context.new_page(); a.goto(server.start()+'studio/'); pa = open_panel(a)
            click(pa, '生成清理计划')
            expect(pa.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
            held = []
            def delay(route):
                response = route.fetch()
                assert response.status == (409 if late == 'first_conflict' else 200)
                held.append((route, response))
            if late in ('first_conflict', 'commit_success'):
                if late == 'first_conflict': save_draft(store, project, 'changed')
                a.route('**/api/ui-state/commit-clear', delay)
                click(pa, '确认清理并保留备份')
            else:
                a.route('**/api/ui-state/commit-clear', lose_success if late == 'inspect_success' else lambda r:r.abort('failed'))
                click(pa, '确认清理并保留备份')
                expect(pa).to_contain_text('清理结果待核实')
                a.unroute('**/api/ui-state/commit-clear')
                if late == 'end_success':
                    click(pa, '核实原清理结果'); expect(pa).to_contain_text('未发现执行证据')
                    a.route('**/api/ui-state/end-clear', delay); click(pa, '结束旧操作并重新计划')
                else:
                    a.route('**/api/ui-state/inspect-clear', delay); click(pa, '核实原清理结果')
            deadline = time.monotonic() + 5
            while not held and time.monotonic() < deadline:
                a.wait_for_timeout(10)
            assert held
            original = retained(a)['request']
            b = context.new_page(); b.goto(server.start()+'studio/'); pb = open_panel(b)
            click(pb, '核实原清理结果')
            if late in ('first_conflict', 'inspect_pending'):
                expect(pb).to_contain_text('未发现执行证据'); click(pb, '结束旧操作并重新计划')
                expect(pb).to_contain_text('旧清理操作已结束')
            else:
                expect(pb).to_contain_text('旧清理操作已结束' if late == 'end_success' else '已清理')
            save_draft(store, project, 'b-new')
            click(pb, '生成清理计划')
            b.route('**/api/ui-state/commit-clear', lose_success)
            click(pb, '确认清理并保留备份'); expect(pb).to_contain_text('清理结果待核实')
            newer = retained(b)
            assert newer['request']['operation_id'] != original['operation_id']
            save_draft(store, project, 'after-b')
            route, response = held[0]; route.fulfill(response=response)
            expect(pa.get_by_role('button', name='核实原清理结果', exact=True)).to_be_enabled()
            assert retained(a) == newer
            expect(pa.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            b.unroute('**/api/ui-state/commit-clear'); b.reload(); pb = open_panel(b)
            click(pb, '核实原清理结果'); expect(pb).to_contain_text('已清理')
            assert retained(b) is None
            assert journal.inspect_clear(project, **newer['request'])['status'] == 'cleared'
            assert [r['draft']['draft_id'] for r in journal.list_drafts(project)['records']] == ['after-b']
            assert store.load_document() == before
            browser.close()
    finally:
        server.stop()


def test_late_first_refusal_preserves_new_end_confirmation_for_same_request(project, store):
    save_draft(store, project); server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(); context = browser.new_context(); a = context.new_page()
            url = server.start()+'studio/'; a.goto(url); pa = open_panel(a); click(pa, '生成清理计划')
            expect(pa.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
            save_draft(store, project, 'changed'); held = []
            def hold(route): held.append((route, route.fetch()))
            a.route('**/api/ui-state/commit-clear', hold); click(pa, '确认清理并保留备份')
            deadline = time.monotonic()+5
            while not held and time.monotonic()<deadline: a.wait_for_timeout(10)
            assert held[0][1].status == 409
            b = context.new_page(); b.goto(url); pb = open_panel(b); click(pb, '核实原清理结果')
            expect(pb).to_contain_text('未发现执行证据')
            b.route('**/api/ui-state/end-clear', hold); click(pb, '结束旧操作并重新计划')
            deadline = time.monotonic()+5
            while len(held)<2 and time.monotonic()<deadline: b.wait_for_timeout(10)
            assert len(held)==2 and held[1][1].ok
            saved = retained(b); assert saved['end_inspection_digest']
            held[0][0].fulfill(response=held[0][1])
            expect(pa.get_by_role('button', name='核实原清理结果', exact=True)).to_be_enabled()
            assert retained(a) == saved
            held[1][0].fulfill(response=held[1][1]); expect(pb).to_contain_text('旧清理操作已结束')
            assert retained(b) is None
            browser.close()
    finally: server.stop()
