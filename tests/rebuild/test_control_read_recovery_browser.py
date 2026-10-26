"""Explicit recovery replaces a stalled read without retrying writes."""
import shutil

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_pr189_clear_ownership_browser import retained
from test_ui_state_clear import save_draft

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('late_response', [False, True])
def test_verified_recovery_does_not_wait_for_old_control_get(tmp_path, late_response):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    before = store.load_document()
    save_draft(store, project)
    server = WorkbenchServer(project)
    held, writes, errors = [], [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'))
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.start() + 'studio/')
            expect(page.locator('#view-title')).to_be_visible()
            title = page.locator('#view-title').inner_text()
            page.get_by_role('button', name='项目菜单', exact=True).click()
            page.get_by_role('button', name='个人状态与恢复', exact=True).click()
            panel = page.get_by_role('dialog', name='个人状态与恢复', exact=True)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            attempted = []

            def unknown_write(route):
                attempted.append(route.request.post_data)
                route.abort('failed')

            page.route('**/api/ui-state/commit-clear', unknown_write)
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('清理结果待核实')
            pending = retained(page)
            assert pending is not None and len(attempted) == 1
            panel.get_by_role('button', name='关闭', exact=True).click()

            def control(route):
                if not held:
                    held.append((route, route.fetch().json()))
                else:
                    route.continue_()

            page.route('**/api/project?light=1', control)
            page.on('request', lambda request: writes.append(request.url)
                    if request.method == 'POST' and '/api/ui-state' not in request.url else None)
            page.get_by_role('navigation', name='项目工作区').get_by_role('button', name='内容与页序', exact=True).click()
            expect(page.locator('#main')).to_have_attribute('aria-busy', 'true')
            page.get_by_role('button', name='连接状态', exact=True).click()
            dialog = page.get_by_role('dialog')
            expect(dialog.get_by_role('status')).to_contain_text('已连接')
            dialog.get_by_role('button', name='重新读取当前工作面').click()
            # The held first GET has not been released. No timeout or retry of
            # that request is needed for this explicit, fresh read to finish.
            expect(page.locator('#main')).not_to_have_attribute('aria-busy', 'true')
            expect(page.locator('#view-title')).to_have_text(title)
            assert len(held) == 1
            if late_response:
                held[0][0].fulfill(json=held[0][1])
                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                expect(page.locator('#view-title')).to_have_text(title)
                expect(page.locator('#main')).not_to_have_attribute('aria-busy', 'true')
            assert not writes
            assert len(attempted) == 1 and retained(page) == pending
            assert not errors
            assert store.load_document() == before
            browser.close()
    finally:
        server.stop()


def test_replaced_control_request_cannot_clear_new_single_flight_owner(tmp_path):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'))
            page = browser.new_page()
            page.goto(server.start() + 'v2/project.js')
            result = page.evaluate('''async () => {
              const {Project} = await import('/v2/project.js');
              const app = {health:{ui_capabilities:[]}};
              const calls=[]; const original=fetch;
              window.fetch=(url, options)=>new Promise((resolve,reject)=>calls.push({resolve,reject,signal:options.signal}));
              try {
                const old=Project.prototype.readControl.call(app).catch(error=>error.name);
                const fresh=Project.prototype.readControl.call(app,true);
                const aborted=calls[0].signal.aborted;
                calls[0].reject(new DOMException('cancelled','AbortError'));
                await old;
                const passive=Project.prototype.readControl.call(app);
                const count=calls.length;
                calls[1].resolve(new Response(JSON.stringify({revision:'fresh'}),{status:200}));
                return {aborted,count,fresh:await fresh,passive:await passive};
              } finally {window.fetch=original;}
            }''')
            assert result == {'aborted': True, 'count': 2,
                              'fresh': {'revision': 'fresh'}, 'passive': {'revision': 'fresh'}}
            browser.close()
    finally:
        server.stop()
