"""Synthetic source cases; separate trace uses a new own original-wheel install.

No actual native agent/model or formal run is called. The original protected
provider and SDK are real; observations/review judgments here are synthetic.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

TOOL=Path(__file__).resolve().parents[2]/'tools/rc3_campaign/supplied_p5_fidelity.py'
spec=importlib.util.spec_from_file_location('s08_cases',TOOL)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def page(pid):
    return {'schema_version':'deck_page_package.v2','page_id':pid,
        'customer_visible':{'title':'Neutral '+pid,'body_blocks':[{'id':'b1','type':'paragraph','text':'Keep the unknown explicit.'}]},
        'speaker_notes':'Neutral supplied complete notes for '+pid,
        'visual_spec':{'intent':'Neutral supplied layout','reference_mode':'new_design'}}


def installation(base,c):
    import deck_master
    from deck_master import capabilities
    module=Path(deck_master.__file__).resolve();identity=capabilities.installation_identity()
    observed=identity.get('install') or {}
    manifest=c.save(base/'engineering-installation-manifest.json',{
        'status':'ENGINEERING_ONLY_NOT_ADMITTED','module_path':str(module),
        **{k:observed.get(k) for k in ('source_sha','source_tree','wheel_sha256')},
        'actual_identity':identity,'source_checkout':module.parents[1].name=='src'})
    return {'python':sys.executable,'module_file':str(module),'manifest':manifest,
        **{k:observed.get(k) for k in ('source_sha','source_tree','wheel_sha256')},
        'package_files':[{'relative_path':str(f.relative_to(module.parent)),'sha256':c.digest(f.read_bytes())}
            for f in sorted(module.parent.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc']}


def fixture(base,tool=p,sdk_cap=80):
    base=Path(base).resolve();base.mkdir(parents=True,exist_ok=True)
    s,c=tool.helpers();instruction=c.write_once(base/'instruction.txt',b'SYNTHETIC: review supplied P5 only, no images.')
    source=c.save(base/'p5.json',page('p5'));grammar=c.save(base/'grammar.json',{'SYNTHETIC_TECHNICAL_ONLY':True})
    exposure=c.save(base/'exposure.json',{'status':'FROZEN','excluded_identities':['/root/engineering_preparer','/root/engineering_author'],
        'opaque_private_index_ref':{'path':str(base/'private'/'never-open-index.json'),'sha256':'0'*64,'bytes':1}})
    row={'profile':'q3q4','case':'Q4','checkpoint':'Q4A','checkpoint_ref':None,'matrix_slot':'08',
        'whole_run_id':'synthetic-supplied-p5','repetition':1,'arm':'B','scope_slot':'synthetic-p5-only',
        'project':str(base/'project'),'project_mode':'new','page_ids':['p5'],'instruction':instruction,
        'materials':[source],'technical_supplements':[],
        'limits':{'writer':48,'review':32,'sdk':sdk_cap,'render':64},
        'native_limits':{'feedback':1,'initial_writer':5,'production':40,'production_review':30,'repair_writer':3,'verification':1}}
    config={'format':s.FORMAT,'status':s.ENGINEERING,'recorder_sha256':tool.SCOPED_SHA,
        'ledger_root':str(base/'campaign'),'common':c.reference(s.SOURCE),'protocol':grammar,'policy_epoch':grammar,
        'admission_review':grammar,'exposure_registry':exposure,'grammar':grammar,
        'installations':{'B':installation(base,c)},'scopes':{'neutral':row}}
    registration=c.save(base/'registration.json',config);s.freeze(registration['path'],base/'campaign')
    state=s.init(base/'campaign',base/'run','neutral');run=Path(state['root'])
    trigger=c.save(base/'instruction-observation.json',{'assurance':'host_attested','observer_id':'/root',
        'scope_slot':row['scope_slot'],'actual_trigger':True,'instruction_sha256':instruction['sha256'],
        'source_observations':[source],'SYNTHETIC_NOT_NATIVE':True})
    s.instruction_event(run,row['scope_slot'],trigger['path'])
    scope={'subject':'pages','page_ids':['p5'],'page_manifest_ref':None,'external_artifact_ref':None,
        'layers':['page_copy','speech','design','blueprint','svg','review','output'],
        'allow_page_membership_change':False,'allow_page_order_change':False,'purpose':'working'}
    s.operate(run,'service.create',{'brief':'Synthetic supplied manuscript; selected P5 only.','sources':[source['path']],
        'draft':{'pages':[page('p1'),page('p5'),page('p9')]},'request_input':{
            'intent':'design_trial','content_intent':None,'scope':scope,
            'instruction_evidence':{'kind':'host_attested_instruction','text':Path(instruction['path']).read_text(),'source_locator':'SYNTHETIC_ONLY'}}})
    bootstrap=c.save(base/'bootstrap.json',{'observation_kind':c.OBSERVER_KIND,'assurance':'host_attested',
        'observed_at_utc':c.now(),'tool':'collaboration.list_agents','observed_running_agents':['/root'],
        'SYNTHETIC_ONLY_NOT_ACTUAL_CHANNEL':True})
    c.save(base/'identity.json',{'isolated':sys.flags.isolated,'dont_write_bytecode':sys.dont_write_bytecode,
        'python':sys.executable,'SYNTHETIC_ONLY':True})
    return {'base':base,'run':run,'state':state,'config':config,'s':s,'c':c,'bootstrap':bootstrap,'tool':tool}


def admit(f):
    tool=f['tool'];*_,scope=tool.context(f['run'],True)
    return f['c'].save(f['base']/'admission.json',{'format':tool.FORMAT,'action':tool.ACTION,
        'status':'ENGINEERING_ONLY_NOT_ADMITTED','observer_id':'/engineering/rc3-s08','assurance':'synthetic_engineering',
        'evidence_kind':'SYNTHETIC_ENGINEERING_ONLY','observed_at_utc':f['c'].now(),'scope':scope,
        'independent_implementation_review_passed':True,'actual_supplied_checkpoint_observed':True})


def prepare(f):
    f['admission']=admit(f)
    return f['tool'].prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)


def step(f,action,**kwargs):
    return f['tool'].advance(action,f['run'],f['admission']['path'],f['admission']['sha256'],engineering=True,**kwargs)


def audit_observation(f,bound,observer='/root/engineering_auditor'):
    return f['c'].save(f['base']/('audit-'+str(len(list(f['base'].glob('audit-*.json'))))+'.json'),{
        'SYNTHETIC_HOST_MECHANICAL_AUDIT_NOT_MODEL':True,'assurance':'host_attested','observed_at_utc':f['c'].now(),
        'observer_id':observer,'status':'PASS','project':f['state']['project'],'task_id':f['dispatch']['task_id'],
        'required_read_closure_checked':True,'raw_workorder_preserved':True,
        **{k:bound[k] for k in ('original_raw_ref','author_view_ref','read_closure_manifest_ref')}})


def launch(f,executor='/root/engineering_reviewer'):
    f['dispatch']=prepare(f);c=f['c'];d=f['dispatch']
    a=audit_observation(f,d);step(f,'audit',observation=a['path'])
    invocation=c.save(f['base']/'invocation.json',{'SYNTHETIC_NOT_ACTUAL_NATIVE_CALL':True,
        'observation_kind':c.OBSERVER_KIND,'assurance':'host_attested','observed_at_utc':c.now(),
        'task_id':d['task_id'],'project_id':d['project_id'],'spawn':{'tool':'collaboration.spawn_agent',
        'canonical_task_name':executor,'returned_task_name':executor,'fork_turns':'none','inherited_identities':[]}})
    f['invocation']=step(f,'begin',observation=invocation['path'])
    f['bound']=step(f,'claim');a=audit_observation(f,f['bound']);step(f,'release',observation=a['path'])
    return f


def review_envelope(f):
    c=f['c'];store=c.store_for(f['state']);doc=store.load_document()
    entry=next(e for e in doc['pages'] if e['page_id']=='p5')
    subjects=[doc[k] for k in ('narrative','content_plan') if doc.get(k)]+[entry['page']]
    deps=[{'kind':'content','identity':k,'sha256':doc[k]['sha256']} for k in ('narrative','content_plan') if doc.get(k)]
    deps+=[{'kind':'content','identity':'page:p5','sha256':entry['page']['sha256']}]
    deps+=[{'kind':'source','identity':s['source_id'],'sha256':s['extract']['sha256']} for s in doc['sources']]
    evidence=store.put_json_object({'SYNTHETIC_NOT_NATIVE_REVIEW':'P5 source only; no N/Plan/other Page read'})
    return {'kind':'review','pages':[],'page_order':[],'artifact_specs':[],'usage_events':[],
        'notes':'SYNTHETIC fidelity, not actual native or professional review','reviews':[
        {'schema_version':'deck_review.v2','review_id':'synthetic-'+kind,'kind':kind,'review_stage':'preproduction',
         'status':'pass','subjects':deepcopy(subjects),'dependencies':deepcopy(deps),'findings':[],
         'observations':['SYNTHETIC check only P5 against supplied source, progression only within P5.'],
         'created_at':c.now(),'replaces':None,'reviewer':{'type':'independent_host','id':f['invocation']['executor'],
          'execution_ref':f['invocation']['executor'],'independence_confirmed':True,'identity_receipt':None,
          'assurance':'host_attested','evidence_ref':evidence}} for kind in ('page_copy','progression')]}


def completion_files(f,envelope=None,**overrides):
    c=f['c'];envelope=review_envelope(f) if envelope is None else envelope
    raw=c.save(f['base']/'synthetic-original-review.json',envelope)
    _,target=c.execution(c.Journal(f['run']),p.STAGE,f['invocation']['ordinal'])
    method=c.reference(target/'method-read-record.json');d=f['dispatch'];bound=f['bound']
    obs=c.save(f['base']/'synthetic-completion.json',{'SYNTHETIC_NOT_ACTUAL_FINAL_OR_COMPLETED':True,
        'observation_kind':c.OBSERVER_KIND,'assurance':'host_attested','observed_at_utc':c.now(),
        'project_id':d['project_id'],'task_id':d['task_id'],'model_output_bytes_sha256':raw['sha256'],
        'method_release':d['method_release'],'all_method_bytes_read':True,'method_read_record_sha256':method['sha256'],
        'author_view_sha256':bound['author_view_ref']['sha256'],'read_closure_manifest_sha256':bound['read_closure_manifest_ref']['sha256'],
        'all_required_view_files_read':True,'raw_workorder_read_by_author':False,
        'full_narrative_plan_or_other_pages_read':False,'review_scope_page_ids':['p5'],
        'completion':{'sender':f['invocation']['executor'],'message_type':'FINAL_ANSWER',
         'status_observation_tool':'collaboration.list_agents','observed_status':'completed',
         'observed_completed_agents':[f['invocation']['executor']],'raw_final_message':Path(raw['path']).read_text()},**overrides})
    return raw,obs


def complete(f,envelope=None,**overrides):
    raw,obs=completion_files(f,envelope,**overrides)
    return step(f,'observe',result=raw['path'],result_sha256=raw['sha256'],observation=obs['path'],observation_sha256=obs['sha256'])


@pytest.fixture
def setup(tmp_path):return fixture(tmp_path)


def test_prepare_has_honest_provided_checkpoint_and_bounded_real_sdk_packet(setup):
    f=setup;dispatch=prepare(f);c=f['c'];store=c.store_for(f['state']);doc=store.load_document()
    checkpoint=c.read(f['run']/'supplied-manuscript-input.json')
    assert checkpoint['format']=='provided_manuscript_input.v1' and checkpoint['native_writer_execution'] is False
    assert checkpoint['scope']['imported_author_execution_refs']==[]
    assert not (f['run']/'snapshots/original_complete.json').exists()
    assert not (f['run']/'snapshots/first_sdk_complete.json').exists()
    view=c.read(dispatch['author_view_ref']['path']);raw=c.read(dispatch['original_raw_ref']['path'])
    assert view['raw_response_read_permission'] is False and view['imported_author_execution_refs']==[]
    assert view['selected_page']==next(e['page'] for e in doc['pages'] if e['page_id']=='p5')
    assert not {'narrative','plan','work_order','project_context'} & view.keys()
    assert raw['work_order']['scope_pages']==['p5']
    assert all('content' not in row for row in view['methods'])


def test_actual_original_protected_receipt_and_P5_gate_never_whole_deck(setup):
    f=launch(setup);c=f['c'];store=c.store_for(f['state']);before=p.protected(store.load_document())
    complete(f);out=step(f,'accept',bootstrap=f['bootstrap']['path'])
    assert out['outcome']['status']=='accepted'
    from deck_master import content_review
    doc=store.load_document()
    assert content_review.preproduction_status(store,doc,page_ids=['p5'])['status']=='pass'
    assert content_review.preproduction_status(store,doc)['status']=='missing'
    assert p.protected(doc)==before
    assert out['binding']['author_execution_refs']==[] and out['binding']['write_scope']=={'layers':['review'],'page_ids':['p5']}
    step(f,'feedback')
    totals,scope,pending=f['s'].Resources(f['state']).totals()
    assert not pending and totals['review']==scope['review']==1 and totals['writer']==0
    assert scope['sdk']==6  # create,dispatch,preflight methods,claim,postclaim methods,accept
    assert len([e for e in c.Journal(f['run']).events() if e['kind']=='feedback_delivered'])==1
    with pytest.raises(Exception):step(f,'feedback')


@pytest.mark.parametrize('field,value',[
    ('revision','different-revision'),('checkpoint','whole-file'),('page_ids',['p1','p5']),
    ('imported_author_execution_refs',['invented-writer']),('original_role_caps',{'feedback':2}),
    ('prior_errors',[{'not':'original'}]),('selected_page',{'not':'actual Page'}),('source',{'not':'supplied'}),
])
def test_wrong_exact_admission_scope_refuses_before_SDK(setup,field,value):
    f=setup;f['admission']=admit(f);c=f['c'];a=c.read(f['admission']['path']);a['scope'][field]=value
    f['admission']=c.save(f['base']/'wrong-scope.json',a);before=f['s'].Resources(f['state']).totals()
    with pytest.raises(p.Error):p.prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)
    assert f['s'].Resources(f['state']).totals()==before
    assert not (f['run']/'supplied-manuscript-input.json').exists()


@pytest.mark.parametrize('field,value',[
    ('observer_id','/root'),('assurance','host_attested'),('status','ADMITTED'),
    ('independent_implementation_review_passed',False),('actual_supplied_checkpoint_observed',False),
    ('action','arbitrary-review'),('message','override'),
])
def test_wrong_control_or_override_refuses(setup,field,value):
    f=setup;f['admission']=admit(f);a=f['c'].read(f['admission']['path']);a[field]=value
    ref=f['c'].save(f['base']/'wrong-control.json',a)
    with pytest.raises(p.Error):p.prepare(f['run'],ref['path'],ref['sha256'],f['bootstrap']['path'],True)
    assert not (f['run']/'supplied-manuscript-input.json').exists()


def test_nested_private_index_is_never_read_or_hashed(setup,monkeypatch):
    f=setup;actual=Path.read_bytes
    def spy(path):
        assert 'never-open-index' not in str(path)
        return actual(path)
    monkeypatch.setattr(Path,'read_bytes',spy)
    prepare(f)


def test_sdk_dispatch_failure_cost_is_once_unknown_and_no_retry(setup,monkeypatch):
    f=setup;f['admission']=admit(f)
    from deck_master import content_review
    def interrupted(*args,**kwargs):raise OSError('SYNTHETIC dispatch transport interruption')
    monkeypatch.setattr(content_review,'dispatch_preproduction_review',interrupted)
    with pytest.raises(OSError):p.prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)
    journal=f['c'].Journal(f['run']);before=f['s'].Resources(f['state']).totals()
    assert len(journal.unfinished())==1 and before[1]['sdk']==2 and before[1]['review']==0
    with pytest.raises(p.Error):p.prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)
    assert f['s'].Resources(f['state']).totals()==before
    assert not (f['run']/'stages'/p.STAGE/'dispatch.json').exists()


def test_actual_accept_commit_then_lost_ack_remains_unknown_without_retry_or_feedback(setup,monkeypatch):
    f=launch(setup);complete(f)
    from deck_master import service
    actual=service.accept_result
    def lost(*args,**kwargs):
        result=actual(*args,**kwargs)
        f['c'].save(f['base']/'actual-SDK-commit-before-lost-ack.json',result)
        raise OSError('SYNTHETIC acknowledgment lost after real SDK acceptance')
    monkeypatch.setattr(service,'accept_result',lost)
    with pytest.raises(OSError):step(f,'accept',bootstrap=f['bootstrap']['path'])
    assert f['c'].store_for(f['state']).load_document()['reviews']
    assert len(f['c'].Journal(f['run']).unfinished())==1
    before=f['s'].Resources(f['state']).totals();assert before[1]['sdk']==6 and before[1]['review']==1
    with pytest.raises(p.Error):step(f,'accept',bootstrap=f['bootstrap']['path'])
    with pytest.raises(p.Error):step(f,'feedback')
    assert f['s'].Resources(f['state']).totals()==before


def test_actual_dispatch_revision_race_is_retained_never_relabelled_success(setup,monkeypatch):
    f=setup;f['admission']=admit(f)
    from deck_master import content_review,service
    actual=content_review.dispatch_preproduction_review
    def concurrent(project,**kwargs):
        service.open_host_task(f['c'].store_for(f['state']),kind='review',page_ids=['p5'],review_stage='preproduction',instruction='SYNTHETIC competing host dispatch')
        return actual(project,**kwargs)
    monkeypatch.setattr(content_review,'dispatch_preproduction_review',concurrent)
    with pytest.raises(p.Error,match='raced initial revision'):
        p.prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)
    events=f['c'].Journal(f['run']).events()
    assert any(e['kind']=='review_dispatch' and e['data']['actual_result']['status']=='review_dispatched' for e in events)
    assert not any(e['kind']=='stage_prepared' for e in events)
    assert not (f['run']/'stages'/p.STAGE/'dispatch.json').exists()


@pytest.mark.parametrize('observer',['/root/engineering_preparer','/root/engineering_author'])
def test_public_original_exclusion_policy_is_enforced_before_launch(setup,observer):
    f=setup;f['dispatch']=prepare(f);a=audit_observation(f,f['dispatch'],observer)
    with pytest.raises(p.Error):step(f,'audit',observation=a['path'])
    assert f['s'].Resources(f['state']).totals()[1]['review']==0


def test_same_reviewer_cannot_audit_postclaim_and_both_audits_are_required(setup):
    f=setup;f['dispatch']=prepare(f);d=f['dispatch'];c=f['c']
    invocation=c.save(f['base']/'premature-invocation.json',{'not':'actual'})
    with pytest.raises(p.Error):step(f,'begin',observation=invocation['path'])
    assert f['s'].Resources(f['state']).totals()[1]['review']==0
    # Complete a separate fixture's actual two audit stages through launch.
    other=fixture(f['base']/'other');launch(other)
    a=audit_observation(other,other['bound'],other['invocation']['executor'])
    with pytest.raises(p.Error):step(other,'release',observation=a['path'])


def test_replay_prepare_begin_and_claim_cannot_renew_cost(setup):
    f=launch(setup);before=f['s'].Resources(f['state']).totals()
    with pytest.raises(p.Error):p.prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)
    with pytest.raises(p.Error):step(f,'begin',observation=str(f['base']/'invocation.json'))
    with pytest.raises(p.Error):step(f,'claim')
    assert f['s'].Resources(f['state']).totals()==before and before[1]['review']==1 and before[1]['writer']==0


@pytest.mark.parametrize('field,value',[
    ('raw_workorder_read_by_author',True),('full_narrative_plan_or_other_pages_read',True),
    ('all_required_view_files_read',False),('review_scope_page_ids',['p1','p5']),
    ('author_view_sha256','0'*64),
])
def test_actual_bounded_read_binding_cannot_be_upgraded_to_whole_read(setup,field,value):
    f=launch(setup)
    with pytest.raises(p.Error):complete(f,**{field:value})
    target=f['run']/'stages'/p.STAGE/'executions'/f"{f['invocation']['ordinal']:04d}"
    assert (target/'raw-native-output').is_file() and (target/'raw-root-completion.json').is_file()
    with pytest.raises(p.Error):step(f,'accept',bootstrap=f['bootstrap']['path'])
    assert f['s'].Resources(f['state']).totals()[1]['sdk']==5


@pytest.mark.parametrize('attack',['argument','speech','other-subject','other-dependency','self-review','wrong-executor','Page-payload','artifact-payload','page-order','wrong-dependency','absent-narrative'])
def test_unread_layer_other_page_or_fake_independence_never_consumed(setup,attack):
    f=launch(setup);envelope=review_envelope(f);review=envelope['reviews'][0]
    if attack in {'argument','speech'}:review['kind']=attack
    elif attack=='other-subject':review['subjects'].append(f['c'].store_for(f['state']).load_document()['pages'][0]['page'])
    elif attack=='other-dependency':review['dependencies'].append({'kind':'content','identity':'page:p1','sha256':'0'*64})
    elif attack=='self-review':review['reviewer']['type']='host_self'
    elif attack=='Page-payload':envelope['pages']=[page('p5')]
    elif attack=='artifact-payload':envelope['artifact_specs']=[{'kind':'not-a-review'}]
    elif attack=='page-order':envelope['page_order']=['p5']
    elif attack=='wrong-dependency':review['dependencies'][0]['sha256']='0'*64
    elif attack=='absent-narrative':review['dependencies'].append({'kind':'content','identity':'narrative','sha256':'0'*64})
    else:review['reviewer']['execution_ref']='/root/another-reviewer'
    complete(f,envelope)
    with pytest.raises(p.Error):step(f,'accept',bootstrap=f['bootstrap']['path'])
    assert not f['c'].store_for(f['state']).load_document()['reviews']
    assert f['s'].Resources(f['state']).totals()[1]['sdk']==5


def test_source_drift_after_packet_is_refused_without_claim_or_new_model_cost(setup):
    f=setup;f['dispatch']=prepare(f);Path(f['state']['materials'][0]['path']).write_text('{}')
    with pytest.raises(p.Error):step(f,'claim')
    assert f['s'].Resources(f['state']).totals()[1]['review']==0


def test_real_SDK_cancelled_review_is_not_claimed_or_replayed(setup):
    f=launch(setup)
    from deck_master import service
    service.task_cancel(f['state']['project'],task_id=f['dispatch']['task_id'])
    before=f['s'].Resources(f['state']).totals()
    with pytest.raises(Exception):step(f,'claim')
    assert f['s'].Resources(f['state']).totals()==before


@pytest.mark.parametrize('executor',['/root/engineering_preparer','/root/engineering_author'])
def test_excluded_preparer_or_author_cannot_be_native_reviewer(setup,executor):
    f=setup
    with pytest.raises(Exception,match='excluded'):launch(f,executor)
    assert f['s'].Resources(f['state']).totals()[1]['review']==0


@pytest.mark.parametrize('provider',['caller-selected-provider','rc3-final-native-root-controller'])
def test_actual_protected_registry_rejects_forged_receipt_selector(setup,provider):
    f=launch(setup);c=f['c'];store=c.store_for(f['state']);task=c.task_for(store,f['dispatch']['task_id'])
    from deck_master.review_evidence import EvidenceRejected,ProviderUnavailable
    with c.native_runtime(f['bootstrap']['path']) as registry:
        with pytest.raises((EvidenceRejected,ProviderUnavailable)):
            registry.review_context(store,store.load_document(),task,review_envelope(f),{'provider_id':provider,'event_id':'invented-completion'})
    assert not store.load_document()['reviews']


def test_immutable_checkpoint_tamper_does_not_launder_nonP5_change(setup):
    f=setup;f['dispatch']=prepare(f);path=f['run']/'supplied-manuscript-input.json'
    value=json.loads(path.read_bytes());value['protected_document']['pages']=[];path.write_text(json.dumps(value))
    with pytest.raises(p.Error,match='immutable provided checkpoint'):step(f,'claim')
    assert f['s'].Resources(f['state']).totals()[1]['review']==0


def test_original_SDK_cap_exhaustion_does_not_invoke_dispatch_or_renew(tmp_path,monkeypatch):
    f=fixture(tmp_path,sdk_cap=1);f['admission']=admit(f)
    from deck_master import content_review
    def not_called(*args,**kwargs):raise AssertionError('SDK invoked despite exhausted original pool')
    monkeypatch.setattr(content_review,'dispatch_preproduction_review',not_called)
    with pytest.raises(Exception,match='cap exhausted'):
        p.prepare(f['run'],f['admission']['path'],f['admission']['sha256'],f['bootstrap']['path'],True)
    assert f['s'].Resources(f['state']).totals()[1]['sdk']==1
    assert not f['c'].Journal(f['run']).unfinished()


def test_transient_admission_cannot_parse_a_different_authority_than_its_digest(setup,monkeypatch):
    f=setup;f['admission']=admit(f);c=f['c'];a=c.read(f['admission']['path']);a['independent_implementation_review_passed']=False
    ref=c.save(f['base']/'unreviewed-admission.json',a);forged=deepcopy(a);forged['independent_implementation_review_passed']=True
    actual=Path.read_bytes;reads=0
    def transient(path):
        nonlocal reads
        if str(path)==ref['path']:
            reads+=1
            if reads==2:return c.encoded(forged)
        return actual(path)
    monkeypatch.setattr(Path,'read_bytes',transient)
    with pytest.raises(p.Error):p.prepare(f['run'],ref['path'],ref['sha256'],f['bootstrap']['path'],True)
    assert not (f['run']/'supplied-manuscript-input.json').exists()


@pytest.mark.parametrize('attack',['other-Page-input','full-source-inline','mismatched-source-original'])
def test_bounded_packet_refuses_unselected_or_full_source_with_raw_retained(setup,attack):
    f=setup;d=prepare(f);c=f['c'];s=f['s'];store=c.store_for(f['state'])
    methods=c.read(d['original_raw_ref']['path']);task=c.task_for(store,d['task_id'])
    if attack=='other-Page-input':methods['work_order']['inputs'].append(store.load_document()['pages'][0]['page'])
    elif attack=='full-source-inline':methods['work_order']['source_reading'][0]['text']=json.dumps({'pages':[page('p1'),page('p5')]})
    else:methods['work_order']['source_reading'][0]['original_file']=store.load_document()['pages'][0]['page']
    target=f['base']/'adversarial-method-response';checkpoint=c.read(f['run']/'supplied-manuscript-input.json')
    with pytest.raises(p.Error):p.packet(s,c,c.Journal(f['run']),f['state'],task,methods,target,checkpoint)
    assert (target/'quarantine/sdk-method-response.json').is_file()
    assert not (target/'author-packet/workorder-view.json').exists()
