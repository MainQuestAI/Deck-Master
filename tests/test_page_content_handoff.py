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

def test_source_references_are_design_provenance_not_fact_support(handoff):
    root,result=handoff
    submit_content(root,result)
    page=json.loads((root/'page_packages/P0.json').read_text())
    assert page['provenance']['source_refs']==['meeting']
    assert page['provenance']['fact_kind']=='design_suggestion'
    assert page['evidence_bindings']==[]
    assert page['internal_only']['evidence_state']=='design_basis'

def test_customer_fact_without_quote_is_rejected(handoff):
    root,result=handoff;result['pages'][0]['fact_kind']='customer_fact'
    with pytest.raises(ValueError,match='verified quote'):
        submit_content(root,result)

@pytest.mark.parametrize('tamper',[False,True])
def test_quote_returns_require_actual_bytes_and_locator(tmp_path,tamper):
    import hashlib
    raw=tmp_path.parent/(tmp_path.name+'-source.txt');raw.write_text('库存状态不可视。')
    source={'source_id':'s','path':str(raw),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
    for name,data in {'request':{'run_id':'r','run_mode':'production'},'context_manifest':{'sources':[source]},'narrative_plan':{'run_id':'r','beats':[{'beat_id':'P1','role':'problem'}]}}.items():
        (tmp_path/f'{name}.json').write_text(json.dumps(data))
    task=prepare_content(tmp_path);quote=raw.read_text()
    result={'schema_version':'deck_page_content_result.v1','run_id':'r','task_id':task['task_id'],'source_fingerprint':task['based_on']['input_fingerprint'],'evidence_quotes':[{'source_id':'s','evidence_id':'e1','quote':quote,'quote_sha256':hashlib.sha256(quote.encode()).hexdigest(),'source_position':{'unit_type':'character','start':1 if tamper else 0,'end':len(quote)}}],'pages':[{'page_id':'P1','page_title':'业务问题','conclusion':quote,'business_implication':'需要业务核实库存异常。','source_refs':['s'],'evidence_bindings':['s::e1'],'fact_kind':'customer_fact'}],'content_review':{'status':'approved_for_build','reviewer':'host','basis':'reviewed exact source statement'}}
    if tamper:
        with pytest.raises(ValueError,match='original source'):submit_content(tmp_path,result)
        assert not (tmp_path/'page_packages/index.json').exists()
    else:
        assert submit_content(tmp_path,result)['page_count']==1
        page=json.loads((tmp_path/'page_packages/P1.json').read_text())
        assert page['evidence_bindings']==['s::e1']
        assert page['internal_only']['evidence_state']=='referenced'
