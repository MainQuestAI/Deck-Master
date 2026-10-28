"""Batch gate and actual Tasks must use one chosen authority: synthetic L1."""
import uuid

import pytest

from deck_master import changes, collaboration, eligibility, service, tasks
from candidate_fixtures import store as candidate_store
from test_rc3_candidate_quota import grant as candidate_grant
from test_rc3_budget_workflow import project, change_input
from test_rc3_budget_workflow import grant, spend
from test_eligibility_enforcement import _scope
from test_eligibility_enforcement import _grant


def test_two_slot_batch_binds_the_same_sufficient_grant_selected_at_gate(candidate_store):
    store=candidate_store
    old=candidate_grant(store,1,replace=True)
    current=candidate_grant(store,2)
    before=store.load_document()
    value={'schema_version':'change_intent.v1','project_id':before['project_id'],
        'base_revision':before['revision_id'],'intent':'repair','instruction':'L1 two-page trial under the explicit two-slot grant',
        'annotation_refs':[],'max_calls':0,'mode':'trial','targets':[
            {'page_id':item['page_id'],'page_ref':item['page'],'layer':'svg','artifact_ref':item['svg']}
            for item in before['pages']]}
    planned=changes.plan(store.project_root,input=value)
    result=changes.commit(store.project_root,plan_id=planned['plan_id'],base_revision=store.current_revision_id(),
        operation_id=str(uuid.uuid4()))['operation_result']
    actual=[tasks._lookup_task(store.load_document(),identity,store) for identity in result['task_ids']]
    assert len(actual)==2
    assert all(task['collaboration_binding']['authorization_ref']==current for task in actual)
    assert eligibility.candidate_budget(store,store.load_document(),old)['used']==0
    assert eligibility.candidate_budget(store,store.load_document(),current)['used']==2
    # A and B were independent explicit grants. Withdraw unused A before
    # proving B's third slot is refused; otherwise A's remaining slot is real.
    collaboration.revoke_authorization(store.project_root,
        authorization_id=store.read_object_json(old)['authorization_id'],
        reason='L1 retire the separate unused one-slot authority',
        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    before=store.load_document()
    third=changes.plan(store.project_root,input={**value,'base_revision':before['revision_id'],
        'targets':value['targets'][:1]})
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        changes.commit(store.project_root,plan_id=third['plan_id'],base_revision=before['revision_id'],
            operation_id=str(uuid.uuid4()))
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document()==before


def test_two_image_batch_does_not_reselect_an_insufficient_single_call_grant(tmp_path):
    path,store=project(tmp_path,intent='edit')
    old=_grant(path,store,actions=('change.commit','dispatch.blueprint'),max_external_calls=1,
        max_candidate_count=2,operation_id='L1-batch-old-one-call')
    current=_grant(path,store,actions=('change.commit','dispatch.blueprint'),max_external_calls=2,
        max_candidate_count=2,operation_id='L1-batch-new-two-call')
    value={**change_input(store),'mode':'trial'}
    planned=changes.plan(path,input=value)
    result=changes.commit(path,plan_id=planned['plan_id'],base_revision=store.current_revision_id(),
        operation_id=str(uuid.uuid4()))['operation_result']
    actual=[tasks._lookup_task(store.load_document(),identity,store) for identity in result['task_ids']]
    assert len(actual)==2
    assert all(task['collaboration_binding']['authorization_ref']==current['authorization_ref'] for task in actual)
    assert eligibility.authorization_budget(store,store.load_document(),old['authorization_ref'])['used']==0
    assert eligibility.authorization_budget(store,store.load_document(),current['authorization_ref'])['used']==2
    assert all(not task.get('generation_attempts') for task in actual)


def test_new_page_retry_uses_explicit_grant_and_preserves_other_initial_credit(tmp_path):
    path, store = project(tmp_path)
    initial = grant(path, store)
    doc = store.load_document()
    original = service.open_blueprint_task(store, doc, doc['pages'][0])
    spend(path, store, original)
    service.task_cancel(path, task_id=original['task_id'], reason='L1 settled first attempt; retry requested separately')
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        service.open_blueprint_task(store, before, before['pages'][0])
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document() == before
    retry = grant(path, store, template='explicit', max_external_calls=1,
                  scope=_scope(page_ids=['p1']))
    doc = store.load_document()
    replacement = service.open_blueprint_task(store, doc, doc['pages'][0])
    assert replacement['collaboration_binding']['authorization_ref'] == retry['authorization_ref']
    assert eligibility.authorization_budget(store, store.load_document(), initial['authorization_ref'])['remaining'] == 1
    doc = store.load_document()
    second = service.open_blueprint_task(store, doc, doc['pages'][1])
    assert second['collaboration_binding']['authorization_ref'] == initial['authorization_ref']
    assert second['collaboration_binding']['budget_key'].endswith(':initial:p2')
    assert eligibility.authorization_budget(store, store.load_document(), retry['authorization_ref'])['used'] == 1
    # The already-bound first Task cannot allocate the new grant's allowance.
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        tasks.allocate_call_allowances(store, task_id=original['task_id'], count=1)
    assert store.load_document() == before


def test_image_batch_skips_initial_grant_with_one_used_target_credit(tmp_path):
    path, store = project(tmp_path, intent='edit')
    # Initial grants belong to full-deck requests; this explicit fixed edit
    # template has the same independent per-page accounting.
    planned = changes.plan(path, input=change_input(store))
    initial = grant(path, store, template='edit_rebuild_per_page', change_plan_id=planned['plan_id'])
    doc = store.load_document()
    original = service.open_blueprint_task(store, doc, doc['pages'][0])
    spend(path, store, original)
    service.task_cancel(path, task_id=original['task_id'], reason='L1 settled call')
    retry = grant(path, store, template='explicit', max_external_calls=2)
    planned = changes.plan(path, input=change_input(store))
    result = changes.commit(path, plan_id=planned['plan_id'], base_revision=store.current_revision_id(),
                            operation_id=str(uuid.uuid4()))['operation_result']
    actual = [tasks._lookup_task(store.load_document(), identity, store) for identity in result['task_ids']]
    assert len(actual) == 2
    assert all(task['collaboration_binding']['authorization_ref'] == retry['authorization_ref'] for task in actual)
    assert eligibility.authorization_budget(store, store.load_document(), initial['authorization_ref'])['remaining'] == 1
