"""Browser local recovery failures must not send or falsely acknowledge a clear."""
import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master.web import WorkbenchServer
from deck_master import ui_journal as journal
from test_ui_state_clear import project, store, save_draft  # noqa: F401
from test_pr189_clear_end_browser import open_panel
from test_pr189_clear_ownership_browser import click, retained

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('fault', ['read', 'write', 'missing_lock', 'rejected_lock'])
def test_local_preflight_failure_never_sends_new_clear(project, store, fault):
    save_draft(store, project); before = store.load_document(); server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(); page = browser.new_page(); page.goto(server.start()+'studio/')
            panel = open_panel(page); click(panel, '生成清理计划'); sent = []
            expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
            page.on('request', lambda r: sent.append(r.url) if r.url.endswith('/commit-clear') else None)
            page.evaluate('''fault => {
              if (fault === 'missing_lock') Object.defineProperty(navigator, 'locks', {value:undefined, configurable:true});
              else if (fault === 'rejected_lock') Object.defineProperty(navigator, 'locks', {value:{request:()=>Promise.reject(new Error('lock unavailable'))}, configurable:true});
              else {
                const method = fault === 'read' ? 'getItem' : 'setItem';
                const original = Storage.prototype[method];
                Storage.prototype[method] = function(key,...args) {
                  if (key.startsWith('deck-master:v3:personal-clear:')) throw new Error('injected local storage failure');
                  return original.call(this,key,...args);
                };
              }
            }''', fault)
            click(panel, '确认清理并保留备份')
            expect(panel).to_contain_text('恢复记录' if fault in ('read','missing_lock') else 'injected' if fault=='write' else 'lock unavailable')
            assert sent == []
            assert len(journal.list_drafts(project)['records']) == 1 and store.load_document() == before
            browser.close()
    finally: server.stop()


@pytest.mark.parametrize('fault', ['remove', 'end_write'])
def test_local_terminal_failure_retains_exact_request(project, store, fault):
    save_draft(store, project); server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(); page = browser.new_page(); page.goto(server.start()+'studio/')
            panel = open_panel(page); click(panel, '生成清理计划')
            page.route('**/api/ui-state/commit-clear', lambda r:r.abort('failed'))
            click(panel, '确认清理并保留备份'); expect(panel).to_contain_text('清理结果待核实')
            original = retained(page); page.unroute('**/api/ui-state/commit-clear')
            if fault == 'end_write': click(panel, '核实原清理结果'); expect(panel).to_contain_text('未发现执行证据')
            page.evaluate('''method => {
              const original = Storage.prototype[method]; window.restoreStorage = () => { Storage.prototype[method] = original; };
              Storage.prototype[method] = function(key,...args) {
                if (key.startsWith('deck-master:v3:personal-clear:')) throw new Error('injected terminal storage failure');
                return original.call(this,key,...args);
              };
            }''', 'removeItem' if fault == 'remove' else 'setItem')
            click(panel, '核实并重试原清理' if fault == 'remove' else '结束旧操作并重新计划')
            expect(panel).to_contain_text('injected terminal storage failure')
            assert retained(page) == original
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            page.evaluate('window.restoreStorage()'); page.reload(); panel = open_panel(page)
            click(panel, '核实原清理结果')
            expect(panel).to_contain_text('已清理' if fault == 'remove' else '未发现执行证据')
            browser.close()
    finally: server.stop()
