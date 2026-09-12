import json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tests.test_sc1_1_native_host_chain import new_run
from runtime.build import run_build
from workflow.actions import check_action_budget

def call(root,*args):
    cli=Path(__file__).resolve().parents[1]/'scripts/deck_master.py'
    return subprocess.run([sys.executable,str(cli),'build',*args,'--run-dir',str(root),'--dev-allow-unsetup'],capture_output=True,text=True)

def test_cancel_cli_stops_until_explicit_retry_and_charges_same_budget(tmp_path):
    root=new_run(tmp_path,'direct_svg');issued=run_build(root)['pages'][0]
    result=call(root,'cancel','--action-id',issued['action_id'],'--reason','Synthetic user stop')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='stopped'
    assert check_action_budget(root,issued['task_id'],max_actions=3)['used']==1
    assert call(root,'cancel','--action-id',issued['action_id'],'--reason','Same stop').returncode==0
    assert check_action_budget(root,issued['task_id'],max_actions=3)['used']==1
    assert run_build(root)['status']=='stopped'
    late=call(root,'submit','--page-id','P001','--action-id',issued['action_id'],'--produced-against',issued['produced_against'],'--svg',str(tmp_path/'missing.svg'),'--scene',str(tmp_path/'missing.scene.json'))
    assert late.returncode!=0
    assert 'cancel' in late.stderr.lower()
    retry=call(root,'retry','--page-id','P001','--stage','svg')
    assert retry.returncode==0,retry.stderr
    action=json.loads(retry.stdout)['pages'][0]
    assert action['action_id']!=issued['action_id']
    assert action['task_id']==issued['task_id']
    assert action['remaining_budget']==2

def test_cancel_exhaustion_cannot_reset_task_budget(tmp_path):
    root=new_run(tmp_path,'direct_svg');action=run_build(root)['pages'][0]
    for index in range(3):
        assert call(root,'cancel','--action-id',action['action_id'],'--reason','Synthetic stop').returncode==0
        result=call(root,'retry','--page-id','P001','--stage','svg')
        if index<2:
            assert result.returncode==0,result.stderr
            action=json.loads(result.stdout)['pages'][0]
        else:
            assert result.returncode!=0
            assert 'budget exhausted' in result.stderr
    assert check_action_budget(root,action['task_id'],max_actions=3)['used']==3
    assert run_build(root)['status']=='stopped'

def test_committed_action_cannot_be_cancelled(tmp_path):
    from tests.test_sc1_1_native_host_chain import host_scene
    from high_density.content import load_content_lock
    from high_density.svg import compile_svg
    from build.native_engine import submit_approved_svg
    root=new_run(tmp_path,'direct_svg');task=run_build(root)['pages'][0]
    scene=host_scene(root,load_content_lock(root,'P001'))
    svg=compile_svg(scene,tmp_path/'page.svg').read_text()
    submit_approved_svg(root,'P001',svg,action_id=task['action_id'],produced_against=task['produced_against'],scene=scene)
    result=call(root,'cancel','--action-id',task['action_id'],'--reason','Too late')
    assert result.returncode!=0
    assert 'committed' in result.stderr
    assert not (root/'workflow/actions/cancelled'/f"{task['action_id']}.json").exists()

def test_cancel_checks_run_and_action_identity(tmp_path):
    root=new_run(tmp_path,'direct_svg');task=run_build(root)['pages'][0]
    for action in ('../../request', 'not-issued'):
        assert call(root,'cancel','--action-id',action,'--reason','Invalid').returncode!=0
    other=new_run(tmp_path/'other','direct_svg')
    assert call(other,'cancel','--action-id',task['action_id'],'--reason','Wrong run').returncode!=0

def test_cancel_during_staging_charges_once(tmp_path,monkeypatch):
    import pytest
    from tests.test_sc1_1_native_host_chain import host_scene
    from high_density.content import load_content_lock
    from high_density.svg import compile_svg
    from build.native_engine import submit_approved_svg
    from build.native_tasks import cancel_native_action
    import workflow.actions as actions
    root=new_run(tmp_path,'direct_svg');task=run_build(root)['pages'][0]
    scene=host_scene(root,load_content_lock(root,'P001'));svg=compile_svg(scene,tmp_path/'page.svg').read_text()
    original=actions.stage_action_result
    def stage_then_cancel(*args,**kwargs):
        result=original(*args,**kwargs)
        cancel_native_action(root,task['action_id'],reason='Synthetic cancellation while host result in flight')
        return result
    monkeypatch.setattr(actions,'stage_action_result',stage_then_cancel)
    with pytest.raises(Exception,match='cancel'):
        submit_approved_svg(root,'P001',svg,action_id=task['action_id'],produced_against=task['produced_against'],scene=scene)
    assert check_action_budget(root,task['task_id'],max_actions=3)['used']==1
    assert not (root/'high_density_build/svg/P001.svg').exists()
