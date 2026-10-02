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


def test_pinned_read_directories_resist_redirection_and_close(tmp_path):
    import os
    import pytest
    store = Store(tmp_path)
    store.ensure_layout()
    ref = store.put_json_object({"value": "original"})
    ctx = workbench._ReadContext(store, {}, pin_directories=True)
    try:
        first = ctx.object_stat(ref)
        bucket = tmp_path / ref["path"].rsplit("/", 1)[0]
        moved = bucket.with_name(bucket.name + "-original")
        bucket.rename(moved)
        bucket.symlink_to(moved, target_is_directory=True)
        assert ctx.object_stat(ref).st_ino == first.st_ino
        other = workbench._ReadContext(store, {}, pin_directories=True)
        try:
            with pytest.raises(OSError):
                other.object_stat(ref)
        finally:
            other.close()
        descriptors = list(ctx.directory_fds.values())
    finally:
        ctx.close()
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_summary_closes_pinned_directories_after_failure(flow, monkeypatch):
    import os
    import pytest
    path, store, task, native = flow
    descriptors = []
    def fail(ctx, **kwargs):
        ctx.object_stat(ctx.document["tasks"][0])
        descriptors.extend(ctx.directory_fds.values())
        raise ValueError("projection failed")
    monkeypatch.setattr(workbench, "_summary", fail)
    with pytest.raises(ValueError, match="projection failed"):
        workbench.workbench_summary(path)
    assert descriptors
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_summary_reuse_expires_at_live_task_deadline(flow, monkeypatch):
    from datetime import datetime, timedelta, timezone
    path, store, task, native = flow
    start(flow)
    first = workbench.workbench_summary(path)
    revision = first["revision_id"]
    def reasons(summary):
        return {item["reason_code"] for item in summary["next_actions"]["actions"]}
    assert "running_task_stale" not in reasons(first)
    future = datetime.now(timezone.utc) + timedelta(seconds=1801)
    class FutureClock:
        @staticmethod
        def now(tz):
            return future
        fromisoformat = staticmethod(datetime.fromisoformat)
    monkeypatch.setattr(workbench, "datetime", FutureClock)
    assert "running_task_stale" in reasons(workbench.workbench_summary(path))
    assert "running_task_stale" not in reasons(workbench.workbench_summary(path, revision=revision))


def test_summary_reuse_detaches_results_and_detects_repair(flow):
    path, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    first = workbench.workbench_summary(path)
    first["pages"][0]["prompt_summary"]["frozen"]["status"] = "tampered by caller"
    assert workbench.workbench_summary(path)["pages"][0]["prompt_summary"]["frozen"]["status"] == "recorded"
    original = path / frozen["request_ref"]["path"]
    data = original.read_bytes()
    original.unlink()
    assert workbench.workbench_summary(path)["pages"][0]["prompt_summary"]["frozen"]["status"] == "unreadable"
    original.write_bytes(data)
    assert workbench.workbench_summary(path)["pages"][0]["prompt_summary"]["frozen"]["status"] == "recorded"
