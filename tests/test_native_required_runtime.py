"""Required font evidence must govern real native build and public readiness."""
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]


def test_missing_fonts_stop_before_native_compile(tmp_path,monkeypatch):
    from test_sc1_1_native_host_chain import new_run,host_scene
    from build.native_engine import submit_approved_svg,run_native_compile,NativeEngineError
    from runtime.build import run_build
    from high_density.content import load_content_lock
    from high_density.svg import compile_svg
    root=new_run(tmp_path,'direct_svg')
    task=run_build(root)['pages'][0]
    scene=host_scene(root,load_content_lock(root,'P001'))
    svg=compile_svg(scene,tmp_path/'host.svg').read_text()
    submit_approved_svg(root,'P001',svg,action_id=task['action_id'],produced_against=task['produced_against'],scene=scene)
    empty=tmp_path/'empty-fonts';empty.mkdir()
    monkeypatch.setenv('DECK_MASTER_NATIVE_FONTS_DIR',str(empty))
    with pytest.raises(NativeEngineError,match='deck_native.fonts'):
        run_native_compile(root)
    readiness=json.loads((root/'build/task_readiness.json').read_text())
    assert readiness['status']=='blocked'
    assert readiness['required_missing']==['deck_native.fonts']
    assert not list((root/'build/native_outputs').glob('*/deck.pptx'))


def test_missing_fonts_block_full_workflow_and_public_production_readiness(tmp_path,monkeypatch):
    from skills import installer
    from runtime import setup_status as setup
    probe={'status':'degraded_ready','checks':{key:{'status':'verified'} for key in ['compile_smoke','render_smoke','rsvg_convert']}}
    probe['checks']['fonts']={'status':'unverified'}
    monkeypatch.setattr(installer,'_native_runtime_probe',lambda:probe)
    monkeypatch.setattr(installer,'inspect_skill_link',lambda *args,**kw:{'skill':kw['skill_name'],'status':'ready','valid':True})
    monkeypatch.setattr(installer,'_cli_status',lambda *args,**kw:'ready')
    monkeypatch.setattr(installer,'inspect_library_status',lambda:{'status':'ready'})
    suite=installer.inspect_suite_status(targets=['codex'])
    assert suite['full_suite_ready'] is True  # installed skills are independent
    assert suite['task_readiness']['native_compile']=='ready'
    assert suite['task_readiness']['native_fonts']=='blocked'
    assert suite['task_readiness']['full_deck_workflow']=='blocked'
    assert suite['status']=='degraded_ready'
    assert any(item['code']=='native_fonts_unverified' for item in suite['blocking_summary'])
    assert 'font' in suite['next_agent_action']
    monkeypatch.setattr(setup,'_read_config',lambda:{'schema_version':setup.SCHEMA_VERSION,'setup_completed_at':'2026-09-09T00:00:00Z','install_root':str(tmp_path),'default_runs_dir':str(tmp_path),'review_cockpit_url':'http://localhost:5050'})
    monkeypatch.setattr(setup,'setup_readiness',lambda **kw:{'status':{'production_ready':True,'install_ready':True,'workspace_ready':True,'run_ready':True}})
    monkeypatch.setattr(setup,'inspect_suite_status',lambda **kw:suite)
    status=setup.setup_status()
    assert status['workspace_entry_ready'] is True
    assert status['production_ready'] is False
