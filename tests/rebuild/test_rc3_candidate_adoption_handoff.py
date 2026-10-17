"""Exact backend adoption scope shared by preview and guarded commit; L1."""
import uuid

import pytest

from deck_master import candidates, changes, collaboration, eligibility
from deck_master.operations import OperationError
from rc3_fixtures import evidence_for
from test_candidates import dispatch, start, accept, plan as adoption_plan
from test_rc3_candidate_adoption_browser import new_request


def trial(tmp_path):
    path, store = new_request(tmp_path)
    doc = store.load_document(); entry = doc['pages'][0]
    changed = changes.plan(path, input={'schema_version':'change_intent.v1', 'project_id':doc['project_id'],
        'base_revision':doc['revision_id'], 'intent':'svg_repair', 'mode':'trial', 'max_calls':0,
        'instruction':'L1 trial of the selected SVG', 'annotation_refs':[],
        'targets':[{'page_id':entry['page_id'], 'page_ref':entry['page'], 'layer':'svg','artifact_ref':entry['svg']}]})
    collaboration.grant(path, input={'mode':'execute','actions':['change.commit','dispatch.blueprint'],
        'budget_template':'edit_rebuild_per_page','change_plan_id':changed['plan_id'],
        'adoption_policy':'candidate_only','max_candidate_count':1,
        'instruction_evidence':evidence_for(path,text='L1 one zero-call trial; explicit adoption remains separate.',locator='L1:trial')},
        base_revision=doc['revision_id'],operation_id=str(uuid.uuid4()))
    task=dispatch(store); start(store,task); cid=accept(store,task)['candidate_ids'][0]
    return path,store,cid


def preview(path,store,cid):
    return candidates.plan(path,input={'schema_version':'candidate_selection.v1','project_id':store.load_document()['project_id'],
        'base_revision':store.current_revision_id(),'candidate_ids':[cid]})


def grant_adoption(path,store,scope):
    return collaboration.grant(path,input={'mode':'execute','actions':['candidate.adopt'],'scope':scope,
        'max_external_calls':0,'max_candidate_count':0,'adoption_policy':'within_scope',
        'instruction_evidence':evidence_for(path,text='L1 explicitly adopt this selected SVG; zero calls.',locator='L1:adopt')},
        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))


def test_preview_is_read_only_and_exact_grant_requires_new_current_plan(tmp_path):
    path,store,cid=trial(tmp_path); before=store.load_document()
    result=preview(path,store,cid); authority=result['adoption_authority']; old=result['plan']
    assert store.load_document()==before
    assert authority['scope']['page_ids']==['p01'] and authority['scope']['layers']==['svg']
    assert not authority['eligibility']['allowed']
    with pytest.raises(eligibility.EligibilityBlocked):
        candidates.adopt(path,input=old,base_revision=old['base_revision'],operation_id=str(uuid.uuid4()))
    grant_adoption(path,store,authority['scope'])
    after_grant=store.load_document()
    assert after_grant['pages']==before['pages']
    with pytest.raises(OperationError):
        candidates.adopt(path,input=old,base_revision=old['base_revision'],operation_id=str(uuid.uuid4()))
    current=preview(path,store,cid)
    assert current['adoption_authority']['eligibility']['allowed']
    assert current['plan']['selections']==old['selections']
    op=str(uuid.uuid4()); value=current['plan']
    adopted=candidates.adopt(path,input=value,base_revision=value['base_revision'],operation_id=op)
    assert candidates.adopt(path,input=value,base_revision=value['base_revision'],operation_id=op)==adopted
    assert store.load_document()['pages'][1]==before['pages'][1]
    assert eligibility.allowance_usage(store,store.load_document())['totals']==eligibility.allowance_usage(store,before)['totals']


def test_revoked_adoption_does_not_survive_replan_or_change_current(tmp_path):
    path,store,cid=trial(tmp_path)
    grant=grant_adoption(path,store,preview(path,store,cid)['adoption_authority']['scope'])
    fixed=adoption_plan(store,[cid])
    collaboration.revoke_authorization(path,authorization_id=grant['authorization_id'],reason='L1 withdraw adoption before commit',
        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    before=store.load_document()
    with pytest.raises(OperationError):
        candidates.adopt(path,input=fixed,base_revision=fixed['base_revision'],operation_id=str(uuid.uuid4()))
    refreshed=preview(path,store,cid)
    assert not refreshed['adoption_authority']['eligibility']['allowed']
    value=refreshed['plan']
    with pytest.raises(eligibility.EligibilityBlocked):
        candidates.adopt(path,input=value,base_revision=value['base_revision'],operation_id=str(uuid.uuid4()))
    assert store.load_document()==before
