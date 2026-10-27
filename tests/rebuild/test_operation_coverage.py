"""SYNTHETIC_ENGINEERING: canonical history correctness and actual I/O counts."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import tracemalloc
import uuid

import pytest

from deck_master import operation_coverage as cache, operations, snapshots
from deck_master.models import bump_revision, canonical_json_bytes
from deck_master.store import Store
from test_workbench_operations import project, submit


@pytest.fixture(autouse=True)
def cold_process_cache():
    cache.clear()
    yield
    cache.clear()


def append(store, count=1, *, receipt=False):
    for _ in range(count):
        doc = store.load_document()
        op = str(uuid.uuid4())
        if receipt:
            submit(store, op, doc['revision_id'], {'synthetic': True})
        else:
            new = bump_revision(doc, {'operation_id': op, 'kind': 'task_update',
                                     'description': 'Synthetic no receipt', 'read_set': []})
            store.commit_change(base_revision=doc['revision_id'], document=new, operation_id=op)
    return store.current_revision_id()


class Counts:
    """Instrument actual bytes reads, filesystem stats and ALL json.loads calls.

    Count based on the decoded result, across every helper/module, so moving a
    decode to a helper cannot hide it. Object JSON reads are reported separately.
    """
    def __init__(self, monkeypatch):
        self.values = {}
        self.object_kinds = {}
        self.snapshot_reads = []
        self.snapshot_decodes = []
        original_loads, original_read, original_stat = json.loads, Path.read_bytes, Path.stat
        original_object = Store.read_object_bytes
        def loads(data, *args, **kwargs):
            result = original_loads(data, *args, **kwargs)
            if isinstance(result, dict):
                key = ('snapshot_decode' if result.get('schema_version') == 'deck_document.v1'
                       else 'receipt_decode' if result.get('schema_version') == 'operation_commit.v1'
                       else 'result_decode' if result.get('status') == 'saved' else 'other_decode')
                self.add(key)
                if key == 'snapshot_decode':
                    self.snapshot_decodes.append(result['revision_id'])
            return result
        def read(path):
            data = original_read(path)
            if path.parent.name == 'revisions':
                self.add('snapshot_read'); self.add('snapshot_bytes', len(data))
                self.snapshot_reads.append(path.stem)
            elif path.parent.name != '.deckmaster':
                self.add('object_read'); self.add('object_bytes', len(data))
                kind = self.object_kinds.get(str(path))
                if kind is not None:
                    self.add(kind + '_read'); self.add(kind + '_bytes', len(data))
            return data
        def stat(path, *args, **kwargs):
            if path.parent.name == 'revisions':
                self.add('snapshot_stat')
            return original_stat(path, *args, **kwargs)
        def object_bytes(store, ref):
            kind = self.object_kinds.get(str(store.project_root / ref['path']))
            if kind is not None:
                self.add(kind + '_reader')
            return original_object(store, ref)
        monkeypatch.setattr(Store, 'read_object_bytes', object_bytes)
        monkeypatch.setattr(json, 'loads', loads)
        monkeypatch.setattr(Path, 'read_bytes', read)
        monkeypatch.setattr(Path, 'stat', stat)
    def add(self, key, value=1):
        self.values[key] = self.values.get(key, 0) + value
    def run(self, function):
        self.values = {}
        self.snapshot_reads = []
        self.snapshot_decodes = []
        started = time.perf_counter()
        result = function()
        return result, {**dict.fromkeys(('snapshot_read', 'snapshot_decode', 'snapshot_bytes', 'snapshot_stat',
                        'receipt_read', 'receipt_bytes', 'receipt_decode', 'receipt_reader',
                        'result_read', 'result_bytes', 'result_decode', 'result_reader'), 0),
                        **self.values, 'elapsed_seconds': time.perf_counter() - started}


def save_evidence(name, value):
    target = os.environ.get('N4B_EVIDENCE_DIR')
    if target:
        directory = Path(target); directory.mkdir(parents=True, exist_ok=True)
        files = ['src/deck_master/operations.py', 'src/deck_master/snapshots.py',
                 'src/deck_master/operation_coverage.py', 'tests/rebuild/test_operation_coverage.py']
        value = {'scope': 'SYNTHETIC_ENGINEERING', 'source_sha': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'python': platform.python_version(),
            'platform': platform.platform(), 'executed_files_sha256': {
                p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}, **value}
        (directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def test_reader_warms_complete_coverage_without_resolver(tmp_path, monkeypatch):
    store = project(tmp_path)
    append(store, 523)
    cache.clear()
    counts = Counts(monkeypatch)
    cold, cold_count = counts.run(lambda: operations.OperationReader(store))
    warm, warm_count = counts.run(lambda: operations.OperationReader(store))
    save_evidence('reader-coverage.json', {'cold': cold_count, 'warm': warm_count})
    assert cold.coverage == warm.coverage
    assert cold_count['snapshot_decode'] == 524
    assert warm_count['snapshot_decode'] == 0
    assert warm_count['snapshot_stat'] >= 524  # Full ancestry guard remains.
    monkeypatch.setenv('DECK_MASTER_OPERATION_CACHE', '0')
    _, disabled = counts.run(lambda: operations.OperationReader(store))
    assert disabled['snapshot_decode'] == 524


def test_reader_does_not_publish_when_head_changes(tmp_path, monkeypatch):
    store = project(tmp_path)
    cache.clear()
    original = operations.OperationReader._check_head
    def changed(reader):
        append(store)
        original(reader)
    monkeypatch.setattr(operations.OperationReader, '_check_head', changed)
    with pytest.raises(ValueError, match='current changed'):
        operations.OperationReader(store)
    assert cache.get(cache.root_identity(store)) is None


def test_v2_completed_content_warms_history_without_a_resolver(tmp_path, monkeypatch):
    from deck_master import workbench
    from test_pr188_completed_content import completed_content
    project_path, store, _ = completed_content(tmp_path)
    append(store, 24)
    cache.clear()
    workbench._summary_cache.clear()
    counts = Counts(monkeypatch)
    cold, cold_count = counts.run(lambda: workbench.workbench_summary(project_path, protocol='workbench_summary.v2'))
    warm, warm_count = counts.run(lambda: workbench.workbench_summary(project_path, protocol='workbench_summary.v2'))
    assert cold == warm
    assert cache.get(cache.root_identity(store)) is not None
    assert cold_count['snapshot_decode'] - warm_count['snapshot_decode'] >= 24
    save_evidence('v2-reader-coverage.json', {'cold': cold_count, 'warm': warm_count})


@pytest.mark.parametrize('length', [100, 500, 1000])
def test_real_cold_hot_incremental_counts(tmp_path, monkeypatch, length):
    store = project(tmp_path)
    op = str(uuid.uuid4())
    original = submit(store, op, store.current_revision_id(), {'text': '原始 🙂\r\n'})
    append(store, length - 2)
    # The receipt is an old ancestor, so use the immutable location returned by
    # the real committed Document rather than guessing from operation ID.
    no_receipt_id = store.load_document()['change']['operation_id']
    receipt_document = snapshots._snapshot(store, original['committed_revision_id'])
    record_ref = receipt_document['change']['operation_commit']
    counts = Counts(monkeypatch)
    counts.object_kinds = {str(store.project_root / record_ref['path']): 'receipt',
                           str(store.project_root / original['result_ref']['path']): 'result'}
    canonical, canonical_count = counts.run(lambda: operations.resolve_operation(store, 'absent', use_cache=False))
    cache.clear()
    tracemalloc.start()
    cold, cold_count = counts.run(lambda: operations.resolve_operation(store, 'absent'))
    retained, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    assert cold == canonical and cold.state == 'not_found'
    assert cold_count['snapshot_decode'] == cold_count['snapshot_read'] == length
    assert canonical_count['snapshot_decode'] == length
    positive, canonical_positive_count = counts.run(lambda: operations.resolve_operation(store, op, use_cache=False))
    assert positive.result == original['operation_result']
    hot = []
    for index in range(10):
        missing, negative_counts = counts.run(lambda: operations.resolve_operation(store, f'absent-{index}'))
        found, positive_counts = counts.run(lambda: operations.resolve_operation(store, op))
        assert missing.state == 'not_found' and found == positive
        assert negative_counts.get('snapshot_decode', 0) == negative_counts.get('snapshot_read', 0) == 0
        assert positive_counts['snapshot_decode'] == positive_counts['snapshot_read'] == 1
        assert negative_counts['snapshot_stat'] >= length and positive_counts['snapshot_stat'] >= length
        assert positive_counts['receipt_decode'] == positive_counts['result_decode'] == 1
        assert positive_counts['receipt_reader'] == positive_counts['result_reader'] == 1
        hot.append({'negative': negative_counts, 'positive': positive_counts})
    incremental = []
    for delta in [1, 10]:
        append(store, delta)
        found, measured = counts.run(lambda: operations.resolve_operation(store, op))
        assert measured['snapshot_decode'] == measured['snapshot_read'] == delta + 1
        compare = operations.resolve_operation(store, op, use_cache=False)
        assert found == compare and found.result == original['operation_result']
        incremental.append({'delta': delta, 'positive': measured})
    no_receipt_cached = operations.resolve_operation(store, no_receipt_id)
    no_receipt_canonical = operations.resolve_operation(store, no_receipt_id, use_cache=False)
    assert no_receipt_cached == no_receipt_canonical and no_receipt_cached.state == 'unknown'
    assert not cache._cache
    save_evidence(f'N4B-counts-{length}.json', {'history_length': length, 'cache_mode': 'enabled/canonical-control',
        'cold_negative': cold_count, 'canonical_negative': canonical_count,
        'no_receipt_cached': asdict(no_receipt_cached), 'no_receipt_canonical': asdict(no_receipt_canonical),
        'canonical_positive': canonical_positive_count, 'hot': hot, 'incremental': incremental,
        'retained_bytes_after_build': retained, 'peak_build_bytes': peak,
        'limits': {'projects': cache.MAX_PROJECTS, 'total_revisions': cache.MAX_REVISIONS},
        'note': 'O(H) stat remains; receipt/result reader calls and JSON decodes are separate from filesystem byte reads (Store already has a signature-verified small-object byte cache). Tracemalloc includes instrumentation and transient build metadata.'})


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'foreign', 'cycle', 'symlink', 'missing_parent_field', 'missing_change', 'bad_change_ref'])
def test_canonical_damage_never_proves_absence(tmp_path, damage):
    store = project(tmp_path); first = store.load_document(); append(store, 2)
    assert operations.resolve_operation(store, 'absent').state == 'not_found'
    path = store.revisions_dir / (first['revision_id'] + '.json')
    if damage == 'missing':
        path.unlink()
    elif damage == 'corrupt':
        path.write_bytes(b'{broken')
    elif damage == 'symlink':
        original = path.read_bytes(); path.unlink(); other = tmp_path / 'copy.json'; other.write_bytes(original); path.symlink_to(other)
    else:
        doc = json.loads(path.read_bytes())
        if damage == 'foreign': doc['project_id'] = 'foreign'
        elif damage == 'cycle': doc['parent_revision_id'] = store.current_revision_id()
        elif damage == 'missing_change': del doc['change']
        elif damage == 'bad_change_ref': doc['change']['operation_commit'] = {'path': '/foreign'}
        else: del doc['parent_revision_id']
        path.write_bytes(canonical_json_bytes(doc))
    outcomes = [asdict(operations.resolve_operation(store, 'absent', use_cache=enabled))
                for enabled in [True, False, True]]
    assert all(result['state'] == 'unknown' for result in outcomes)
    assert not cache._cache
    save_evidence(f'N4B-fault-{damage}.json', {'damage': damage, 'cache_modes': [True, False, True],
        'outcomes': outcomes, 'current_revision_id': store.current_revision_id(),
        'fault_revision_id': first['revision_id'],
        'fault_bytes_sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None})


def test_hot_replacement_and_orphan_do_not_create_commit(tmp_path):
    store = project(tmp_path); head = store.current_revision_id()
    operations.resolve_operation(store, 'absent')
    orphan = bump_revision(store.load_document(), {'operation_id': 'forged', 'kind': 'task_update',
                                                'description': 'Orphan', 'read_set': []})
    (store.revisions_dir / (orphan['revision_id'] + '.json')).write_bytes(canonical_json_bytes(orphan))
    assert operations.resolve_operation(store, 'forged').state == 'not_found'
    assert operations.resolve_operation(store, 'forged', head_revision=orphan['revision_id']).state == 'unknown'
    path = store.revisions_dir / (head + '.json')
    changed = json.loads(path.read_bytes()); changed['parent_revision_id'] = 'missing'
    replacement = path.with_suffix('.replacement'); replacement.write_bytes(canonical_json_bytes(changed)); replacement.replace(path)
    assert operations.resolve_operation(store, 'absent').state == 'unknown'


def test_result_corruption_is_rechecked_on_hot_positive(tmp_path):
    store = project(tmp_path); op = str(uuid.uuid4())
    saved = submit(store, op, store.current_revision_id(), {})
    operations.resolve_operation(store, 'absent')
    path = store.project_root / saved['result_ref']['path']
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(b'{broken')
    outcome = operations.resolve_operation(store, op)
    assert outcome.state == 'unknown'
    assert not cache._cache
    save_evidence('N4B-fault-result.json', {'outcome': asdict(outcome), 'original_result_sha256': original_hash,
        'corrupt_result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'current_revision_id': store.current_revision_id()})


def test_duplicate_ids_are_unknown(tmp_path):
    store = project(tmp_path); op = str(uuid.uuid4())
    submit(store, op, store.current_revision_id(), {})
    doc = store.load_document(); new = bump_revision(doc, {'operation_id': op, 'kind': 'task_update',
                                                          'description': 'Duplicate', 'read_set': []})
    # Fault injection bypasses writer deduplication, without pretending a hint is a commit.
    (store.revisions_dir / (new['revision_id'] + '.json')).write_bytes(canonical_json_bytes(new))
    (store.deck_root / 'current.json').write_bytes(canonical_json_bytes({'format': 'deckmaster-current.v1', 'revision_id': new['revision_id']}))
    assert operations.resolve_operation(store, op).state == 'unknown'


def test_forged_disk_hint_and_legacy_log_are_never_trust(tmp_path):
    store = project(tmp_path); op = str(uuid.uuid4()); saved = submit(store, op, store.current_revision_id(), {})
    legacy = store.deck_root / 'operations' / 'legacy.json'; legacy.parent.mkdir(exist_ok=True)
    original = b'{"kind":"input_update","request_sha256":"keep-original"}'
    legacy.write_bytes(original)
    hint = store.deck_root / 'cache' / 'operation-lookup.v1.json'; hint.parent.mkdir()
    pointer = (store.deck_root / 'current.json').read_bytes()
    for content in [b'', b'{broken', canonical_json_bytes({'complete': True, 'operations': {op: 'orphan', 'fake': saved['committed_revision_id']},
                                                        'checksum': hashlib.sha256(b'forged').hexdigest()})]:
        hint.write_bytes(content); cache.clear()
        assert operations.resolve_operation(store, op).result == saved['operation_result']
        assert operations.resolve_operation(store, op, use_cache=False).result == saved['operation_result']
        assert operations.resolve_operation(store, 'fake').state == 'not_found'
        assert hint.read_bytes() == content and legacy.read_bytes() == original
        assert (store.deck_root / 'current.json').read_bytes() == pointer
    save_evidence('N4B-forged-hints.json', {'cases': ['empty', 'truncated', 'forged-complete-map-checksum'],
        'atomic_result_equal': True, 'fake_operation_state': 'not_found',
        'legacy_bytes_sha256_before_after': hashlib.sha256(original).hexdigest(),
        'pointer_bytes_sha256_before_after': hashlib.sha256(pointer).hexdigest()})


def test_explicit_head_is_validated_without_double_decode(tmp_path, monkeypatch):
    store = project(tmp_path); old = store.current_revision_id(); append(store, 5)
    counts = Counts(monkeypatch)
    result, measured = counts.run(lambda: operations.resolve_operation(store, 'absent', head_revision=old))
    assert result.state == 'not_found' and result.head_revision == old
    assert measured['snapshot_decode'] == 6
    hot, measured = counts.run(lambda: operations.resolve_operation(store, 'absent', head_revision=old))
    assert hot == result and measured.get('snapshot_decode', 0) == 0


def test_pointer_race_bounded_retry_and_unknown(tmp_path, monkeypatch):
    store = project(tmp_path); append(store)
    real = cache.current_head
    reads = []
    def moving(store):
        reads.append(1)
        if len(reads) in [2, 4]: append(store)
        return real(store)
    monkeypatch.setattr(cache, 'current_head', moving)
    result = operations.resolve_operation(store, 'absent')
    assert result.state == 'unknown' and result.reason == 'current_changed' and len(reads) == 4
    assert operations.lookup_error(result, 'absent').http_status == 503
    assert not cache._cache
    monkeypatch.setattr(cache, 'current_head', real)
    assert operations.resolve_operation(store, 'absent').head_revision == real(store)


def test_projects_copy_eviction_and_disable(tmp_path, monkeypatch):
    store = project(tmp_path / 'original'); append(store, 2)
    operations.resolve_operation(store, 'absent')
    copy = tmp_path / 'copy'; shutil.copytree(store.project_root, copy); copied = Store(copy)
    counts = Counts(monkeypatch)
    found, measured = counts.run(lambda: operations.resolve_operation(copied, 'absent'))
    assert found.state == 'not_found' and measured['snapshot_decode'] == 3
    monkeypatch.setattr(cache, 'MAX_PROJECTS', 1)
    cache.publish(cache.get(cache.root_identity(copied)))
    _, measured = counts.run(lambda: operations.resolve_operation(store, 'absent'))
    assert measured['snapshot_decode'] == 3
    monkeypatch.setenv('DECK_MASTER_OPERATION_CACHE', '0')
    _, measured = counts.run(lambda: operations.resolve_operation(store, 'absent'))
    assert measured['snapshot_decode'] == 3
    cache.clear(); monkeypatch.setattr(cache, 'MAX_REVISIONS', 2)
    operations.resolve_operation(store, 'absent', use_cache=True)
    partial = cache.get(cache.root_identity(store))
    assert not partial.complete and len(partial.headers) == 2


def _child_query(root, queue):
    # A fork must not import the parent's verified coverage as trust.
    original = snapshots.snapshot_evidence
    decoded = []
    def count(*args): decoded.append(1); return original(*args)
    snapshots.snapshot_evidence = count
    result = operations.resolve_operation(Store(root), 'absent')
    queue.put((asdict(result), len(decoded)))


def test_forked_process_builds_own_coverage(tmp_path):
    store = project(tmp_path); append(store, 5)
    parent = operations.resolve_operation(store, 'absent')
    ctx = multiprocessing.get_context('fork'); queue = ctx.Queue()
    process = ctx.Process(target=_child_query, args=(store.project_root, queue)); process.start(); process.join(30)
    assert process.exitcode == 0
    result, count = queue.get(timeout=3)
    assert result == asdict(parent) and count == 6
    save_evidence('N4B-process-cold.json', {'child_outcome': result, 'parent_outcome': asdict(parent),
        'child_snapshot_decode': count, 'history_length': 6, 'start_method': 'fork'})


def test_missing_nanosecond_signature_uses_canonical_each_time(tmp_path, monkeypatch):
    store = project(tmp_path); append(store, 3)
    real = snapshots.snapshot_signature
    def weak(store, revision):
        real(store, revision)
        return None
    monkeypatch.setattr(snapshots, 'snapshot_signature', weak)
    counts = Counts(monkeypatch)
    for _ in range(2):
        result, measured = counts.run(lambda: operations.resolve_operation(store, 'absent'))
        assert result.state == 'not_found' and measured['snapshot_decode'] == 4
        assert not cache._cache


def _child_append(root):
    append(Store(root))


def _child_commit_operation(root, operation_id):
    store = Store(root)
    submit(store, operation_id, store.current_revision_id(), {'race_target': True})


@pytest.mark.parametrize('commit_target', [False, True])
def test_other_process_advances_during_read_then_retry_fixes_head(tmp_path, monkeypatch, commit_target):
    store = project(tmp_path); append(store, 3)
    previous = store.current_revision_id()
    operation_id = str(uuid.uuid4()) if commit_target else 'absent'
    assert operations.resolve_operation(store, operation_id).state == 'not_found'
    real = cache.current_head
    reads = []
    def moving(store):
        reads.append(1)
        if len(reads) == 2:
            target = _child_commit_operation if commit_target else _child_append
            args = (store.project_root, operation_id) if commit_target else (store.project_root,)
            process = multiprocessing.get_context('fork').Process(target=target, args=args)
            process.start(); process.join(30)
            assert process.exitcode == 0
        return real(store)
    monkeypatch.setattr(cache, 'current_head', moving)
    result = operations.resolve_operation(store, operation_id)
    assert result.state == ('committed' if commit_target else 'not_found')
    assert result.head_revision != previous
    assert result.head_revision == store.current_revision_id() and len(reads) == 4
    if commit_target:
        assert result.committed_revision_id == result.head_revision
        assert result.result['value'] == {'race_target': True}
    name = 'N4B-process-target-commit.json' if commit_target else 'N4B-process-current-advance.json'
    save_evidence(name, {'old_control': previous, 'operation_id': operation_id,
        'returned': asdict(result), 'current_revision_id': store.current_revision_id(),
        'safe_current_captures': len(reads), 'child_exitcode': 0,
        'note': 'child commits the previously absent target' if commit_target else
                'child appends an unrelated revision; bounded retry returns new verified head'})


def test_strict_resolver_does_not_write_or_publish(tmp_path, monkeypatch):
    store = project(tmp_path); op = str(uuid.uuid4())
    saved = submit(store, op, store.current_revision_id(), {})
    before = {str(p.relative_to(store.deck_root)): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail('pure resolver attempted persistent write')
    monkeypatch.setattr(operations, 'publish_index', forbidden)
    monkeypatch.setattr(operations, '_atomic_write_bytes', forbidden)
    for enabled in [True, False, True]:
        assert operations.resolve_operation(store, op, use_cache=enabled).result == saved['operation_result']
        assert operations.resolve_operation(store, 'absent', use_cache=enabled).state == 'not_found'
    after = {str(p.relative_to(store.deck_root)): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()}
    assert before == after


def test_store_receipt_wrapper_has_one_cold_scan(tmp_path, monkeypatch):
    store = project(tmp_path); append(store, 11); cache.clear()
    counts = Counts(monkeypatch)
    result, measured = counts.run(lambda: store.operation_receipt('absent'))
    assert result is None and measured['snapshot_decode'] == measured['snapshot_read'] == 12
    result, measured = counts.run(lambda: store.operation_receipt('another-absent'))
    assert result is None and measured['snapshot_decode'] == measured['snapshot_read'] == 0


@pytest.mark.parametrize('old_damage', ['unchanged', 'missing', 'corrupt_replacement', 'symlink'])
@pytest.mark.parametrize('reader', [False, True])
def test_divergent_history_rebuilds_without_merging_unreachable_operations(tmp_path, old_damage, reader):
    store = project(tmp_path); base = store.load_document()
    op = str(uuid.uuid4()); saved = submit(store, op, base['revision_id'], {})
    if reader:
        operations.OperationReader(store)
    else:
        operations.resolve_operation(store, 'absent')
    # Replace the control with a different valid branch from the same root,
    # reusing the operation ID only on that selected ancestry. Cached branch
    # metadata must not make this appear to be two committed occurrences.
    branch = bump_revision(base, {'operation_id': op, 'kind': 'task_update',
                                 'description': 'Selected divergent ancestry', 'read_set': []})
    (store.revisions_dir / (branch['revision_id'] + '.json')).write_bytes(canonical_json_bytes(branch))
    (store.deck_root / 'current.json').write_bytes(canonical_json_bytes({'format': 'deckmaster-current.v1', 'revision_id': branch['revision_id']}))
    old_path = store.revisions_dir / (saved['committed_revision_id'] + '.json')
    if old_damage == 'missing':
        old_path.unlink()
    elif old_damage == 'corrupt_replacement':
        replacement = old_path.with_suffix('.replacement')
        replacement.write_bytes(b'{broken'); replacement.replace(old_path)
    elif old_damage == 'symlink':
        external = tmp_path / 'old-unreachable.json'; external.write_bytes(old_path.read_bytes())
        old_path.unlink(); old_path.symlink_to(external)
    pointer = (store.deck_root / 'current.json').read_bytes()
    logs = {path.name: path.read_bytes() for path in (store.deck_root / 'operations').glob('*.json')}
    # The first cache-enabled lookup must fall back from stale coverage, not
    # report unknown merely because an unreachable old snapshot is unreadable.
    assert cache.get(cache.root_identity(store)).head == saved['committed_revision_id']
    first_enabled = (operations.OperationReader(store).resolve('absent') if reader else
                     operations.resolve_operation(store, 'absent'))
    canonical_absent = operations.resolve_operation(store, 'absent', use_cache=False)
    assert first_enabled == canonical_absent
    assert first_enabled.state == 'not_found' and first_enabled.head_revision == branch['revision_id']
    assert (store.deck_root / 'current.json').read_bytes() == pointer
    assert {path.name: path.read_bytes() for path in (store.deck_root / 'operations').glob('*.json')} == logs
    save_evidence(f'N4B-stale-coverage-{old_damage}.json', {'old_unreachable_damage': old_damage,
        'first_enabled': asdict(first_enabled), 'canonical': asdict(canonical_absent),
        'pointer_bytes_sha256_before_after': hashlib.sha256(pointer).hexdigest(),
        'operations_log_sha256_before_after': {name: hashlib.sha256(raw).hexdigest() for name, raw in logs.items()}})
    enabled = operations.resolve_operation(store, op)
    canonical = operations.resolve_operation(store, op, use_cache=False)
    assert enabled == canonical and enabled.reason == 'legacy_receipt_only'
    assert enabled.committed_revision_id == branch['revision_id']
    # A new complete root also cannot inherit operation IDs from the old chain.
    branch['parent_revision_id'] = None
    branch['change']['operation_id'] = 'different'
    (store.revisions_dir / (branch['revision_id'] + '.json')).write_bytes(canonical_json_bytes(branch))
    operations.resolve_operation(store, 'absent')
    assert operations.resolve_operation(store, op).state == 'not_found'


@pytest.mark.parametrize('newer', [0, 4])
@pytest.mark.parametrize('warm', [False, True])
def test_show_reuses_single_lookup_and_matching_document(tmp_path, monkeypatch, newer, warm):
    store = project(tmp_path); op = str(uuid.uuid4())
    saved = submit(store, op, store.current_revision_id(), {}); append(store, newer)
    if warm:
        operations.resolve_operation(store, 'absent')
    else:
        cache.clear()
    counts = Counts(monkeypatch)
    entry_reads, lookups = [], []
    original_load, original_resolve = snapshots.load_snapshot, operations.resolve_operation
    def measured_call(function, observations, *args, **kwargs):
        before = counts.values.copy()
        value = function(*args, **kwargs)
        observations.append({key: counts.values.get(key, 0) - before.get(key, 0)
                             for key in ('snapshot_read', 'snapshot_decode')})
        return value
    def load(*args, **kwargs):
        return measured_call(original_load, entry_reads, *args, **kwargs)
    def resolve(*args, **kwargs):
        return measured_call(original_resolve, lookups, *args, **kwargs)
    monkeypatch.setattr(snapshots, 'load_snapshot', load)
    monkeypatch.setattr(operations, 'resolve_operation', resolve)
    result, measured = counts.run(lambda: operations.show(store.project_root, operation_id=op))
    assert result['operation_result'] == saved['operation_result']
    # N4 §5.3 / AC09 limits I01's historical reads. The public entry also
    # validates the current Document before it may publish a derived index.
    # Count both scopes, including the current read. A current receipt reuses
    # that verified evidence; an old receipt needs its own immutable Document.
    assert entry_reads == [{'snapshot_read': 1, 'snapshot_decode': 1}]
    resolver_reads = (int(newer > 0) if warm else newer + 1)
    assert lookups == [{'snapshot_read': resolver_reads, 'snapshot_decode': resolver_reads}]
    assert measured['snapshot_read'] == measured['snapshot_decode'] == resolver_reads + 1
    assert counts.snapshot_reads == counts.snapshot_decodes
    assert len(set(counts.snapshot_reads)) == len(counts.snapshot_reads)
    assert counts.snapshot_reads[0] == store.current_revision_id()
    if warm:
        expected = [store.current_revision_id()]
        if newer:
            expected.append(saved['committed_revision_id'])
        assert counts.snapshot_reads == expected
    else:
        assert len(counts.snapshot_reads) == newer + 2
    save_evidence(f'N4B-show-read-scopes-{newer}-{"warm" if warm else "cold"}.json', {
        'cache_mode': 'warm' if warm else 'cold', 'newer_revisions': newer, 'public_entry_total': measured,
        'entry_current_validation': entry_reads, 'i01_resolver': lookups,
        'snapshot_read_revisions': counts.snapshot_reads, 'snapshot_decode_revisions': counts.snapshot_decodes,
        'note': 'one I01 call; every canonical snapshot read/decoded at most once across the complete public entry'})


@pytest.mark.parametrize('damage', ['pointer_symlink', 'snapshot_symlink', 'corrupt_snapshot', 'missing_snapshot', 'invalid_schema'])
def test_show_validates_current_before_lookup_or_index_publication(tmp_path, monkeypatch, damage):
    store = project(tmp_path); op = str(uuid.uuid4())
    saved = submit(store, op, store.current_revision_id(), {}); append(store, 2)
    operations.resolve_operation(store, 'absent')
    pointer = store.deck_root / 'current.json'
    current = store.revisions_dir / (store.current_revision_id() + '.json')
    receipt = store.deck_root / 'operations' / (op + '.json')
    receipt_before = hashlib.sha256(receipt.read_bytes()).hexdigest()
    if damage in ('pointer_symlink', 'snapshot_symlink'):
        target = pointer if damage == 'pointer_symlink' else current
        external = tmp_path / 'external.json'
        external.write_bytes(target.read_bytes()); target.unlink(); target.symlink_to(external)
    elif damage == 'corrupt_snapshot':
        current.write_bytes(b'{broken')
    elif damage == 'invalid_schema':
        doc = json.loads(current.read_bytes()); doc['collaboration'] = ['invalid']
        current.write_bytes(canonical_json_bytes(doc))
    else:
        current.unlink()
    pointer_before = hashlib.sha256(pointer.read_bytes()).hexdigest()
    def forbidden(*args, **kwargs):
        pytest.fail('unsafe current must be rejected before lookup or index publication')
    monkeypatch.setattr(operations, 'resolve_operation', forbidden)
    monkeypatch.setattr(operations, 'publish_index', forbidden)
    with pytest.raises(operations.OperationError) as error:
        operations.show(store.project_root, operation_id=op)
    assert error.value.error_code == 'operation_unavailable'
    assert error.value.http_status == 503 and error.value.operation_state == 'unknown'
    assert hashlib.sha256(pointer.read_bytes()).hexdigest() == pointer_before
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == receipt_before
    save_evidence(f'N4B-entry-safety-{damage}.json', {'damage': damage,
        'outcome': error.value.payload(), 'committed_revision_id': saved['committed_revision_id'],
        'pointer_bytes_sha256_before_after': pointer_before, 'receipt_bytes_sha256_before_after': receipt_before,
        'lookup_calls': 0, 'index_publications': 0})


@pytest.mark.parametrize('damage', ['rewrite', 'replace', 'symlink'])
def test_show_request_evidence_rechecks_signature_after_entry(tmp_path, monkeypatch, damage):
    store = project(tmp_path); op = str(uuid.uuid4())
    saved = submit(store, op, store.current_revision_id(), {})
    operations.resolve_operation(store, 'absent')
    current = store.revisions_dir / (store.current_revision_id() + '.json')
    real = operations.resolve_operation
    def change_before_lookup(*args, **kwargs):
        if damage == 'rewrite':
            current.write_bytes(b'{broken')
        elif damage == 'replace':
            replacement = current.with_suffix('.replacement')
            replacement.write_bytes(b'{broken'); replacement.replace(current)
        else:
            external = tmp_path / 'external.json'; external.write_bytes(current.read_bytes())
            current.unlink(); current.symlink_to(external)
        return real(*args, **kwargs)
    monkeypatch.setattr(operations, 'resolve_operation', change_before_lookup)
    def forbidden(*args, **kwargs):
        pytest.fail('changed snapshot must not publish an old successful result')
    monkeypatch.setattr(operations, 'publish_index', forbidden)
    with pytest.raises(operations.OperationError) as error:
        operations.show(store.project_root, operation_id=op)
    assert error.value.error_code == 'operation_unavailable' and error.value.operation_state == 'unknown'
    assert not cache._cache
    save_evidence(f'N4B-entry-race-{damage}.json', {'damage': damage, 'outcome': error.value.payload(),
        'original_committed_revision_id': saved['committed_revision_id'], 'index_publications': 0})


def test_show_request_evidence_does_not_reuse_weak_signatures(tmp_path, monkeypatch):
    store = project(tmp_path); op = str(uuid.uuid4())
    saved = submit(store, op, store.current_revision_id(), {})
    original_signature = snapshots.snapshot_signature
    def weak(*args):
        original_signature(*args)
        return None
    monkeypatch.setattr(snapshots, 'snapshot_signature', weak)
    counts = Counts(monkeypatch)
    observations = []
    for _ in range(2):
        result, measured = counts.run(lambda: operations.show(store.project_root, operation_id=op))
        assert result['operation_result'] == saved['operation_result']
        assert measured['snapshot_read'] == measured['snapshot_decode'] == 3
        assert not cache._cache
        observations.append(measured)
    save_evidence('N4B-entry-weak-signatures.json', {'observations': observations,
        'note': 'two reachable snapshots plus current-entry validation, reread on each request; weak signatures confer no reuse'})
