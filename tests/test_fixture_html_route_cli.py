"""Real preview CLI lifecycle without native host work or external render."""
import json
import subprocess
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
import test_final_readiness as final_tests
from build.build_route import resolve_build_route, validate_route

@pytest.mark.parametrize('mode',['fixture','dev'])
def test_unprofiled_preview_prepare_run_status_repeats(mode):
    baseline=final_tests.FinalReadinessTests();baseline.setUp()
    try:
        baseline._write_baseline();root=baseline.run_dir
        request=json.loads((root/'request.json').read_text());request['run_mode']=mode;(root/'request.json').write_text(json.dumps(request))
        for action in ['prepare','run','status','prepare','run','status']:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/deck_master.py'),'build',action,'--run-dir',str(root)],cwd=ROOT,text=True,capture_output=True)
            assert result.returncode==0,result.stdout+result.stderr
            payload=json.loads(result.stdout)
            if action=='status':assert payload['status']=='completed',payload
        route=json.loads((root/'build/route.json').read_text())
        assert route['engine_id']=='fixture_html'
        assert (root/'build/deck.html').is_file()
        assert not list(root.glob('build/native_outputs/*/deck.pptx'))
    finally:baseline.doCleanups()

def test_production_default_remains_native_and_fixture_route_is_rejected():
    route=resolve_build_route({'run_mode':'production'})
    assert route['engine_id']=='deck_native'
    with pytest.raises(Exception):
        validate_route({**route,'engine_id':'fixture_html','authoring_mode':'fixture_preview'})


@pytest.mark.parametrize('route_request',[{'run_mode':'fixture','profile':'native'},{'run_mode':'dev','profile':'direct-svg'},{'run_mode':'fixture','authoring_mode':'direct_svg'}])
def test_explicit_native_authoring_keeps_native_route(route_request):
    assert resolve_build_route(route_request)['engine_id']=='deck_native'


def test_fixture_route_cannot_satisfy_production_rc(tmp_path, monkeypatch):
    from build.build_route import persist_route
    from runtime import rc_gate
    persist_route(tmp_path, resolve_build_route({'run_mode':'fixture'}))
    monkeypatch.setenv('DECK_MASTER_RC_RUN_DIR',str(tmp_path))
    monkeypatch.setattr(rc_gate,'external_dependency_statuses',lambda: [])
    def release(root, **kwargs):
        root.mkdir();(root/'deck_capability_lock.json').write_text('{"external_dependencies":[]}')
    monkeypatch.setattr(rc_gate,'build_release_tree',release)
    result=rc_gate._external_dependency_closure_check({'status':'report_ready'})
    assert result['status']=='fail'
    assert 'fixture HTML preview cannot satisfy production dependency closure' in str(result)
