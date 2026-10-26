"""Control-only changes retain reading of adopted content and keep write guards."""
from copy import deepcopy

import pytest

from deck_master import eligibility, run_desk, workbench
from test_pr188_completed_content import completed_content
from test_workbench_actions import commit


@pytest.mark.parametrize('control', ['paused', 'completed', 'rejected', 'withdrawn', 'background'])
def test_adopted_content_reading_survives_control_only_changes(tmp_path, control):
    project, store, task = completed_content(tmp_path)
    doc = deepcopy(store.load_document())
    request = doc['collaboration']['request']
    if control == 'paused':
        request.update(paused=True, pause_reason='Synthetic explicit stop')
    elif control == 'background':
        request['background_request_ids'] = ['synthetic-other-request']
    else:
        request.update(closed=True, closed_reason=control)
    commit(store, doc, 'round2-control-only-' + control)
    before = store.load_document()
    row = run_desk.detail(project, task_id=task['task_id'])['task']
    assert row['current_relation']['status'] == 'current'
    assert 'review_results' in row['human_actions']
    assert task['task_id'] in {row['task_id'] for row in run_desk.listing(project, attention=True)['tasks']}
    summary = workbench.workbench_summary(project)
    action = next(action for action in summary['next_actions']['actions'] if action['kind'] == 'review_results')
    targets = workbench.action_targets(project, action['action_id'], revision=summary['revision_id'])['targets']
    assert task['task_id'] in {row['object_id'] for row in targets}
    assert store.load_document() == before
    if control != 'background':
        decision = eligibility.evaluate(store, before, before, 'dispatch.compose')
        assert not decision['allowed']
        assert ('request_paused' if control == 'paused' else 'request_closed') in decision['reason_codes']


@pytest.mark.parametrize('change', ['intent', 'scope', 'evidence'])
def test_request_semantics_still_stale_adopted_content(tmp_path, change):
    project, store, task = completed_content(tmp_path)
    doc = deepcopy(store.load_document())
    request = doc['collaboration']['request']
    if change == 'intent':
        request.update(intent='review_only', content_intent=None)
    elif change == 'scope':
        request['scope']['purpose'] = 'exploratory'
    else:
        request['instruction_evidence']['source_locator'] += ':changed-instruction'
    commit(store, doc, 'round2-semantic-' + change)
    assert run_desk.detail(project, task_id=task['task_id'])['task']['current_relation']['status'] == 'historical'
