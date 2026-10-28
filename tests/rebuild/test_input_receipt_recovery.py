"""RC4 N1 synthetic engineering: actual state, byte and process boundaries."""
from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
import shutil
import uuid

import pytest

from deck_master import cli, content_ops, operations, service, source_uploads
from deck_master.errors import InputRevisionConflict
from deck_master.models import bump_revision, canonical_json_bytes, compute_input_digest, sha256_bytes
from deck_master.store import Store
from test_rc3_collaboration_adapters import http, http_server


def project(tmp_path, *, pages=False):
    root = tmp_path / 'project'
    draft = {'pages': [{'schema_version': 'deck_page_package.v2', 'page_id': 'p01',
        'customer_visible': {'title': 'Synthetic page bytes', 'body_blocks': []},
        'visual_spec': {'intent': 'Synthetic N1 immutable page check', 'reference_mode': 'new_design'}}]} if pages else None
    service.create(root, brief='Explicit synthetic N1 recovery fixture', draft=draft)
    return root, Store(root)


def saved_bytes(store):
    return {str(p.relative_to(store.deck_root)): p.read_bytes()
            for p in store.deck_root.rglob('*') if p.is_file() and p.name != 'project.lock'}


def advance(store, operation='unrelated'):
    doc = store.load_document()
    new = bump_revision(doc, {'kind': 'task_update', 'operation_id': operation,
                             'description': 'Synthetic later revision', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=new, operation_id=operation)
    return new


def update(root, store, patch=None, operation='plain-operation', base=None, **kw):
    return service.inputs_update(root, patch=patch or {'reason': 'Synthetic input', 'task_patch': {'audience': '测试 🙂'}},
                                 operation_id=operation, base_revision=base or store.current_revision_id(), **kw)


def deny_reads(monkeypatch):
    calls = {'material': 0, 'snapshot': 0, 'upload_resolve': 0, 'upload_show': 0}
    def fail(key):
        def read(*a, **kw):
            calls[key] += 1
            pytest.fail('replay attempted material read: ' + key)
        return read
    monkeypatch.setattr(service, '_read_patch_material', fail('material'))
    monkeypatch.setattr(service, 'read_source_snapshot', fail('snapshot'))
    monkeypatch.setattr(source_uploads, 'resolve', fail('upload_resolve'))
    monkeypatch.setattr(source_uploads, 'show', fail('upload_show'))
    return calls


def test_long_safe_id_atomic_flat_response_and_resolver_pure(tmp_path):
    root, store = project(tmp_path)
    base = store.current_revision_id()
    op = 'safe-' + 'a' * 155
    result = update(root, store, operation=op)
    assert result['status'] == 'updated' and result['pending_tasks']
    assert 'operation_result' not in result
    doc = store.load_document()
    assert doc['change']['operation_receipt']['response'] == result
    assert doc['change']['operation_receipt']['format'] == 'operation_receipt.v1'
    assert doc['parent_revision_id'] == base
    before = saved_bytes(store)
    lookup = operations.resolve_operation(store, op)
    assert lookup.state == 'committed' and lookup.head_revision == result['revision_id']
    assert lookup.stored_kind == 'input_update' and lookup.receipt_format == 'operation_receipt.v1'
    assert lookup.result == result and lookup.record['base_revision'] == base
    assert saved_bytes(store) == before
    shown = operations.show(root, operation_id=op)
    assert shown['operation_result'] == result and shown['committed_revision_id'] == result['revision_id']


@pytest.mark.parametrize('source_kind', ['add', 'replace', 'upload'])
@pytest.mark.parametrize('cache_damage', ['missing', 'corrupt'])
def test_replay_before_material_and_upload_reads(tmp_path, monkeypatch, source_kind, cache_damage):
    root, store = project(tmp_path)
    material = tmp_path / 'material.md'
    material.write_text('Explicit synthetic neutral source 一🙂\n')
    if source_kind == 'replace':
        update(root, store, {'reason': 'Register', 'source_changes': {'add': [{'path': str(material)}]}}, operation='register')
    if source_kind == 'upload':
        upload_id = 'upload-' + str(uuid.uuid4())
        source_uploads.receive(root, upload_id=upload_id, name='material.md', data=material.read_bytes())
        item = {'upload_id': upload_id}
        key = 'add'
    else:
        item, key = {'path': str(material)}, source_kind
    if source_kind == 'replace':
        item['source_id'] = store.load_document()['sources'][0]['source_id']
        material.write_text('Explicit synthetic changed source 二🙂\n')
    patch = {'reason': 'Register material', 'source_changes': {key: [item]}}
    base = store.current_revision_id()
    result = update(root, store, patch, base=base)
    advance(store)
    material.unlink()
    if source_kind == 'upload':
        shutil.rmtree(store.deck_root / 'workbench' / 'uploads')
    cache = store.deck_root / 'operations' / 'plain-operation.json'
    if cache_damage == 'missing':
        cache.unlink()
    else:
        cache.write_bytes(b'corrupt cache')
    before = saved_bytes(store)
    calls = deny_reads(monkeypatch)
    replay = update(root, store, patch, base=base)
    assert replay == {**result, 'replayed': True, 'current_revision_id': store.current_revision_id()}
    assert calls == dict.fromkeys(calls, 0)
    assert saved_bytes(store) == before
    assert len([d for d in operations.committed_snapshots(store) if d['change']['operation_id'] == 'plain-operation']) == 1


@pytest.mark.parametrize('phase', ['object', 'revision', 'before_pointer', 'after_pointer', 'cache'])
def test_atomic_fault_boundaries(tmp_path, monkeypatch, phase):
    from deck_master import store as module
    root, store = project(tmp_path)
    base = store.current_revision_id()
    patch = {'reason': 'Fault boundary', 'task_patch': {'audience': 'changed'}}
    original = module._atomic_write_bytes
    original_link = module.os.link
    def link(source, target):
        if phase == 'object' and store.staging_dir in Path(source).parents:
            raise OSError('Synthetic IO interruption')
        return original_link(source, target)
    monkeypatch.setattr(module.os, 'link', link)
    def write(path, data):
        if ((phase == 'object' and store.staging_dir in path.parents)
                or (phase == 'revision' and path.parent == store.revisions_dir)
                or (phase == 'before_pointer' and path.name == 'current.json')
                or (phase == 'cache' and path.parent.name == 'operations')):
            raise OSError('Synthetic IO interruption')
        original(path, data)
        if phase == 'after_pointer' and path.name == 'current.json':
            raise SystemExit('Synthetic process termination after pointer')
    monkeypatch.setattr(module, '_atomic_write_bytes', write)
    # operations imported its own cache writer, so cover that actual path too.
    monkeypatch.setattr(operations, '_atomic_write_bytes', write)
    if phase == 'cache':
        result = update(root, store, patch, base=base)
        assert result['journal_warning']['code'] == 'receipt_cache_unavailable'
    else:
        with pytest.raises((OSError, SystemExit)):
            update(root, store, patch, base=base)
    monkeypatch.setattr(module, '_atomic_write_bytes', original)
    monkeypatch.setattr(module.os, 'link', original_link)
    monkeypatch.setattr(operations, '_atomic_write_bytes', original)
    lookup = operations.resolve_operation(store, 'plain-operation')
    committed = phase in ('after_pointer', 'cache')
    assert lookup.state == ('committed' if committed else 'not_found')
    assert (store.current_revision_id() != base) == committed
    assert store.load_document()['task']['audience'] == ('changed' if committed else '')
    final = update(root, store, patch, base=base)
    assert final['revision_id'] == store.current_revision_id()
    assert final['status'] == 'updated'
    assert len([d for d in operations.committed_snapshots(store) if d['change']['operation_id'] == 'plain-operation']) == 1


def test_raw_binding_preserves_base_whitespace_unicode_and_path_context(tmp_path, monkeypatch):
    root, store = project(tmp_path)
    material = tmp_path / 'material.md'
    material.write_text('Synthetic material')
    patch = {'reason': '  原始 🙂e\u0301\n', 'source_changes': {'add': [{'path': 'material.md'}]}}
    base = store.current_revision_id()
    first = update(root, store, patch, base=base, patch_dir=tmp_path)
    deny_reads(monkeypatch)
    assert update(root, store, dict(reversed(list(patch.items()))), base=base, patch_dir=tmp_path)['revision_id'] == first['revision_id']
    for changed, changed_base, directory in [
        ({**patch, 'reason': patch['reason'].strip()}, base, tmp_path),
        ({**patch, 'reason': '  原始 🙂é\n'}, base, tmp_path),
        (patch, first['revision_id'], tmp_path),
        (patch, base, tmp_path / 'other')]:
        with pytest.raises(InputRevisionConflict) as error:
            update(root, store, changed, base=changed_base, patch_dir=directory)
        assert error.value.cause == 'operation_payload_conflict'
    assert store.current_revision_id() == first['revision_id']


@pytest.mark.parametrize('direction', ['ordinary_first', 'content_first'])
def test_cross_family_occupancy_and_content_digest_unchanged(tmp_path, direction):
    root, store = project(tmp_path)
    op = str(uuid.uuid4()); base = store.current_revision_id()
    patch = {'reason': 'No business change'}
    old_digest = operations.request_digest(store.load_document(), 'content.inputs', base, {'input': patch})
    if direction == 'ordinary_first':
        first = update(root, store, patch, operation=op, base=base)
        with pytest.raises(operations.OperationError) as error:
            content_ops.inputs(root, input=patch, operation_id=op, base_revision=base)
        assert error.value.error_code == 'operation_type_conflict'
    else:
        first = content_ops.inputs(root, input=patch, operation_id=op, base_revision=base)
        assert first['request_digest'] == old_digest
        assert first['status'] == 'committed'
        with pytest.raises(InputRevisionConflict) as error:
            update(root, store, patch, operation=op, base=base)
        assert error.value.cause == 'operation_type_conflict'
    assert operations.show(root, operation_id=op)['status'] == 'committed'
    assert store.current_revision_id() == first.get('revision_id', first.get('committed_revision_id'))


def legacy_fixture(root, store, patch, *, no_op=False, operation="legacy"):
    base = store.load_document()
    if not no_op:
        doc = bump_revision(base, {'kind': 'input_update', 'operation_id': operation,
                                 'description': 'Original synthetic pre-RC4 commit', 'read_set': []})
        doc['task']['audience'] = patch.get('task_patch', {}).get('audience', '')
        store.commit_change(base_revision=base['revision_id'], document=doc, operation_id=operation)
    normalized = service._normalize_input_patch(patch, patch_dir=Path.cwd())
    result = {'status': 'unchanged' if no_op else 'updated', 'revision_id': store.current_revision_id(), 'original': '旧结果'}
    service._write_input_operation(store, operation, sha256_bytes(canonical_json_bytes(normalized)), result)
    return result


@pytest.mark.parametrize('no_op', [True, False])
def test_legacy_original_digest_replay_projection_and_occupancy(tmp_path, no_op):
    root, store = project(tmp_path)
    patch = {'reason': '  Old reason  ', 'task_patch': {} if no_op else {'audience': 'old audience'}}
    result = legacy_fixture(root, store, patch, no_op=no_op)
    advance(store)
    before = saved_bytes(store)
    lookup = operations.resolve_operation(store, 'legacy')
    assert lookup.state == ('not_found' if no_op else 'unknown')
    if not no_op:
        assert lookup.reason == 'legacy_receipt_only'
    assert update(root, store, patch, operation='legacy', base='old-base-not-bound')['revision_id'] == result['revision_id']
    shown = operations.show(root, operation_id='legacy')
    assert shown['status'] == 'legacy_recorded' and shown['receipt_source'] == 'legacy_log'
    assert shown['operation_result'] == result and 'result_ref' not in shown
    operations.publish_index(store, {'operation_id': 'legacy', 'kind': 'input_update'})
    assert saved_bytes(store) == before
    # Internal content adapter must also reject a legacy-owned non-UUID identifier.
    with pytest.raises(operations.OperationError) as error:
        service._recover_input_request(store, 'legacy', 'irrelevant', patch, Path.cwd(), content=True)
    assert error.value.error_code == 'operation_type_conflict'
    assert saved_bytes(store) == before


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'unreachable', 'wrong_id', 'symlink'])
def test_legacy_unknown_does_not_read_material_or_rewrite_files(tmp_path, monkeypatch, damage):
    root, store = project(tmp_path)
    patch = {'reason': 'Legacy', 'task_patch': {'audience': 'old'}}
    legacy_fixture(root, store, patch)
    path = store.deck_root / 'operations' / 'legacy.json'
    if damage == 'missing':
        path.unlink()
    elif damage == 'corrupt':
        path.write_bytes(b'not JSON')
    elif damage == 'symlink':
        target = tmp_path / 'external.json'; target.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(target)
    else:
        data = json.loads(path.read_bytes())
        if damage == 'unreachable':
            data['result']['revision_id'] = 'orphan'
        else:
            data['operation_id'] = 'other'
        path.write_bytes(canonical_json_bytes(data))
    before = saved_bytes(store)
    deny_reads(monkeypatch)
    with pytest.raises(operations.OperationError) as error:
        update(root, store, patch, operation='legacy')
    assert error.value.error_code == 'operation_unverified'
    assert error.value.operation_state == 'unknown' and error.value.exit_code == 4
    assert saved_bytes(store) == before


def test_lost_legacy_noop_is_indistinguishable_and_not_fabricated(tmp_path):
    root, store = project(tmp_path)
    patch = {'reason': 'Original no-op'}
    legacy_fixture(root, store, patch, no_op=True)
    (store.deck_root / 'operations' / 'legacy.json').unlink()
    assert operations.resolve_operation(store, 'legacy').state == 'not_found'
    with pytest.raises(operations.OperationError) as error:
        operations.show(root, operation_id='legacy')
    assert error.value.error_code == 'operation_not_found'
    assert update(root, store, patch, operation='legacy')['status'] == 'unchanged'


@pytest.mark.parametrize('branch', ['noop', 'name', 'actual'])
def test_three_branches_atomic_and_replay_has_no_business_effects(tmp_path, branch):
    root, store = project(tmp_path, pages=True)
    material = tmp_path / 'material.md'; material.write_text('Synthetic source')
    update(root, store, {'reason': 'Register', 'source_changes': {'add': [{'path': str(material)}]}}, operation='register')
    before = store.load_document(); base = before['revision_id']
    patch = {'reason': 'Same inputs'}
    if branch == 'name':
        patch['source_changes'] = {'metadata': [{'source_id': before['sources'][0]['source_id'], 'name': 'Display name'}]}
    elif branch == 'actual':
        patch['task_patch'] = {'audience': 'changed'}
    result = update(root, store, patch, base=base)
    after = store.load_document()
    assert after['change']['operation_receipt']['response'] == result
    assert after['revision_id'] != before['revision_id']
    if branch != 'actual':
        assert result['status'] == 'unchanged'
        for key in ('pages', 'tasks', 'content_basis', 'reviews', 'outputs'):
            assert after.get(key) == before.get(key)
        assert compute_input_digest(after) == compute_input_digest(before)
    byte_state = saved_bytes(store)
    assert update(root, store, patch, base=base)['replayed'] is True
    assert saved_bytes(store) == byte_state


def _process_update(root, base, patch, gate, queue):
    gate.wait(10)
    try:
        result = service.inputs_update(root, patch=patch, base_revision=base, operation_id='process-race')
        queue.put(('success', result))
    except InputRevisionConflict as exc:
        queue.put(('conflict', exc.cause))
    except BaseException as exc:
        queue.put(('unexpected', repr(exc)))


@pytest.mark.parametrize('different', [False, True])
def test_independent_process_same_id_race(tmp_path, different):
    root, store = project(tmp_path)
    base = store.current_revision_id(); before_tasks = len(store.load_document()['tasks'])
    ctx = multiprocessing.get_context('spawn'); gate = ctx.Event(); queue = ctx.Queue()
    patches = [{'reason': 'Concurrent', 'task_patch': {'audience': 'first'}},
               {'reason': 'Concurrent', 'task_patch': {'audience': 'second' if different else 'first'}}]
    processes = [ctx.Process(target=_process_update, args=(root, base, patch, gate, queue)) for patch in patches]
    for p in processes:
        p.start()
    gate.set()
    results = [queue.get(timeout=30) for _ in processes]
    for p in processes:
        p.join(30)
        assert p.exitcode == 0
    assert sorted(r[0] for r in results) == (['conflict', 'success'] if different else ['success', 'success'])
    if not different:
        assert len({r[1]['revision_id'] for r in results}) == 1
        assert sum(bool(r[1].get('replayed')) for r in results) == 1
    assert len([d for d in operations.committed_snapshots(store) if d['change']['operation_id'] == 'process-race']) == 1
    assert len(store.load_document()['tasks']) == before_tasks + 1


@pytest.mark.parametrize('first_entry', ['cli', 'python', 'http'])
def test_python_cli_http_cross_entry_replay_and_conflict(tmp_path, monkeypatch, capsys, first_entry):
    root, store = project(tmp_path)
    base = store.current_revision_id()
    patch = {'reason': 'Same raw request', 'task_patch': {'audience': '原始 🙂'}}
    patch_file = tmp_path / 'patch.json'; patch_file.write_bytes(canonical_json_bytes(patch))
    monkeypatch.setattr(cli, '_project_has_pages', lambda *a: False)
    if first_entry == 'cli':
        assert cli.main(['inputs', 'update', '--project', str(root), '--patch', str(patch_file),
                         '--base-revision', base, '--operation-id', 'cross-entry']) == 0
        first = json.loads(capsys.readouterr().out)
    elif first_entry == 'python':
        first = update(root, store, patch, operation='cross-entry', base=base)
    else:
        with http_server(root) as url:
            status, first = http(url, '/api/inputs/update', {'patch': patch, 'base_revision': base, 'operation_id': 'cross-entry'})
        assert status == 200
    with http_server(root) as url:
        status, replay = http(url, '/api/inputs/update', {'patch': patch, 'base_revision': base, 'operation_id': 'cross-entry'})
        assert status == 200 and replay['revision_id'] == first['revision_id'] and replay['replayed']
        status, error = http(url, '/api/inputs/update', {'patch': patch, 'base_revision': first['revision_id'], 'operation_id': 'cross-entry'})
        assert status == 409 and error['error']['code'] == 'input_revision_conflict'
        assert error['error']['cause'] == 'operation_payload_conflict'
    assert update(root, store, patch, operation='cross-entry', base=base)['revision_id'] == first['revision_id']
    assert cli.main(['inputs', 'update', '--project', str(root), '--patch', str(patch_file),
                     '--base-revision', base, '--operation-id', 'cross-entry']) == 0
    assert json.loads(capsys.readouterr().out)['revision_id'] == first['revision_id']



def test_history_failure_is_unknown_unavailable_without_material_reads(tmp_path, monkeypatch):
    root, store = project(tmp_path)
    head = store.load_document(); ancestor = head['parent_revision_id']
    if ancestor is None:
        advance(store); head = store.load_document(); ancestor = head['parent_revision_id']
    (store.revisions_dir / (ancestor + '.json')).write_bytes(b'broken ancestor')
    deny_reads(monkeypatch)
    lookup = operations.resolve_operation(store, 'new-request')
    assert lookup.state == 'unknown' and lookup.reason == 'history_unreadable'
    with http_server(root) as url:
        status, result = http(url, '/api/inputs/update', {'patch': {'reason': 'Read failure'},
            'base_revision': head['revision_id'], 'operation_id': 'new-request'})
    assert status == 503 and result['error']['code'] == 'operation_unavailable'
    assert str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize('reason', ['request_paused', 'scope_exceeded', 'decision_needed', 'stale_base'])
def test_http_cli_python_preserve_business_reasons(tmp_path, monkeypatch, capsys, reason):
    from deck_master import eligibility
    from test_rc3_collaboration_adapters import new_project, instruction, write
    root = new_project(tmp_path); store = Store(root)
    if reason == 'request_paused':
        result, status, _ = write(root, 'pause', 'pause', request_id=store.load_document()['collaboration']['request']['request_id'],
            reason='Explicit synthetic pause', evidence=instruction())
        assert status == 200, result
    elif reason in ('scope_exceeded', 'decision_needed'):
        document = store.load_document()
        new = bump_revision(document, {'operation_id': 'control-fixture', 'kind': 'task_update',
            'description': 'Explicit synthetic control counterexample', 'read_set': []})
        if reason == 'scope_exceeded':
            new['collaboration']['request']['scope']['layers'] = ['review']
        else:
            new['collaboration']['request'] = None
        store.commit_change(base_revision=document['revision_id'], document=new, operation_id='control-fixture')
    base = store.current_revision_id() if reason != 'stale_base' else 'stale-revision'
    patch = {'reason': 'Business gate', 'task_patch': {'audience': 'Synthetic changed audience'}}
    before = saved_bytes(store)
    with pytest.raises((eligibility.EligibilityBlocked, InputRevisionConflict)) as error:
        update(root, store, patch, base=base)
    expected = 'input_revision_conflict' if reason == 'stale_base' else reason
    assert error.value.error_code == expected
    assert saved_bytes(store) == before
    with http_server(root) as url:
        status, ordinary = http(url, '/api/inputs/update', {'patch': patch, 'base_revision': base, 'operation_id': 'plain-operation'})
        assert status == 409 and ordinary['error']['code'] == expected
        if reason != 'stale_base':
            assert ordinary['error']['reason_codes'][0] == reason
            for field in ('reasons', 'responsible_role', 'next_action', 'decision_card', 'artifact_revision_id', 'control_revision_id'):
                assert field in ordinary['error']
            assert ordinary['error']['control_revision_id'] == store.current_revision_id()
        status, content = http(url, '/api/content/inputs', {'input': patch, 'base_revision': base, 'operation_id': str(uuid.uuid4())})
        assert status == 409 and content['error']['code'] == expected
    patch_file = tmp_path / 'patch.json'; patch_file.write_bytes(canonical_json_bytes(patch))
    monkeypatch.setattr(cli, '_project_has_pages', lambda *a: False)
    exit_code = cli.main(['inputs', 'update', '--project', str(root), '--patch', str(patch_file),
        '--base-revision', base, '--operation-id', 'plain-operation'])
    assert exit_code == (5 if reason == 'stale_base' else 4)
    cli_error = json.loads(capsys.readouterr().err)
    assert cli_error['error']['code'] == expected
    assert str(tmp_path) not in json.dumps(ordinary)
    assert saved_bytes(store) == before


@pytest.mark.parametrize('patch', [[], {'reason': ''}, {'reason': 'Bad', 'task_patch': []}, {'reason': 'Bad', 'unknown': True}])
def test_http_invalid_shape_has_structured_compatible_error(tmp_path, patch):
    root, store = project(tmp_path)
    before = saved_bytes(store)
    with http_server(root) as url:
        status, result = http(url, '/api/inputs/update', {'patch': patch, 'base_revision': store.current_revision_id(), 'operation_id': 'invalid'})
    assert status == 400 and result['error']['code'] == 'invalid_input'
    assert all(field in result['error'] for field in ('code', 'message', 'field', 'next_action'))
    assert saved_bytes(store) == before


def test_legacy_log_only_corruption_and_source_bindings_are_unverified(tmp_path, monkeypatch):
    root, store = project(tmp_path)
    patch = {'reason': 'Old no-op'}
    legacy_fixture(root, store, patch, no_op=True)
    path = store.deck_root / 'operations' / 'legacy.json'
    path.write_bytes(b'corrupt surviving old log')
    before = saved_bytes(store)
    deny_reads(monkeypatch)
    with pytest.raises(operations.OperationError) as error:
        update(root, store, patch, operation='legacy')
    assert error.value.error_code == 'operation_unverified'
    assert saved_bytes(store) == before
    with http_server(root) as url:
        status, response = http(url, '/api/inputs/update', {'patch': patch,
            'base_revision': store.current_revision_id(), 'operation_id': 'legacy'})
    assert status == 409 and response['error']['operation_state'] == 'unknown'
    assert response['error']['retryable'] is False
    assert str(tmp_path) not in json.dumps(response)


def test_legacy_file_normalization_does_not_reopen_old_sources(tmp_path, monkeypatch):
    root, store = project(tmp_path)
    material = tmp_path / 'material.md'; material.write_text('Old synthetic source')
    patch = {'reason': 'Old source binding', 'source_changes': {'add': [{'path': str(material)}]}}
    legacy_fixture(root, store, patch, no_op=True)
    material.unlink()
    before = saved_bytes(store)
    calls = deny_reads(monkeypatch)
    with pytest.raises(operations.OperationError) as error:
        update(root, store, patch, operation='legacy')
    assert error.value.error_code == 'operation_unverified'
    assert calls == dict.fromkeys(calls, 0)
    assert saved_bytes(store) == before


@pytest.mark.parametrize('no_op', [False, True])
def test_public_content_rejects_legacy_uuid_occupancy(tmp_path, no_op):
    root, store = project(tmp_path)
    patch = {'reason': 'Old ordinary protocol', 'task_patch': {'audience': 'old'}}
    operation = str(uuid.uuid4())
    legacy_fixture(root, store, patch, operation=operation, no_op=no_op)
    before = saved_bytes(store)
    with pytest.raises(operations.OperationError) as error:
        content_ops.inputs(root, input=patch, operation_id=operation, base_revision=store.current_revision_id())
    assert error.value.error_code == 'operation_type_conflict'
    assert saved_bytes(store) == before


@pytest.mark.parametrize('body,expected', [(b'{broken', 400), (b'[]', 422), (b'{}', 400)])
def test_old_http_json_and_field_status_mapping_is_preserved(tmp_path, body, expected):
    import urllib.error
    import urllib.request
    root, store = project(tmp_path)
    before = saved_bytes(store)
    with http_server(root) as url:
        request = urllib.request.Request(url + '/api/inputs/update', data=body, headers={
            'Origin': url, 'X-Deck-Token': 'explicit-synthetic-session', 'Content-Type': 'application/json'})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        result = json.loads(error.value.read())
    assert error.value.code == expected and result['error']['code'] == 'invalid_input'
    assert saved_bytes(store) == before


@pytest.mark.parametrize('operation_id', ['', '../unsafe', 'unsafe/id'])
def test_ordinary_unsafe_id_keeps_invalid_input_status(tmp_path, operation_id):
    root, store = project(tmp_path)
    with http_server(root) as url:
        status, result = http(url, '/api/inputs/update', {'patch': {'reason': 'Bad ID'},
            'base_revision': store.current_revision_id(), 'operation_id': operation_id})
    assert status == 400 and result['error']['code'] == 'invalid_input'


def test_material_parser_errors_do_not_publish_local_paths(tmp_path, capsys):
    root, store = project(tmp_path)
    missing = tmp_path / 'private-missing.md'
    patch = {'reason': 'Missing material', 'source_changes': {'add': [{'path': str(missing)}]}}
    base = store.current_revision_id(); before = saved_bytes(store)
    with http_server(root) as url:
        status, response = http(url, '/api/inputs/update', {'patch': patch, 'base_revision': base, 'operation_id': 'missing'})
    assert status == 422 and response['error']['code'] == 'source_unreadable'
    assert str(tmp_path) not in json.dumps(response)
    patch_file = tmp_path / 'patch.json'; patch_file.write_bytes(canonical_json_bytes(patch))
    assert cli.main(['inputs', 'update', '--project', str(root), '--patch', str(patch_file),
        '--base-revision', base, '--operation-id', 'missing']) == 2
    cli_error = json.loads(capsys.readouterr().err)
    assert cli_error['error']['code'] == 'source_unreadable'
    assert str(tmp_path) not in json.dumps(cli_error)
    assert saved_bytes(store) == before
