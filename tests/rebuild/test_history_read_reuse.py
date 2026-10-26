"""RP-29 request-scoped history reuse; synthetic data, no production calls."""

import json
import uuid

import pytest

from deck_master import editing, operations, personal_recovery, snapshots, ui_journal, view
from deck_master.models import bump_revision
from deck_master.samples import create_sample
from deck_master.store import Store, StoreError
from test_ui_state_clear import save_draft, plan as clear_plan, commit as clear_commit


@pytest.fixture
def history_store(tmp_path):
    project = tmp_path / "history"
    create_sample(project, page_count=2, readonly=False)
    store = Store(project)
    revisions = []
    for i in range(8):
        doc = store.load_document()
        op = str(uuid.uuid4())
        new = bump_revision(
            doc, {"operation_id": op, "kind": "task_update", "description": "Synthetic fixed history " + str(i), "read_set": []}
        )
        with store._locked():
            operations.commit_locked(
                store,
                document=new,
                base_revision=doc["revision_id"],
                operation_id=op,
                kind="fixture.history",
                digest=operations.request_digest(doc, "fixture.history", doc["revision_id"], {}),
                result={"revision_id": new["revision_id"], "fixture": i},
            )
        revisions.append(new["revision_id"])
    return store, revisions, op


def test_history_page_decodes_only_selected_rows_and_parent_when_warm(history_store, monkeypatch):
    store, revisions, _ = history_store
    head = revisions[-1]
    list(snapshots.committed_headers(store))
    calls = []
    original = snapshots.snapshot_evidence

    def counted(store, revision):
        calls.append(revision)
        return original(store, revision)

    monkeypatch.setattr(snapshots, "snapshot_evidence", counted)
    result = editing.history(store.project_root, revision=head, cursor=head + ":" + revisions[1], limit=2, related_only=False)
    assert [row["revision_id"] for row in result["revisions"]] == [revisions[1], revisions[0]]
    assert len(calls) <= 5  # control, fixed head, selected two and their parent
    assert revisions[3] not in calls and revisions[4] not in calls


def test_reason_uses_one_fixed_ancestry_proof(history_store, monkeypatch):
    store, _, _ = history_store
    doc = store.load_document()
    depth = len(list(snapshots.committed_headers(store)))
    calls = []
    original = snapshots._header

    def counted(*args):
        calls.append(args[1])
        return original(*args)

    monkeypatch.setattr(snapshots, "_header", counted)
    assert view._latest_input_update_reason(store, doc) is None
    assert len(calls) == depth


@pytest.mark.parametrize("damage", ["cycle", "foreign", "malformed"])
def test_history_revalidates_warm_intermediate_ancestors(history_store, damage):
    store, revisions, _ = history_store
    list(snapshots.committed_headers(store))
    path = store.revisions_dir / (revisions[3] + ".json")
    doc = json.loads(path.read_bytes())
    if damage == "cycle":
        doc["parent_revision_id"] = revisions[-1]
    elif damage == "foreign":
        doc["project_id"] = "another-project"
    path.write_text("not JSON" if damage == "malformed" else json.dumps(doc))
    with pytest.raises(snapshots.ReadModelError):
        editing.history(store.project_root, revision=revisions[-1], cursor=revisions[-1] + ":" + revisions[0], limit=2)


def test_fixed_head_refuses_newer_cursor_and_unknown_head(history_store):
    store, revisions, _ = history_store
    with pytest.raises(StoreError, match="fixed committed ancestry"):
        editing.history(store.project_root, revision=revisions[2], cursor=revisions[2] + ":" + revisions[-1], limit=2)
    with pytest.raises(snapshots.ReadModelError):
        editing.history(store.project_root, revision="orphan")
    with pytest.raises(StoreError, match="original history head"):
        editing.history(store.project_root, revision=revisions[2], cursor=revisions[-1] + ":" + revisions[0])


def test_reader_rechecks_selected_bytes_and_is_not_a_cross_request_cache(history_store):
    store, revisions, _ = history_store
    reader = snapshots.FixedSnapshotReader(store)
    assert reader.load(revisions[0])["revision_id"] == revisions[0]
    path = store.revisions_dir / (revisions[0] + ".json")
    path.write_text("broken")
    with pytest.raises(snapshots.ReadModelError):
        reader.load(revisions[0])
    with pytest.raises(snapshots.ReadModelError):
        snapshots.FixedSnapshotReader(store)


def test_correct_index_recovery_does_not_write_and_bad_index_is_rebuilt(history_store, monkeypatch):
    store, _, op = history_store
    calls = []
    original = operations._atomic_write_bytes
    monkeypatch.setattr(operations, "_atomic_write_bytes", lambda *a, **k: (calls.append(a[0]), original(*a, **k))[1])
    first = operations.show(store.project_root, operation_id=op)
    second = operations.show(store.project_root, operation_id=op)
    assert first == second and calls == []
    path = store.deck_root / "operations" / (op + ".json")
    path.write_text("corrupt")
    assert operations.show(store.project_root, operation_id=op) == first
    assert calls == [path]
    assert operations.show(store.project_root, operation_id=op) == first and calls == [path]
    # Forged disposable indexes cannot establish a committed operation.
    fake = str(uuid.uuid4())
    (path.parent / (fake + ".json")).write_text(path.read_text().replace(op, fake))
    with pytest.raises(operations.OperationError) as rejected:
        operations.show(store.project_root, operation_id=fake)
    assert rejected.value.error_code == "operation_not_found"


def test_backup_listing_shares_log_and_context_but_checks_each_backup(history_store, monkeypatch):
    store, _, _ = history_store
    project = store.project_root
    for index in range(4):
        save_draft(store, project, text="Synthetic backup " + str(index))
        clear_commit(project, clear_plan(project))
    calls = {"context": 0, "log": 0}
    original_context, original_log = ui_journal.context, ui_journal._read_clear_log

    def context(*a, **k):
        calls["context"] += 1
        return original_context(*a, **k)

    def log(*a, **k):
        calls["log"] += 1
        return original_log(*a, **k)

    monkeypatch.setattr(ui_journal, "context", context)
    monkeypatch.setattr(ui_journal, "_read_clear_log", log)
    rows = personal_recovery.listing(project)["backups"]
    assert len(rows) == 4 and all(row["available"] for row in rows)
    assert calls == {"context": 1, "log": 1}
    path = store.deck_root / "workbench" / "clear-backups" / (rows[1]["backup_id"] + ".json")
    path.write_text("broken")
    rows = personal_recovery.listing(project)["backups"]
    assert [row["available"] for row in rows] == [True, False, True, True]


def test_concurrent_restore_recaptures_state_under_lock(history_store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from deck_master.local_state import LocalStateConflict

    store, _, _ = history_store
    project = store.project_root
    save_draft(store, project, text="Concurrent recovery")
    key = clear_commit(project, clear_plan(project))["manifest_digest"][:16]
    preview = personal_recovery.plan(project, backup_id=key)
    barrier = Barrier(2)

    def restore():
        barrier.wait(timeout=10)
        try:
            return personal_recovery.restore(project, backup_id=key, plan_digest=preview["plan_digest"])["status"]
        except LocalStateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(restore) for _ in range(2)]
        outcomes = [future.result(timeout=20) for future in futures]
    assert sorted(outcomes) == ["conflict", "restored"]
    records = ui_journal.list_drafts(project)["records"]
    assert len(records) == 1 and records[0]["draft"]["content"]["text"] == "Concurrent recovery"
