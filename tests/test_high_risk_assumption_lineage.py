import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from conversation.brief_compiler import compile_deck_brief
from planning.claim_map import build_claim_map
from narrative.claim_graph import build_claim_evidence_graph


def test_high_risk_assumption_survives_brief_claim_graph_without_generic_support():
    statement = '现有接口可承载每秒一千次库存预占请求'
    assumption = {'assumption_id': 'capacity', 'statement': statement, 'fact_kind': 'working_assumption', 'risk_level': 'high', 'recheck_trigger': '取得实际接口压测记录，未通过则不启用自动预占'}
    extract = {'goal_decision': '是否批准旁路试点', 'audience': '运营与技术', 'current_state': '接口未确认', 'key_problems': ['工作假设：' + statement], 'constraints': ['不得中断交易'], 'non_goals': ['替换现有交易'], 'acceptance': ['接口验证通过'], 'working_assumptions': [assumption]}
    context = {'sources': [{'source_id': 'meeting', 'name': '会议纪要', 'kind': 'meeting', 'summary': '仅确认库存可视需求，尚未提供接口容量证据'}]}
    brief = compile_deck_brief({'run_id': 'risk-case'}, context, {}, extract)
    assert brief['working_assumptions'] == [assumption]
    claims = build_claim_map(brief, context)
    graph = build_claim_evidence_graph(claims, {}, context)
    claim = graph['claims'][0]
    assert claim['supporting_evidence'] == []
    assert claim['fact_kind'] == 'working_assumption'
    assert claim['support_status'] == 'unsupported'
    carried = next(a for a in graph['assumptions'] if a['assumption_id'] == 'capacity')
    assert carried['risk_level'] == 'high'
    assert carried['recheck_trigger'] == assumption['recheck_trigger']
    assert carried['statement'] == statement


def test_generic_source_candidates_do_not_become_supporting_evidence():
    brief = {'run_id': 'risk-case', 'core_points': ['库存准确率达到99%']}
    context = {'sources': [{'source_id': 'meeting', 'name': '会议纪要', 'summary': '只讨论会议日期'}]}
    graph = build_claim_evidence_graph(build_claim_map(brief, context), {}, context)
    assert graph['claims'][0]['supporting_evidence'] == []
    assert graph['claims'][0]['support_status'] == 'unsupported'
    assert graph['assumptions']
