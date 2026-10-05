"""RC regressions against the real workbench and journal; no Host acceptance claim."""
import json

import pytest
from playwright.sync_api import expect
from test_deep_quality_browser import workbench  # noqa: F401
from test_icon_quality import icon_store  # noqa: F401

pytestmark = pytest.mark.browser


def saved_requirement(page, text, refs=None):
    for _ in range(100):
        records = page.request.get(page.url.split('#')[0] + 'api/drafts').json()['records']
        matching = [r for r in records if r['draft']['content'].get('requirement', {}).get('text') == text]
        if matching and (refs is None or matching[-1]['draft']['content']['requirement']['annotation_refs'] == refs):
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


def persisted_requirement(workbench):
    page, _, store, _, goto, _ = workbench
    goto()
    opinion(page)
    goto()
    expect(page.locator('[aria-label="页面内容"]')).to_have_attribute('data-revision', store.current_revision_id())
    page.get_by_label('选入意见 1', exact=True).check()
    page.get_by_label('修改要求', exact=True).fill('原要求：保留数字')
    return saved_requirement(page, '原要求：保留数字')


def isolated_context(workbench, **options):
    context = workbench[1].browser.new_context(**options)
    context.on('page', lambda p: p.on('pageerror', lambda error: workbench[5].append(str(error))))
    return context


def recover_on_new_port(workbench, text, refs):
    from deck_master.web import WorkbenchServer
    page, context, store, old_url, goto, _ = workbench
    fragment = page.url.split('#')[1]
    goto.stop_server()
    server = WorkbenchServer(store.project_root)
    fresh = isolated_context(workbench)
    try:
        url = server.start()
        assert url != old_url
        recovered = fresh.new_page()
        recovered.goto(url + '#' + fragment)
        expect(recovered.get_by_label('修改要求', exact=True)).to_have_value(text)
        if refs:
            expect(recovered.get_by_label('选入意见 1', exact=True)).to_be_checked()
        else:
            expect(recovered.get_by_label('选入意见 1', exact=True)).not_to_be_checked()
        assert saved_requirement(recovered, text)['annotation_refs'] == refs
    finally:
        fresh.close()
        server.stop()


@pytest.mark.parametrize('list_error', [False, True])
def test_unresolved_requirement_refs_survive_edit_save_and_new_port(workbench, list_error):
    page, _, _, _, _, _ = workbench
    original = persisted_requirement(workbench)
    held = []
    page.route('**/api/annotations?*', lambda route: held.append(route))
    page.reload()
    requirement = page.get_by_label('修改要求', exact=True)
    expect(requirement).to_be_editable()
    expect(requirement).to_have_value(original['text'])
    expect(page.get_by_role('button', name='预览修改影响', exact=True)).to_be_disabled()
    text = '列表等待期间改写：\n保留原数字与换行'
    requirement.fill(text)
    stored = saved_requirement(page, text)
    assert stored['annotation_refs'] == original['annotation_refs']
    assert stored['basis'] == original['basis']
    assert held
    if list_error:
        held.pop(0).abort('failed')
        expect(page.get_by_role('button', name='重新读取已保存意见', exact=True)).to_be_visible()
        requirement.fill(text + '（失败后继续写）')
        text += '（失败后继续写）'
        assert saved_requirement(page, text)['annotation_refs'] == original['annotation_refs']
        page.unroute('**/api/annotations?*')
        page.get_by_role('button', name='重新读取已保存意见', exact=True).click()
    else:
        for route in held:
            route.fulfill(response=route.fetch())
        page.unroute('**/api/annotations?*')
    expect(page.get_by_label('选入意见 1', exact=True)).to_be_checked()
    expect(requirement).to_have_value(text)
    page.reload()
    expect(page.get_by_label('选入意见 1', exact=True)).to_be_checked()
    page.get_by_label('选入意见 1', exact=True).uncheck()
    assert saved_requirement(page, text, refs=[])['annotation_refs'] == []
    page.reload()
    expect(page.get_by_label('选入意见 1', exact=True)).not_to_be_checked()
    page.get_by_label('选入意见 1', exact=True).check()
    assert saved_requirement(page, text, refs=original['annotation_refs'])['annotation_refs'] == original['annotation_refs']
    recover_on_new_port(workbench, text, original['annotation_refs'])


@pytest.mark.parametrize('invalid', ['missing_ref', 'old_basis'])
def test_requirement_edit_preserves_unusable_refs_and_basis_until_reselect(workbench, invalid):
    import copy
    from deck_master import ui_journal
    page, context, store, url, _, _ = workbench
    state = persisted_requirement(workbench)
    record = next(r for r in ui_journal.list_drafts(store.project_root)['records']
                  if r['draft']['content'].get('requirement') == state)
    draft = copy.deepcopy(record['draft'])
    if invalid == 'missing_ref':
        draft['content']['requirement']['annotation_refs'][0]['sha256'] = '0' * 64
    else:
        draft['content']['requirement']['basis']['revision_id'] = store.read_object_json(
            store.load_document()['annotations'][0])['base_revision']
    ui_journal.save(store.project_root, draft=draft, expected_etag=record['etag'])
    original = copy.deepcopy(draft['content']['requirement'])
    other = isolated_context(workbench)
    try:
        test_page = other.new_page()
        test_page.goto(url + '#' + page.url.split('#')[1])
        expect(test_page.locator('.requirement-ref')).to_have_count(0)
        expect(test_page.locator('.change-requirement')).to_contain_text('请重新选择')
        text = '只改文字，保留原来的引用证据'
        test_page.get_by_label('修改要求', exact=True).fill(text)
        stored = saved_requirement(test_page, text)
        assert stored['annotation_refs'] == original['annotation_refs']
        assert stored['basis'] == original['basis']
        test_page.reload()
        expect(test_page.get_by_role('button', name='预览修改影响', exact=True)).to_be_disabled()
        test_page.get_by_label('选入意见 1', exact=True).check()
        expect(test_page.get_by_role('button', name='预览修改影响', exact=True)).to_be_enabled()
        test_page.get_by_role('button', name='预览修改影响', exact=True).click()
        expect(test_page.get_by_role('button', name='确认计划并创建交接', exact=True)).to_be_visible()
    finally:
        other.close()


def test_requirement_only_copy_is_saved_to_project_and_recovers(workbench):
    import copy
    from deck_master import ui_journal
    page, context, store, url, goto, _ = workbench
    state = persisted_requirement(workbench)
    record = next(r for r in ui_journal.list_drafts(store.project_root)['records']
                  if r['draft']['content'].get('requirement') == state)
    old = store.read_object_json(store.load_document()['annotations'][0])['base_revision']
    # A separate historical draft, with no note or opinion body.
    draft = copy.deepcopy(record['draft'])
    draft['draft_id'] = 'requirement-only-old'
    draft['base_revision'] = old
    draft['content'] = {'text': '', 'requirement': state}
    ui_journal.save(store.project_root, draft=draft)
    fresh = isolated_context(workbench)
    try:
        other = fresh.new_page()
        other.goto(url + '#' + page.url.split('#')[1])
        other.get_by_text('恢复、下载与版本详情', exact=True).click()
        other.get_by_label('恢复项目中的个人草稿').select_option(draft['draft_id'])
        other.get_by_role('button', name='对当前版本写新意见', exact=True).click()
        other.get_by_text('私人笔记（不进入意见与制作）', exact=True).click()
        expect(other.get_by_role('button', name='保存个人草稿', exact=True)).to_be_enabled()
        other.get_by_role('button', name='保存个人草稿', exact=True).click()
        expect(other.locator('.draft-state')).to_contain_text('已保存到项目')
        records = ui_journal.list_drafts(store.project_root)['records']
        copied = next(r['draft'] for r in records if r['draft']['draft_id'] not in
                      [draft['draft_id'], record['draft']['draft_id']] and
                      'requirement' in r['draft']['content'] and
                      r['draft']['content']['requirement']['basis'] is None)
        assert copied['content']['requirement']['text'] == state['text']
        assert copied['content']['requirement']['annotation_refs'] == []
        assert copied['pending'] is None
        assert 'annotation' not in copied['content']
        assert 'trial' not in copied['content']
        assert any(r['draft']['draft_id'] == draft['draft_id'] for r in records)
        # Restore only the saved new draft in another origin, without browser buffers.
        fragment = other.url.split('#')[1]
        goto.stop_server()
        from deck_master.web import WorkbenchServer
        server = WorkbenchServer(store.project_root)
        try:
            new_url = server.start()
            assert new_url != url
            restored = fresh.new_page()
            restored.goto(new_url + '#' + fragment)
            restored.get_by_text('恢复、下载与版本详情', exact=True).click()
            restored.get_by_label('恢复项目中的个人草稿').select_option(copied['draft_id'])
            expect(restored.get_by_label('修改要求', exact=True)).to_have_value(state['text'])
            expect(restored.get_by_role('button', name='预览修改影响', exact=True)).to_be_disabled()
        finally:
            server.stop()
    finally:
        fresh.close()


@pytest.mark.parametrize('kind,width,height', [
    ('note', 1280, 800), ('opinion', 1280, 800), ('requirement', 1280, 800),
    ('same_note', 1280, 800), ('all', 1440, 900), ('all', 1280, 800), ('all', 390, 844),
])
def test_real_draft_conflict_compares_downloads_and_saves_all_texts(workbench, tmp_path, kind, width, height):
    import copy
    import os
    from pathlib import Path
    from deck_master import ui_journal
    page, context, store, url, _, errors = workbench
    state = persisted_requirement(workbench)
    record = next(r for r in ui_journal.list_drafts(store.project_root)['records']
                  if r['draft']['content'].get('requirement') == state)
    initial = copy.deepcopy(record['draft'])
    initial['content']['text'] = '共同笔记' if kind == 'same_note' else ''
    initial['content']['annotation'] = {'body': '', 'scope': 'page', 'regions': [], 'intent': '修改建议',
                                      'chapter_id': page.get_by_label('意见所属章节').input_value()}
    initial['content']['requirement']['text'] = ''
    ui_journal.save(store.project_root, draft=initial, expected_etag=record['etag'])
    project_texts = ['共同笔记' if kind == 'same_note' else '', '', '']
    local_texts = list(project_texts)
    for index, purpose in enumerate(['笔记', '意见', '要求']):
        if kind == 'all' or kind == ['note', 'opinion', 'requirement'][index] or kind == 'same_note' and index == 2:
            project_texts[index] = f'项目{purpose} A\n保留换行'
            local_texts[index] = f'本机{purpose} B\n保留换行'
    a_context = context.browser.new_context(viewport={'width': width, 'height': height})
    b_context = context.browser.new_context(viewport={'width': width, 'height': height}, accept_downloads=True)
    for browser_context in [a_context, b_context]:
        browser_context.on('page', lambda p: p.on('pageerror', lambda error: errors.append(str(error))))
    try:
        a, b = a_context.new_page(), b_context.new_page()
        for window in [a, b]:
            window.goto(url + '#' + page.url.split('#')[1])
            expect(window.get_by_label('意见正文', exact=True)).to_be_editable()
            window.get_by_text('私人笔记（不进入意见与制作）', exact=True).click()
            expect(window.get_by_label('个人草稿', exact=True)).to_have_value(initial['content']['text'])
        labels = ['个人草稿', '意见正文', '修改要求']
        def edit(window, texts):
            for label, value in zip(labels, texts, strict=True):
                if window.get_by_label(label, exact=True).input_value() != value:
                    window.get_by_label(label, exact=True).fill(value)
        edit(a, project_texts)
        expect(a.locator('.draft-state')).to_contain_text('已保存到项目')
        with b.expect_response(lambda response: '/api/drafts/save' in response.url and response.status == 409) as conflict:
            edit(b, local_texts)
        assert conflict.value.status == 409
        expect(b.locator('.draft-state')).to_contain_text('保存冲突')
        b.get_by_role('button', name='比较两份草稿', exact=True).click()
        dialog = b.get_by_role('dialog')
        expect(dialog).to_be_visible()
        expect(dialog.locator('.conflict-panes textarea')).to_have_count(6)
        for prefix, texts in [('本机', local_texts), ('项目', project_texts)]:
            for purpose, value in zip(['私人笔记', '意见正文', '修改要求'], texts, strict=True):
                field = dialog.get_by_label(prefix + purpose, exact=True)
                expect(field).to_have_value(value)
                expect(field).not_to_be_editable()
                if not value:
                    expect(field).to_have_attribute('placeholder', '空白')
        panes = dialog.locator('.draft-conflict-pane')
        expect(panes).to_have_count(2)
        for index in range(2):
            detail = json.loads(panes.nth(index).locator('pre').text_content())
            assert detail['target'] == initial['target']
            assert detail['base_revision'] == initial['base_revision']
            assert detail['base_ref'] == initial['base_ref']
            assert detail['requirement_basis'] == state['basis']
            assert detail['annotation_refs'] == state['annotation_refs']
        assert b.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert dialog.evaluate('(node) => node.scrollWidth <= node.clientWidth')
        evidence = Path(os.environ.get('DECK_MASTER_RC_EVIDENCE', str(tmp_path)))
        evidence.mkdir(parents=True, exist_ok=True)
        b.screenshot(path=str(evidence / f'conflict-{kind}-{width}.png'))
        with b.expect_download() as downloaded:
            dialog.get_by_role('button', name='下载本机稿', exact=True).click()
        recovery = json.loads(Path(downloaded.value.path()).read_text())
        expected = copy.deepcopy(initial)
        expected['content']['text'] = local_texts[0]
        expected['content']['annotation']['body'] = local_texts[1]
        expected['content']['requirement']['text'] = local_texts[2]
        assert recovery['draft'] == expected
        # The open comparison stays frozen if the other window saves again.
        a.get_by_label('个人草稿', exact=True).fill('项目后续修改')
        expect(a.locator('.draft-state')).to_contain_text('已保存到项目')
        expect(dialog.get_by_label('项目私人笔记', exact=True)).to_have_value(project_texts[0])
        dialog.get_by_role('button', name='另存为个人草稿', exact=True).click()
        expect(b.locator('.draft-state')).to_contain_text('已保存到项目')
        records = ui_journal.list_drafts(store.project_root)['records']
        new = next(r['draft'] for r in records if r['draft']['draft_id'] != initial['draft_id'] and
                   r['draft']['content'] == expected['content'])
        expected['draft_id'] = new['draft_id']
        assert new == expected
        original = ui_journal.get(store.project_root, initial['draft_id'])['record']['draft']
        assert original['content']['text'] == '项目后续修改'
        assert original['content']['annotation']['body'] == project_texts[1]
        assert original['content']['requirement']['text'] == project_texts[2]
    finally:
        a_context.close()
        b_context.close()


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
    expect(page.get_by_label('冻结的原请求', exact=True)).to_have_value(original)
    expect(page.get_by_label('之后继续编辑的草稿', exact=True)).to_have_value(later)
    expect(page.get_by_label('修改要求', exact=True)).to_have_value(later)


def test_page_candidate_uses_one_fixed_lineage_read(workbench):
    from urllib.parse import urlencode
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
    from urllib.parse import urlencode
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
    assert json.loads(page.get_by_label('冻结的原请求', exact=True).input_value()) == {'plan_id': 'old-plan'}
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
