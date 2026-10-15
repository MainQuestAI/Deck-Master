"""L1 Host facts: empty input is not a receipt and enrichment is not proof."""
import json

import pytest

from deck_master import generation, tasks
from rc3_fixtures import source_snapshot
from test_t06_boundaries import claim_begin, dispatch, setup_project


def _started(tmp_path):
    store = setup_project(tmp_path)
    task = dispatch(store)
    begun = claim_begin(store, task)
    return store, task, begun['attempt_id']


def _settle(store, task, attempt, *, report=None, outcome='consumed', invocation=None):
    return tasks.call_settle(store, task_id=task['task_id'], allowance_id='call-1',
        attempt_id=attempt, outcome=outcome, report_bytes=report, invocation_ref=invocation)


@pytest.mark.parametrize('report', [None, b'', b'{}', b'[]', b' \n\t'])
@pytest.mark.parametrize('initial', ['in_flight', 'unknown'])
def test_empty_report_cannot_resolve_consumption_or_unknown(tmp_path, report, initial):
    store, task, attempt = _started(tmp_path)
    if initial == 'unknown':
        _settle(store, task, attempt, outcome='unknown')
    before = source_snapshot(store.project_root)
    with pytest.raises((tasks.EnvelopeError, generation.GenerationError)):
        _settle(store, task, attempt, report=report)
    assert source_snapshot(store.project_root) == before
    shown = generation.show(store.project_root, attempt_id=attempt)
    assert shown['call']['state'] == initial
    assert shown['observations'] == []


@pytest.mark.parametrize('report', [None, b'', b'{}', b'[]', b' \n\t'])
def test_empty_report_cannot_add_an_invocation_to_a_known_fact(tmp_path, report):
    store, task, attempt = _started(tmp_path)
    _settle(store, task, attempt, report=b'{"sent":true,"basis":"L1 original Host fact"}')
    before = source_snapshot(store.project_root)
    with pytest.raises((tasks.EnvelopeError, generation.GenerationError)):
        _settle(store, task, attempt, report=report, invocation='L1-new-invocation')
    assert source_snapshot(store.project_root) == before


def test_known_receipt_replays_and_same_report_only_enriches_missing_invocation(tmp_path):
    store, task, attempt = _started(tmp_path)
    report = b'{"sent":true,"basis":"L1 original Host fact, price unknown"}'
    first = _settle(store, task, attempt, report=report)
    original = generation.show(store.project_root, attempt_id=attempt)
    before = source_snapshot(store.project_root)
    assert _settle(store, task, attempt)['status'] == 'already_settled'
    assert _settle(store, task, attempt, report=report)['status'] == 'already_settled'
    assert source_snapshot(store.project_root) == before
    with pytest.raises(tasks.TaskConflict):
        _settle(store, task, attempt, report=b'{"sent":false}', invocation='L1-invocation')
    assert source_snapshot(store.project_root) == before
    enriched = _settle(store, task, attempt, report=report, invocation='L1-invocation')
    shown = generation.show(store.project_root, attempt_id=attempt)
    assert enriched['attempt_ref'] != first['attempt_ref']
    assert shown['call']['state'] == 'consumed'
    assert shown['call']['invocation_ref'] == 'L1-invocation'
    assert shown['call']['evidence_level'] == 'host_reported'
    assert set(json.dumps(ref, sort_keys=True) for ref in original['call']['evidence']) <= set(
        json.dumps(ref, sort_keys=True) for ref in shown['call']['evidence'])
    assert len(shown['observations']) == 2
    assert all(observation['observer'] == 'host_reported' and not observation['coverage']
        and observation['output'] is None for observation in shown['observations'])
    assert tasks._lookup_task(store.load_document(), task['task_id'], store)['usage']['external_calls'] is None
    before = source_snapshot(store.project_root)
    assert _settle(store, task, attempt, report=report, invocation='L1-invocation')['status'] == 'already_settled'
    with pytest.raises(tasks.TaskConflict):
        _settle(store, task, attempt, report=report, invocation='different-invocation')
    assert source_snapshot(store.project_root) == before
