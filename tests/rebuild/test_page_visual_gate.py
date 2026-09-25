"""Pre-compile SVG acceptance and one-page visual review workflow."""
from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest
from PIL import Image

from deck_master import service
from deck_master.store import Store
from deck_master.tasks import EnvelopeError, TaskConflict
from page_visual_helpers import make_page_reviews, pass_page_review
from test_service_flow import _blueprint_envelope, _draft_page, _png_bytes, _svg_for


def _accept(project, task, envelope, *, file_name=None, data=None):
    if file_name:
        staging = project / '.deckmaster' / 'staging' / task['operation_id']
        staging.mkdir(parents=True, exist_ok=True)
        (staging / file_name).write_bytes(data)
    return service.accept_result(project, task_id=task['task_id'],
                                 operation_id=task['operation_id'],
                                 produced_against=task['produced_against'],
                                 result_payload=envelope)


def _start(project, page_id):
    store = Store(project)
    task = service.continue_project(project)['pending_tasks'][0]
    assert task['kind'] == 'blueprint'
    entry = next(e for e in store.load_document()['pages'] if e['page_id'] == page_id)
    _accept(project, task, _blueprint_envelope({'page_id': page_id, 'ref': entry['page']}),
            file_name='reference.png', data=_png_bytes())
    task = service.continue_project(project)['pending_tasks'][0]
    assert task['kind'] == 'reconstruct'
    entry = next(e for e in store.load_document()['pages'] if e['page_id'] == page_id)
    blueprint_sha = store.read_object_json(entry['blueprint'])['file']['sha256']
    page = store.read_object_json(entry['page'])
    svg = _svg_for(page).replace(b'<svg ', f'<svg data-blueprint-sha256="{blueprint_sha}" '.encode(), 1)
    return task, svg


def _svg_envelope(page_id, kind='reconstruct'):
    return {'kind': kind,
            'files': [{'file_id': 's', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
            'artifact_specs': [{'file_id': 's', 'role': 'svg', 'page_id': page_id,
                                'provenance': {'source_type': 'unknown', 'tool': 'test-host',
                                               'invocation_ref': None}}]}


def test_unsupported_svg_is_rejected_on_current_page_before_adoption(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='SVG 预检', draft={'pages': [_draft_page('p1', '标题', '正文。')]})
    task, svg = _start(project, 'p1')
    bad = svg.replace(b'</svg>', b'<line id="bad-line" x1="1" y1="1" x2="9" y2="9" stroke="red" stroke-dasharray="4 2"/></svg>')
    before = Store(project).load_document()
    with pytest.raises(EnvelopeError, match='p1/bad-line.*stroke-dasharray'):
        _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=bad)
    after = Store(project).load_document()
    assert after['pages'][0]['svg'] is None
    assert after['revision_id'] == before['revision_id']
    assert _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)['status'] == 'accepted'


def test_compose_new_page_svg_uses_same_preflight_and_atomic_adoption(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='完整稿')
    task = service.continue_project(project)['pending_tasks'][0]
    page = _draft_page('p1', '标题', '正文。')
    svg = _svg_for(page)
    envelope = {'kind': 'compose', 'pages': [page], 'page_order': ['p1'],
                'files': [{'file_id': 's', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
                'artifact_specs': [{'file_id': 's', 'role': 'svg', 'page_id': 'p1',
                                    'provenance': {'source_type': 'unknown', 'tool': 'test-host',
                                                   'invocation_ref': None}}]}
    bad = svg.replace(b'</svg>', b'<line id="bad" x1="1" y1="1" x2="9" y2="9" stroke="red" stroke-dasharray="4 2"/></svg>')
    before = Store(project).load_document()
    with pytest.raises(EnvelopeError, match='p1/bad.*stroke-dasharray'):
        _accept(project, task, envelope, file_name='page.svg', data=bad)
    assert Store(project).load_document()['revision_id'] == before['revision_id']
    assert _accept(project, task, envelope, file_name='page.svg', data=svg)['status'] == 'accepted'
    assert Store(project).load_document()['pages'][0]['svg'] is not None


def test_compose_blueprint_and_svg_in_one_envelope_use_candidate_image(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='完整蓝图与 SVG')
    task = service.continue_project(project)['pending_tasks'][0]
    page = _draft_page('p1', '标题', '正文。')
    image = _png_bytes()
    svg = _svg_for(page).replace(b'<svg ',
        f'<svg data-blueprint-sha256="{hashlib.sha256(image).hexdigest()}" '.encode(), 1)
    envelope = {'kind': 'compose', 'pages': [page], 'page_order': ['p1'],
                'files': [{'file_id': 'b', 'path': 'reference.png', 'media_type': 'image/png'},
                          {'file_id': 's', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
                'artifact_specs': [
                    {'file_id': 's', 'role': 'svg', 'page_id': 'p1',
                     'provenance': {'source_type': 'unknown', 'tool': 'test-host', 'invocation_ref': None}},
                    {'file_id': 'b', 'role': 'blueprint', 'page_id': 'p1',
                     'provenance': {'source_type': 'unknown', 'tool': 'test-host', 'invocation_ref': None}}]}
    staging = project / '.deckmaster' / 'staging' / task['operation_id']
    staging.mkdir(parents=True, exist_ok=True)
    (staging / 'reference.png').write_bytes(image)
    (staging / 'page.svg').write_bytes(svg)
    assert _accept(project, task, envelope)['status'] == 'accepted'
    entry = Store(project).load_document()['pages'][0]
    assert entry['svg'] and entry['blueprint']


@pytest.mark.render
def test_page_review_blocks_next_blueprint_until_current_three_checks_pass(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='逐页审图', draft={'pages': [
        _draft_page('p1', '第一页', '正文一。'), _draft_page('p2', '第二页', '正文二。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    first = service.continue_project(project)
    visual = first['pending_tasks'][0]
    assert first['next_action'] == 'codex_review_page_visual'
    assert visual['kind'] == 'review' and visual['review_stage'] == 'page_visual'
    assert Store(project).load_document()['pages'][0]['svg_preview'] is not None
    assert service.continue_project(project)['pending_tasks'][0]['task_id'] == visual['task_id']
    with pytest.raises(EnvelopeError, match='requires exactly'):
        _accept(project, visual, {'kind': 'review', 'reviews': make_page_reviews(visual)[:1]})
    assert pass_page_review(project, visual)['status'] == 'accepted'
    next_step = service.continue_project(project)
    assert next_step['pending_tasks'][0]['kind'] == 'blueprint'
    assert next_step['pending_tasks'][0]['scope_pages'] == ['p2']
    second_task, second_svg = _start(project, 'p2')
    _accept(project, second_task, _svg_envelope('p2'), file_name='page.svg', data=second_svg)
    second_review = service.continue_project(project)['pending_tasks'][0]
    pass_page_review(project, second_review)
    final = service.continue_project(project)
    assert final['next_action'] == 'codex_review_renderings'
    assert final['pending_tasks'][0]['review_stage'] == 'final'
    assert final['pending_tasks'][0]['scope_pages'] == ['p1', 'p2']
    from deck_master.editing import check_summary
    assert check_summary(Store(project), Store(project).load_document())['status'] == 'not_evaluated'


@pytest.mark.render
def test_accepted_variance_on_same_page_advances_to_next_blueprint(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='合理差异', draft={'pages': [
        _draft_page('p1', '第一页', '正文一。'), _draft_page('p2', '第二页', '正文二。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    visual = service.continue_project(project)['pending_tasks'][0]
    reviews = make_page_reviews(visual)
    original = next(r for r in reviews if r['kind'] == 'blueprint_fidelity')
    original['status'] = 'needs_review'
    original['findings'] = [{'finding_id': 'overlap', 'kind': 'design',
                             'impact': 'needs_judgment', 'page_id': 'p1',
                             'element_refs': ['title'], 'message': '文本框相交',
                             'expected': '无可见遮挡', 'actual': '框边界相交',
                             'evidence': [], 'resolution': 'open'}]
    _accept(project, visual, {'kind': 'review', 'reviews': reviews})
    assert service.continue_project(project)['pending_tasks'][0]['kind'] == 'review'
    store = Store(project)
    doc = store.load_document()
    old_ref = next(ref for ref in doc['reviews']
                   if store.read_object_json(ref)['review_id'] == original['review_id'])
    recheck = service.continue_project(project)['pending_tasks'][0]
    accepted = make_page_reviews(recheck)
    replacement = next(r for r in accepted if r['kind'] == 'blueprint_fidelity')
    replacement['review_id'] = original['review_id']
    replacement['replaces'] = old_ref
    replacement['findings'] = [{**original['findings'][0], 'resolution': 'accepted_variance',
                                'resolution_reason': '字形未遮挡',
                                'evidence': [replacement['subjects'][3]]}]
    _accept(project, recheck, {'kind': 'review', 'reviews': accepted})
    next_task = service.continue_project(project)['pending_tasks'][0]
    assert next_task['kind'] == 'blueprint' and next_task['scope_pages'] == ['p2']


@pytest.mark.render
def test_failed_visual_review_requires_page_repair_and_evidenced_closure(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='逐页返修', draft={'pages': [
        _draft_page('p1', '第一页', '正文一。'), _draft_page('p2', '第二页', '正文二。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    review_task = service.continue_project(project)['pending_tasks'][0]
    reviews = make_page_reviews(review_task)
    failed = next(r for r in reviews if r['kind'] == 'blueprint_fidelity')
    failed['status'] = 'fail'
    failed['findings'] = [{'finding_id': 'missing-icon', 'kind': 'design', 'impact': 'must_fix',
                           'page_id': 'p1', 'element_refs': ['icon'], 'message': '图标缺失',
                           'expected': '图标存在', 'actual': '图标缺失', 'evidence': [],
                           'resolution': 'open'}]
    _accept(project, review_task, {'kind': 'review', 'reviews': reviews})
    repair = service.continue_project(project)['pending_tasks'][0]
    assert repair['kind'] == 'repair' and repair['review_stage'] == 'page_visual'
    assert repair['scope_pages'] == ['p1']
    changed = svg.replace(b'</svg>', b'<circle id="icon" cx="10" cy="10" r="5"/></svg>')
    _accept(project, repair, _svg_envelope('p1', 'repair'), file_name='page.svg', data=changed)
    recheck = service.continue_project(project)['pending_tasks'][0]
    assert recheck['kind'] == 'review' and recheck['review_stage'] == 'page_visual'
    assert recheck['scope_pages'] == ['p1']
    prior = next(x for x in recheck['prior_page_visual_findings'] if x['kind'] == 'blueprint_fidelity')
    corrected = make_page_reviews(recheck)
    fidelity = next(r for r in corrected if r['kind'] == 'blueprint_fidelity')
    fidelity['review_id'] = prior['review_id']
    fidelity['replaces'] = prior['review_ref']
    fidelity['findings'] = [{**deepcopy(failed['findings'][0]), 'resolution': 'fixed',
                            'evidence': [recheck['page_visual_requirements'][0]['subject_refs'][2]],
                            'resolution_reason': '已查看新 SVG 和预览中的图标'}]
    _accept(project, recheck, {'kind': 'review', 'reviews': corrected})
    assert service.continue_project(project)['pending_tasks'][0]['scope_pages'] == ['p2']


@pytest.mark.render
def test_unchanged_page_visual_repair_stops_without_another_repair_loop(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='无进展返修', draft={'pages': [_draft_page('p1', '标题', '正文。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    review_task = service.continue_project(project)['pending_tasks'][0]
    reviews = make_page_reviews(review_task)
    failed = next(r for r in reviews if r['kind'] == 'blueprint_fidelity')
    failed['status'] = 'fail'
    failed['findings'] = [{'finding_id': 'missing-icon', 'kind': 'design', 'impact': 'must_fix',
                           'page_id': 'p1', 'element_refs': ['icon'], 'message': '图标缺失',
                           'expected': '图标存在', 'actual': '图标缺失', 'evidence': [],
                           'resolution': 'open'}]
    _accept(project, review_task, {'kind': 'review', 'reviews': reviews})
    repair = service.continue_project(project)['pending_tasks'][0]
    _accept(project, repair, _svg_envelope('p1', 'repair'), file_name='page.svg', data=svg)
    result = service.continue_project(project)
    assert result['status'] == 'needs_input' and result['next_action'] == 'repair_no_progress'
    assert result['pending_tasks'] == []


@pytest.mark.render
def test_preflight_and_preview_share_approved_image_assets(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='批准图片', draft={'pages': [_draft_page('p1', '标题', '正文。')]})
    image = tmp_path / 'approved.png'
    Image.new('RGB', (20, 12), 'blue').save(image)
    service.import_asset(project, asset_id='approved', kind='image', file_path=image)
    task, _ = _start(project, 'p1')
    blueprint_sha = Store(project).read_object_json(Store(project).load_document()['pages'][0]['blueprint'])['file']['sha256']
    svg = (f'<svg viewBox="0 0 320 180" data-blueprint-sha256="{blueprint_sha}">'
           '<image href="approved" x="20" y="20" width="100" height="60"/></svg>').encode()
    assert _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)['status'] == 'accepted'
    visual = service.continue_project(project)['pending_tasks'][0]
    assert visual['review_stage'] == 'page_visual'
    assert Store(project).load_document()['pages'][0]['svg_preview']
    dependencies = visual['page_visual_requirements'][0]['dependencies']
    assert any(d['kind'] == 'asset' and d['identity'] == 'approved' for d in dependencies)


@pytest.mark.render
def test_missing_preview_renderer_blocks_next_page_with_tool_reason(tmp_path, monkeypatch):
    from deck_master import pipeline

    project = tmp_path / 'project'
    service.create(project, brief='缺渲染器', draft={'pages': [
        _draft_page('p1', '第一页', '正文一。'), _draft_page('p2', '第二页', '正文二。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    original = pipeline.executable

    def missing(name):
        if name == 'rsvg-convert':
            raise pipeline.NeedsTool('rsvg-convert unavailable; configure DECK_MASTER_RSVG_CONVERT')
        return original(name)

    monkeypatch.setattr(pipeline, 'executable', missing)
    result = service.continue_project(project)
    assert result['status'] == 'needs_tool'
    assert 'rsvg-convert unavailable' in result['findings'][0]
    assert Store(project).load_document()['pages'][1]['blueprint'] is None


@pytest.mark.render
def test_page_review_cannot_pass_after_design_asset_change(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='过期逐页审图', draft={'pages': [_draft_page('p1', '标题', '正文。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    visual = service.continue_project(project)['pending_tasks'][0]
    image = tmp_path / 'new-asset.png'
    Image.new('RGB', (20, 12), 'green').save(image)
    service.import_asset(project, asset_id='new-asset', kind='image', file_path=image)
    with pytest.raises(TaskConflict, match='after cancellation'):
        pass_page_review(project, visual)
    replacement = service.continue_project(project)['pending_tasks'][0]
    assert replacement['review_stage'] == 'page_visual'
    assert replacement['task_id'] != visual['task_id']
    assert pass_page_review(project, replacement)['status'] == 'accepted'


@pytest.mark.render
def test_style_change_retires_open_review_and_rebuilds_only_current_page(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='样式调整续跑', draft={'pages': [
        _draft_page('p1', '第一页', '正文一。'), _draft_page('p2', '第二页', '正文二。')]})
    task, svg = _start(project, 'p1')
    _accept(project, task, _svg_envelope('p1'), file_name='page.svg', data=svg)
    visual = service.continue_project(project)['pending_tasks'][0]
    store = Store(project)
    design = deepcopy(store.load_document()['design_context'])
    design['styles'][0]['colors']['accent'] = '#00AA66'
    service.update_design(project, design_context=design)
    changed = store.load_document()
    assert changed['pages'][0]['svg'] is None
    assert changed['pages'][1]['blueprint'] is None
    old_task = next(store.read_object_json(ref) for ref in changed['tasks']
                    if store.read_object_json(ref)['task_id'] == visual['task_id'])
    assert old_task['status'] == 'superseded'
    with pytest.raises(TaskConflict, match='after cancellation'):
        pass_page_review(project, visual)
    reconstruct = service.continue_project(project)['pending_tasks'][0]
    assert reconstruct['kind'] == 'reconstruct' and reconstruct['scope_pages'] == ['p1']
    _accept(project, reconstruct, _svg_envelope('p1'), file_name='page.svg', data=svg)
    replacement = service.continue_project(project)['pending_tasks'][0]
    assert replacement['kind'] == 'review' and replacement['task_id'] != visual['task_id']
    pass_page_review(project, replacement)
    assert service.continue_project(project)['pending_tasks'][0]['scope_pages'] == ['p2']
