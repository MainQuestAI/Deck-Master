"""Read/decide an actual old-installed candidate with cf; no real project touched."""
from pathlib import Path
import copy,hashlib,json,shutil,sys,uuid
import deck_master
from deck_master import candidates,collaboration,models,production,tasks,eligibility,generation
from deck_master.store import Store
OUT=Path(__file__).resolve().parent
assert 'candidate-03-cf61e5e' in deck_master.__file__
seed=json.loads((OUT/'old5db-candidate-seed.json').read_text())
source=Path(seed['project'])
results=[]
def clone(name):
 path=OUT/('cross-version-'+name);shutil.copytree(source,path);return path,Store(path)
def immutable_intact(store):
 return all(hashlib.sha256(store.read_object_bytes(item['ref'])).hexdigest()==item['bytes_sha256'] for item in seed['immutable_refs'])
def selection(doc):
 return {'schema_version':'candidate_selection.v1','project_id':doc['project_id'],
  'base_revision':doc['revision_id'],'candidate_ids':[seed['candidate_id']]}
def replace_decision(path,store,value):
 return collaboration.record_decision(path,input=value,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['decision_ref']
def inject_candidate(store,mutate):
 # Explicit L1 metadata fault injection only in a disposable clone, retaining
 # all old immutable objects. Match ordinary linkage so digest gates execute.
 doc=store.load_document();candidate=copy.deepcopy(seed['candidate']);mutate(candidate)
 models.validate_schema('candidate',candidate);ref=store.put_json_object(candidate)
 doc['candidates']=[ref if item==seed['candidate_ref'] else item for item in doc['candidates']]
 task=tasks._lookup_task(doc,seed['task_id'],store)
 task['candidate_refs']=[ref if item==seed['candidate_ref'] else item for item in task['candidate_refs']]
 doc=tasks._replace_task_ref(doc,task,store.put_json_object(task),store)
 op=str(uuid.uuid4());doc=models.bump_revision(doc,{'operation_id':op,'kind':'task_update',
  'description':'audit-only L1 candidate metadata fault injection','read_set':[]})
 store.commit_change(base_revision=store.current_revision_id(),document=doc,operation_id=op)

path,store=clone('same-audit')
before=candidates.show(path,candidate_id=seed['candidate_id'])
assert before['generation_basis']['status']=='current'
new_ref=replace_decision(path,store,{**seed['decision_value'],'replaces':seed['decision_ref']})
shown=candidates.show(path,candidate_id=seed['candidate_id'])
assert shown['generation_basis']['status']=='current'
assert shown['candidate']==seed['candidate']
doc=store.load_document();task=tasks._lookup_task(doc,seed['task_id'],store)
actual_basis=candidates.generation_basis(store,doc,'p1','blueprint',task=task)
assert actual_basis['design_digest']==seed['old_exact_design_digest']
request=store.read_object_json(seed['request_ref']);current=production.resolve_generation_design(store,doc,doc['pages'][0],recipe_ref=seed['recipe_ref'])
normalized_digest=models.sha256_bytes(models.canonical_json_bytes(production.consumed_design(current,store=store)))
assert normalized_digest!=seed['old_exact_design_digest']
assert current['content_basis']['decision_refs']==[new_ref]
assert request['input']['design_context']['content_basis']['decision_refs']==[seed['decision_ref']]
budget_before=eligibility.allowance_usage(store,doc)['totals']
plan=candidates.plan(path,input=selection(doc))
adopt=candidates.adopt(path,input=plan['plan'],base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
assert store.load_document()['pages'][0]['blueprint']==seed['candidate']['result_ref']
assert eligibility.allowance_usage(store,store.load_document())['totals']==budget_before
assert generation.show(path,attempt_id=seed['attempt_id'])['call']['state']=='consumed'
assert immutable_intact(store)
results.append({'case':'real_old5db_candidate_same_semantics','status':'PASS','old_exact_design_digest':seed['old_exact_design_digest'],
 'cf_resolved_design_digest':actual_basis['design_digest'],'normalized_alternate_digest':normalized_digest,
 'candidate_unchanged':True,'request_and_original_objects_unchanged':True,'explicit_adopt_success':True,'new_calls':0})

for change in ('value','normalized_alternate_digest','foreign_request'):
 path,store=clone(change)
 if change=='value':
  replace_decision(path,store,{**seed['decision_value'],'replaces':seed['decision_ref'],'value':{'palette':'green'}})
 elif change=='normalized_alternate_digest':
  inject_candidate(store,lambda obj:obj['generation_basis'].update(design_digest=normalized_digest))
 else:
  foreign=store.read_object_json(seed['request_ref']);foreign['project_id']='foreign-project'
  foreign['request_id']='foreign-request-'+uuid.uuid4().hex
  models.validate_schema('generation_request',foreign)
  foreign_ref=store.put_json_object(foreign)
  inject_candidate(store,lambda obj:obj.update(request_ref=foreign_ref))
 pointer=store.read_current();doc=store.load_document();oldpages=copy.deepcopy(doc['pages']);oldusage=eligibility.allowance_usage(store,doc)['totals']
 try:candidates.plan(path,input=selection(doc))
 except Exception as exc:
  if change!='foreign_request':assert isinstance(exc,candidates.AdoptionConflict),type(exc)
  else:assert getattr(exc,'error_code',None)=='candidate_invalid'
  rejection={'type':type(exc).__name__,'code':getattr(exc,'error_code',None),'message':str(exc)}
 else:raise AssertionError('candidate accepted '+change)
 assert store.read_current()==pointer and store.load_document()['pages']==oldpages
 assert eligibility.allowance_usage(store,store.load_document())['totals']==oldusage
 assert immutable_intact(store)
 results.append({'case':change,'rejected':True,'rejection':rejection,'original_immutable_refs_unchanged':True,'no_adoption_or_fee_change':True})

result={'status':'PASS','evidence_kind':'cross-interpreter fixed actual old/new installed SDK; synthetic candidate content/controller/authority only',
 'old_source_sha':seed['old_source_sha'],'new_source_sha':'cf61e5e717fc852263b5a5baf4d97a07e126362b',
 'old_module':seed['module'],'new_module':deck_master.__file__,'cases':results,'real_image_calls':0,'real_project_writes':0}
(OUT/'cross-version-candidate-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
