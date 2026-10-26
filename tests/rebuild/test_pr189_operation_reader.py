"""One read verifies ancestry once; a later read must detect history damage."""
import pytest
from deck_master.operations import OperationReader
from deck_master.snapshots import ReadModelError
from deck_master import operation_coverage
from test_pr188_completed_content import completed_content


def test_receipts_equal_canonical_lookup_and_scan_once(tmp_path, monkeypatch):
    _, store, task = completed_content(tmp_path)
    ids = [store.read_object_json(ref)['operation_id'] for ref in store.load_document()['tasks']]
    expected = [store.operation_receipt(op) for op in ids]
    calls = []
    original = operation_coverage.scan
    def scan(*args, **kwargs):
        calls.append(kwargs['operation_id'])
        return original(*args, **kwargs)
    monkeypatch.setattr(operation_coverage, 'scan', scan)
    reader = OperationReader(store)
    for _ in range(3):
        assert [store.operation_receipt(op, reader=reader) for op in ids] == expected
    assert len(calls) == 1
    assert store.operation_receipt(task['operation_id'], reader=reader)


def test_new_read_revalidates_old_ancestry(tmp_path):
    _, store, task = completed_content(tmp_path)
    reader = OperationReader(store)
    assert store.operation_receipt(task['operation_id'], reader=reader)
    root = next(rev for rev, header in reader.coverage.headers.items() if header.parent is None)
    (store.revisions_dir / (root + '.json')).write_text('{}')
    with pytest.raises(ReadModelError, match='snapshot is not readable'):
        OperationReader(store)
