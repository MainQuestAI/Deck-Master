"""Authored no-copy-change reasoning survives actual v2 adoption and replay."""
from copy import deepcopy

import pytest

from deck_master import content_production, tasks
from rc3_fixtures import claim_fixture_task, source_snapshot
from test_compose_v2_phases import _deck_with_pages, _submit
from test_rc3_entry_transactions import operation


def _revision(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    task = content_production.open_phase_task(store, store.load_document(),
        operation_id=operation(), intent='input_revision', page_ids=['p1'], adoption_policy='within_scope')
    claim_fixture_task(project, task)
    before = store.load_document()
    plan = deepcopy(store.read_object_json(before['content_plan'])['input'])
    payload = {'changed_layers': ['plan'],
        'proposals': [{'layer': 'plan', 'ref': store.put_json_object(plan)}],
        'diff': {'input_digest': task['input_digest'], 'summary': 'The new material supplies context.',
            'changed_page_ids': [], 'page_order': ['p1'],
            'unchanged_reason': 'The existing visible facts and qualifications remain exact.'}}
    return project, store, task, before, payload


def test_v2_adoption_keeps_distinct_impact_and_unchanged_reason_and_exact_replay(tmp_path):
    project, store, task, before, payload = _revision(tmp_path)
    result = _submit(project, task, payload, 'input_revision')
    assert result['impact_summary'] == payload['diff']['summary']
    assert result['unchanged_reason'] == payload['diff']['unchanged_reason']
    assert result['impact_summary'] != result['unchanged_reason']
    assert store.load_document()['pages'] == before['pages']
    assert store.load_document()['outputs'] == before['outputs']
    snapshot = source_snapshot(project)
    replay = _submit(project, task, payload, 'input_revision')
    assert replay['status'] == 'already_applied' and replay['same_revision'] is True
    for field in ('revision_id', 'impact_summary', 'unchanged_reason', 'result_refs'):
        assert replay[field] == result[field]
    assert source_snapshot(project) == snapshot


@pytest.mark.parametrize('reason', [None, '', '  ', {}, []])
def test_invalid_explicit_unchanged_reason_refuses_without_any_adoption(tmp_path, reason):
    project, store, task, _, payload = _revision(tmp_path)
    payload['diff']['unchanged_reason'] = reason
    snapshot = source_snapshot(project)
    with pytest.raises(tasks.EnvelopeError, match='concrete reason'):
        _submit(project, task, payload, 'input_revision')
    assert source_snapshot(project) == snapshot
