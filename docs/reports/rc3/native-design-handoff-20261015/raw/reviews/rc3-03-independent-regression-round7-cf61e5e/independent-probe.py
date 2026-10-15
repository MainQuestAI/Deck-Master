"""F9 independent public replacement/adoption path; isolated synthetic L1 only."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid

import deck_master
from deck_master import candidates,collaboration,content_review,generation,production,service,tasks
from deck_master.models import canonical_json_bytes,content_identity,sha256_bytes
from deck_master.native_image_evidence import NativeImageRuntime
SNAP=Path('/workspace/work/rc3/reviews/rc3-03-code-snapshot-cf61e5e')
assert Path(deck_master.__file__).is_relative_to(SNAP/'src')
sys.path.insert(0,str(SNAP/'tests/rebuild'))
import test_rc3_native_visual_reuse as helper
from test_rc3_design_workflows import confirmed,dispatch
from test_rc3_restyle_workflows import begin,edit
from test_rc3_notes_visual_inputs import enf
OUT=Path(__file__).parent
path,store,_=helper._project(OUT/'public-replacement-project')
rows=[]

def record(name,**facts):
    rows.append({'name':name,'status':'PASS',**facts})
    (OUT/'independent-probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(name,'PASS',flush=True)

def decide(value):
    return collaboration.record_decision(path,input=value,base_revision=store.current_revision_id(),
        operation_id=str(uuid.uuid4()))['decision_ref']

value={'topic':'style','decision_id':'independent-r7-style','subject_refs':[],
    'value':{'palette':'blue','contrast':'medium'},'disposition':'accepted','authority_mode':'direct_user',
    'scope':enf._scope(page_ids=['p1']),'instruction_evidence':enf._declared(store)}
original_ref=decide(value)
recipe=confirmed(path,store)
task=dispatch(path,store,recipe,['p1'])[0]
doc=store.load_document()
original=production.resolve_generation_design(store,doc,doc['pages'][0],recipe_ref=recipe['recipe_ref'])
identity=content_identity(doc)
same_ref=decide({**value,'replaces':original_ref})
doc=store.load_document()
actual=production.resolve_generation_design(store,doc,doc['pages'][0],recipe_ref=recipe['recipe_ref'])
assert actual['content_basis']['decision_refs']==[same_ref]
assert original['content_basis']['decision_refs']==[original_ref]
assert production.consumed_design(original,store=store)==production.consumed_design(actual,store=store)
assert content_identity(doc)==identity and tasks.task_inputs_current(store,doc,task)
record('public_same_identity_replacement_keeps_one_real_head',old_ref=original_ref,new_ref=same_ref,
    manuscript_identity_unchanged=True,full_consumed_design_equal=True)

sent=begin(path,store,task)
frozen,attempt,_,registry=sent
frozen_bytes=store.read_object_bytes(frozen['request_ref'])
with NativeImageRuntime(registry).bound():
    context=helper._issue(store,task,sent)
    assert helper._settle(store,task,sent,context)['native_observation_status']=='accepted'
candidate_id=helper.accept(path,store,task,sent)['candidate_ids'][0]
candidate_before=candidates.show(path,candidate_id=candidate_id)['candidate']
third_ref=decide({**value,'replaces':same_ref})
state=candidates.show(path,candidate_id=candidate_id)
assert state['generation_basis']['status']=='current' and state['candidate']==candidate_before
doc=store.load_document()
plan=candidates.plan(path,input={'schema_version':'candidate_selection.v1','project_id':doc['project_id'],
    'base_revision':doc['revision_id'],'candidate_ids':[candidate_id]})['plan']
candidates.adopt(path,input=plan,base_revision=plan['base_revision'],operation_id=str(uuid.uuid4()))
doc=store.load_document()
assert doc['pages'][0]['blueprint']==candidate_before['result_ref']
assert candidates.show(path,candidate_id=candidate_id)['candidate']==candidate_before
assert store.read_object_bytes(frozen['request_ref'])==frozen_bytes
record('audit_replacement_then_explicit_candidate_plan_and_adopt',third_ref=third_ref,
    exact_original_design_digest=candidate_before['generation_basis']['design_digest'],candidate_bytes_unchanged=True,
    old_frozen_request_bytes_unchanged=True,external_tools_called=0)

reconstruct=service.open_host_task(store,kind='reconstruct',page_ids=['p1'],
    instruction='Independent reconstruct exact adopted image after audit replacements',base_revision=store.current_revision_id())
before=store.load_document()
assert service.task_summary(store,before,reconstruct)['page_design_contexts']['p1']==frozen['input']['design_context']
before_identity=content_identity(before)
changed_ref=decide({**value,'value':{'palette':'green','contrast':'medium'},'replaces':third_ref})
after=store.load_document()
assert content_identity(after)==before_identity
assert not tasks.task_inputs_current(store,after,reconstruct)
try:
    production.resolve_page_design(store,after,after['pages'][0],require_current=True)
except Exception as exc:
    refusal={'type':type(exc).__name__,'message':str(exc)}
else:
    raise AssertionError('An actual Decision value change revived the adopted frozen image')
assert 'consumed Page/Plan/design inputs changed' in refusal['message']
record('real_value_change_rejected_despite_same_manuscript_identity',new_ref=changed_ref,
    same_manuscript_identity=True,stale_reconstruct=True,refusal=refusal)

# A full context difference cannot reuse the old candidate digest encoding.
mutated=copy.deepcopy(actual)
mutated['recipe_parameters']['density']='Different actual execution density; not an audit change'
encoded=candidates._recorded_design_basis(store,mutated,actual)
old_encoded=candidates._recorded_design_basis(store,actual,actual)
assert encoded!=old_encoded
assert sha256_bytes(canonical_json_bytes(encoded))!=sha256_bytes(canonical_json_bytes(old_encoded))
assert encoded['recipe_parameters']['density']==mutated['recipe_parameters']['density']
record('candidate_digest_compatibility_requires_full_semantic_equality',
    altered_full_context_cannot_reuse_old_encoding=True,arbitrary_second_digest_not_accepted=True,
    boundary='Read-only isolated helper contrast; no fabricated candidate or production permission.')

edit(path,store,'p1',lambda page:page['customer_visible'].update(title='实际正文修订仍需独立于旧图重新核稿'))
helper._fidelity_review(path,store)
doc=store.load_document()
assert content_review.qualify_for_production(store,doc)['allowed'] is True
assert not tasks.task_inputs_current(store,doc,reconstruct)
closed=tasks._lookup_task(doc,task['task_id'],store)
assert len(closed['call_allowances'])==1 and closed['call_allowances'][0]['state']=='consumed'
assert generation.show(path,attempt_id=attempt['attempt_id'])['call']['state']=='consumed'
assert sum(len(store.read_object_json(ref).get('call_allowances') or []) for ref in doc['tasks'])==1
assert store.read_object_bytes(frozen['request_ref'])==frozen_bytes
record('current_body_requalification_not_blocked_by_old_image',
    honest_host_self_fidelity_requalified=True,old_visual_task_still_stale=True,
    original_consumed_allowance_preserved=True,total_allowances=1,actual_image_tools_called=0)
