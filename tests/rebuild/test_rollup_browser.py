"""PR96 browser regressions against real loopback project state."""
import copy
from urllib.parse import urlencode

import pytest

from deck_master import icons, result_reading
from test_action_targets_browser import action_browser
from test_icon_browser import icon_browser
from test_icon_quality import icon_store, confirm, dispatch
from test_workbench_actions import commit, synthetic_task

pytestmark = pytest.mark.browser


def _reading_tasks(store):
    from deck_master.pipeline import artifact
    doc = copy.deepcopy(store.load_document())
    doc['tasks'] = []
    for entry in doc['pages']:
        file = store.put_blob(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><rect width="20" height="20"/></svg>', ext='svg')
        entry['svg'] = artifact(store, store.project_root / file['path'], 'svg',
                                page_id=entry['page_id'], dependencies=[
                                    {'kind': 'blueprint', 'identity': 'page:' + entry['page_id'],
                                     'sha256': entry['blueprint']['sha256']}])
    tasks = []
    for index, page_id in enumerate(('p01', 'p01', 'p02', 'p03')):
        pending = page_id == 'p03'  # Keep the real summary poll at three seconds.
        task = synthetic_task(doc, f'poll-{index}', 'awaiting_host' if pending else 'completed',
                              result_refs=[] if pending else [doc['pages'][index // 2]['page']])
        task['scope_pages'] = [page_id]
        doc['tasks'].append(store.put_json_object(task))
        tasks.append(task)
    commit(store, doc, 'poll-browser')
    return tasks


def _next(page, number):
    return page.locator('.matrix tbody tr').filter(
        has=page.get_by_role('button', name=f'打开第 {number:02d} 页', exact=True)
    ).locator('.matrix-next button')


def _next_summary(page):
    return page.expect_response(lambda response: '/api/view/summary?' in response.url,
                                timeout=7000)


def _mark_read(store, task):
    reading = result_reading.get(store.project_root)
    return result_reading.mark(store.project_root, project_identity=reading['project_identity'],
                               revision=store.current_revision_id(), task_id=task['task_id'],
                               result_key=result_reading.key(task), expected_etag=reading['etag'])


@pytest.mark.parametrize('size', [(1280, 800), (1440, 900), (390, 844)])
def test_natural_summary_poll_preserves_next_action_node_and_keyboard_focus(action_browser, size):
    from playwright.sync_api import expect
    page, server, _, store = action_browser
    _reading_tasks(store)
    page.set_viewport_size({'width': size[0], 'height': size[1]})
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    # Let initial draft and chapter reads settle, then observe an actual timer
    # poll, without dispatching a synthetic summary event or changing its delay.
    with _next_summary(page):
        pass
    next_action = _next(page, 1)
    next_action.focus()
    original = next_action.element_handle()
    with _next_summary(page):
        pass
    expect(next_action).to_be_focused()
    assert original.evaluate('(node) => node.isConnected')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_real_attention_change_preserves_only_same_page_and_action_focus(action_browser):
    from playwright.sync_api import expect
    page, server, _, store = action_browser
    tasks = _reading_tasks(store)
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    with _next_summary(page):
        pass
    first = _next(page, 1)
    first.focus()
    original = first.element_handle()
    # A separate page loses its unread result. The first page's same action
    # remains focused even though the matrix must reflect changed attention.
    with _next_summary(page):
        _mark_read(store, tasks[2])
    expect(_next(page, 2)).not_to_have_text('去阅读')
    expect(first).to_be_focused()
    assert not original.evaluate('(node) => node.isConnected')
    # Same caption, different result membership: do not move focus onto a new
    # action which Enter would activate without the user's explicit selection.
    with _next_summary(page):
        _mark_read(store, tasks[0])
    expect(first).to_have_text('去阅读')
    expect(first).not_to_be_focused()
    assert page.evaluate('document.activeElement === document.body')


def test_dispatch_unknown_explains_preservation_without_redispatch(icon_browser):
    from playwright.sync_api import expect
    page, store, _ = icon_browser
    recipe = confirm(store)
    dispatch(store, recipe)
    doc = store.load_document()
    task_ref = doc['tasks'][-1]
    damaged = store.project_root / task_ref['path']
    damaged.write_bytes(b'{broken task')
    before = store.load_document()
    requests = []
    page.on('request', lambda request: requests.append(request.url)
            if request.method == 'POST' and request.url.split('/api/')[-1]
            in ('icons/confirm', 'icons/plan', 'changes/commit') else None)
    query = dict(part.split('=', 1) for part in page.url.split('#')[1].split('&'))
    query['revision'] = store.current_revision_id()
    page.goto(page.url.split('#')[0] + '#' + urlencode(query))
    warning = page.get_by_text('派发状态待核实；原记录与已确认范围保留，请先核实原任务，未确认前不要重复派发。', exact=True)
    expect(warning).to_be_visible()
    expect(page.get_by_role('button', name='确认这些图标范围和处理方式', exact=True)).to_be_disabled()
    page.get_by_role('button', name='刷新图标方案', exact=True).click()
    expect(warning).to_be_visible()
    assert icons.listing(store.project_root, include_stale=True)['proposals'][0]['status'] == 'dispatch_unknown'
    assert store.load_document() == before and damaged.read_bytes() == b'{broken task'
    assert requests == []


def test_damaged_preview_busy_polls_without_automatic_retry(icon_browser):
    import fcntl
    from playwright.sync_api import expect
    from deck_master import candidate_preview
    from test_icon_quality import accept, input_for, start
    page, store, _ = icon_browser
    recipe = confirm(store, input_for(store, method='standard'))
    task = dispatch(store, recipe)[0]
    start(store, task)
    draft = icons.draft(store.project_root, recipe_id=recipe['recipe_id'], page_id='p01')
    candidate_id = accept(store, task, draft['svg'].encode())['candidate_ids'][0]
    key = candidate_preview._context(store.project_root, candidate_id)[-1]
    state = candidate_preview._state_path(store, key)
    state.write_bytes(b'{broken preview state')
    requests = []
    page.on('request', lambda request: requests.append(request.method)
            if '/api/candidate-preview/' in request.url else None)
    query = dict(part.split('=', 1) for part in page.url.split('#')[1].split('&'))
    query.update(revision=store.current_revision_id(), candidate=candidate_id)
    status = page.locator('.candidate-icon-review [role=status]')
    with (state.parent / 'worker.lock').open('a+b') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        page.goto(page.url.split('#')[0] + '#' + urlencode(query))
        expect(status).to_have_text('检查记录损坏，执行状态待核实；原记录已保留，等待现有任务结束后明确重试。')
        page.get_by_role('button', name='生成或重试实际 PPT 检查', exact=True).click()
        expect(status).to_have_text('检查记录损坏，执行状态待核实；原记录已保留，等待现有任务结束后明确重试。')
        with page.expect_response(lambda response: '/api/candidate-preview/status?' in response.url, timeout=5000):
            pass
        assert state.read_bytes() == b'{broken preview state'
    expect(status).to_have_text('检查记录损坏，原记录已保留；请明确重试实际 PPT 检查。', timeout=6000)
    assert requests.count('POST') == 1
    assert state.read_bytes() == b'{broken preview state'
    assert not (state.parent / 'candidate.pptx').exists()
