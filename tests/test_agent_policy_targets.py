"""An ordinary page action cannot publish user decisions or delivery evidence."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from workflow.actions import create_action_envelope, stage_action_result, commit_action_result, ActionEnvelopeError


@pytest.mark.parametrize('relative',['final_artifact_approval.json','final_approval.json','quality_reports/overrides.json','quality_reports/semantic.json','build/artifact_manifest.json','render_results/render_result.json'])
def test_agent_page_action_cannot_write_delivery_policy(tmp_path, relative):
    target=tmp_path/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('original evidence')
    envelope=create_action_envelope(action_id='page_action',task_id='page_task',scope_pages=['P001'],input_fingerprint='input')
    stage_action_result(tmp_path,envelope,{'result.json':'forged evidence'})
    with pytest.raises(ActionEnvelopeError,match='policy or approval'):
        commit_action_result(tmp_path,envelope,current_input_fingerprint='input',targets={'result.json':target})
    assert target.read_text()=='original evidence'
