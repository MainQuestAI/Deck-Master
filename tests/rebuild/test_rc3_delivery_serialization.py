"""Delivery/control serialization with actual locks, without product patches."""
from pathlib import Path
import os
import threading
import uuid

import pytest

from deck_master import collaboration, delivery_eligibility, eligibility, exports
from deck_master.local_state import local_lock
from test_export import _passing_deck


def test_legacy_export_preserves_review_wait_exit_three_without_changing_shared_admission(tmp_path, capsys):
    from deck_master import cli
    from test_export import _set_policy
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        exports.create(project, purpose='delivery')
    assert blocked.value.decision['reason_codes'] == ['professional_review_required']
    code = cli.main(['export', '--project', str(project), '--out', str(tmp_path / 'legacy-delivery'),
                     '--purpose', 'delivery'])
    assert code == 3 and 'professional_review_required' in capsys.readouterr().err
    assert not (tmp_path / 'legacy-delivery').exists()


@pytest.mark.parametrize('control', ['pause', 'revoke'])
def test_waiting_delivery_rechecks_committed_control_before_publishing_any_bundle(tmp_path, monkeypatch, control):
    # The helper authors real PPTX bytes and explicitly synthetic engineering
    # facts. This checks transaction ordering, not human/model quality.
    project, store = _passing_deck(tmp_path)
    assert delivery_eligibility.describe(project)['status'] == 'ready'
    root = store.deck_root / 'workbench' / 'exports'
    root.mkdir(parents=True, exist_ok=True)
    lock = root / 'exports.lock'
    destination = tmp_path / 'delivery'
    before_records = sorted(root.glob('*/export-record.json'))
    outcome = {}
    waiting = threading.Event()
    actual_open = os.open

    def observe_open(path, *args, **kwargs):
        descriptor = actual_open(path, *args, **kwargs)
        if Path(path) == lock and threading.current_thread() is worker:
            waiting.set()
        return descriptor

    def deliver():
        try:
            outcome['response'] = exports.create(project, purpose='delivery', output_dir=destination)
        except Exception as exc:
            outcome['error'] = exc

    worker = threading.Thread(target=deliver)
    monkeypatch.setattr(os, 'open', observe_open)
    with local_lock(lock):
        worker.start()
        # Observe the worker's real descriptor while retaining the real parent
        # lock. The worker still blocks in flock, on macOS as well as Linux.
        assert waiting.wait(5) and worker.is_alive(), outcome
        # This actual public write must commit while export waits on its own
        # cache lock, so delivery must re-evaluate after taking that lock.
        doc = store.load_document()
        evidence = {'kind': 'host_attested_instruction', 'text': 'L1 stop this delivery before publication'}
        if control == 'pause':
            collaboration.pause_request(project, reason='L1 delivery paused before publication',
                instruction_evidence=evidence, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
        else:
            authorizations = [store.read_object_json(ref) for ref in doc['collaboration']['authorizations']]
            record = next(row for row in authorizations if 'export.delivery' in row['actions'] and row['status'] == 'active')
            collaboration.revoke_authorization(project, authorization_id=record['authorization_id'],
                reason='L1 revoke before delivery publication', instruction_evidence=evidence,
                base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
        at_control = store.load_document()
    worker.join(5)
    assert not worker.is_alive() and 'response' not in outcome
    assert isinstance(outcome.get('error'), eligibility.EligibilityBlocked), outcome
    assert not destination.exists() and not list(tmp_path.glob('.delivery-*'))
    assert sorted(root.glob('*/export-record.json')) == before_records
    assert not list(root.glob('.export-*'))
    assert store.load_document() == at_control
    assert delivery_eligibility.describe(project)['status'] == 'blocked'
    # Read-only/review delivery packets remain available under the same pause
    # or withdrawal, and are labelled as review rather than public approval.
    review = exports.create(project, purpose='review', output_dir=tmp_path / 'review')
    assert review['purpose'] == 'review' and (tmp_path / 'review' / 'deck.pptx').is_file()
    assert store.load_document() == at_control
