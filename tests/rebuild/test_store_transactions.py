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


# ---------------------------------------------------------------------------
# T12 evidence: invalidation scope (AC-S04), concurrency/rebase (AC-S08),
# restore and relocation (AC-S10).

import shutil
from copy import deepcopy

from deck_master import service
from deck_master.editing import edit_page, restore
from deck_master.pipeline import artifact as adopt_artifact
from deck_master.store import Store
import hashlib


def _page(page_id, title):
    return {
        "schema_version": "deck_page_package.v2",
        "page_id": page_id,
        "customer_visible": {"title": title, "body_blocks": [
            {"id": "b1", "type": "paragraph", "text": f"{title}的正文。"}]},
        "visual_spec": {"intent": "test", "reference_mode": "new_design"},
    }


def _two_page_project(tmp_path):
    project = tmp_path / "proj"
    service.create(project, brief="局部修改", draft={"pages": [_page("p1", "标题一"), _page("p2", "标题二")]})
    return project


def _attach_slots(store, document, svg_bytes=b"<svg viewBox='0 0 10 10'/>", png_bytes=b""):
    """Fabricate blueprint/svg/preview artifacts per page plus current outputs."""
    from PIL import Image
    import io as _io
    if not png_bytes:
        buffer = _io.BytesIO()
        Image.new("RGB", (8, 6), (240, 240, 240)).save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
    work = store.staging_dir / "attach"
    work.mkdir(parents=True, exist_ok=True)
    svg_file = work / "page.svg"
    svg_file.write_bytes(svg_bytes)
    png_file = work / "art.png"
    png_file.write_bytes(png_bytes)
    from deck_master.models import bump_revision
    bumped = bump_revision(document, {"operation_id": "attach-fixtures", "kind": "task_update",
                                      "description": "attach fixtures", "read_set": []})
    bumped["outputs"] = dict(bumped.get("outputs") or {})
    for entry in bumped["pages"]:
        entry["blueprint"] = adopt_artifact(store, png_file, "blueprint", page_id=entry["page_id"])
        entry["svg"] = adopt_artifact(store, svg_file, "svg", page_id=entry["page_id"])
        entry["svg_preview"] = adopt_artifact(store, png_file, "svg_preview", page_id=entry["page_id"])
        entry["ppt_preview"] = adopt_artifact(store, png_file, "ppt_preview", page_id=entry["page_id"])
    pptx_file = work / "deck.pptx"
    pptx_file.write_bytes(b"fake-pptx-bytes")
    bumped["outputs"]["pptx"] = adopt_artifact(store, pptx_file, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="attach-fixtures")
    return store.load_document()


def _slot_refs(document, page_id):
    entry = next(e for e in document["pages"] if e["page_id"] == page_id)
    return {slot: entry[slot] for slot in ("blueprint", "svg", "svg_preview", "ppt_preview")}


def test_task_management_changes_do_not_invalidate_untouched_pages(tmp_path):
    # AC-S04 negative: task claim/cancel (budget/notes analogues) advance
    # revisions but keep every page slot and current outputs untouched.
    project = _two_page_project(tmp_path)
    store = Store(project)
    document = _attach_slots(store, store.load_document())
    task = service.open_host_task(store, kind="repair", page_ids=["p1"], instruction="notes only")
    service.task_start(project, task_id=task["task_id"], execution_ref="run-1")
    service.task_cancel(project, task_id=task["task_id"], reason="budget hold")
    after = store.load_document()
    assert after["revision_id"] != document["revision_id"]
    for page_id in ("p1", "p2"):
        assert _slot_refs(after, page_id) == _slot_refs(document, page_id)
    assert after["outputs"] == document["outputs"]
    assert store.read_object_json(after["tasks"][-1])["status"] == "cancelled"


def test_content_edit_invalidates_only_the_edited_page(tmp_path):
    # AC-S04 positive: a real text edit on p1 clears p1's SVG/previews and the
    # assembled outputs, keeps p1's original blueprint, and leaves p2 untouched.
    project = _two_page_project(tmp_path)
    store = Store(project)
    document = _attach_slots(store, store.load_document())
    page = store.read_object_json(document["pages"][0]["page"])
    changed = deepcopy(page)
    changed["customer_visible"]["title"] = "标题一(修订)"
    result = edit_page(store.project_root, page=changed, base_revision=document["revision_id"],
                       page_hash=document["pages"][0]["page"]["sha256"], operation_id="edit-p1")
    assert result["status"] == "edited"
    after = store.load_document()
    p1 = _slot_refs(after, "p1")
    assert p1["svg"] is None and p1["svg_preview"] is None and p1["ppt_preview"] is None
    assert p1["blueprint"] == _slot_refs(document, "p1")["blueprint"]
    assert _slot_refs(after, "p2") == _slot_refs(document, "p2")
    assert all(value is None for value in after["outputs"].values())


def test_disjoint_page_edits_rebase_safely(tmp_path):
    # AC-S08 positive: writer A edits p1; writer B (working from the older
    # revision) edits p2 — the second commit rebases onto the latest revision.
    project = _two_page_project(tmp_path)
    store = Store(project)
    base = store.load_document()
    first_page = store.read_object_json(base["pages"][0]["page"])
    first = deepcopy(first_page)
    first["customer_visible"]["title"] = "标题一(A)"
    edit_page(store.project_root, page=first, base_revision=base["revision_id"],
              page_hash=base["pages"][0]["page"]["sha256"], operation_id="writer-a")
    second_page = store.read_object_json(base["pages"][1]["page"])
    second = deepcopy(second_page)
    second["customer_visible"]["title"] = "标题二(B)"
    edit_page(store.project_root, page=second, base_revision=base["revision_id"],  # stale base
              page_hash=base["pages"][1]["page"]["sha256"], operation_id="writer-b")
    after = store.load_document()
    assert store.read_object_json(after["pages"][0]["page"])["customer_visible"]["title"] == "标题一(A)"
    assert store.read_object_json(after["pages"][1]["page"])["customer_visible"]["title"] == "标题二(B)"


def test_same_page_concurrent_edit_conflicts_without_overwrite(tmp_path):
    # AC-S08 negative: two writers on the same page — the late one is rejected
    # with its stale page hash; the first writer's content survives.
    project = _two_page_project(tmp_path)
    store = Store(project)
    base = store.load_document()
    first = deepcopy(store.read_object_json(base["pages"][0]["page"]))
    first["customer_visible"]["title"] = "标题一(先写)"
    edit_page(store.project_root, page=first, base_revision=base["revision_id"],
              page_hash=base["pages"][0]["page"]["sha256"], operation_id="writer-a")
    committed = store.load_document()
    late = deepcopy(first)
    late["customer_visible"]["title"] = "标题一(后写覆盖)"
    with pytest.raises(Exception, match="page_hash"):
        edit_page(store.project_root, page=late, base_revision=committed["revision_id"],
                  page_hash=base["pages"][0]["page"]["sha256"], operation_id="writer-b")
    # Same operation_id with a different payload is also a conflict.
    different = deepcopy(first)
    different["customer_visible"]["title"] = "标题一(另一结果)"
    with pytest.raises(Exception, match="operation_id"):
        edit_page(store.project_root, page=different, base_revision=committed["revision_id"],
                  page_hash=committed["pages"][0]["page"]["sha256"], operation_id="writer-a")
    current = store.load_document()
    assert store.read_object_json(current["pages"][0]["page"])["customer_visible"]["title"] == "标题一(先写)"


def test_restore_keeps_call_facts_and_old_snapshot(tmp_path):
    # AC-S10: restore picks old content into a NEW revision; the cancelled
    # task fact and the old snapshot stay exactly as committed.
    project = tmp_path / "proj"
    service.create(project, brief="恢复", draft={"pages": [_page("p1", "原标题")]})
    store = Store(project)
    original = store.load_document()
    response = service.continue_project(project)
    task = response["pending_tasks"][0]
    cancelled = service.task_cancel(project, task_id=task["task_id"], reason="user stop")
    assert cancelled["status"] == "cancelled"
    edited_page = deepcopy(store.read_object_json(original["pages"][0]["page"]))
    edited_page["customer_visible"]["title"] = "改过的标题"
    edit_page(store.project_root, page=edited_page, base_revision=store.load_document()["revision_id"],
              page_hash=original["pages"][0]["page"]["sha256"], operation_id="edit-title")
    current = store.load_document()
    result = restore(store.project_root, revision_id=original["revision_id"],
                     base_revision=current["revision_id"], operation_id="restore-r0")
    assert result["status"] == "restored"
    restored = store.load_document()
    assert restored["revision_id"] not in (current["revision_id"], original["revision_id"])
    assert restored["pages"][0]["page"] == original["pages"][0]["page"]
    # Operation facts survive: the cancelled task is still cancelled...
    statuses = {store.read_object_json(t)["status"] for t in restored["tasks"]}
    assert "cancelled" in statuses
    # ...and the old snapshot itself is untouched and loadable.
    snapshot = store.load_document(current["revision_id"])
    assert snapshot["revision_id"] == current["revision_id"]
    assert store.read_object_json(snapshot["pages"][0]["page"])["customer_visible"]["title"] == "改过的标题"


def test_relocated_project_refs_resolve_and_source_hash_verified(tmp_path):
    # AC-S10 relocation: project-relative object refs keep working after the
    # whole directory moves; a moved source verifies against its known hash.
    material = tmp_path / "brief.txt"
    material.write_text("季度材料正文。", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="搬迁", sources=[material], draft={"pages": [_page("p1", "标题")]})
    store = Store(project)
    document = _attach_slots(store, store.load_document())
    moved = tmp_path / "moved"
    shutil.copytree(project, moved)
    relocated = Store(moved)
    moved_doc = relocated.load_document()
    assert moved_doc["revision_id"] == document["revision_id"]
    assert relocated.read_object_bytes(moved_doc["pages"][0]["page"]) == \
        store.read_object_bytes(document["pages"][0]["page"])
    pptx = relocated.read_object_json(moved_doc["outputs"]["pptx"])
    assert relocated.read_object_bytes(pptx["file"]) == b"fake-pptx-bytes"
    # The user remaps the source next to the moved project; the known original
    # hash verifies the new bytes as the same source version.
    moved_material = moved / "brief.txt"
    shutil.copyfile(material, moved_material)
    source = moved_doc["sources"][0]
    assert hashlib.sha256(moved_material.read_bytes()).hexdigest() == source["original_sha256"]
    # A different byte version is detected instead of being silently accepted.
    moved_material.write_text("季度材料正文(改)。", encoding="utf-8")
    assert hashlib.sha256(moved_material.read_bytes()).hexdigest() != source["original_sha256"]
