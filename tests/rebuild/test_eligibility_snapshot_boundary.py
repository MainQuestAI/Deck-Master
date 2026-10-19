"""N1 synthetic SDK/HTTP parity and fixed artifact/control read boundaries."""
import copy
import json

import pytest

from deck_master import collaboration_api, eligibility, operations, service, snapshots
from deck_master.models import canonical_json_bytes
from deck_master.snapshots import ReadModelError
from deck_master.store import Store
from test_input_receipt_recovery import advance, saved_bytes
from test_rc3_collaboration_adapters import http, http_server, instruction, new_project, write


def request(root, revision):
    return collaboration_api.invoke(root, 'eligibility', {'action': 'content.inputs_update',
        'artifact_revision': revision, 'targets': {'layers': ['narrative']}})


def test_current_and_history_sdk_http_equal_and_readonly(tmp_path):
    root = new_project(tmp_path); store = Store(root)
    historical = store.current_revision_id(); advance(store)
    for revision in (None, historical):
        before = saved_bytes(store)
        sdk = eligibility.describe(root, 'content.inputs_update', revision=revision, targets={'layers': ['narrative']})
        response, status, code = request(root, revision)
        assert (status, code) == (200, 0)
        assert sdk['allowed'] == response['result']['allowed']
        assert sdk['reason_codes'] == response['result']['reason_codes']
        assert sdk['artifact_revision_id'] == response['artifact_revision_id']
        assert sdk['control_revision_id'] == response['control_revision_id'] == store.current_revision_id()
        assert saved_bytes(store) == before


@pytest.mark.parametrize('damage', ['empty', 'path', 'illegal', 'orphan', 'foreign', 'symlink', 'corrupt'])
def test_sdk_http_reject_same_snapshot_code_without_writes(tmp_path, damage):
    root = new_project(tmp_path); store = Store(root)
    historical = store.current_revision_id(); advance(store)
    revision = historical
    if damage == 'empty':
        revision = ''
    elif damage == 'path':
        revision = '../current'
    elif damage == 'illegal':
        revision = '非法'
    elif damage in ('orphan', 'foreign'):
        doc = copy.deepcopy(store.load_document()); revision = damage
        doc['revision_id'] = revision
        if damage == 'foreign':
            other = tmp_path / 'foreign-source'; service.create(other, brief='Foreign synthetic project')
            doc = Store(other).load_document(); revision = doc['revision_id']
        (store.revisions_dir / (revision + '.json')).write_bytes(canonical_json_bytes(doc))
    elif damage == 'symlink':
        path = store.revisions_dir / (historical + '.json')
        target = tmp_path / 'external.json'; target.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(target)
    else:
        (store.revisions_dir / (historical + '.json')).write_bytes(b'not JSON')
    before = saved_bytes(store)
    with pytest.raises(ReadModelError) as error:
        eligibility.describe(root, 'content.inputs_update', revision=revision)
    response, status, code = request(root, revision)
    assert status == error.value.http_status and response['error']['code'] == error.value.error_code
    assert code == error.value.exit_code
    assert saved_bytes(store) == before
    assert str(tmp_path) not in json.dumps(response)


def test_foreign_or_cycle_in_canonical_chain_cannot_prove_absence(tmp_path):
    root = new_project(tmp_path); store = Store(root)
    head = store.load_document(); parent = head['parent_revision_id']
    if parent is None:
        head = advance(store); parent = head['parent_revision_id']
    path = store.revisions_dir / (parent + '.json'); original = path.read_bytes()
    for kind in ('foreign', 'cycle'):
        doc = json.loads(original)
        if kind == 'foreign':
            doc['project_id'] = 'another-project'
        else:
            doc['parent_revision_id'] = head['revision_id']
        path.write_bytes(canonical_json_bytes(doc))
        lookup = operations.resolve_operation(store, 'unused-operation')
        assert lookup.state == 'unknown' and lookup.reason == 'history_unreadable'
        with pytest.raises(ReadModelError):
            eligibility.describe(root, 'content.inputs_update', revision='missing')
    path.write_bytes(original)
    assert operations.resolve_operation(store, 'unused-operation').state == 'not_found'


@pytest.mark.parametrize('location', ['current', 'historical', 'intermediate'])
def test_schema_corrupt_eligibility_snapshot_has_safe_sdk_http_error(tmp_path, location):
    root = new_project(tmp_path); store = Store(root)
    selected = store.current_revision_id()
    damaged = selected
    if location != 'current':
        damaged = advance(store)['revision_id'] if location == 'intermediate' else selected
        advance(store, operation='after-damaged-snapshot')
    path = store.revisions_dir / (damaged + '.json')
    doc = json.loads(path.read_bytes())
    doc['collaboration'] = [str(tmp_path / 'private-diagnostic-marker')]
    path.write_bytes(canonical_json_bytes(doc))
    revision = None if location == 'current' else selected
    before = saved_bytes(store)
    with pytest.raises(ReadModelError) as error:
        eligibility.describe(root, 'content.inputs_update', revision=revision)
    assert error.value.error_code == 'revision_unavailable'
    response, status, code = request(root, revision)
    assert (status, code) == (error.value.http_status, error.value.exit_code)
    assert response['error']['code'] == error.value.error_code
    project_id = doc['project_id']
    with http_server(root) as url:
        http_status, payload = http(url, f'/api/projects/{project_id}/eligibility', {
            'action': 'content.inputs_update', 'artifact_revision': revision})
    assert http_status == status and payload['error']['code'] == error.value.error_code
    assert str(tmp_path) not in json.dumps([response, payload])
    assert operations.resolve_operation(store, 'unused-operation').state == 'unknown'
    assert saved_bytes(store) == before


@pytest.mark.parametrize('entry', ['sdk', 'http'])
def test_control_capture_is_fixed_across_concurrent_pause(tmp_path, monkeypatch, entry):
    root = new_project(tmp_path); store = Store(root)
    artifact_revision = store.current_revision_id(); advance(store)
    captured_revision = store.current_revision_id()
    original = snapshots.capture_head
    changed = []
    def capture(s):
        captured = original(s)
        if not changed:
            changed.append(True)
            request_id = store.load_document()['collaboration']['request']['request_id']
            response, status, _ = write(root, 'pause', 'pause-after-capture', request_id=request_id,
                reason='Synthetic concurrent pause', evidence=instruction())
            assert status == 200, response
        return captured
    monkeypatch.setattr(snapshots, 'capture_head', capture)
    if entry == 'sdk':
        result = eligibility.describe(root, 'content.inputs_update', revision=artifact_revision)
    else:
        response, status, _ = request(root, artifact_revision)
        assert status == 200
        result = response['result']
    assert result['artifact_revision_id'] == artifact_revision
    assert result['control_revision_id'] == captured_revision
    assert result['control_revision_id'] != store.current_revision_id()
    assert 'request_paused' not in result['reason_codes']
    monkeypatch.setattr(snapshots, 'capture_head', original)
    latest = eligibility.describe(root, 'content.inputs_update', revision=artifact_revision)
    assert 'request_paused' in latest['reason_codes']
    assert latest['control_revision_id'] == store.current_revision_id()


def test_explicit_head_is_verified_and_fixed(tmp_path):
    root = new_project(tmp_path); store = Store(root)
    old = store.current_revision_id(); advance(store)
    lookup = operations.resolve_operation(store, 'unused', head_revision=old)
    assert lookup.head_revision == old and lookup.state == 'not_found'
    doc = store.load_document(); doc['revision_id'] = 'orphan'
    (store.revisions_dir / 'orphan.json').write_bytes(canonical_json_bytes(doc))
    assert operations.resolve_operation(store, 'unused', head_revision='orphan').state == 'unknown'


def test_actual_http_eligibility_uses_same_errors_and_fixed_wrapper(tmp_path):
    root = new_project(tmp_path); store = Store(root)
    historical = store.current_revision_id(); advance(store)
    project_id = store.load_document()['project_id']
    with http_server(root) as url:
        status, response = http(url, f'/api/projects/{project_id}/eligibility', {
            'action': 'content.inputs_update', 'artifact_revision': historical})
        assert status == 200 and response['artifact_revision_id'] == historical
        assert response['control_revision_id'] == store.current_revision_id()
        status, response = http(url, f'/api/projects/{project_id}/eligibility', {
            'action': 'content.inputs_update', 'artifact_revision': ''})
        assert status == 400 and response['error']['code'] == 'invalid_revision'


def test_http_duplicate_revision_query_cannot_fall_back_current(tmp_path):
    root = new_project(tmp_path); store = Store(root)
    before = saved_bytes(store)
    project_id = store.load_document()['project_id']
    with http_server(root) as url:
        status, response = http(url, f'/api/projects/{project_id}/eligibility?artifact_revision=&artifact_revision=current',
            {'action': 'content.inputs_update'})
    assert status == 400 and response['error']['code'] == 'invalid_input'
    assert saved_bytes(store) == before
