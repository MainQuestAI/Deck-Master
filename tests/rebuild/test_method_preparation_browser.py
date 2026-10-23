"""RP-18 actual Chromium clipboard -> preview -> installed resource reader."""
import json
import shutil
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright, expect
from deck_master import ui_journal, method_library_view as lib, method_resources
from deck_master.web import WorkbenchServer
from test_webui_content_insight import candidate

pytestmark = pytest.mark.browser


@pytest.mark.parametrize(('role', 'phase', 'units', 'instruction'), [
    ('deck-review', 'speech', ['speech'], '只审阅口播，不修复'),
    ('deck-master', 'argument', [], '请先写逐页正文，再设计两页样页'),
])
@pytest.mark.parametrize('route', ['studio/','v2/'])
def test_speech_clipboard_and_no_phase_catalog(tmp_path, route, role, phase, units, instruction):
    project, store, _, _ = candidate(tmp_path)
    before = store.load_document()
    server = WorkbenchServer(project)
    url = server.start()
    info = ui_journal.project_info(project)
    link = url+route+'#'+urlencode({'project':info['project_identity'],'surface':'content',
        'layer':'content','revision':store.current_revision_id(),'content_area':'methods'})
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
            context = browser.new_context(permissions=['clipboard-read','clipboard-write'],viewport={'width':1280,'height':800})
            page = context.new_page()
            errors, sent = [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: sent.append(r.post_data_json) if r.method=='POST' and r.url.endswith('/method-library/preview') else None)
            try:
                page.goto(link)
                if route == 'studio/':
                    page.get_by_role('button',name='方法与案例',exact=True).click()
                area = page.get_by_role('heading',name='方法与案例准备',exact=True).locator('..')
                expect(area).to_contain_text('当前没有可准备的新阶段')
                expect(page.locator('label.method-entry')).to_have_count(len(lib.catalog()[1]))
                # Method selection remains forbidden here; catalogue reading does not.
                entry = page.locator('label.method-entry').filter(has=page.get_by_role('button',name='浏览 content-to-visual',exact=True))
                expect(entry.locator('input')).to_be_disabled()
                entry.get_by_role('button',name='浏览 content-to-visual',exact=True).click()
                expect(area.locator(':scope > pre')).to_contain_text('内容到设计')
                expect(page.get_by_role('button',name='重新核对后复制准备要求')).to_be_disabled()
                page.get_by_label('准备上下文').select_option('independent')
                page.get_by_label('方法阅读角色').select_option(role)
                page.get_by_label('方法阅读阶段').select_option(phase)
                expect(page.get_by_role('button',name='重新核对后复制准备要求')).to_be_enabled()
                # Exercise a slow clipboard provider while still writing/reading
                # Chromium's real clipboard, not a fixture receipt.
                page.evaluate("""async () => {
                    await navigator.clipboard.writeText('');
                    const write = navigator.clipboard.writeText.bind(navigator.clipboard);
                    navigator.clipboard.writeText = async text => {
                        await new Promise(resolve => setTimeout(resolve, 750));
                        return write(text);
                    };
                }""")
                page.get_by_role('button',name='重新核对后复制准备要求').click()
                # copyText announces success only after the real write resolves.
                # wait_for_function treats a Promise as truthy before its boolean
                # resolves, so an async clipboard predicate does not poll.
                expect(page.get_by_text('已复制，尚未开始。请在制作工具中发送。', exact=True)).to_be_visible()
                copied = page.evaluate('navigator.clipboard.readText()')
                assert 'method_preparation_handoff.v1' in copied
                packet = json.loads(copied.split('```json\n')[1].split('\n```')[0])
                assert sent[-1]['context']['review_units'] == units
                assert packet['effective_context']['role'] == role
                assert packet['effective_context']['phase'] == phase
                assert packet['effective_context']['review_units'] == units
                recovered = lib.preview(project,packet['preview_request'])
                assert recovered['preview_digest'] == packet['preview_digest']
                reader = method_resources.read_skill_methods(role, entry_mode='natural',
                    project=project, text=instruction, review_units=units if role=='deck-review' else None)
                assert reader['skill'] == role
                assert [(r['id'], r['sha256']) for r in reader['methods']] == [
                    (r['id'], r['sha256']) for r in recovered['resolved_manifest']]
                for r in recovered['resolved_manifest']:
                    body = lib.resource(r['id'],catalog_digest=recovered['catalog_digest'],sha256=r['sha256'])
                    assert body['content'] and body['sha256'] == r['sha256']
                page.screenshot(path=str(tmp_path/'methods.png'),full_page=True)
                assert store.load_document() == before and not errors
            finally:
                browser.close()
    finally:
        server.stop()
