import copy
import uuid

import pytest

from deck_master import changes, service, tasks
from deck_master.models import content_identity
from deck_master.operations import OperationError
from deck_master.samples import create_sample
from deck_master.store import Store


@pytest.fixture
def sample(tmp_path):
    project = tmp_path / "synthetic ' $(no-command)"; create_sample(project, page_count=2, readonly=False)
    store = Store(project); doc = store.load_document()
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'intent': 'clarify', 'instruction': 'Clarify the selected page.',
             'annotation_refs': [], 'max_calls': 0,
             'targets': [{'page_id': 'p01', 'page_ref': doc['pages'][0]['page'], 'layer': 'content',
                          'artifact_ref': doc['pages'][0]['page']}]}
    return store, doc, value


def commit(store, value, op=None):
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=value['base_revision'],
                            operation_id=op or str(uuid.uuid4()))
    return plan, result


def start(store, task_id):
    return service.task_start(store.project_root, task_id=task_id, execution_ref='synthetic-test-host',
                              supported_protocols=['changes.v1', 'generation.v1'],
                              capabilities=['change_plan', 'generation_request_freeze', 'attempt_binding', 'native_tool_observation'])


def test_plan_is_readonly_commit_replay_and_real_status_transitions(sample):
    store, doc, value = sample; before = store.read_current(); identity = content_identity(doc)
    plan = changes.plan(store.project_root, input=value)
    assert store.read_current() == before and store.load_document()['tasks'] == doc['tasks']
    assert plan['plan']['actions'][0]['write_slots'] == ['page']
    op = str(uuid.uuid4())
    result = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=op)
    task_id = result['operation_result']['task_ids'][0]; change_id = result['operation_result']['change_id']
    assert content_identity(store.load_document()) == identity
    assert changes.handoff(store.project_root, change_id=change_id)['status'] == 'awaiting_host'
    start(store, task_id)
    assert changes.handoff(store.project_root, change_id=change_id)['status'] == 'running'
    replay = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=op)
    assert replay['operation_result'] == result['operation_result']
    page = store.read_object_json(doc['pages'][0]['page']); page['customer_visible']['title'] = 'Clear title'
    task = tasks._lookup_task(store.load_document(), task_id, store)
    service.accept_result(store.project_root, task_id=task_id, operation_id=task['operation_id'],
                          produced_against=task['produced_against'], result_payload={'kind': 'repair', 'pages': [page]})
    assert changes.handoff(store.project_root, change_id=change_id)['status'] == 'completed'


def test_new_base_or_payload_needs_new_plan_and_new_operation(sample):
    store, doc, value = sample; plan, result = commit(store, value)
    with pytest.raises(OperationError, match='changed'):
        changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    value['instruction'] = 'Different'; value['base_revision'] = store.current_revision_id()
    other = changes.plan(store.project_root, input=value)
    with pytest.raises(OperationError) as error:
        changes.commit(store.project_root, plan_id=other['plan_id'], base_revision=value['base_revision'], operation_id=result['operation_id'])
    assert error.value.error_code == 'operation_payload_conflict'


def test_upper_bound_batch_reserves_once_and_cannot_allocate_more(sample):
    store, doc, value = sample
    value['targets'] = [{'page_id': e['page_id'], 'page_ref': e['page'], 'layer': 'original_image', 'artifact_ref': e['blueprint']} for e in doc['pages']]
    with pytest.raises(OperationError, match='upper bound'): changes.plan(store.project_root, input=value)
    value['max_calls'] = 2
    _, result = commit(store, value)
    now = store.load_document()
    selected = [tasks._lookup_task(now, tid, store) for tid in result['operation_result']['task_ids']]
    assert [len(t['call_allowances']) for t in selected] == [1, 1]
    with pytest.raises(tasks.CallBlocked, match='upper bound'):
        tasks.allocate_call_allowances(store, task_id=selected[0]['task_id'], count=1)
    assert store.current_revision_id() == now['revision_id']


def test_result_cannot_expand_planned_layer_and_cancel_refuses_late_result(sample):
    store, doc, value = sample; _, result = commit(store, value)
    task_id = result['operation_result']['task_ids'][0]; start(store, task_id)
    task = tasks._lookup_task(store.load_document(), task_id, store)
    args = {key: task[key] for key in ('task_id', 'operation_id', 'produced_against')}
    before = store.current_revision_id()
    with pytest.raises(OperationError, match='planned'):
        service.accept_result(store.project_root, **args, result_payload={'kind': 'repair', 'page_order': ['p01']})
    assert store.current_revision_id() == before
    service.task_cancel(store.project_root, task_id=task_id, reason='Synthetic cancellation')
    original_ref = store.load_document()['pages'][0]['page']
    page = store.read_object_json(original_ref); page['customer_visible']['title'] = 'Late'
    with pytest.raises(tasks.TaskConflict, match='after cancellation'):
        service.accept_result(store.project_root, **args, result_payload={'kind': 'repair', 'pages': [page]})
    assert store.load_document()['pages'][0]['page'] == original_ref


def test_foreign_or_forged_plan_and_wrong_target_rejected(sample, tmp_path):
    store, doc, value = sample
    forged = copy.deepcopy(value); forged['targets'][0]['page_ref'] = doc['pages'][1]['page']
    with pytest.raises(OperationError): changes.plan(store.project_root, input=forged)
    plan = changes.plan(store.project_root, input=value)
    record = plan['plan']; record['max_calls'] = 200
    ref = store.put_json_object(record)
    with pytest.raises(OperationError, match='payload'):
        changes.commit(store.project_root, plan_id='plan-' + ref['sha256'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    assert store.current_revision_id() == doc['revision_id']
