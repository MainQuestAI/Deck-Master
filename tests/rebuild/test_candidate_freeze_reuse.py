"""Synthetic cache safety/count tests; no claim of actual renderer acceptance."""
from pathlib import Path

import pytest

from deck_master import candidate_preview as preview
from deck_master.local_state import write_json
from deck_master.operations import OperationError
from test_candidate_preview_recovery import context, cached_report, state_path  # noqa: F401
from test_icon_quality import icon_store  # noqa: F401


def ready(context):
    report = cached_report(context)
    write_json(state_path(context), {'status': 'ready', 'cache_key': context[-1], 'check_id': report['check_id']})
    return report


def test_download_reuses_verified_target_and_status_does_not_collect_package(context, monkeypatch):
    ready(context)
    reads = []
    original = Path.read_bytes
    def read(path):
        if path.parent == state_path(context).parent and path.name in preview._FILES:
            reads.append(path.name)
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', read)
    raw, _ = preview.file_bytes(context[0].project_root, cache_key=context[-1], name='candidate.png')
    assert raw == b'original candidate.png'
    assert sorted(reads) == sorted(preview._FILES)
    retained = {}
    assert preview._cached(context[0], context[-1], context[-2], verified_files=retained, retain_name='candidate.png')
    assert retained == {'candidate.png': raw}


def test_ordinary_preview_validation_retains_only_one_raw_file(context):
    import hashlib
    import tracemalloc
    report = ready(context)
    folder = state_path(context).parent
    for name in preview._FILES:
        raw = b'x' * (8 * 1024 * 1024)
        (folder / name).write_bytes(raw)
        report['files'][name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    write_json(folder / 'report.json', report)
    del raw
    tracemalloc.start()
    try:
        assert preview._cached(context[0], context[-1], context[-2]) == report
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 12 * 1024 * 1024


def test_freeze_constructs_one_context_and_reads_each_verified_byte_once(context, monkeypatch):
    report = ready(context)
    calls = {'contexts': 0, 'file_reads': 0}
    original_context, read = preview._context, Path.read_bytes

    def counted_context(*args):
        calls['contexts'] += 1
        return original_context(*args)

    def counted_read(path):
        if path.parent == state_path(context).parent and path.name in preview._FILES:
            calls['file_reads'] += 1
        return read(path)

    monkeypatch.setattr(preview, '_context', counted_context)
    monkeypatch.setattr(Path, 'read_bytes', counted_read)
    frozen = context[0].read_object_json(preview.freeze_check(context[0], 'candidate'))
    assert frozen['check_id'] == report['check_id']
    for name, record in frozen['files'].items():
        assert context[0].read_object_bytes(record['file']) == ('original ' + name).encode()
    assert calls == {'contexts': 1, 'file_reads': 4}


@pytest.mark.parametrize('damage', ['bytes', 'size', 'check_id', 'toolchain', 'cancelled'])
def test_freeze_rejects_changed_cache_facts(context, damage):
    report = ready(context)
    folder = state_path(context).parent
    if damage == 'bytes':
        (folder / 'candidate.png').write_bytes(b'changed')
    elif damage == 'size':
        report['files']['candidate.png']['bytes'] += 1
        write_json(folder / 'report.json', report)
    elif damage == 'toolchain':
        report['identity'] = {**report['identity'], 'tools': {'different': 'toolchain'}}
        write_json(folder / 'report.json', report)
    else:
        write_json(state_path(context), {'status': 'interrupted' if damage == 'cancelled' else 'ready',
                   'cache_key': context[-1], 'check_id': 'superseded-check'})
    with pytest.raises(OperationError):
        preview.freeze_check(context[0], 'candidate')


def test_freeze_persists_validated_bytes_even_if_external_writer_changes_cache(context, monkeypatch):
    ready(context)
    store = context[0]
    original = store.put_blob
    mutated = []

    def mutate_after_validation(raw, *, ext, **kwargs):
        if not mutated:
            # Uncooperative external writer: the adopted proof must contain the
            # already verified snapshot, never re-read changed bytes unchecked.
            (state_path(context).parent / 'candidate.png').write_bytes(b'outside mutation')
            mutated.append(True)
        return original(raw, ext=ext, **kwargs)

    monkeypatch.setattr(store, 'put_blob', mutate_after_validation)
    frozen = store.read_object_json(preview.freeze_check(store, 'candidate'))
    assert store.read_object_bytes(frozen['files']['candidate.png']['file']) == b'original candidate.png'
    with pytest.raises(OperationError):
        preview.freeze_check(store, 'candidate')
