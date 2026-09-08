"""Default prepare must not turn its own fresh manifest into legacy evidence."""
import json,subprocess,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from test_sc1_1_native_host_chain import new_run


def default_run(tmp_path):
    root=new_run(tmp_path)
    request=json.loads((root/'request.json').read_text())
    request.pop('profile');request.pop('authoring_mode')
    (root/'request.json').write_text(json.dumps(request))
    return root


def command(root,action):
    return subprocess.run([sys.executable,str(ROOT/'scripts/deck_master.py'),'build',action,'--run-dir',str(root)],cwd=ROOT,capture_output=True,text=True)


def test_default_prepare_then_run_keeps_native_imagegen_handoff(tmp_path):
    root=default_run(tmp_path)
    first=command(root,'prepare')
    assert first.returncode==0,first.stdout+first.stderr
    second=command(root,'run')
    assert second.returncode==0,second.stdout+second.stderr
    assert json.loads(second.stdout)['status']=='awaiting_agent_imagegen'
    route=json.loads((root/'build/route.json').read_text())
    assert route['engine_id']=='deck_native'
    assert route['authoring_mode']=='image_blueprint'
    assert route['selection_origin']=='default_policy'
    assert not list(root.glob('build/native_outputs/*/deck.pptx'))


def test_prepare_keeps_unidentified_historical_output_read_only(tmp_path):
    root=default_run(tmp_path);manifest=root/'build/build_manifest.json';manifest.parent.mkdir(exist_ok=True)
    original=b'{"old":"unidentified historical output"}'
    manifest.write_bytes(original)
    result=command(root,'prepare')
    assert result.returncode!=0
    assert 'migration_required' in result.stdout+result.stderr
    assert manifest.read_bytes()==original
    assert not (root/'build/route.json').exists()
