"""Review-only history diagnostics never authorize old output or scan every PPTX."""
import copy
import uuid

import pytest

from deck_master.handoff import check_handoff
from deck_master.models import bump_revision
from deck_master.store import Store
from test_export import _deck


def commit_outputs(store, outputs):
    doc = store.load_document()
    operation = uuid.uuid4().hex
    new = bump_revision(copy.deepcopy(doc), {'operation_id': operation, 'kind': 'task_update',
        'description': 'Synthetic historical output fixture', 'read_set': []})
    new['outputs'] = outputs
    store.commit_change(document=new, base_revision=doc['revision_id'], operation_id=operation)
    return new


@pytest.fixture
def history(tmp_path):
    project, store = _deck(tmp_path)
    doc = store.load_document()
    output = doc['outputs']['pptx']
    file_ref = store.read_object_json(output)['file']
    candidate = tmp_path / 'old.pptx'
    candidate.write_bytes(store.read_object_bytes(file_ref))
    commit_outputs(store, doc['outputs'])
    commit_outputs(store, {key: None for key in doc['outputs']})
    return project, store, candidate, output, file_ref


def test_exact_historical_match_is_identified_and_still_blocked(history, monkeypatch):
    project, store, candidate, output, file_ref = history
    from deck_master.snapshots import committed_snapshots
    revisions = {s['revision_id'] for s in committed_snapshots(store)
                 if s['outputs'].get('pptx') == output}
    before = store.load_document()
    original = Store.read_object_bytes
    reads = []
    def tracked(self, ref):
        if ref == file_ref:
            reads.append(ref)
        return original(self, ref)
    monkeypatch.setattr(Store, 'read_object_bytes', tracked)
    result = check_handoff(project, file_path=candidate)
    assert result['candidate_relation'] == 'historical_output'
    assert {m['revision_id'] for m in result['matched_historical_outputs']} == revisions
    assert all(m['output_ref'] == output for m in result['matched_historical_outputs'])
    assert result['status'] == 'blocked' and 'candidate_not_current_output' in result['gaps']
    assert len(reads) == 1  # verify the matching immutable file once, not once per revision
    assert store.load_document() == before


@pytest.mark.parametrize('damage', ['missing_object', 'corrupt_object', 'broken_history'])
def test_history_damage_is_reported_as_unknown_without_writing(history, damage):
    project, store, candidate, _, file_ref = history
    if damage == 'broken_history':
        from deck_master.snapshots import committed_snapshots
        rows = list(committed_snapshots(store))
        (store.revisions_dir / (rows[1]['revision_id'] + '.json')).write_text('{broken')
    else:
        target = store._resolve_object_path(file_ref['path'])
        if damage == 'missing_object':
            target.unlink()
        else:
            target.write_bytes(b'x' * target.stat().st_size)
    before = {str(p): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()}
    result = check_handoff(project, file_path=candidate)
    assert result['status'] == 'blocked'
    assert result['history_status'] == 'incomplete'
    assert result['candidate_relation'] == 'unverified'
    assert 'historical_output_unverifiable' in result['gaps']
    assert {str(p): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()} == before


def test_same_size_wrong_bytes_are_not_a_history_match(history):
    project, _, candidate, _, _ = history
    candidate.write_bytes(b'x' * candidate.stat().st_size)
    result = check_handoff(project, file_path=candidate)
    assert result['candidate_relation'] == 'unverified'
    assert result['matched_historical_outputs'] == []
    assert result['status'] == 'blocked'


def test_history_index_does_not_read_unmatched_pptx_bodies(history, tmp_path, monkeypatch):
    from deck_master.pipeline import artifact
    project, store, candidate, _, matched_file = history
    other_files = set()
    for i in range(6):
        path = tmp_path / f'other-{i}.pptx'
        path.write_bytes(candidate.read_bytes() + b'x' * (i + 1) * 1000)
        output = artifact(store, path, 'pptx')
        other_files.add(store.read_object_json(output)['file']['sha256'])
        outputs = dict(store.load_document()['outputs'], pptx=output)
        commit_outputs(store, outputs)
    commit_outputs(store, {key: None for key in store.load_document()['outputs']})
    original = Store.read_object_bytes
    reads = []
    def bounded(self, ref):
        assert ref['sha256'] not in other_files, 'unmatched historical PPTX must only be statted'
        if ref == matched_file:
            reads.append(ref)
        return original(self, ref)
    monkeypatch.setattr(Store, 'read_object_bytes', bounded)
    result = check_handoff(project, file_path=candidate)
    assert result['candidate_relation'] == 'historical_output'
    assert len(reads) == 1
