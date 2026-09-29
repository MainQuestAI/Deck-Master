"""HTTP security/CLI parity harness. Host execution is separately verified."""
import json
import uuid
from pathlib import Path

import pytest

from deck_master import cli
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_web import _get_json, _post_json, _session_token


@pytest.fixture
def running(tmp_path):
    project = tmp_path / 'sample'; create_sample(project, page_count=1, readonly=False)
    server = WorkbenchServer(project); url = server.start().rstrip('/')
    try: yield project, Store(project), url, _session_token(url)
    finally: server.stop()


def test_annotation_plan_commit_query_handoff_cli_http_parity(running, tmp_path, capsys):
    project, store, url, token = running; doc = store.load_document(); entry = doc['pages'][0]
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
            'scope': 'page', 'page_id': entry['page_id'], 'page_ref': entry['page'],
            'intent': 'clarify', 'body': '<script>not executable</script>', 'status': 'open', 'location': {'kind': 'whole'}}
    payload = {'input': {'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'], 'annotations': [note]},
               'base_revision': doc['revision_id'], 'operation_id': str(uuid.uuid4())}
    for headers in [(None, None), (token, 'https://foreign.invalid'), ('wrong', url)]:
        assert _post_json(url + '/api/annotations/batch', payload, *headers)[0] == 403
    assert store.current_revision_id() == doc['revision_id']
    code, saved = _post_json(url + '/api/annotations/batch', payload, token, url)
    assert code == 200
    assert _get_json(url + '/api/operations/' + payload['operation_id'])[2]['operation_result'] == saved['operation_result']
    assert cli.main(['operations', 'show', '--project', str(project), '--operation-id', payload['operation_id']]) == 0
    assert json.loads(capsys.readouterr().out)['operation_result'] == saved['operation_result']
    base = store.current_revision_id()
    change = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'], 'base_revision': base,
              'targets': [{'page_id': entry['page_id'], 'page_ref': entry['page'], 'layer': 'content', 'artifact_ref': entry['page']}],
              'intent': 'clarify', 'instruction': 'Clarify the page', 'max_calls': 0,
              'annotation_refs': [saved['operation_result']['annotations'][0]['ref']]}
    code, plan = _post_json(url + '/api/changes/plan', {'input': change}, token, url)
    assert code == 200 and store.current_revision_id() == base
    input_path = tmp_path / 'change.json'; input_path.write_text(json.dumps(change))
    assert cli.main(['changes', 'plan', '--project', str(project), '--input', str(input_path)]) == 0
    assert json.loads(capsys.readouterr().out) == plan
    request = {'plan_id': plan['plan_id'], 'base_revision': base, 'operation_id': str(uuid.uuid4())}
    code, committed = _post_json(url + '/api/changes/commit', request, token, url)
    assert code == 200
    identity = committed['operation_result']['change_id']
    handoff = _get_json(url + '/api/changes/' + identity + '/handoff')[2]
    assert handoff['status'] == 'awaiting_host'
    assert cli.main(['changes', 'handoff', '--project', str(project), '--change-id', identity]) == 0
    assert json.loads(capsys.readouterr().out) == handoff
    assert _get_json(url + '/api/changes')[2]['changes'][0]['change_id'] == identity
    assert _get_json(url + '/api/annotations')[2]['annotations'][0]['annotation']['body'] == note['body']


def test_typed_not_found_conflict_and_invalid_fields_match_cli(running, tmp_path, capsys):
    project, store, url, token = running; missing = str(uuid.uuid4())
    code, http = _get_json(url + '/api/operations/' + missing)[::2]
    assert code == 404
    assert cli.main(['operations', 'show', '--project', str(project), '--operation-id', missing]) == 2
    assert json.loads(capsys.readouterr().err) == http
    error = http['error']; assert error['operation_state'] == 'not_found'
    assert Path(error['docs_ref'].split('#')[0]).is_file()
    code, invalid = _post_json(url + '/api/changes/commit', {'unrecognized': 1}, token, url)
    assert code == 422 and invalid['error']['code'] == 'invalid_input'
    code, invalid = _post_json(url + '/api/annotations/batch', {'input': {}, 'base_revision': store.current_revision_id(), 'operation_id': str(uuid.uuid4())}, token, url)
    assert code == 422 and 'docs_ref' in invalid['error']
    assert str(project) not in json.dumps(invalid)
