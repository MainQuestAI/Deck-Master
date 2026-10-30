"""D05 synthetic mechanism tests; no model calls or business acceptance claims."""
import copy
import uuid

import pytest

from deck_master import business_recompile as business, collaboration, content_impact, content_production, models, native_review, service, tasks
from test_business_content_review import adopted, full_request
from test_content_preproduction_review import _page
from test_native_review import FixtureSession


def send(path, task, payload, variant='input_revision'):
    return service.accept_result(path, task_id=task['task_id'], operation_id=task['operation_id'],
        produced_against=task['produced_against'], result_payload={'schema_version':'compose_result.v2',
            'kind':'compose','variant':variant,'task_id':task['task_id'],'operation_id':task['operation_id'],
            'produced_against':task['produced_against'],'eligibility_digest':task['collaboration_binding']['eligibility_digest'],
            'payload':payload,'usage_events':[]})


def claim(path, task):
    return service.task_start(path, task_id=task['task_id'], execution_ref='synthetic-d05-writer',
        supported_protocols=['compose.v2'], capabilities=task['required_capabilities'])


@pytest.fixture
def deck(tmp_path, monkeypatch):
    FixtureSession.calls=[];FixtureSession.status='pass';FixtureSession.corrupt=False;FixtureSession.before_finish=None
    monkeypatch.setattr(native_review,'CodexReviewSession',FixtureSession)
    path,store=adopted(tmp_path);full_request(path,store);native_review.run(path,subject='outline')
    doc=store.load_document();task=content_production.open_phase_task(store,doc,operation_id='d05-initial-copy',phase='page_copy')
    claim(path,task);plan=store.read_object_json(doc['content_plan'])['input'];page=_page(store,doc,'p1',notes='')
    send(path,task,{'pages':[page],'page_order':['p1'],'plan_input':plan},'page_copy')
    doc=store.load_document();task=content_production.open_phase_task(store,doc,operation_id='d05-initial-speech',phase='speech')
    claim(path,task);notes='先记录未知，再说明下一责任人的实际动作。';entry=doc['pages'][0]
    send(path,task,{'updates':[{'page_id':'p1','page_ref':entry['page'],'speaker_notes':notes,
        'speech_segments':[{'segment_id':'initial','start_codepoint':0,'end_codepoint':len(notes),
            'narrative_node_ids':['n1'],'kind':'verbatim','estimated_seconds':20}]}]},'speech')
    assert store.load_document()['collaboration']['request']['closed']
    return path,store


def followup(path,store):
    doc=store.load_document();old=doc['collaboration']['request'];scope={**old['scope'],
        'layers':['narrative','plan','page_copy','speech','review'],'allow_page_order_change':True}
    return collaboration.start_request(path,input={'intent':'content_only','content_intent':'content_full',
        'replace_request_id':old['request_id'],'scope':scope,'instruction_evidence':{'kind':'host_attested_instruction',
            'text':'Synthetic explicit follow-up: change first proposal into bid response, preserve actual facts; no visuals or model calls.',
            'source_locator':'test:d05-followup'}},base_revision=doc['revision_id'],operation_id=str(uuid.uuid4()))


def change(path,store,patch=None):
    out=service.inputs_update(path,patch={'task_patch':patch or {'scenario':'competitive_bid'},
        'reason':'Synthetic explicit strategy change'},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    task=next(store.read_object_json(r) for r in reversed(store.load_document()['tasks'])
        if store.read_object_json(r).get('intent')=='input_revision')
    return out,task


def payload_for(store,task):
    doc=store.load_document();n=copy.deepcopy(store.read_object_json(doc['narrative']))
    n['input_basis']=task['collaboration_binding']['eligibility_basis'];n['business_strategy'].update(
        scenario=doc['task']['scenario'],author_goal='Respond to procurement requirements and prove delivery fit',
        rationale='The bid tests fit, handoff and evidence; it does not repeat category education')
    n['nodes'][0]['statement']='按采购要求说明适配、交付责任与验证依据，不预设验收通过。'
    nr=store.put_json_object(n);plan=copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])
    plan['page_roles'][0].update(role='说明需求适配、交付及验证',intended_takeaway='适配须由交付及验证支撑')
    pr=store.put_json_object(plan);page=copy.deepcopy(store.read_object_json(doc['pages'][0]['page']))
    page['customer_visible']['body_blocks'][0]['text']='先对应采购需求，再说明交付责任和验证依据；缺失字段仍记录未知，不虚构节时结果。'
    page['content_mapping']['narrative_ref']=nr;ref=store.put_json_object(page)
    speech=copy.deepcopy(store.read_object_json(doc['pages'][0]['page']));speech['speaker_notes']='按采购要求核对方案适配、交付责任与验证证据，不推定已验收。'
    speech['content_mapping']['speech_segments']=[{'segment_id':'revised','start_codepoint':0,'end_codepoint':len(speech['speaker_notes']),
        'narrative_node_ids':['n1'],'kind':'verbatim','estimated_seconds':30}]
    sr=store.put_json_object(speech)
    return {'changed_layers':['narrative','plan','page_copy','speech'],'proposals':[{'layer':'narrative','ref':nr},
        {'layer':'plan','ref':pr},{'layer':'page_copy','ref':ref},{'layer':'speech','ref':sr}],
        'diff':{'input_digest':task['input_digest'],'summary':'Synthetic actual strategy-dependent content selection.',
            'strategy_summary':'Switch from teaching the existing work to requirement, delivery responsibility and verification evidence.',
            'changed_page_ids':['p1'],'page_order':['p1'],'page_assessments':[{'page_id':'p1','state':'affected',
                'reason_codes':['procurement_response_required'],'reason':'The former explanatory copy does not answer the procurement criteria.',
                'evidence_refs':[doc['pages'][0]['page'],nr,pr]}]}}


@pytest.mark.parametrize('closed', [True,False])
def test_real_followup_input_change_and_atomic_recompile(deck,closed):
    path,store=deck;old=store.load_document();old_request=old['collaboration']['request'];raw=store.read_object_bytes(old['pages'][0]['page'])
    if closed:
        with pytest.raises(Exception,match='closed'):change(path,store)
    followup(path,store)
    if not closed:assert not store.load_document()['collaboration']['request']['closed']
    out,task=change(path,store);impact=out['content_impact']
    assert impact['schema_version']=='content_impact.v2' and 'unaffected_pages' not in impact
    assert impact['page_assessments'][0]['state']=='needs_reassessment' and impact['changed_sources']=={'added':[],'removed':[],'changed':[]}
    assert business.frozen_impact(store,task)==impact and business.CAPABILITY in task['required_capabilities']
    assert models.writer_at_least(store.load_document(),business.CAPABILITY)
    claim(path,task);result=send(path,task,payload_for(store,task));doc=store.load_document()
    assert result['adopted'] and models.input_alignment(doc)=='current'
    assert '交付责任和验证依据' in store.read_object_json(doc['pages'][0]['page'])['customer_visible']['body_blocks'][0]['text']
    assert store.read_object_bytes(old['pages'][0]['page'])==raw and store.load_document(old['revision_id'])['collaboration']['request']==old_request
    assert store.read_object_json(doc['content_plan'])['narrative_ref']==doc['narrative']
    assert result['page_assessments'][0]['state']=='affected' and doc['sources']==old['sources']
    assert not doc['outputs'].get('pptx') and all(store.read_object_json(r)['kind']!='blueprint' for r in doc['tasks'])


@pytest.mark.parametrize('defect', ['missing-assessments','unverified','title-only','unchanged-role','no-paired-plan','missing-reason'])
def test_reconciliation_cannot_claim_unreviewed_or_title_only_strategy(deck,defect):
    path,store=deck;followup(path,store);_,task=change(path,store);claim(path,task);payload=payload_for(store,task)
    if defect=='missing-assessments':payload['diff'].pop('page_assessments')
    elif defect=='unverified':payload['diff']['page_assessments'][0]['state']='unverified'
    elif defect=='missing-reason':payload['diff']['page_assessments'][0]['reason']=''
    elif defect=='no-paired-plan':payload['changed_layers'].remove('plan');payload['proposals']=[p for p in payload['proposals'] if p['layer']!='plan']
    elif defect=='title-only':
        page=copy.deepcopy(store.read_object_json(store.load_document()['pages'][0]['page']));page['customer_visible']['title']='竞标响应'
        payload['proposals'][2]['ref']=store.put_json_object(page)
    elif defect=='unchanged-role':payload['proposals'][1]['ref']=store.put_json_object(store.read_object_json(store.load_document()['content_plan'])['input'])
    before=store.load_document()
    with pytest.raises((models.ModelError,ValueError)):send(path,task,payload)
    assert store.load_document()==before


def test_followup_failure_does_not_reopen_old_request_and_is_recoverable(deck):
    path,store=deck;old=store.load_document();followup(path,store);current=store.load_document()
    with pytest.raises(Exception):service.inputs_update(path,patch={'task_patch':{'bad_field':True}},base_revision=current['revision_id'],operation_id=str(uuid.uuid4()))
    assert store.load_document()==current and store.load_document(old['revision_id'])['collaboration']['request']['closed']
    _,task=change(path,store);claim(path,task);send(path,task,payload_for(store,task))


def test_second_change_supersedes_old_result_and_keeps_all_pending_facts(deck):
    path,store=deck;followup(path,store);_,first=change(path,store);claim(path,first);old_payload=payload_for(store,first)
    _,second=change(path,store,{'audience':'Procurement and technical assessors'})
    assert {'scenario','audience'}<=set(business.frozen_impact(store,second)['changed_task_fields'])
    before=store.load_document()
    with pytest.raises(Exception):send(path,first,old_payload)
    settled=store.load_document()
    assert all(settled[k]==before[k] for k in ('task','sources','pages','narrative','content_plan','content_basis','outputs'))
    assert not tasks.task_inputs_current(store,settled,first)


def test_unreadable_page_is_unverified_and_v1_remains_unchanged(deck):
    path,store=deck;before=store.load_document();after=copy.deepcopy(before);after['task']['scenario']='competitive_bid'
    ref=after['pages'][0]['page'];file=store.project_root/ref['path'];file.write_text('broken-object')
    impact=content_impact.analyze_input_change(store,before,after)
    assert impact['page_assessments'][0]['state']=='unverified' and not impact['affected_pages']


@pytest.mark.parametrize('missing', [None,'old-page','current-strategy','reason'])
def test_reviewed_reuse_preserves_exact_old_page_ref_and_needs_proof(deck,missing):
    path,store=deck;followup(path,store);_,task=change(path,store,{'page_limit':8});claim(path,task)
    before=store.load_document();plan=store.read_object_json(before['content_plan'])['input']
    row={'page_id':'p1','state':'reusable_after_review','reason_codes':['expanded_budget_same_role'],
        'reason':'Only the upper page budget increased; the complete existing one-page role, facts and script remain suitable.',
        'evidence_refs':[before['pages'][0]['page'],before['narrative']]}
    if missing=='old-page':row['evidence_refs'].pop(0)
    if missing=='current-strategy':row['evidence_refs'].pop()
    if missing=='reason':row['reason']=''
    payload={'changed_layers':['plan'],'proposals':[{'layer':'plan','ref':store.put_json_object(plan)}],
        'diff':{'input_digest':task['input_digest'],'summary':'Expanded budget; specific old page reviewed against unchanged direction.',
            'changed_page_ids':[],'page_assessments':[row]}}
    if missing:
        with pytest.raises(models.ModelError):send(path,task,payload)
        assert store.load_document()==before
    else:
        result=send(path,task,payload)
        assert result['adopted'] and store.load_document()['pages']==before['pages']
        assert result['page_assessments'][0]['state']=='reusable_after_review'


def test_copy_cannot_leave_an_old_script_unreconciled(deck):
    path,store=deck;followup(path,store);_,task=change(path,store);claim(path,task);payload=payload_for(store,task)
    payload['changed_layers'].remove('speech');payload['proposals']=[p for p in payload['proposals'] if p['layer']!='speech']
    with pytest.raises(models.ModelError,match='speech reconciliation'):send(path,task,payload)


def test_direct_recovery_builder_freezes_same_pending_impact_and_refuses_old_host(deck):
    path,store=deck;followup(path,store);_,task=change(path,store)
    direct=content_production.build_phase_task(store,store.load_document(),intent='input_revision',operation_id='direct-probe')
    assert business.frozen_impact(store,direct)==business.frozen_impact(store,task)
    with pytest.raises(Exception):
        service.task_start(path,task_id=task['task_id'],execution_ref='old-host',supported_protocols=['compose.v2'],
            capabilities=[c for c in task['required_capabilities'] if c!=business.CAPABILITY])


def test_cancelled_result_only_settles_facts_and_cannot_replace_copy(deck):
    path,store=deck;followup(path,store);_,task=change(path,store);claim(path,task);payload=payload_for(store,task)
    service.task_cancel(path,task_id=task['task_id'],reason='Synthetic caller cancellation')
    before=store.load_document()
    with pytest.raises(Exception):send(path,task,payload)
    after=store.load_document()
    assert all(after[k]==before[k] for k in ('task','pages','narrative','content_plan','content_basis','outputs'))


@pytest.mark.browser
def test_real_browser_displays_versioned_reassessment_and_historical_unverified(deck):
    from playwright.sync_api import expect, sync_playwright
    from deck_master.web import WorkbenchServer
    path,store=deck;followup(path,store);server=WorkbenchServer(path)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':800});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='内容与页序',exact=True).click()
            page.get_by_role('button',name='材料与来源',exact=True).click()
            page.get_by_role('button',name='材料与要求',exact=True).click()
            page.get_by_role('button',name='修改任务要求',exact=True).click()
            page.get_by_label('交流场景',exact=True).fill('competitive_bid')
            page.get_by_label('本次输入变化说明',exact=True).fill('Synthetic business scenario change; no model calls or image work.')
            page.get_by_role('button',name='预览材料与任务变化',exact=True).click()
            page.get_by_role('button',name='确认输入并交接判断',exact=True).click()
            expect(page.get_by_label('内容影响判断',exact=True)).to_contain_text('需要重新判断')
            assert store.load_document()['task']['scenario']=='competitive_bid'
            # Exercise the same renderer for historical projection; a source miss is not reviewed reuse.
            text=page.evaluate("""async () => {const {inputImpactView}=await import('/v2/content-edit.js');
              return inputImpactView({schema_version:'content_impact.v1',affected_pages:[],unaffected_pages:['p1']},[{page_id:'p1',title:'历史页'}]).textContent;}""")
            assert '尚未核验' in text and '复核后可复用' not in text
            assert not errors
            browser.close()
    finally:server.stop()
