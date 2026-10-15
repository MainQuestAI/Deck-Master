"""Same original instruction replay after another request; public services."""
from copy import deepcopy
import json
from pathlib import Path
import uuid
from deck_master import collaboration, collaboration_budget, service
from deck_master.store import Store

OUT = Path(__file__).resolve().parent
project = OUT / 'probe-source-replay-project'
def op(): return str(uuid.uuid4())
service.create(project, brief='One original bounded work request; no new production instruction.')
store = Store(project)
doc = store.load_document()
original = deepcopy(doc['collaboration']['request'])
source_input = {k: deepcopy(original[k]) for k in ('intent','content_intent','scope','instruction_evidence','variant')}
source_input['instruction_evidence'].pop('assurance', None)
alternate = deepcopy(source_input)
alternate['instruction_evidence'] = {'kind':'host_attested_instruction','text':'Pause production and inspect current material only.', 'source_locator':'independent-review:alternate-request'}
alternate['intent']='review_only'
alternate['scope']['layers']=['review']
alternate['replace_request_id']=original['request_id']
second = collaboration.start_request(project,input=alternate,base_revision=doc['revision_id'],operation_id=op())
middle=store.load_document()
source_input['replace_request_id']=middle['collaboration']['request']['request_id']
third=collaboration.start_request(project,input=source_input,base_revision=middle['revision_id'],operation_id=op())
after=store.load_document()
current=after['collaboration']['request']
old_credit=collaboration_budget.initial_per_page_plan(store,after,request_id=original['request_id'],page_ids=['p1'])['credits']
new_credit=collaboration_budget.initial_per_page_plan(store,after,request_id=current['request_id'],page_ids=['p1'])['credits']
result={'evidence_level':'L1_SYNTHETIC','original_request':original,'middle':middle,'response':third,'after':after,
 'same_source_key':collaboration._request_source_key(original)==collaboration._request_source_key(current),
 'original_request_id':original['request_id'],'current_request_id':current['request_id'],
 'request_recreated':original['request_id']!=current['request_id'],'original_credit':old_credit,'new_credit':new_credit,
 'note':'Credit planner is pure; no image calls or actual consumed-credit claim is made.'}
(OUT/'probe-request-source-replay-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('same_source_key','original_request_id','current_request_id','request_recreated','original_credit','new_credit')},ensure_ascii=False))
