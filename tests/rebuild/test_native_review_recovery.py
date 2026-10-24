"""RP-11 synthetic owned completions/faults. No model or real approval."""
from copy import deepcopy
import json

import pytest

from deck_master import native_review, review_evidence, service, tasks
from deck_master.models import bump_revision
from test_native_review import native, _review_task, FixtureSession
from test_content_preproduction_review import _deck


def fail_acceptance(project, monkeypatch):
    original = service.accept_result
    with monkeypatch.context() as patch:
        patch.setattr(service, 'accept_result', lambda *a, **k: (_ for _ in ()).throw(OSError('synthetic acceptance fault')))
        with pytest.raises(OSError):
            native_review.run(project)
    return original


def test_committed_proof_recovers_without_repeating_native_execution(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    fail_acceptance(project, monkeypatch)
    failed = _review_task(store)
    assert failed['status'] == 'failed'
    records = native_review._checkpoints(store, failed)
    assert [r['state'] for r in records] == ['observed', 'ready']
    assert native_review.run(project)['status'] == 'recovery_available'
    result = native_review.recover(project, task_id=failed['task_id'])
    assert result['status'] == 'recovered' and not result['model_called']
    assert result['preproduction']['status'] == 'pass'
    completed = _review_task(store)
    assert completed['execution_ref'] == failed['execution_ref']
    assert completed['execution_started_at'] == failed['execution_started_at']
    assert completed['call_allowances'] == failed['call_allowances']
    assert len(native.calls) == 1
    assert native_review.recover(project, task_id=failed['task_id'])['status'] == 'already_applied'
    assert len(native.calls) == 1


def test_invalid_output_preserves_observation_but_cannot_self_sign_it(tmp_path, native):
    project, store = _deck(tmp_path)
    native.corrupt = True
    with pytest.raises(review_evidence.EvidenceRejected):
        native_review.run(project)
    task = _review_task(store)
    records = native_review._checkpoints(store, task)
    assert [r['state'] for r in records] == ['observed']
    assert store.read_object_json(records[0]['observation_ref'])['raw_final_message'] == 'not-json'
    before = store.load_document()
    assert native_review.recover(project, task_id=task['task_id'])['status'] == 'needs_evidence'
    assert store.load_document() == before
    assert len(native.calls) == 1


def test_proof_persistence_failure_does_not_promote_loose_observation(tmp_path, native, monkeypatch):
    from deck_master.store import Store
    project, store = _deck(tmp_path)
    original = Store.put_json_object
    def fail(self, value, *args, **kwargs):
        if value.get('schema_version') == 'authenticated_review_receipt.v1':
            raise OSError('synthetic proof persistence failure')
        return original(self, value, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Store, 'put_json_object', fail)
        with pytest.raises(OSError):
            native_review.run(project)
    task = _review_task(store)
    assert native_review.recover(project, task_id=task['task_id'])['status'] == 'needs_evidence'
    assert len(native.calls) == 1


def test_uncertain_acceptance_checks_committed_state_instead_of_reexecuting(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    original = service.accept_result
    def lost_response(*args, **kwargs):
        original(*args, **kwargs)
        raise TimeoutError('synthetic response lost after committed acceptance')
    with monkeypatch.context() as patch:
        patch.setattr(service, 'accept_result', lost_response)
        with pytest.raises(TimeoutError):
            native_review.run(project)
    task = _review_task(store)
    assert task['status'] == 'completed'
    assert native_review.recover(project, task_id=task['task_id'])['status'] == 'already_applied'
    assert len(native.calls) == 1


def test_cancelled_completion_cannot_be_recovered(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    fail_acceptance(project, monkeypatch)
    task = _review_task(store)
    service.task_cancel(project, task_id=task['task_id'])
    with pytest.raises(tasks.TaskConflict):
        native_review.recover(project, task_id=task['task_id'])
    assert len(native.calls) == 1
    assert not store.load_document()['reviews']


@pytest.mark.parametrize('field', ['execution_ref', 'project_id', 'result'])
def test_recovery_rejects_changed_executor_project_or_payload(tmp_path, native, monkeypatch, field):
    project, store = _deck(tmp_path)
    fail_acceptance(project, monkeypatch)
    task = _review_task(store)
    if field == 'execution_ref':
        task['execution_ref'] = 'codex-native:another-execution'
    else:
        refs = []
        for ref in task['result_refs']:
            record = store.read_object_json(ref)
            if record.get('state') == 'ready':
                if field == 'project_id':
                    record['project_id'] = 'another-project'
                else:
                    envelope = store.read_object_json(record['envelope_ref'])
                    envelope['reviews'][0]['observations'] = ['Forged replacement judgment']
                    record['envelope_ref'] = store.put_json_object(envelope)
                ref = store.put_json_object(record)
            refs.append(ref)
        task['result_refs'] = refs
    # Deliberate committed corruption, beyond normal caller APIs: every bound
    # field is still checked, not accepted because it happens to be local JSON.
    doc = store.load_document()
    updated = bump_revision(deepcopy(doc), {'operation_id': 'tamper-fixture', 'kind': 'task_update',
        'description': 'Synthetic adversarial binding mismatch', 'read_set': []})
    updated['tasks'][-1] = store.put_json_object(task)
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='tamper-fixture')
    with pytest.raises(review_evidence.EvidenceRejected):
        native_review.recover(project, task_id=task['task_id'])
    assert len(native.calls) == 1
    assert not store.load_document()['reviews']


def test_stale_manuscript_recovery_is_refused(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    fail_acceptance(project, monkeypatch)
    task = _review_task(store)
    doc = store.load_document()
    changed = deepcopy(doc)
    page = store.read_object_json(changed['pages'][0]['page'])
    page['customer_visible']['title'] += ' changed after review'
    changed['pages'][0]['page'] = store.put_json_object(page)
    updated = bump_revision(changed, {'operation_id': 'stale-fixture', 'kind': 'task_update',
        'description': 'Synthetic manuscript edit', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='stale-fixture')
    with pytest.raises(tasks.StaleInputContext):
        native_review.recover(project, task_id=task['task_id'])
    assert len(native.calls) == 1


def test_multiple_clean_owners_can_be_rechecked_without_merging_identities(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    native.status = 'pass'
    # Clean owners are explicitly rechecked; a synthetic fail without findings
    # is not permission to erase an unresolved failed judgment.
    native_review.run(project)
    # Synthetic legacy history can contain multiple independent owners per unit.
    document = store.load_document()
    changed = deepcopy(document)
    for ref in document['reviews']:
        historical = store.read_object_json(ref)
        historical['review_id'] += '-legacy-owner'
        changed['reviews'].append(store.put_json_object(historical))
    changed = bump_revision(changed, {'operation_id': 'legacy-owner-fixture', 'kind': 'task_update',
        'description': 'Synthetic historical multiple owners', 'read_set': []})
    store.commit_change(base_revision=document['revision_id'], document=changed, operation_id='legacy-owner-fixture')
    prior = {ref['sha256']: store.read_object_json(ref) for ref in store.load_document()['reviews']}
    assert len(prior) == 8
    original = FixtureSession.review
    def recheck(self, prompt, schema):
        observation = original(self, prompt, schema)
        rows = [{'kind': item['review']['kind'], 'status': 'pass',
                 'observations': ['Synthetic recheck of this exact historical owner'],
                 'findings': [], 'replaces': item['ref']} for item in self.calls[-1]['prior_reviews']]
        observation['raw_final_message'] = json.dumps({'reviews': rows})
        return observation
    monkeypatch.setattr(FixtureSession, 'review', recheck)
    result = native_review.run(project, force_units=sorted({row["kind"] for row in prior.values()}))
    assert result['preproduction']['status'] == 'pass'
    after = store.load_document()
    assert len(after['reviews']) == 16
    replacements = [store.read_object_json(ref) for ref in after['reviews'][8:]]
    for row in replacements:
        owner = prior[row['replaces']['sha256']]
        assert row['review_id'] == owner['review_id']
        assert row['kind'] == owner['kind']
    assert len(native.calls) == 2


def test_expired_original_proof_is_not_renewed(tmp_path, native, monkeypatch):
    from datetime import datetime, timedelta, timezone
    project, store = _deck(tmp_path)
    fail_acceptance(project, monkeypatch)
    task = _review_task(store)
    later = datetime.now(timezone.utc) + timedelta(hours=1)
    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return later
    monkeypatch.setattr(review_evidence, 'datetime', Later)
    with pytest.raises(review_evidence.EvidenceRejected, match='expired'):
        native_review.recover(project, task_id=task['task_id'])
    assert len(native.calls) == 1
    assert _review_task(store)['status'] == 'failed'


def test_multiple_finding_owners_close_only_their_own_history():
    from deck_master import review
    from test_review import _page_only_owner, _r1_closing, _page_only_context, ref
    first = _page_only_owner()
    second = deepcopy(first)
    second['review_id'] = 'other-owner'
    second['ref'] = ref('other-owner')
    second['findings'][0]['finding_id'] = 'other-finding'
    first_close = _r1_closing(first)
    second_close = _r1_closing(second)
    second_close['findings'][0]['finding_id'] = 'other-finding'
    context = _page_only_context()
    partial = [first, second, first_close]
    assert review.finding_closed(partial, first, first['findings'][0], context)
    assert not review.finding_closed(partial, second, second['findings'][0], context)
    complete = [*partial, second_close]
    assert review.finding_closed(complete, first, first['findings'][0], context)
    assert review.finding_closed(complete, second, second['findings'][0], context)


def test_recovery_consumes_task_accept_eligibility_before_adoption(tmp_path, native, monkeypatch):
    from deck_master import eligibility
    project, store = _deck(tmp_path)
    fail_acceptance(project, monkeypatch)
    failed = _review_task(store)
    evaluate = eligibility.evaluate
    checked = []

    def refuse_adoption(store, before, after, action, *args, **kwargs):
        decision = evaluate(store, before, after, action, *args, **kwargs)
        if action == 'task.accept':
            checked.append(action)
            decision = {**decision, 'allowed': False, 'reason_codes': ['synthetic_admission_denied'],
                        'reasons': [{'detail': 'Synthetic negative admission decision'}]}
        return decision

    monkeypatch.setattr(eligibility, 'evaluate', refuse_adoption)
    with pytest.raises(eligibility.EligibilityBlocked, match='Synthetic negative admission'):
        native_review.recover(project, task_id=failed['task_id'])
    assert checked == ['task.accept']
    assert not store.load_document()['reviews']
    after = _review_task(store)
    assert after['status'] == 'failed'
    assert after['execution_ref'] == failed['execution_ref']
    assert after['call_allowances'] == failed['call_allowances']
    assert len(native.calls) == 1
