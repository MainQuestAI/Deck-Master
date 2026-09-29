"""W10 core/query/recovery evidence; explicitly synthetic, never model proof."""
import copy
from datetime import datetime, timezone
import json
import urllib.error
import urllib.request

import pytest

from deck_master import changes, cli, generation, run_desk, service, tasks
from deck_master.models import bump_revision, require_writer
from deck_master.samples import create_sample
from deck_master.store import Store, StoreError
from deck_master.web import WorkbenchServer
from test_candidates import accept, adopt, dispatch, plan, start


@pytest.fixture
def store(tmp_path):
    project = tmp_path / 'run-project'; create_sample(project, page_count=3, readonly=False)
    return Store(project)


def get(url):
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_real_claim_time_survives_same_executor_and_unknown_call(store, monkeypatch):
    task = dispatch(store, layer='original_image')
    monkeypatch.setattr(service, '_utc_now_iso', lambda: '2026-09-30T00:00:00Z')
    start(store, task)
    claimed = run_desk.detail(store.project_root, task_id=task['task_id'])
    assert claimed['task']['execution_started_at'] == '2026-09-30T00:00:00Z'
    assert store.read_current()['minimum_writer'] == 'run-desk.v1'
    pointer = store.read_current()
    monkeypatch.setattr(service, '_utc_now_iso', lambda: '2026-09-30T00:20:00Z')
    start(store, task)
    assert store.read_current() == pointer
    task = tasks._lookup_task(store.load_document(), task['task_id'], store)
    frozen = generation.freeze(store.project_root, task_id=task['task_id'],
        input=generation.prepared_input(store, store.load_document(), task),
        base_revision=store.current_revision_id(), operation_id='freeze-real-core')
    attempt = tasks.call_begin(store, task_id=task['task_id'], allowance_id=task['call_allowances'][0]['allowance_id'],
        execution_ref='synthetic-test-host', request_id=frozen['request_id'])
    tasks.call_settle(store, task_id=task['task_id'], allowance_id=attempt['allowance_id'],
        attempt_id=attempt['attempt_id'], outcome='unknown', report_bytes=None)
    before = store.read_current()
    for _ in range(2):
        value = run_desk.detail(store.project_root, task_id=task['task_id'])
        assert value['task']['execution_started_at'] == claimed['task']['execution_started_at']
        assert value['task']['call_counts'] == {'unknown': 1}
        assert 'verify_unknown_call' in value['task']['human_actions']
        assert value['links']['generation_attempts'][0]['attempt_id'] == attempt['attempt_id']
    assert store.read_current() == before
    service.task_cancel(store.project_root, task_id=task['task_id'])
    value = run_desk.detail(store.project_root, task_id=task['task_id'])
    assert value['task']['status'] == 'cancelled' and value['call_allowances'][0]['state'] == 'unknown'
    assert value['task']['execution_started_at'] == claimed['task']['execution_started_at']


def test_running_is_not_human_todo_and_old_time_is_not_invented(store):
    task = dispatch(store); start(store, task)
    current = tasks._lookup_task(store.load_document(), task['task_id'], store)
    now = datetime.fromisoformat(current['execution_started_at'].replace('Z', '+00:00'))
    assert run_desk.task_row(current, now=now)['human_actions'] == []
    current['updated_at'] = '2026-09-30T00:29:00Z'; current['execution_started_at'] = '2026-09-30T00:00:00Z'
    value = run_desk.task_row(current, now=datetime(2026, 9, 30, 0, 30, tzinfo=timezone.utc))
    assert value['human_actions'] == ['verify_execution']
    del current['execution_started_at']
    value = run_desk.task_row(current, now=datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc))
    assert value['execution_started_at'] is None and value['execution_time_source'] == 'not_recorded'
    assert value['waiting_time_basis'] == 'last_task_update' and value['needs_verification']


def test_pagination_fixed_revision_reverse_completion_and_adoption(store):
    first = dispatch(store); second = dispatch(store, 'p02'); start(store, first); start(store, second)
    frozen = store.current_revision_id()
    expected = run_desk.listing(store.project_root, revision=frozen, limit=1)
    second_result = accept(store, second)
    current = run_desk.listing(store.project_root, limit=1)
    assert current['tasks'][0]['task_id'] == second['task_id']
    assert current['tasks'][0]['human_actions'] == ['compare_candidates']
    assert run_desk.listing(store.project_root, revision=frozen, limit=1) == expected
    next_page = run_desk.listing(store.project_root, revision=frozen, limit=1, offset=1)
    assert next_page['tasks'][0]['task_id'] == first['task_id']
    adopted = adopt(store, plan(store, second_result['candidate_ids']))
    assert adopted['operation_result']['candidate_ids'] == second_result['candidate_ids']
    assert run_desk.detail(store.project_root, task_id=second['task_id'])['task']['human_actions'] == []
    accept(store, first)
    assert run_desk.detail(store.project_root, task_id=first['task_id'])['task']['scope_pages'] == ['p01']
    assert run_desk.listing(store.project_root, limit=1)['pagination']['next_offset'] == 1


def test_group_links_and_handoff_claim_time_share_core_facts(store):
    task = dispatch(store); start(store, task)
    listing = run_desk.listing(store.project_root); group = listing['groups'][0]
    handoff = changes.handoff(store.project_root, change_id=group['change_id'])
    row = handoff['handoff']['tasks'][0]
    detail = run_desk.detail(store.project_root, task_id=task['task_id'])
    assert row['execution_started_at'] == detail['task']['execution_started_at']
    assert row['scope_pages'] == ['p01'] and row['task_id'] == task['task_id']
    assert run_desk.listing(store.project_root, change_id=group['change_id'])['pagination']['total'] == 1
    assert run_desk.listing(store.project_root, status='cancelled')['tasks'] == []


def test_writer_boundary_survives_candidate_adoption_content_and_operation(store):
    task = dispatch(store); start(store, task); result = accept(store, task)
    adopt(store, plan(store, result['candidate_ids']))
    assert store.read_current()['minimum_writer'] == 'run-desk.v1'
    from deck_master.content_plan import attach
    doc = store.load_document(); attach(doc, doc['content_plan']); assert doc['compatibility']['minimum_writer'] == 'run-desk.v1'
    for minimum in ('generation.v1', 'content-plan.v1', 'changes.v1', 'candidates.v1'):
        require_writer(doc, minimum); assert doc['compatibility']['minimum_writer'] == 'run-desk.v1'
    lower = bump_revision(copy.deepcopy(doc), {'operation_id': 'bad-downgrade', 'kind': 'task_update', 'description': 'fault injection', 'read_set': []})
    lower['compatibility']['minimum_writer'] = 'candidates.v1'
    with pytest.raises(StoreError, match='downgraded'):
        store.commit_change(base_revision=doc['revision_id'], document=lower, operation_id='bad-downgrade')


def test_http_cli_identical_readonly_errors_and_legacy_tasks_shape(store, capsys):
    task = dispatch(store); before = store.read_current(); server = WorkbenchServer(store.project_root)
    try:
        url = server.start().rstrip('/')
        status, payload = get(url + '/api/tasks?limit=1')
        assert status == 200 and payload['tasks'][0]['status'] == 'awaiting_host'
        assert cli.main(['task', 'list', '--project', str(store.project_root), '--limit', '1', '--json']) == 0
        assert json.loads(capsys.readouterr().out) == payload
        status, detail = get(url + '/api/tasks/' + task['task_id'])
        assert status == 200
        assert cli.main(['task', 'status', '--project', str(store.project_root), '--task-id', task['task_id'], '--details', '--json']) == 0
        assert json.loads(capsys.readouterr().out) == detail
        status, old = get(url + '/api/tasks')
        assert status == 200 and set(old) == {'project_id', 'revision_id', 'tasks'}
        for query in ('limit=0', 'limit=101', 'limit=abc', 'limit=1&limit=2', 'offset=-1', 'attention=yes', 'status=bogus'):
            status, error = get(url + '/api/tasks?' + query)
            assert status == 400 and error['error']['code'] == 'invalid_run_query'
            assert error['error']['docs_ref'] == run_desk.DOCS
        status, error = get(url + '/api/tasks/missing')
        assert status == 404 and error['error']['code'] == 'task_not_found'
        assert cli.main(['task', 'status', '--project', str(store.project_root), '--task-id', 'missing', '--details']) == 2
        assert json.loads(capsys.readouterr().err) == error
    finally:
        server.stop()
    assert store.read_current() == before


def test_corrupt_task_local_error_does_not_hide_other_tasks(store):
    first = dispatch(store); second = dispatch(store, 'p02')
    doc = store.load_document()
    ref = next(ref for ref in doc['tasks'] if store.read_object_json(ref)['task_id'] == first['task_id'])
    run_desk.listing(store.project_root)
    (store.project_root / ref['path']).write_bytes(b'broken')
    value = run_desk.listing(store.project_root)
    assert any(t['status'] == 'unreadable' and t['error']['docs_ref'] == run_desk.DOCS for t in value['tasks'])
    assert any(t['task_id'] == second['task_id'] for t in value['tasks'])
    assert str(store.project_root) not in json.dumps(value)


def test_fixed_revision_does_not_acquire_a_live_timeout(store, monkeypatch):
    task = dispatch(store)
    monkeypatch.setattr(service, '_utc_now_iso', lambda: '2000-01-01T00:00:00Z')
    start(store, task); revision = store.current_revision_id()
    live = run_desk.detail(store.project_root, task_id=task['task_id'])
    fixed = run_desk.detail(store.project_root, task_id=task['task_id'], revision=revision)
    assert live['task']['needs_verification']
    assert not fixed['task']['needs_verification']
    assert fixed['task']['verification_clock'] == 'not_evaluated_for_fixed_revision'
    assert fixed['task']['execution_started_at'] == live['task']['execution_started_at']
