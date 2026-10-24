"""Completed content is judged against its committed adoption, never re-acceptance."""
import copy

import pytest

from deck_master import run_desk, workbench
from test_compose_v2_phases import _deck_with_pages
from test_workbench_actions import commit


def completed_content(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    task = next(store.read_object_json(ref) for ref in reversed(store.load_document()['tasks'])
                if store.read_object_json(ref).get('result_refs') and
                (store.read_object_json(ref).get('collaboration_binding') or {}).get('phase') == 'page_copy')
    return project, store, task


def test_adopted_compose_is_current_in_all_readers(tmp_path):
    project, store, task = completed_content(tmp_path)
    before = copy.deepcopy(store.load_document())
    detail = run_desk.detail(project, task_id=task['task_id'])['task']
    assert detail['current_relation']['status'] == 'current'
    assert 'review_results' in detail['human_actions']
    assert task['task_id'] in {row['task_id'] for row in run_desk.listing(project, attention=True)['tasks']}
    summary = workbench.workbench_summary(project)
    action = next(a for a in summary['next_actions']['actions'] if a['kind'] == 'review_results')
    assert task['task_id'] in {row['object_id'] for row in workbench.action_targets(
        project, action['action_id'], revision=summary['revision_id'])['targets']}
    assert store.load_document() == before


@pytest.mark.parametrize('change', ['page', 'inputs', 'source', 'metadata', 'request'])
def test_adopted_compose_tracks_only_real_subsequent_changes(tmp_path, change):
    project, store, task = completed_content(tmp_path)
    doc = copy.deepcopy(store.load_document())
    if change == 'page':
        page = store.read_object_json(doc['pages'][0]['page'])
        page['customer_visible']['title'] += ' 后续修改'
        doc['pages'][0]['page'] = store.put_json_object(page)
    elif change == 'inputs':
        doc['task']['audience'] += ' 新受众'
    elif change == 'source':
        doc['sources'][0]['usage_note'] = 'Changed source usage constraint'
    elif change == 'request':
        doc['collaboration']['request']['request_id'] = 'replacement-request'
    else:
        doc['sources'][0]['name'] = 'Display-only rename'
    commit(store, doc, 'synthetic-after-adoption-' + change)
    expected = 'current' if change == 'metadata' else 'historical'
    row = run_desk.detail(project, task_id=task['task_id'])['task']
    assert row['current_relation']['status'] == expected
    assert ('review_results' in row['human_actions']) == (expected == 'current')


def test_completed_input_revision_uses_its_adopted_snapshot(tmp_path):
    from deck_master import content_production, models
    from test_compose_v2_phases import _page, _submit, claim_fixture_task, tasks_lookup
    project, store, original = completed_content(tmp_path)
    doc = store.load_document()
    task = content_production.build_phase_task(store, doc, operation_id='revision-result', intent='input_revision')
    doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, 'dispatch-revision-result')
    task = tasks_lookup(store, task['task_id'])
    claim_fixture_task(project, task)
    page = _page(store, store.load_document(), 'p1', text='先记录未知；紧急程度决定流转，版本未知不等于紧急。')
    result = _submit(project, task, {
        'changed_layers': ['page_copy'],
        'proposals': [{'layer': 'page_copy', 'ref': store.put_json_object(page)}],
        'diff': {'input_digest': models.compute_input_digest(doc), 'summary': '补充条件',
                 'changed_page_ids': ['p1']}}, 'input_revision')
    assert result['status'] == 'accepted'
    assert run_desk.detail(project, task_id=task['task_id'])['task']['current_relation']['status'] == 'current'
    # The old plan remains adopted, but one retained reference cannot keep the
    # original whole compose result current after its Page was replaced.
    assert run_desk.detail(project, task_id=original['task_id'])['task']['current_relation']['status'] == 'historical'


def test_missing_receipt_is_unknown(tmp_path, monkeypatch):
    from deck_master.store import Store
    project, store, task = completed_content(tmp_path)
    monkeypatch.setattr(Store, 'operation_receipt', lambda *args: None)
    assert run_desk.detail(project, task_id=task['task_id'])['task']['current_relation'] == {
        'status': 'unknown', 'reason': 'adoption_receipt_missing'}
