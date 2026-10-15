"""Reproduce audit-only design decision version invalidation via installed SDK."""
import copy
import json
from pathlib import Path
import sys
import uuid
import deck_master
from deck_master import collaboration, production, tasks

OUT = Path(__file__).resolve().parent
sys.path.append('/workspace/Deck-Master/.venv/lib/python3.12/site-packages')
sys.path.append('/workspace/work/rc3/reviews/rc3-03-code-snapshot-5dbdf72/tests/rebuild')
from test_rc3_design_workflows import project, confirmed, dispatch
from test_rc3_notes_visual_inputs import enf

base=OUT/('decision-audit-ref-probe-'+uuid.uuid4().hex[:8])
base.mkdir(exist_ok=True)
path,store,grant=project(base)
value={'topic':'style','decision_id':'audit-stable-style','subject_refs':[],
 'value':{'palette':'blue'},'disposition':'accepted','authority_mode':'direct_user',
 'scope':enf._scope(page_ids=['p1']),'instruction_evidence':enf._declared(store)}
recorded=collaboration.record_decision(path,input=value,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
old_ref=recorded['decision_ref']
recipe=confirmed(path,store)
task=dispatch(path,store,recipe,['p1'])[0]
before=store.load_document()
old=production.resolve_generation_design(store,before,before['pages'][0],recipe_ref=recipe['recipe_ref'])
assert tasks.task_inputs_current(store,before,task)
replacement={**copy.deepcopy(value),'replaces':old_ref}
recorded2=collaboration.record_decision(path,input=replacement,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
after=store.load_document()
public_error=None
try:
 new=production.resolve_generation_design(store,after,after['pages'][0],recipe_ref=recipe['recipe_ref'])
except Exception as exc:
 public_error={'type':type(exc).__name__,'message':str(exc)}
# A read-only contrast removes only historical decision refs from the resolver
# view. This isolates the second issue; it does not modify the real project or
# imply that public production succeeded after the legal decision replacement.
head_only=copy.deepcopy(after)
head_only['collaboration']['decisions']=[recorded2['decision_ref']]
new=production.resolve_generation_design(store,head_only,head_only['pages'][0],recipe_ref=recipe['recipe_ref'])
old_semantic=old['content_basis']['consumed']['decision_slices'][0]['sha256']
new_semantic=new['content_basis']['consumed']['decision_slices'][0]['sha256']
assert old_semantic==new_semantic
assert old['content_requirements']==new['content_requirements']
assert {k:v for k,v in old.items() if k!='content_basis'}=={k:v for k,v in new.items() if k!='content_basis'}
result={'status':'CONFIRMED_PRODUCT_GAP','evidence_kind':'synthetic authority fixture, actual installed public SDK; zero external calls',
 'project':str(path),'task_id':task['task_id'],'source_sha':'5dbdf72089d6625449a23a52ef3e23859c597b4e',
 'old_decision_ref':old_ref,'new_decision_ref':recorded2['decision_ref'],
 'same_effective_decision_slice_sha256':old_semantic,
 'same_page':before['pages'][0]['page']==after['pages'][0]['page'],
 'same_content_requirements':True,'same_actual_projected_design':True,
 'public_generation_resolver_error':public_error,
 'head_only_readonly_contrast_used_for_consumed_design':True,
 'same_consumed_design':production.consumed_design(old)==production.consumed_design(new),
 'old_task_still_current':tasks.task_inputs_current(store,after,task),
 'expected':'same consumed design and task current; exact Refs remain historical audit evidence',
 'actual':'Public legal decision replacement leaves historical refs that block generation resolver. Separately, head-only read-only contrast still leaks decision_ref into consumed_design despite equal registered effective slice.',
 'files':{'before':str(OUT/'decision-audit-ref-before.json'),'after':str(OUT/'decision-audit-ref-after.json')}}
(OUT/'decision-audit-ref-before.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
(OUT/'decision-audit-ref-after.json').write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n')
(OUT/'decision-audit-ref-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
assert public_error is not None and not result['same_consumed_design']
