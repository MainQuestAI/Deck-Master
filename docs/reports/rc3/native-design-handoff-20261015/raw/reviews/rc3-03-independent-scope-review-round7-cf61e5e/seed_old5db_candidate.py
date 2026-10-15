"""Create a disposable candidate with the genuine fixed old-5db install."""
from pathlib import Path
import hashlib,json,sys,uuid
import deck_master
from deck_master import collaboration,candidates,generation,production,models
from deck_master.native_image_evidence import NativeImageRuntime
OUT=Path(__file__).resolve().parent
sys.path.append('/workspace/work/rc3/reviews/env-03-snapshot-cf61e5e/lib/python3.12/site-packages')
sys.path.append('/workspace/work/rc3/reviews/rc3-03-code-snapshot-5dbdf72/tests/rebuild')
import test_rc3_native_visual_reuse as reuse
from test_rc3_design_workflows import confirmed,dispatch
from test_rc3_notes_visual_inputs import enf
from test_rc3_restyle_workflows import begin
assert 'candidate-03-5dbdf72' in deck_master.__file__
base=OUT/'old5db-candidate';base.mkdir(exist_ok=True)
path,store,grant=reuse._project(base)
value={'topic':'style','decision_id':'real-old-install-decision','subject_refs':[],
 'value':{'palette':'blue'},'disposition':'accepted','authority_mode':'direct_user',
 'scope':enf._scope(page_ids=['p1']),'instruction_evidence':enf._declared(store)}
record=collaboration.record_decision(path,input=value,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
recipe=confirmed(path,store);task=dispatch(path,store,recipe,['p1'])[0]
sent=begin(path,store,task)
with NativeImageRuntime(sent[3]).bound():
 context=reuse._issue(store,task,sent)
 assert reuse._settle(store,task,sent,context)['native_observation_status']=='accepted'
 candidate_id=reuse.accept(path,store,task,sent)['candidate_ids'][0]
shown=candidates.show(path,candidate_id=candidate_id)
request=store.read_object_json(sent[0]['request_ref']);resolved=request['input']['design_context']
old_digest=models.sha256_bytes(models.canonical_json_bytes(production.consumed_design(resolved)))
assert shown['candidate']['generation_basis']['design_digest']==old_digest
candidate_ref=next(ref for ref in store.load_document()['candidates'] if store.read_object_json(ref)['candidate_id']==candidate_id)
refs=[candidate_ref,sent[0]['request_ref'],record['decision_ref'],shown['candidate']['result_ref']]
seed={'evidence_kind':'actual old installed SDK; explicitly synthetic PNG/controller/authority, no actual model or image call',
 'old_source_sha':'5dbdf72089d6625449a23a52ef3e23859c597b4e','module':deck_master.__file__,
 'project':str(path),'candidate_id':candidate_id,'candidate_ref':candidate_ref,'candidate':shown['candidate'],
 'task_id':task['task_id'],'recipe_ref':recipe['recipe_ref'],'decision_value':value,'decision_ref':record['decision_ref'],
 'request_ref':sent[0]['request_ref'],'attempt_id':sent[1]['attempt_id'],'old_exact_design_digest':old_digest,
 'immutable_refs':[{'ref':ref,'bytes_sha256':hashlib.sha256(store.read_object_bytes(ref)).hexdigest()} for ref in refs]}
(OUT/'old5db-candidate-seed.json').write_text(json.dumps(seed,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'module':deck_master.__file__,'candidate_id':candidate_id,'exact_design_digest':old_digest}))
