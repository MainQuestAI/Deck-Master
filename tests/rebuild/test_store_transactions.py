"""T02 store transaction and file-safety tests (AC-S01, AC-S02).

AC-S01 exercises three crash points (blob write, revision write, pointer
swap); each must leave the project on the complete old or complete new
revision, never a mixture.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from deck_master.models import new_document
from deck_master.store import (
    ConflictError,
    OperationCancelled,
    Store,
    StoreError,
)


def _updated_document(base: dict, operation_id: str, description: str) -> dict:
    document = new_document(
        project_id=base["project_id"],
        task=base["task"],
        policy=base["policy"],
    )
    document["parent_revision_id"] = base["revision_id"]
    document["change"] = {
        "operation_id": operation_id,
        "kind": "content_update",
        "description": description,
        "read_set": [],
    }
    return document


@pytest.mark.parametrize("crash_point", ["objects", "document", "pointer"])
def test_atomic_current_failure(
    store: Store, monkeypatch: pytest.MonkeyPatch, crash_point: str
) -> None:
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")

    updated = _updated_document(first, "op-edit-1", "second revision")

    if crash_point == "objects":
        # Fail the blob hard-link/copy stage of put_blob before commit.
        real_link = os.link

        def failing_link(src, dst, *args, **kwargs):
            if str(dst).endswith(".bin"):
                raise OSError("injected failure during blob write")
            return real_link(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "link", failing_link)
        with pytest.raises(OSError):
            store.put_blob(b"payload", ext="bin", operation_id="op-edit-1")
        monkeypatch.undo()
        # The project still resolves to the complete old revision.
        assert store.current_revision_id() == first["revision_id"]
        assert store.load_document() == first
        return

    if crash_point == "document":
        real_write = os.replace

        def failing_replace(src, dst, *args, **kwargs):
            if "/revisions/" in str(dst):
                raise OSError("injected failure during revision write")
            return real_write(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(OSError):
            store.commit_change(
                base_revision=first["revision_id"],
                document=updated,
                operation_id="op-edit-1",
            )
        monkeypatch.undo()
        assert store.current_revision_id() == first["revision_id"]
        assert store.load_document() == first
        return

    # pointer: revision written, pointer swap fails; old stays readable and new is complete.
    real_replace = os.replace

    def failing_replace_pointer(src, dst, *args, **kwargs):
        if str(dst).endswith("current.json"):
            raise OSError("injected failure before pointer swap")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", failing_replace_pointer)
    with pytest.raises(OSError):
        store.commit_change(
            base_revision=first["revision_id"],
            document=updated,
            operation_id="op-edit-1",
        )
    monkeypatch.undo()
    assert store.current_revision_id() == first["revision_id"]
    assert store.load_document() == first
    # The written revision is complete and becomes committable next attempt.
    new_revision = store.commit_change(
        base_revision=first["revision_id"],
        document=updated,
        operation_id="op-edit-1",
    )
    assert new_revision == updated["revision_id"]
    assert store.load_document() == updated


def test_pointer_swapped_response_lost_is_complete_new(store: Store) -> None:
    """Pointer already swapped + caller loses the response = new revision is current."""
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")
    updated = _updated_document(first, "op-edit-1", "second revision")
    revision = store.commit_change(
        base_revision=first["revision_id"],
        document=updated,
        operation_id="op-edit-1",
    )
    reopened = Store(store.project_root)
    assert reopened.current_revision_id() == revision
    assert reopened.load_document() == updated


def test_stale_base_conflict(store: Store) -> None:
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")
    second = _updated_document(first, "op-a", "A")
    store.commit_change(base_revision=first["revision_id"], document=second, operation_id="op-a")

    third = _updated_document(first, "op-b", "B")
    with pytest.raises(ConflictError):
        store.commit_change(
            base_revision=first["revision_id"], document=third, operation_id="op-b"
        )
    assert store.current_revision_id() == second["revision_id"]


def test_read_set_mismatch_blocks_commit(store: Store) -> None:
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")
    blob_ref = store.put_blob(b"payload-v1", ext="bin", operation_id="op-b")
    fourth = _updated_document(first, "op-c", "C")
    fourth["change"] = {
        "operation_id": "op-c",
        "kind": "content_update",
        "description": "C",
        "read_set": [{"identity": blob_ref["path"], "sha256": "f" * 64}],
    }
    with pytest.raises(StoreError):
        store.commit_change(
            base_revision=first["revision_id"], document=fourth, operation_id="op-c"
        )
    assert store.current_revision_id() == first["revision_id"]

    # Correct read_set passes verification and commits.
    fifth = _updated_document(first, "op-d", "D")
    fifth["change"] = {
        "operation_id": "op-d",
        "kind": "content_update",
        "description": "D",
        "read_set": [{"identity": blob_ref["path"], "sha256": blob_ref["sha256"]}],
    }
    revision = store.commit_change(
        base_revision=first["revision_id"], document=fifth, operation_id="op-d"
    )
    assert revision == fifth["revision_id"]


def test_cancelled_task_check_blocks_commit(store: Store) -> None:
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")
    updated = _updated_document(first, "op-x", "X")
    with pytest.raises(OperationCancelled):
        store.commit_change(
            base_revision=first["revision_id"],
            document=updated,
            operation_id="op-x",
            cancelled_task_check=lambda: True,
        )
    assert store.current_revision_id() == first["revision_id"]


def test_path_escape_and_symlink_rejected(store: Store) -> None:
    with pytest.raises(StoreError):
        store.put_blob(b"x", ext="json/../evil")
    with pytest.raises(StoreError):
        store.put_blob(b"x", ext="JSON")

    outside = store.project_root / "outside-secret.txt"
    outside.write_bytes(b"secret")
    payload = b"secret-or-not"
    digest = hashlib.sha256(payload).hexdigest()
    object_dir = store.objects_dir / digest[:2]
    object_dir.mkdir(parents=True, exist_ok=True)
    object_path = object_dir / f"{digest}.bin"
    os.symlink(outside, object_path)
    with pytest.raises(StoreError):
        store.put_blob(payload, ext="bin", operation_id="op-sym")
    assert outside.read_bytes() == b"secret"
    assert object_path.is_symlink()

    with pytest.raises(StoreError):
        store.read_object_bytes(
            {"path": f".deckmaster/objects/{digest[:2]}/{digest}.bin", "sha256": digest}
        )


def test_corrupt_object_cannot_overwrite_or_read(store: Store) -> None:
    real_payload = json.dumps({"legit": True}, sort_keys=True).encode()
    real_digest = hashlib.sha256(real_payload).hexdigest()
    object_dir = store.objects_dir / real_digest[:2]
    object_dir.mkdir(parents=True, exist_ok=True)
    (object_dir / f"{real_digest}.json").write_bytes(b'{"tampered": true}')
    with pytest.raises(StoreError):
        store.put_blob(real_payload, ext="json", operation_id="op-c")
    assert (object_dir / f"{real_digest}.json").read_bytes() == b'{"tampered": true}'

    good = store.put_blob(b"clean", ext="txt", operation_id="op-r")
    (store.objects_dir / good["sha256"][:2] / f"{good['sha256']}.txt").write_bytes(b"dirty")
    with pytest.raises(StoreError):
        store.read_object_bytes(good)


def test_identical_bytes_reuse_object(store: Store) -> None:
    first = store.put_blob(b"same-bytes", ext="bin", operation_id="op-1")
    second = store.put_blob(b"same-bytes", ext="bin", operation_id="op-2")
    assert first == second


def test_document_revision_files_are_immutable(store: Store) -> None:
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")
    path = store.revisions_dir / f"{first['revision_id']}.json"
    with pytest.raises(StoreError):
        store.save_revision({**first, "task": {**first["task"], "title": "hijack"}})
    assert json.loads(path.read_text("utf-8"))["task"]["title"] == "One"


def test_operation_id_cannot_escape_staging(store: Store) -> None:
    with pytest.raises(StoreError):
        store.put_blob(b"x", ext="bin", operation_id="../escape")


def test_idempotent_replay_returns_same_revision(store: Store) -> None:
    first = new_document(project_id="demo", task={"title": "One", "brief": "First."})
    store.init_project(first, operation_id="op-create-1")
    updated = _updated_document(first, "op-edit-1", "second revision")
    first_result = store.commit_change(
        base_revision=first["revision_id"], document=updated, operation_id="op-edit-1"
    )
    replay_result = store.commit_change(
        base_revision=updated["revision_id"], document=updated, operation_id="op-edit-1"
    )
    assert first_result == replay_result == updated["revision_id"]

    conflicting = _updated_document(first, "op-edit-1", "second revision")
    with pytest.raises(StoreError):
        store.commit_change(
            base_revision=updated["revision_id"], document=conflicting, operation_id="op-edit-1"
        )
