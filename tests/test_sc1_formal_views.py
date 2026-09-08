import copy,json
import pytest
from planning.solution_model import build_solution_model
from production.diagram_views import build_diagram_view,validate_diagram_view,impact_of_component_change
from jsonschema import Draft202012Validator
from native_pptx.contracts import SCHEMA_DIR


def design():
 return dict(model_id='retail',revision=1,decision_object='试点旁路库存可见性',problems=[dict(id='p_stock',statement='库存事实分散',evidence_refs=['sources/raw.txt'],impact='异常定位困难')],capabilities=[dict(id='c_visible',name='库存可见',problem_refs=['p_stock'],mechanism='同步库存事件并核对来源与时间',actors=['运营'],inputs=['库存事件'],outputs=['库存事实'],owner='运营',acceptance=['事件可追溯'])],components=[dict(id=i,name=n,status='proposed',responsibility=n,requirement_refs=['p_stock'],evidence_refs=[],rationale='旁路试点建议') for i,n in [('ingest','库存接入'),('service','库存服务'),('audit','独立审计')]],relations=[dict(id='r_data',from_id='ingest',to_id='service',type='data_flow',status='proposed',payload='库存事件',evidence_refs=[],rationale='汇总库存')],implementation_phases=[dict(id='phase1',name='接入试点',component_refs=['ingest','service'],depends_on=[],deliverables=['可追溯事件'],acceptance=['不中断交易'],owner='运营'),dict(id='phase2',name='独立审计',component_refs=['audit'],depends_on=[],deliverables=['审计记录'],acceptance=['记录可追溯'],owner='审计')],alternatives=[dict(id='a1',name='旁路接入',approach='保留交易链路',tradeoffs=['需对账'],rationale='不中断交易'),dict(id='a2',name='同步替换',approach='替换交易链路',tradeoffs=['切换风险'],rationale='不建议首期采用')],recommended_alternative_id='a1',single_viable_reason='',assumptions=[])


def formal(tmp_path):
 (tmp_path/'sources').mkdir(exist_ok=True);(tmp_path/'sources/raw.txt').write_text('合成零售输入：库存分散，试点不中断交易。')
 (tmp_path/'request.json').write_text(json.dumps({'run_id':tmp_path.name,'run_mode':'production'}))
 return build_solution_model(tmp_path,design(),source_refs=['sources/raw.txt'])


def view(model,kind='data_flow'):
 return build_diagram_view(view_id='v_'+kind,view_type=kind,solution_model=model,target_page_id='P004',nodes=[{'id':'n1','model_refs':['ingest'],'label':'库存接入','aggregation_reason':''},{'id':'n2','model_refs':['service'],'label':'库存服务','aggregation_reason':''}],edges=[{'id':'e1','from_node_id':'n1','to_node_id':'n2','relation_ref':'r_data','label':'库存事件'}])


def test_formal_model_and_four_views_are_schema_valid(tmp_path):
 m=formal(tmp_path);Draft202012Validator(json.loads((SCHEMA_DIR/'solution-model.v1.schema.json').read_text())).validate(m)
 for kind in ['business_architecture','application_architecture','data_flow','implementation_roadmap']:
  v=view(m,kind);Draft202012Validator(json.loads((SCHEMA_DIR/'diagram-view.v1.schema.json').read_text())).validate(v)
  assert not validate_diagram_view(v,solution_model=m)


def test_direction_and_aggregation_and_unknown_refs_rejected(tmp_path):
 m=formal(tmp_path);v=view(m)
 v['edges'][0]['from_node_id']='n2';v['edges'][0]['to_node_id']='n1'
 assert any('direction' in x for x in validate_diagram_view(v,solution_model=m))
 v=view(m);v['nodes'][0]['model_refs']=['ingest','audit']
 assert any('aggregation' in x for x in validate_diagram_view(v,solution_model=m))
 v=view(m);v['nodes'][0]['model_refs']=['ghost']
 assert any('does not exist' in x for x in validate_diagram_view(v,solution_model=m))


def test_in_place_change_impacts_related_text_views_and_phases(tmp_path):
 m=formal(tmp_path);changed=copy.deepcopy(m);changed['components'][1]['responsibility']='计算可售量并保留预占'
 v=view(m);other=copy.deepcopy(v);other.update(view_id='v_other',page_id='P010');other['nodes']=[{'id':'n3','model_refs':['audit']}];other['edges']=[]
 result=impact_of_component_change(m,changed,[v,other],narrative_plan={'beats':[{'beat_id':'P006','required_components':['service']},{'beat_id':'P010','required_components':['audit']}]})
 assert result['changed_components']==['service']
 assert result['affected_page_ids']==['P004','P006']
 assert result['affected_phase_ids']==['phase1']
 changed=copy.deepcopy(m);changed['relations'][0]['payload']='带来源与时序的库存事件'
 assert 'v_data_flow' in impact_of_component_change(m,changed,[v])['affected_views']


def test_model_rejects_broken_refs_and_missing_source(tmp_path):
 m=formal(tmp_path);payload=design();payload['relations'][0]['to_id']='ghost'
 with pytest.raises(ValueError,match='ghost'):build_solution_model(tmp_path,payload,source_refs=['sources/raw.txt'])
 with pytest.raises(ValueError,match='source'):build_solution_model(tmp_path,design(),source_refs=['sources/missing.txt'])
