"""RC regressions against the real workbench and journal; no Host acceptance claim."""
import json

import pytest
from playwright.sync_api import expect
from test_deep_quality_browser import workbench  # noqa: F401
from test_icon_quality import icon_store  # noqa: F401

pytestmark = pytest.mark.browser


def saved_requirement(page, text):
    for _ in range(100):
        records = page.request.get(page.url.split('#')[0] + 'api/drafts').json()['records']
        matching = [r for r in records if r['draft']['content'].get('requirement', {}).get('text') == text]
        if matching:
            return matching[-1]['draft']['content']['requirement']
        page.wait_for_timeout(50)
    raise AssertionError({'records': records, 'state': page.locator('.draft-state').all_text_contents(),
                          'errors': page.locator('.field-error').all_text_contents(),
                          'local': page.evaluate('() => Object.entries(localStorage).filter(([k]) => k.includes(":draft:"))')})


def opinion(page, text='缩短标题'):
    page.get_by_role('button', name='整页意见', exact=True).click()
    page.get_by_label('意见正文', exact=True).fill(text)
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    page.get_by_label('选入意见 1', exact=True).check()


def test_requirement_survives_reload_and_deselect(workbench):
    page, _, store, _, goto, _ = workbench
    goto()
    opinion(page)
    goto()
    expect(page.locator('[aria-label="页面内容"]')).to_have_attribute('data-revision', store.current_revision_id())
    page.get_by_label('选入意见 1', exact=True).check()
    text = '标题保持12字以内，保留原数字，禁止新增效果承诺'
    page.get_by_label('修改要求', exact=True).fill(text)
    assert saved_requirement(page, text)['annotation_refs']
    page.reload()
    expect(page.get_by_label('选入意见 1', exact=True)).to_be_checked()
    expect(page.get_by_label('修改要求', exact=True)).to_have_value(text)
    page.get_by_label('选入意见 1', exact=True).uncheck()
    expect(page.get_by_label('修改要求', exact=True)).to_have_value(text)
    page.get_by_label('选入意见 1', exact=True).check()
    expect(page.get_by_label('修改要求', exact=True)).to_have_value(text)


def test_old_basis_copy_clears_scope_and_requirement_selection(workbench):
    from deck_master import ui_journal
    page, _, store, _, goto, _ = workbench
    old = store.current_revision_id()
    goto()
    opinion(page)
    records = ui_journal.list_drafts(store.project_root)['records']
    record = next(r for r in records if r['draft']['base_revision'] == old)
    draft = record['draft']
    draft['content']['annotation'].update(scope='chapter', chapter_id='old-chapter', regions=[{'kind': 'whole'}])
    draft['content']['requirement'] = {'text': '保留原数字', 'edited': True,
        'annotation_refs': [], 'basis': {'revision_id': old}}
    ui_journal.save(store.project_root, draft=draft, expected_etag=record['etag'])
    goto()
    page.get_by_text('恢复、下载与版本详情', exact=True).click()
    choices = page.get_by_label('恢复项目中的个人草稿')
    choices.select_option(draft['draft_id'])
    expect(page.get_by_label('意见正文', exact=True)).not_to_be_editable()
    page.get_by_role('button', name='对当前版本写新意见', exact=True).click()
    expect(page.get_by_label('意见作用范围', exact=True)).to_have_value('page')
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('缩短标题')
    expect(page.get_by_label('修改要求', exact=True)).to_have_value('保留原数字')
    expect(page.get_by_label('选入意见 1', exact=True)).not_to_be_checked()
    expect(page.get_by_role('button', name='预览修改影响', exact=True)).to_be_disabled()


def test_nearby_candidates_bind_historical_revision(workbench):
    from test_candidates import dispatch, start, accept
    page, _, store, _, goto, _ = workbench
    old = store.current_revision_id()
    task = dispatch(store, 'p01', layer='svg')
    start(store, task)
    accept(store, task)
    requests = []
    page.on('request', lambda r: requests.append(r.url) if '/api/candidates?' in r.url else None)
    goto(revision=old)
    page.get_by_text('本页候选与试作', exact=True).wait_for()
    expect(page.locator('.page-trial-entry')).to_contain_text('尚无候选')
    assert requests and all('revision=' + old in url for url in requests)


def test_requirement_recovers_on_a_new_port(workbench):
    from deck_master.web import WorkbenchServer
    page, context, store, _, goto, _ = workbench
    goto()
    opinion(page)
    goto()
    expect(page.locator('[aria-label="页面内容"]')).to_have_attribute('data-revision', store.current_revision_id())
    page.get_by_label('选入意见 1', exact=True).check()
    text = '保留数字，标题12字以内'
    page.get_by_label('修改要求', exact=True).fill(text)
    saved_requirement(page, text)
    server = WorkbenchServer(store.project_root)
    new_page = context.new_page()
    try:
        new_page.goto(server.start() + '#' + page.url.split('#')[1])
        expect(new_page.get_by_label('修改要求', exact=True)).to_have_value(text)
        expect(new_page.get_by_label('选入意见 1', exact=True)).to_be_checked()
    finally:
        new_page.close()
        server.stop()


@pytest.mark.parametrize('old_error', [False, True])
def test_late_annotation_list_cannot_remove_a_saved_opinion(workbench, old_error):
    page, _, _, _, goto, _ = workbench
    goto()
    opinion(page, '意见 A')
    held = []
    def delay_first(route):
        response = route.fetch()
        if not held:
            held.append((route, response))
        else:
            route.fulfill(response=response)
    page.route('**/api/annotations?*', delay_first)
    goto()
    page.get_by_role('button', name='整页意见', exact=True).click()
    page.get_by_label('意见正文', exact=True).fill('意见 B')
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(page.locator('.saved-annotations')).to_contain_text('意见 B')
    assert held
    prior = page.locator('.annotations-panel .field-error[role=status]').inner_text()
    if old_error:
        held[0][0].abort('failed')
    else:
        with page.expect_response('**/api/annotations?*'):
            held[0][0].fulfill(response=held[0][1])
    page.wait_for_timeout(100)
    expect(page.locator('.saved-annotations')).to_contain_text('意见 B')
    expect(page.locator('.annotations-panel .field-error[role=status]')).to_have_text(prior)


def test_commit_conflict_shows_frozen_requirement_and_later_draft(workbench):
    import copy
    import uuid
    from deck_master.models import bump_revision
    page, _, store, _, goto, _ = workbench
    goto()
    opinion(page)
    original, later = '原请求 A：仅缩短标题', '后写草稿 B：保留原数字'
    page.get_by_label('修改要求', exact=True).fill(original)
    saved_requirement(page, original)
    page.get_by_role('button', name='预览修改影响', exact=True).click()
    confirm = page.get_by_role('button', name='确认计划并创建交接', exact=True)
    expect(confirm).to_be_visible()
    held = []
    page.route('**/api/changes/commit', lambda route: held.append(route))
    confirm.click()
    for _ in range(100):
        if held:
            break
        page.wait_for_timeout(20)
    assert held
    drafts = page.request.get(page.url.split('#')[0] + 'api/drafts').json()['records']
    pending = next(r['draft']['pending'] for r in drafts if r['draft']['pending'])
    assert pending['payload']['display_context']['instruction'] == original
    expect(page.get_by_label('修改要求', exact=True)).to_be_editable()
    page.get_by_label('修改要求', exact=True).fill(later)
    old = store.load_document()
    moved = copy.deepcopy(old)
    artifact = store.read_object_json(moved['pages'][0]['svg'])
    artifact['limitations'] = ['Synthetic concurrent write']
    moved['pages'][0]['svg'] = store.put_json_object(artifact)
    moved = bump_revision(moved, {'operation_id': str(uuid.uuid4()), 'kind': 'artifact_adoption',
                                 'description': 'Concurrent basis change', 'read_set': []})
    store.commit_change(base_revision=old['revision_id'], document=moved, operation_id=moved['change']['operation_id'])
    with page.expect_response('**/api/changes/commit') as response:
        held[0].fulfill(response=held[0].fetch())
    assert response.value.status == 409
    expect(page.get_by_label('未提交的本机草稿', exact=True)).to_have_value(original)
    expect(page.get_by_label('之后继续编辑的草稿', exact=True)).to_have_value(later)
    expect(page.get_by_label('修改要求', exact=True)).to_have_value(later)


def test_page_candidate_uses_one_fixed_lineage_read(workbench):
    from urllib.parse import urlencode, parse_qs, urlsplit
    import uuid
    from deck_master import changes
    from test_content_candidates import content_intent, start_task, page_envelope, accept
    page, _, store, url, _, _ = workbench
    plan = changes.plan(store.project_root, input=content_intent(store, 'p01'))
    task_id = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                             operation_id=str(uuid.uuid4()))['operation_result']['task_ids'][0]
    task = next(store.read_object_json(r) for r in store.load_document()['tasks'] if store.read_object_json(r)['task_id'] == task_id)
    start_task(store.project_root, task)
    accept(store.project_root, task, page_envelope(store, task))
    candidate = store.read_object_json(store.load_document()['candidates'][0])
    requests = []
    page.on('request', lambda r: requests.append(r.url) if '/lineage?' in r.url else None)
    info = page.request.get(url + 'api/project').json()
    page.goto(url + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p01',
        'layer': 'content', 'revision': store.current_revision_id(), 'candidate': candidate['candidate_id']}))
    expect(page.locator('.candidate-columns')).to_be_visible()
    assert len([u for u in requests if 'revision=' + candidate['base_revision'] in u]) == 1


def test_prepared_prompt_selection_mounts_one_recovery_panel(workbench):
    import uuid
    from urllib.parse import urlencode, parse_qs, urlsplit
    from deck_master import changes
    page, _, store, url, _, _ = workbench
    for instruction in ['仅调整标题层级', '仅调整配色']:
        doc = store.load_document()
        entry = doc['pages'][0]
        plan = changes.plan(store.project_root, input={'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
            'base_revision': doc['revision_id'], 'intent': 'style', 'instruction': instruction, 'annotation_refs': [],
            'max_calls': 1, 'mode': 'trial', 'targets': [{'page_id': entry['page_id'], 'page_ref': entry['page'],
                'layer': 'original_image', 'artifact_ref': entry['blueprint']}]})
        changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    info = page.request.get(url + 'api/project').json()
    page.goto(url + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p01',
        'layer': 'prepared_prompt', 'revision': store.current_revision_id()}))
    select = page.get_by_label('选择草稿绑定的预备提示词')
    expect(select.locator('option')).to_have_count(3)
    values = select.locator('option').evaluate_all('(options) => options.map(o => o.value).filter(Boolean)')
    for ref in [values[0], values[1], values[0]]:
        select.select_option(ref)
        recovery = page.get_by_text('恢复、下载与版本详情', exact=True)
        expect(recovery).to_have_count(1)
        recovery.click()
        expect(page.get_by_role('button', name='下载草稿恢复文件', exact=True)).to_be_visible()
        expect(page.get_by_label('意见正文', exact=True)).to_be_editable()
        with page.expect_download() as download:
            page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
        from pathlib import Path
        recovered = json.loads(Path(download.value.path()).read_text())
        assert recovered['draft']['base_ref']['sha256'] == ref


def test_loading_draft_is_readonly_and_old_pending_shows_exact_request(workbench):
    page, _, _, _, goto, _ = workbench
    held = []
    page.route('**/api/drafts', lambda route: held.append(route))
    goto()
    expect(page.get_by_label('意见正文', exact=True)).not_to_be_editable()
    expect(page.locator('.annotation-notice')).to_contain_text('正在读取草稿')
    for route in list(held):
        route.fulfill(response=route.fetch())
    page.unroute('**/api/drafts')
    expect(page.get_by_label('意见正文', exact=True)).to_be_editable()
    # Render an old recovery record with no display_context via the production class.
    page.evaluate('''async () => {
      const {BusinessOperations} = await import('/v2/business-operations.js');
      const business = new BusinessOperations({info: await (await fetch('/api/project')).json(),
        root: document.createElement('div')});
      await business.ready;
      await business.conflict({pending: {payload: {action: 'changes.commit', request: {plan_id: 'old-plan'}}},
        editor: {pendingText: () => '后写文字'}, note: '旧请求冲突'}, {details: {}});
    }''')
    assert json.loads(page.get_by_label('未提交的本机草稿', exact=True).input_value()) == {'plan_id': 'old-plan'}
    expect(page.get_by_label('之后继续编辑的草稿', exact=True)).to_have_value('后写文字')
    expect(page.get_by_role('dialog')).to_contain_text('旧记录未保存修改要求正文')


def test_buffered_draft_remains_readonly_until_project_recovery_loads(workbench):
    page, _, _, _, goto, _ = workbench
    goto()
    body = page.get_by_label('意见正文', exact=True)
    expect(body).to_be_editable()
    body.fill('已有浏览器缓冲')
    page.get_by_text('私人笔记（不进入意见与制作）', exact=True).click()
    page.get_by_role('button', name='保存个人草稿', exact=True).click()
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    held = []
    page.route('**/api/drafts', lambda route: held.append(route))
    page.reload()
    expect(body).not_to_be_editable()
    expect(page.locator('.annotation-notice')).to_contain_text('正在读取草稿')
    for route in list(held):
        route.fulfill(response=route.fetch())
    page.unroute('**/api/drafts')
    expect(body).to_be_editable()
    expect(body).to_have_value('已有浏览器缓冲')


@pytest.mark.parametrize('destination', ['candidate', 'page'])
@pytest.mark.parametrize('late_error', [False, True])
def test_late_candidate_reads_leave_the_new_surface_alone(workbench, destination, late_error):
    from urllib.parse import urlencode, parse_qs, urlsplit
    from test_content_candidates import dispatch_content_trial, start_task, page_envelope, accept
    page, _, store, url, _, _ = workbench
    ids = []
    for suffix in [' candidate A', ' candidate B']:
        task = dispatch_content_trial(store.project_root, store)
        start_task(store.project_root, task)
        ids.append(accept(store.project_root, task, page_envelope(store, task, suffix))['candidate_ids'][0])
    identity = page.request.get(url + 'api/project').json()['project_identity']
    route = {'project': identity, 'surface': 'page', 'page': 'p01', 'layer': 'content',
             'revision': store.current_revision_id(), 'candidate': ids[0]}
    page.goto(url + '#' + urlencode(route))
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', ids[0])
    held = []
    page.route('**/api/candidates/' + ids[1], lambda r: held.append((r, r.fetch())))
    page.get_by_label('选择本页候选', exact=True).select_option(ids[1])
    for _ in range(100):
        if held:
            break
        page.wait_for_timeout(20)
    assert held
    if destination == 'page':
        route.pop('candidate')
        route['page'] = 'p02'
    new_hash = '#' + urlencode(route)
    page.evaluate('(hash) => location.hash = hash', new_hash)
    if destination == 'candidate':
        expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', ids[0])
    else:
        expect(page.locator('[aria-label="页面内容"]')).to_have_attribute('data-page-id', 'p02')
    if late_error:
        held[0][0].abort('failed')
    else:
        held[0][0].fulfill(response=held[0][1])
    page.wait_for_timeout(100)
    final_route = parse_qs(urlsplit(page.url).fragment)
    assert final_route['page'] == [route['page']]
    assert final_route['revision'] == [route['revision']]
    assert final_route.get('candidate') == ([route['candidate']] if 'candidate' in route else None)
    if destination == 'candidate':
        expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', ids[0])
        expect(page.locator('.candidate-columns')).to_contain_text('candidate A')
        expect(page.locator('.candidate-columns')).not_to_contain_text('candidate B')
        expect(page.locator('.candidate-impact .field-error')).to_have_count(0)
    else:
        expect(page.locator('.candidate-desk')).to_have_count(0)
