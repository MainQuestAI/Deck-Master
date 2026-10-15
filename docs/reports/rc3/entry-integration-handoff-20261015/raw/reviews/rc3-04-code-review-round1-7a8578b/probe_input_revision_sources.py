"""A syntactically valid, nonexistent source link through actual v2 adoption."""
from copy import deepcopy
import json
from pathlib import Path
import uuid
from deck_master import content_production, service
from deck_master.store import Store

OUT=Path(__file__).resolve().parent
project=OUT/'probe-input-revision-source-project'
def op(): return str(uuid.uuid4())
page={'schema_version':'deck_page_package.v2','page_id':'p1',
 'customer_visible':{'title':'Fixed imported manuscript','body_blocks':[]},
 'visual_spec':{'intent':'synthetic L1 source validation','reference_mode':'new_design'}}
service.create(project,brief='Retain the manuscript source and revise p1 copy only.',draft={'pages':[page]})
store=Store(project)
doc=store.load_document()
task=content_production.open_phase_task(store,doc,operation_id=op(),intent='input_revision',
 page_ids=['p1'],adoption_policy='within_scope')
service.task_start(project,task_id=task['task_id'],execution_ref='synthetic-L1-independent-probe-author',
 supported_protocols=[task['protocol_version']],capabilities=task['required_capabilities'])
before=store.load_document()
changed=deepcopy(store.read_object_json(before['pages'][0]['page']))
changed['customer_visible']['title']='Revised copy citing a source that does not exist in this project'
fake={'source_id':'nonexistent-source','source_version':{'original_sha256':'0'*64,
 'extract':{'path':'.deckmaster/objects/00/'+'0'*64+'.json','sha256':'0'*64}},'locator':'L999'}
changed['content_mapping']['visible_links'][0]['source_links']=[fake]
proposed=store.put_json_object(changed)
payload={'changed_layers':['page_copy'],'proposals':[{'layer':'page_copy','ref':proposed}],
 'diff':{'input_digest':task['input_digest'],'summary':'Explicit p1-only synthetic content revision',
 'changed_page_ids':['p1']}}
envelope={'schema_version':'compose_result.v2','kind':'compose','variant':'input_revision',
 'task_id':task['task_id'],'operation_id':task['operation_id'],'produced_against':task['produced_against'],
 'eligibility_digest':task['collaboration_binding']['eligibility_digest'],'payload':payload,'usage_events':[]}
try:
 response=service.accept_result(project,task_id=task['task_id'],operation_id=task['operation_id'],
  produced_against=task['produced_against'],result_payload=envelope)
 error=None
except Exception as exc:
 response=None;error={'type':type(exc).__name__,'message':str(exc)}
after=store.load_document()
actual=store.read_object_json(after['pages'][0]['page'])
result={'evidence_level':'L1_SYNTHETIC','task':task,'before':before,'input':envelope,
 'response':response,'error':error,'after':after,'actual_page':actual,
 'invalid_source_adopted':actual['content_mapping']['visible_links'][0]['source_links']==[fake],
 'source_ids':[row['source_id'] for row in after['sources']]}
(OUT/'probe-input-revision-source-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('error','invalid_source_adopted','source_ids')},ensure_ascii=False))
