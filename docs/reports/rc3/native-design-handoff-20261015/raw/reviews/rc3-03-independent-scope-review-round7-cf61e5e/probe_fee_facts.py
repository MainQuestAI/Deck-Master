"""Independent begin/change/settle assertions; synthetic controller, actual SDK ledger."""
from pathlib import Path
import copy,json,sys,uuid
import deck_master
from deck_master import collaboration,generation,eligibility,tasks,models
from deck_master.native_image_evidence import NativeImageRuntime
OUT=Path(__file__).resolve().parent
sys.path.append('/workspace/work/rc3/reviews/env-03-snapshot-cf61e5e/lib/python3.12/site-packages')
sys.path.append('/workspace/work/rc3/reviews/rc3-03-code-snapshot-cf61e5e/tests/rebuild')
import test_rc3_native_visual_reuse as reuse
from test_rc3_design_workflows import confirmed,dispatch
from test_rc3_notes_visual_inputs import enf
from test_rc3_restyle_workflows import begin
results=[]
for change,outcome in [('value','consumed'),('value','unknown'),('scope','consumed'),('scope','unknown'),('same','consumed')]:
 base=OUT/'fee-probes'/(change+'-'+outcome);base.mkdir(parents=True,exist_ok=True)
 path,store,_=reuse._project(base)
 value={'topic':'style','decision_id':'fee-stable-style','subject_refs':[],
  'value':{'palette':'blue'},'disposition':'accepted','authority_mode':'direct_user',
  'scope':enf._scope(page_ids=['p1']),'instruction_evidence':enf._declared(store)}
 old=collaboration.record_decision(path,input=value,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['decision_ref']
 recipe=confirmed(path,store);task=dispatch(path,store,recipe,['p1'])[0]
 sent=begin(path,store,task);request_bytes=store.read_object_bytes(sent[0]['request_ref'])
 original_pages=copy.deepcopy(store.load_document()['pages'])
 budget_before=eligibility.authorization_budget(store,store.load_document(),task['collaboration_binding']['authorization_ref'])
 with NativeImageRuntime(sent[3]).bound():
  proof=reuse._issue(store,task,sent)
  patch={**value,'replaces':old}
  if change=='value':patch['value']={'palette':'green'}
  elif change=='scope':patch['scope']=enf._scope(page_ids=['p2'])
  collaboration.record_decision(path,input=patch,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
  settled=reuse._settle(store,task,sent,proof,outcome=outcome)
 doc=store.load_document();actual=tasks._lookup_task(doc,task['task_id'],store)
 call=generation.show(path,attempt_id=sent[1]['attempt_id'])['call']
 budget_after=eligibility.authorization_budget(store,doc,task['collaboration_binding']['authorization_ref'])
 assert call['state']==outcome
 assert {key:budget_after[key] for key in ('ceiling','used','remaining')}=={key:budget_before[key] for key in ('ceiling','used','remaining')}
 assert budget_after['state']==('unknown' if outcome=='unknown' else 'available')
 assert len(actual['call_allowances'])==len(actual['generation_attempts'])==1
 assert actual['usage']=={'source':'not_reported','external_calls':None}
 assert doc['pages']==original_pages and store.read_object_bytes(sent[0]['request_ref'])==request_bytes
 assert settled['native_observation_status']==('accepted' if change=='same' else 'rejected')
 if change=='same':
  candidate=reuse.accept(path,store,task,sent)['candidate_ids'][0]
  assert candidate and not store.load_document().get('candidate_adoptions')
  rejected=False
 else:
  pointer=store.read_current()
  try:reuse.accept(path,store,task,sent)
  except (eligibility.EligibilityBlocked,tasks.TaskConflict,generation.GenerationError):rejected=True
  else:raise AssertionError('late changed decision result accepted')
  assert store.load_document()['pages']==original_pages and not store.load_document().get('candidates')
 results.append({'change':change,'outcome':outcome,'native_observation':settled['native_observation_status'],
  'call_state':call['state'],'used':budget_after['used'],'remaining':budget_after['remaining'],
  'budget_state':budget_after['state'],'late_result_rejected':rejected,'new_allowances':0,
  'frozen_request_unchanged':True,'current_pages_unchanged':True,'actual_image_calls':0})
(OUT/'independent-fee-facts.json').write_text(json.dumps({'status':'PASS','cases':results,
 'evidence_kind':'synthetic native/authority fixtures, actual installed begin/settle/accept and ledger; no real image'},indent=2)+'\n')
print(json.dumps({'status':'PASS','cases':len(results),'charged_facts_preserved':True}))
