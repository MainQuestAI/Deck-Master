"""Adoption receipts must revalidate ancestors older than the adopted snapshot."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from deck_master import run_desk, workbench
from deck_master.snapshots import snapshot_evidence
from test_candidates import store as candidate_store, dispatch  # noqa: F401
from test_pr188_completed_content import completed_content
from test_workbench_actions import commit


def review_results_members(project, summary):
    members = set()
    for action in summary['next_actions'].get('actions', []):
        if action['kind'] == 'review_results':
            members.update(target['object_id'] for target in workbench.action_targets(
                project, action['action_id'], revision=summary['revision_id'])['targets'])
    return members


@pytest.mark.parametrize('damage', ['malformed', 'foreign_project'])
def test_completed_content_revalidates_full_receipt_ancestry_after_warm_summary(tmp_path, damage):
    project, store, task = completed_content(tmp_path)
    receipt = store.operation_receipt(task['operation_id'])
    adopted = snapshot_evidence(store, receipt['response']['revision_id'])[0]
    ancestor_id = adopted['parent_revision_id']
    assert ancestor_id not in (adopted['revision_id'], store.current_revision_id())
    ancestor_path = store.revisions_dir / (ancestor_id + '.json')
    original = ancestor_path.read_bytes()
    before = workbench.workbench_summary(project)
    assert task['task_id'] in review_results_members(project, before)
    try:
        if damage == 'malformed':
            ancestor_path.write_bytes(b'{"broken":')
        else:
            ancestor = json.loads(original)
            ancestor['project_id'] = 'foreign-integration-fixture'
            ancestor_path.write_text(json.dumps(ancestor))
        warm = workbench.workbench_summary(project)
        with workbench._summary_cache_lock:
            workbench._summary_cache.clear()
        cold = workbench.workbench_summary(project)
        assert warm == cold
        assert task['task_id'] not in review_results_members(project, warm)
        relation = run_desk.detail(project, task_id=task['task_id'])['task']['current_relation']
        assert relation['status'] == relation['state'] == 'unknown'
        assert relation['reason'] == 'adoption_basis_unreadable'
    finally:
        ancestor_path.write_bytes(original)
    restored = workbench.workbench_summary(project)
    assert task['task_id'] in review_results_members(project, restored)
    assert run_desk.detail(project, task_id=task['task_id'])['task']['current_relation']['status'] == 'current'
    assert restored == before


@pytest.mark.parametrize('execution', ['unclaimed', 'stale'])
def test_replaced_running_work_stays_historical_but_unknown_calls_remain_actionable(candidate_store, execution):
    store = candidate_store
    old = dispatch(store, page='p01', layer='original_image')
    uncertain = dispatch(store, page='p02', layer='original_image')
    document = copy.deepcopy(store.load_document())
    for index, ref in enumerate(document['tasks']):
        task = store.read_object_json(ref)
        if task['task_id'] not in (old['task_id'], uncertain['task_id']):
            continue
        task['status'] = 'running'
        task['collaboration_binding']['request_id'] = 'replaced-integration-request'
        if execution == 'stale':
            task['execution_ref'] = 'synthetic-historical-host'
            task['execution_started_at'] = '2000-01-01T00:00:00Z'
        else:
            task['execution_ref'] = None
        if task['task_id'] == uncertain['task_id']:
            task['call_allowances'][0]['state'] = 'unknown'
        document['tasks'][index] = store.put_json_object(task)
    commit(store, document, 'historical-running-and-unknown-call')
    before = store.load_document()
    summary = workbench.workbench_summary(store.project_root)
    verify = next(action for action in summary['next_actions']['actions'] if action['kind'] == 'verify_execution')
    targets = workbench.action_targets(store.project_root, verify['action_id'], revision=summary['revision_id'])['targets']
    assert {target['object_id'] for target in targets} == {uncertain['task_id']}
    rows = {row['task_id']: row for row in run_desk.listing(store.project_root, limit=100)['tasks']}
    assert rows[old['task_id']]['status'] == 'running'
    assert rows[old['task_id']]['current_relation']['status'] == 'historical'
    assert rows[old['task_id']]['human_actions'] == []
    assert rows[uncertain['task_id']]['current_relation']['status'] == 'unknown'
    assert 'verify_unknown_call' in rows[uncertain['task_id']]['human_actions']
    attention = {row['task_id'] for row in run_desk.listing(store.project_root, attention=True)['tasks']}
    assert uncertain['task_id'] in attention and old['task_id'] not in attention
    assert store.load_document() == before


@pytest.mark.parametrize('protocol', ['workbench_summary.v1', 'workbench_summary.v2'])
@pytest.mark.parametrize('case', ['mixed', 'unknown_task'])
def test_summary_protocols_validate_new_relationship_facts(candidate_store, protocol, case):
    from test_candidates import candidate
    from test_rp08_current_actions import mixed

    store = candidate_store
    if case == 'mixed':
        mixed(store)
    else:
        candidate(store)
        document = store.load_document()
        original = store.read_object_json(document['candidates'][0])
        unknown = {**original, 'candidate_id': 'unknown-task-candidate', 'task_id': 'no-such-task'}
        document['candidates'] = [store.put_json_object(unknown)]
        commit(store, document, 'candidate-with-unreadable-task')
    before = store.load_document()
    summary = workbench.workbench_summary(store.project_root, protocol=protocol)
    version = protocol.rsplit('.', 1)[1]
    schema_path = Path(workbench.__file__).parent / f'resources/contracts/workbench-summary.{version}.schema.json'
    Draft202012Validator(json.loads(schema_path.read_text())).validate(summary)
    if case == 'mixed':
        block = summary['candidates']
        assert block['count'] == 22 and block['pending_count'] == block['actionable_count'] == 1
        assert block['historical_count'] == block['stale_count'] == 21
    else:
        compare = next(action for action in summary['next_actions']['actions'] if action['kind'] == 'compare_candidates')
        assert compare['enabled'] is False
        assert compare['state'] == 'unknown' and compare['blocked_reason'] == 'candidate_task_unreadable'
        if protocol == 'workbench_summary.v2':
            work = summary['current_work']
            assert work['next']['primary_action']['enabled'] is True
            readable = [*work['next']['actions'], *work['optional']]
            assert any(action['kind'] == 'compare_candidates' and not action['enabled'] for action in readable)
    assert store.load_document() == before
