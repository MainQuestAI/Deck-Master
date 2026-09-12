import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

def cli(run, *args):
    return subprocess.run([sys.executable, str(ROOT/'scripts/deck_master.py'), 'workflow', *args, '--run-dir', str(run)], text=True, capture_output=True, env={**os.environ, 'DECK_MASTER_DEV_SKIP_SETUP':'1'})

def seed(tmp_path):
    run=tmp_path/'controlled-negative';run.mkdir();(run/'request.json').write_text(json.dumps({'run_id':run.name,'run_mode':'production','project_name':'Explicit synthetic question acceptance'}));return run

def answer(run, token, **overrides):
    values=dict(stage_id='deck-init',question_id='init.customer_visible_forbidden',answer_json='"否"',source_type='user',actor_id='synthetic-test-user',actor_role='user',input_fingerprint=token);values.update(overrides)
    args=[part for k,v in values.items() for part in ['--'+k.replace('_','-'),v]]
    return cli(run,'answer',*args)

def test_cli_negative_consumed_and_revision_receipt(tmp_path):
    run=seed(tmp_path);q=cli(run,'questions');assert q.returncode==0,q.stderr
    before=json.loads(q.stdout);assert any(q['question_id']=='init.customer_visible_forbidden' for q in before['questions'])
    result=answer(run,before['input_fingerprint']);assert result.returncode==0,result.stderr
    after=json.loads(cli(run,'questions').stdout);assert not any(q['question_id']=='init.customer_visible_forbidden' for q in after['questions'])
    receipt=json.loads(result.stdout)['receipt'];snap=run/'build/revisions'/receipt['revision_id'];assert (snap/'workflow/decision_log.jsonl').is_file()
    (run/'workflow/decision_log.jsonl').write_text('')
    assert not any(q['question_id']=='init.customer_visible_forbidden' for q in json.loads(cli(run,'questions').stdout)['questions'])

def test_cli_rejects_stale_unknown_authority_without_writing(tmp_path):
    run=seed(tmp_path);q=cli(run,'questions');assert q.returncode==0,q.stderr
    token=json.loads(q.stdout)['input_fingerprint']
    for changes in [dict(input_fingerprint='stale'),dict(question_id='unknown'),dict(source_type='user',actor_role='agent'),dict(source_type='agent_assumption',actor_role='user'),dict(source_type='agent_assumption',actor_role='agent',question_id='init.scan_scope'),dict(stage_id='deck-brief'),dict(answer_json='false',question_id='init.scan_scope')]:
        result=answer(run,token,**changes);assert result.returncode!=0,result.stdout
        assert not (run/'workflow/decision_log.jsonl').exists()
    (run/'request.json').write_text('{"changed": true}')
    assert answer(run,token).returncode!=0

def test_answer_rechecks_changed_inputs_at_commit_without_partial_record(tmp_path, monkeypatch):
    from workflow import question_commands as commands
    run=seed(tmp_path);token=commands.read_questions(run)['input_fingerprint']
    stage=commands.stage_action_result
    def change_after_stage(root, envelope, files):
        result=stage(root,envelope,files)
        (root/'request.json').write_text('{"changed_during_stage": true}')
        return result
    monkeypatch.setattr(commands,'stage_action_result',change_after_stage)
    import pytest
    with pytest.raises(ValueError,match='stale'):
        commands.answer_question(run,stage_id='deck-init',question_id='init.customer_visible_forbidden',answer=False,source_type='user',actor={'id':'synthetic','role':'user'},input_fingerprint=token)
    assert not (run/'workflow/decision_log.jsonl').exists()
    assert not (run/'build/current_revision.json').exists()

def test_pre_revision_explicit_question_dependency_changes_token(tmp_path):
    run=seed(tmp_path)
    for name in ['deck_project.json','material_inventory.json','workspace_policy.json']:
        (run/name).write_text('{}')
    (run/'deck_brief.json').write_text('{"constraints":["No cloud"]}')
    before=json.loads(cli(run,'questions').stdout);assert before['stage_id']=='deck-brief'
    (run/'deck_brief.json').write_text('{"constraints":["Only on-prem; additional condition"]}')
    after=json.loads(cli(run,'questions').stdout)
    assert before['input_fingerprint']!=after['input_fingerprint']
    result=answer(run,before['input_fingerprint'],stage_id='deck-brief',question_id='brief.non_negotiable_constraints',answer_json='"No cloud"')
    assert result.returncode!=0
    assert not (run/'workflow/decision_log.jsonl').exists()
