"""Current intermediate parent caps constrain already-bound descendants: L1."""
import uuid

import pytest

from deck_master import eligibility, service, tasks
from deck_master.models import ModelError
from test_eligibility_enforcement import _grant
from test_rc3_budget_workflow import project, spend


def chain(path,store):
    root=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
        max_external_calls=2,max_candidate_count=2,operation_id='L1-ancestor-root')
    parent=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
        parent_authorization_ref=root['authorization_ref'],max_external_calls=2,
        max_candidate_count=2,operation_id='L1-ancestor-parent')
    child=_grant(path,store,actions=('dispatch.blueprint',),
        parent_authorization_ref=parent['authorization_ref'],max_external_calls=2,
        max_candidate_count=2,operation_id='L1-ancestor-child')
    return root,parent,child


def lower_parent(path,store,root,parent):
    return _grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
        authorization_id=parent['authorization_id'],replaces=parent['authorization_ref'],
        parent_authorization_ref=root['authorization_ref'],max_external_calls=0,
        max_candidate_count=0,operation_id='L1-lower-current-parent')


def test_bound_child_cannot_reserve_against_superseded_larger_intermediate_parent(tmp_path):
    path,store=project(tmp_path)
    root,parent,child=chain(path,store)
    doc=store.load_document();task=service.open_blueprint_task(store,doc,doc['pages'][0])
    assert task['collaboration_binding']['authorization_ref']==child['authorization_ref']
    lower_parent(path,store,root,parent)
    before=store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        tasks.allocate_call_allowances(store,task_id=task['task_id'],count=1)
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document()==before
    assert eligibility.authorization_budget(store,before,child['authorization_ref'])['remaining']==0
    # A pre-existing held call is still its own call; reducing new-call capacity
    # does not fabricate a withdrawal or erase observation/settlement rights.
    spend(path,store,task)
    assert eligibility.authorization_budget(store,store.load_document(),child['authorization_ref'])['used']==1


def test_candidate_budget_uses_current_intermediate_parent_cap(tmp_path):
    path,store=project(tmp_path)
    root,parent,child=chain(path,store)
    lower_parent(path,store,root,parent)
    before=store.load_document()
    assert eligibility.candidate_budget(store,before,child['authorization_ref'])['remaining']==0
    assert store.load_document()==before


def test_replacement_cannot_move_existing_consumption_to_a_different_root(tmp_path):
    path,store=project(tmp_path)
    root,parent,child=chain(path,store)
    doc=store.load_document();task=service.open_blueprint_task(store,doc,doc['pages'][0])
    spend(path,store,task)
    other=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
        max_external_calls=2,max_candidate_count=2,operation_id='L1-separate-root')
    before=store.load_document()
    with pytest.raises(ModelError,match='cannot move historical consumption'):
        _grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
            authorization_id=parent['authorization_id'],replaces=parent['authorization_ref'],
            parent_authorization_ref=other['authorization_ref'],max_external_calls=2,
            max_candidate_count=2,operation_id='L1-forbidden-root-move')
    assert store.load_document()==before
    assert eligibility.authorization_budget(store,before,root['authorization_ref'])['used']==1
    assert eligibility.authorization_budget(store,before,other['authorization_ref'])['used']==0


@pytest.mark.parametrize('parent_version', ['current', 'stale'])
def test_lowered_numeric_parent_cannot_mint_a_fresh_computed_root(tmp_path, parent_version):
    from deck_master import collaboration_budget
    from test_eligibility_enforcement import _declared
    path,store=project(tmp_path)
    root,parent,child=chain(path,store)
    current_parent=lower_parent(path,store,root,parent)
    before=store.load_document()
    try:
        derived=collaboration_budget.materialize_execution(path,
            parent_authorization_ref=(current_parent if parent_version == 'current' else parent)['authorization_ref'],
            budget_template='initial_per_page',base_revision=store.current_revision_id(),
            operation_id='L1-no-fresh-root-after-parent-zero',instruction_evidence=_declared(store))
    except (ModelError,eligibility.EligibilityBlocked):
        assert store.load_document()==before
        return
    doc=store.load_document()
    assert store.read_object_json(derived['authorization_ref'])['max_external_calls']==0
    assert eligibility.authorization_budget(store,doc,derived['authorization_ref'])['remaining']==0
    with pytest.raises(eligibility.EligibilityBlocked):
        service.open_blueprint_task(store,doc,doc['pages'][0])
    assert store.load_document()==doc


@pytest.mark.parametrize('kind',['explicit_zero','lowered_top_level'])
def test_numeric_zero_top_level_cannot_be_reclassified_as_pure_planning(tmp_path,kind):
    from deck_master import collaboration_budget
    from test_eligibility_enforcement import _declared
    path,store=project(tmp_path)
    parent=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
        max_external_calls=0 if kind=='explicit_zero' else 2,max_candidate_count=0,
        budget_template='explicit' if kind=='explicit_zero' else None,
        operation_id='L1-numeric-top-parent')
    if kind=='lowered_top_level':
        parent=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),
            authorization_id=parent['authorization_id'],replaces=parent['authorization_ref'],
            max_external_calls=0,max_candidate_count=0,operation_id='L1-lower-top-parent')
    before=store.load_document()
    try:
        derived=collaboration_budget.materialize_execution(path,
            parent_authorization_ref=parent['authorization_ref'],budget_template='initial_per_page',
            base_revision=store.current_revision_id(),operation_id='L1-no-new-numeric-root',
            instruction_evidence=_declared(store))
    except (ModelError,eligibility.EligibilityBlocked):
        assert store.load_document()==before
        return
    doc=store.load_document()
    assert eligibility.authorization_budget(store,doc,derived['authorization_ref'])['remaining']==0
    with pytest.raises(eligibility.EligibilityBlocked):
        service.open_blueprint_task(store,doc,doc['pages'][0])
    assert store.load_document()==doc
