"""New-reader-only requalification of existing actual p04; never a project writer."""
from pathlib import Path
import hashlib,json
import deck_master
from deck_master import editing,production,service,tasks
from deck_master.store import Store
from deck_master.capabilities import installation_identity

OUT=Path(__file__).resolve().parent
PILOT=Path('/workspace/work/rc3/native-image-pilot-03')
PROJECT=PILOT/'run-02-project'
OLD_AUDIT=Path('/workspace/work/rc3/reviews/rc3-03-independent-scope-audit-5dbdf72')
oldcheck=json.loads((OLD_AUDIT/'actual-native-file-check.json').read_text())
retained=[{'path':item['path'],'sha256':hashlib.sha256(Path(item['path']).read_bytes()).hexdigest(),
 'expected_sha256':item['sha256']} for item in oldcheck['files']]
assert all(item['sha256']==item['expected_sha256'] for item in retained)
store=Store(PROJECT)
pointer_before=store.read_current()
revision=store.current_revision_id()
doc=store.load_document(revision)
assert doc['revision_id']==revision
entry=next(item for item in doc['pages'] if item['page_id']=='p04')
original_workorder=json.loads((PILOT/'run-02-reconstruction-5dbdf72/workorder.json').read_text())
old_context=original_workorder['page_design_contexts']['p04']
context=production.resolve_page_design(store,doc,entry,require_current=True)
assert context==old_context
artifact=store.read_object_json(entry['blueprint'])
request_ref=artifact['provenance']['generation_request']
request_bytes=store.read_object_bytes(request_ref)
request=json.loads(request_bytes)
assert request['input']['design_context']==context
assert artifact['file']['sha256']=='8cf79c6ada8476c72ebc13f822821a6e02d5ffa7215bfad1984c74fd52eb147c'
digests=editing._current_artifact_digests(store,doc)
visual_tasks=[]
for ref in doc['tasks']:
 task=store.read_object_json(ref)
 if task.get('review_stage')=='page_visual' and 'p04' in task.get('scope_pages',[]):
  record={'task_id':task['task_id'],'status':task['status'],'dispatch_revision':task.get('dispatch_revision'),
   'inputs_current':tasks.task_inputs_current(store,doc,task),'required_capabilities':task.get('required_capabilities')}
  if task['status'] in ('awaiting_host','running'):
   summary=service.task_summary(store,doc,task)
   assert summary['page_design_contexts']['p04']==old_context
   assert record['inputs_current']
   record['page_visual_requirements']=summary['page_visual_requirements']
   record['work_order_context_status']=summary['project_context']['context_status']
  visual_tasks.append(record)
status=editing.page_visual_summary(store,doc,entry)
reviews=[]
from deck_master.review import dependency_problems
for ref in doc['reviews']:
 review=store.read_object_json(ref)
 if review.get('review_stage')=='page_visual' and any(subject in review.get('subjects',[]) for subject in (entry.get('blueprint'),entry.get('svg'),entry.get('svg_preview')) if subject):
  problems=dependency_problems(review,digests)
  reviews.append({'ref':ref,'kind':review['kind'],'status':review['status'],'dependency_problems':problems})
  assert not problems
assert store.read_object_bytes(request_ref)==request_bytes
assert all(hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256'] for item in retained)
result={'status':'PASS_FOR_READ_ONLY_F9_REQUALIFICATION','reader_source_sha':'cf61e5e717fc852263b5a5baf4d97a07e126362b',
 'reader_identity':installation_identity(),'project':str(PROJECT),'selected_fixed_revision':revision,
 'reader_did_not_claim_settle_accept_or_write':True,'pointer_unchanged_during_read':store.read_current()==pointer_before,
 'exact_old_frozen_context_retained':True,'request_ref':request_ref,'request_bytes_sha256':hashlib.sha256(request_bytes).hexdigest(),
 'actual_image_origin_source_sha':'8057905162f20926cfc1a0a96252bc6745f4e700',
 'actual_image_origin_did_not_change':True,'old_reconstruction_method_release':original_workorder['method_release'],
 'visual_tasks':visual_tasks,'page_visual_current_summary':status,'review_dependencies_checked':reviews,
 'retained_actual_files':retained,'phase_note':'This is cf reader requalification of old 805 image and 5db reconstruction, not a new model run, native compile/render or review submission.',
 'limitations':['No F05 physical-canvas conclusion.','No new independent page_visual or human verdict.','No E2/E3 or whole-deck acceptance.']}
(OUT/'actual-p04-readonly-requalification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ('status','selected_fixed_revision','exact_old_frozen_context_retained','pointer_unchanged_during_read','visual_tasks','review_dependencies_checked')},ensure_ascii=False,indent=2))
