import json
from unittest import mock
import pytest
from runtime.next_step import resolve_next_step
from runtime.skill_route import route_for_stage
from skills import installer


@pytest.mark.parametrize('stage', ['needs_build', 'awaiting_agent_execution', 'needs_draft_gate'])
def test_native_next_step_does_not_request_legacy_skills(tmp_path, stage):
    (tmp_path/'request.json').write_text(json.dumps({'run_mode':'production'}))
    continuation={'stage':stage,'reason':'native continuation','next_command':'deck-master build run','host_task':{}}
    with mock.patch('build.native_state.native_continuation',return_value=continuation):
        result=resolve_next_step(tmp_path)
    assert result['skill_route']['backend_dependency']==''
    assert result['skill_route']['compat_skills']==[]
    assert result['next_command']==continuation['next_command']


def test_legacy_builder_dependency_is_preserved():
    assert route_for_stage('needs_builder_backend')['backend_dependency']=='ppt-master'
    assert route_for_stage('needs_builder_backend')['compat_skills']==['ppt-master','render']


@pytest.mark.parametrize(('failed_check','expected'), [('compile_smoke','compiler'),('render_smoke','soffice'),('fonts','Noto Sans SC'),('rsvg_convert','rsvg-convert')])
def test_required_native_recovery_precedes_optional_library(tmp_path, failed_check, expected):
    checks={name:{'status':'verified'} for name in ['compile_smoke','render_smoke','fonts','rsvg_convert']}
    checks[failed_check]={'status':'blocked','error':'actual failure detail'}
    probe={'status':'blocked' if failed_check in ['compile_smoke','rsvg_convert'] else 'degraded_ready','checks':checks}
    def link(target, directory, *,skill_name,required):
        return {'skill':skill_name,'status':'ready','valid':True,'required':required}
    with mock.patch.object(installer,'_native_runtime_probe',return_value=probe),mock.patch.object(installer,'inspect_library_status',return_value={'status':'blocked'}),mock.patch.object(installer,'inspect_skill_link',side_effect=link),mock.patch.object(installer,'_cli_status',return_value='ready'):
        status=installer.inspect_suite_status(targets=['custom'],agent_skill_dir=str(tmp_path))
    assert status['full_suite_ready']
    assert status['task_readiness']['full_deck_workflow']=='blocked'
    assert status['next_command']!='deck-master library-status'
    assert expected in status['next_agent_action']
    assert 'actual failure detail' in status['next_agent_action']
