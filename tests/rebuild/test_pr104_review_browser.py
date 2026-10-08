"""PR104 review counterexamples: shipped modules, real Chromium/core, synthetic data.

Transport delays and an explicitly synthetic adopted-sample listing do not call
a Host or prove visual quality. Clipboard and final service drafts are asserted.
"""
import copy
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode

import pytest

from deck_master import annotation_service, styles, ui_journal
from deck_master.web import WorkbenchServer
from test_icon_quality import icon_store  # noqa: F401
from test_page_tools_panel_browser import page_fixture  # noqa: F401
from test_styles import flow, confirm, dispatch  # noqa: F401
from test_visual_styles import completed

pytestmark = pytest.mark.browser


@contextmanager
def browser_for(project):
    from playwright.sync_api import sync_playwright
    server = WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(server.start())
            page.get_by_role('heading', name='制作总览', exact=True).wait_for()
            yield page, server
            assert errors == []
        finally:
            destination = os.environ.get('DECK_MASTER_PR104_EVIDENCE_DIR')
            if destination:
                path = Path(destination); path.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(path / (project.parent.name + '.png')), full_page=True, animations='disabled')
            browser.close(); server.stop()


def save_ui(store, name, content, *, layer='svg'):
    doc = store.load_document(); project = layer == 'notes'
    draft = {'schema_version': 'ui_draft.v1', 'draft_id': name, 'project_id': doc['project_id'],
             'project_identity': ui_journal.list_drafts(store.project_root)['project_identity'],
             'target': {'scope': 'project' if project else 'page', 'page_id': None if project else 'p01', 'layer': layer},
             'base_revision': doc['revision_id'], 'base_ref': None if project else doc['pages'][0]['svg'],
             'content': {'text': name, **content}, 'pending': None}
    return ui_journal.save(store.project_root, draft=draft)['record']


def restore(page, name, *, style=False):
    from playwright.sync_api import expect
    if style:
        detail = page.locator('.style-calibration > details').filter(has_text='个人草稿与恢复')
    else:
        page.get_by_role('button', name='笔记', exact=True).click()
        detail = page.locator('details.source-detail').filter(has_text='恢复、下载与版本详情')
    if not detail.evaluate('n => n.open'):
        detail.locator(':scope > summary').click()
    select = page.get_by_label('恢复项目中的个人草稿', exact=True)
    expect(select.locator(f'option[value="{name}"]')).to_be_attached()
    select.select_option(name)
    if page.get_by_role('button', name='打开所选草稿', exact=True).is_visible():
        page.get_by_role('button', name='打开所选草稿', exact=True).click()
    expect(page.get_by_label('个人草稿', exact=True)).to_have_value(name)


def open_page(page, server, store, *, layer='svg'):
    base = server.start().split('#')[0]
    identity = page.request.get(base + 'api/project').json()['project_identity']
    page.goto(base + '#' + urlencode({'project': identity, 'surface': 'page', 'page': 'p01', 'layer': layer}))
    page.locator('.page-tools').wait_for()


def opinions(store):
    doc = store.load_document(); entry = doc['pages'][0]
    notes = [{'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
              'scope': 'page', 'page_id': 'p01', 'page_ref': entry['page'], 'intent': 'clarify',
              'body': body, 'status': 'open', 'location': {'kind': 'whole'}} for body in ('意见 A', '意见 B')]
    annotation_service.save(store.project_root, input={'schema_version': 'annotation_batch.v1',
        'project_id': doc['project_id'], 'annotations': notes}, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    return annotation_service.list_annotations(store.project_root)['annotations']


@pytest.mark.parametrize('replacement', ['B', 'empty', 'absent'])
def test_icon_editor_replacement_rebuilds_selection_and_rejects_late_reads(icon_store, replacement):
    from playwright.sync_api import expect
    rows = opinions(icon_store); refs = [row['ref'] for row in rows]
    save_ui(icon_store, 'draft-A', {'icon_ui': {'method': 'redraw', 'annotation_refs': [refs[0]]}})
    b = {'method': 'redraw', 'annotation_refs': [refs[1]] if replacement == 'B' else []}
    save_ui(icon_store, 'draft-B', {} if replacement == 'absent' else {'icon_ui': b})
    with browser_for(icon_store.project_root) as (page, server):
        open_page(page, server, icon_store)
        restore(page, 'draft-A')
        page.get_by_role('button', name='图标优化', exact=True).click()
        boxes = page.locator('.icon-opinions input')
        expect(boxes).to_have_count(2); expect(boxes.nth(0)).to_be_checked()
        # Refresh the same editor with an unsaved choice; it must survive.
        boxes.nth(1).check()
        page.get_by_role('button', name='刷新图标方案', exact=True).click()
        expect(boxes.nth(1)).to_be_checked()
        held = []
        def hold_notes(route):
            if not held:
                held.append((route, route.fetch()))
                page.evaluate('() => window.notesHeld=true')
            else: route.continue_()
        page.route('**/api/annotations', hold_notes)
        page.get_by_role('button', name='刷新图标方案', exact=True).click()
        page.wait_for_function('() => window.notesHeld===true')
        restore(page, 'draft-B')
        page.get_by_role('button', name='图标优化', exact=True).click()
        expect(boxes).to_have_count(2)
        expect(boxes.nth(0)).not_to_be_checked()
        if replacement == 'B': expect(boxes.nth(1)).to_be_checked()
        else: expect(boxes.nth(1)).not_to_be_checked()
        assert held
        held[0][0].fulfill(response=held[0][1])
        expect(boxes.nth(0)).not_to_be_checked()
        # Empty / missing icon_ui cannot copy A; a newly selected B is exact.
        boxes.nth(1).check()
        page.evaluate("() => Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.iconCopy=text}})")
        page.get_by_role('button', name='复制给 Agent 的图标要求', exact=True).click()
        page.wait_for_function('() => Boolean(window.iconCopy)')
        payload = page.evaluate('JSON.parse(window.iconCopy)')
        assert payload['annotation_refs'] == [refs[1]]
        assert payload['opinions'] == [rows[1]['annotation']]
        final = ui_journal.get(icon_store.project_root, 'draft-B')['record']['draft']['content']['icon_ui']
        assert final['annotation_refs'] == [refs[1]]


@pytest.mark.parametrize('method', ['reuse', 'standard'])
def test_icon_method_restoration_is_independent_of_failed_catalog(icon_store, method):
    from playwright.sync_api import expect
    rows = opinions(icon_store)
    sample = {'sample_candidate_id': 'synthetic-adopted', 'sample_icon_index': 0,
              'page_id': 'p02', 'label': '合成已采用样例', 'semantic_key': 'cross', 'style': {}}
    save_ui(icon_store, 'draft-method', {'icon_ui': {'method': method, 'asset': 'workflow',
        'sample_identity': sample, 'annotation_refs': [rows[0]['ref']]}})
    with browser_for(icon_store.project_root) as (page, server):
        page.route('**/api/icons/catalog', lambda route: route.abort())
        page.route('**/api/icons/list?*', lambda route: route.fulfill(json={'proposals': [], 'recipes': [], 'samples': [sample]}))
        open_page(page, server, icon_store)
        page.get_by_role('button', name='图标优化', exact=True).click()
        expect(page.get_by_label('图标处理方式')).to_have_value(method)
        expect(page.get_by_role('button', name='重新读取标准目录')).to_be_visible()
        expect(page.locator('.icon-opinions input').first).to_be_checked()
        page.evaluate("() => Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.iconCopy=text}})")
        page.get_by_role('button', name='复制给 Agent 的图标要求', exact=True).click()
        if method == 'reuse':
            page.wait_for_function('() => Boolean(window.iconCopy)')
            assert page.evaluate('JSON.parse(window.iconCopy).requested_method') == 'reuse'
            assert page.evaluate('JSON.parse(window.iconCopy).adopted_sample') == sample
        else:
            expect(page.locator('.icon-workbench [role=status]')).to_contain_text('标准目录')
            assert page.evaluate('window.iconCopy === undefined')
        saved = ui_journal.get(icon_store.project_root, 'draft-method')['record']['draft']['content']['icon_ui']
        assert saved['method'] == method and saved['asset'] == 'workflow' and saved['sample_identity'] == sample
        page.unroute('**/api/icons/catalog')
        page.get_by_role('button', name='重新读取标准目录').click()
        expect(page.get_by_label('建议的标准图标')).to_have_value('workflow')
        expect(page.get_by_label('图标处理方式')).to_have_value(method)


@pytest.mark.parametrize('layer', ['original_image', 'svg', 'ppt'])
@pytest.mark.parametrize('same', [True, False])
def test_icon_opinion_basis_maps_each_layer_exactly(icon_store, layer, same):
    from playwright.sync_api import expect
    from test_workbench_actions import commit
    doc = copy.deepcopy(icon_store.load_document()); entry = doc['pages'][0]
    if layer == 'ppt':
        artifact = icon_store.read_object_json(entry['blueprint']); artifact['role'] = 'ppt_preview'
        entry['ppt_preview'] = icon_store.put_json_object(artifact)
        commit(icon_store, doc, str(uuid.uuid4())); doc = icon_store.load_document(); entry = doc['pages'][0]
    key = {'original_image': 'blueprint', 'svg': 'svg', 'ppt': 'ppt_preview'}[layer]
    ref = entry[key]
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
            'scope': 'artifact', 'page_id': 'p01', 'page_ref': entry['page'], 'layer': layer, 'artifact_ref': ref,
            'intent': 'clarify', 'body': '核对图层依据', 'status': 'open', 'location': {'kind': 'whole'}}
    annotation_service.save(icon_store.project_root, input={'schema_version': 'annotation_batch.v1',
        'project_id': doc['project_id'], 'annotations': [note]}, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    if not same:
        current = copy.deepcopy(icon_store.load_document())
        changed = icon_store.read_object_json(ref); changed['limitations'] = ['Synthetic changed artifact reference']
        current['pages'][0][key] = icon_store.put_json_object(changed)
        commit(icon_store, current, str(uuid.uuid4()))
    with browser_for(icon_store.project_root) as (page, server):
        open_page(page, server, icon_store)
        page.get_by_role('button', name='图标优化', exact=True).click()
        label = page.locator('.icon-opinion').filter(has_text='核对图层依据')
        expect(label).to_contain_text('与当前产物一致' if same else '旧底稿意见')


def visual_setup(flow):
    ref, task, row = completed(flow)
    state = {'ids': [row['reference_id']], 'targets': ['p02', 'p03'], 'instruction': '保留目标内容',
             'task_id': task['task_id'], 'recipe': None,
             'spec_edits': {'ref': ref['sha256'], 'dimensions': {'palette': 'blue #225588', 'typography': '保留文字层级'}}}
    save_ui(flow.store, 'visual-A', {'style_source': 'screenshot', 'visual_style': state}, layer='notes')
    return state


def visual_open(page):
    from playwright.sync_api import expect
    page.get_by_role('button', name='风格校准', exact=True).click()
    expect(page.get_by_label('风格参考来源')).to_have_value('screenshot')
    page.get_by_text('调整借用维度', exact=True).click()
    expect(page.get_by_label('配色规范', exact=True)).to_have_value('blue #225588')


def hold_confirmation(page):
    held = []
    def delay(route):
        held.append((route, route.fetch()))
        page.evaluate('() => window.confirmHeld = true')
    page.route('**/api/styles/confirm', delay)
    page.get_by_role('button', name='检查并确认视觉规范', exact=True).click()
    page.wait_for_function('() => window.confirmHeld === true')
    return held[0]


def test_screenshot_confirmation_freezes_all_formal_inputs_and_plan_matches(flow):
    from playwright.sync_api import expect
    visual_setup(flow)
    with browser_for(flow.project) as (page, _server):
        visual_open(page)
        route, response = hold_confirmation(page)
        for label in ['配色规范', '文字层级规范', '借用截图配色', '借用截图构图',
                      '确认使用的已注册字体', '截图风格试作目标']:
            expect(page.get_by_label(label, exact=True)).to_be_disabled()
        expect(page.get_by_label('配色规范')).to_have_value('blue #225588')
        route.fulfill(response=response)
        receipt = response.json()['operation_result']
        page.wait_for_function('id => location.hash.includes(id)', arg=receipt['revision_id'])
        trial = page.locator('.visual-style button').filter(has_text='预览单页试作')
        expect(trial).to_be_enabled()
        from test_visual_styles_browser import open_visual_phase
        open_visual_phase(page, 2)
        with page.expect_response('**/api/styles/plan') as result:
            trial.click()
        assert result.value.ok, result.value.json()
        assert result.value.request.post_data_json['input']['page_ids'] == ['p02']
        assert result.value.request.post_data_json['input']['recipe_id'] == receipt['recipe_id']
        recipe = styles.show(flow.project, recipe_id=receipt['recipe_id'])['recipe']
        assert recipe['dimensions']['palette'] == 'blue #225588'
        assert set(recipe['dimensions']) == {'palette', 'typography'}
        assert not recipe['input'].get('font_id')


@pytest.mark.parametrize('changed', ['palette', 'font', 'dimensions'])
def test_screenshot_old_confirmation_cannot_mark_a_restored_draft_confirmed(flow, changed):
    from playwright.sync_api import expect
    state = visual_setup(flow); other = copy.deepcopy(state)
    other['spec_edits']['dimensions']['palette'] = 'red #ff0000'
    if changed == 'font': other['font_id'] = flow.store.load_document()['design_context']['fonts'][0]['font_id']
    if changed == 'dimensions': other['spec_edits']['dimensions'] = {'palette': 'red #ff0000', 'composition': '居中构图'}
    save_ui(flow.store, 'visual-B', {'style_source': 'screenshot', 'visual_style': other}, layer='notes')
    with browser_for(flow.project) as (page, _server):
        page.get_by_role('button', name='风格校准', exact=True).click()
        restore(page, 'visual-A', style=True)
        page.get_by_text('调整借用维度', exact=True).click()
        route, response = hold_confirmation(page)
        restore(page, 'visual-B', style=True)
        expect(page.get_by_label('配色规范')).to_have_value('red #ff0000')
        route.fulfill(response=response)
        expect(page.locator('.business-pending')).to_be_hidden()
        expect(page.get_by_label('配色规范')).to_have_value('red #ff0000')
        expect(page.locator('.visual-style button').filter(has_text='预览单页试作')).to_be_disabled()
        final = ui_journal.get(flow.project, 'visual-B')['record']['draft']['content']['visual_style']
        assert final['recipe'] is None and final['spec_edits'] == other['spec_edits']
        assert final.get('font_id') == other.get('font_id')
        recipe = styles.show(flow.project, recipe_id=response.json()['operation_result']['recipe_id'])['recipe']
        assert recipe['dimensions']['palette'] == 'blue #225588'


def test_primary_style_target_survives_restore_confirm_refresh_and_first_plan(flow):
    from playwright.sync_api import expect
    with browser_for(flow.project) as (page, _server):
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_label('风格参考原图').select_option('p01')
        primary = page.locator('.style-calibration').get_by_role('combobox', name='当前风格试作目标', exact=True)
        primary.select_option('p02')
        # The preview deliberately shares the target's accessible description.
        # Wait until it is present to cover slow image-pool scheduling as in CI,
        # then select through the actual form control rather than a label alias.
        expect(page.locator('.style-primary-target [aria-label="当前风格试作目标"]')).to_be_attached()
        primary.select_option('p03')
        expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
        records = ui_journal.list_drafts(flow.project)['records']
        saved = next(r['draft'] for r in records if r['draft']['content'].get('style_calibration'))
        assert saved['content']['style_calibration']['targets'] == ['p03', 'p02']
        page.reload(); expect(primary).to_have_value('p03')
        page.get_by_role('button', name='检查风格要求', exact=True).click()
        with page.expect_response('**/api/styles/confirm') as confirmation:
            page.get_by_role('button', name='确认这版风格要求', exact=True).click()
        receipt = confirmation.value.json()['operation_result']
        page.wait_for_function('id => location.hash.includes(id)', arg=receipt['revision_id'])
        recipe = styles.show(flow.project, recipe_id=receipt['recipe_id'])['recipe']
        assert recipe['input']['target_page_ids'] == ['p03', 'p02']
        page.get_by_role('button', name='刷新风格版本', exact=True).click()
        expect(page.get_by_label('先试哪一页')).to_have_value('p03')
        page.locator('.style-calibration > .style-phase').nth(2).locator(':scope > summary').click()
        with page.expect_request('**/api/styles/plan') as planned:
            page.locator('.style-calibration > .style-phase').nth(2).get_by_role('button', name='预览单页试作').click()
        assert planned.value.post_data_json['input']['page_ids'] == ['p03']


@pytest.mark.parametrize('area', ['版本', '文件'])
def test_leaving_task_context_rebuilds_without_reload(flow, area):
    from playwright.sync_api import expect
    task = dispatch(flow, confirm(flow))
    with browser_for(flow.project) as (page, server):
        base = server.start().split('#')[0]; identity = page.request.get(base + 'api/project').json()['project_identity']
        page.goto(base + '#' + urlencode({'project': identity, 'surface': 'runs', 'task': task['task_id']}))
        expect(page.locator('.run-detail')).to_contain_text(task['task_id'])
        page.evaluate('() => window.sameDocument = "retained"')
        page.get_by_role('button', name=area, exact=True).click()
        expect(page.locator('#view-title')).to_have_text('任务与交付')
        page.get_by_role('button', name='正在进行', exact=True).click()
        expect(page.locator('.run-detail')).to_be_empty()
        expect(page.locator('.run-rows')).to_be_visible()
        expect(page.locator('#view-title')).to_have_text('任务与交付')
        assert 'task=' not in page.url and page.evaluate('window.sameDocument') == 'retained'
        page.locator(f'[data-task-id="{task["task_id"]}"]').get_by_role('button', name='查看这项任务').click()
        expect(page.locator('.run-detail')).to_contain_text(task['task_id'])


@pytest.mark.parametrize('mode', ['点标注', '框选模式'])
@pytest.mark.parametrize('face', ['详情', '图标优化', '笔记', '试作与候选'])
def test_hidden_opinion_tool_stops_canvas_mutation_and_keeps_existing_regions(page_fixture, mode, face):
    from playwright.sync_api import expect
    page, server, _path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_page(page, server, store, layer='original_image')
    page.get_by_label('意见正文', exact=True).fill('保留已有正文与范围')
    page.get_by_text('范围与标注工具', exact=True).click()
    page.get_by_role('button', name=mode, exact=True).click()
    overlay = page.locator('.annotation-overlay'); overlay.wait_for()
    def mark():
        box = overlay.bounding_box(); x, y = box['x'] + box['width'] * .3, box['y'] + box['height'] * .3
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 30, y + 30); page.mouse.up()
    mark(); expect(page.locator('.annotation-mark:not(.saved)')).to_have_count(1)
    page.get_by_role('button', name=face, exact=True).click()
    assert overlay.evaluate('n => getComputedStyle(n).pointerEvents') == 'none'
    mark(); expect(page.locator('.annotation-mark:not(.saved)')).to_have_count(1)
    page.get_by_role('button', name='意见', exact=True).click()
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('保留已有正文与范围')
    expect(page.get_by_role('button', name='阅读模式', exact=True)).to_have_attribute('aria-pressed', 'true')


def test_copy_private_note_opens_opinions_focuses_body_and_keeps_note(page_fixture):
    from playwright.sync_api import expect
    page, server, _path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_page(page, server, store)
    page.get_by_role('button', name='笔记', exact=True).click()
    page.get_by_label('个人草稿', exact=True).fill('私人笔记保留原文')
    page.get_by_role('button', name='从私人笔记复制', exact=True).click()
    body = page.get_by_label('意见正文', exact=True)
    expect(body).to_be_visible(); expect(body).to_be_focused(); expect(body).to_have_value('私人笔记保留原文')
    expect(page.locator('.annotations-panel [role=status]').filter(has_text='已从私人笔记复制')).to_be_visible()
    page.get_by_role('button', name='笔记', exact=True).click()
    expect(page.get_by_label('个人草稿', exact=True)).to_have_value('私人笔记保留原文')


@pytest.mark.parametrize('mode', ['点标注', '框选模式'])
def test_closing_narrow_tools_keeps_intentional_canvas_annotation(page_fixture, mode):
    from playwright.sync_api import expect
    page, server, _path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_page(page, server, store, layer='original_image')
    page.get_by_text('范围与标注工具', exact=True).click()
    page.get_by_role('button', name=mode, exact=True).click()
    page.get_by_label('意见正文', exact=True).fill('窄屏收起工具仍有意标注')
    page.set_viewport_size({'width': 1024, 'height': 800})
    page.get_by_role('button', name='工具', exact=True).click()
    page.get_by_role('button', name='回到画面', exact=True).click()
    overlay = page.locator('.annotation-overlay')
    assert overlay.evaluate('n => getComputedStyle(n).pointerEvents') == 'auto'
    box = overlay.bounding_box(); x, y = box['x'] + box['width'] * .4, box['y'] + box['height'] * .4
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 25, y + 25); page.mouse.up()
    expect(page.locator('.annotation-mark:not(.saved)')).to_have_count(1)
    page.get_by_role('button', name='工具', exact=True).click()
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('窄屏收起工具仍有意标注')
    page.get_by_role('button', name='详情', exact=True).click()
    assert overlay.evaluate('n => getComputedStyle(n).pointerEvents') == 'none'


def test_private_autosave_does_not_retire_a_held_business_receipt(page_fixture):
    from playwright.sync_api import expect
    page, server, _path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_page(page, server, store, layer='original_image')
    held = []
    def hold(route):
        held.append((route, route.fetch())); page.evaluate('() => window.opinionHeld=true')
    page.route('**/api/annotations/batch', hold)
    page.get_by_role('button', name='整页意见', exact=True).click()
    page.get_by_label('意见正文', exact=True).fill('正式意见甲')
    page.get_by_role('button', name='保存意见', exact=True).click()
    page.wait_for_function('() => window.opinionHeld===true')
    page.get_by_role('button', name='笔记', exact=True).click()
    page.get_by_label('个人草稿', exact=True).fill('私人稿保存与正式回执相互独立')
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    expect(page.locator('.business-pending')).to_be_visible()
    records = ui_journal.list_drafts(store.project_root)['records']
    draft = next(r['draft'] for r in records if r['draft']['content']['text'] == '私人稿保存与正式回执相互独立')
    assert draft['pending'] is not None and len(store.load_document()['annotations']) == 1
    page.get_by_role('button', name='写新意见', exact=True).click()
    page.get_by_role('button', name='整页意见', exact=True).click()
    page.get_by_label('意见正文', exact=True).fill('正式意见乙')
    expect(page.get_by_role('button', name='保存意见', exact=True)).to_be_disabled()
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    held[0][0].fulfill(response=held[0][1]); page.unroute('**/api/annotations/batch')
    page.wait_for_function('''async id => {
      const data = await (await fetch('/api/drafts')).json();
      return data.records.some(r => r.draft.draft_id === id && r.draft.pending === null);
    }''', arg=draft['draft_id'])
    expect(page.locator('.business-pending')).to_be_hidden()
    page.wait_for_function('''async id => {
      const rows = (await (await fetch('/api/drafts')).json()).records;
      return rows.some(r => r.draft.draft_id===id && !r.draft.pending);
    }''', arg=draft['draft_id'])
    expect(page.get_by_role('button', name='保存意见', exact=True)).to_be_enabled()
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(page.locator('.saved-annotations')).to_contain_text('正式意见乙')
    assert len(store.load_document()['annotations']) == 2
