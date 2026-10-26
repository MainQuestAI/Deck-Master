"""Public UI plus CLI: another legal clear must not strand the retained request."""
import json
import shutil
import os
from pathlib import Path
import subprocess
import sys
import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master import ui_journal as journal
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401
from test_pr189_clear_end_browser import open_panel
from test_pr189_clear_ownership_browser import click, retained

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('lost_end', [False, True])
def test_other_cli_clear_then_ui_end_refresh_download_and_replan(project, store, tmp_path, lost_end):
    save_draft(store, project); before = store.load_document(); server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('chromium-browser')); page = browser.new_page(); page.goto(server.start()+'studio/')
            panel = open_panel(page); click(panel, '生成清理计划')
            page.route('**/api/ui-state/commit-clear', lambda r:r.abort('failed'))
            click(panel, '确认清理并保留备份'); expect(panel).to_contain_text('清理结果待核实')
            a = retained(page)['request']; page.unroute('**/api/ui-state/commit-clear')
            input_path = tmp_path/'clear-input.json'; input_path.write_text(json.dumps(a['input']))
            # Explicitly use the parent's product package in the CLI subprocess,
            # including in the separate installed-wheel gate.
            import deck_master
            env = {**os.environ, 'PYTHONPATH':str(Path(deck_master.__file__).resolve().parent.parent)}
            result = subprocess.run([sys.executable, '-m', 'deck_master', 'ui', 'commit-clear',
                '--project', str(project), '--operation-id','other-cli-operation', '--input', str(input_path),
                '--plan-id',a['plan_id'], '--manifest-digest',a['manifest_digest']], env=env,
                capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stderr
            b = json.loads(result.stdout); assert b['status'] == 'cleared'
            backup = journal._clear_backup_path(store, a['manifest_digest']).read_bytes()
            log = journal._clear_log_path(store).read_bytes()
            save_draft(store, project, 'after-cli')
            click(panel, '核实原清理结果'); expect(panel).to_contain_text('同范围备份属于另一清理操作')
            expect(panel.get_by_role('button', name='结束旧操作并重新计划', exact=True)).to_be_enabled()
            if lost_end:
                def lose(route):
                    assert route.fetch().ok; route.abort('failed')
                page.route('**/api/ui-state/end-clear', lose)
            click(panel, '结束旧操作并重新计划')
            expect(panel).to_contain_text('请重新核实' if lost_end else '旧清理操作已结束')
            page.unroute('**/api/ui-state/end-clear'); page.reload(); panel = open_panel(page)
            if lost_end:
                click(panel, '核实原清理结果'); expect(panel).to_contain_text('旧清理操作已结束')
            panel.get_by_role('button', name='查看清理备份', exact=True).first.click(); dialog = page.get_by_role('dialog', name='个人状态备份', exact=True)
            for label, filename in [('下载清理备份','b.json'), ('下载旧操作恢复记录','a.json')]:
                with page.expect_download() as download: dialog.get_by_role('link', name=label, exact=True).click()
                download.value.save_as(tmp_path/filename)
            assert json.loads((tmp_path/'b.json').read_bytes()) == json.loads(backup)
            bundle = json.loads((tmp_path/'a.json').read_bytes())
            assert bundle['request'] == a and bundle['backup'] is None
            assert bundle['inspection']['backup']['related_operation']['operation_id'] == 'other-cli-operation'
            dialog.get_by_role('button', name='关闭', exact=True).click()
            panel = open_panel(page)
            click(panel, '生成清理计划'); expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
            assert [r['draft']['draft_id'] for r in journal.list_drafts(project)['records']] == ['after-cli']
            assert journal._clear_backup_path(store, a['manifest_digest']).read_bytes() == backup
            assert journal._clear_log_path(store).read_bytes() == log
            assert store.load_document() == before
            browser.close()
    finally: server.stop()
