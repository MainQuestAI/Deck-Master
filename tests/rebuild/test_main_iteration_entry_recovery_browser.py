"""Real role imports and launcher recovery, without changing module URLs."""
from contextlib import contextmanager
import threading

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import local_runtime, service
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@contextmanager
def entries(tmp_path):
    source = tmp_path / 'brief.md'; source.write_text('# synthetic entry recovery')
    project = tmp_path / 'project'
    service.create(project, brief='synthetic', audience='synthetic', sources=[source], project_format='workbench.v3')
    project_server = WorkbenchServer(project)
    launcher, state = local_runtime.bind_server(local_runtime.descriptor(registry=tmp_path / 'registry.json'))
    worker = threading.Thread(target=launcher.serve_forever, daemon=True); worker.start()
    try:
        yield {'project': project_server.start(), 'launcher': state['url'], 'external_review': state['url']}
    finally:
        project_server.stop(); launcher.shutdown(); launcher.server_close(); worker.join(timeout=2)


@pytest.mark.parametrize('entry', ['project', 'launcher', 'external_review'])
@pytest.mark.parametrize('failure', ['404', 'offline', 'dependency'])
def test_entry_module_recovers_with_product_reload(tmp_path, entry, failure):
    module = {'project': 'project.js', 'launcher': 'launcher-ui.js', 'external_review': 'collaboration-desk.js'}[entry]
    with entries(tmp_path) as urls, sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page()
        url = urls[entry]; pattern = '**/v2/' + module
        original = page.request.get(url + 'v2/' + module).text()
        modules, documents, writes, errors = [], [], [], []
        page.on('request', lambda request: modules.append(request.url) if request.url.endswith('/v2/' + module) else None)
        page.on('request', lambda request: documents.append(request.url) if request.is_navigation_request() else None)
        page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        def faulty(route):
            if failure == '404': route.fulfill(status=404, body='missing module')
            elif failure == 'offline': route.abort('internetdisconnected')
            else: route.fulfill(content_type='text/javascript', body=original + "\nimport './entry-recovery-probe.js';")
        page.route(pattern, faulty)
        page.route('**/v2/entry-recovery-probe.js', lambda route: route.fulfill(content_type='text/javascript', body='throw new Error("dependency failed");'))
        page.goto(url + 'studio/')
        if entry == 'external_review': page.get_by_role('button', name='只读审阅稿件', exact=True).click()
        reload = page.get_by_role('button', name='重新加载工作台', exact=True)
        expect(reload).to_be_visible()
        if entry == 'external_review':
            page.get_by_role('button', name='刷新项目列表', exact=True).click()
            expect(reload).to_be_visible()
        if failure == 'offline':
            page.context.set_offline(True); page.wait_for_function('navigator.onLine === false')
            page.context.set_offline(False); page.wait_for_function('navigator.onLine === true')
            expect(reload).to_be_visible()
        page.unroute(pattern, faulty)
        assert page.request.get(url + 'v2/' + module).status == 200
        previous_modules, previous_documents = len(modules), len(documents)
        with page.expect_request(pattern): reload.click()
        if entry == 'project': expect(page.locator('#view-title')).to_be_visible()
        elif entry == 'launcher': expect(page.get_by_role('button', name='新建项目', exact=True)).to_be_visible()
        else:
            dialog = page.get_by_role('dialog', name='只读审阅稿件', exact=True)
            expect(dialog).to_be_visible()
            expect(dialog.get_by_label('源文件或项目位置（必填）', exact=True)).to_have_value('')
            assert 'launcher_action' not in page.url
            dialog.get_by_role('button', name='关闭', exact=True).click()
            page.reload()
            expect(page.get_by_role('button', name='只读审阅稿件', exact=True)).to_be_visible()
            expect(dialog).not_to_be_visible()
        assert len(modules) > previous_modules and len(documents) > previous_documents
        assert not any('/api/projects/' in value or '/api/collaboration/' in value or '/api/drafts/save' in value for value in writes)
        assert errors == []
        browser.close()


def test_launcher_module_reload_preserves_protected_and_queued_forms(tmp_path):
    with entries(tmp_path) as urls, sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page(); page.goto(urls['launcher'] + 'studio/')
        page.get_by_role('button', name='新建项目', exact=True).click()
        page.get_by_label('项目名称（必填）', exact=True).fill('retain this form')
        page.route('**/v2/collaboration-desk.js', lambda route: route.fulfill(status=404, body='missing'))
        # Native modality prevents an ordinary click. A stale asynchronous entry
        # must still be unable to reload either the active or a queued form.
        page.evaluate("""() => [...document.querySelectorAll('button')].find(b=>b.textContent==='只读审阅稿件').click()""")
        expect(page.get_by_role('button', name='重新加载工作台', exact=True)).to_be_visible()
        page.evaluate("""async () => {const {modal,el}=await import('/v2/dom.js');
          window.queuedForm=modal('排队输入',el('input',{value:'queued retained'}),[],{protectDraft:true});
          window.reloadControl=[...document.querySelectorAll('button')].find(b=>b.textContent==='重新加载工作台');
          window.documentMarker=crypto.randomUUID();reloadControl.click();}""")
        assert page.evaluate("() => !!window.documentMarker && queuedForm.isConnected && !queuedForm.open")
        expect(page.get_by_label('项目名称（必填）', exact=True)).to_have_value('retain this form')
        assert 'launcher_action' not in page.url
        page.get_by_role('dialog', name='新建项目', exact=True).get_by_role('button', name='关闭', exact=True).click()
        expect(page.get_by_role('dialog', name='排队输入', exact=True)).to_be_visible()
        page.evaluate('() => reloadControl.click()')
        expect(page.get_by_role('dialog', name='排队输入', exact=True).locator('input')).to_have_value('queued retained')
        assert page.evaluate('() => !!window.documentMarker')
        browser.close()


def test_launcher_old_failure_control_expires_when_another_form_opens(tmp_path):
    with entries(tmp_path) as urls, sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page(); page.goto(urls['launcher'] + 'studio/')
        page.route('**/v2/collaboration-desk.js', lambda route: route.fulfill(status=404, body='missing'))
        page.get_by_role('button', name='只读审阅稿件', exact=True).click()
        expect(page.get_by_role('button', name='重新加载工作台', exact=True)).to_be_visible()
        page.evaluate("() => {window.oldReload=[...document.querySelectorAll('button')].find(b=>b.textContent==='重新加载工作台');window.documentMarker='same';}")
        page.get_by_role('button', name='新建项目', exact=True).click()
        page.get_by_label('项目名称（必填）', exact=True).fill('new target')
        page.get_by_role('dialog', name='新建项目', exact=True).get_by_role('button', name='关闭', exact=True).click()
        page.evaluate('() => oldReload.click()')
        expect(page.get_by_role('button', name='新建项目', exact=True)).to_be_visible()
        assert page.evaluate('() => window.documentMarker') == 'same'
        browser.close()


@pytest.mark.parametrize('entry,path', [('project', '/api/health'), ('launcher', '/api/health'), ('project', '/api/project?light=1')])
def test_ordinary_entry_reads_retry_without_reloading_the_document(tmp_path, entry, path):
    with entries(tmp_path) as urls, sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page(); pattern = '**' + path
        page.route(pattern, lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":{"message":"read unavailable"}}'))
        page.goto(urls[entry] + 'studio/')
        retry = page.get_by_role('button', name='重新连接', exact=True); expect(retry).to_be_visible()
        expect(page.get_by_role('button', name='重新加载工作台', exact=True)).to_have_count(0)
        page.evaluate("() => {window.documentMarker='same';}"); page.unroute(pattern)
        with page.expect_request(pattern): retry.click()
        expect(page.locator('#view-title')).to_be_visible()
        assert page.evaluate('() => window.documentMarker') == 'same'
        browser.close()
