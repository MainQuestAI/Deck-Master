"""Failed candidate selection must keep the retained candidate's sole reader alive."""
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect

from deck_master import icons
from test_icon_browser import icon_browser  # noqa: F401
from test_icon_quality import accept, confirm, dispatch, icon_store, input_for, start  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('inflight', ['GET', 'POST'])
@pytest.mark.parametrize('completion', ['visible', 'hidden', 'disposed'])
def test_failed_candidate_selection_resumes_retained_preview(icon_browser, inflight, completion):
    page, store, _ = icon_browser
    ids = []
    for index in range(2):
        value = input_for(store, method='standard')
        value['instruction'] += str(index)
        recipe = confirm(store, value)
        task = dispatch(store, recipe)[0]
        start(store, task)
        draft = icons.draft(store.project_root, recipe_id=recipe['recipe_id'], page_id='p01')
        ids.append(accept(store, task, draft['svg'].encode())['candidate_ids'][0])
    reads, posts = [], []

    def status(route):
        reads.append(route)
        if len(reads) > 1:
            route.fulfill(json={'status': 'interrupted', 'candidate_id': ids[0]})
        elif inflight == 'POST':
            route.fulfill(json={'status': 'not_requested', 'candidate_id': ids[0]})

    page.route('**/api/candidate-preview/status?*', status)
    page.route('**/api/candidate-preview/request', lambda route: posts.append(route))
    page.route('**/api/candidates/' + ids[1] + '*', lambda route: route.fulfill(
        status=503, json={'error': {'code': 'selection_failed', 'message': 'controlled selection failure'}}))
    query = dict(part.split('=', 1) for part in page.url.split('#')[1].split('&'))
    query.update(revision=store.current_revision_id(), candidate=ids[0])
    with page.expect_request('**/api/candidate-preview/status?*'):
        page.goto(page.url.split('#')[0] + '#' + urlencode(query))
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', ids[0])
    if inflight == 'POST':
        expect(page.locator('.candidate-icon-review [role=status]')).to_have_text('尚未检查')
        with page.expect_request('**/api/candidate-preview/request'):
            page.get_by_role('button', name='生成候选实际 PPT', exact=True).click()
    # Attempt A -> B; the failed read restores selection A without replacing it.
    page.get_by_label('选择本页候选', exact=True).select_option(ids[1])
    expect(page.locator('.candidate-impact')).to_contain_text('controlled selection failure')
    expect(page.get_by_label('选择本页候选', exact=True)).to_have_value(ids[0])
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', ids[0])
    if completion == 'hidden':
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    elif completion == 'disposed':
        page.locator('.sidebar').get_by_role('button', name='制作总览', exact=True).click()
        expect(page.locator('.candidate-desk')).to_have_count(0)
    held = reads[0] if inflight == 'GET' else posts[0]
    if completion == 'visible':
        with page.expect_request('**/api/candidate-preview/status?*'):
            held.fulfill(json={'status': 'running', 'candidate_id': ids[0]})
    else:
        held.fulfill(json={'status': 'running', 'candidate_id': ids[0]})
        page.wait_for_timeout(2200)  # Cross the original timer deadline.
        assert len(reads) == 1
        if completion == 'hidden':
            with page.expect_request('**/api/candidate-preview/status?*'):
                page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))")
    if completion != 'disposed':
        expect(page.locator('.candidate-icon-review [role=status]')).to_have_text('实际检查已中断，请明确重试')
        assert len(reads) == 2
    assert len(posts) == (1 if inflight == 'POST' else 0)
