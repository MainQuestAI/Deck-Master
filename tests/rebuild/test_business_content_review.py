"""D04 transaction/criteria mechanisms; synthetic contents and reviewer transports.

These tests do not establish live semantic reviewer performance or author approval.
"""
import copy
import json

import pytest

from deck_master import business_review as business, collaboration, content_production, content_review, models, native_review, outline_review, service, tasks
from test_business_framing import proposals, adoption_request, SCOPE
from test_content_preproduction_review import _deck, _page
from test_native_review import FixtureSession
from test_workbench_reads import commit


@pytest.fixture
def native(monkeypatch):
    FixtureSession.calls=[];FixtureSession.status='pass';FixtureSession.corrupt=False;FixtureSession.before_finish=None
    monkeypatch.setattr(native_review,'CodexReviewSession',FixtureSession)
    return FixtureSession


def adopted(tmp_path):
    path,store,refs=proposals(tmp_path);_,decision=adoption_request(path,store,refs)
    for i,ref in enumerate(refs):
        content_production.adopt_proposal(path,input={'proposal_ref':ref,'decision_ref':decision,'write_scope':SCOPE},
            base_revision=store.current_revision_id(),operation_id=f'adopt-for-d04-{i}')
    return path,store


def full_request(path,store):
    request=store.load_document()['collaboration']['request']
    collaboration.start_request(path,input={'intent':'content_only','content_intent':'content_full',
        'replace_request_id':request['request_id'],'scope':{**SCOPE,'layers':['narrative','plan','page_copy','speech','review'],
            'allow_page_membership_change':True},'instruction_evidence':{'kind':'host_attested_instruction',
                'text':'Synthetic explicit full content request; no visual production.','source_locator':'test:d04-full-content'}},
        base_revision=store.current_revision_id(),operation_id='d04-full-request')


def test_versioned_packet_and_unavailable_channel_are_read_only(tmp_path):
    path,store=adopted(tmp_path);before=store.load_document()
    packet=outline_review.packet(store,before);view=packet['business_review'];standard=view['standard']
    assert standard['version']==business.VERSION and standard['method']['id']=='method-review'
    assert '只在标题' in standard['criteria_text'] and '首提／竞标' in standard['criteria_text']
    assert view['topics'][0]['planned_page_ids']==['p1'] and 'topic:handoff' in view['finding_locations']
    assert packet['effective_requirements']['argument']['business_review_standard']==standard['dependency']
    result=outline_review.dispatch(path)
    assert result['status']=='needs_reviewer' and result['review_draft']['business_review']==view
    assert store.load_document()==before and not models.writer_at_least(before,business.CAPABILITY)


def test_native_binding_and_new_writer_are_atomic(tmp_path,native):
    path,store=adopted(tmp_path);result=native_review.run(path,subject='outline');doc=store.load_document()
    assert result['preproduction']['status']=='pass' and not result['preproduction']['production_qualified']
    task=next(store.read_object_json(r) for r in doc['tasks'] if store.read_object_json(r)['task_id']==result['task_id'])
    assert business.CAPABILITY in task['required_capabilities'] and models.writer_at_least(doc,business.CAPABILITY)
    standard=business.frozen_standard(store,task)
    assert standard==business.standard(store,doc)
    assert all(standard['dependency'] in store.read_object_json(r)['dependencies'] for r in doc['reviews'])
    assert native.calls[-1]['packet']['business_review']['standard']==standard
    assert native_review.run(path,subject='outline')['status']=='already_reviewed' and len(native.calls)==1


def test_old_review_is_retained_but_cannot_satisfy_new_criteria(tmp_path,native,monkeypatch):
    path,store=adopted(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(business,'standard',lambda *a:None)
        native_review.run(path,subject='outline')
    before=store.load_document();raw={r['sha256']:store.read_object_bytes(r) for r in before['reviews']}
    assert outline_review.status(store,before)['status']=='missing'
    assert store.load_document()==before
    assert all(store.read_object_bytes(r)==raw[r['sha256']] for r in before['reviews'])
    assert all(store.read_object_json(r)['status']=='pass' for r in before['reviews'])


def test_frozen_review_requires_standard_and_real_finding_location(tmp_path,native):
    path,store=adopted(tmp_path);native_review.run(path,subject='outline');doc=store.load_document()
    task=store.read_object_json(doc['tasks'][-1]);review=copy.deepcopy(store.read_object_json(doc['reviews'][0]))
    review['dependencies']=[d for d in review['dependencies'] if d['kind']!='policy']
    with pytest.raises(models.ModelError,match='frozen business standard'):business.validate_result(store,task,[review])
    review['dependencies'].append(business.frozen_standard(store,task)['dependency'])
    finding={'element_refs':['topic:invented'],'evidence':[doc['narrative']]};review['findings']=[finding]
    with pytest.raises(models.ModelError,match='actual frozen content locator'):business.validate_result(store,task,[review])
    finding['element_refs']=['topic:handoff'];business.validate_result(store,task,[review])


def test_changed_criteria_retire_pending_task_without_rewriting_it(tmp_path,monkeypatch):
    from synthetic_review_provider import synthetic_context,synthetic_runtime_call
    path,store=adopted(tmp_path)
    result=synthetic_runtime_call(outline_review.dispatch,path,adapter_context=synthetic_context())
    task=result['task'];original=business.standard
    def changed(*a):
        value=copy.deepcopy(original(*a))
        if value:value['dependency']['sha256']='a'*64
        return value
    with monkeypatch.context() as patch:
        patch.setattr(business,'standard',changed)
        assert not tasks.task_inputs_current(store,store.load_document(),task)
    assert tasks.task_inputs_current(store,store.load_document(),task)
    assert business.frozen_standard(store,task)==original(store,store.load_document())


def test_expansion_requires_outline_even_at_direct_dispatch_then_keeps_role_basis(tmp_path,native):
    path,store=adopted(tmp_path);full_request(path,store);before=store.load_document()
    assert content_production.content_phase_status(store,before)['reason']=='business_outline_review_required'
    with pytest.raises(models.ModelError,match='current argument/progression'):
        content_production.open_phase_task(store,before,operation_id='premature-copy',phase='page_copy')
    assert store.load_document()==before
    native_review.run(path,subject='outline');doc=store.load_document();plan=store.read_object_json(doc['content_plan'])['input']
    changed=copy.deepcopy(plan);changed['page_roles'][0]['narrative_node_ids']=[]
    with pytest.raises(models.ModelError,match='retain adopted role nodes'):
        business.validate_expansion(store,doc,plan['page_order'],changed)
    with pytest.raises(models.ModelError,match='adopted planned order'):
        business.validate_expansion(store,doc,['other'],plan)
    task=content_production.open_phase_task(store,doc,operation_id='actual-copy',phase='page_copy')
    assert '不能只改标题' in task['instruction'] and '不声称已连通' in task['instruction']
    page=_page(store,doc,'p1')
    service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-d04-copy',supported_protocols=['compose.v2'],capabilities=task['required_capabilities'])
    result=service.accept_result(path,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],
        result_payload={'schema_version':'compose_result.v2','kind':'compose','variant':'page_copy','task_id':task['task_id'],
            'operation_id':task['operation_id'],'produced_against':task['produced_against'],
            'eligibility_digest':task['collaboration_binding']['eligibility_digest'],
            'payload':{'pages':[page],'page_order':['p1'],'plan_input':plan},'usage_events':[]})
    assert result['status']=='accepted'
    doc=store.load_document();packet=content_review.build_review_packet(store,doc)
    assert len(packet['manuscript']['pages'])==1 and packet['manuscript']['pages'][0]['speaker_notes']==page['speaker_notes']
    assert 'atom:p1:block:b1:text' in packet['business_review']['finding_locations']
    assert content_review.preproduction_status(store,doc)['status']!='pass'
    assert doc['collaboration']['request']['closed']
    collaboration.start_request(path,input={'intent':'content_only','content_intent':'speech_only',
        'scope':{**SCOPE,'subject':'pages','page_ids':['p1'],'layers':['speech']},
        'instruction_evidence':{'kind':'host_attested_instruction','text':'Explicit synthetic speech-only continuation.',
                                'source_locator':'test:d04-speech-continuation'}},
        base_revision=store.current_revision_id(),operation_id='d04-speech-request')
    doc=store.load_document()
    speech=content_production.open_phase_task(store,doc,operation_id='actual-speech',phase='speech',page_ids=['p1'])
    assert '不重新造框架' in speech['instruction']


def test_legacy_packet_does_not_acquire_business_standard(tmp_path):
    _,store=_deck(tmp_path);packet=content_review.build_review_packet(store,store.load_document())
    assert 'business_review' not in packet and all('business_review_standard' not in r for r in packet['effective_requirements'].values())


def test_new_standard_rechecks_prior_owner_instead_of_relabeling_it(tmp_path,native,monkeypatch):
    path,store=adopted(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(business,'standard',lambda *a:None)
        native_review.run(path,subject='outline')
    old_refs=copy.deepcopy(store.load_document()['reviews'])
    class RecheckingSession(FixtureSession):
        def review(self,prompt,schema):
            observation=super().review(prompt,schema);value=json.loads(observation['raw_final_message'])
            owners={r['kind']:r['review_ref'] for r in self.calls[-1]['packet']['review_scope']['owners']}
            for row in value['reviews']:row['replaces']=owners[row['kind']]
            observation['raw_final_message']=json.dumps(value);return observation
    monkeypatch.setattr(native_review,'CodexReviewSession',RecheckingSession)
    assert native_review.run(path,subject='outline')['preproduction']['status']=='pass'
    doc=store.load_document();new=[r for r in doc['reviews'] if r not in old_refs]
    assert len(new)==2 and all(store.read_object_json(r)['replaces'] in old_refs for r in new)
    assert all(business.standard(store,doc)['dependency'] in store.read_object_json(r)['dependencies'] for r in new)


def test_located_failure_remains_blocking_without_professional_claim(tmp_path,native,monkeypatch):
    path,store=adopted(tmp_path);full_request(path,store)
    class FailureSession(FixtureSession):
        def review(self,prompt,schema):
            observation=super().review(prompt,schema);value=json.loads(observation['raw_final_message'])
            packet=self.calls[-1]['packet'];ref=packet['business_review']['narrative_ref']
            row=next(r for r in value['reviews'] if r['kind']=='argument');row.update(status='fail',findings=[{
                'finding_id':'synthetic-topic-gap','kind':'content','impact':'must_fix','page_id':None,
                'element_refs':['topic:handoff'],'message':'Synthetic located finding; not live semantic reviewer performance.',
                'expected':'Meaning and capability mapping need substantive checking.','actual':'Synthetic incomplete interpretation.',
                'evidence':[ref],'resolution':'open','resolution_reason':''}])
            observation['raw_final_message']=json.dumps(value);return observation
    monkeypatch.setattr(native_review,'CodexReviewSession',FailureSession)
    result=native_review.run(path,subject='outline');assert result['preproduction']['status']=='blocked'
    assert result['preproduction']['blocking_findings'][0]['finding_id']=='synthetic-topic-gap'
    before=store.load_document()
    with pytest.raises(models.ModelError,match='current argument/progression'):
        content_production.open_phase_task(store,before,operation_id='blocked-by-topic',phase='page_copy')
    assert store.load_document()==before


def test_direct_producer_adds_one_packet_and_rejects_forged_projection(tmp_path):
    path,store=adopted(tmp_path);before=store.load_document()
    packet=outline_review.packet(store,before);packet['business_review']['finding_locations'].append('topic:invented')
    bad=store.put_json_object(packet)
    with pytest.raises(models.ModelError,match='do not forge locators'):
        service.open_host_task(store,kind='review',page_ids=[],review_stage='preproduction',review_subject='outline',
            review_units=[{'kind':'argument','page_ids':[],'reason':'missing'}],instruction='Synthetic direct review',extra_inputs=[bad])
    assert store.load_document()==before
    task=service.open_host_task(store,kind='review',page_ids=[],review_stage='preproduction',review_subject='outline',
        review_units=[{'kind':'argument','page_ids':[],'reason':'missing'}],instruction='Synthetic direct review')
    packets=[store.read_object_json(r) for r in task['inputs'] if r['path'].endswith('.json') and
             store.read_object_json(r).get('schema_version')=='content_review_packet.v1']
    assert len(packets)==1 and business.CAPABILITY in task['required_capabilities']


def test_business_locator_projection_stays_inside_reviewed_page_scope(tmp_path):
    from test_business_framing import v2
    path,store=_deck(tmp_path);doc=store.load_document();narrative=store.read_object_json(doc['narrative'])
    fields=v2(doc['project_id']);narrative.update(schema_version='narrative.v2',business_strategy=fields['business_strategy'],
        business_frame=fields['business_frame'],method_applications=[])
    models.validate_narrative_semantics(narrative);doc['narrative']=store.put_json_object(narrative)
    plan=store.read_object_json(doc['content_plan']);plan['narrative_ref']=doc['narrative']
    for entry in doc['pages']:
        page=store.read_object_json(entry['page']);page['content_mapping']['narrative_ref']=doc['narrative'];entry['page']=store.put_json_object(page)
    for link in plan['page_links']:link['page_ref']=next(e['page'] for e in doc['pages'] if e['page_id']==link['page_id'])
    doc['content_plan']=store.put_json_object(plan);commit(store,doc,'synthetic-scope-fixture')
    packet=content_review.build_review_packet(store,store.load_document(),page_ids=['p1'])
    locations=packet['business_review']['finding_locations']
    assert 'atom:p1:title' in locations and not any(location.startswith(('atom:p2:','segment:p2:')) for location in locations)
    assert [p['page_id'] for p in packet['manuscript']['pages']]==['p1']


def test_partial_outline_adoption_cannot_skip_review_by_omitting_plan(tmp_path):
    path,store,refs=proposals(tmp_path);_,decision=adoption_request(path,store,refs)
    content_production.adopt_proposal(path,input={'proposal_ref':refs[0],'decision_ref':decision,'write_scope':SCOPE},
        base_revision=store.current_revision_id(),operation_id='only-narrative-adopted')
    full_request(path,store);before=store.load_document()
    assert content_production.content_phase_status(store,before)['action']=='blocked'
    with pytest.raises(models.ModelError,match='matching planned Plan'):
        content_production.open_phase_task(store,before,operation_id='unpaired-copy',phase='page_copy')
    assert store.load_document()==before


def test_full_copy_speech_and_four_unit_review_keep_one_adopted_argument(tmp_path,native):
    path,store=adopted(tmp_path);full_request(path,store);native_review.run(path,subject='outline')
    doc=store.load_document();nref=doc['narrative'];plan=copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])
    plan['speech_policy']={'mode':'verbatim','source':'provided','output':'separate_script'}
    task=content_production.open_phase_task(store,doc,operation_id='full-copy',phase='page_copy')
    def submit(task,variant,payload):
        service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-d04-'+variant,supported_protocols=['compose.v2'],capabilities=task['required_capabilities'])
        return service.accept_result(path,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],
            result_payload={'schema_version':'compose_result.v2','kind':'compose','variant':variant,'task_id':task['task_id'],
                'operation_id':task['operation_id'],'produced_against':task['produced_against'],
                'eligibility_digest':task['collaboration_binding']['eligibility_digest'],'payload':payload,'usage_events':[]})
    submit(task,'page_copy',{'pages':[_page(store,doc,'p1',notes='')],'page_order':['p1'],'plan_input':plan})
    doc=store.load_document();assert not doc['collaboration']['request']['closed']
    task=content_production.next_phase_task(store,doc);assert task['stage_request']['speech_kind']=='verbatim'
    page_ref=store.load_document()['pages'][0]['page'];notes='先核对已经确认的条件，再按原规则交接。'
    submit(task,'speech',{'updates':[{'page_id':'p1','page_ref':page_ref,'speaker_notes':notes,'speech_segments':[
        {'segment_id':'s1','start_codepoint':0,'end_codepoint':len(notes),'kind':'verbatim','narrative_node_ids':['n1'],'estimated_seconds':12}]}]})
    doc=store.load_document();assert doc['narrative']==nref and doc['collaboration']['request']['closed']
    collaboration.start_request(path,input={'intent':'review_only','content_intent':None,'scope':{**SCOPE,'page_ids':['p1'],'layers':['review']},
        'instruction_evidence':{'kind':'host_attested_instruction','text':'Synthetic explicit review of the actual full manuscript and notes.',
                               'source_locator':'test:d04-complete-review'}},base_revision=store.current_revision_id(),operation_id='full-review-request')
    result=native_review.run(path);assert result['preproduction']['status']=='pass'
    packet=native.calls[-1]['packet'];assert set(packet['required_units'])=={'argument','page_copy','progression','speech'}
    assert packet['narrative']==store.read_object_json(nref) and packet['manuscript']['pages'][0]['speaker_notes']==notes
    doc=store.load_document();assert not any(doc['outputs'].values()) and all(e['blueprint'] is None for e in doc['pages'])
