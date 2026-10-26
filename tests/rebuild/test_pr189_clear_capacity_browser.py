"""R1 full HTTP/Chromium recovery with an accepted near-limit backup."""
import json
import shutil
from pathlib import Path
import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master import ui_journal as j
from deck_master.local_state import MAX_BODY
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store  # noqa: F401
from test_pr189_clear_capacity import large_request
from test_pr189_clear_end_browser import open_panel

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('lost_response', [False, True])
def test_large_interrupted_clear_ends_refreshes_downloads_and_replans(project, store, monkeypatch, tmp_path, lost_response):
    large_request(project, store, size=MAX_BODY-800, chinese=True)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('chromium-browser'))
            page = browser.new_page(accept_downloads=True)
            page.goto(server.start()+'studio/')
            panel = open_panel(page)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            unlink = Path.unlink
            def fail(path, *args, **kwargs):
                if path == j._draft_path(store, 'draft-001'): raise OSError('capacity interruption')
                return unlink(path, *args, **kwargs)
            with monkeypatch.context() as patch:
                patch.setattr(Path, 'unlink', fail)
                with page.expect_response('**/api/ui-state/commit-clear') as response:
                    panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
                req = json.loads(response.value.request.post_data)
                assert not response.value.ok
            expect(panel).to_contain_text('清理结果待核实')
            assert MAX_BODY-1500 < j._clear_backup_path(store, req['manifest_digest']).stat().st_size <= MAX_BODY
            with page.expect_response('**/api/ui-state/commit-clear') as replay:
                panel.get_by_role('button', name='核实并重试原清理', exact=True).click()
            assert replay.value.status == 409
            panel.get_by_role('button', name='核实原清理结果', exact=True).click()
            end = panel.get_by_role('button', name='结束旧操作并重新计划', exact=True)
            expect(end).to_be_enabled()
            if lost_response:
                def lose(route):
                    assert route.fetch().ok
                    route.abort('failed')
                page.route('**/api/ui-state/end-clear', lose)
                with page.expect_event('requestfailed', predicate=lambda r:r.url.endswith('/api/ui-state/end-clear')):
                    end.click()
                expect(panel).to_contain_text('请重新核实')
                page.unroute('**/api/ui-state/end-clear')
            else:
                end.click(); expect(panel).to_contain_text('旧清理操作已结束')
            page.reload(); panel = open_panel(page)
            if lost_response:
                panel.get_by_role('button', name='核实原清理结果', exact=True).click()
                expect(panel).to_contain_text('旧清理操作已结束')
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_enabled()
            panel.get_by_role('button', name='查看清理备份', exact=True).first.click()
            backup = page.get_by_role('dialog', name='个人状态备份', exact=True)
            with page.expect_download() as event:
                backup.get_by_role('link', name='下载旧操作恢复记录', exact=True).click()
            target = tmp_path/'recovery.json'; event.value.save_as(target)
            value = json.loads(target.read_text())
            assert target.stat().st_size > MAX_BODY
            assert value['request'] == req and len(value['backup']['records']) >= 2
            page.reload(); panel = open_panel(page)
            with page.expect_response('**/api/ui-state/plan-clear') as fresh:
                panel.get_by_role('button', name='生成清理计划', exact=True).click()
            assert [r['id'] for r in fresh.value.json()['items'] if r['kind']=='draft'] == ['draft-001']
            expect(panel).to_contain_text('将清理')
            assert store.load_document() == before
            assert len(j.list_drafts(project)['records']) == 1
            browser.close()
    finally:
        server.stop()
