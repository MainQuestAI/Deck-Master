"""Warm overview reads retain compact records and still detect corruption."""
from deck_master import workbench
from deck_master.store import Store
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
