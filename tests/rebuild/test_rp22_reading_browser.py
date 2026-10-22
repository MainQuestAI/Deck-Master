"""RP22 mounted views and real clipboard; synthetic core data, no model calls."""
import shutil
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import changes, tasks
from deck_master.web import WorkbenchServer
from test_candidates import store as candidate_store, dispatch, start
from test_rp08_current_actions import mixed

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('route', ['studio', 'v2'])
@pytest.mark.parametrize('size', [(1280,800), (1440,900), (1024,800)])
def test_mixed_overview_long_prompt_and_handoff(candidate_store, tmp_path, route, size):
    store = candidate_store
    task = dispatch(store, page='p02')
    mixed(store)
    before = store.load_document()
    group = next(store.read_object_json(ref) for ref in before['changes']
                 if task['task_id'] in store.read_object_json(ref)['task_ids'])
    expected = changes.handoff(store.project_root, change_id=group['change_id'])
    server = WorkbenchServer(store.project_root)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            context = browser.new_context(viewport={'width':size[0], 'height':size[1]}, permissions=['clipboard-read','clipboard-write'])
            page = context.new_page(); errors = []; writes = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' else None)
            url = server.start()
            identity = page.request.get(url+'api/project').json()['project_identity']
            def go(**state):
                page.goto(url+route+'/#'+urlencode({'project':identity, **state}))
            go(surface='overview')
            expect(page.locator('.todo-priority')).to_be_visible()
            expect(page.locator('.todo-more')).not_to_have_attribute('open', '')
            cta = page.locator('.todo-priority button.primary')
            assert cta.evaluate('e=>getComputedStyle(e).backgroundColor') in ['rgb(23, 23, 23)', 'rgb(32, 38, 46)']
            assert page.locator('.todo-priority').evaluate('e=>getComputedStyle(e).backgroundColor') != 'rgb(13, 13, 13)'
            assert cta.bounding_box()['y'] + cta.bounding_box()['height'] < size[1]
            matrix = page.get_by_role('table', name='逐页制作进展')
            page.screenshot(path=str(tmp_path/f'{route}-{size[0]}-viewport.png'))
            assert matrix.bounding_box()['y'] < size[1]
            assert matrix.locator('tbody tr:not(.chapter-row)').first.bounding_box()['y'] + 44 < size[1]
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/f'{route}-{size[0]}-overview.png'), full_page=True)
            if size[0] <= 1100:
                page.locator('.todo-secondary > summary').click()
            more = page.locator('.todo-more > summary'); more.focus(); page.keyboard.press('Enter')
            expect(page.get_by_role('heading', name='3 个任务 · 失败待查看', exact=True)).to_be_visible()
            go(surface='page', page='p01', layer='prepared_prompt', revision=before['revision_id'])
            text = page.locator('.page-reading .selectable-text').first
            expect(text).to_be_visible()
            assert len(text.inner_text()) > 1000
            expect(page.locator('.opinion-composer')).not_to_have_attribute('open', '')
            expect(page.get_by_label('意见正文', exact=True)).to_be_hidden()
            geometry = text.evaluate('e=>({scroll:e.scrollHeight,client:e.clientHeight,overflow:getComputedStyle(e).overflowY})')
            assert geometry['overflow'] == 'visible' and geometry['scroll'] <= geometry['client'] + 1
            text.focus(); page.keyboard.press('End')
            assert before['revision_id'] in page.url
            page.screenshot(path=str(tmp_path/f'{route}-{size[0]}-prompt.png'))
            go(surface='runs', task=task['task_id'])
            copy = page.get_by_role('button', name='复制交接说明', exact=True)
            expect(copy).to_be_enabled()
            command = page.get_by_label('读取本次交接的实际命令')
            expect(command).to_have_text(expected['handoff']['read_command'])
            copy.click()
            assert page.evaluate('navigator.clipboard.readText()') == expected['text']
            expect(page.locator('.task-handoff')).to_contain_text('复制不会启动制作')
            assert tasks._lookup_task(store.load_document(), task['task_id'], store)['status'] == 'awaiting_host'
            assert store.load_document() == before
            assert all(url.endswith('/api/ui-state') for url in writes)  # only navigation preferences
            # A local synthetic claim tests the subsequent factual refresh,
            # not a real Host session or image/model production.
            start(store, task)
            page.reload()
            expect(page.get_by_role('button', name='复制交接说明', exact=True)).to_have_count(0)
            expect(page.locator('.run-detail')).to_contain_text('尚无接手记录')
            page.get_by_role('button', name='核实最新执行状态', exact=True).click()
            expect(page.locator('.run-detail')).to_contain_text('synthetic-test-host')
            assert not errors
            browser.close()
    finally:
        server.stop()
