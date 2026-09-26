"""W02 recovery slice: synthetic fault injection, not real Host acceptance."""
import copy
import json
from pathlib import Path

import pytest

from deck_master import service, tasks, store as store_module
from deck_master.models import ModelError, bump_revision, canonical_json_bytes, sha256_bytes
from deck_master.store import Store

ENVELOPE = Path(__file__).resolve().parents[2] / "docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/compose.json"


def pending(tmp_path):
    project = tmp_path / "synthetic-project"
    source = tmp_path / "synthetic.md"
    source.write_text("Synthetic recovery fixture. Not customer material.")
    service.create(project, brief="W02 recovery test", sources=[source])
    task = service.continue_project(project)["pending_tasks"][0]
    return project, Store(project), task, json.loads(ENVELOPE.read_text())


def submit(project, task, payload, **overrides):
    args = {k: task[k] for k in ("task_id", "operation_id", "produced_against")}
    return service.accept_result(project, result_payload=payload, **(args | overrides))


def advance(store):
    doc = store.load_document()
    later = bump_revision(doc, {"operation_id": "later-independent-progress", "kind": "task_update",
                               "description": "synthetic later progress", "read_set": []})
    store.commit_change(base_revision=doc["revision_id"], document=later, operation_id="later-independent-progress")
    return later["revision_id"]


def journal_path(store, task):
    return store.deck_root / "operations" / (task["operation_id"] + ".json")


def test_lost_response_after_commit_recovers_across_later_commit(tmp_path, monkeypatch):
    project, store, task, payload = pending(tmp_path)
    original = tasks.write_operation_journal

    def crash(*args, **kwargs):
        raise SystemExit("synthetic process crash after pointer swap")

    monkeypatch.setattr(tasks, "write_operation_journal", crash)
    with pytest.raises(SystemExit):
        submit(project, task, payload)
    applied = store.load_document()
    receipt = applied["change"]["operation_receipt"]
    completed = next(store.read_object_json(r) for r in applied["tasks"]
                     if store.read_object_json(r)["task_id"] == task["task_id"])
    assert completed["status"] == "completed"
    assert completed["result_refs"] == receipt["response"]["result_refs"] == [applied["pages"][0]["page"]]
    assert not journal_path(store, task).exists()
    later = advance(store)
    pointer = (store.deck_root / "current.json").read_bytes()
    monkeypatch.setattr(tasks, "write_operation_journal", original)
    replay = submit(project, task, payload)
    assert replay["status"] == "already_applied"
    assert replay["revision_id"] == applied["revision_id"]
    assert replay["current_revision_id"] == later
    assert replay["operation_result"] == receipt["response"]
    assert replay["result_refs"] == completed["result_refs"]
    assert (store.deck_root / "current.json").read_bytes() == pointer
    assert json.loads(journal_path(store, task).read_text())["revision_id"] == applied["revision_id"]


def test_journal_io_error_reports_committed_result_and_recoverable_warning(tmp_path, monkeypatch):
    project, store, task, payload = pending(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("/private/not-for-clients/journal.json")

    monkeypatch.setattr(tasks, "write_operation_journal", fail)
    first = submit(project, task, payload)
    assert first["status"] == "accepted"
    assert first["journal_warning"]["code"] == "receipt_cache_unavailable"
    assert "/private/not-for-clients" not in json.dumps(first)
    replay = submit(project, task, payload)
    assert replay["status"] == "already_applied"
    assert replay["operation_result"] == first["operation_result"]
    assert replay["journal_warning"] == first["journal_warning"]


@pytest.mark.parametrize("difference", ["payload", "binding"])
def test_committed_request_refuses_changed_payload_or_binding(tmp_path, difference):
    project, store, task, payload = pending(tmp_path)
    submit(project, task, payload)
    journal_path(store, task).unlink()
    advance(store)
    before = store.current_revision_id()
    changed = copy.deepcopy(payload)
    if difference == "payload":
        changed["notes"] = "A different logical result"
    overrides = {"produced_against": "a" * 64} if difference == "binding" else {}
    with pytest.raises(tasks.TaskConflict, match="different result"):
        submit(project, task, changed, **overrides)
    assert store.current_revision_id() == before
    assert not journal_path(store, task).exists()


def test_orphan_receipt_from_failed_pointer_swap_is_not_an_applied_operation(tmp_path, monkeypatch):
    project, store, task, payload = pending(tmp_path)
    before = store.current_revision_id()
    old_revisions = set(store.revisions_dir.iterdir())
    original = store_module._atomic_write_bytes

    def fail_pointer(path, data):
        if path.name == "current.json":
            raise OSError("synthetic pointer failure")
        return original(path, data)

    monkeypatch.setattr(store_module, "_atomic_write_bytes", fail_pointer)
    with pytest.raises(OSError):
        submit(project, task, payload)
    assert store.current_revision_id() == before
    assert set(store.revisions_dir.iterdir()) - old_revisions
    assert store.operation_receipt(task["operation_id"]) is None
    assert not journal_path(store, task).exists()
    monkeypatch.setattr(store_module, "_atomic_write_bytes", original)
    assert submit(project, task, payload)["status"] == "accepted"


def test_legacy_completed_task_without_digest_is_not_guessed(tmp_path):
    project, store, task, payload = pending(tmp_path)
    submit(project, task, payload)
    legacy = store.load_document()
    legacy["change"].pop("operation_receipt")
    # An old-format synthetic fixture, not an in-place production migration.
    (store.revisions_dir / (legacy["revision_id"] + ".json")).write_bytes(canonical_json_bytes(legacy))
    journal_path(store, task).unlink()
    assert store.operation_receipt(task["operation_id"]) is None
    with pytest.raises(tasks.TaskConflict, match="already completed"):
        submit(project, task, payload)


@pytest.mark.parametrize("damaged", [b"not JSON", b'{"result_digest":"wrong"}'])
def test_committed_receipt_rebuilds_a_corrupt_or_conflicting_journal_cache(tmp_path, damaged):
    project, store, task, payload = pending(tmp_path)
    first = submit(project, task, payload)
    journal_path(store, task).write_bytes(damaged)
    replay = submit(project, task, payload)
    assert replay["operation_result"] == first["operation_result"]
    assert json.loads(journal_path(store, task).read_bytes())["result_digest"] == sha256_bytes(canonical_json_bytes(tasks.parse_envelope(payload)))


def test_input_revision_recovery_keeps_changed_page_refs_and_alignment(tmp_path, monkeypatch):
    project, store, task, payload = pending(tmp_path)
    submit(project, task, payload)
    update = service.inputs_update(project, patch={"task_patch": {"audience": "Synthetic new audience"}, "reason": "test"},
                                   base_revision=store.current_revision_id(), operation_id="synthetic-new-input")
    task = update["pending_tasks"][0]
    page = store.read_object_json(store.load_document()["pages"][0]["page"])
    page["customer_visible"]["title"] = "New title for new inputs"
    result = {"kind": "compose", "content_update": {"input_digest": update["input_digest"], "upsert_pages": [page],
              "remove_page_ids": [], "page_order": [page["page_id"]], "impact_summary": "Changed the title"}}
    original = tasks.write_operation_journal
    monkeypatch.setattr(tasks, "write_operation_journal", lambda *a, **kw: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        submit(project, task, result)
    applied = store.load_document()
    advance(store)
    monkeypatch.setattr(tasks, "write_operation_journal", original)
    replay = submit(project, task, result)
    assert replay["revision_id"] == applied["revision_id"]
    assert replay["input_alignment"] == "current"
    assert replay["result_refs"] == [applied["pages"][0]["page"]]
    assert replay["operation_result"]["impact_summary"] == "Changed the title"


def test_a_receipt_cannot_be_carried_into_a_different_revision(tmp_path):
    project, store, task, payload = pending(tmp_path)
    submit(project, task, payload)
    invalid = copy.deepcopy(store.load_document())
    invalid["parent_revision_id"] = invalid["revision_id"]
    invalid["revision_id"] = "synthetic-wrong-receipt-revision"
    with pytest.raises(ModelError, match="operation_receipt"):
        store.save_revision(invalid)
    assert not (store.revisions_dir / (invalid["revision_id"] + ".json")).exists()
