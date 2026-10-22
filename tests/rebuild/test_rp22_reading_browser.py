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


@pytest.mark.parametrize('route', ['studio', 'v2'])
def test_single_verify_survives_deferred_fixed_read(candidate_store, tmp_path, route):
    store = candidate_store
    task = dispatch(store, page='p02')
    other = dispatch(store, page='p01')
    revision = store.load_document()['revision_id']
    server = WorkbenchServer(store.project_root)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page()
            url = server.start()
            identity = page.request.get(url+'api/project').json()['project_identity']
            target = url+route+'/#'+urlencode(dict(project=identity, surface='runs', task=task['task_id'], revision=revision))
            page.goto(target)
            expect(page.locator('.run-detail')).to_contain_text('尚无接手记录')
            expect(page.get_by_role('button', name='核实最新执行状态', exact=True)).to_be_enabled()
            start(store, task)
            latest = store.load_document()['revision_id']
            page.reload()
            expect(page.locator('.run-detail')).to_contain_text('尚无接手记录')
            expect(page.get_by_role('button', name='核实最新执行状态', exact=True)).to_be_enabled()
            held = []
            def hold_fixed(request):
                response = request.fetch()
                held.append((request, response))
            pattern = '**/api/tasks/'+task['task_id']+'?revision=*'
            page.route(pattern, hold_fixed)
            page.evaluate("document.querySelector('#app').dispatchEvent(new Event('draft-editor-replaced'))")
            # Wait on the request itself, not on arbitrary timing or polling cadence.
            for _ in range(100):
                if held: break
                page.wait_for_timeout(10)
            assert len(held) == 1
            page.get_by_role('button', name='核实原任务', exact=True).click()
            expect(page.locator('.run-detail')).to_contain_text('synthetic-test-host')
            held[0][0].fulfill(response=held[0][1])
            expect(page.get_by_role('button', name='核实最新执行状态', exact=True)).to_be_enabled()
            expect(page.locator('.run-detail')).to_contain_text('synthetic-test-host')
            assert revision in page.url  # Single verification does not change historical navigation.
            expect(page.locator('.task-verified-revision')).to_have_text('已核实原任务的当前执行状态 · R '+latest[:8])
            expect(page.get_by_role('button', name='取消原任务', exact=True)).to_be_disabled()
            page.unroute(pattern, hold_fixed)
            # A later background fixed-list read must keep the explicit current detail.
            with page.expect_response(lambda response: response.url == url+'api/tasks/'+task['task_id']) as refreshed:
                page.evaluate("document.querySelector('#app').dispatchEvent(new Event('draft-editor-replaced'))")
            refreshed.value.finished()
            expect(page.get_by_role('button', name='核实最新执行状态', exact=True)).to_be_enabled()
            expect(page.locator('.run-detail')).to_contain_text('synthetic-test-host')
            # A late verification from a disposed task must not replace the new selection.
            pending = []
            def hold_latest(request):
                pending.append((request, request.fetch()))
            page.route('**/api/tasks/'+task['task_id'], hold_latest)
            page.get_by_role('button', name='核实原任务', exact=True).click()
            for _ in range(100):
                if pending: break
                page.wait_for_timeout(10)
            assert len(pending) == 1
            page.evaluate('(hash)=>location.hash=hash', urlencode(dict(project=identity, surface='runs', task=other['task_id'], revision=revision)))
            expect(page.locator('.run-detail')).to_contain_text(other['task_id'])
            with page.expect_response(lambda response: response.url == url+'api/tasks/'+task['task_id']) as released:
                pending[0][0].fulfill(response=pending[0][1])
            released.value.finished()
            page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            expect(page.locator('.run-detail')).to_contain_text(other['task_id'])
            expect(page.locator('.run-detail')).not_to_contain_text('synthetic-test-host')
            browser.close()
    finally:
        server.stop()
