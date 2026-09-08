import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pytest
from conversation.brief_compiler import compile_deck_brief
from planning.claim_map import build_claim_map

def inputs(tmp_path):
    sources=[]
    for sid,text in [('early','Use a cloud database.'),('revision','Use the local database. This replaces the earlier cloud requirement.')]:
        p=tmp_path/(sid+'.txt');p.write_text(text)
        sources.append({'source_id':sid,'kind':'customer_material','origin_ref':p.name,'file_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'evidence_candidates':[{'evidence_id':'E1','quote':text,'quote_sha256':hashlib.sha256(text.encode()).hexdigest(),'source_position':{'unit_type':'line','start':1,'end':1}}]})
    conflict={'conflict_id':'db','description':'Cloud and local are mutually exclusive','evidence_refs':['early::E1','revision::E1'],'status':'open','resolution':'','decision_ref':''}
    context={'sources':sources,'conflicts':[conflict]}
    extract={'goal_decision':'Choose pilot deployment','audience':'Board','current_state':'Two statements differ','key_problems':['Conflicting deployment constraints'],'constraints':['Use a cloud database.'],'non_goals':[],'acceptance':['Deployment location known']}
    return context,extract

def test_agent_omission_preserves_declared_conflict_and_blocks(tmp_path):
    context,extract=inputs(tmp_path)
    brief=compile_deck_brief({'run_id':'test'},context,{},agent_extract=extract,run_dir=tmp_path)
    assert brief['source_conflicts']==context['conflicts']
    assert brief['status']=='blocked'
    with pytest.raises(ValueError,match='source conflict'):build_claim_map(brief,context,run_dir=tmp_path)

def test_resolved_conflict_requires_real_source_and_selected_constraint(tmp_path):
    context,extract=inputs(tmp_path)
    resolution='Use the local database.'
    extract['source_conflicts']=[{**context['conflicts'][0],'status':'resolved','resolution':resolution,'decision_ref':'revision::E1'}]
    extract['constraints']=[resolution]
    brief=compile_deck_brief({'run_id':'test'},context,{},agent_extract=extract,run_dir=tmp_path)
    assert brief['status']=='brief_ready'
    assert brief['source_conflicts'][0]['evidence_refs']==context['conflicts'][0]['evidence_refs']
    assert build_claim_map(brief,context,run_dir=tmp_path)['claims']

@pytest.mark.parametrize('corruption',['missing_ref','wrong_hash','wrong_constraint','changed_declaration'])
def test_resolution_cannot_invent_or_drop_basis(tmp_path,corruption):
    context,extract=inputs(tmp_path)
    resolved={**context['conflicts'][0],'status':'resolved','resolution':'Use local database.','decision_ref':'revision::E1'}
    extract['constraints']=['Use local database.'];extract['source_conflicts']=[resolved]
    if corruption=='missing_ref':resolved['decision_ref']='unknown'
    if corruption=='wrong_hash':(tmp_path/'revision.txt').write_text('New unrelated text')
    if corruption=='wrong_constraint':extract['constraints']=['Use a cloud database.']
    if corruption=='changed_declaration':resolved['evidence_refs']=['revision::E1']
    brief=compile_deck_brief({'run_id':'test'},context,{},agent_extract=extract,run_dir=tmp_path)
    assert brief['status']=='blocked'
    assert brief['source_conflicts'][0]['status']=='open'

def test_stored_ready_flag_cannot_hide_new_declared_conflict(tmp_path):
    from workflow.stage_checks import evaluate_stage_checks
    context,extract=inputs(tmp_path)
    forged={'status':'brief_ready','constraints':extract['constraints'],'source_conflicts':[]}
    (tmp_path/'deck_brief.json').write_text(json.dumps(forged))
    (tmp_path/'context_manifest.json').write_text(json.dumps(context))
    assert not evaluate_stage_checks(tmp_path,'deck-brief').valid
    with pytest.raises(ValueError,match='source conflict'):build_claim_map(forged,context,run_dir=tmp_path)

def test_real_quote_cannot_support_opposite_selected_constraint(tmp_path):
    context,extract=inputs(tmp_path)
    extract['source_conflicts']=[{**context['conflicts'][0],'status':'resolved','resolution':'Use a cloud database.','decision_ref':'revision::E1'}]
    brief=compile_deck_brief({'run_id':'test'},context,{},agent_extract=extract,run_dir=tmp_path)
    assert brief['status']=='blocked'
