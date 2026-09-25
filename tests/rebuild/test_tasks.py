"""T04 task tests: the five result envelopes and atomic adoption (AC-S14)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import deck_master.service as service
from deck_master import tasks as tasks_mod
from deck_master.models import bump_revision, canonical_json_bytes, sha256_bytes
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


@pytest.mark.parametrize('bad,location', [
    ({'artifact_specs': [{'role': 'svg', 'page_id': 'p09', 'file_id': 'missing'}]}, 'artifact_specs[0]/file_id'),
    ({'reviews': [{'kind': 'conversion'}]}, 'reviews[0]'),
    ({'reviews': [None]}, 'reviews[0]'),
    ({'artifact_specs': [None]}, 'artifact_specs[0]'),
])
def test_malformed_nested_envelope_is_located_and_does_not_switch_document(tmp_path, bad, location):
    project, task = _make_project(tmp_path)
    before = Store(project).load_document()
    envelope = _compose_envelope()
    envelope.update(bad)
    with pytest.raises(tasks_mod.EnvelopeError, match=location.replace('[', r'\[').replace(']', r'\]')):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                              produced_against=task['produced_against'], result_payload=envelope)
    assert Store(project).load_document()['pages'] == before['pages']


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
    # With content adopted, continue dispatches the real T06 blueprint task.
    response = service.continue_project(project)
    assert response["pending_tasks"][0]["kind"] == "blueprint"
    assert response["next_action"] == "codex_generate_blueprint"

    # Blueprint envelope via a dedicated task object built for this test.
    store = service.Store(project)
    document = store.load_document()
    page_ref = document["pages"][0]["page"]
    from deck_master.models import content_identity

    produced = content_identity(document)
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
    from deck_master.models import content_identity

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
        produced_against=content_identity(document),
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

    service.task_start(project, task_id=task["task_id"], execution_ref="exec-1")
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


# ---------------------------------------------------------------------------
# T12 AC-S09: cancellation races — cancel-first never lands the late product,
# accept-first cannot be revoked by a later cancel.


def test_cancel_wins_late_result_is_settled_not_adopted(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    service.task_cancel(project, task_id=task["task_id"], reason="user stopped the call")
    envelope = _compose_envelope()
    with pytest.raises(tasks_mod.TaskConflict, match="after cancellation"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope)
    store = Store(project)
    document = store.load_document()
    assert document["pages"] == [], "cancel-first: the late product never enters current"
    settled = store.read_object_json(document["tasks"][-1])
    assert settled["status"] == "cancelled"
    # The identical late result is replay-idempotent and still not adopted.
    replay = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                   produced_against=task["produced_against"], result_payload=envelope)
    assert replay["status"] == "already_applied"
    assert Store(project).load_document()["pages"] == []


def test_accept_wins_cancel_cannot_revoke_adopted_product(tmp_path: Path) -> None:
    project, task = _make_project(tmp_path)
    envelope = _compose_envelope()
    outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                    produced_against=task["produced_against"], result_payload=envelope)
    assert outcome["status"] == "accepted"
    store = Store(project)
    adopted = store.load_document()
    assert len(adopted["pages"]) == len(envelope["pages"])
    with pytest.raises(tasks_mod.TaskConflict, match="cancel refused"):
        service.task_cancel(project, task_id=task["task_id"], reason="too late")
    current = store.load_document()
    assert current["pages"] == adopted["pages"], "adopted product survives the refused cancel"
    assert current["revision_id"] == adopted["revision_id"]


# ---------------------------------------------------------------------------
# T13.04/05/06: multi-round repair archives (AC-S11), no-progress stop,
# executor race for the last allowance (AC-S12).


def _adopt_compose(tmp_path: Path):
    project, task = _make_project(tmp_path)
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload=_compose_envelope())
    return project, Store(project)


def test_repair_rounds_archive_distinct_ids_all_recoverable(tmp_path: Path) -> None:
    # AC-S11: four repair rounds keep four independent page objects; no round
    # overwrites attempt N, and every round's original stays readable.
    project, store = _adopt_compose(tmp_path)
    refs = []
    for round_index in range(4):
        document = store.load_document()
        page = store.read_object_json(document["pages"][0]["page"])
        page["customer_visible"]["body_blocks"][0]["heading"] = f"第{round_index + 1}轮返修正文"
        task = service.open_host_task(store, kind="repair", page_ids=["p09"],
                                      instruction=f"repair round {round_index + 1}")
        outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                        produced_against=task["produced_against"],
                                        result_payload={"kind": "repair", "files": [], "pages": [page]})
        assert outcome["status"] == "accepted"
        refs.append(store.load_document()["pages"][0]["page"])
    assert len({ref["sha256"] for ref in refs}) == 4, "no attempt overwrites a previous one"
    for round_index, ref in enumerate(refs):
        page = store.read_object_json(ref)
        assert page["customer_visible"]["body_blocks"][0]["heading"] == f"第{round_index + 1}轮返修正文"
    # No repair round consumed an external image call.
    document = store.load_document()
    assert all(not store.read_object_json(t).get("call_allowances") for t in document["tasks"])


@pytest.mark.render
def test_no_progress_repair_stops_instead_of_looping(tmp_path: Path) -> None:
    # Same failing readback + unchanged content: the second repair dispatch is
    # refused with an explicit no-progress explanation (stopping != passing).
    from deck_master.pipeline import produce
    project = tmp_path / "proj"
    page = json.loads((ENVELOPES / "compose.json").read_text())["pages"][0]
    service.create(project, brief="无进展返修", draft={"pages": [page]})
    store = Store(project)

    def drive(envelope, accept_kind, staged_name=None, staged_bytes=None):
        response = service.continue_project(project)
        task = response["pending_tasks"][0]
        assert task["kind"] == accept_kind, (accept_kind, task["kind"])
        if staged_name:
            _stage(project, task["operation_id"], staged_name, staged_bytes)
        outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                        produced_against=task["produced_against"], result_payload=envelope)
        assert outcome["status"] == "accepted"
        return task

    import io as _io
    from PIL import Image
    png = _io.BytesIO()
    Image.new("RGB", (16, 9), (250, 250, 250)).save(png, format="PNG")
    document = store.load_document()
    drive(_png_blueprint_envelope(document["pages"][0]["page"]), "blueprint",
          "reference.png", png.getvalue())
    # SVG deliberately misses the page's visible atoms -> readback fail.
    bad_svg = (b'<svg viewBox="0 0 100 75" data-blueprint-sha256="' +
               store.read_object_json(store.load_document()["pages"][0]["blueprint"])["file"]["sha256"].encode() +
               b'"><rect width="10" height="10"/></svg>')
    drive(_svg_envelope("p09"), "reconstruct", "page.svg", bad_svg)
    report = produce(project)
    assert report["status"] == "fail" and report["findings"]

    # Round 1: a repair that changes nothing (same page bytes back).
    document = store.load_document()
    repair_task = service.continue_project(project)["pending_tasks"][0]
    assert repair_task["kind"] == "repair"
    assert "findings-sig:" in repair_task["instruction"]
    unchanged = store.read_object_json(document["pages"][0]["page"])
    _stage(project, repair_task["operation_id"], "page.svg", bad_svg)
    service.accept_result(project, task_id=repair_task["task_id"], operation_id=repair_task["operation_id"],
                          produced_against=repair_task["produced_against"],
                          result_payload={"kind": "repair",
                                          "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
                                          "pages": [unchanged],
                                          "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p09",
                                                              "provenance": {"source_type": "unknown",
                                                                             "tool": "host-reconstruct",
                                                                             "invocation_ref": None}}]})
    again = produce(project)
    assert again["status"] == "fail"

    # Round 2 dispatch: same findings + same content -> stop with explanation.
    response = service.continue_project(project)
    assert response["next_action"] == "repair_no_progress"
    assert response["status"] == "needs_input"
    assert response["pending_tasks"] == []
    assert response["findings"], "the real failing findings stay visible; stopping is not a pass"

    # A repair candidate that really changes content is allowed a new round.
    document = store.load_document()
    from copy import deepcopy
    changed = deepcopy(store.read_object_json(document["pages"][0]["page"]))
    changed["customer_visible"]["title"] = changed["customer_visible"]["title"] + "(改法)"
    from deck_master.editing import edit_page
    edit_page(store.project_root, page=changed, base_revision=document["revision_id"],
              page_hash=document["pages"][0]["page"]["sha256"], operation_id="real-progress")
    after_change = service.continue_project(project)
    assert after_change["next_action"] == "codex_generate_blueprint" or \
        after_change["next_action"] in ("codex_reconstruct_svg", "repair_readback"), \
        after_change["next_action"]


def _png_blueprint_envelope(page_ref):
    return {
        "kind": "blueprint",
        "files": [{"file_id": "b", "path": "reference.png", "media_type": "image/png"}],
        "artifact_specs": [{"file_id": "b", "role": "blueprint", "page_id": "p09",
                            "derived_from": [page_ref],
                            "provenance": {"source_type": "unknown", "tool": "host-imagegen",
                                           "invocation_ref": None, "generated_from_page": page_ref}}],
    }


def _svg_envelope(page_id):
    return {
        "kind": "reconstruct",
        "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
        "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": page_id,
                            "provenance": {"source_type": "unknown", "tool": "host-reconstruct",
                                           "invocation_ref": None}}],
    }


def _stage(project: Path, operation_id: str, name: str, data: bytes) -> None:
    staging = project / ".deckmaster" / "staging" / operation_id
    staging.mkdir(parents=True, exist_ok=True)
    (staging / name).write_bytes(data)


def test_two_executions_race_for_the_last_allowance(tmp_path: Path) -> None:
    # AC-S12: with one slot left, only one execution claims the task and
    # begins the call; the other execution is refused at both layers.
    project, _ = _make_project(tmp_path)
    store = Store(project)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "limit-1", "kind": "policy_update",
                                      "description": "one call left", "read_set": []})
    bumped["policy"] = {**bumped["policy"], "external_call_limit": 1}
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="limit-1")
    task_id = service.continue_project(store.project_root)["pending_tasks"][0]["task_id"]
    service.task_start(store.project_root, task_id=task_id, execution_ref="exec-a")
    with pytest.raises(tasks_mod.TaskConflict, match="another execution"):
        service.task_start(store.project_root, task_id=task_id, execution_ref="exec-b")
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    assert tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1",
                                execution_ref="exec-a")["status"] == "started"
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1", execution_ref="exec-b")


def test_operation_journal_json_keeps_status() -> None:
    journal = tasks_mod.OperationJournal(
        operation_id="op-1", task_id="task-1", kind="compose",
        produced_against="abc", result_digest="def", revision_id="rev-1",
        status="late_result_settled", usage_events=[{"allowance_id": "call-1", "outcome": "unknown"}],
    )
    payload = journal.to_json()
    assert payload["status"] == "late_result_settled"
    assert payload["usage_events"][0]["outcome"] == "unknown"


# ---------------------------------------------------------------------------
# PR 轮 B: envelope/task binding, artifact scope, blueprint lineage,
# settle-first call facts, and receipt-based evidence grading.


def _adopted_project(tmp_path):
    """compose adopted so pages exist; returns (project, store, compose_task)."""
    project, _ = _make_project(tmp_path)
    store = Store(project)
    task = service.continue_project(project)["pending_tasks"][0]
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload=_compose_envelope())
    return project, store, task


def test_accept_rejects_foreign_operation_id(tmp_path):
    project, store, compose_task = _adopted_project(tmp_path)
    pending = service.continue_project(project)["pending_tasks"][0]
    with pytest.raises(tasks_mod.TaskConflict, match="operation_id"):
        service.accept_result(project, task_id=pending["task_id"], operation_id="different-op",
                              produced_against=pending["produced_against"],
                              result_payload={"kind": "blueprint", "files": [], "artifact_specs": []})


def test_completed_task_refuses_new_submission(tmp_path):
    project, store, task = _adopted_project(tmp_path)
    replay = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                   produced_against=task["produced_against"], result_payload=_compose_envelope())
    assert replay["status"] == "already_applied"
    altered = _compose_envelope()
    altered["notes"] = "different result for the same completed task"
    with pytest.raises(tasks_mod.TaskConflict, match="different result"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=altered)


def test_artifact_specs_are_scoped_to_task_pages(tmp_path):
    project, store, _ = _adopted_project(tmp_path)
    task = service.open_host_task(store, kind="reconstruct", page_ids=["p09"], instruction="scope check")
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "page.svg").write_text("<svg/>")
    envelope = {"kind": "reconstruct",
                "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
                "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p10",
                                    "provenance": {"source_type": "unknown", "tool": "h",
                                                   "invocation_ref": None}}]}
    with pytest.raises(tasks_mod.EnvelopeError, match="outside the authorized scope"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope)


def png_bytes():
    from PIL import Image
    import io
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_task_kind_cannot_deliver_foreign_roles(tmp_path):
    project, store, _ = _adopted_project(tmp_path)
    task = service.open_host_task(store, kind="reconstruct", page_ids=["p09"], instruction="role check")
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "ref.png").write_bytes(png_bytes())
    envelope = {"kind": "reconstruct",
                "files": [{"file_id": "b", "path": "ref.png", "media_type": "image/png"}],
                "artifact_specs": [{"file_id": "b", "role": "blueprint", "page_id": "p09",
                                    "provenance": {"source_type": "unknown", "tool": "h",
                                                   "invocation_ref": None}}]}
    with pytest.raises(tasks_mod.EnvelopeError, match="may not deliver role"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope)


def test_blueprint_reference_regions_are_preserved(tmp_path):
    from PIL import Image
    project, store, _ = _adopted_project(tmp_path)
    page_ref = store.load_document()["pages"][0]["page"]
    png = tmp_path / "ref.png"
    Image.new("RGB", (8, 6), (240, 240, 240)).save(png)
    regions = [{"region_id": "main", "description": "全页", "bbox_normalized": [0.0, 0.0, 1.0, 1.0],
                "importance": "essential"}]
    envelope = {"kind": "blueprint",
                "files": [{"file_id": "b", "path": "ref.png", "media_type": "image/png"}],
                "artifact_specs": [{"file_id": "b", "role": "blueprint", "page_id": "p09",
                                    "derived_from": [page_ref],
                                    "reference_regions": regions,
                                    "provenance": {"source_type": "unknown", "tool": "h",
                                                   "invocation_ref": None,
                                                   "generated_from_page": page_ref}}]}
    task = service.continue_project(project)["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "ref.png").write_bytes(png.read_bytes())
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload=envelope)
    document = store.load_document()
    blueprint = store.read_object_json(document["pages"][0]["blueprint"])
    assert blueprint["reference_regions"] == regions


def test_blueprint_lineage_rejects_preview_backfeed(tmp_path):
    from PIL import Image
    project, store, _ = _adopted_project(tmp_path)
    page_ref = store.load_document()["pages"][0]["page"]
    png = tmp_path / "ref.png"
    Image.new("RGB", (8, 6), (240, 240, 240)).save(png)
    preview = store.put_json_object({
        "schema_version": "deck_artifact.v1", "artifact_id": "preview-1", "page_id": "p09",
        "role": "svg_preview",
        "file": store.put_blob(png.read_bytes(), ext="png"),
        "media_type": "image/png", "created_at": "2026-09-23T00:00:00Z",
        "dependencies": [], "derived_from": [], "provenance": {"source_type": "tool_generated"},
        "limitations": []})
    envelope = {"kind": "blueprint",
                "files": [{"file_id": "b", "path": "ref.png", "media_type": "image/png"}],
                "artifact_specs": [{"file_id": "b", "role": "blueprint", "page_id": "p09",
                                    "derived_from": [preview],
                                    "provenance": {"source_type": "unknown", "tool": "h",
                                                   "invocation_ref": None}}]}
    task = service.continue_project(project)["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "ref.png").write_bytes(png.read_bytes())
    with pytest.raises(tasks_mod.EnvelopeError, match="must not derive"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope)


@pytest.mark.render
def test_svg_only_fix_is_progress_not_no_progress(tmp_path):
    """Round-B 附加-1: a repair round that only changes the SVG (page text
    untouched) is real progress — the no-progress guard must not stop it."""
    import io
    from PIL import Image
    from deck_master.pipeline import produce
    project = tmp_path / "proj"
    page = json.loads((ENVELOPES / "compose.json").read_text())["pages"][0]
    service.create(project, brief="svg 进展", draft={"pages": [page]})
    store = Store(project)

    def drive(envelope, kind, name=None, data=None):
        task = service.continue_project(project)["pending_tasks"][0]
        assert task["kind"] == kind, (kind, task["kind"])
        if name:
            staging = project / ".deckmaster" / "staging" / task["operation_id"]
            staging.mkdir(parents=True, exist_ok=True)
            (staging / name).write_bytes(data)
        assert service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                     produced_against=task["produced_against"],
                                     result_payload=envelope)["status"] == "accepted"
        return task

    png = io.BytesIO()
    Image.new("RGB", (16, 9), (250, 250, 250)).save(png, format="PNG")
    document = store.load_document()
    drive(_png_blueprint_envelope(document["pages"][0]["page"]), "blueprint",
          "reference.png", png.getvalue())
    blueprint_sha = store.read_object_json(store.load_document()["pages"][0]["blueprint"])["file"]["sha256"]
    bad_svg = (b'<svg viewBox="0 0 100 75" data-blueprint-sha256="' + blueprint_sha.encode()
               + b'"><rect width="10" height="10"/></svg>')
    drive(_svg_envelope("p09"), "reconstruct", "page.svg", bad_svg)
    assert produce(project)["status"] == "fail"
    repair_task = service.continue_project(project)["pending_tasks"][0]
    unchanged_page = store.read_object_json(store.load_document()["pages"][0]["page"])
    # The host fixes ONLY the SVG geometry; the page copy is byte-identical.
    changed_svg = (b'<svg viewBox="0 0 100 75" data-blueprint-sha256="' + blueprint_sha.encode()
                   + b'"><rect width="20" height="20"/></svg>')
    _stage(project, repair_task["operation_id"], "page.svg", changed_svg)
    service.accept_result(project, task_id=repair_task["task_id"], operation_id=repair_task["operation_id"],
                          produced_against=repair_task["produced_against"],
                          result_payload={"kind": "repair",
                                          "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
                                          "pages": [unchanged_page],
                                          "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p09",
                                                              "provenance": {"source_type": "unknown", "tool": "h",
                                                                             "invocation_ref": None}}]})
    assert produce(project)["status"] == "fail"
    # Same findings, but the SVG bytes genuinely moved: a new round must be
    # dispatched instead of repair_no_progress.
    response = service.continue_project(project)
    assert response["next_action"] == "repair_readback"
    assert response["pending_tasks"][0]["kind"] == "repair"


def test_settle_facts_survive_content_refusal(tmp_path):
    """Round-B 附加-3: valid usage events settle even when the envelope
    content is refused — call facts are never rolled back by a content error."""
    project, store, _ = _adopted_project(tmp_path)
    task = service.open_host_task(store, kind="repair", page_ids=["p09"], instruction="settle then refuse")
    service.task_start(project, task_id=task["task_id"], execution_ref="round-b-exec")
    tasks_mod.allocate_call_allowances(store, task_id=task["task_id"], count=1)
    tasks_mod.call_begin(store, task_id=task["task_id"], allowance_id="call-1", execution_ref="round-b-exec")
    report = tmp_path / "tool-report.json"
    report.write_text(json.dumps({"tool": "image-gen", "calls": 1}))
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "page.svg").write_text("<svg/>")
    envelope = {
        "kind": "repair",
        "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"},
                  {"file_id": "report", "path": "report", "media_type": "application/json"}],
        "pages": [{**json.loads((ENVELOPES / "minimal-page.json").read_text()), "page_id": "p99"}],
        "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p09",
                            "provenance": {"source_type": "unknown", "tool": "h", "invocation_ref": None}}],
        "usage_events": [{"allowance_id": "call-1", "outcome": "consumed",
                          "invocation_ref": "inv-content-fail",
                          "evidence_file_ids": ["report"]}],
        "notes": "settled before refusal",
    }
    with pytest.raises(Exception):
        # The page belongs to no current page entry → content prevalidation
        # refuses AFTER the usage facts already settled.
        (staging / "report").write_text(report.read_text())
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope)
    settled = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                   if store.read_object_json(ref)["task_id"] == task["task_id"])
    allowance = settled["call_allowances"][0]
    assert allowance["state"] == "consumed", "call facts survive the content refusal"
    assert allowance["invocation_ref"] == "inv-content-fail"


@pytest.mark.parametrize("event, field", [
    ({"allowance_id": {"x": 1}, "outcome": "consumed"}, "allowance_id"),
    ({"allowance_id": "a", "outcome": "consumed", "evidence_file_ids": 1}, "evidence_file_ids"),
    ({"allowance_id": "a", "outcome": ["consumed"]}, "outcome"),
    ({"allowance_id": "a", "outcome": "consumed", "invocation_ref": 7}, "invocation_ref"),
])
def test_malformed_usage_event_fields_are_envelope_errors(event, field) -> None:
    envelope = {"kind": "compose", "files": [], "usage_events": [event]}
    with pytest.raises(tasks_mod.EnvelopeError, match=f"usage_events\\[0\\]/{field}"):
        tasks_mod.parse_envelope(envelope)


def _final_review_setup(tmp_path: Path):
    from deck_master.models import content_identity
    from deck_master.pipeline import artifact as adopt_artifact

    project, task = _make_project(tmp_path)
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload=_compose_envelope())
    store = service.Store(project)
    document = store.load_document()
    deck = store.staging_dir / "deck.pptx"
    deck.parent.mkdir(parents=True, exist_ok=True)
    deck.write_bytes(b"synthetic deck")
    bumped = tasks_mod.bump_revision(document, {"operation_id": "attach-deck", "kind": "task_update",
                                                "description": "deck", "read_set": []})
    bumped["outputs"]["pptx"] = adopt_artifact(store, deck, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-deck")
    document = store.load_document()
    page_ref = document["pages"][0]["page"]
    task_obj = tasks_mod.new_task(
        task_id=uuid_hex(12), operation_id="final-op", kind="review", scope_pages=["p09"],
        instruction="final", inputs=[page_ref],
        dependencies=[{"kind": "content", "identity": "page:p09", "sha256": page_ref["sha256"]}],
        dispatch_revision=document["revision_id"], produced_against=content_identity(document))
    bumped = tasks_mod.bump_revision(document, {"operation_id": "final-dispatch", "kind": "task_update",
                                                "description": "open final", "read_set": []})
    bumped["tasks"] = list(bumped.get("tasks") or []) + [store.put_json_object(task_obj)]
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="final-dispatch")
    review = json.loads((ENVELOPES / "review.json").read_text())["reviews"][0]
    finding = {"finding_id": "f1", "kind": "conversion", "impact": "must_fix", "page_id": "p09",
               "element_refs": [], "message": "缺字", "expected": "有", "actual": "无",
               "evidence": [], "resolution": "open"}
    review = {**review, "status": "fail", "findings": [finding],
              "subjects": [document["outputs"]["pptx"], page_ref]}

    def submit(item):
        return service.accept_result(project, task_id=task_obj["task_id"], operation_id="final-op",
                                     produced_against=task_obj["produced_against"],
                                     result_payload={"kind": "review", "files": [], "reviews": [item]})
    return review, page_ref, submit


def test_final_review_must_cite_current_deck_and_finding_page(tmp_path: Path) -> None:
    review, page_ref, submit = _final_review_setup(tmp_path)
    with pytest.raises(tasks_mod.EnvelopeError, match="current PPTX"):
        submit({**review, "subjects": [page_ref]})
    with pytest.raises(tasks_mod.EnvelopeError, match="task scope"):
        submit({**review, "findings": [{**review["findings"][0], "page_id": None}]})
    deck_only = [s for s in review["subjects"] if s != page_ref]
    with pytest.raises(tasks_mod.EnvelopeError, match="current Page"):
        submit({**review, "subjects": deck_only})
    assert submit(review)["status"] == "accepted"
