"""U01 navigation in Chromium against real loopback reads; synthetic data."""
from pathlib import Path
import shutil
import copy
import uuid

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_action_targets import add_handoffs, current_read_task
from candidate_fixtures import candidate
from test_content_candidates import dispatch_content_ops_trial, start_task, accept, changeset_envelope
from test_workbench_actions import commit
from rc3_fixtures import evidence_for, settle_fidelity_review
from test_service_flow import _prepare_production

pytestmark = pytest.mark.browser


def _prepare_browser_project(path, *, max_candidate_count=4):
    """Explicit L1 editorial scope; local candidates never grant image calls."""
    from deck_master import collaboration
    scope = _prepare_production(path,
        actions=['content.operation', 'change.commit', 'candidate.adopt'],
        max_external_calls=0, max_candidate_count=max_candidate_count,
        membership=True, order=True,
        scenario=f'L1 fixed manuscript browser transactions, {max_candidate_count} local candidates, zero image calls')
    store = Store(path)
    collaboration.record_decision(path, input={'topic': 'direction', 'disposition': 'accepted',
        'authority_mode': 'direct_user', 'value': 'Preserve this exact synthetic manuscript direction',
        'scope': scope, 'subject_refs': [],
        'instruction_evidence': evidence_for(path,
            text='L1 explicitly confirmed editorial direction for these fixed pages and bounded local trials.',
            locator='L1:browser-editorial-direction')},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    # The accepted direction is a new effective requirement. Review against it
    # through the real workorder before dispatching any visual candidate.
    settle_fidelity_review(path, page_ids=[entry['page_id'] for entry in store.load_document()['pages']],
        execution_ref='L1-browser-confirmed-direction',
        scenario='L1 fixed manuscript rechecked against the newly confirmed editorial direction')


@pytest.fixture
def action_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'browser-project'
    create_sample(path, page_count=3, readonly=False)
    _prepare_browser_project(path)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for navigation checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close()
            server.stop()


def test_grouped_todo_lists_every_task_then_opens_the_selected_task(action_browser):
    page, server, path, store = action_browser
    add_handoffs(store)
    before = store.read_current()
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='去交接', exact=True).click()
    page.get_by_role('heading', name='待办对象', exact=True).wait_for()
    assert page.locator('.action-target').count() == 2
    page.screenshot(path=str(path.parent / 'grouped-tasks.png'))
    page.locator('.action-target').nth(1).get_by_role('button', name='查看这个对象').click()
    page.get_by_role('heading', name='当前任务', exact=True).wait_for()
    assert 'task=handoff-1' in page.url
    assert store.read_current() == before


def test_multi_candidate_todo_and_historical_candidate_reads(action_browser):
    page, server, path, store = action_browser
    ids = [candidate(store, width=20), candidate(store, width=24)]
    revision = store.current_revision_id()
    before = store.read_current()
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.get_by_role('heading', name='待办对象', exact=True).wait_for()
    assert page.locator('.action-target').count() == 2
    page.locator('.action-target').nth(1).get_by_role('button', name='查看这个对象').click()
    page.wait_for_selector('.candidate-desk[data-candidate-id="' + ids[1] + '"]')
    assert 'page=p01' in page.url and 'layer=svg' in page.url
    assert store.read_current() == before
    old_url = page.url
    doc = copy.deepcopy(store.load_document())
    doc['policy']['user_stop'] = True
    commit(store, doc, str(uuid.uuid4()))
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/api/candidates' in request.url else None)
    page.goto(old_url)
    page.reload()
    page.wait_for_selector('.candidate-desk[data-candidate-id="' + ids[1] + '"]')
    page.get_by_text('历史版本 · 只读', exact=True).wait_for()
    assert requests and all('revision=' + revision in url for url in requests)
    assert page.get_by_role('button', name='预览采用这个候选', exact=True).is_disabled()


def test_changeset_todo_opens_fixed_deck_comparison_without_fake_page(action_browser):
    page, server, path, store = action_browser
    task = dispatch_content_ops_trial(path, store, 'merge', ('p01', 'p02'))
    start_task(path, task)
    accept(path, task, changeset_envelope(store, task, 'merge'))
    before = store.read_current()
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.get_by_role('heading', name='整稿正文变更集比较', exact=True).wait_for()
    assert 'surface=content' in page.url and 'candidate=' in page.url and '&page=' not in page.url
    page.locator('.changeset-page').filter(has_text='Synthetic derived page 0').locator('summary').click()
    page.get_by_role('heading', name='固定基准正文', exact=True).wait_for()
    assert 'Synthetic derived page 0' in page.locator('[data-side="candidate"]').inner_text()
    assert 'Synthetic derived page 0' not in page.locator('[data-side="current"]').inner_text()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(path.parent / 'changeset-mobile.png'))
    assert store.read_current() == before


def test_foreign_project_link_keeps_the_loaded_work_surface(action_browser):
    from playwright.sync_api import expect
    page, server, path, store = action_browser
    before = store.read_current()
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.evaluate("revision => {location.hash = new URLSearchParams({project:'0'.repeat(64),surface:'overview',revision})}", store.current_revision_id())
    expect(page.locator('.notice')).to_contain_text('这个链接属于另一个项目')
    assert page.get_by_role('heading', name='制作总览', exact=True).is_visible()
    assert store.read_current() == before


def test_read_result_removes_same_overview_target_and_survives_reload(action_browser):
    from test_workbench_actions import synthetic_task
    page,server,path,store=action_browser
    doc=copy.deepcopy(store.load_document());doc['tasks']=[]
    for i in range(2):
        task=current_read_task(store,doc,f'reading-{i}','completed',page_ids=['p01'],result_refs=[doc['pages'][0]['page']]);doc['tasks'].append(store.put_json_object(task))
    commit(store,doc,'reading-browser');before=store.load_document()
    errors=[];page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.add_init_script("window.cspErrors=[];document.addEventListener('securitypolicyviolation',e=>window.cspErrors.push(e.violatedDirective))")
    page.goto(server.start())
    summary=page.request.get(server.start().rstrip('/')+'/api/view/summary?protocol=workbench_summary.v2&personal=1').json()
    assert summary['current_work']['next']['action']=='review_results'
    page.locator('.todo-priority').get_by_role('button',name='去阅读',exact=True).click()
    page.get_by_role('heading',name='待办对象',exact=True).wait_for();assert page.locator('.action-target').count()==2
    page.locator('.action-target').first.get_by_role('button',name='查看这个对象').click()
    page.get_by_role('button',name='标记这些结果已读',exact=True).click()
    from playwright.sync_api import expect
    expect(page.get_by_role('button',name='已标记读过这些结果',exact=True)).to_be_disabled()
    page.reload();expect(page.get_by_role('button',name='已标记读过这些结果',exact=True)).to_be_disabled()
    reading=page.request.get(server.start().rstrip('/')+'/api/result-reading').json()
    assert len(reading['seen'])==1 and store.load_document()==before
    summary=page.request.get(server.start().rstrip('/')+'/api/view/summary?personal=1').json()
    action=next(a for a in summary['next_actions']['actions'] if a['kind']=='review_results')
    target=page.request.get(server.start().rstrip('/')+'/api/actions/'+action['action_id']+'/targets?revision='+summary['revision_id']+'&personal=1&reading_etag='+reading['etag']).json()
    assert target['total']==1
    assert errors==[] and page.evaluate('window.cspErrors')==[]


def test_target_paging_failure_retries_exact_page_and_ignores_departed_response(action_browser):
    """A 65-object list retains display identity while another page is requested."""
    from playwright.sync_api import expect
    from urllib.parse import parse_qs, urlparse
    from test_workbench_actions import synthetic_task
    page,server,path,store=action_browser
    doc=copy.deepcopy(store.load_document());doc['tasks']=[]
    for index in range(65):
        task=current_read_task(store,doc,f'pageable-handoff-{index:02d}','awaiting_host',page_ids=['p01'])
        doc['tasks'].append(store.put_json_object(task))
    commit(store,doc,'pageable-action-targets');before=store.read_current()
    page.goto(server.start()+'studio/')
    page.locator('.todo-priority').get_by_role('button',name='去交接',exact=True).click()
    expect(page.locator('.action-target')).to_have_count(30)
    first=page.locator('.action-target').first.get_attribute('data-target-id')
    requests=[];held=[]
    def hold_second(route):
        query=parse_qs(urlparse(route.request.url).query)
        if query.get('offset')==['30']:
            requests.append(route.request.url);held.append(route)
        else:route.continue_()
    page.route('**/api/actions/*/targets?*',hold_second)
    page.get_by_role('button',name='下一页对象',exact=True).click()
    expect(page.get_by_role('button',name='下一页对象',exact=True)).to_be_disabled()
    expect(page.get_by_role('button',name='上一页对象',exact=True)).to_be_disabled()
    assert len(held)==1
    held.pop().abort()
    retry=page.get_by_role('button',name='重试第 2 页对象',exact=True)
    expect(retry).to_be_visible()
    expect(page.locator('.action-target')).to_have_count(30)
    assert page.locator('.action-target').first.get_attribute('data-target-id')==first
    expect(page.locator('.action-targets > .row')).to_contain_text('第 1 页')
    retry.click();expect(retry).to_be_disabled()
    assert len(held)==1 and len(requests)==2 and requests[0]==requests[1]
    held.pop().continue_()
    expect(page.locator('.action-targets > .row')).to_contain_text('第 2 页')
    assert page.locator('.action-target').first.get_attribute('data-target-id')!=first
    expect(retry).to_have_count(0)
    def mismatched_third(route):
        query=parse_qs(urlparse(route.request.url).query)
        if query.get('offset')==['60']:
            response=route.fetch();value=response.json();value['action_id']='unrelated-action'
            route.fulfill(response=response,json=value)
        else:route.fallback()
    page.route('**/api/actions/*/targets?*',mismatched_third)
    page.get_by_role('button',name='下一页对象',exact=True).click()
    expect(page.get_by_role('button',name='重试第 3 页对象',exact=True)).to_be_visible()
    expect(page.locator('.action-targets > .row')).to_contain_text('第 2 页')
    expect(page.locator('.action-target')).to_have_count(30)
    page.unroute('**/api/actions/*/targets?*',mismatched_third)
    page.get_by_role('button',name='重试第 3 页对象',exact=True).click()
    expect(page.locator('.action-target')).to_have_count(5)
    expect(page.locator('.action-targets > .row')).to_contain_text('第 3 页')
    expect(page.get_by_role('button',name='下一页对象',exact=True)).to_be_disabled()
    page.get_by_role('button',name='上一页对象',exact=True).click()
    expect(page.get_by_role('button',name='下一页对象',exact=True)).to_be_disabled()
    assert len(held)==1
    page.get_by_role('button',name='返回制作总览',exact=True).click()
    held.pop().continue_()
    expect(page.get_by_role('heading',name='制作总览',exact=True)).to_be_visible()
    expect(page.locator('.action-targets')).to_have_count(0)
    assert store.read_current()==before
