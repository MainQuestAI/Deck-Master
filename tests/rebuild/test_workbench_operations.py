"""Synthetic transaction/process-fault tests; no Host acceptance claim."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from deck_master import operations, store as store_module
from deck_master.models import bump_revision, new_document, content_identity
from deck_master.store import Store, ConflictError


def project(tmp_path):
    store = Store(tmp_path / 'project')
    doc = new_document(project_id='synthetic-operations', task={
        'title': 'Test', 'brief': 'Synthetic', 'audience': 'Tests', 'scenario': 'test',
        'presentation_mode': 'live', 'page_limit': None, 'existing_decisions': []})
    doc['compatibility'] = {'project_format': 'workbench.v3', 'minimum_writer': 'content-plan.v1'}
    store.init_project(doc)
    return store


def submit(store, operation_id, base, payload):
    operations.validate_id(operation_id, new=True)
    with store._locked():
        doc = store.load_document()
        digest = operations.request_digest(doc, 'synthetic', base, payload)
        prior = operations.recover(store, operation_id, digest)
        if prior:
            return prior
        if doc['revision_id'] != base:
            raise ConflictError('base_revision', 'changed')
        new = bump_revision(doc, {'operation_id': operation_id, 'kind': 'task_update',
                                 'description': 'Synthetic operation', 'read_set': []})
        result = {'status': 'saved', 'revision_id': new['revision_id'], 'value': payload}
        return operations.commit_locked(store, document=new, base_revision=base,
                                         operation_id=operation_id, kind='synthetic', digest=digest, result=result)


def advance(store):
    doc = store.load_document(); op = str(uuid.uuid4())
    changed = bump_revision(doc, {'operation_id': op, 'kind': 'task_update',
                                  'description': 'Unrelated progress', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id=op)


def test_history_replay_ignores_corrupt_index_and_later_revisions(tmp_path):
    store = project(tmp_path); base = store.current_revision_id(); op = str(uuid.uuid4())
    first = submit(store, op, base, {'text': 'A🙂e\u0301\r\n中'})
    for _ in range(3): advance(store)
    pointer = store.read_current(); identity = content_identity(store.load_document())
    index = store.deck_root / 'operations' / (op + '.json')
    for damage in [None, b'broken', b'{"format":"operation_index.v1","committed_revision_id":"forged"}']:
        if damage is None: index.unlink(missing_ok=True)
        else: index.write_bytes(damage)
        replay = submit(store, op, base, {'text': 'A🙂e\u0301\r\n中'})
        assert replay['operation_result'] == first['operation_result']
        assert replay['result_ref'] == first['result_ref']
        assert store.read_current() == pointer
        assert content_identity(store.load_document()) == identity
        assert json.loads(index.read_bytes())['committed_revision_id'] == first['committed_revision_id']
    with pytest.raises(operations.OperationError) as error:
        submit(store, op, base, {'text': 'changed'})
    assert error.value.error_code == 'operation_payload_conflict'
    assert store.operation_receipt(op)['response'] == first['operation_result']


@pytest.mark.parametrize('phase', ['before_pointer', 'after_pointer', 'before_index', 'after_index'])
def test_interruption_boundary(tmp_path, monkeypatch, phase):
    store = project(tmp_path); base = store.current_revision_id(); op = str(uuid.uuid4())
    original_write = store_module._atomic_write_bytes
    original_index = operations.publish_index
    def write(path, data):
        if path.name == 'current.json' and phase == 'before_pointer':
            raise SystemExit('synthetic process interruption')
        original_write(path, data)
        if path.name == 'current.json' and phase == 'after_pointer':
            raise SystemExit('synthetic process interruption')
    def index(*args):
        if phase == 'before_index': raise SystemExit('synthetic process interruption')
        result = original_index(*args)
        if phase == 'after_index': raise SystemExit('synthetic process interruption')
        return result
    monkeypatch.setattr(store_module, '_atomic_write_bytes', write)
    monkeypatch.setattr(operations, 'publish_index', index)
    with pytest.raises(SystemExit): submit(store, op, base, {'value': 1})
    monkeypatch.setattr(store_module, '_atomic_write_bytes', original_write)
    monkeypatch.setattr(operations, 'publish_index', original_index)
    found = operations.recover(store, op)
    assert (found is None) == (phase == 'before_pointer')
    committed = store.current_revision_id()
    if found:
        advance(store); advance(store)
    replay = submit(store, op, base, {'value': 1})
    assert replay['operation_result']['value'] == {'value': 1}
    if found: assert replay['committed_revision_id'] == committed
    assert len([d for d in operations.committed_snapshots(store) if d['change']['operation_id'] == op]) == 1


@pytest.mark.parametrize('different', [False, True])
def test_concurrent_same_operation_is_one_transaction(tmp_path, different):
    store = project(tmp_path); base = store.current_revision_id(); op = str(uuid.uuid4())
    def call(value):
        try: return submit(Store(store.project_root), op, base, value)
        except operations.OperationError as error: return error.error_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, [1, 2 if different else 1]))
    if different:
        assert sum(x == 'operation_payload_conflict' for x in results if isinstance(x, str)) == 1
    else:
        assert results[0]['operation_result'] == results[1]['operation_result']
    assert len([d for d in operations.committed_snapshots(store) if d['change']['operation_id'] == op]) == 1


def test_uncommitted_index_is_not_truth_and_symlink_not_followed(tmp_path):
    store = project(tmp_path); op = str(uuid.uuid4()); base = store.current_revision_id()
    directory = store.deck_root / 'operations'; directory.mkdir()
    victim = tmp_path / 'outside'; victim.write_text('untouched')
    (directory / (op + '.json')).symlink_to(victim)
    assert operations.recover(store, op) is None
    result = submit(store, op, base, {})
    assert result['status'] == 'committed'
    assert result['journal_warning']['code'] == 'receipt_cache_unavailable'
    assert victim.read_text() == 'untouched'


@pytest.mark.parametrize('value', ['../outside', 'x'*129, uuid.uuid4().hex, str(uuid.uuid1()), None])
def test_new_operation_ids_are_uuid4(value):
    with pytest.raises(operations.OperationError): operations.validate_id(value, new=True)


@pytest.mark.parametrize('phase', ['before_pointer', 'after_pointer', 'before_index', 'after_index'])
@pytest.mark.parametrize('path_kind', ['new_operation', 'old_task_accept'])
def test_actual_process_exit_preserves_exactly_one_committed_result(tmp_path, phase, path_kind):
    import os
    import subprocess
    import sys
    from pathlib import Path
    from test_task_receipt_recovery import pending, submit as task_submit
    if path_kind == 'old_task_accept':
        project_dir, store, task, envelope = pending(tmp_path)
        base = store.current_revision_id(); op = task['operation_id']
        request_file = tmp_path / 'request.json'
        request_file.write_text(json.dumps({'task': task, 'envelope': envelope}))
    else:
        store = project(tmp_path); project_dir = store.project_root
        base = store.current_revision_id(); op = str(uuid.uuid4()); request_file = tmp_path / 'unused'
    program = r'''
import os, sys, json
from pathlib import Path
from deck_master import operations, tasks, store as module
from deck_master.store import Store
root, op, base, phase, kind, request_file = sys.argv[1:]
original = module._atomic_write_bytes
original_index = operations.publish_index if kind == 'new_operation' else tasks.write_operation_journal
def write(path, data):
    if path.name == 'current.json' and phase == 'before_pointer': os._exit(73)
    original(path, data)
    if path.name == 'current.json' and phase == 'after_pointer': os._exit(73)
def index(*args, **kwargs):
    if phase == 'before_index': os._exit(73)
    result = original_index(*args, **kwargs)
    if phase == 'after_index': os._exit(73)
    return result
module._atomic_write_bytes = write
if kind == 'new_operation':
    from test_workbench_operations import submit
    operations.publish_index = index
    submit(Store(root), op, base, {'synthetic': 1})
else:
    from test_task_receipt_recovery import submit
    tasks.write_operation_journal = index
    request = json.loads(Path(request_file).read_text())
    submit(root, request['task'], request['envelope'])
'''
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(Path(__file__).parents[2] / 'src'), str(Path(__file__).parent)])
    child = subprocess.run([sys.executable, '-c', program, str(project_dir), op, base, phase, path_kind, str(request_file)],
                           env=env, capture_output=True, timeout=20)
    assert child.returncode == 73, child.stderr.decode()
    found = operations.recover(store, op)
    assert (found is None) == (phase == 'before_pointer')
    if found:
        advance(store); advance(store)
    if path_kind == 'new_operation':
        replay = submit(store, op, base, {'synthetic': 1})
        result = replay['operation_result']
    else:
        replay = task_submit(project_dir, task, envelope)
        result = replay['operation_result']
    if found: assert result == found['operation_result']
    assert len([d for d in operations.committed_snapshots(store) if d['change']['operation_id'] == op]) == 1
    assert operations.show(project_dir, operation_id=op)['operation_result'] == result
