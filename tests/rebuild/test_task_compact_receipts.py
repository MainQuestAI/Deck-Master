"""RP-07: negotiated mutation facts; all projects and executor names synthetic."""
import copy
import json
import time
import uuid

import pytest

from deck_master import service, tasks, method_resources
from deck_master.models import bump_revision
from deck_master.store import Store
from test_tasks import _make_project, _compose_envelope, ENVELOPES
from test_content_ops import prepare_editorial_project, dispatch
from test_task_receipt_recovery import pending, submit, advance

PROTOCOL = 'task_receipt.v1'


def claim(project, task, protocol=PROTOCOL, execution='L1-compact-receipt'):
    return service.task_start(project, task_id=task['task_id'], execution_ref=execution,
                              supported_protocols=[task['protocol_version']],
                              capabilities=task['required_capabilities'], response_protocol=protocol)


def test_claim_receipt_explicit_context_read_and_idempotent_claim(tmp_path, monkeypatch):
    project, task = _make_project(tmp_path)
    def no_work_orders(*args, **kwargs):
        pytest.fail('mutation receipt must not construct pending work orders')
    monkeypatch.setattr(service, '_pending_host_tasks', no_work_orders)
    first = claim(project, task)
    assert first['schema_version'] == PROTOCOL
    assert first['task']['execution_ref'] == 'L1-compact-receipt'
    assert first['task']['status'] == 'running'
    assert 'pending_tasks' not in first and first['context_ready'] is False
    assert first['context_read'] == {'command': 'methods', 'task_id': task['task_id'],
                                     'read_protocol': 'work_context.v2', 'body_mode': 'full'}
    repeated = claim(project, task)
    assert repeated['revision_id'] == first['revision_id']
    assert repeated['task'] == first['task']
    full = method_resources.read_task_methods(project, task['task_id'],
                                              read_protocol='work_context.v2', body_mode='full')
    assert len(full['tasks']) == 1 and full['tasks'][0]['task_id'] == task['task_id']
    assert '季度对照正文' in json.dumps(full, ensure_ascii=False)
    with pytest.raises(tasks.TaskConflict, match='another execution'):
        claim(project, task, execution='L1-wrong-execution')


def test_accept_and_replay_keep_applied_task_and_result_identity(tmp_path, monkeypatch):
    project, store, task, payload = pending(tmp_path)
    monkeypatch.setattr(service, '_pending_host_tasks', lambda *a, **k: pytest.fail('expanded pending work orders'))
    first = submit(project, task, payload, response_protocol=PROTOCOL)
    assert first['status'] == 'accepted'
    assert first['task']['task_id'] == task['task_id']
    assert first['task']['result_refs'] == first['result_refs']
    assert first['task']['status'] == 'completed'
    later = advance(store)
    replay = submit(project, task, payload, response_protocol=PROTOCOL)
    assert replay['status'] == 'already_applied'
    assert replay['current_revision_id'] == later
    assert replay['revision_id'] == first['revision_id']
    assert replay['task'] == first['task']
    assert replay['operation_result'] == first['operation_result']
    assert replay['result_refs'] == first['result_refs']
    changed = copy.deepcopy(payload)
    changed['payload']['diff']['summary'] = 'different request'
    with pytest.raises(tasks.TaskConflict):
        submit(project, task, changed, response_protocol=PROTOCOL)
    assert store.current_revision_id() == later


@pytest.mark.parametrize('protocol', [None, PROTOCOL])
def test_cancel_and_late_result_protection_identical(tmp_path, protocol):
    project, store, task, payload = pending(tmp_path)
    result = service.task_cancel(project, task_id=task['task_id'], response_protocol=protocol)
    assert result['status'] == 'cancelled'
    if protocol:
        assert result['task']['status'] == 'cancelled' and 'pending_tasks' not in result
    else:
        assert 'pending_tasks' in result and 'schema_version' not in result
    before = store.load_document()
    with pytest.raises(tasks.TaskConflict, match='result arrived after cancellation; call facts were settled'):
        submit(project, task, payload, response_protocol=protocol)
    after = store.load_document()
    # Late-result settlement is a real recorded transaction, not adoption.
    assert after['pages'] == before['pages'] and after['outputs'] == before['outputs']
    settled = tasks._lookup_task(after, task['task_id'], store)
    assert settled['status'] == 'cancelled'
    assert settled['call_allowances'] == tasks._lookup_task(before, task['task_id'], store)['call_allowances']
    journal = json.loads((store.deck_root / 'operations' / (task['operation_id'] + '.json')).read_text())
    assert journal['status'] == 'late_result_settled'


@pytest.mark.parametrize('operation', ['start', 'cancel', 'accept'])
def test_invalid_response_protocol_refused_before_writes(tmp_path, operation):
    project, task = _make_project(tmp_path)
    store = Store(project)
    before = store.current_revision_id()
    with pytest.raises(service.ServiceError, match='unsupported task response protocol'):
        if operation == 'start':
            claim(project, task, 'unknown.v9')
        elif operation == 'cancel':
            service.task_cancel(project, task_id=task['task_id'], response_protocol='unknown.v9')
        else:
            submit(project, task, {}, response_protocol='unknown.v9')
    assert store.current_revision_id() == before


def test_cli_can_negotiate_receipt(tmp_path, capsys):
    from deck_master.cli import main
    project, task = _make_project(tmp_path)
    args = ['task', 'start', '--project', str(project), '--task-id', task['task_id'],
            '--execution-ref', 'L1-cli', '--supported-protocol', task['protocol_version'],
            '--response-protocol', PROTOCOL]
    for value in task['required_capabilities']:
        args.extend(['--capability', value])
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['schema_version'] == PROTOCOL and result['task']['execution_ref'] == 'L1-cli'


def test_http_cancel_can_negotiate_receipt(tmp_path):
    from deck_master.web import WorkbenchServer
    from test_web import _session_token, _post_json
    project, task = _make_project(tmp_path)
    server = WorkbenchServer(project)
    try:
        url = server.start().rstrip('/')
        status, result = _post_json(url + '/api/cancel',
            {'task_id': task['task_id'], 'response_protocol': PROTOCOL},
            token=_session_token(url), origin=url)
        assert status == 200
        assert result['schema_version'] == PROTOCOL and result['task']['status'] == 'cancelled'
    finally:
        server.stop()


def _load_project(tmp_path, count):
    """Fixed six 16-KiB sources; duplicate only synthetic pending Task refs.

    Original task is dispatched through the public scoped editorial path.
    Clones are read-load fixtures, never model executions or adopted results.
    """
    tmp_path.mkdir(parents=True)
    material = []
    for index in range(6):
        source = tmp_path / f'material-{index}.txt'
        source.write_text(f'SOURCE-{index}-' + 'source body. ' * 1365)
        material.append(source)
    project = tmp_path / 'project'
    page = json.loads((ENVELOPES / 'compose.json').read_text())['pages'][0]
    service.create(project, brief='L1 receipt scaling', sources=material, draft={'pages': [page]})
    prepare_editorial_project(project)
    store = Store(project)
    task = dispatch(project, store, 'rewrite', ('p09',))
    document = store.load_document()
    for index in range(1, count):
        other = {**task, 'task_id': f'L1-load-task-{index}', 'operation_id': f'L1-load-operation-{index}'}
        document['tasks'].append(store.put_json_object(other))
    op = str(uuid.uuid4())
    bumped = bump_revision(document, {'operation_id': op, 'kind': 'task_update',
        'description': 'synthetic pending-task read workload', 'read_set': []})
    store.commit_change(base_revision=document['revision_id'], document=bumped, operation_id=op)
    return project, task


@pytest.mark.parametrize('count', [1, 13, 30])
def test_receipt_scaling_same_workload(tmp_path, monkeypatch, count):
    # Compare repeated claims on the same snapshot/workload. First claim warms
    # files; legacy running-claim fast path only returns one work order, so
    # measure response construction directly after that real mutation.
    project, task = _load_project(tmp_path / 'fixture', count)
    claim(project, task)
    store = Store(project)
    doc = store.load_document()
    current = tasks._lookup_task(doc, task['task_id'], store)
    decoded = 0
    original = Store.read_object_json
    def counted(self, *args, **kwargs):
        nonlocal decoded
        decoded += 1
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Store, 'read_object_json', counted)
    def build(protocol):
        result = service._response(status='running', document=doc, requested_action='task update',
            pending_tasks=service._pending_host_tasks(doc, store) if protocol is None else None)
        return service._task_receipt(result, current) if protocol else result
    rows = []
    for protocol in (None, PROTOCOL):
        build(protocol)  # one warm-up, excluded
        samples = []
        for _ in range(3):
            decoded = 0
            start = time.process_time_ns()
            result = build(protocol)
            cpu_ns = time.process_time_ns() - start
            samples.append({'cpu_ns': cpu_ns, 'object_json_reads': decoded,
                            'response_bytes': len(json.dumps(result, ensure_ascii=False).encode())})
        rows.append({'protocol': protocol or 'legacy', 'samples': samples})
    legacy = build(None)
    compact = build(PROTOCOL)
    assert len(legacy['pending_tasks']) == count
    assert all('SOURCE-0-' in json.dumps(item) for item in legacy['pending_tasks'])
    assert 'SOURCE-0-' not in json.dumps(compact)
    assert all(s['object_json_reads'] == 0 for s in rows[1]['samples'])
    assert rows[1]['samples'][0]['response_bytes'] < rows[0]['samples'][0]['response_bytes']
    result = {'pending_tasks': count, 'source_count': 6, 'source_characters_each': len('SOURCE-0-' + 'source body. ' * 1365),
              'scope': 'response construction only; warm-up then 3 samples, not end-to-end latency', 'rows': rows}
    (tmp_path / 'measurement.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


def test_compact_accept_uses_committed_snapshot_even_if_head_advances(tmp_path, monkeypatch):
    project, store, task, payload = pending(tmp_path)
    original = tasks.accept_result
    observed = {}
    def with_progress(*args, **kwargs):
        outcome = original(*args, **kwargs)
        observed['applied'] = outcome['revision_id']
        observed['current'] = advance(store)
        return outcome
    monkeypatch.setattr(tasks, 'accept_result', with_progress)
    response = submit(project, task, payload, response_protocol=PROTOCOL)
    assert response['revision_id'] == observed['applied']
    assert response['current_revision_id'] == observed['current']
    assert response['task']['status'] == 'completed'


@pytest.mark.parametrize('protocol', [None, PROTOCOL])
def test_stale_result_binding_unchanged_by_response_protocol(tmp_path, protocol):
    project, store, task, payload = pending(tmp_path)
    before = store.current_revision_id()
    with pytest.raises(tasks.TaskConflict):
        submit(project, task, payload, produced_against='0' * 64, response_protocol=protocol)
    assert store.current_revision_id() == before
