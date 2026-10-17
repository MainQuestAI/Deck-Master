"""Batch gate and actual Tasks must use one chosen authority: synthetic L1."""
import uuid

import pytest

from deck_master import changes, collaboration, eligibility, tasks
from test_candidates import store as candidate_store
from test_rc3_candidate_quota import grant as candidate_grant
from test_rc3_budget_workflow import project, change_input
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
