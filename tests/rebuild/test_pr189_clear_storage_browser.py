"""Browser local recovery failures must not send or falsely acknowledge a clear."""
import shutil
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
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('chromium-browser')); page = browser.new_page(); page.goto(server.start()+'studio/')
            panel = open_panel(page); click(panel, '生成清理计划'); sent = []
            expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
            page.on('request', lambda r: sent.append(r.url) if r.url.endswith('/commit-clear') else None)
            page.evaluate('''fault => {
              if (fault === 'missing_lock') Object.defineProperty(navigator, 'locks', {value:undefined, configurable:true});
              else if (fault === 'rejected_lock') Object.defineProperty(navigator, 'locks', {value:{request:()=>Promise.reject(new Error('lock unavailable'))}, configurable:true});
              else {
                const method = fault === 'read' ? 'get' : 'put';
                const original = IDBObjectStore.prototype[method];
                IDBObjectStore.prototype[method] = function(...args) {
                  if (this.name === 'records' && this.transaction.db.name === 'deck-master:personal-clear') throw new Error('injected local storage failure');
                  return original.apply(this,args);
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
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('chromium-browser')); page = browser.new_page(); page.goto(server.start()+'studio/')
            panel = open_panel(page); click(panel, '生成清理计划')
            page.route('**/api/ui-state/commit-clear', lambda r:r.abort('failed'))
            click(panel, '确认清理并保留备份'); expect(panel).to_contain_text('清理结果待核实')
            original = retained(page); page.unroute('**/api/ui-state/commit-clear')
            if fault == 'end_write': click(panel, '核实原清理结果'); expect(panel).to_contain_text('未发现执行证据')
            page.evaluate('''fault => {
              const original = IDBObjectStore.prototype.put;
              window.restoreStorage = () => { IDBObjectStore.prototype.put = original; };
              IDBObjectStore.prototype.put = function(value,...args) {
                if (this.name === 'records' && this.transaction.db.name === 'deck-master:personal-clear' &&
                    (fault === 'remove' ? value.pending === null : Boolean(value.pending?.end_inspection_digest)))
                  throw new Error('injected terminal storage failure');
                return original.call(this,value,...args);
              };
            }''', fault)
            click(panel, '核实并重试原清理' if fault == 'remove' else '结束旧操作并重新计划')
            expect(panel).to_contain_text('injected terminal storage failure')
            assert retained(page) == original
            expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
            page.evaluate('window.restoreStorage()'); page.reload(); panel = open_panel(page)
            click(panel, '核实原清理结果')
            expect(panel).to_contain_text('已清理' if fault == 'remove' else '未发现执行证据')
            browser.close()
    finally: server.stop()


def test_two_first_attempts_serialize_only_the_local_record(project, store):
    save_draft(store, project); server = WorkbenchServer(project)
    identity = journal.list_drafts(project)['project_identity']
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('chromium-browser')); context = browser.new_context(); pages = []
            url = server.start()+'studio/'
            for _ in range(2):
                page = context.new_page(); page.goto(url); panel = open_panel(page); click(panel, '生成清理计划')
                expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
                pages.append((page, panel))
            sent = []
            def absent(route):
                sent.append(route.request.post_data_json); route.abort('failed')
            context.route('**/api/ui-state/commit-clear', absent)
            a, _ = pages[0]
            a.evaluate('''key => {
                window.held = navigator.locks.request(key, () => new Promise(resolve => {window.releaseLock = resolve;}));
            }''', 'deck-master:v3:personal-clear:'+identity)
            a.wait_for_function('typeof window.releaseLock === "function"')
            for page, panel in pages:
                with page.expect_response('**/api/project?light=1'):
                    click(panel, '确认清理并保留备份')
            assert sent == []
            a.evaluate('() => { window.releaseLock(); }')
            for page, panel in pages:
                expect(panel.get_by_role('button', name='核实原清理结果', exact=True)).to_be_enabled()
            assert len(sent) == 1
            assert retained(pages[0][0]) == retained(pages[1][0])
            assert retained(a)['request'] == sent[0]
            assert len(journal.list_drafts(project)['records']) == 1
            browser.close()
    finally: server.stop()
