"""Two public Task lifecycles; all native controller observations are synthetic."""
import copy
import pytest
from deck_master import generation, service, tasks, production, workbench
from deck_master.models import canonical_json_bytes
from deck_master.native_image_evidence import image_binding, NativeImageRegistry, NativeImageRuntime
from test_generation_protocol import flow, accept
from test_rc3_native_image_bridge import prepared, SyntheticController, issue, settle_native
from rc3_fixtures import authorize_scope, evidence_for


def pair(flow, *, parameters=None):
    project,store,b,_=flow
    frozen_b,attempt_b,provider,registry=prepared(flow)
    with NativeImageRuntime(registry).bound():
        settle_native(flow,attempt_b,issue(flow,attempt_b,registry))
    accept(flow,frozen_b,attempt_b,provider.png)
    doc=store.load_document()
    scope=copy.deepcopy(doc['collaboration']['request']['scope'])
    authorize_scope(project, actions=['generation.reuse'],scope=scope,max_external_calls=0,
        max_candidate_count=0,adoption_policy='within_scope',evidence=evidence_for(project,
        text='Explicitly reuse the settled same-project native original under current scope.',locator='L1:reuse'))
    doc=store.load_document()
    a=service.open_blueprint_task(store,doc,doc['pages'][0])
    service.task_start(project,task_id=a['task_id'],execution_ref='synthetic-distinct-reuse-A',
        supported_protocols=[generation.PROTOCOL],capabilities=a['required_capabilities'])
    value=generation.prepared_input(store,store.load_document(),a)
    if parameters is not None:value['parameters']=parameters
    frozen_a=generation.freeze(project,task_id=a['task_id'],input=value,
        base_revision=store.current_revision_id(),operation_id='reuse-freeze-a')
    attempt_a=tasks.call_begin(store,task_id=a['task_id'],allowance_id='call-1',
        execution_ref='synthetic-distinct-reuse-A',request_id=frozen_a['request_id'])
    tasks.call_settle(store,task_id=a['task_id'],allowance_id='call-1',attempt_id=attempt_a['attempt_id'],
        outcome='consumed',report_bytes=canonical_json_bytes({'source':'host_reported','note':'A consumption reported; no native output claim'}))
    stage=store.staging_dir/a['operation_id'];stage.mkdir(exist_ok=True);(stage/'result.png').write_bytes(provider.png)
    payload={'kind':'blueprint','files':[{'file_id':'output','path':'result.png','media_type':'image/png'}],
        'generation_result':{'request_id':frozen_a['request_id'],'attempt_id':attempt_a['attempt_id'],
            'reuse_from':{'task_id':b['task_id'],'request_id':frozen_b['request_id'],'attempt_id':attempt_b['attempt_id']}},
        'artifact_specs':[{'role':'blueprint','page_id':'p1','file_id':'output',
            'provenance':{'source_type':'host_generated','tool':'image_gen'}}]}
    return a,b,payload,provider.png


def submit(flow,a,payload):
    return service.accept_result(flow[0],result_payload=payload,**{k:a[k] for k in ('task_id','operation_id','produced_against')})


def test_two_settled_calls_reuse_native_b_without_rewriting_a(flow):
    a,b,payload,png=pair(flow)
    store=flow[1];before=store.load_document();floor=before['compatibility']['minimum_writer']
    b_before=tasks._lookup_task(before,b['task_id'],store)
    a_before=tasks._lookup_task(before,a['task_id'],store)
    assert tasks.task_inputs_current(store,before,b_before)
    assert floor!='settled-image-reuse.v1'
    result=submit(flow,a,payload)
    assert result['status']=='accepted'
    doc=store.load_document();artifact=store.read_object_json(doc['pages'][0]['blueprint'])
    association=store.read_object_json(artifact['provenance']['generation_reuse'])
    assert association['destination_task_id']==a['task_id']
    assert association['source_task_id']==b['task_id']
    assert artifact['provenance']['generation_attempt']==association['source_attempt_ref']
    assert store.read_object_bytes(artifact['file'])==png
    assert tasks._lookup_task(doc,b['task_id'],store)==b_before
    after_a=tasks._lookup_task(doc,a['task_id'],store)
    assert after_a['call_allowances']==a_before['call_allowances']
    assert after_a['generation_attempts']==a_before['generation_attempts']
    assert sum(c['state']=='consumed' for t in (after_a,b_before) for c in t['call_allowances'])==2
    assert doc['compatibility']['minimum_writer']=='settled-image-reuse.v1'
    assert production.adopted_blueprint_design(store,doc,doc['pages'][0])['resolved_design_context']
    from deck_master.models import validate_schema, _contract_registry
    lineage=workbench.page_lineage(flow[0],'p1')
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    from referencing import Registry,Resource
    folder=Path(__file__).parents[2]/'src/deck_master/resources/contracts'
    shared=json.loads((folder/'workbench-summary.v1.schema.json').read_text())
    registry=Registry().with_resource(shared['$id'],Resource.from_contents(shared))
    Draft202012Validator(json.loads((folder/'page-lineage.v1.schema.json').read_text()),registry=registry).validate(lineage)
    assert lineage['generation']['reuse']==association
    assert lineage['generation']['adopted_observation']['collector']=='native-host-image.v1'
    assert not lineage['generation']['errors']
    revision=doc['revision_id']
    assert submit(flow,a,payload)['status']=='already_applied'
    assert store.current_revision_id()==revision


def replace_task(store,task_id,change):
    """Explicit corrupt-state/fault fixture; never used for positive setup."""
    from deck_master.models import bump_revision
    doc=store.load_document();updated=copy.deepcopy(doc)
    for index,ref in enumerate(updated['tasks']):
        task=store.read_object_json(ref)
        if task['task_id']==task_id:
            change(task)
            updated['tasks'][index]=store.put_json_object(task)
    updated=bump_revision(updated,{'operation_id':'reuse-negative-fixture','kind':'task_update','description':'Synthetic fault injection','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='reuse-negative-fixture')


@pytest.mark.parametrize('fault',['unknown','in_flight','source_cancelled','source_superseded','trial','source_trial',
    'old_capability','foreign_request','missing_native','output','selector','association_injection','same_task','same_execution'])
def test_reuse_faults_fail_without_refunding_or_reassigning_calls(flow,fault):
    from deck_master.store import StoreError
    a,b,payload,_=pair(flow);store=flow[1]
    target=a['task_id']
    if fault in ('unknown','in_flight'):
        replace_task(store,target,lambda t:t['call_allowances'][0].update(state=fault))
    elif fault=='source_trial':
        replace_task(store,b['task_id'],lambda t:t.update(stage_request={'mode':'trial','stage':'blueprint','references':[]}))
    elif fault.startswith('source_'):
        replace_task(store,b['task_id'],lambda t:t.update(status=fault.removeprefix('source_')))
    elif fault=='trial':
        replace_task(store,target,lambda t:t.update(stage_request={'mode':'trial','stage':'blueprint','references':[]}))
    elif fault=='old_capability':
        replace_task(store,target,lambda t:(t['required_capabilities'].remove('settled_image_reuse_v1'),t['host_protocol']['capabilities'].remove('settled_image_reuse_v1')))
    elif fault=='foreign_request':
        payload['generation_result']['reuse_from']['request_id']=payload['generation_result']['request_id']
    elif fault=='missing_native':
        def strip(t):
            attempt=store.read_object_json(t['generation_attempts'][0]);attempt['observations']=[]
            t['generation_attempts'][0]=store.put_json_object(attempt)
        replace_task(store,b['task_id'],strip)
    elif fault=='output':
        (store.staging_dir/a['operation_id']/'result.png').write_bytes(b'not-the-native-output')
    elif fault=='selector':
        payload['generation_result']['reuse_from']['receipt']={'authentication':'protected_transport'}
    elif fault=='association_injection':
        payload['artifact_specs'][0]['provenance']['generation_reuse']=store.put_json_object({'fake':True})
    elif fault=='same_task':
        payload['generation_result']['reuse_from'].update(task_id=a['task_id'],request_id=payload['generation_result']['request_id'],attempt_id=payload['generation_result']['attempt_id'])
    elif fault=='same_execution':
        def same(t):
            attempt=store.read_object_json(t['generation_attempts'][0]);attempt['execution_ref']=tasks._lookup_task(store.load_document(),b['task_id'],store)['execution_ref']
            t['call_allowances'][0]['execution_ref']=attempt['execution_ref'];t['generation_attempts'][0]=store.put_json_object(attempt)
        replace_task(store,target,same)
    before=store.load_document()
    with pytest.raises((StoreError,tasks.EnvelopeError)) as caught:submit(flow,a,payload)
    if fault in ('unknown','in_flight','missing_native'):
        assert caught.value.error_code=='generation_reuse_invalid'
        assert caught.value.path==('observation' if fault=='missing_native' else 'allowance')
    assert store.load_document()==before


@pytest.mark.parametrize('control',['pause','revoke_reuse','revoke_original','cancel_a'])
def test_current_public_control_blocks_late_reuse(flow,control):
    from deck_master import collaboration
    from deck_master.store import StoreError
    a,b,payload,_=pair(flow);store=flow[1];doc=store.load_document()
    if control=='pause':
        collaboration.pause_request(flow[0],reason='Synthetic pause',base_revision=doc['revision_id'],operation_id='reuse-pause')
    elif control.startswith('revoke'):
        if control=='revoke_original':ref=a['collaboration_binding']['authorization_ref']
        else:ref=next(ref for ref,record in __import__('deck_master.eligibility',fromlist=[''])._authorization_heads(store,doc) if 'generation.reuse' in record['actions'])
        collaboration.revoke_authorization(flow[0],authorization_id=store.read_object_json(ref)['authorization_id'],reason='Synthetic withdraw',base_revision=doc['revision_id'],operation_id='reuse-revoke')
    else:service.task_cancel(flow[0],task_id=a['task_id'],reason='Synthetic stop')
    before=store.load_document()
    with pytest.raises((StoreError,tasks.EnvelopeError)) as caught:submit(flow,a,payload)
    after=store.load_document()
    if control=='cancel_a':
        assert after['pages']==before['pages'] and after['outputs']==before['outputs']
        for item in (a,b):
            old=tasks._lookup_task(before,item['task_id'],store)
            new=tasks._lookup_task(after,item['task_id'],store)
            assert old['call_allowances']==new['call_allowances']
            assert old['result_refs']==new['result_refs']
        assert tasks.read_operation_journal(store,a['operation_id'])['status']=='late_result_settled'
    else:
        assert after==before
        if control.startswith('revoke'):
            assert 'authorization_revoked' in caught.value.decision['reason_codes']


def test_changed_replay_conflicts_and_exact_replay_survives_pause(flow):
    from deck_master import collaboration
    from deck_master.store import StoreError
    a,b,payload,_=pair(flow);store=flow[1];submit(flow,a,payload)
    doc=store.load_document()
    collaboration.pause_request(flow[0],reason='After accepted reuse',base_revision=doc['revision_id'],operation_id='pause-after-reuse')
    before=store.load_document()
    assert submit(flow,a,payload)['status']=='already_applied'
    changed=copy.deepcopy(payload);changed['generation_result']['reuse_from']['task_id']=a['task_id']
    with pytest.raises((StoreError,tasks.EnvelopeError)):submit(flow,a,changed)
    assert store.load_document()==before


def test_lowered_original_budget_refuses_zero_call_reuse(flow):
    from deck_master import collaboration
    from deck_master.store import StoreError
    a,b,payload,_=pair(flow);store=flow[1];doc=store.load_document()
    ref=a['collaboration_binding']['authorization_ref'];record=store.read_object_json(ref)
    replacement={k:copy.deepcopy(record[k]) for k in ('authorization_id','mode','actions','scope','max_candidate_count','adoption_policy')}
    replacement.update(replaces=ref,max_external_calls=1,instruction_evidence=evidence_for(flow[0],text='Lower original bounded grant to one call; existing spend remains.',locator='L1:reuse-lower'))
    collaboration.grant(flow[0],input=replacement,base_revision=doc['revision_id'],operation_id='reuse-lower')
    before=store.load_document()
    from deck_master.generation_reuse import budget_current
    from deck_master.eligibility import EligibilityBlocked
    with pytest.raises(generation.GenerationError) as budget:
        budget_current(store,before,a)
    assert budget.value.path=='budget' and budget.value.error_code=='generation_reuse_invalid'
    with pytest.raises(EligibilityBlocked) as blocked:submit(flow,a,payload)
    assert blocked.value.error_code=='binding_invalid'
    assert store.load_document()==before


def test_reuse_failed_commit_leaves_no_association_or_budget_change_then_recovers(flow,monkeypatch):
    from deck_master.store import Store,ConflictError
    a,b,payload,_=pair(flow);store=flow[1];before=store.load_document()
    commit=Store._commit_locked
    def fail(self,**kwargs):
        if kwargs.get('operation_id')==a['operation_id']:
            raise ConflictError('base_revision','Synthetic CAS conflict before pointer publication')
        return commit(self,**kwargs)
    with monkeypatch.context() as context:
        context.setattr(Store,'_commit_locked',fail)
        with pytest.raises(ConflictError):submit(flow,a,payload)
    assert store.load_document()==before
    assert submit(flow,a,payload)['status']=='accepted'
    assert submit(flow,a,payload)['status']=='already_applied'


def test_original_image_reuse_stays_unavailable_to_ordinary_receipt_json(flow):
    from deck_master.store import StoreError
    a,b,payload,_=pair(flow);store=flow[1]
    def counterfeit(task):
        attempt=store.read_object_json(task['generation_attempts'][0])
        observation=store.read_object_json(attempt['observations'][0])
        receipt=store.read_object_json(observation['source']['receipt_ref'])
        receipt['claims']['binding']['execution_ref']='fabricated-A'
        observation['source']['receipt_ref']=store.put_json_object(receipt)
        attempt['observations']=[store.put_json_object(observation)]
        task['generation_attempts']=[store.put_json_object(attempt)]
    replace_task(store,b['task_id'],counterfeit)
    before=store.load_document()
    with pytest.raises(StoreError,match='persisted native evidence'):submit(flow,a,payload)
    assert store.load_document()==before


def test_real_distinct_frozen_parameters_refuse_reuse(flow):
    a,b,payload,_=pair(flow,parameters={'transparent_background':True})
    before=flow[1].load_document()
    with pytest.raises(generation.GenerationError) as caught:submit(flow,a,payload)
    assert caught.value.error_code=='generation_reuse_invalid' and caught.value.path=='input'
    assert flow[1].load_document()==before


def test_published_reuse_recovers_after_lost_response(flow,monkeypatch):
    from deck_master.store import Store
    a,b,payload,_=pair(flow);store=flow[1];commit=Store._commit_locked
    def lost(self,**kwargs):
        result=commit(self,**kwargs)
        if kwargs.get('operation_id')==a['operation_id']:
            raise OSError('Synthetic lost response after durable commit')
        return result
    with monkeypatch.context() as context:
        context.setattr(Store,'_commit_locked',lost)
        with pytest.raises(OSError,match='lost response'):submit(flow,a,payload)
    before=store.load_document()
    assert submit(flow,a,payload)['status']=='already_applied'
    assert store.load_document()==before
    assert before['compatibility']['minimum_writer']=='settled-image-reuse.v1'


def test_old_writer_refuses_committed_reuse_floor(flow,monkeypatch):
    import deck_master.store as store_module
    a,b,payload,_=pair(flow);submit(flow,a,payload)
    before=flow[1].current_revision_id()
    with monkeypatch.context() as context:
        context.setattr(store_module,'SUPPORTED_WRITERS',tuple(x for x in store_module.SUPPORTED_WRITERS if x!='settled-image-reuse.v1'))
        with pytest.raises(store_module.StoreError,match='writer'):
            store_module.Store(flow[0]).load_document()
    assert flow[1].current_revision_id()==before


def test_source_report_cannot_overwrite_settled_original_after_reuse(flow):
    a,b,payload,_=pair(flow);submit(flow,a,payload);store=flow[1]
    task=tasks._lookup_task(store.load_document(),b['task_id'],store)
    attempt=store.read_object_json(task['generation_attempts'][0])
    before=store.load_document()
    with pytest.raises(tasks.TaskConflict,match='conflicting settlement report'):
        tasks.call_settle(store,task_id=b['task_id'],allowance_id=attempt['allowance_id'],attempt_id=attempt['attempt_id'],
            outcome='consumed',report_bytes=canonical_json_bytes({'source':'host_reported','note':'Supplementary report, not a new call'}))
    doc=store.load_document()
    assert doc==before
    assert production.adopted_blueprint_design(store,doc,doc['pages'][0])


def test_historical_contract_can_explicitly_negotiate_reuse_without_new_call(flow,monkeypatch):
    # Issue the destination with the historical required capability contract,
    # through the public dispatcher. No Task/Attempt record is edited.
    with monkeypatch.context() as context:
        context.setattr(generation,'CAPABILITIES',[c for c in generation.CAPABILITIES if c!='settled_image_reuse_v1'])
        a,b,payload,_=pair(flow)
    store=flow[1];before=tasks._lookup_task(store.load_document(),a['task_id'],store)
    with pytest.raises(generation.GenerationError) as blocked:submit(flow,a,payload)
    assert blocked.value.path=='host_protocol'
    service.task_start(flow[0],task_id=a['task_id'],execution_ref=before['execution_ref'],
        supported_protocols=before['host_protocol']['supported_protocols'],
        capabilities=before['host_protocol']['capabilities']+['settled_image_reuse_v1'])
    assert submit(flow,a,payload)['status']=='accepted'
    after=tasks._lookup_task(store.load_document(),a['task_id'],store)
    for key in ('required_capabilities','method_manifest','generation_requests','generation_attempts','call_allowances','execution_ref'):
        assert after.get(key)==before.get(key)
