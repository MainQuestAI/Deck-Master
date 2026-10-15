"""Host evidence must not collapse returned method bytes into execution."""
import hashlib
import json
from pathlib import Path
import runpy

import pytest

DRIVER = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'examples/workbench/rc3_four_skill_paths.py'))


def test_verification_refuses_incomplete_matrix(tmp_path):
    (tmp_path / 'packet.json').write_text(json.dumps({'schema_version': 'four_skill_host_packet.v1', 'cases': []}))
    with pytest.raises(ValueError, match='complete frozen 16-path packet'):
        DRIVER['verify'](tmp_path)


def test_returned_workorders_without_actual_execution_never_verify(tmp_path):
    rows = []
    for skill in DRIVER['SKILLS']:
        for mode in DRIVER['MODES']:
            identity = skill + '--' + mode
            path = tmp_path / (identity + '.workorder.json')
            path.write_text(json.dumps({'skill': skill, 'entry_mode': mode}))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append({'case_id': identity, 'workorder': path.name, 'sha256': digest})
            (tmp_path / (identity + '.application.json')).write_text(json.dumps(
                {'case_id': identity, 'workorder_sha256': digest, 'executed': False,
                 'execution': {'source': None, 'locator': None}}))
    (tmp_path / 'packet.json').write_text(json.dumps({'schema_version': 'four_skill_host_packet.v1', 'cases': rows}))
    with pytest.raises(ValueError, match='actual Host execution has not been recorded'):
        DRIVER['verify'](tmp_path)
