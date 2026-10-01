"""U01 fixed action membership; synthetic projects, no model dispatch."""
import copy
import json
import uuid

import pytest

from deck_master import workbench
from deck_master.models import validate_schema
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_web import _get_json
from test_workbench_actions import commit, synthetic_task
from test_candidates import candidate
from test_content_candidates import dispatch_content_ops_trial, start_task, accept, changeset_envelope
from test_workbench_reads import make_project


@pytest.fixture
def action_project(tmp_path):
    path = tmp_path / 'action-project'
    create_sample(path, page_count=3, readonly=False)
    return path, Store(path)


def add_handoffs(store):
    doc = store.load_document()
    for index, page in enumerate(doc['pages'][:2]):
        task = synthetic_task(doc, 'handoff-' + str(index), 'awaiting_host')
        task['scope_pages'] = [page['page_id']]
        doc['tasks'].append(store.put_json_object(task))
    return commit(store, doc, str(uuid.uuid4()))


def action(summary, kind):
    return next(row for row in summary['next_actions']['actions'] if row['kind'] == kind)


def test_grouped_tasks_pagination_and_per_page_members(action_project):
    path, store = action_project
    add_handoffs(store)
    before = store.read_current()
    summary = workbench.workbench_summary(path)
    handoff = action(summary, 'handoff')
    first = workbench.action_targets(path, handoff['action_id'], revision=summary['revision_id'], limit=1)
    second = workbench.action_targets(path, handoff['action_id'], revision=summary['revision_id'], limit=1, offset=1)
    assert first['total'] == second['total'] == 2
    assert first['targets'][0]['object_id'] == 'handoff-0'
    assert second['targets'][0]['object_id'] == 'handoff-1'
    assert first['targets'][0]['target_id'] != second['targets'][0]['target_id']
    for page in summary['pages'][:2]:
        item = next(item for item in page['attention']['items'] if item['kind'] == 'handoff')
        result = workbench.action_targets(path, item['action_id'], revision=summary['revision_id'])
        assert result['total'] == 1 and result['targets'][0]['page_ids'] == [page['page_id']]
        validate_schema('action_targets', result)
    assert store.read_current() == before


def test_same_title_pages_remain_distinct_without_summary_expansion(action_project):
    path, store = action_project
    doc = store.load_document()
    for entry in doc['pages']:
        entry['blueprint'] = entry['svg'] = entry['svg_preview'] = entry['ppt_preview'] = None
        page = copy.deepcopy(store.read_object_json(entry['page']))
        page['customer_visible']['title'] = 'Same title'
        entry['page'] = store.put_json_object(page)
    commit(store, doc, str(uuid.uuid4()))
    before = workbench.workbench_summary(path)
    result = workbench.action_targets(path, action(before, 'prepare_stage')['action_id'], revision=before['revision_id'])
    assert [target['object_id'] for target in result['targets']] == ['p01', 'p02', 'p03']
    assert all(target['kind'] == 'page_layer' and target['layer'] == 'original_image' for target in result['targets'])
    assert workbench.workbench_summary(path) == before
    assert 'targets' not in json.dumps(before)


def test_candidates_resolve_business_ids_and_damage_stays_isolated(action_project):
    path, store = action_project
    ids = [candidate(store, width=20), candidate(store, width=22)]
    summary = workbench.workbench_summary(path)
    result = workbench.action_targets(path, action(summary, 'compare_candidates')['action_id'], revision=summary['revision_id'])
    assert {target['object_id'] for target in result['targets']} == set(ids)
    assert all(target['kind'] == 'candidate' and target['page_ids'] == ['p01'] for target in result['targets'])
    refs = store.load_document()['candidates']
    (path / refs[0]['path']).write_bytes(b'corrupted')
    damaged = workbench.workbench_summary(path)
    blocked = next(row for row in damaged['next_actions']['actions'] if row['kind'] == 'compare_candidates' and not row['enabled'])
    target = workbench.action_targets(path, blocked['action_id'], revision=damaged['revision_id'])['targets'][0]
    assert target['object_id'] is None and not target['enabled'] and target['status'] == 'unreadable'


def test_candidate_missing_business_identity_cannot_crash_or_guess(action_project):
    path, store = action_project
    candidate(store)
    doc = store.load_document()
    broken = store.read_object_json(doc['candidates'][0])
    broken.pop('candidate_id')
    doc['candidates'] = [store.put_json_object(broken)]
    commit(store, doc, str(uuid.uuid4()))
    summary = workbench.workbench_summary(path)
    result = workbench.action_targets(path, action(summary, 'compare_candidates')['action_id'], revision=summary['revision_id'])
    target = result['targets'][0]
    assert result['total'] == 1 and target['object_id'] is None
    assert not target['enabled'] and target['blocked_reason'] == 'target_identity_mismatch'


def test_changeset_is_not_forced_into_a_single_page(action_project):
    path, store = action_project
    task = dispatch_content_ops_trial(path, store, 'merge', ('p01', 'p02'))
    start_task(path, task)
    accept(path, task, changeset_envelope(store, task, 'merge'))
    summary = workbench.workbench_summary(path)
    result = workbench.action_targets(path, action(summary, 'compare_candidates')['action_id'], revision=summary['revision_id'])
    record = store.read_object_json(store.load_document()['candidates'][0])
    assert result['targets'][0]['kind'] == 'content_changeset'
    assert result['targets'][0]['object_id'] == record['candidate_id']
    assert result['targets'][0]['layer'] == 'content'


def test_reviews_keep_every_real_identity_and_isolate_damage(action_project):
    path, store = action_project
    doc = store.load_document()
    refs = []
    for review_id in ('review-one', 'review-two'):
        value = {'schema_version': 'deck_review.v1', 'review_id': review_id, 'kind': 'content',
                 'status': 'not_evaluated', 'subjects': [doc['pages'][0]['page']], 'dependencies': [],
                 'reviewer': {'type': 'host_self', 'id': 'synthetic', 'execution_ref': None, 'independence_confirmed': False},
                 'observations': ['Synthetic record only'], 'findings': [], 'created_at': '2026-10-01T00:00:00Z', 'replaces': None}
        validate_schema('review', value)
        refs.append(store.put_json_object(value))
    doc['reviews'] = refs
    commit(store, doc, str(uuid.uuid4()))
    summary = workbench.workbench_summary(path)
    selected = action(summary, 'review_quality')
    result = workbench.action_targets(path, selected['action_id'], revision=summary['revision_id'])
    assert [target['object_id'] for target in result['targets']] == ['review-one', 'review-two']
    (path / refs[1]['path']).write_bytes(b'corrupted review')
    result = workbench.action_targets(path, selected['action_id'], revision=summary['revision_id'])
    assert result['total'] == 2 and result['targets'][0]['enabled']
    assert result['targets'][1]['object_id'] is None and not result['targets'][1]['enabled']


def test_live_clock_action_resolves_only_while_snapshot_is_current(action_project):
    path, store = action_project
    doc = store.load_document()
    task = synthetic_task(doc, 'running-one', 'running')
    task['scope_pages'] = ['p01']
    task['execution_ref'] = 'synthetic-execution'
    task['updated_at'] = '2000-01-01T00:00:00Z'
    doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))
    summary = workbench.workbench_summary(path)
    selected = next(row for row in summary['next_actions']['actions'] if row['reason_code'] == 'running_task_stale')
    result = workbench.action_targets(path, selected['action_id'], revision=summary['revision_id'])
    assert result['targets'][0]['object_id'] == task['task_id']
    commit(store, store.load_document(), str(uuid.uuid4()))
    with pytest.raises(workbench.ReadModelError, match='not present'):
        workbench.action_targets(path, selected['action_id'], revision=summary['revision_id'])


def test_300_page_resolution_does_not_scan_history_or_expand_summary(tmp_path, monkeypatch):
    path, store = make_project(tmp_path / 'large', count=300)
    summary = workbench.workbench_summary(path)
    selected = action(summary, 'prepare_stage')
    def no_history(*args, **kwargs):
        raise AssertionError('action resolution must not load the full history view')
    from deck_master import editing
    monkeypatch.setattr(editing, 'history', no_history)
    result = workbench.action_targets(path, selected['action_id'], revision=summary['revision_id'], limit=7)
    assert result['total'] > 7 and len(result['targets']) == 7
    assert workbench.workbench_summary(path) == summary
    assert len(json.dumps(result)) < len(json.dumps(summary))


def test_old_revision_and_foreign_actions_do_not_change_current(action_project, tmp_path):
    path, store = action_project
    add_handoffs(store)
    old = workbench.workbench_summary(path)
    old_action = action(old, 'handoff')
    expected = workbench.action_targets(path, old_action['action_id'], revision=old['revision_id'])
    doc = store.load_document()
    doc['tasks'] = []
    commit(store, doc, str(uuid.uuid4()))
    before = store.read_current()
    assert workbench.action_targets(path, old_action['action_id'], revision=old['revision_id']) == expected
    with pytest.raises(workbench.ReadModelError, match='not present'):
        workbench.action_targets(path, old_action['action_id'], revision=store.current_revision_id())
    other = tmp_path / 'other'
    create_sample(other, page_count=3, readonly=False)
    with pytest.raises(workbench.ReadModelError):
        workbench.action_targets(other, old_action['action_id'], revision=old['revision_id'])
    assert store.read_current() == before


@pytest.mark.parametrize('query', ['', 'revision=', 'revision=a&revision=b', 'revision=a&extra=1', 'revision=a&limit=no', 'revision=a&limit=101', 'revision=a&offset=-1'])
def test_http_rejects_unbounded_or_ambiguous_queries(action_project, query):
    path, store = action_project
    summary = workbench.workbench_summary(path)
    selected = action(summary, 'prepare_stage')
    server = WorkbenchServer(path)
    try:
        url = server.start()
        status, _, payload = _get_json(url + 'api/actions/' + selected['action_id'] + '/targets?' + query)
        assert status == 400 and payload['error']['code'] in ('invalid_action_query', 'invalid_revision')
    finally:
        server.stop()


def test_http_fixed_read_is_bounded_and_unknown_action_is_404(action_project):
    path, store = action_project
    add_handoffs(store)
    summary = workbench.workbench_summary(path)
    server = WorkbenchServer(path)
    try:
        url = server.start()
        target_url = url + 'api/actions/' + action(summary, 'handoff')['action_id'] + '/targets?revision=' + summary['revision_id']
        status, _, result = _get_json(target_url + '&limit=1')
        assert status == 200 and len(result['targets']) == 1 and result['total'] == 2
        status, _, result = _get_json(url + 'api/actions/' + '0' * 32 + '/targets?revision=' + summary['revision_id'])
        assert status == 404 and result['error']['code'] == 'action_not_found'
    finally:
        server.stop()
