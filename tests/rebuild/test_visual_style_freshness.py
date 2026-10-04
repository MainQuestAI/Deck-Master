"""A v2 trial preserves its exact target image until explicit adoption."""
import uuid

import pytest

from test_styles import flow, dispatch, mutate  # noqa: F401
from test_visual_styles import completed
from deck_master import candidates, generation, styles, tasks
from deck_master.operations import OperationError


def style_trial(flow):
    ref, _, _ = completed(flow)
    doc = flow.store.load_document()
    proposed = styles.propose(flow.project, input={'schema_version':'style_input.v2',
        'project_id':doc['project_id'], 'base_revision':doc['revision_id'], 'visual_style_ref':ref,
        'target_page_ids':['p02','p03'], 'instruction':'Preserve target geometry; use typography only',
        'dimensions':{'typography':'Confirmed target text hierarchy'}})
    recipe = styles.confirm(flow.project, proposal_id=proposed['proposal_id'],
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))['operation_result']
    return recipe, dispatch(flow, recipe)


def test_changed_preservation_target_refuses_claim_without_publishing(flow):
    _, task = style_trial(flow)
    mutate(flow, 'p02', 'blueprint')
    before = flow.store.read_current()
    assert not tasks.task_inputs_current(flow.store, flow.store.load_document(), task)
    with pytest.raises(tasks.StaleInputContext, match='target original image changed'):
        flow.start(task)
    assert before == flow.store.read_current()


def test_changed_preservation_target_refuses_freeze_begin_and_submission(flow):
    _, task = style_trial(flow)
    flow.start(task)
    prepared = generation.prepared_input(flow.store, flow.store.load_document(), task)
    frozen = generation.freeze(flow.project, task_id=task['task_id'], input=prepared,
        base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    mutate(flow, 'p02', 'blueprint')
    before = flow.store.read_current()
    with pytest.raises(generation.GenerationError, match='current active task'):
        generation.freeze(flow.project, task_id=task['task_id'], input=prepared,
            base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    with pytest.raises(generation.GenerationError, match='current'):
        tasks.call_begin(flow.store, task_id=task['task_id'], allowance_id=task['call_allowances'][0]['allowance_id'],
            execution_ref=flow.task(task['task_id'])['execution_ref'], request_id=frozen['request_id'])
    with pytest.raises(tasks.StaleInputContext):
        tasks.accept_result(flow.store, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], envelope_raw={'kind':'blueprint'})
    assert before == flow.store.read_current()


def test_candidate_records_preserved_target_and_refuses_adoption_after_it_moves(flow):
    _, task = style_trial(flow)
    cid = flow.image(task)['candidate_ids'][0]
    candidate = candidates.show(flow.project, candidate_id=cid)
    assert candidate['candidate']['generation_basis']['blueprint_ref'] == task['stage_request']['target_reference_ref']
    mutate(flow, 'p02', 'blueprint')
    before = flow.store.read_current()
    state = candidates.show(flow.project, candidate_id=cid)['generation_basis']
    assert state['status'] == 'changed' and 'blueprint_ref' in state['changed_fields']
    with pytest.raises(candidates.AdoptionConflict):
        flow.adopt([cid])
    assert before == flow.store.read_current()


def test_self_adoption_permits_expansion_but_later_target_changes_invalidate_sample(flow):
    recipe, task = style_trial(flow)
    cid = flow.image(task)['candidate_ids'][0]
    flow.adopt([cid])
    assert candidates.show(flow.project, candidate_id=cid)['generation_basis']['status'] == 'current'
    expansion = dispatch(flow, recipe, ['p03'], cid)
    assert expansion['stage_request']['target_reference_ref'] == flow.store.load_document()['pages'][2]['blueprint']
    mutate(flow, 'p02', 'blueprint')
    assert candidates.show(flow.project, candidate_id=cid)['generation_basis']['status'] == 'changed'
    with pytest.raises(OperationError, match='currently adopted'):
        # The sample must still be the currently adopted original image.
        styles.plan(flow.project, input={'recipe_id':recipe['recipe_id'], 'page_ids':['p03'],
            'max_calls':1, 'adopted_candidate_id':cid})


def test_unrelated_blueprint_changes_do_not_stale_preservation_trial(flow):
    _, task = style_trial(flow)
    mutate(flow, 'p01', 'blueprint')
    assert tasks.task_inputs_current(flow.store, flow.store.load_document(), task)
    flow.start(task)


def test_historical_null_basis_uses_immutable_task_anchor_without_rewriting(flow, monkeypatch):
    _, task = style_trial(flow)
    real = candidates.generation_basis
    def old_basis(*args, **kwargs):
        value = real(*args, **kwargs)
        if kwargs.get('preserve_blueprint'):
            value['blueprint_ref'] = None
        return value
    with monkeypatch.context() as patch:
        patch.setattr(candidates, 'generation_basis', old_basis)
        cid = flow.image(task)['candidate_ids'][0]
    record = candidates.show(flow.project, candidate_id=cid)
    raw = flow.store.read_object_bytes(record['candidate_ref'])
    assert record['candidate']['generation_basis']['blueprint_ref'] is None
    assert record['generation_basis']['status'] == 'current'
    mutate(flow, 'p02', 'blueprint')
    assert candidates.show(flow.project, candidate_id=cid)['generation_basis']['status'] == 'changed'
    assert flow.store.read_object_bytes(record['candidate_ref']) == raw


def test_unmarked_blueprint_trial_retains_its_existing_scope(flow):
    task = flow.dispatch(page_id='p02')
    assert 'target_reference_ref' not in task['stage_request']
    mutate(flow, 'p02', 'blueprint')
    assert tasks.task_inputs_current(flow.store, flow.store.load_document(), task)
    flow.start(task)
    prepared = generation.prepared_input(flow.store, flow.store.load_document(), task)
    assert generation.freeze(flow.project, task_id=task['task_id'], input=prepared,
        base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))['status'] == 'frozen'
