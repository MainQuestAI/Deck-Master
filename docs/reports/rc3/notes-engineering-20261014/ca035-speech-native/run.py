"""Reproducible L1 authority/review fixtures + actual native files, no human/model quality claim."""
from pathlib import Path
import sys, json, importlib.util, copy, hashlib, traceback
sys.path.append('/workspace/work/rc3/reviews/rc3-02-speech-native-0b0ed2a/fixture-deps')
ROOT=Path('/workspace/work/rc3/reviews/rc3-02-code-snapshot-ca035')
sys.path.insert(0,str(ROOT/'tests/rebuild'))
from deck_master import service, collaboration, content_production, content_review, pipeline, exports, editing, tasks
from deck_master.models import bump_revision,require_writer,sha256_bytes
from deck_master.store import Store
from deck_master.compiler.native import notes_records,normalize_notes
from synthetic_review_provider import dispatch_with_synthetic_provider,accept_with_synthetic_provider
import test_compose_v2_phases as phase
import test_content_preproduction_review as review
import test_eligibility_enforcement as enf
from test_rc3_notes_visual_inputs import _seed_imported_plan
from test_service_flow import _draft_page,_svg_for
from test_page_visual_gate import _accept,_svg_envelope
from page_visual_helpers import pass_page_review,make_page_reviews
spec=importlib.util.spec_from_file_location('synthetic_w07',ROOT/'examples/workbench/w07_synthetic.py')
w07=importlib.util.module_from_spec(spec);spec.loader.exec_module(w07)
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent/'run-final'
OUT.mkdir(exist_ok=True)

def module_bytes(label):
 import deck_master
 base=Path(deck_master.__file__).resolve().parent
 save(OUT,label,{'package_root':str(base),'python':sys.executable,'files':{str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}})
FULL=['narrative','plan','page_copy','speech','design','blueprint','svg','review','output']

def save(where,name,value):
 (where/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')

def initial(where,mode):
 material=where/'source.txt';material.write_text('第一行：版本未知时先记录未知。\n第二行：紧急程度与可得性是两个维度。\n第三行：不得从缺字段率推出节省比例。\n')
 project=where/'project'
 draft=None if mode=='bound' else {'pages':[_draft_page('p1','已确认稿甲','54/120=45%，不是节约率。'),_draft_page('p2','已确认稿乙','交接完成不等于解决。')]}
 if draft:
  for p in draft['pages']: p['speaker_notes']='用户原注：'+p['page_id']+'\n\n末段原注。\n'
 service.create(project,brief='Explicit synthetic RC3 speech native engineering trace',sources=[material],draft=draft,project_format='workbench.v3')
 store=Store(project);doc=store.load_document()
 doc2=bump_revision(copy.deepcopy(doc),{'operation_id':'bootstrap-control','kind':'collaboration_update','description':'Explicit L1 fixture control, not human evidence','read_set':[]})
 doc2['collaboration']={'schema_version':'collaboration.v1','authority_policy':'traceable','quality_profile':{'content_review_requirement':'independent_model_or_human' if mode=='bound' else 'fidelity_only','requirement_origin':'default_new_argument' if mode=='bound' else 'confirmed_manuscript','override_decision_ref':None},'request':None,'decisions':[],'authorizations':[]}
 require_writer(doc2,'collaboration.v1');store.commit_change(base_revision=doc['revision_id'],document=doc2,operation_id='bootstrap-control')
 scope=phase._scope(layers=FULL,page_ids=[] if mode=='bound' else ['p1','p2'])
 collaboration.start_request(project,input={'intent':'full_deck','content_intent':None,'instruction_evidence':phase._instruction(store,'explicit-synthetic-full-engineering-request'),'scope':scope,'replace_request_id':None},base_revision=store.current_revision_id(),operation_id='request-initial')
 if mode=='bound':
  for ref in store.load_document()['tasks']:
   legacy=store.read_object_json(ref)
   if legacy['status'] in ('queued','awaiting_host','running') and not legacy.get('collaboration_binding'):
    assert not legacy['call_allowances']
    save(where,'original-legacy-task-cancelled',service.task_cancel(project,task_id=legacy['task_id'],reason='Explicit engineering migration switches to accountable compose.v2; original 0-call task retained as cancelled history'))
  t=content_production.open_phase_task(store,store.load_document(),operation_id='argument',phase='argument')
  out=phase._submit(project,t,{'narrative':phase._argument_narrative(store.load_document()['project_id'])},'narrative')
  phase._adopt_direction(project,store,out['operation_result']['result_refs'][0])
  t=content_production.open_phase_task(store,store.load_document(),operation_id='page-copy',phase='page_copy')
  doc=store.load_document()
  pages=[phase._page(store,doc,pid,notes='用户原注：'+pid+'\n\n末段原注。\n') for pid in ('p1','p2')]
  phase._submit(project,t,{'pages':pages,'page_order':['p1','p2'],'plan_input':phase._plan_input(doc,['p1','p2'],source_links=[phase._source_link(store,doc,'L1')])},'page_copy')
 else:
  _seed_imported_plan(store);doc=store.load_document();plan=store.read_object_json(doc['content_plan']);plan['input']['speech_policy']={'mode':'cues','source':'provided','output':'pptx_notes'}
  updated=bump_revision(copy.deepcopy(doc),{'operation_id':'seed-policy','kind':'content_update','description':'Schema-valid imported initial state; not RC3-04 import E2E','read_set':[]});updated['content_plan']=store.put_json_object(plan);store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='seed-policy')
 save(where,'initial-control',store.load_document()['collaboration'])
 grant=enf._grant(project,store,actions=('dispatch.blueprint','dispatch.host_task','task.start','task.accept','allowance.allocate','generation.dispatch','call.begin','render.preview','compile.ppt','dispatch.compose','export.review'),max_external_calls=2,scope={**scope,'page_ids':['p1','p2']})
 save(where,'explicit-synthetic-execute-grant',grant)
 return project,store

def qualify(where,project,store,label):
 doc=store.load_document();subjects=[ref for ref in [doc.get('narrative'),doc.get('content_plan'),*[e['page'] for e in doc['pages']]] if ref]
 adapter=review._independent_adapter(store,doc,subjects=subjects)
 out=dispatch_with_synthetic_provider(project,adapter_context=adapter)
 save(where,label+'-dispatch',out)
 if out['status']!='review_dispatched': raise RuntimeError(out)
 t=out['task'];units=content_review.required_units(store,doc)
 source_deps=[{'kind':'source','identity':x['source_id'],'sha256':x['extract']['sha256']} for x in doc['sources']]
 reviews=[review._review(store,doc,k,subjects=subjects,deps=source_deps+[{'kind':'content','identity':key,'sha256':ref['sha256']} for key,ref in [('narrative',doc.get('narrative')),('content_plan',doc.get('content_plan')),*[(f"page:{e['page_id']}",e['page']) for e in doc['pages']]] if ref],reviewer={'type':'independent_host','id':'model-b','execution_ref':'exec-independent','independence_confirmed':True,'identity_receipt':None,'assurance':'host_attested'}) for k in units]
 accepted=accept_with_synthetic_provider(project,task_id=t['task_id'],operation_id=t['operation_id'],produced_against=t['produced_against'],result_payload={'kind':'review','reviews':reviews,'notes':'Explicit synthetic independent L1 fixture, no actual model or human quality claim'},adapter_context=adapter)
 save(where,label+'-accepted',accepted)
 state=content_review.preproduction_status(store,store.load_document());save(where,label+'-status',state);assert state['status']=='pass'

def complete_visual(where,project,store):
 flow=w07.SyntheticW07.__new__(w07.SyntheticW07);flow.project=project;flow.store=store;flow.root=where;flow.runtime=where/'synthetic-runtime'
 for pid in ('p1','p2'):
  doc=store.load_document();entry=next(e for e in doc['pages'] if e['page_id']==pid)
  t=service.open_blueprint_task(store,doc,entry);save(where,pid+'-actual-blueprint-task',t);flow.image(t)
  t=service.open_host_task(store,kind='reconstruct',page_ids=[pid],instruction='Explicit synthetic reconstruct fixture, actual SVG compiler')
  doc=store.load_document();entry=next(e for e in doc['pages'] if e['page_id']==pid);page=store.read_object_json(entry['page']);sha=store.read_object_json(entry['blueprint'])['file']['sha256']
  svg=_svg_for(page).replace(b'<svg ',f'<svg data-blueprint-sha256="{sha}" '.encode(),1)
  payload=_svg_envelope(pid);payload['artifact_specs'][0]['provenance']['generated_from_page']=entry['page'];payload['artifact_specs'][0]['dependencies']=[{'kind':'content','identity':'page:'+pid,'sha256':entry['page']['sha256']}]
  _accept(project,t,payload,file_name='page.svg',data=svg)
  response=service.continue_project(project);save(where,pid+'-actual-normal-continue',response)
  entry=next(e for e in store.load_document()['pages'] if e['page_id']==pid)
  assert entry['svg_preview'] is not None,response
  t=next(t for t in response['pending_tasks'] if t['kind']=='review' and t.get('review_stage')=='page_visual' and t['scope_pages']==[pid])
  save(where,pid+'-actual-pagevisual-public-task',t)
  fixture_reviews=make_page_reviews(t);save(where,pid+'-actual-pagevisual-L1-fixture',fixture_reviews)
  assert all(ref is not None for review in fixture_reviews for ref in review['subjects'])
  pass_page_review(project,t)
 for entry in store.load_document()['pages']: assert editing.page_visual_summary(store,store.load_document(),entry)['status']=='pass'

def ledger(store,doc):
 ts=[store.read_object_json(ref) for ref in doc['tasks']]
 return {'image_tasks':[t['task_id'] for t in ts if t['kind']=='blueprint'],'allowances':[{'task_id':t['task_id'],'values':t['call_allowances']} for t in ts if t['kind']=='blueprint'],'attempts':[ref for t in ts for ref in t.get('generation_attempts') or []]}

def run(mode):
 where=OUT/mode;where.mkdir();project,store=initial(where,mode);qualify(where,project,store,'before-review');complete_visual(where,project,store)
 before_report=pipeline.produce(project);save(where,'initial-native-compile',before_report);before=store.load_document();save(where,'before-document',before)
 assert before_report['status']=='pass'
 oldref=before['outputs']['pptx'];oldfile=store.read_object_json(oldref)['file'];oldbytes=store.read_object_bytes(oldfile);(where/'original.pptx').write_bytes(oldbytes)
 oldreviewbytes={r['sha256']:hashlib.sha256(store.read_object_bytes(r)).hexdigest() for r in before['reviews']}
 original_ledger=ledger(store,before)
 t=content_production.open_phase_task(store,before,operation_id='speech-update',phase='speech',page_ids=['p1']);save(where,'actual-speech-task',t)
 notes='口播：54/120=45%，不是节约率。\n\n\n交接完成不等于解决。\n末段新讲稿。\n'
 update={'page_id':'p1','page_ref':before['pages'][0]['page'],'speaker_notes':notes,'speech_segments':[{'segment_id':'s1','start_codepoint':0,'end_codepoint':len(notes),'narrative_node_ids':['n1'] if mode=='bound' else [],'kind':'cue','estimated_seconds':12}]}
 save(where,'speech-accepted',phase._submit(project,t,{'updates':[update]},'speech'));after=store.load_document();save(where,'after-speech-document',after)
 for old,new in zip(before['pages'],after['pages']):
  assert all(old[s]==new[s] for s in ('blueprint','svg','svg_preview'))
  assert editing.page_visual_summary(store,after,new)['status']=='pass'
 assert after['outputs']['pptx'] is None
 assert oldreviewbytes=={r['sha256']:hashlib.sha256(store.read_object_bytes(r)).hexdigest() for r in before['reviews']}
 plan=store.read_object_json(after['content_plan']);assert {x['page_id']:x['page_ref'] for x in plan['page_links']}=={e['page_id']:e['page'] for e in after['pages']}
 if mode!='bound': assert plan['narrative_ref'] is None and after.get('narrative') is None
 try: pipeline.produce(project)
 except Exception as error: save(where,'honest-current-qualification-block',{'type':type(error).__name__,'reason':str(error),'code':getattr(error,'error_code',None)})
 else: save(where,'honest-current-qualification-block',{'blocked':False})
 status=content_review.preproduction_status(store,store.load_document());save(where,'post-speech-before-review-status',status)
 if status['status']!='pass': qualify(where,project,store,'after-speech-review')
 compiled=pipeline.produce(project);save(where,'final-native-compile',compiled);assert compiled['status']=='pass'
 result=exports.create(project,purpose='review',output_dir=where/'public',notes_policy='pptx_notes');save(where,'actual-export',result)
 exported,_=exports.download(project,export_id=result['export_id'],filename='deck.pptx');(where/'downloaded.pptx').write_bytes(exported)
 records=notes_records(exported);doc=store.load_document();expected=[normalize_notes(store.read_object_json(e['page']).get('speaker_notes','')) for e in doc['pages']]
 assert [r['notes'] for r in records]==expected and [r['page_id'] for r in records]==[e['page_id'] for e in doc['pages']]
 assert ledger(store,doc)==original_ledger
 save(where,'final-readback',records);save(where,'zero-additional-image-ledger',{'before':original_ledger,'after':ledger(store,doc),'equal':True})
 summary={'mode':mode,'status':'PASS','source':'ca0351d2397ba154e9f77363bd0f325629eb0ebd','quality':'synthetic L1 authority/reviews only','actual_files':True,'original_pptx_sha256':sha256_bytes(oldbytes),'final_pptx_sha256':sha256_bytes(exported),'full_notes_equal':True,'zero_additional_image_tasks_allowances_attempts':True,'desktop':'NOT_RUN','human':'NOT_RUN','import_entry_e2e':'NOT_RUN' if mode!='bound' else 'not_applicable'}
 save(where,'summary',summary);return summary

if __name__=='__main__':
 import deck_master
 origin=Path(deck_master.__file__).resolve()
 expected=Path('/workspace/work/rc3/candidate-02-ca035/prefix/.deck-master/releases/ca0351d2397b-17a3bb5c40bd/venv')
 assert origin.is_relative_to(expected),str(origin)
 save(OUT,'fixed-execution-origin',{'python':sys.executable,'deck_master':str(origin),'fixture_snapshot':str(ROOT),'source_sha':'ca0351d2397ba154e9f77363bd0f325629eb0ebd','tree':'05191deede70f26e661b28f4221c3c0d00ef2ecf','public_subjects':'Actual normal continue rendered SVG preview and dispatched review; no omitted subject or reduced check.'})
 module_bytes('installed-product-bytes-before')
 summaries=[]
 for mode in (sys.argv[2:] or ('bound','imported_mapping_null_narrative')):
  try: summaries.append(run(mode))
  except Exception as error:
   report={'mode':mode,'status':'BLOCKED','error_type':type(error).__name__,'error':str(error),'traceback':traceback.format_exc(),'desktop':'NOT_RUN','human':'NOT_RUN'};save(OUT,mode+'-blocked',report);summaries.append(report)
 module_bytes('installed-product-bytes-after')
 save(OUT,'summary',summaries);print(json.dumps(summaries,ensure_ascii=False,indent=2))
