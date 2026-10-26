"""Real browser/HTTP cleanup recovery. No model or visual-quality assertions."""
import json
import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master import ui_journal
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401

pytestmark = pytest.mark.browser


def open_panel(page):
    page.get_by_role('button', name='项目菜单', exact=True).click()
    page.get_by_role('button', name='个人状态与恢复', exact=True).click()
    return page.get_by_role('dialog', name='个人状态与恢复', exact=True)


@pytest.mark.parametrize('lost_end_response', [False, True])
def test_not_sent_changed_replay_conflict_can_end_and_replan(project, store, lost_end_response, tmp_path):
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.goto(server.start() + 'studio/')
            panel = open_panel(page)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            sent = []
            def not_sent(route):
                sent.append(json.loads(route.request.post_data)); route.abort('failed')
            page.route('**/api/ui-state/commit-clear', not_sent)
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('清理结果待核实')
            save_draft(store, project, 'new-draft')
            page.unroute('**/api/ui-state/commit-clear')
            page.reload(); panel = open_panel(page)
            with page.expect_response('**/api/ui-state/commit-clear') as response:
                panel.get_by_role('button', name='核实并重试原清理', exact=True).click()
            assert response.value.status == 409
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            panel.get_by_role('button', name='核实原清理结果', exact=True).click()
            expect(panel).to_contain_text('未发现执行证据')
            if lost_end_response:
                def lost(route):
                    assert route.fetch().ok; route.abort('failed')
                page.route('**/api/ui-state/end-clear', lost)
            if lost_end_response:
                with page.expect_event('requestfailed', predicate=lambda r: r.url.endswith('/api/ui-state/end-clear')):
                    panel.get_by_role('button', name='结束旧操作并重新计划', exact=True).click()
                expect(panel).to_contain_text('请重新核实')
            else:
                panel.get_by_role('button', name='结束旧操作并重新计划', exact=True).click()
            if lost_end_response:
                page.unroute('**/api/ui-state/end-clear')
                page.reload(); panel = open_panel(page)
                panel.get_by_role('button', name='核实原清理结果', exact=True).click()
            expect(panel).to_contain_text('旧清理操作已结束')
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_enabled()
            assert ui_journal.inspect_clear(project, **sent[0])['status'] == 'ended'
            assert len(ui_journal.list_drafts(project)['records']) == 2
            with page.expect_response('**/api/ui-state/plan-clear') as planned:
                panel.get_by_role('button', name='生成清理计划', exact=True).click()
            items = planned.value.json()['items']
            assert sorted(r['id'] for r in items if r['kind'] == 'draft') == ['draft-b05', 'new-draft']
            expect(panel).to_contain_text(f'将清理 {len(items)} 项')
            assert len(ui_journal.list_drafts(project)['records']) == 2
            assert store.load_document() == before
            # The recovery download remains discoverable after the pending key is gone.
            page.reload(); panel = open_panel(page)
            panel.get_by_role('button', name='查看清理备份', exact=True).click()
            backup = page.get_by_role('dialog', name='个人状态备份', exact=True)
            with page.expect_download() as event:
                backup.get_by_role('link', name='下载旧操作恢复记录', exact=True).click()
            path = tmp_path / 'ended.json'; event.value.save_as(path)
            assert json.loads(path.read_text())['request'] == sent[0]
            browser.close()
    finally: server.stop()


def test_inspection_of_lost_success_does_not_clear_later_draft(project, store):
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(); page = browser.new_page()
            page.goto(server.start() + 'studio/'); panel = open_panel(page)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            completed = []
            def lost(route):
                response = route.fetch(); assert response.ok
                completed.append(response.json()); route.abort('failed')
            page.route('**/api/ui-state/commit-clear', lost)
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('清理结果待核实')
            save_draft(store, project, 'later')
            page.unroute('**/api/ui-state/commit-clear')
            page.reload(); panel = open_panel(page)
            panel.get_by_role('button', name='核实原清理结果', exact=True).click()
            assert [r['id'] for r in completed[0]['cleared'] if r['kind'] == 'draft'] == ['draft-b05']
            expect(panel).to_contain_text(f"已清理 {len(completed[0]['cleared'])} 项")
            assert [r['draft']['draft_id'] for r in ui_journal.list_drafts(project)['records']] == ['later']
            assert store.load_document() == before
            browser.close()
    finally: server.stop()


@pytest.mark.parametrize('fault', ['mismatched_inspection', 'end_storage_failure', 'stale_inspection'])
def test_recovery_fault_keeps_original_request(project, store, monkeypatch, fault):
    from deck_master import ui_clear_recovery
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(); page = browser.new_page()
            page.goto(server.start() + 'studio/'); panel = open_panel(page)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            page.route('**/api/ui-state/commit-clear', lambda r: r.abort('failed'))
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('清理结果待核实')
            saved = page.evaluate("Object.entries(localStorage).find(([k])=>k.startsWith('deck-master:v3:personal-clear:'))")
            if fault == 'mismatched_inspection':
                def mismatch(route):
                    response = route.fetch(); value = response.json(); value['request_digest'] = '0' * 64
                    route.fulfill(response=response, json=value)
                page.route('**/api/ui-state/inspect-clear', mismatch)
            panel.get_by_role('button', name='核实原清理结果', exact=True).click()
            if fault == 'mismatched_inspection':
                expect(panel).to_contain_text('无法与原清理请求对应')
                expect(panel.get_by_role('button', name='结束旧操作并重新计划', exact=True)).to_be_disabled()
            else:
                expect(panel).to_contain_text('未发现执行证据')
                if fault == 'end_storage_failure':
                    monkeypatch.setattr(ui_clear_recovery, 'write_json', lambda *a, **kw: (_ for _ in ()).throw(OSError('injected disk failure')))
                else:
                    save_draft(store, project, 'changed-after-inspection')
                with page.expect_response('**/api/ui-state/end-clear') as response:
                    panel.get_by_role('button', name='结束旧操作并重新计划', exact=True).click()
                assert not response.value.ok
                expect(panel).to_contain_text('请重新核实')
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            retained = json.loads(page.evaluate('(key)=>localStorage.getItem(key)', saved[0]))
            assert retained['request'] == json.loads(saved[1])['request']
            assert store.load_document() == before
            browser.close()
    finally: server.stop()
