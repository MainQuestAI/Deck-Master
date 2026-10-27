"""Synthetic complete ancestry checks while retained metadata is partial."""
from dataclasses import asdict
import json
import uuid

import pytest

from deck_master import operation_coverage as cache, operations
from deck_master.models import canonical_json_bytes
from test_operation_coverage import append, Counts
from test_workbench_operations import project, submit


@pytest.fixture(autouse=True)
def bounded(monkeypatch):
    cache.clear()
    monkeypatch.setattr(cache, 'MAX_REVISIONS', 4)
    yield
    cache.clear()


def test_partial_cache_is_bounded_and_walks_uncached_tail(tmp_path, monkeypatch):
    store = project(tmp_path)
    append(store, 7)
    counts = Counts(monkeypatch)
    for expected in (8, 4, 4):
        result, measured = counts.run(lambda: operations.resolve_operation(store, 'absent'))
        assert result.state == 'not_found' and measured['snapshot_decode'] == expected
        retained = cache.get(cache.root_identity(store))
        assert len(retained.headers) == 4 and not retained.complete
    reader = operations.OperationReader(store)
    assert reader.coverage.complete and len(reader.coverage.headers) == 8


@pytest.mark.parametrize('damage', ['cached_corrupt', 'tail_missing', 'tail_foreign', 'tail_cycle', 'tail_duplicate'])
def test_partial_cache_never_proves_absence_through_damage(tmp_path, damage):
    store = project(tmp_path)
    first = store.current_revision_id()
    append(store, 7)
    assert operations.resolve_operation(store, 'absent').state == 'not_found'
    head = store.load_document()
    revision = head['revision_id'] if damage == 'cached_corrupt' else first
    path = store.revisions_dir / (revision + '.json')
    if damage == 'cached_corrupt':
        path.write_bytes(b'{broken')
    elif damage == 'tail_missing':
        path.unlink()
    else:
        doc = json.loads(path.read_bytes())
        if damage == 'tail_foreign':
            doc['project_id'] = 'foreign'
        elif damage == 'tail_cycle':
            doc['parent_revision_id'] = head['revision_id']
        else:
            doc['change']['operation_id'] = head['change']['operation_id']
        path.write_bytes(canonical_json_bytes(doc))
    cached = operations.resolve_operation(store, 'absent')
    canonical = operations.resolve_operation(store, 'absent', use_cache=False)
    assert asdict(cached) == asdict(canonical) and cached.state == 'unknown'
    assert not cache._cache


def test_partial_positive_and_explicit_head_match_canonical(tmp_path):
    store = project(tmp_path)
    old_op, new_op = str(uuid.uuid4()), str(uuid.uuid4())
    old = submit(store, old_op, store.current_revision_id(), {'old': True})
    append(store, 6)
    submit(store, new_op, store.current_revision_id(), {'new': True})
    assert operations.resolve_operation(store, 'absent').state == 'not_found'
    for op, head in [(old_op, None), (new_op, None), (new_op, old['committed_revision_id']), (old_op, old['committed_revision_id'])]:
        cached = operations.resolve_operation(store, op, head_revision=head)
        canonical = operations.resolve_operation(store, op, head_revision=head, use_cache=False)
        assert asdict(cached) == asdict(canonical)
