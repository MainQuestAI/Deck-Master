"""Warm overview reads retain compact records and still detect corruption."""
from deck_master import workbench
from deck_master.store import Store
from deck_master.models import bump_revision
from test_generation_protocol import flow, freeze, start  # noqa: F401


def test_warm_summary_does_not_reread_request_bodies_and_detects_replacement(flow, monkeypatch):
    path, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    first = workbench.workbench_summary(path)
    reads = []
    original = Store.read_object_json
    def tracked(store, ref):
        reads.append(ref['sha256'])
        return original(store, ref)
    monkeypatch.setattr(Store, 'read_object_json', tracked)
    warm = workbench.workbench_summary(path)
    assert warm == first and reads == []
    request_path = path / frozen['request_ref']['path']
    request_path.write_bytes(b'corrupt after warm cache')
    changed = workbench.workbench_summary(path)
    prompt = changed['pages'][0]['prompt_summary']
    assert prompt['frozen']['status'] == 'unreadable'
    assert prompt['prepared']['status'] == 'recorded'
    assert reads == [frozen['request_ref']['sha256']]


def test_candidate_header_cannot_be_reported_as_a_frozen_request(flow):
    path, store, task, native = flow
    start(flow)
    freeze(flow)
    doc = store.load_document()
    # Explicit damaged linkage: matching task/project/page identities alone
    # cannot turn a candidate header into a frozen generation request.
    wrong = store.put_json_object({'schema_version': 'candidate.v1',
        'candidate_id': 'wrong-kind', 'project_id': doc['project_id'],
        'task_id': task['task_id'], 'page_id': task['scope_pages'][0]})
    updated = bump_revision(doc, {'operation_id': 'wrong-request-kind',
        'kind': 'task_update', 'description': 'Synthetic damaged request linkage', 'read_set': []})
    for index, ref in enumerate(doc['tasks']):
        record = store.read_object_json(ref)
        if record['task_id'] == task['task_id']:
            updated['tasks'][index] = store.put_json_object({**record, 'generation_requests': [wrong]})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='wrong-request-kind')
    prompt = workbench.workbench_summary(path)['pages'][0]['prompt_summary']
    assert prompt['frozen']['status'] == 'unreadable'
    assert prompt['prepared']['status'] == 'recorded'
