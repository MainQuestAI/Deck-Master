"""Only R5-C3 installed delta. Explicit synthetic L1, no images/providers.

Preload the fixed wheel before appending only the fixed test-helper path.
Named helpers construct L1 data; no imported tests or source core execution.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys
import traceback
import uuid

import deck_master
from deck_master import collaboration, eligibility, icons, pipeline, production, service, ui_journal
from deck_master.models import ModelError, bump_revision
from deck_master.store import Store, StoreError

OUT=Path(__file__).resolve().parent
RUN=OUT/'run1'
RUN.mkdir(exist_ok=False)
EXPECTED=Path('/workspace/work/rc3/reviews/env-04-r5-installed-740af2b/lib/python3.12/site-packages/deck_master')
assert Path(deck_master.__file__).resolve().parent == EXPECTED
assert sys.flags.isolated and sys.dont_write_bytecode
PRELOADED={k:str(getattr(v,'__file__',None)) for k,v in sys.modules.items() if k=='deck_master' or k.startswith('deck_master.')}
HELPER=Path('/workspace/work/rc3/reviews/rc3-04-r5-code-snapshot-740af2b/tests/rebuild')
sys.path.append(str(HELPER))
from rc3_fixtures import authorize_scope, evidence_for, settle_fidelity_review, source_snapshot
from test_icon_quality import icon_store, confirm, dispatch
from test_service_flow import _draft_page

def clean(value):
    if isinstance(value,Path):return str(value)
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,(str,int,float,bool)) or value is None:return value
    return repr(value)

def save(name,value):
    (RUN/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2)+'\n')

def call(label,fn,*args,**kwargs):
    row={'label':label,'function':fn.__module__+'.'+fn.__name__,'args':clean(args),'kwargs':clean(kwargs)}
    try:
        result=fn(*args,**kwargs)
        row['result']=clean(result)
        return result
    except Exception as exc:
        row['exception']={'type':type(exc).__name__,'message':str(exc),'attributes':clean(vars(exc))}
        raise
    finally:
        with (RUN/'events.jsonl').open('a') as stream:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')

def observe(project,name):
    store=Store(project)
    value={'tree':source_snapshot(project),'document':store.load_document(),
        'current_bytes_hex':(store.deck_root/'current.json').read_bytes().hex()}
    save(name+'.json',value)
    return value

def expect_error(label,kind,fn,*args,path=None,contains=None,**kwargs):
    try:
        call(label,fn,*args,**kwargs)
    except kind as exc:
        if path is not None:assert exc.path==path,(exc.path,path)
        if contains is not None:assert contains in str(exc)
        return {'type':type(exc).__name__,'message':str(exc),'path':getattr(exc,'path',None),'detail':getattr(exc,'detail',None)}
    raise AssertionError(label+' unexpectedly accepted')

def corrupt_task():
    folder=RUN/'C3-task-corruption'
    folder.mkdir()
    store=call('explicit L1 icon fixture constructor',icon_store.__wrapped__,folder)
    project=store.project_root
    healthy=call('healthy preproduction before actual Task damage',eligibility.preproduction_state,store,store.load_document())
    assert healthy['satisfied'] is True
    recipe=call('actual zero-call icon confirmation',confirm,store)
    task=call('actual icon dispatch',dispatch,store,recipe)[0]
    doc=store.load_document()
    ref=next(r for r in doc['tasks'] if store.read_object_json(r)['task_id']==task['task_id'])
    damaged=project/ref['path']
    original=damaged.read_bytes()
    (RUN/'C3-original-task-bytes.bin').write_bytes(original)
    save('C3-damage.json',{'ref':ref,'original_sha256':hashlib.sha256(original).hexdigest(),
        'replacement_bytes_hex':b'{R5 independent L1 broken Task'.hex(),'evidence_level':'L1_SYNTHETIC_MECHANICAL_ONLY'})
    damaged.write_bytes(b'{R5 independent L1 broken Task')
    before=observe(project,'C3-damaged-before')
    state=call('narrow expected lineage ModelError isolation',eligibility.preproduction_state,store,doc)
    assert state['status']=='unreadable' and state['satisfied'] is False
    assert state['missing_units']==state['units'] and not state['satisfied_units'] and not state['review_refs']
    assert state['via'] is None and any('preserve' in r for r in state['reasons'])
    described=call('actual collaboration.describe remains readable',collaboration.describe,project)
    info=call('actual project_info remains readable',ui_journal.project_info,project)
    assert described['revision_id']==info['revision_id']==doc['revision_id']
    card=next(c for c in described['blocking_cards'] if c['action']=='dispatch.blueprint')
    assert card['decision']['allowed'] is False and 'unreadable' in json.dumps(card['decision'])
    listed=call('original dispatch_unknown warning remains',icons.listing,project,include_stale=True)
    assert listed['proposals'][0]['status']=='dispatch_unknown'
    assert observe(project,'C3-read-after')==before
    strict=expect_error('strict production lineage still refuses',ModelError,
        production.resolve_page_rendering_design,store,doc,doc['pages'][0],
        path='blueprint/provenance/generation_request',contains='generation lineage')
    try:
        call('public produce blocks unreadable preproduction',pipeline.produce,project)
    except eligibility.EligibilityBlocked as exc:
        assert 'preproduction_blocked' in exc.decision['reason_codes']
        assert exc.decision['preproduction']['status']=='unreadable'
        refusal=exc.decision
    else:raise AssertionError('produce admitted damaged Task')
    assert observe(project,'C3-refusals-after')==before
    assert damaged.read_bytes()==b'{R5 independent L1 broken Task'
    return {'healthy':healthy,'damaged_state':state,'strict_refusal':strict,'produce_refusal':refusal,
        'all_reads_refusals_full_tree_Current_refs_fees_unchanged':True,
        'no_damage_repair_no_real_provider_image_human':True}

def asset_project(name):
    folder=RUN/name
    folder.mkdir()
    logo=folder/'logo.svg'
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><path d="M1 1L7 7"/></svg>')
    project=folder/'project'
    call('actual create with one allowed L1 local asset',service.create,project,
        brief='R5 independent one-page asset boundary L1 synthetic',
        draft={'pages':[_draft_page('p1','合成资产边界','本页仅用于资产错误与恢复的软件验证。')]},
        design={'assets':[{'asset_id':'logo','kind':'logo','file':str(logo),'external_use':'allowed'}],
                'allowed_asset_ids':['logo']})
    store=Store(project)
    scope={'subject':'pages','page_ids':['p1'],'page_manifest_ref':None,'external_artifact_ref':None,
        'layers':['blueprint'],'allow_page_membership_change':False,'allow_page_order_change':False,'purpose':'working'}
    evidence=call('store explicit L1 bounded production instruction',evidence_for,project,
        text='L1 synthetic engineering review: only p1 blueprint dispatch, at most one call, zero candidates; no image/provider call will occur. Require actual valid assets and current manuscript fidelity before dispatch.',
        locator='L1:R5-independent-asset-boundary:'+name)
    call('actual narrowly bounded grant',authorize_scope,project,actions=['dispatch.blueprint'],scope=scope,
        max_external_calls=1,max_candidate_count=0,adoption_policy='within_scope',evidence=evidence)
    call('actual L1 current manuscript fidelity task claim and adoption',settle_fidelity_review,project,
        page_ids=['p1'],execution_ref='L1-r5-independent-fidelity-'+name,
        scenario='Explicit synthetic fixed manuscript before local asset fault; no independent model/human/native quality claim')
    healthy=call('healthy actual preproduction before asset fault',eligibility.preproduction_state,store,store.load_document())
    assert healthy['satisfied'] is True
    assert not any(store.read_object_json(r)['kind']=='blueprint' for r in store.load_document()['tasks'])
    return project,store,healthy

def asset_case(permission=None):
    name='asset-'+(permission or 'missing')
    project,store,healthy=asset_project(name)
    before_doc=store.load_document()
    design=deepcopy(before_doc['design_context'])
    if permission is not None:
        design['assets'][0]['external_use']=permission
    else:
        design['assets'][0]['artifact']={'path':'.deckmaster/objects/ff/'+'f'*64+'.json','sha256':'f'*64}
    before_write=observe(project,name+'-before-write-refusal')
    if permission is not None:
        write_refusal=expect_error('public update_design rejects forbidden asset',ModelError,service.update_design,
            project,design_context=design,base_revision=before_doc['revision_id'],
            path='design_context/allowed_asset_ids',contains='not allowed for external use')
    else:
        write_refusal=expect_error('public update_design rejects missing asset',service.ServiceError,
            service.update_design,project,design_context=design,base_revision=before_doc['revision_id'],contains='unreadable')
    assert observe(project,name+'-after-write-refusal')==before_write
    # Deliberately create a new private L1 historical-bad-design fixture using
    # actual Store CAS. No fake Task, trusted reviewer or validator bypass.
    operation='L1-r5-asset-fault-'+uuid.uuid4().hex
    injected=bump_revision(before_doc,{'operation_id':operation,'kind':'design_update',
        'description':'L1 deliberate persisted historical asset fault, isolated review only','read_set':[]})
    injected['design_context']=design
    call('explicit private historical L1 fault commit',store.commit_change,
        base_revision=before_doc['revision_id'],document=injected,operation_id=operation)
    before=observe(project,name+'-fault-before')
    doc=store.load_document()
    error_type=ModelError if permission is not None else StoreError
    error_path='design_context/allowed_asset_ids' if permission is not None else 'asset:logo'
    preprod=expect_error('preproduction preserves precise original asset error',error_type,
        eligibility.preproduction_state,store,doc,path=error_path)
    dispatch_refusal=expect_error('actual strict blueprint dispatch preserves asset error',error_type,
        service.open_blueprint_task,store,doc,doc['pages'][0],path=error_path)
    if permission is None:
        continued=call('public continue returns exact asset recovery hint',service.continue_project,project)
        assert continued['status']=='needs_input' and not continued['pending_tasks']
        assert continued['findings'][0]['code']=='broken_asset_reference'
        assert continued['findings'][0]['field']=='asset:logo'
        assert continued['next_action']=='restore_or_replace_asset'
        continued_record=continued
    else:
        continued_record=expect_error('public continue does not relabel semantic asset permission',ModelError,
            service.continue_project,project,path=error_path)
    assert observe(project,name+'-fault-after')==before
    assert not any(store.read_object_json(r)['kind']=='blueprint' for r in doc['tasks'])
    return {'permission':permission,'healthy_preproduction_before_fault':healthy,
        'current_write_refusal':write_refusal,'actual_preproduction_refusal':preprod,
        'strict_dispatch_refusal':dispatch_refusal,'continue':continued_record,
        'full_tree_Current_task_refs_authority_fee_unchanged_by_all_refusals':True,
        'no_blueprint_task_no_reserved_or_begun_image_call':True}

CASES=[('C3-bad-Task-JSON',corrupt_task),
    ('C3-asset-restricted',lambda:asset_case('restricted')),
    ('C3-asset-unspecified',lambda:asset_case('unspecified')),
    ('C3-asset-missing',asset_case)]
results=[]
for name,fn in CASES:
    try:
        result=fn()
        row={'case':name,'status':'PASS','observation':result}
    except Exception as exc:
        row={'case':name,'status':'FAIL','exception':{'type':type(exc).__name__,'message':str(exc)},'traceback':traceback.format_exc()}
    results.append(row)
    save('results.json',results)
    print(json.dumps({'case':name,'status':row['status'],'exception':row.get('exception')},ensure_ascii=False),flush=True)

origins={}
for name,module in sorted(sys.modules.items()):
    if name=='deck_master' or name.startswith('deck_master.'):
        path=getattr(module,'__file__',None)
        assert path is not None and Path(path).resolve().is_relative_to(EXPECTED),(name,path)
        origins[name]=path
save('runtime-origins.json',{'python':sys.executable,'version':deck_master.__version__,
    'preloaded_before_helpers':PRELOADED,'all_deck_master_origins':origins,
    'only_test_helper_path':str(HELPER),'source_core_imports':False,'isolated':sys.flags.isolated,
    'dont_write_bytecode':sys.dont_write_bytecode,'actual_real_model_image_provider_human_calls':0,
    'evidence_level':'L1_SYNTHETIC_MECHANICAL_ONLY'})
sys.exit(0 if all(r['status']=='PASS' for r in results) else 1)
