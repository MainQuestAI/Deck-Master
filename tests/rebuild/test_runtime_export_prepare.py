"""Fixed export preparation releases the project lock and never retries itself."""
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

import pytest

from deck_master import collaboration, eligibility, exports
from deck_master.models import bump_revision
from test_export import _passing_deck


@pytest.mark.parametrize('change', ['pause', 'revoke', 'advance'])
def test_delivery_prepare_allows_control_write_and_rejects_publication(tmp_path, monkeypatch, change):
    project, store = _passing_deck(tmp_path)
    entered, release = threading.Event(), threading.Event()
    real_bundle, calls = exports._bundle, []
    destination = tmp_path / 'external'

    def prepare(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(8)
        return real_bundle(*args, **kwargs)

    def mutate():
        doc = store.load_document()
        evidence = {'kind': 'host_attested_instruction', 'text': 'L1 change while preparing fixed export'}
        if change == 'pause':
            collaboration.pause_request(project, reason='L1 pause during preparation', instruction_evidence=evidence,
                base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
        elif change == 'revoke':
            grants = [store.read_object_json(ref) for ref in doc['collaboration']['authorizations']]
            active = next(row for row in grants if 'export.delivery' in row['actions'] and row['status'] == 'active')
            collaboration.revoke_authorization(project, authorization_id=active['authorization_id'],
                reason='L1 revoke during preparation', instruction_evidence=evidence,
                base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
        else:
            op = str(uuid.uuid4())
            new = bump_revision(doc, {'operation_id': op, 'kind': 'task_update',
                                     'description': 'Unrelated synthetic commit', 'read_set': []})
            store.commit_change(base_revision=doc['revision_id'], document=new, operation_id=op)
        return store.current_revision_id()

    monkeypatch.setattr(exports, '_bundle', prepare)
    with ThreadPoolExecutor(max_workers=2) as workers:
        delivery = workers.submit(exports.create, project, purpose='delivery', output_dir=destination)
        try:
            assert entered.wait(5)
            writer = workers.submit(mutate)
            control = writer.result(timeout=3)  # Must complete while bundle is blocked.
        finally:
            release.set()
        expected = exports.ExportError if change == 'advance' else eligibility.EligibilityBlocked
        with pytest.raises(expected) as failure:
            delivery.result(timeout=5)
    if change == 'advance':
        assert failure.value.error_code == 'conflict' and failure.value.exit_code == 5
    cache = store.deck_root / 'workbench' / 'exports'
    assert len(calls) == 1 and store.current_revision_id() == control
    assert not destination.exists() and not list(cache.glob('*/export-record.json'))
    assert not list(cache.glob('.export-*'))
