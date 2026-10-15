"""Independent F9 public SDK matrix; explicit synthetic authority, no model calls."""
from pathlib import Path
import copy,json,sys,uuid
import deck_master
from deck_master import collaboration,models,production,tasks,service,generation
OUT=Path(__file__).resolve().parent
sys.path.append('/workspace/work/rc3/reviews/env-03-snapshot-cf61e5e/lib/python3.12/site-packages')
sys.path.append('/workspace/work/rc3/reviews/rc3-03-code-snapshot-cf61e5e/tests/rebuild')
from test_rc3_design_workflows import project,confirmed,dispatch
from test_rc3_notes_visual_inputs import enf

def record(path,store,value):
 return collaboration.record_decision(path,input=value,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['decision_ref']
def resolve(store,recipe,doc=None):
 doc=doc or store.load_document()
 return production.resolve_generation_design(store,doc,doc['pages'][0],recipe_ref=recipe['recipe_ref'])

cases=['same_version_twice','value','scope','layers','topic_to_speech','topic_to_tradeoff',
 'reject','withdrawn','new_identity_equal_value','unrelated_p2_style','unrelated_p1_speech',
 'scope_p2_to_p1','topic_speech_to_style']
results=[]
for name in cases:
 base=OUT/'matrix'/name;base.mkdir(parents=True,exist_ok=True)
 path,store,_=project(base)
 value={'topic':'style','decision_id':'stable-identity','subject_refs':[],
  'value':{'palette':'blue'},'disposition':'accepted','authority_mode':'direct_user',
  'scope':enf._scope(page_ids=['p1']),'instruction_evidence':enf._declared(store)}
 if name in ('unrelated_p2_style','scope_p2_to_p1'):value['scope']=enf._scope(page_ids=['p2'])
 if name in ('unrelated_p1_speech','topic_speech_to_style'):value['topic']='speech'
 old_ref=record(path,store,value)
 recipe=confirmed(path,store);task=dispatch(path,store,recipe,['p1'])[0]
 before=store.load_document();old=resolve(store,recipe)
 immutable={old_ref['path']:store.read_object_bytes(old_ref)}
 prepared=generation.prepared_input(store,before,task)
 patch={**copy.deepcopy(value),'replaces':old_ref}
 if name in ('value','unrelated_p2_style','unrelated_p1_speech'):patch['value']={'palette':'green'}
 elif name=='scope':patch['scope']=enf._scope(page_ids=['p2'])
 elif name=='layers':patch['scope']=enf._scope(page_ids=['p1'],layers=['design'])
 elif name=='topic_to_speech':patch['topic']='speech'
 elif name=='topic_to_tradeoff':patch['topic']='tradeoff'
 elif name=='reject':patch['disposition']='rejected'
 elif name=='new_identity_equal_value':patch.pop('replaces');patch['decision_id']='separate-identity'
 elif name=='scope_p2_to_p1':patch['scope']=enf._scope(page_ids=['p1'])
 elif name=='topic_speech_to_style':patch['topic']='style'
 new_ref=record(path,store,patch)
 if name=='same_version_twice':new_ref=record(path,store,{**copy.deepcopy(value),'replaces':new_ref})
 if name=='withdrawn':
  # Public record_decision always creates active; only this explicitly
  # synthetic disposable project injects a schema-valid withdrawn head.
  doc=store.load_document();withdrawn=store.read_object_json(new_ref)
  withdrawn.update(status='withdrawn',replaces=new_ref);models.validate_decision_semantics(withdrawn)
  new_ref=store.put_json_object(withdrawn);doc['collaboration']['decisions'].append(new_ref)
  op=str(uuid.uuid4());doc=models.bump_revision(doc,{'operation_id':op,'kind':'collaboration_update',
   'description':'audit-only withdrawn head L1 status injection','read_set':[]})
  store.commit_change(base_revision=store.current_revision_id(),document=doc,operation_id=op)
 after=store.load_document();new=resolve(store,recipe)
 same=production.consumed_design(old,store=store)==production.consumed_design(new,store=store)
 expected=name in ('same_version_twice','unrelated_p2_style','unrelated_p1_speech')
 current=tasks.task_inputs_current(store,after,task)
 assert same is expected and current is expected,(name,same,current)
 assert before['pages']==after['pages']
 assert models.content_identity(before)==models.content_identity(after)
 assert generation.prepared_input(store,after,task)==prepared
 assert all(store.read_object_bytes({'path':p,'sha256':p.split('/')[-1].split('.')[0]})==data for p,data in immutable.items())
 refs=new['content_basis']['decision_refs']
 assert len(refs)==len(set(item['path'] for item in refs))
 if name=='same_version_twice':
  assert refs==[new_ref] and old['content_basis']['decision_refs']==[old_ref]
  # The original failing public sequence now also permits claim + exact
  # Request freeze; it does not reconstruct a new historical basis.
  service.task_start(path,task_id=task['task_id'],execution_ref='independent-f9-same-audit',
   supported_protocols=[generation.PROTOCOL],capabilities=task['required_capabilities'])
  frozen=generation.freeze(path,task_id=task['task_id'],input=prepared,
   base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
  assert frozen['input']==prepared
  wrong=copy.deepcopy(prepared)
  wrong['design_context']['content_basis']['consumed']['decision_slices'][0]['sha256']='0'*64
  pointer=store.read_current()
  try:generation.freeze(path,task_id=task['task_id'],input=wrong,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
  except generation.GenerationError as exc:freeze_tamper={'type':type(exc).__name__,'message':str(exc)}
  else:raise AssertionError('frozen-basis SHA tamper accepted')
  assert store.read_current()==pointer
  (OUT/'original-repro-before.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
  (OUT/'original-repro-after.json').write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n')
  (OUT/'original-repro-frozen-request.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
 results.append({'case':name,'expected_current':expected,'actual_current':current,'same_consumed_design':same,
  'manuscript_content_identity_unchanged':True,'actual_basis_refs':refs,'old_ref':old_ref,'new_ref':new_ref,
  'project':str(path),'task_id':task['task_id'],'frozen_preparation_unchanged':True})

# Normalization cannot erase decision identity, foreign project, scope or
# mismatched basis Ref evidence. These are read-only context fault probes.
faults=[]
reference=json.loads((OUT/'original-repro-before.json').read_text())
path=Path(results[0]['project'])
from deck_master.store import Store
store=Store(path)
original_ref=reference['content_basis']['decision_refs'][0]
for fault in ('foreign_project','foreign_page','foreign_topic','mismatched_refs'):
 bad=copy.deepcopy(reference);decision=store.read_object_json(original_ref)
 if fault=='foreign_project':decision['project_id']='foreign-project'
 elif fault=='foreign_page':decision['scope']=enf._scope(page_ids=['p2'])
 elif fault=='foreign_topic':decision['topic']='speech'
 else:decision['value']={'palette':'tampered'}
 foreign_ref=store.put_json_object(decision)
 bad['content_basis']['consumed']['decision_slices'][0]['decision_ref']=foreign_ref
 if fault!='mismatched_refs':bad['content_basis']['decision_refs']=[foreign_ref]
 try:production.consumed_design(bad,store=store)
 except models.ModelError as exc:faults.append({'fault':fault,'rejected':True,'error':str(exc)})
 else:raise AssertionError('normalization accepted '+fault)
assert json.loads((OUT/'original-repro-before.json').read_text())==reference
result={'status':'PASS','evidence_kind':'independent installed public SDK, synthetic authority, zero image calls',
 'cases':results,'faults':faults,'frozen_digest_tamper':freeze_tamper,'external_calls':0,
 'limitations':['withdrawn status is explicit synthetic schema-valid injection because no public status writer exists.']}
(OUT/'independent-public-matrix.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','cases':len(results),'normalization_faults':len(faults),'freeze_tamper_rejected':True}))
