"""Bounded public budgets and actual SDK allowance transitions: L1, zero paid calls."""
import copy
import json
import uuid

import pytest

from deck_master import (changes, collaboration, collaboration_api, collaboration_budget,
                         eligibility, generation, service, tasks)
from deck_master.models import ModelError, canonical_json_bytes
from test_eligibility_enforcement import _declared, _grant, _project, _scope, _settle_preproduction, _start
from test_rc3_notes_visual_inputs import _seed_imported_plan


def project(tmp_path, *, intent='full_deck', pages=('p1', 'p2')):
    path, store = _project(tmp_path)
    _seed_imported_plan(store)
    _start(path, store, intent=intent, scope=_scope(page_ids=list(pages)))
    _settle_preproduction(store, seed=uuid.uuid4().hex[:8])
    return path, store


def grant(path, store, *, template='initial_per_page', **updates):
    value = {'mode': 'execute', 'actions': ['dispatch.blueprint', 'change.commit'],
             'scope': store.load_document()['collaboration']['request']['scope'],
             'budget_template': template, 'instruction_evidence': _declared(store)}
    value.update(updates)
    response, http, code = collaboration_api.invoke(path, 'grant', {
        **value, 'base_revision': store.current_revision_id(), 'operation_id': str(uuid.uuid4())})
    assert (http, code) == (200, 0), response
    return response['result']


def spend(path, store, task, *, outcome='consumed'):
    """Real claim/freeze/begin/settle; report explicitly says no external tool ran."""
    execution = 'L1-synthetic-ledger-host'
    service.task_start(path, task_id=task['task_id'], execution_ref=execution,
        supported_protocols=[task['protocol_version']], capabilities=task['required_capabilities'])
    value = generation.prepared_input(store, store.load_document(), task)
    frozen = generation.freeze(path, task_id=task['task_id'], input=value,
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    allowance = task['call_allowances'][0]['allowance_id']
    attempt = tasks.call_begin(store, task_id=task['task_id'], allowance_id=allowance,
                               execution_ref=execution, request_id=frozen['request_id'])
    assert tasks.call_begin(store, task_id=task['task_id'], allowance_id=allowance,
        execution_ref=execution, request_id=frozen['request_id'])['status'] == 'already_started'
    settled = tasks.call_settle(store, task_id=task['task_id'], allowance_id=allowance,
        attempt_id=attempt['attempt_id'], outcome=outcome,
        report_bytes=canonical_json_bytes({'evidence_level': 'L1_SYNTHETIC',
            'observation': 'Synthetic protocol ledger observation; no external tool or model ran.',
            'native_observation': False}))
    return settled


def change_input(store, *, layer='original_image', ids=('p1', 'p2')):
    doc = store.load_document()
    return {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
        'base_revision': doc['revision_id'], 'instruction': 'Synthetic bounded two-page usable image revision',
        'intent': 'Explicit L1 update with usable artwork', 'targets': [
            {'page_id': entry['page_id'], 'page_ref': entry['page'], 'layer': layer,
             'artifact_ref': entry.get({'original_image':'blueprint','content':'page','svg':'svg'}[layer])}
            for entry in doc['pages'] if entry['page_id'] in ids],
        'annotation_refs': [], 'max_calls': len(ids) if layer == 'original_image' else 0}


def test_readonly_api_and_cli_preview_compute_two_credits_without_writes(tmp_path, capsys):
    path, store = project(tmp_path)
    before = store.load_document()
    response, http, code = collaboration_api.invoke(path, 'budget.describe', {'budget_template':'initial_per_page'})
    assert (http, code) == (200, 0), response
    assert response['result']['max_external_calls'] == 2
    assert len({item['budget_key'] for item in response['result']['credits']}) == 2
    assert store.load_document() == before
    from deck_master.cli import main
    descriptor = tmp_path / 'budget.json'; descriptor.write_text(json.dumps({'budget_template':'initial_per_page'}))
    assert main(['collaboration','budget','--project',str(path),'--input',str(descriptor)]) == 0
    assert json.loads(capsys.readouterr().out)['result']['max_external_calls'] == 2
    assert store.load_document() == before


def test_two_page_normal_grant_dispatch_begin_settle_binds_distinct_credits(tmp_path):
    path, store = project(tmp_path)
    authorization = grant(path, store)
    record = store.read_object_json(authorization['authorization_ref'])
    assert record['max_external_calls'] == 2 and record['budget_key'] is None
    keys = []
    for page_id in ['p1', 'p2']:
        doc = store.load_document(); entry = next(item for item in doc['pages'] if item['page_id'] == page_id)
        task = service.open_blueprint_task(store, doc, entry)
        key = task['collaboration_binding']['budget_key']; keys.append(key)
        assert key == f"{record['request_id']}:initial:{page_id}"
        assert eligibility.credit_state(store, store.load_document(), key)['used'] == 1
        spend(path, store, task)
        assert eligibility.credit_state(store, store.load_document(), key)['state'] == 'exhausted'
    assert len(set(keys)) == 2
    budget = eligibility.authorization_budget(store, store.load_document(), authorization['authorization_ref'])
    assert (budget['ceiling'], budget['used'], budget['remaining']) == (2, 2, 0)
    assert eligibility.allowance_usage(store, store.load_document())['totals']['consumed'] == 2
    before = store.load_document()
    response, http, code = collaboration_api.invoke(path, 'grant', {
        'mode':'execute','actions':['dispatch.blueprint'],'budget_template':'initial_per_page',
        'scope':record['scope'],'instruction_evidence':_declared(store),
        'base_revision':store.current_revision_id(),'operation_id':str(uuid.uuid4())})
    assert (http, code) == (409,4) and 'budget_exhausted' == response['error']['code']
    assert store.load_document() == before


def test_repeat_unspent_grants_share_numeric_root_and_replay_does_not_duplicate(tmp_path):
    path, store = project(tmp_path)
    first = grant(path, store)
    second = grant(path, store)
    assert store.read_object_json(second['authorization_ref'])['budget_parent_ref'] == first['authorization_ref']
    state = eligibility.authorization_budget(store, store.load_document(), second['authorization_ref'])
    assert state['ceiling'] == 2 and len(state['chain_ids']) == 2
    payload = {'mode':'execute','actions':['dispatch.blueprint'],'budget_template':'initial_per_page',
        'instruction_evidence':_declared(store),'base_revision':store.current_revision_id(),
        'operation_id':str(uuid.uuid4())}
    original = collaboration_api.invoke(path,'grant',payload)
    before = store.load_document()
    replay = collaboration_api.invoke(path,'grant',payload)
    assert original[1:] == replay[1:] == (200,0)
    assert replay[0]['result']['status'] == 'already_applied'
    assert store.load_document() == before


def test_smaller_explicit_cap_wins_and_cannot_be_raised_by_repeat(tmp_path):
    path, store = project(tmp_path)
    first = grant(path, store, max_external_calls=1)
    assert first['budget']['explicit_limit_conflict']
    second = grant(path, store, max_external_calls=50)
    assert store.read_object_json(second['authorization_ref'])['max_external_calls'] == 1
    assert eligibility.authorization_budget(store,store.load_document(),second['authorization_ref'])['ceiling'] == 1


def test_child_cannot_raise_numeric_parent_or_escape_root(tmp_path):
    path, store = project(tmp_path)
    parent = _grant(path,store,actions=('dispatch.blueprint',),mode='delegate',max_external_calls=1)
    before = store.load_document()
    with pytest.raises(ModelError,match='parent ceiling'):
        _grant(path,store,actions=('dispatch.blueprint',),max_external_calls=2,
            parent_authorization_ref=parent['authorization_ref'],operation_id='L1-child-too-large')
    assert store.load_document() == before
    child = _grant(path,store,actions=('dispatch.blueprint',),max_external_calls=1,
        parent_authorization_ref=parent['authorization_ref'],operation_id='L1-child-bounded')
    assert store.read_object_json(child['authorization_ref'])['budget_parent_ref'] == parent['authorization_ref']


def test_single_page_allowance_cannot_allocate_two_credits(tmp_path):
    path, store = project(tmp_path)
    authorization = grant(path, store)
    doc = store.load_document(); task = service.open_blueprint_task(store,doc,doc['pages'][0])
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        tasks.allocate_call_allowances(store,task_id=task['task_id'],count=1)
    assert 'budget_exhausted' in failure.value.payload()['error']['reason_codes']
    assert store.load_document() == before
    assert eligibility.authorization_budget(store,before,authorization['authorization_ref'])['remaining'] == 1


@pytest.mark.parametrize('outcome',['consumed','unknown'])
def test_failed_or_unknown_observation_never_refreshes_credit(tmp_path,outcome):
    path, store = project(tmp_path)
    result = grant(path,store)
    doc = store.load_document(); task = service.open_blueprint_task(store,doc,doc['pages'][0])
    spend(path,store,task,outcome=outcome)
    key = task['collaboration_binding']['budget_key']
    assert eligibility.credit_state(store,store.load_document(),key)['remaining'] == 0
    decision = eligibility.evaluate(store,store.load_document(),store.load_document(),'dispatch.blueprint',
        {'targets':{'page_ids':['p1'],'layers':['blueprint']}})
    assert 'budget_exhausted' in decision['reason_codes']
    if outcome == 'unknown':
        assert eligibility.authorization_budget(store,store.load_document(),result['authorization_ref'])['state'] == 'unknown'


def test_edit_budget_uses_actual_change_plan_and_refuses_stale_input(tmp_path):
    path, store = project(tmp_path,intent='edit')
    planned = changes.plan(path,input=change_input(store))
    preview = collaboration_budget.describe(path,budget_template='edit_rebuild_per_page',change_plan_id=planned['plan_id'])
    assert preview['must_redraw_page_ids'] == ['p1','p2']
    assert preview['max_external_calls'] == 2 and preview['retry_budget'] == 0
    authorized = grant(path,store,template='edit_rebuild_per_page',change_plan_id=planned['plan_id'])
    assert len(authorized['budget']['credits']) == 2
    with pytest.raises(ModelError,match='preview it against current control'):
        collaboration_budget.describe(path,budget_template='edit_rebuild_per_page',change_plan_id=planned['plan_id'])
    # The same explicit instruction re-previewed at the new control revision
    # does not mint credits; actual dispatch remains within the original root.
    replanned = changes.plan(path,input=change_input(store))
    committed = changes.commit(path,plan_id=replanned['plan_id'],base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    actual = [tasks._lookup_task(store.load_document(),tid,store) for tid in committed['task_ids']]
    assert len(actual) == 2
    for task in actual:
        assert task['collaboration_binding']['budget_key'].endswith(':rebuild:'+task['scope_pages'][0])
        spend(path,store,task)
    assert eligibility.authorization_budget(store,store.load_document(),authorized['authorization_ref'])['remaining'] == 0


def test_text_only_change_plan_never_gets_image_budget(tmp_path):
    path, store = project(tmp_path,intent='edit')
    planned = changes.plan(path,input=change_input(store,layer='content'))
    preview = collaboration_budget.describe(path,budget_template='edit_rebuild_per_page',change_plan_id=planned['plan_id'])
    assert preview['max_external_calls'] == 0 and preview['credits'] == []
    assert preview['must_redraw_page_ids'] == []


@pytest.mark.parametrize('intent', ['design_trial','content_only','review_only'])
def test_initial_template_never_broadens_non_full_deck_requests(tmp_path,intent):
    path, store = _project(tmp_path)
    _seed_imported_plan(store)
    _start(path,store,intent=intent,content_intent='content_full' if intent == 'content_only' else None)
    before = store.load_document()
    with pytest.raises(ModelError,match='request intent'):
        collaboration_budget.describe(path,budget_template='initial_per_page')
    assert store.load_document() == before


def test_client_cannot_forge_computed_budget_metadata(tmp_path):
    path, store = project(tmp_path)
    before = store.load_document()
    with pytest.raises(ModelError,match='computed by the Runtime'):
        collaboration.grant(path,input={'mode':'execute','actions':['dispatch.blueprint'],
            'constraints':{'fixed_budget':{'credits':[]}},'instruction_evidence':_declared(store)},
            base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    assert store.load_document() == before


def test_explicit_numeric_template_keeps_its_declared_cap_without_derived_credits(tmp_path):
    path, store = project(tmp_path)
    result = grant(path, store, template='explicit', max_external_calls=1)
    record = store.read_object_json(result['authorization_ref'])
    assert record['budget_template'] == 'explicit' and record['max_external_calls'] == 1
    assert 'fixed_budget' not in record['constraints']
    doc = store.load_document()
    task = service.open_blueprint_task(store, doc, doc['pages'][0])
    assert task['collaboration_binding']['authorization_ref'] == result['authorization_ref']
    spend(path, store, task)
    assert eligibility.authorization_budget(store, store.load_document(), result['authorization_ref'])['remaining'] == 0


def test_numeric_child_cannot_switch_to_an_unrelated_larger_root(tmp_path):
    path, store = project(tmp_path)
    parent = _grant(path,store,actions=('dispatch.blueprint',),mode='delegate',
        max_external_calls=1,operation_id='L1-small-parent')
    other = _grant(path,store,actions=('dispatch.blueprint',),mode='delegate',
        max_external_calls=10,operation_id='L1-other-large-budget')
    before = store.load_document()
    with pytest.raises(ModelError,match='share its numeric authority parent root'):
        _grant(path,store,actions=('dispatch.blueprint',),max_external_calls=1,
            parent_authorization_ref=parent['authorization_ref'],budget_parent_ref=other['authorization_ref'],
            operation_id='L1-root-switch-refused')
    assert store.load_document() == before


def test_subset_budget_never_attaches_a_whole_deck_manifest(tmp_path):
    path, store = project(tmp_path)
    result = grant(path,store,scope=_scope(page_ids=['p1']))
    record = store.read_object_json(result['authorization_ref'])
    assert record['scope']['page_ids'] == ['p1'] and record['scope']['page_manifest_ref'] is None
    decision = eligibility.evaluate(store,store.load_document(),store.load_document(),'dispatch.blueprint',
        {'targets':{'page_ids':['p2'],'layers':['blueprint']}})
    assert decision['allowed'] is False


def test_stale_adopted_plan_and_future_page_never_receive_credits(tmp_path):
    path, store = project(tmp_path)
    before = store.load_document()
    with pytest.raises(ModelError,match='current adopted Plan'):
        collaboration_budget.describe(path,budget_template='initial_per_page',plan_ref=_declared(store)['source_ref'])
    with pytest.raises(ModelError,match='current adopted Plan'):
        collaboration_budget.describe(path,budget_template='initial_per_page',scope=_scope(page_ids=['future-page']))
    assert store.load_document() == before


def test_reuse_requires_current_legal_blueprint_lineage(tmp_path):
    from test_budget_templates import _with_blueprint
    from deck_master.models import bump_revision
    path, store = project(tmp_path)
    original = _with_blueprint(store,'p1')
    before = store.load_document()
    preview = collaboration_budget.describe(path,budget_template='initial_per_page')
    assert preview['reused_page_ids'] == ['p1'] and preview['max_external_calls'] == 1
    page = store.read_object_json(before['pages'][0]['page'])
    page['customer_visible']['title'] = 'A different visible manuscript'
    updated = bump_revision(before,{'operation_id':'L1-stale-lineage','kind':'content_update',
        'description':'Explicit L1 stale image lineage counterexample','read_set':[]})
    updated['pages'][0]['page'] = store.put_json_object(page)
    store.commit_change(base_revision=before['revision_id'],document=updated,operation_id='L1-stale-lineage')
    preview = collaboration_budget.describe(path,budget_template='initial_per_page')
    assert preview['reused_page_ids'] == [] and preview['max_external_calls'] == 2
    assert store.load_document()['pages'][0]['blueprint'] == original


def test_new_explicit_grant_shares_revoked_numeric_history_without_reviving_authority(tmp_path):
    path, store = project(tmp_path)
    first = grant(path,store)
    collaboration.revoke_authorization(path,authorization_id=first['authorization_id'],reason='L1 withdraw unused authority',
        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()),instruction_evidence=_declared(store))
    second = grant(path,store)
    record = store.read_object_json(second['authorization_ref'])
    assert record['parent_authorization_ref'] is None
    assert eligibility.authorization_budget(store,store.load_document(),second['authorization_ref'])['ceiling'] == 2
    from deck_master import dependency_slices
    assert not dependency_slices.authorization_effectiveness(store,store.load_document(),first['authorization_ref'])['effective']
    assert dependency_slices.authorization_effectiveness(store,store.load_document(),second['authorization_ref'])['effective']
    doc = store.load_document(); task = service.open_blueprint_task(store,doc,doc['pages'][0])
    assert task['collaboration_binding']['authorization_ref'] == second['authorization_ref']
    spend(path,store,task)
    collaboration.revoke_authorization(path,authorization_id=second['authorization_id'],reason='L1 withdraw after fact',
        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()),instruction_evidence=_declared(store))
    before = store.load_document()
    response,http,code = collaboration_api.invoke(path,'grant',{'mode':'execute',
        'actions':['dispatch.blueprint'],'budget_template':'initial_per_page',
        'instruction_evidence':_declared(store),'operation_id':str(uuid.uuid4()),'base_revision':store.current_revision_id()})
    assert (http,code) == (409,4) and response['error']['code'] == 'budget_exhausted'
    assert store.load_document() == before


def test_explicit_empty_pages_scope_never_expands_in_preview_or_grant(tmp_path):
    path,store=project(tmp_path)
    scope=_scope(subject='pages',page_ids=[],page_manifest_ref=None)
    before=store.load_document()
    with pytest.raises(ModelError,match="empty page set is not 'all pages'"):
        collaboration_budget.describe(path,budget_template='initial_per_page',scope=scope)
    response,http,code=collaboration_api.invoke(path,'grant',{'mode':'execute',
        'actions':['dispatch.blueprint'],'budget_template':'initial_per_page','scope':scope,
        'instruction_evidence':_declared(store),'base_revision':store.current_revision_id(),
        'operation_id':str(uuid.uuid4())})
    assert (http,code)==(400,2) and response['error']['code']=='invalid_input'
    assert store.load_document()==before


def test_manifest_only_fixed_parent_materializes_without_future_selector(tmp_path):
    path,store=project(tmp_path)
    scope=_scope(subject='deck',page_ids=[],page_manifest_ref=store.load_document()['content_plan'])
    parent=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),scope=scope,
        max_external_calls=0,operation_id='L1-manifest-only-parent')
    child=collaboration_budget.materialize_execution(path,parent_authorization_ref=parent['authorization_ref'],
        budget_template='initial_per_page',base_revision=store.current_revision_id(),
        operation_id='L1-manifest-only-child',instruction_evidence=_declared(store))
    record=store.read_object_json(child['authorization_ref'])
    assert record['scope']['page_ids']==['p1','p2']
    assert record['max_external_calls']==2
    assert record['parent_authorization_ref']==parent['authorization_ref']


def test_explicit_single_page_materialization_never_expands_through_parent_manifest(tmp_path):
    path,store=project(tmp_path)
    scope=_scope(subject='deck',page_ids=[],page_manifest_ref=store.load_document()['content_plan'])
    parent=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),scope=scope,
        max_external_calls=0,operation_id='L1-manifest-subset-parent')
    before=store.load_document()
    with pytest.raises(ModelError,match='explicit page_order cannot be expanded'):
        collaboration_budget.materialize_execution(path,parent_authorization_ref=parent['authorization_ref'],
            page_order=['p1'],budget_template='initial_per_page',base_revision=store.current_revision_id(),
            operation_id='L1-manifest-subset-refused',instruction_evidence=_declared(store))
    assert store.load_document()==before


def test_project_info_remains_readable_after_template_grant_without_action_targets(tmp_path):
    from deck_master import ui_journal
    from deck_master.web import UI_CAPABILITIES
    path,store=project(tmp_path)
    grant(path,store)
    before=store.load_document()
    assert ui_journal.project_info(path,server_capabilities=UI_CAPABILITIES)['revision_id']==before['revision_id']
    assert store.load_document()==before


@pytest.mark.parametrize('empty_scope',[{},None])
def test_explicit_empty_scope_object_never_defaults_to_whole_request(tmp_path,empty_scope):
    path,store=project(tmp_path)
    before=store.load_document()
    response,http,code=collaboration_api.invoke(path,'grant',{'mode':'execute',
        'actions':['dispatch.blueprint'],'budget_template':'initial_per_page','scope':empty_scope,
        'instruction_evidence':_declared(store),'base_revision':store.current_revision_id(),
        'operation_id':str(uuid.uuid4())})
    assert (http,code)==(400,2)
    assert store.load_document()==before


def test_fixed_manifest_zero_call_delegate_materializes_a_real_executable_child(tmp_path):
    path,store=project(tmp_path)
    scope=_scope(subject='deck',page_ids=[],page_manifest_ref=store.load_document()['content_plan'])
    parent=_grant(path,store,mode='delegate',actions=('dispatch.blueprint',),scope=scope,
        max_external_calls=0,operation_id='L1-zero-call-fixed-delegate')
    child=collaboration_budget.materialize_execution(path,parent_authorization_ref=parent['authorization_ref'],
        budget_template='initial_per_page',base_revision=store.current_revision_id(),
        operation_id='L1-zero-call-execute-child',instruction_evidence=_declared(store))
    doc=store.load_document();task=service.open_blueprint_task(store,doc,doc['pages'][0])
    assert task['collaboration_binding']['authorization_ref']==child['authorization_ref']
    assert task['collaboration_binding']['budget_key'].endswith(':initial:p1')
    spend(path,store,task)
    assert eligibility.authorization_budget(store,store.load_document(),parent['authorization_ref'])['ceiling']==0
    assert eligibility.authorization_budget(store,store.load_document(),child['authorization_ref'])['used']==1


def test_old_zero_execute_does_not_shadow_new_explicit_positive_grant(tmp_path):
    path,store=project(tmp_path)
    original=_grant(path,store,actions=('dispatch.blueprint',),max_external_calls=0,
        operation_id='L1-old-zero-execute')
    current=grant(path,store,instruction_evidence={'kind':'host_attested_instruction',
        'text':'Explicit new L1 full-deck production authority: use the fixed per-page budget once.',
        'source_locator':'L1:new-budget-source'})
    doc=store.load_document();task=service.open_blueprint_task(store,doc,doc['pages'][0])
    assert task['collaboration_binding']['authorization_ref']==current['authorization_ref']
    spend(path,store,task)
    assert eligibility.authorization_budget(store,store.load_document(),original['authorization_ref'])['used']==0
    assert eligibility.authorization_budget(store,store.load_document(),current['authorization_ref'])['used']==1


def test_bound_task_cannot_borrow_new_larger_grant_but_its_last_held_call_can_finish(tmp_path):
    path,store=project(tmp_path)
    original=_grant(path,store,actions=('dispatch.blueprint',),max_external_calls=1,
        operation_id='L1-original-one-call')
    doc=store.load_document();task=service.open_blueprint_task(store,doc,doc['pages'][0])
    assert task['collaboration_binding']['authorization_ref']==original['authorization_ref']
    added=_grant(path,store,actions=('dispatch.blueprint',),max_external_calls=10,
        operation_id='L1-explicit-extra-grant',instruction_evidence={
            'kind':'host_attested_instruction','text':'Explicit new L1 extra bounded authority; retain prior Task bindings.',
            'source_locator':'L1:explicit-extra-source'})
    before=store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        tasks.allocate_call_allowances(store,task_id=task['task_id'],count=1)
    assert 'budget_exhausted' in failure.value.payload()['error']['reason_codes']
    assert store.load_document()==before
    assert eligibility.authorization_budget(store,before,added['authorization_ref'])['used']==0
    spend(path,store,task)
    assert eligibility.authorization_budget(store,store.load_document(),original['authorization_ref'])['used']==1
    assert eligibility.authorization_budget(store,store.load_document(),added['authorization_ref'])['used']==0
