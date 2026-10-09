"""PR104 supplemental review: real UI/core, synthetic fixtures, zero Host calls."""
import copy
import json
import uuid
from urllib.parse import urlencode

import pytest

from deck_master import annotation_service, editing, ui_journal
from deck_master.models import bump_revision
from test_page_tools_panel_browser import page_fixture  # noqa: F401
from test_pr104_review_browser import browser_for
from test_styles import flow  # noqa: F401
from test_usability_pressure import module
from test_visual_styles import completed

pytestmark = pytest.mark.browser


def change_artifact(store, page_id, slot='blueprint'):
    doc = store.load_document(); updated = copy.deepcopy(doc)
    entry = next(row for row in updated['pages'] if row['page_id'] == page_id)
    artifact = store.read_object_json(entry[slot])
    artifact['limitations'] = ['Synthetic metadata change ' + uuid.uuid4().hex]
    entry[slot] = store.put_json_object(artifact)
    updated = bump_revision(updated, {'operation_id': str(uuid.uuid4()), 'kind': 'artifact_adoption',
        'description': 'Synthetic isolated artifact change', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated,
                        operation_id=updated['change']['operation_id'])
    return updated['revision_id']


def open_page(page, server, store, layer='original_image'):
    base = server.start(); page.goto(base)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(base + 'api/project').json()['project_identity']
    page.goto(base + '#' + urlencode({'project': identity, 'surface': 'page', 'page': 'p01',
        'layer': layer, 'revision': store.current_revision_id()}))
    page.locator('.page-tools').wait_for()


def test_page_history_offers_the_direct_before_snapshot_and_deduplicates_paging(page_fixture):
    from playwright.sync_api import expect
    page, server, _, store = page_fixture
    for _ in range(23):
        change_artifact(store, 'p01')
    before = change_artifact(store, 'p02')
    fixed = change_artifact(store, 'p01')
    rows = editing.history(store.project_root, revision=fixed, page_id='p01', limit=20)['revisions']
    assert rows[0]['revision_id'] == fixed and rows[0]['parent_revision_id'] == before
    assert before not in [row['revision_id'] for row in rows]
    open_page(page, server, store)
    page.get_by_text('页面操作', exact=True).click()
    page.get_by_role('button', name='比较此页版本', exact=True).click()
    select = page.get_by_role('combobox', name='选择同页比较版本', exact=True)
    expect(select.locator(f'option[value="{before}"]')).to_contain_text('修改前')
    expect(page.get_by_label('显示这页全部历史记录')).not_to_be_checked()
    select.select_option(before)
    page.get_by_role('button', name='固定比较这个版本', exact=True).click()
    left = page.get_by_label('页面内容', exact=True)
    right = page.get_by_label('比较版本内容', exact=True)
    expect(left).to_have_attribute('data-revision', fixed)
    expect(right).to_have_attribute('data-revision', before)
    expect(right.locator('canvas.page-image')).to_be_visible()
    more = page.get_by_role('button', name='更早的修改', exact=True)
    expect(more).to_be_enabled(); more.click(); expect(more).to_be_disabled()
    values = select.locator('option').evaluate_all('(nodes)=>nodes.map(node=>node.value)')
    assert len(values) == len(set(values)) and fixed not in values
    expect(select).to_have_value(before)
    expect(right).to_have_attribute('data-revision', before)


@pytest.mark.parametrize('note_layer,display_layer', [
    ('original_image', 'svg'), ('svg', 'original_image'), ('ppt', 'svg'), ('content', 'svg'),
])
def test_same_page_other_layer_opinion_is_selectable_and_reaches_core_plan(page_fixture, note_layer, display_layer):
    from playwright.sync_api import expect
    page, server, _, store = page_fixture
    doc = store.load_document(); entry = doc['pages'][0]
    if note_layer == 'ppt':
        # A real readable PNG artifact with a disclosed synthetic PPT-preview role.
        artifact = store.read_object_json(entry['blueprint']); artifact['role'] = 'ppt_preview'
        entry['ppt_preview'] = store.put_json_object(artifact)
        updated = bump_revision(doc, {'operation_id': str(uuid.uuid4()), 'kind': 'artifact_adoption',
            'description': 'Synthetic PPT preview', 'read_set': []})
        store.commit_change(base_revision=doc['revision_id'], document=updated,
                            operation_id=updated['change']['operation_id'])
        doc = store.load_document(); entry = doc['pages'][0]
    slot = {'original_image': 'blueprint', 'svg': 'svg', 'ppt': 'ppt_preview', 'content': 'page'}[note_layer]
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
        'scope': 'artifact', 'page_id': 'p01', 'page_ref': entry['page'], 'layer': note_layer,
        'artifact_ref': entry[slot], 'intent': 'clarify', 'body': '跨图层的本页要求',
        'status': 'open', 'location': {'kind': 'whole'}}
    annotation_service.save(store.project_root, input={'schema_version': 'annotation_batch.v1',
        'project_id': doc['project_id'], 'annotations': [note]}, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    ref = annotation_service.list_annotations(store.project_root)['annotations'][0]['ref']
    open_page(page, server, store, display_layer)
    page.locator('details.saved-group').filter(has_text='本页其它图层').locator('summary').click()
    card = page.locator(f'.saved-opinion[data-ref="{ref["sha256"]}"]')
    check = card.get_by_role('checkbox'); expect(check).to_be_enabled(); check.check()
    expect(page.get_by_label('修改要求', exact=True)).to_have_value(note['body'])
    with page.expect_request(lambda request: '/api/changes/plan' in request.url) as sent:
        page.get_by_role('button', name='预览修改影响', exact=True).click()
    payload = sent.value.post_data_json['input']
    assert payload['annotation_refs'] == [ref] and payload['targets'][0]['layer'] == display_layer
    expect(page.locator('.change-plan-preview')).to_contain_text('修改影响预览')
    # A routine read must preserve the same legal selection and its persisted refs.
    expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
    page.reload(); page.locator('.page-tools').wait_for()
    expect(card.locator('input[type=checkbox]')).to_be_checked()
    records = ui_journal.list_drafts(store.project_root)['records']
    assert any(row['draft']['content'].get('requirement', {}).get('annotation_refs') == [ref] for row in records)


@pytest.mark.parametrize('invalid', ['own_layer_changed', 'own_layer_missing', 'other_page', 'page_changed'])
def test_other_layer_opinion_keeps_its_own_staleness_and_page_gates(page_fixture, invalid):
    from playwright.sync_api import expect
    page, server, _, store = page_fixture
    doc = store.load_document(); entry = doc['pages'][1 if invalid == 'other_page' else 0]
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
        'scope': 'artifact', 'page_id': entry['page_id'], 'page_ref': entry['page'], 'layer': 'original_image',
        'artifact_ref': entry['blueprint'], 'intent': 'clarify', 'body': '不应迁移的意见',
        'status': 'open', 'location': {'kind': 'whole'}}
    annotation_service.save(store.project_root, input={'schema_version': 'annotation_batch.v1',
        'project_id': doc['project_id'], 'annotations': [note]}, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    ref = annotation_service.list_annotations(store.project_root)['annotations'][0]['ref']
    if invalid == 'own_layer_changed':
        change_artifact(store, 'p01')
    elif invalid in ('own_layer_missing', 'page_changed'):
        doc = store.load_document(); updated = copy.deepcopy(doc)
        if invalid == 'own_layer_missing':
            updated['pages'][0]['blueprint'] = None
        else:
            body = store.read_object_json(updated['pages'][0]['page']); body['customer_visible']['title'] += ' changed'
            updated['pages'][0]['page'] = store.put_json_object(body)
        updated = bump_revision(updated, {'operation_id': str(uuid.uuid4()), 'kind': 'task_update',
            'description': 'Synthetic unavailable annotation basis', 'read_set': []})
        store.commit_change(base_revision=doc['revision_id'], document=updated,
                            operation_id=updated['change']['operation_id'])
    open_page(page, server, store, 'svg')
    expect(page.locator(f'.saved-opinion[data-ref="{ref["sha256"]}"]').locator('input[type=checkbox]')).to_be_disabled()


@pytest.mark.parametrize('reading', ['current', 'historical', 'readonly'])
def test_pressure_history_and_full_breakdown_use_visible_production_controls(flow, reading):
    from playwright.sync_api import expect
    _, task, row = completed(flow)
    for _ in range(25):
        change_artifact(flow.store, 'p03')
    fixed = flow.store.current_revision_id()
    if reading == 'historical':
        change_artifact(flow.store, 'p02')
    elif reading == 'readonly':
        marker = flow.project / '.deckmaster/workbench/sample.json'
        value = json.loads(marker.read_text()); value['readonly'] = True
        marker.write_text(json.dumps(value))
    pressure = module('w10_pressure'); info = ui_journal.project_info(flow.project)
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='任务与交付', exact=True).click()
        expect(page.get_by_role('button', name='正在进行', exact=True)).to_have_attribute('aria-pressed', 'true')
        expect(page.locator('[aria-label="阅读历史版本"]')).to_be_hidden()
        counts = {}
        pressure.read_history_phase(page, counts)
        expect(page.get_by_role('combobox', name='阅读历史版本')).to_be_visible()
        assert counts == {'history_paging': 1}
        state = {'ids': [row['reference_id']], 'targets': ['p02'], 'task_id': task['task_id'],
                 'instruction': 'Synthetic pressure read only', 'recipe': None}
        page.evaluate('(args)=>localStorage.setItem(args[0],JSON.stringify(args[1]))',
                      ['deck-master:visual-style:' + info['project_identity'], state])
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
        if reading == 'historical':
            page.goto(page.url.split('#')[0] + '#' + urlencode({'project': info['project_identity'],
                'surface': 'style', 'revision': fixed}))
            page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
        expect(page.get_by_role('button', name='查看完整拆解图', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='查看完整拆解图', exact=True)).to_be_enabled()
        if reading != 'current':
            expect(page.get_by_role('button', name='检查并确认视觉规范', exact=True)).to_be_disabled()
            expect(page.get_by_label('配色规范', exact=True)).to_be_disabled()
        assert page.locator('.visual-style').get_by_text('查看视觉拆解图', exact=True).count() == 0
        pressure.read_breakdown_phase(page, counts)
        expect(page.get_by_role('dialog')).not_to_be_visible()
        assert counts['breakdown_reading'] == 1
        assert page.evaluate("document.activeElement?.textContent") == '查看完整拆解图'
        page.get_by_role('button', name='整稿画廊', exact=True).click()
        expect(page.locator('.gallery-viewport')).to_be_visible()


def test_pressure_candidate_phase_opens_the_decisions_subarea(tmp_path):
    from playwright.sync_api import expect
    factory = module('w01_pressure'); pressure = module('w10_pressure')
    project = tmp_path / 'synthetic-pressure-candidates'
    factory.create_fixture(project, page_count=24)
    with browser_for(project) as (page, _):
        page.get_by_role('button', name='任务与交付', exact=True).click()
        expect(page.locator('.candidate-batch-row').first).to_be_hidden()
        pressure.read_candidate_phase(page)
        expect(page.locator('.candidate-desk')).to_be_visible()
        expect(page.locator('.candidate-column').last.locator('[data-image-state=ready]')).to_be_visible()
