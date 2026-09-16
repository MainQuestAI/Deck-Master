"""T04 task tests: the five result envelopes and atomic adoption (AC-S14)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import deck_master.service as service
from deck_master import tasks as tasks_mod
from deck_master.models import canonical_json_bytes, sha256_bytes
from deck_master.store import Store

SPEC_DIR = Path(__file__).resolve().parents[2] / "docs" / "specs" / "deck-master-rebuild-v1"
ENVELOPES = SPEC_DIR / "examples" / "roundtrips" / "result-envelope"


def _make_project(tmp_path: Path) -> tuple[Path, dict]:
    material = tmp_path / "material.txt"
    material.write_text("季度对照正文\n(尾部约束)合成数据不可回写。", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="设备运维汇报", sources=[material])
    response = service.continue_project(project)
    return project, response["pending_tasks"][0]


def _compose_envelope() -> dict:
    return json.loads((ENVELOPES / "compose.json").read_text())


def _staging_dir(project: Path, operation_id: str) -> Path:
    staging = project / ".deckmaster" / "staging" / operation_id
    staging.mkdir(parents=True, exist_ok=True)
    return staging


def test_envelope_roundtrip(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    response = service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=json.loads((ENVELOPES / "compose.json").read_text()),
    )
    assert response["status"] == "accepted"
    assert response["next_action"] == "auto_view_then_production"
    document = service.Store(project).load_document()
    assert len(document["pages"]) == 1
    assert document["pages"][0]["page_id"] == "p09"
    assert document["tasks"][0]["path"].startswith(".deckmaster/objects/")


def test_idempotent_replay_returns_same_revision(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    envelope = json.loads((ENVELOPES / "compose.json").read_text())
    first = service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=envelope,
    )
    second = service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=envelope,
    )
    assert second["status"] == "already_applied"
    assert second["revision_id"] == first["revision_id"]


def test_same_operation_different_output_conflicts(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    envelope = json.loads((ENVELOPES / "compose.json").read_text())
    first = service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=envelope,
    )
    envelope["notes"] = "a different result for the same operation"
    with pytest.raises(tasks_mod.TaskConflict):
        service.accept_result(
            project,
            task_id=task["task_id"],
            operation_id=task["operation_id"],
            produced_against=task["produced_against"],
            result_payload=envelope,
        )
    document = service.Store(project).load_document()
    assert document["revision_id"] == first["revision_id"]


def test_stale_produced_against_conflicts(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    envelope = json.loads((ENVELOPES / "compose.json").read_text())
    with pytest.raises(tasks_mod.TaskConflict):
        service.accept_result(
            project,
            task_id=task["task_id"],
            operation_id=task["operation_id"],
            produced_against="0" * 63 + "1",
            result_payload=envelope,
        )
    document = service.Store(project).load_document()
    assert (
        document["revision_id"] == task["dispatch_revision"]
        or document["parent_revision_id"] == task["dispatch_revision"]
    )


def test_cancelled_task_late_result_settles_usage(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    # Allocate one allowance on the task (project transaction, T13 semantics).
    store = service.Store(project)
    document = store.load_document()
    task_obj = tasks_mod._lookup_task(document, task["task_id"], store)
    allowances = [
        {
            "allowance_id": "call-1",
            "state": "consumed",
            "execution_ref": "exec-real",
            "invocation_ref": "invocation-1",
            "evidence": [],
        }
    ]
    updated = {**task_obj, "call_allowances": allowances, "updated_at": "2026-09-16T00:00:00Z"}
    tasks_mod.validate_task_semantics(updated)
    task_ref = store.put_json_object(updated)
    bumped = tasks_mod.bump_revision(
        document,
        {"operation_id": "alloc-1", "kind": "task_update", "description": "allocate", "read_set": []},
    )
    bumped = tasks_mod._replace_task_ref(bumped, task_obj, task_ref, store)
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="alloc-1")

    service.task_cancel(project, task_id=task["task_id"], reason="user stop")

    envelope = json.loads((ENVELOPES / "compose.json").read_text())
    envelope["usage_events"] = [
        {"allowance_id": "call-1", "outcome": "unknown", "invocation_ref": "invocation-1", "evidence_file_ids": []}
    ]
    with pytest.raises(tasks_mod.TaskConflict):
        service.accept_result(
            project,
            task_id=task["task_id"],
            operation_id=task["operation_id"],
            produced_against=task["produced_against"],
            result_payload=envelope,
        )
    # Call facts survive: the settled state stays visible through the Document history.
    document = service.Store(project).load_document()
    late_task = None
    for ref in document["tasks"]:
        candidate = store.read_object_json(ref)
        if candidate["task_id"] == task["task_id"]:
            late_task = candidate
    assert late_task["status"] == "cancelled"
    assert late_task["call_allowances"][0]["state"] in ("consumed", "unknown")


def test_path_escape_rejected_in_envelope(tmp_path: Path) -> None:
    envelope = json.loads((ENVELOPES / "invalid-path-escape.json").read_text())
    with pytest.raises(tasks_mod.EnvelopeError) as excinfo:
        tasks_mod.parse_envelope(envelope)
    assert "staging" in excinfo.value.detail or ".." in str(excinfo.value.detail)


def test_unknown_type_discriminator_rejected(tmp_path: Path) -> None:
    envelope = json.loads((ENVELOPES / "invalid-type-discriminator.json").read_text())
    envelope.pop("kind", None)
    with pytest.raises(tasks_mod.EnvelopeError) as excinfo:
        tasks_mod.parse_envelope(envelope)
    assert "kind" in excinfo.value.path or "kind" in excinfo.value.detail


def test_blueprint_envelope_stages_files_and_prompt(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    # First adopt the compose result so page p09 exists.
    compose = json.loads((ENVELOPES / "compose.json").read_text())
    service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=compose,
    )
    # Continue produces a blueprint task against the new revision.
    response = service.continue_project(project)
    blueprint_task = response["pending_tasks"][0]
    assert blueprint_task["kind"] == "compose"  # continue only opens compose (T06 opens blueprint later)

    # Blueprint envelope via a dedicated task object built for this test.
    store = service.Store(project)
    document = store.load_document()
    page_ref = document["pages"][0]["page"]
    produced = sha256_bytes(canonical_json_bytes(document))
    task_obj = tasks_mod.new_task(
        task_id=uuid_hex(12),
        operation_id="blueprint-op-1",
        kind="blueprint",
        scope_pages=["p09"],
        instruction="Produce the real blueprint image and prompt.",
        inputs=[page_ref],
        dependencies=[{"kind": "content", "identity": "page:p09", "sha256": page_ref["sha256"]}],
        dispatch_revision=document["revision_id"],
        produced_against=produced,
        call_allowances=[
            {"allowance_id": "img-1", "state": "reserved", "execution_ref": None, "invocation_ref": None, "evidence": []}
        ],
    )
    task_ref = store.put_json_object(task_obj)
    bumped = tasks_mod.bump_revision(
        document,
        {"operation_id": "blueprint-dispatch-1", "kind": "task_update", "description": "open blueprint", "read_set": []},
    )
    bumped = {**bumped, "tasks": list(bumped.get("tasks") or []) + [task_ref]}
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="blueprint-dispatch-1")

    staging = _staging_dir(project, "blueprint-op-1")
    (staging / "reference.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (staging / "submitted-prompt.txt").write_text("实际提交的prompt内容", encoding="utf-8")
    envelope = json.loads((ENVELOPES / "blueprint.json").read_text())
    outcome = service.accept_result(
        project,
        task_id=task_obj["task_id"],
        operation_id="blueprint-op-1",
        produced_against=task_obj["produced_against"],
        result_payload=envelope,
    )
    assert outcome["status"] == "accepted"
    document = store.load_document()
    blueprint_slot = document["pages"][0]["blueprint"]
    assert blueprint_slot and blueprint_slot["path"].startswith(".deckmaster/objects/")
    artifact = store.read_object_json(blueprint_slot)
    assert artifact["role"] == "blueprint"
    prompt_ref = artifact["provenance"]["submitted_prompt"]
    assert store.read_object_bytes(prompt_ref) == "实际提交的prompt内容".encode("utf-8")


def test_review_envelope_keeps_not_evaluated(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    compose = json.loads((ENVELOPES / "compose.json").read_text())
    service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=compose,
    )
    store = service.Store(project)
    document = store.load_document()
    page_ref = document["pages"][0]["page"]
    review = json.loads((ENVELOPES / "review.json").read_text())["reviews"][0]
    review = {**review, "subjects": [page_ref]}
    envelope = {"kind": "review", "files": [], "reviews": [review]}
    task_obj = tasks_mod.new_task(
        task_id=uuid_hex(12),
        operation_id="review-op-1",
        kind="review",
        scope_pages=["p09"],
        instruction="Review the adopted page.",
        inputs=[page_ref],
        dependencies=[{"kind": "content", "identity": "page:p09", "sha256": page_ref["sha256"]}],
        dispatch_revision=document["revision_id"],
        produced_against=sha256_bytes(canonical_json_bytes(document)),
    )
    task_ref = store.put_json_object(task_obj)
    bumped = tasks_mod.bump_revision(
        document,
        {"operation_id": "review-dispatch-1", "kind": "task_update", "description": "open review", "read_set": []},
    )
    bumped = {**bumped, "tasks": list(bumped.get("tasks") or []) + [task_ref]}
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="review-dispatch-1")

    response = service.accept_result(
        project,
        task_id=task_obj["task_id"],
        operation_id="review-op-1",
        produced_against=task_obj["produced_against"],
        result_payload=envelope,
    )
    assert response["status"] == "accepted"
    document = store.load_document()
    review_ref = document["reviews"][-1]
    saved = store.read_object_json(review_ref)
    assert saved["status"] == "not_evaluated"


def test_call_begin_settle_flow(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    store = service.Store(project)
    document = store.load_document()
    task_obj = tasks_mod._lookup_task(document, task["task_id"], store)
    updated = {
        **task_obj,
        "call_allowances": [
            {"allowance_id": "img-1", "state": "reserved", "execution_ref": None, "invocation_ref": None, "evidence": []}
        ],
    }
    tasks_mod.validate_task_semantics(updated)
    task_ref = store.put_json_object(updated)
    bumped = tasks_mod.bump_revision(
        document,
        {"operation_id": "alloc-2", "kind": "task_update", "description": "allocate", "read_set": []},
    )
    bumped = tasks_mod._replace_task_ref(bumped, task_obj, task_ref, store)
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="alloc-2")

    first_begin = tasks_mod.call_begin(store, task_id=task["task_id"], allowance_id="img-1", execution_ref="exec-1")
    assert first_begin["status"] in ("in_flight", "started")
    # Idempotent same execution
    again = tasks_mod.call_begin(store, task_id=task["task_id"], allowance_id="img-1", execution_ref="exec-1")
    assert again["status"] == "already_started"
    # Another execution conflicts
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.call_begin(store, task_id=task["task_id"], allowance_id="img-1", execution_ref="exec-2")

    # Settle consumed with a real report file
    report = tmp_path / "report.json"
    report.write_text('{"tool": "image-gen", "observed": true}', encoding="utf-8")
    settled = tasks_mod.call_settle(
        store,
        task_id=task["task_id"],
        allowance_id="img-1",
        outcome="consumed",
        report_bytes=report.read_bytes(),
    )
    assert settled["status"] == "settled"
    document = store.load_document()
    final_task = tasks_mod._lookup_task(document, task["task_id"], store)
    allowance = final_task["call_allowances"][0]
    assert allowance["state"] == "consumed"
    assert allowance["evidence"], "settled consumption keeps the report as evidence"


def uuid_hex(length: int) -> str:
    import uuid

    return uuid.uuid4().hex[:length]
