"""Actual resolver/freeze contracts on synthetic projects, no image-quality claim."""
import copy

import pytest

from deck_master import models, production, tasks
from deck_master.models import ModelError
from test_rc3_design_requirements import _snapshot, _replace_plan
from test_rc3_notes_visual_inputs import _blueprint_with_imported_plan


def _policy(strategy='model_designed'):
    return {'version': 'design_policy.v1', 'strategy': strategy, 'purpose': '解释人工确认责任',
            'primary_object': '确认链', 'free_layout': '可调整位置与留白，保留主体归属和先后关系',
            'layout_instruction': '不使用泳道，用责任标签', 'table_roles': []}


def _change_page(store, doc, index, mutate):
    entry = doc['pages'][index]
    page = store.read_object_json(entry['page'])
    mutate(page)
    models.validate_page_semantics(page)
    entry['page'] = store.put_json_object(page)
    if doc.get('content_plan'):
        plan = store.read_object_json(doc['content_plan'])
        for link in plan['page_links']:
            if link['page_id'] == entry['page_id']:
                link['page_ref'] = entry['page']
        _replace_plan(store, doc, plan)
    return page


def _request(store, doc, index=0):
    entry = doc['pages'][index]
    resolved = production.resolve_generation_design(store, doc, entry)
    return production.project_prompt(store.read_object_json(entry['page']), resolved, [])


@pytest.mark.parametrize('strategy', ['agreed_layout', 'model_designed'])
def test_effective_override_removes_superseded_swimlanes_and_preserves_relations(tmp_path, strategy):
    store, doc, _ = _snapshot(tmp_path)
    doc['design_context']['styles'][0]['layout_notes'] = '三泳道'
    doc['design_context']['styles'][0]['layout_page_ids'] = ['p1']
    def change(page):
        page['visual_spec'].update(layout_hint='三泳道', design_policy=_policy(strategy),
                                  design_overrides={'layout_notes': '只使用责任标签'})
    page = _change_page(store, doc, 0, change)
    before = copy.deepcopy(page)
    request = _request(store, doc)
    assert '三泳道' not in request['prompt']
    assert request['projection']['style']['layout_notes'] == '只使用责任标签'
    assert request['projection']['content_requirements']['layout_hint'] == '不使用泳道，用责任标签'
    assert request['projection']['visual_spec']['edges'] == page['visual_spec']['edges']
    assert request['projection']['visual_spec']['nodes'] == page['visual_spec']['nodes']
    assert request['projection']['customer_visible'] == page['customer_visible']
    assert page == before
    assert _request(store, doc, 1)['projection']['style']['layout_notes'] == ''


@pytest.mark.parametrize('role', ['comparison', 'content_inventory'])
def test_tables_keep_every_cell_and_ownership_for_both_roles(tmp_path, role):
    store, doc, _ = _snapshot(tmp_path)
    policy = _policy()
    policy['table_roles'] = [{'block_id': 'cost', 'role': role}]
    page = _change_page(store, doc, 0, lambda p: p['visual_spec'].update(design_policy=policy))
    request = _request(store, doc)
    assert request['projection']['customer_visible']['body_blocks'] == page['customer_visible']['body_blocks']
    assert request['projection']['design_policy']['table_roles'] == policy['table_roles']
    assert 'Tables are comparisons by default' in request['prompt']


def test_cover_has_no_node_minimum_and_default_is_only_for_new_preparation(tmp_path):
    store, doc, _ = _snapshot(tmp_path, legacy=True)
    page = _change_page(store, doc, 0, lambda p: p['visual_spec'].update(nodes=[], edges=[], layout_hint=''))
    request = _request(store, doc)
    assert request['projection']['design_policy']['strategy'] == 'model_designed'
    assert request['projection']['visual_spec']['nodes'] == []
    assert 'design_policy' not in page['visual_spec']
    legacy = production.resolve_generation_design(store, doc, doc['pages'][0], design_policy=False)
    old = production.project_prompt(page, legacy, [])
    ref = store.put_json_object(old)
    task = {'inputs': [doc['pages'][0]['page'], ref], 'scope_pages': ['p1'], 'protocol_version': 'generation.v1'}
    assert production.stored_blueprint_request(store, task) == (old, ref)
    assert 'design_policy' not in old['projection']


@pytest.mark.parametrize('index,expected', [(0, False), (1, True)])
def test_changed_policy_only_stales_consuming_page(tmp_path, index, expected):
    _, store, task = _blueprint_with_imported_plan(tmp_path)
    doc = copy.deepcopy(store.load_document())
    prepared, ref = production.stored_blueprint_request(store, task)
    before = store.read_object_bytes(ref)
    _change_page(store, doc, index, lambda p: p['visual_spec'].update(design_policy=_policy()))
    assert tasks.task_inputs_current(store, doc, task) is expected
    assert store.read_object_bytes(ref) == before
    assert production.stored_blueprint_request(store, task) == (prepared, ref)


def test_scope_metadata_does_not_stale_unaffected_page(tmp_path):
    _, store, task = _blueprint_with_imported_plan(tmp_path)
    doc = copy.deepcopy(store.load_document())
    doc['design_context']['styles'][0]['layout_page_ids'] = [task['scope_pages'][0]]
    assert tasks.task_inputs_current(store, doc, task)


@pytest.mark.parametrize('mutation', [lambda p: p.update(strategy='automatic'),
    lambda p: p.update(extra=True), lambda p: p.update(strategy='agreed_layout', layout_instruction=''),
    lambda p: p.update(table_roles=[{'block_id': 'missing', 'role': 'comparison'}]),
    lambda p: p.update(table_roles=[{'block_id': 'cost', 'role': 'comparison'}]*2)])
def test_policy_is_strict_and_table_roles_reference_actual_unique_tables(tmp_path, mutation):
    store, doc, _ = _snapshot(tmp_path)
    page = store.read_object_json(doc['pages'][0]['page'])
    policy = _policy()
    mutation(policy)
    page['visual_spec']['design_policy'] = policy
    with pytest.raises(ModelError):
        models.validate_page_semantics(page)


def test_policy_itself_supersedes_global_layout_without_duplicate_override(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    doc['design_context']['styles'][0]['layout_notes'] = '三泳道'
    _change_page(store, doc, 0, lambda p: p['visual_spec'].update(layout_hint='三泳道', design_policy=_policy()))
    assert '三泳道' not in _request(store, doc)['prompt']


@pytest.mark.parametrize('feature', ['policy', 'override', 'scope'])
def test_persisted_fields_raise_writer_floor_and_old_reader_refuses(tmp_path, monkeypatch, feature):
    from deck_master import store as store_module
    from deck_master.store import StoreError
    _, store, _ = _blueprint_with_imported_plan(tmp_path)
    doc = copy.deepcopy(store.load_document())
    old_revision = store.current_revision_id()
    if feature == 'policy':
        _change_page(store, doc, 0, lambda p: p['visual_spec'].update(design_policy=_policy()))
    elif feature == 'override':
        _change_page(store, doc, 0, lambda p: p['visual_spec'].update(design_overrides={'layout_notes': ''}))
    else:
        doc['design_context']['styles'][0]['layout_page_ids'] = []
    doc['revision_id'] = 'rev-rp17-' + feature
    doc['change']['operation_id'] = 'rp17-writer-' + feature
    store.commit_change(base_revision=old_revision, document=doc, operation_id=doc["change"]["operation_id"])
    assert store.load_document()['compatibility']['minimum_writer'] == 'design-policy.v1'
    monkeypatch.setattr(store_module, 'SUPPORTED_WRITERS', tuple(w for w in store_module.SUPPORTED_WRITERS
                                                              if w != 'design-policy.v1'))
    with pytest.raises(StoreError, match='writer'):
        store.read_current()


def test_revised_policy_replaces_v3_recipe_composition_before_freeze(tmp_path):
    from test_rc3_design_recipes import recipe, input_value
    store, doc, _ = _snapshot(tmp_path)
    value = input_value(doc)
    value['recipe_draft']['composition'] = '三泳道'
    actual_recipe, _ = recipe(store, doc, value)
    ref = store.put_json_object(actual_recipe)
    doc["style_recipes"] = [ref]
    _change_page(store, doc, 0, lambda p: p['visual_spec'].update(design_policy=_policy()))
    resolved = production.resolve_generation_design(store, doc, doc['pages'][0], recipe_ref=ref)
    request = production.project_prompt(store.read_object_json(doc['pages'][0]['page']), resolved, [])
    assert '三泳道' not in request['prompt']
    assert request['projection']['recipe_parameters']['composition'] == _policy()['layout_instruction']
    assert request['projection']['recipe_parameters']['density'] == actual_recipe['parameters']['density']
    assert store.read_object_json(ref) == actual_recipe


def test_new_task_policy_is_frozen_exactly_and_protected_by_writer_floor(tmp_path):
    from deck_master import generation, service
    project, store, task = _blueprint_with_imported_plan(tmp_path)
    prepared, ref = production.stored_blueprint_request(store, task)
    assert store.load_document()['compatibility']['minimum_writer'] == 'design-policy.v1'
    service.task_start(project, task_id=task['task_id'], execution_ref='rp17-synthetic',
                       supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    frozen = generation.freeze(project, task_id=task['task_id'],
        input=generation.prepared_input(store, store.load_document(), task),
        base_revision=store.current_revision_id(), operation_id='rp17-freeze')
    assert frozen['input']['prompt'] == prepared['prompt']
    assert frozen['input']['design_context']['design_policy'] == prepared['projection']['design_policy']
    assert production.stored_blueprint_request(store, task) == (prepared, ref)


def test_old_task_without_strategy_does_not_stale_from_new_default(tmp_path):
    _, store, task = _blueprint_with_imported_plan(tmp_path)
    doc = store.load_document()
    prepared, ref = production.stored_blueprint_request(store, task)
    resolved = production.resolve_generation_design(store, doc, doc['pages'][0], design_policy=False)
    page = store.read_object_json(resolved['content_basis']['page_ref'])
    historical = production.project_prompt(page, resolved, [])
    old_ref = store.put_json_object(historical)
    old_task = copy.deepcopy(task)
    old_task['inputs'] = [old_ref if item == ref else item for item in task['inputs']]
    current = production.resolve_generation_design(store, doc, doc["pages"][0], design_policy=False)
    assert production.consumed_design(resolved, store=store) == production.consumed_design(current, store=store)
    assert tasks.task_inputs_current(store, doc, old_task)
    assert production.stored_blueprint_request(store, old_task) == (historical, old_ref)
