import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from context_intake.context_pack import _source_to_manifest_entry
from conversation.brief_compiler import compile_deck_brief

def test_partial_host_reading_survives_import():
    source={'source_id':'pdf','reading':{'coverage':'partial','read_ranges':[{'page':1}],'unread_ranges':[{'page':2,'critical':True}],'failures':[]},'sha256':'a'*64}
    result=_source_to_manifest_entry(source)
    assert result['reading']['coverage']=='partial'
    assert result['sha256']=='a'*64

def test_critical_unread_source_blocks_even_agent_brief():
    context={'sources':[{'source_id':'pdf','reading':{'coverage':'partial','read_ranges':[{'page':1}],'unread_ranges':[{'page':2,'critical':True}],'failures':[]}}]}
    brief=compile_deck_brief({'run_mode':'production'},context,{},agent_extract={'goal_decision':'Review proposal','key_problems':['Problem'],'constraints':[]})
    assert brief['status']=='blocked'
    assert any('pdf' in str(x) for x in brief['conflict_blockers'])

def test_full_read_without_source_version_rejected():
    from context_intake.context_pack import validate_context_pack
    pack={'schema_version':'deck_context_pack.v1','run_id':'r','sources':[{'source_id':'s','reading':{'coverage':'full','read_ranges':[{'page':1}],'unread_ranges':[],'failures':[]}}]}
    assert not validate_context_pack(pack)['valid']

def test_source_bytes_and_unread_range_cannot_be_laundered(tmp_path):
    from context_intake.reading import verify_source_bytes, reading_errors
    import pytest
    f=tmp_path/'source.txt';f.write_text('Actual content')
    with pytest.raises(ValueError,match='SHA256'):
        verify_source_bytes({'origin_path':str(f),'sha256':'a'*64})
    assert reading_errors({'extraction':{'read_units':1,'total_units':2,'status':'complete','unread_regions':[]}})

def test_replay_does_not_invalidate_synthetic_stage_approval(tmp_path):
    import json
    from tests.test_workflow_approval import _seed_brief, _brief_handoff, REGISTRY
    from workflow.approval import ApprovalRuntime
    from context_intake.context_pack import import_context_pack
    from runtime.run_state import create_run
    root=create_run(tmp_path,{'run_mode':'fixture'},run_id='r')
    import hashlib
    source=tmp_path/'source.txt'; source.write_text('Synthetic test source')
    pack={'schema_version':'deck_context_pack.v1','run_id':'r','sources':[{'source_id':'s','summary':'Synthetic test source','origin_path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'reading':{'method':'direct_text','coverage':'full','read_ranges':[{'start_char':0,'end_char':21}],'unread_ranges':[],'failures':[]}}]}
    import_context_pack(root,pack)
    # Explicitly synthetic test approval, never imported into a real production run.
    _seed_brief(root)
    actor={'id':'synthetic-approval-fixture','role':'approver'}
    ap=ApprovalRuntime(registry=REGISTRY); hid=_brief_handoff(root)
    record=ap.request(root,hid,run_id='r',actor=actor)
    ap.approve(root,record['approval_id'],actor=actor)
    assert ap.is_transition_cleared(root,'deck-brief',run_id='r')[0]
    current=(root/'build/current_revision.json').read_bytes()
    assert import_context_pack(root,pack,merge=True)['status']=='idempotent'
    assert (root/'build/current_revision.json').read_bytes()==current
    assert ap.is_transition_cleared(root,'deck-brief',run_id='r')[0]

def test_real_cli_next_step_exposes_unread_ranges(tmp_path):
    import json,subprocess
    from runtime.run_state import create_run
    run=create_run(tmp_path,{'run_mode':'production'},run_id='partial-cli')
    (run/'context_manifest.json').write_text(json.dumps({'sources':[{'source_id':'pdf','reading':{'coverage':'partial','read_ranges':[{'page':1}],'unread_ranges':[{'page':2,'critical':True}],'failures':[]}}]}))
    cli=Path(__file__).resolve().parents[1]/'scripts/deck_master.py'
    result=subprocess.run([sys.executable,str(cli),'next-step','--run-dir',str(run),'--dev-allow-unsetup'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report['status']=='blocked_context_reading'
    assert report['host_task']['kind']=='extract_context_sources'
    assert report['blocking_issues'][0]['unread_ranges']==[{'page':2,'critical':True}]
