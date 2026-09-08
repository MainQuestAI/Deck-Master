import copy
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from production.content_handoff import prepare_content,submit_content,content_continuation

@pytest.fixture
def handoff(tmp_path):
    for name,data in {'request':{'run_id':'retail','run_mode':'production'},'context_manifest':{'sources':[{'source_id':'meeting'}]},'narrative_plan':{'run_id':'retail','beats':[{'beat_id':f'P{i}','role':'solution','content_goal':'分析库存异常的责任安排'} for i in range(2)]}}.items():
        (tmp_path/f'{name}.json').write_text(json.dumps(data))
    task=prepare_content(tmp_path)
    result={'schema_version':'deck_page_content_result.v1','run_id':'retail','task_id':task['task_id'],'source_fingerprint':task['based_on']['input_fingerprint'],'pages':[{'page_id':p,'page_title':'库存协同','conclusion':'建议先建立库存异常可见性。','business_implication':'门店运营负责复核异常，交易流程保持可用。','evidence_refs':['meeting'],'fact_kind':'design_suggestion'} for p in task['page_ids']],'content_review':{'status':'approved_for_build','reviewer':'test reviewer','basis':'reviewed source bindings and finished text'}}
    return tmp_path,result

@pytest.mark.parametrize('bad',['order','missing','review','source','number','fingerprint'])
def test_invalid_return_never_writes_packages(handoff,bad):
    root,result=handoff
    if bad=='order':result['pages'].reverse()
    if bad=='missing':result['pages'].pop()
    if bad=='review':result.pop('content_review')
    if bad=='source':result['pages'][0]['evidence_refs']=['invented']
    if bad=='number':result['pages'][0]['conclusion']='库存周转提升30%。'
    if bad=='fingerprint':result['source_fingerprint']='old'
    with pytest.raises(ValueError):submit_content(root,result)
    assert not (root/'page_packages/index.json').exists()
    assert content_continuation(root)['host_task']['kind']=='page_content'

def test_complete_source_bound_content_is_atomic_and_replayable(handoff):
    root,result=handoff
    output=submit_content(root,result)
    assert output['page_count']==2 and not output['delivery_approved']
    assert content_continuation(root) is None
    assert prepare_content(root)['status']=='content_ready'
    assert submit_content(root,copy.deepcopy(result))['status']=='already_applied'
    assert len(list((root/'page_packages').glob('P*.json')))==2

def test_production_content_cannot_be_downgraded(handoff):
    root,result=handoff
    request=json.loads((root/'request.json').read_text())
    request.update(origin_run_mode='production',run_mode='fixture')
    (root/'request.json').write_text(json.dumps(request))
    for operation in (lambda:prepare_content(root),lambda:submit_content(root,result)):
        with pytest.raises(ValueError,match='RUN_MODE_CONFLICT'):
            operation()
    assert not (root/'page_packages/index.json').exists()
