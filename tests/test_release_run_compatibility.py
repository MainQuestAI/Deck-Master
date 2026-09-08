"""The stable launcher protects new Run data after an older release is restored."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from skills import installer


@pytest.fixture
def installed(tmp_path, monkeypatch):
    central=tmp_path/'central';current=central/'current'
    (current/'.venv/bin').mkdir(parents=True)
    (current/'.venv/bin/python').symlink_to(sys.executable)
    (current/'scripts').mkdir()
    (current/'scripts/deck_master.py').write_text("from pathlib import Path; Path('old-runtime-invoked').write_text('yes'); print('{\\\"status\\\":\\\"ready\\\"}')")
    (current/'release-manifest.json').write_text('{}')
    monkeypatch.setattr(installer,'INSTALL_LOG_DIR',central)
    launcher=installer._write_global_launcher()
    run=tmp_path/'new-run';run.mkdir()
    (run/'request.json').write_text('{"profile":"native"}')
    return current,launcher,run


@pytest.mark.parametrize('command',[['build','run'],['build','prepare'],['build','retry'],['import-plan']])
def test_older_release_cannot_write_native_run(installed,tmp_path,command):
    current,launcher,run=installed
    before=(run/'request.json').read_bytes()
    result=subprocess.run([str(launcher),*command,'--run-dir',str(run)],cwd=tmp_path,text=True,capture_output=True)
    assert result.returncode==2,result.stdout+result.stderr
    assert json.loads(result.stdout)['code']=='RUN_FORMAT_READ_ONLY'
    assert not (tmp_path/'old-runtime-invoked').exists()
    assert (run/'request.json').read_bytes()==before


def test_legacy_status_is_explicitly_read_only_not_ready(installed,tmp_path):
    current,launcher,run=installed
    result=subprocess.run([str(launcher),'build','status',f'--run-dir={run}'],cwd=tmp_path,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    payload=json.loads(result.stdout)
    assert payload['status']=='legacy_read_only' and payload['read_only'] is True
    assert not (tmp_path/'old-runtime-invoked').exists()


def test_declared_support_allows_current_runtime(installed,tmp_path):
    current,launcher,run=installed
    (current/'release-manifest.json').write_text(json.dumps({'supported_run_formats':['deck_build_route.v1','deck_build_revision.v2']}))
    result=subprocess.run([str(launcher),'build','run','--run-dir',str(run)],cwd=tmp_path,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'old-runtime-invoked').exists()


def test_new_revision_version_blocks_even_without_native_profile(installed,tmp_path):
    current,launcher,run=installed
    (run/'request.json').write_text('{}')
    revision=run/'build/revisions/revision1';revision.mkdir(parents=True)
    (run/'build/current_revision.json').write_text('{"revision_id":"revision1"}')
    (revision/'revision_manifest.json').write_text('{"schema_version":"deck_build_revision.v99"}')
    result=subprocess.run([str(launcher),'build','run','--run-dir',str(run)],cwd=tmp_path,text=True,capture_output=True)
    assert result.returncode==2
    assert json.loads(result.stdout)['unsupported_run_formats']==['deck_build_revision.v99']
    assert not (tmp_path/'old-runtime-invoked').exists()


def test_run_id_resolution_cannot_bypass_guard(installed,tmp_path):
    current,launcher,run=installed
    result=subprocess.run([str(launcher),'build','run','--runs-dir',str(run.parent),'--run-id',run.name],cwd=tmp_path,text=True,capture_output=True)
    assert result.returncode==2
    assert json.loads(result.stdout)['code']=='RUN_FORMAT_READ_ONLY'
    assert not (tmp_path/'old-runtime-invoked').exists()


def test_unrecognized_revision_metadata_fails_closed(installed,tmp_path):
    current,launcher,run=installed
    (run/'build').mkdir()
    (run/'build/current_revision.json').write_text('{invalid')
    result=subprocess.run([str(launcher),'build','run','--run-dir',str(run)],cwd=tmp_path,text=True,capture_output=True)
    assert result.returncode==2
    assert json.loads(result.stdout)['code']=='RUN_FORMAT_UNREADABLE'
    assert not (tmp_path/'old-runtime-invoked').exists()
