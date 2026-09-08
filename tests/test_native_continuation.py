from test_sc1_1_native_host_chain import new_run
from runtime.build import run_build
from runtime.next_step import resolve_next_step
from runtime.run_state_resolver import _resolve_stage


def test_native_next_step_uses_issued_task_without_old_hd_workflow(tmp_path):
    root = new_run(tmp_path, 'direct_svg')
    first = run_build(root)
    result = resolve_next_step(root)
    assert result['runtime_stage'] == 'awaiting_agent_execution'
    assert result['host_task']['pages'][0]['action_id'] == first['pages'][0]['action_id']
    assert _resolve_stage(root, 'production')[0] == result['runtime_stage']
    assert resolve_next_step(root) == result
