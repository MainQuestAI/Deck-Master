"""Synthetic count and concurrency checks; real rendering stays in its existing gate."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError

import pytest

from deck_master import exports, pipeline, review_import
from test_candidates import store  # noqa: F401
from test_pipeline_preview_reuse import prepared
from test_versioned_exports import project


@pytest.mark.parametrize('size', [20 * 1024, 100 * 1024])
@pytest.mark.parametrize('writer', [None, 'asset-inputs.v1'])
def test_writer_classification_reads_large_task_at_most_once(tmp_path, monkeypatch, size, writer):
    from deck_master.models import bump_revision, new_document, require_writer, validate_task_semantics
    from deck_master.store import Store
    from deck_master.tasks import new_task
    store = Store(tmp_path / 'writer-project')
    doc = new_document(project_id='synthetic-writer', task={'title': 'Writer classification'})
    if writer:
        require_writer(doc, writer)
    store.init_project(doc, operation_id=doc['change']['operation_id'])
    task = new_task(task_id='synthetic-check', operation_id='synthetic-task', kind='check',
        scope_pages=[], instruction='x' * size, inputs=[], dependencies=[],
        dispatch_revision=doc['revision_id'], produced_against='0' * 64)
    if writer is None:
        # Exercise the supported historical Task shape, before frozen method
        # contracts. A modern manifest correctly raises the writer floor and
        # cannot be inserted into an unmigrated legacy document.
        task.pop('method_manifest')
        task.pop('method_release')
        validate_task_semantics(task)
    ref = store.put_json_object(task)
    new = bump_revision(doc, {'operation_id': 'synthetic-classify', 'kind': 'task_update',
        'description': 'Count transaction-local classification only', 'read_set': []})
    new['tasks'] = [ref]
    original, reads = store.read_object_bytes, []
    def counted(value):
        if value == ref:
            reads.append(1)
        return original(value)
    monkeypatch.setattr(store, 'read_object_bytes', counted)
    store.commit_change(base_revision=doc['revision_id'], document=new, operation_id='synthetic-classify')
    assert len(reads) == (0 if writer else 1)


def test_version_does_not_import_production_dependencies():
    code = """import json,sys
from deck_master.cli import main
try: main(['--version'])
except SystemExit as exc: assert exc.code == 0
print(json.dumps([name for name in sys.modules if name.startswith('deck_master.')]))
"""
    lines = subprocess.check_output([sys.executable, '-c', code], text=True).splitlines()
    assert lines[0] == 'deck-master 1.0.0'
    modules = json.loads(lines[1])
    assert 'deck_master.service' not in modules
    assert 'deck_master.pipeline' not in modules


def test_copy_validates_manifest_once_and_checks_actual_files(tmp_path, monkeypatch):
    root, _ = project(tmp_path)
    original = exports.create(root, purpose='review')
    validate, calls = exports._record, []
    def counted(*args):
        calls.append(1)
        return validate(*args)
    monkeypatch.setattr(exports, '_record', counted)
    exports.create(root, purpose='review', export_id=original['export_id'], output_dir=tmp_path / 'copy')
    assert len(calls) == 2  # Existing export + one bounded copy context.
    for name in original['files']:
        assert (tmp_path / 'copy' / name).read_bytes() == exports.download(root, export_id=original['export_id'], filename=name)[0]
    name = next(name for name in original['files'] if name not in ('manifest.json', original['archive']))
    target = root / '.deckmaster/workbench/exports' / original['export_id'] / name
    target.write_bytes(b'corrupted')
    with pytest.raises(exports.ExportError, match='frozen export file'):
        exports.create(root, purpose='review', export_id=original['export_id'], output_dir=tmp_path / 'bad-copy')
    assert not (tmp_path / 'bad-copy').exists()


def test_review_binding_unique_reads_preserve_order_and_multiple_matches():
    from deck_master.models import canonical_json_bytes, sha256_bytes
    raw = canonical_json_bytes({'file': {'sha256': 'f' * 64}})
    first = {'path': 'first.json', 'sha256': sha256_bytes(raw)}
    second = {'path': 'second.json', 'sha256': sha256_bytes(raw)}
    class Reader:
        calls = []
        def read_object_bytes(self, ref):
            self.calls.append(ref['path'])
            return raw
    reader = Reader()
    report = {'subjects': [{'source_uri': 'file:///a', 'sha256': 'f' * 64},
                           {'source_uri': 'file:///b', 'sha256': first['sha256']}]}
    result = review_import._describe_bindings(reader, {'project_id': 'p', 'revision_id': 'c'},
        {'revision_id': 'a'}, [first, second, first], report)
    assert reader.calls == ['first.json', 'second.json']
    assert [row['target_ref'] for row in result['source_bindings']] == [first, second, first] * 2


@pytest.mark.parametrize('waiter_timeout,changed_base', [(False, False), (True, False), (False, True), (True, True)])
def test_assembly_waiters_do_not_start_or_release_an_active_compiler(store, monkeypatch, waiter_timeout, changed_base):
    before = prepared(store)
    entered, release, waiting = threading.Event(), threading.Event(), threading.Event()
    calls, waiters = [], []
    class ObservedFuture(Future):
        def result(self, timeout=None):
            waiters.append(1)
            if len(waiters) == 2:
                waiting.set()
            return super().result(timeout=0 if waiter_timeout else timeout)
    def blocked_compile(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(10)
        raise RuntimeError('controlled compiler failure')
    monkeypatch.setattr(pipeline, 'Future', ObservedFuture)
    monkeypatch.setattr(pipeline, 'compile_deck', blocked_compile)
    args = {'base_revision': before['revision_id'], 'operation_id': str(uuid.uuid4())}
    with ThreadPoolExecutor(max_workers=3) as executor:
        owner = executor.submit(pipeline.produce, store.project_root, **args)
        try:
            assert entered.wait(10)
            other_args = {**args, **({'base_revision': '0' * 32} if changed_base else {})}
            others = [executor.submit(pipeline.produce, store.project_root, **other_args) for _ in range(2)]
            assert waiting.wait(10)
            assert len(calls) == 1
            assert pipeline._ASSEMBLIES
            if waiter_timeout:
                for item in others:
                    with pytest.raises(TimeoutError):
                        item.result(timeout=10)
                assert pipeline._ASSEMBLIES  # Only the still-running owner may remove it.
        finally:
            release.set()
        with pytest.raises(RuntimeError, match='controlled compiler failure'):
            owner.result(timeout=10)
        if not waiter_timeout:
            for item in others:
                from deck_master.operations import OperationError
                error = OperationError if changed_base else RuntimeError
                with pytest.raises(error, match='assembly basis changed' if changed_base else 'controlled compiler failure'):
                    item.result(timeout=10)
    assert not pipeline._ASSEMBLIES
    assert store.load_document() == before
