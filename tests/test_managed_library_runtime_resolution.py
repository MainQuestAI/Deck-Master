from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from runtime.library_status import inspect_library_status
from skills.capability_lock import install_managed_component

def test_status_resolves_managed_program_without_path_and_honors_library_home(tmp_path):
    exe=tmp_path/'.deck-master/backends/ppt-library/current/bin/ppt-lib';exe.parent.mkdir(parents=True);exe.write_text('#!/bin/sh\nexit 1\n');exe.chmod(0o755)
    library=tmp_path/'isolated-library'
    library.mkdir();(library/'index.db').write_bytes(b'')
    seen=[]
    def snapshot(source,target):
        seen.append(source);return False
    with patch('pathlib.Path.home',return_value=tmp_path),patch.dict('os.environ',{'PATH':'/usr/bin:/bin','PPT_LIB_HOME_DIR':str(library)}):
        result=inspect_library_status(snapshotter=snapshot,cache_ttl_seconds=0)
    assert 'PPT_LIBRARY_CLI_MISSING' not in result['blocking_summary']
    assert seen==[library]

def test_component_version_comes_from_real_cli_version_response(tmp_path):
    source=tmp_path/'source';exe=source/'bin/ppt-lib';exe.parent.mkdir(parents=True);exe.write_text('#!/bin/sh\necho "ppt-lib 2.7.3"\n');exe.chmod(0o755)
    with patch('pathlib.Path.home',return_value=tmp_path/'home'):
        result=install_managed_component('ppt-library',source)
    assert result['version']=='2.7.3'
    import json
    assert json.loads((Path(result['installed_path'])/'managed_component_manifest.json').read_text())['version']=='2.7.3'


def test_preview_copy_honors_explicit_library_home_but_rejects_other_roots(tmp_path):
    from tools.ppt_library_client import _is_safe_screenshot_source
    library=tmp_path/'library';library.mkdir();image=library/'page.png';image.write_bytes(b'\x89PNG\r\n\x1a\n')
    outside=tmp_path/'outside.png';outside.write_bytes(image.read_bytes())
    with patch.dict('os.environ',{'PPT_LIB_HOME_DIR':str(library)}):
        assert _is_safe_screenshot_source(image,tmp_path/'run')
        assert not _is_safe_screenshot_source(outside,tmp_path/'run')
