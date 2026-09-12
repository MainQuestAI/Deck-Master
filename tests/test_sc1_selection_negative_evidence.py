"""Counterexamples for user choices, negative answers and evidence collisions."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
import pytest
from test_sc1_solution_narrative import _request, _solution_model_healthcare
from planning.narrative_planner import plan_narrative
from workflow.questions import QuestionResolver
from workflow.decisions import DecisionLog
from narrative.claim_graph import build_claim_evidence_graph

CANDIDATES = [{'candidate_id':'A','title':'Pilot','recommended':True,'recommendation_reason':'Lower risk'}, {'candidate_id':'B','title':'All sites','why_rejected':'Higher cost'}]

def plan(**kwargs):
    return plan_narrative(_request(), planner_mode='production_narrative', solution_model=_solution_model_healthcare(), narrative_candidates=CANDIDATES, **kwargs)

def test_recommendation_is_not_selection():
    result = plan()
    assert result['recommended_candidate_id'] == 'A'
    assert result['selected_candidate_id'] is None
    assert any(g['field'] == 'narrative_selection' for g in result['gaps'])

def test_explicit_selection_survives_and_does_not_reask():
    result = plan(selected_candidate_id='B', selection_decision_ref='workflow/decision_log.jsonl#decision_1')
    assert result['selected_candidate_id'] == 'B'
    assert result['selection_decision_ref'].endswith('decision_1')
    assert not any(g['field'] == 'narrative_selection' for g in result['gaps'])

@pytest.mark.parametrize('selected,ref', [('B',''),('missing','workflow/decision_log.jsonl#decision_1')])
def test_unbound_or_invalid_selection_rejected(selected,ref):
    with pytest.raises(ValueError):
        plan(selected_candidate_id=selected, selection_decision_ref=ref)

@pytest.mark.parametrize('answer', ['没有','否','no',False])
def test_semantic_boolean_negative_answer_completes_question(tmp_path, answer):
    qr=QuestionResolver();fp=qr.input_fingerprint(qr.registry.contract('deck-init'),tmp_path)
    DecisionLog().record(tmp_path,run_id='test',stage_id='deck-init',question_id='init.customer_visible_forbidden',answer=answer,actor={'id':'test','role':'approver'},required=False,input_fingerprint=fp)
    assert not any(g.question_id=='init.customer_visible_forbidden' for g in qr.gaps(tmp_path,'deck-init',include_optional=True))

def test_open_question_still_rejects_contentless_no(tmp_path):
    qr=QuestionResolver();fp=qr.input_fingerprint(qr.registry.contract('deck-init'),tmp_path)
    DecisionLog().record(tmp_path,run_id='test',stage_id='deck-init',question_id='init.scan_scope',answer='没有',actor={'id':'test','role':'approver'},required=True,input_fingerprint=fp)
    assert next(g for g in qr.gaps(tmp_path,'deck-init') if g.question_id=='init.scan_scope').answer_status=='needs_follow_up'

def graph(ref):
    sources=[{'source_id':sid,'evidence_candidates':[{'evidence_id':'E001','quote_or_excerpt':sid+' evidence'}]} for sid in ['source_a','source_b']]
    return build_claim_evidence_graph({'claims':[{'claim_id':'C1','claim':'Customer fact','evidence_refs':[ref]}]}, {'tasks':[]}, {'sources':sources})

def test_ambiguous_legacy_evidence_does_not_choose_last_source():
    result=graph('E001')
    assert result['claims'][0]['supporting_evidence']==[]
    assert any(g.get('reason')=='ambiguous_evidence_ref' for g in result['gaps'])
    assert len([e for e in result['evidence'] if e.get('candidate_id')=='E001'])==2

def test_source_qualified_evidence_selects_exact_candidate():
    result=graph('source_a::E001')
    ids=result['claims'][0]['supporting_evidence']
    assert len(ids)==1
    evidence=next(e for e in result['evidence'] if e['evidence_id']==ids[0])
    assert evidence['source_ref']=='source_a'
    assert evidence['candidate_id']=='E001'


def test_replanning_preserves_request_recorded_selection():
    request = _request(selected_candidate_id='B', selection_decision_ref='workflow/decision_log.jsonl#prior')
    result = plan_narrative(request, planner_mode='production_narrative', solution_model=_solution_model_healthcare(), narrative_candidates=CANDIDATES)
    assert result['selected_candidate_id'] == 'B'
    assert result['selection_decision_ref'].endswith('#prior')
    assert not any(g['field']=='narrative_selection' for g in result['gaps'])


def test_typed_boolean_does_not_require_chinese_prompt():
    qr=QuestionResolver()
    assert qr._is_vague_answer('no', question={'prompt':'Excluded?', 'answer_schema':{'type':'boolean'}}) is False
    assert qr._is_vague_answer('unknown', question={'answer_schema':{'type':'boolean'}}) is True
