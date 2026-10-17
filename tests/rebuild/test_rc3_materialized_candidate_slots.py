"""Ready-review regression: real SDK transactions, synthetic inputs, zero calls."""
import uuid
import pytest
from deck_master import (changes, collaboration, collaboration_budget, content_review,
                         eligibility, review_evidence, service, tasks)
from test_content_preproduction_review import _deck, _instruction
from test_eligibility_enforcement import _declared, _grant
from test_rc3_budget_workflow import change_input, grant, project
from test_rc3_review_policy_workflow import choice, decide

def task_by_id(store, task_id):
    return tasks._lookup_task(store.load_document(), task_id, store)


@pytest.mark.parametrize('parent_slots', [None, 0, 1, 5])
@pytest.mark.parametrize('mode', ['trial', 'auto'])
def test_materialized_candidate_ceiling_follows_current_plan_and_parent(tmp_path, parent_slots, mode):
    path, store = project(tmp_path, intent='edit')
    parent = _grant(path, store, actions=('change.commit', 'dispatch.blueprint'), mode='delegate',
        max_external_calls=0, max_candidate_count=parent_slots) if parent_slots is not None else None
    def value():
        return {**change_input(store, layer='content', ids=('p1',)), 'intent': 'content', 'mode': mode}
    plan = changes.plan(path, input=value())
    materialized = collaboration_budget.materialize_execution(path,
        parent_authorization_ref=parent['authorization_ref'] if parent else None,
        budget_template='edit_rebuild_per_page', change_plan_id=plan['plan_id'],
        actions=['change.commit', 'dispatch.blueprint'], instruction_evidence=_declared(store),
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    ref = materialized['authorization_ref']
    expected = int(mode == 'trial' and parent_slots != 0)
    assert store.read_object_json(ref)['max_candidate_count'] == expected
    if mode == 'auto':
        return  # candidate-only grants deliberately cannot auto-adopt production.
    plan = changes.plan(path, input=value())
    before = store.load_document()
    if mode == 'trial' and parent_slots == 0:
        with pytest.raises(eligibility.EligibilityBlocked):
            changes.commit(path, plan_id=plan['plan_id'], base_revision=before['revision_id'],
                           operation_id=str(uuid.uuid4()))
        assert store.load_document() == before
    else:
        result = changes.commit(path, plan_id=plan['plan_id'], base_revision=before['revision_id'],
                                operation_id=str(uuid.uuid4()))['operation_result']
        assert task_by_id(store, result['task_ids'][0])['collaboration_binding']['authorization_ref'] == ref
        assert eligibility.candidate_budget(store, store.load_document(), ref)['used'] == expected


@pytest.mark.parametrize('explicit', [0, 1, 5])
def test_template_candidate_limit_keeps_smaller_explicit_limit_and_history(tmp_path, explicit):
    path, store = project(tmp_path, intent='edit')
    def value():
        return {**change_input(store, layer='content', ids=('p1',)), 'intent': 'content', 'mode': 'trial'}
    planned = changes.plan(path, input=value())
    auth = grant(path, store, template='edit_rebuild_per_page', change_plan_id=planned['plan_id'],
                 max_candidate_count=explicit, adoption_policy='candidate_only')
    assert store.read_object_json(auth['authorization_ref'])['max_candidate_count'] == min(1, explicit)
    if explicit:
        planned = changes.plan(path, input=value())
        changes.commit(path, plan_id=planned['plan_id'], base_revision=store.current_revision_id(),
                       operation_id=str(uuid.uuid4()))
        assert eligibility.candidate_budget(store, store.load_document(), auth['authorization_ref'])['remaining'] == 0
        planned = changes.plan(path, input=value())
        repeated = grant(path, store, template='edit_rebuild_per_page', change_plan_id=planned['plan_id'],
                         max_candidate_count=explicit, adoption_policy='candidate_only')
        assert eligibility.candidate_budget(store, store.load_document(), repeated['authorization_ref'])['remaining'] == 0


def test_repeated_materialization_cannot_refresh_explicit_zero_candidate_root(tmp_path):
    path, store = project(tmp_path, intent='edit')
    def value():
        return {**change_input(store, layer='content', ids=('p1',)), 'intent': 'content', 'mode': 'trial'}
    planned = changes.plan(path, input=value())
    first = grant(path, store, template='edit_rebuild_per_page', change_plan_id=planned['plan_id'],
                  max_candidate_count=0, adoption_policy='candidate_only')
    planned = changes.plan(path, input=value())
    second = collaboration_budget.materialize_execution(path, budget_template='edit_rebuild_per_page',
        change_plan_id=planned['plan_id'], actions=['change.commit', 'dispatch.blueprint'],
        instruction_evidence=_declared(store), base_revision=store.current_revision_id(),
        operation_id=str(uuid.uuid4()))
    for ref in (first['authorization_ref'], second['authorization_ref']):
        assert store.read_object_json(ref)['max_candidate_count'] == 0
        assert eligibility.candidate_budget(store, store.load_document(), ref)['remaining'] == 0
    planned = changes.plan(path, input=value())
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        changes.commit(path, plan_id=planned['plan_id'], base_revision=before['revision_id'],
                       operation_id=str(uuid.uuid4()))
    assert store.load_document() == before

