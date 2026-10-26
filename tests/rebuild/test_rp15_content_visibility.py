"""RP-15 synthetic projection/freeze compatibility; never image quality evidence."""
import copy

import pytest

from deck_master import content_plan, generation, models, production, service, tasks
from deck_master.models import ModelError
from test_rc3_design_requirements import _snapshot, _resolve, _replace_plan
from test_rc3_notes_visual_inputs import _blueprint_with_imported_plan


@pytest.mark.parametrize('profile', ['simple', 'evidence', 'mechanism', 'data_dense', 'mixed'])
def test_profile_and_internal_density_are_not_an_additional_copy_source(tmp_path, profile):
    store, doc, plan = _snapshot(tmp_path)
    plan['input']['page_roles'][0].update(content_profile=profile,
        density_rationale='内部核验：来源定位 L42；作者已核对账本。为两项业务条件保留空间。')
    _replace_plan(store, doc, plan)
    resolved = {**models.default_design_context(), **_resolve(store, doc)}
    page = store.read_object_json(doc['pages'][0]['page'])
    before = copy.deepcopy(page)
    request = production.project_prompt(page, resolved, [])
    req = request['projection']['content_requirements']
    assert req['text_visibility'] == 'customer_visible_only.v1'
    assert req['content_profile'] == profile and req['required_qualifications'] == ['q1']
    assert '内部核验' in req['density_rationale']  # Actual design rationale remains inspectable.
    assert request['projection']['customer_visible'] == before['customer_visible']
    assert '内部核验' not in str(request['projection']['customer_visible'])
    assert request['projection']['customer_visible']['footnotes'][0]['text'] == '仅比较指定记录，不外推节约率。'
    assert 'customer_visible is the ONLY source of text to render' in request['prompt']
    assert 'required_qualifications contains Narrative node IDs, never copy to print' in request['prompt']
    assert 'return the gap to the content stage' in request['prompt']
    assert page == before


def test_legal_source_and_assumption_language_is_not_keyword_filtered(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['footnotes'][0]['text'] = '来源：公开统计年鉴；仅在既定容量假设下适用。'
    request = production.project_prompt(page, {**models.default_design_context(), **_resolve(store, doc)}, [])
    assert request['projection']['customer_visible']['footnotes'] == page['customer_visible']['footnotes']
    assert '来源：公开统计年鉴；仅在既定容量假设下适用。' in request['prompt']


def test_qualification_ids_are_real_project_nodes_and_empty_is_valid(tmp_path):
    store, doc, plan = _snapshot(tmp_path)
    value = copy.deepcopy(plan['input'])
    # No hardcoded product registry of project-specific IDs; existing q-new is legal.
    value['page_roles'][0]['required_qualifications'] = ['q-new']
    content_plan.validate_plan_input_v2(store, doc, value)
    value['page_roles'][0]['required_qualifications'] = []
    content_plan.validate_plan_input_v2(store, doc, value)
    for invalid in ['unknown-node', 'n1', '仅比较指定记录，不外推节约率。']:
        value['page_roles'][0]['required_qualifications'] = [invalid]
        with pytest.raises(content_plan.ContentPlanError, match='qualifications must name actual qualification nodes'):
            content_plan.validate_plan_input_v2(store, doc, value)


def test_visibility_policy_is_strict_and_legacy_defaults_are_unknown(tmp_path):
    store, doc, _ = _snapshot(tmp_path, legacy=True)
    req = _resolve(store, doc)['content_requirements']
    assert req['content_profile'] is None and req['density_rationale'] is None
    assert req['required_qualifications'] == []
    models.validate_schema('content_requirements', req)
    old = copy.deepcopy(req)
    old.pop('text_visibility')
    models.validate_schema('content_requirements', old)
    for mutation in ({'text_visibility': 'render_all.v1'}, {'customer_visible': 'arbitrary copy'}):
        with pytest.raises(ModelError):
            models.validate_schema('content_requirements', {**req, **mutation})


def test_old_preparation_without_policy_is_read_verbatim_not_upgraded(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    resolved = {**models.default_design_context(), **_resolve(store, doc)}
    resolved['content_requirements'].pop('text_visibility')
    page_ref = doc['pages'][0]['page']
    old = production.project_prompt(store.read_object_json(page_ref), resolved, [])
    assert 'customer_visible_only.v1' not in old['prompt']
    ref = store.put_json_object(old)
    task = {'inputs': [page_ref, ref], 'scope_pages': ['p1'], 'protocol_version': generation.PROTOCOL}
    original_bytes = store.read_object_bytes(ref)
    actual, actual_ref = production.stored_blueprint_request(store, task)
    assert (actual, actual_ref) == (old, ref)
    assert store.read_object_bytes(ref) == original_bytes
    assert 'text_visibility' not in actual['projection']['content_requirements']


def test_new_real_task_and_freeze_keep_the_same_visibility_and_fixed_copy(tmp_path):
    project, store, task = _blueprint_with_imported_plan(tmp_path)
    prepared, ref = production.stored_blueprint_request(store, task)
    service.task_start(project, task_id=task['task_id'], execution_ref='rp15-synthetic',
        supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    frozen = generation.freeze(project, task_id=task['task_id'],
        input=generation.prepared_input(store, store.load_document(), task),
        base_revision=store.current_revision_id(), operation_id='rp15-freeze')
    assert frozen['input']['prompt'] == prepared['prompt']
    assert frozen['input']['design_context']['content_requirements'] == prepared['projection']['content_requirements']
    assert frozen['input']['design_context']['content_requirements']['text_visibility'] == 'customer_visible_only.v1'
    page = store.read_object_json(frozen['input']['page']['page_ref'])
    assert prepared['projection']['customer_visible']['title'] == page['customer_visible']['title']
    assert production.stored_blueprint_request(store, task) == (prepared, ref)
    assert store.read_object_json(store.load_document()['tasks'][0]).get('generation_attempts', []) == []


@pytest.mark.parametrize('target,field,value,expected', [
    (0, 'content_profile', 'mechanism', False),
    (0, 'density_rationale', '保留业务限定，但内部核验文字不上屏', False),
    (1, 'density_rationale', '无关页的密度依据', True),
    (0, 'timing_seconds', 45, True),
])
def test_new_task_freshness_tracks_actual_page_consumption_only(tmp_path, target, field, value, expected):
    _, store, task = _blueprint_with_imported_plan(tmp_path)
    current = copy.deepcopy(store.load_document())
    plan = store.read_object_json(current['content_plan'])
    plan['input']['page_roles'][target][field] = value
    current['content_plan'] = store.put_json_object(plan)
    assert tasks.task_inputs_current(store, current, task) is expected
