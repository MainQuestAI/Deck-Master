"""Recovery keeps damaged preview bytes and excludes superseded workers."""
import hashlib
import json
import subprocess
import sys

import pytest

from deck_master import candidate_preview as preview
from deck_master.local_state import write_json
from deck_master.operations import OperationError
from test_icon_quality import icon_store, confirm, input_for, dispatch, start, accept


@pytest.fixture
def context(created_store, monkeypatch):
    identity = {"candidate_ref": {"sha256": "candidate"}}
    value = (created_store, {}, {}, {}, {}, {}, b"", {}, {}, identity, "a" * 64)
    monkeypatch.setattr(preview, "_context", lambda *args: value)
    return value


def state_path(context):
    return preview._state_path(context[0], context[-1])


def cached_report(context, check_id="old-check"):
    folder = state_path(context).parent
    report = {"identity": context[-2], "cache_key": context[-1],
              "candidate_ref": context[-2]["candidate_ref"], "candidate_id": "candidate",
              "check_id": check_id, "status": "ready", "native_check": "pass",
              "readback": {"status": "pass"}, "scope_check": {"status": "pass"}, "files": {}}
    for name in ("candidate.svg", "candidate.pptx", "candidate.png", "readback.json"):
        raw = ("original " + name).encode()
        (folder / name).write_bytes(raw)
        report["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    write_json(folder / "report.json", report)
    return report


@pytest.mark.parametrize("raw", [b"{", b"[]", b"null", b"{}", b'{"status":"running"}',
    b'{"status":"invented","cache_key":"bad","check_id":"old"}',
    *[json.dumps({"status": "failed", "cache_key": "a" * 64, "check_id": "old", field: value}).encode()
      for field, value in (("error", None), ("error", "broken"), ("candidate_id", []))]])
def test_damaged_state_is_read_only_and_never_reuses_ready_report(context, raw):
    cached_report(context)
    path = state_path(context)
    path.write_bytes(raw)
    for result in (preview.status(context[0].project_root, candidate_id="candidate"),
                   preview.request(context[0].project_root, candidate_id="candidate")):
        assert result["status"] == "interrupted"
        assert result["error"]["code"] == "candidate_preview_state_damaged"
    assert path.read_bytes() == raw
    with pytest.raises(OperationError):
        preview.require_ready(context[0].project_root, "candidate")
    with pytest.raises(OperationError):
        preview.file_bytes(context[0].project_root, cache_key=context[-1], name="candidate.png")


def test_missing_state_is_distinct_from_invalid_state(context):
    assert preview.status(context[0].project_root, candidate_id="candidate")["status"] == "not_requested"
    assert not state_path(context).exists()


def test_explicit_retry_preserves_all_original_bytes_before_starting(context, monkeypatch):
    cached_report(context)
    path = state_path(context)
    path.write_bytes(b'{"broken"')
    originals = {p.name: p.read_bytes() for p in path.parent.iterdir() if p.is_file()}
    calls = []

    def generate(project, candidate_id, value, check_id, lease):
        calls.append(check_id)
        try:
            backups = list(path.parent.glob("recovery-*"))
            assert len(backups) == 1
            assert {p.name: p.read_bytes() for p in backups[0].iterdir()} == originals
            assert json.loads(path.read_bytes())["check_id"] == check_id
            assert preview._publish(value[0], value[-1], check_id, {"status": "failed"})
        finally:
            lease.close()
            preview._JOBS.pop((str(value[0].project_root), value[-1]), None)

    monkeypatch.setattr(preview, "_generate", generate)
    result = preview.request(context[0].project_root, candidate_id="candidate", retry=True)
    assert result["status"] == "failed" and result["check_id"] == calls[0]
    assert calls[0] != "old-check"


@pytest.mark.parametrize("failure", ["backup", "state"])
def test_retry_write_failure_keeps_state_and_releases_lease(context, monkeypatch, failure):
    cached_report(context)
    path = state_path(context)
    path.write_bytes(b"{broken")
    originals = {p.name: p.read_bytes() for p in path.parent.iterdir() if p.is_file()}
    started = []
    monkeypatch.setattr(preview, "_generate", lambda *args: started.append(True))
    atomic = preview._atomic_write_bytes
    original_write = preview.write_json

    def fail_backup(target, raw):
        if target.parent.name.startswith("recovery-"):
            raise OSError("backup disk full")
        return atomic(target, raw)

    def fail_state(target, value):
        if target == path:
            raise OSError("state disk full")
        return original_write(target, value)

    monkeypatch.setattr(preview, "_atomic_write_bytes", fail_backup if failure == "backup" else atomic)
    monkeypatch.setattr(preview, "write_json", fail_state if failure == "state" else original_write)
    with pytest.raises(OperationError):
        preview.request(context[0].project_root, candidate_id="candidate", retry=True)
    assert not started
    assert all((path.parent / name).read_bytes() == raw for name, raw in originals.items())
    import fcntl
    with (path.parent / "worker.lock").open("a+b") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_live_cross_process_lease_prevents_damaged_state_takeover(context):
    path = state_path(context)
    path.write_bytes(b"{broken")
    code = """import fcntl,sys
with open(sys.argv[1], 'a+b') as lease:
    fcntl.flock(lease, fcntl.LOCK_EX)
    print('locked', flush=True)
    sys.stdin.read()
"""
    process = subprocess.Popen([sys.executable, "-c", code, str(path.parent / "worker.lock")],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "locked"
        for result in (preview.status(context[0].project_root, candidate_id="candidate"),
                       preview.request(context[0].project_root, candidate_id="candidate", retry=True)):
            assert result["status"] == "busy"
        assert path.read_bytes() == b"{broken"
        assert not list(path.parent.glob("recovery-*"))
    finally:
        process.communicate(timeout=5)
    assert preview.status(context[0].project_root, candidate_id="candidate")["status"] == "interrupted"


def test_download_rejects_report_from_another_check(context):
    cached_report(context, "old-check")
    write_json(state_path(context), {"status": "failed", "cache_key": context[-1], "check_id": "new-check"})
    with pytest.raises(OperationError):
        preview.file_bytes(context[0].project_root, cache_key=context[-1], name="candidate.png")


def test_download_url_remains_bound_to_original_check(context):
    report = cached_report(context, "new-check")
    write_json(state_path(context), {"status": "ready", "cache_key": context[-1], "check_id": "new-check"})
    assert "check_id=new-check" in preview._public(report)["files"]["candidate.png"]["url"]
    with pytest.raises(OperationError):
        preview.file_bytes(context[0].project_root, cache_key=context[-1], name="candidate.png", check_id="old-check")
    raw, _ = preview.file_bytes(context[0].project_root, cache_key=context[-1], name="candidate.png", check_id="new-check")
    assert raw == b"original candidate.png"


@pytest.mark.parametrize("candidate_id", [None, [], ""])
def test_download_refuses_damaged_report_candidate(context, candidate_id):
    report = cached_report(context)
    report["candidate_id"] = candidate_id
    write_json(state_path(context).parent / "report.json", report)
    write_json(state_path(context), {"status": "ready", "cache_key": context[-1], "check_id": "old-check"})
    with pytest.raises(OperationError) as failure:
        preview.file_bytes(context[0].project_root, cache_key=context[-1], name="candidate.png")
    assert "candidate is not available" in str(failure.value)


def test_late_worker_cannot_publish_state(context):
    write_json(state_path(context), {"status": "queued", "cache_key": context[-1], "check_id": "new-check"})
    assert preview._publish(context[0], context[-1], "old-check", {"status": "ready"}) is False
    assert json.loads(state_path(context).read_bytes())["check_id"] == "new-check"


def test_late_worker_cannot_publish_any_file_or_remove_new_job(context):
    report = cached_report(context, "new-check")
    path = state_path(context)
    write_json(path, {"status": "ready", "cache_key": context[-1], "check_id": "new-check"})
    originals = {p.name: p.read_bytes() for p in path.parent.iterdir() if p.is_file()}
    late = {**report, "check_id": "old-check", "files": {}}
    assert preview._publish_report(context[0], context[-1], "old-check", late,
                                   {"candidate.png": b"late bytes"}) is False
    assert all((path.parent / name).read_bytes() == raw for name, raw in originals.items())
    job = (str(context[0].project_root), context[-1])
    preview._JOBS[job] = {"check_id": "new-check"}
    with (path.parent / "worker.lock").open("a+b") as lease:
        preview._generate(context[0].project_root, "candidate", context, "old-check", lease)
        assert lease.closed
    assert preview._JOBS.pop(job) == {"check_id": "new-check"}


@pytest.mark.parametrize("wait", [True, False])
def test_publish_error_always_releases_worker_lease(context, monkeypatch, wait):
    def broken_publish(*args):
        raise OSError("state disk full")
    monkeypatch.setattr(preview, "_publish", broken_publish)
    if not wait:
        def broken_submit(*args):
            raise RuntimeError("executor unavailable")
        monkeypatch.setattr(preview._EXECUTOR, "submit", broken_submit)
    with pytest.raises(OperationError):
        preview.request(context[0].project_root, candidate_id="candidate", wait=wait)
    assert (str(context[0].project_root), context[-1]) not in preview._JOBS
    import fcntl
    with (state_path(context).parent / "worker.lock").open("a+b") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.render
def test_damaged_state_retries_actual_compile_render_and_readback(icon_store):
    recipe = confirm(icon_store, input_for(icon_store, method="standard"))
    task = dispatch(icon_store, recipe)[0]
    start(icon_store, task)
    from deck_master import icons
    raw = icons.draft(icon_store.project_root, recipe_id=recipe["recipe_id"], page_id="p01")["svg"].encode()
    candidate_id = accept(icon_store, task, raw)["candidate_ids"][0]
    revision = icon_store.current_revision_id()
    original = preview.request(icon_store.project_root, candidate_id=candidate_id)
    assert original["status"] == "ready", original
    path = preview._state_path(icon_store, original["cache_key"])
    path.write_bytes(b'{"interrupted write"')
    names = ("state.json", "report.json", "candidate.svg", "candidate.pptx", "candidate.png", "readback.json")
    saved = {name: (path.parent / name).read_bytes() for name in names}
    assert preview.status(icon_store.project_root, candidate_id=candidate_id)["status"] == "interrupted"
    result = preview.request(icon_store.project_root, candidate_id=candidate_id, retry=True)
    assert result["status"] == "ready", result
    assert result["check_id"] != original["check_id"]
    assert result["native_check"] == result["readback"]["status"] == result["scope_check"]["status"] == "pass"
    backup = path.parent / ("recovery-" + result["check_id"])
    assert {name: (backup / name).read_bytes() for name in names} == saved
    assert icon_store.current_revision_id() == revision
    pptx, media = preview.file_bytes(icon_store.project_root, cache_key=result["cache_key"], name="candidate.pptx")
    assert pptx[:2] == b"PK" and media.endswith("presentation")
