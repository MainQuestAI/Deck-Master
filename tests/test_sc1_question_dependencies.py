"""Question dependency snapshots keep unrelated changes from reopening decisions."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from workflow.questions import QuestionResolver
from workflow.decisions import DecisionLog

def seed(root):
    for name,payload in {'deck_project.json':{},'material_inventory.json':{},'workspace_policy.json':{},'request.json':{'business_goal':'Pilot','audience':'Board'},'deck_brief.json':{'business_goal':'Pilot','acceptance':['Stock visible'],'constraints':['No private data']},'claim_map.json':{'claims':[]}}.items():
        (root/name).write_text(json.dumps(payload))

def answer(root):
    qr=QuestionResolver();contract=qr.registry.contract('deck-brief');fp=qr.input_fingerprint(contract,root)
    for q in contract.forcing_questions:
        if q['required']:
            DecisionLog().record(root,run_id='test',stage_id='deck-brief',question_id=q['question_id'],answer='Confirmed detail',actor={'id':'test'},required=True,input_fingerprint=fp)
    return qr

def test_unrelated_material_and_colour_keep_business_answers(tmp_path):
    seed(tmp_path);qr=answer(tmp_path)
    (tmp_path/'material_inventory.json').write_text('{"optional_colour_reference":"colour.png"}')
    brief=json.loads((tmp_path/'deck_brief.json').read_text());brief['style_preference']='blue';(tmp_path/'deck_brief.json').write_text(json.dumps(brief))
    assert qr.gaps(tmp_path,'deck-brief')==[]

def test_business_change_only_reopens_dependent_question(tmp_path):
    seed(tmp_path);qr=answer(tmp_path)
    request=json.loads((tmp_path/'request.json').read_text());request['business_goal']='All regions';(tmp_path/'request.json').write_text(json.dumps(request))
    assert [(g.question_id,g.answer_status) for g in qr.gaps(tmp_path,'deck-brief')]==[('brief.decision_object','stale')]

def test_legacy_unscoped_records_stay_conservative(tmp_path):
    seed(tmp_path);qr=answer(tmp_path)
    log=tmp_path/'workflow/decision_log.jsonl'
    records=[json.loads(line) for line in log.read_text().splitlines()]
    for record in records:record.pop('input_dependency_fingerprint',None)
    log.write_text(''.join(json.dumps(r)+'\n' for r in records))
    (tmp_path/'material_inventory.json').write_text('{"new_material":"x"}')
    assert all(g.stale for g in qr.gaps(tmp_path,'deck-brief'))
    assert len(qr.gaps(tmp_path,'deck-brief'))==4

def test_delayed_record_does_not_rebind_to_current_inputs(tmp_path):
    seed(tmp_path);qr=QuestionResolver();old=qr.input_fingerprint(qr.registry.contract('deck-brief'),tmp_path)
    (tmp_path/'material_inventory.json').write_text('{"changed":true}')
    rec=DecisionLog().record(tmp_path,run_id='test',stage_id='deck-brief',question_id='brief.decision_object',answer='Old answer',actor={'id':'test'},required=True,input_fingerprint=old)
    assert 'input_dependency_fingerprint' not in rec
    assert next(g for g in qr.gaps(tmp_path,'deck-brief') if g.question_id=='brief.decision_object').stale
