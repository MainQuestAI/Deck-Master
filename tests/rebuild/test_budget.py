"""T13.min tests: allocation, unknown pause, cancel does not refund (AC-S12 min)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import deck_master.service as service
from deck_master import tasks as tasks_mod
from deck_master.models import bump_revision
from deck_master.store import Store


def _active_task(tmp_path: Path, *, call_limit: int | None = None) -> tuple[Store, str]:
    material = tmp_path / "material.txt"
    material.write_text("材料正文", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="设备运维汇报", sources=[material])
    store = Store(project)
    response = service.continue_project(project)
    task_id = response["pending_tasks"][0]["task_id"]
    if call_limit is not None:
        document = store.load_document()
        bumped = bump_revision(
            document,
            {
                "operation_id": "limit-1",
                "kind": "policy_update",
                "description": "set external call limit",
                "read_set": [],
            },
        )
        bumped["policy"] = {**bumped["policy"], "external_call_limit": call_limit}
        store.commit_change(
            base_revision=document["revision_id"], document=bumped, operation_id="limit-1"
        )
    return store, task_id


def test_allocation_reserves_in_project_transaction(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=3)
    outcome = tasks_mod.allocate_call_allowances(store, task_id=task_id, count=2)
    assert outcome["status"] == "allocated"
    assert outcome["allowance_ids"] == ["call-1", "call-2"]
    task = tasks_mod._lookup_task(store.load_document(), task_id, store)
    states = [entry["state"] for entry in task["call_allowances"]]
    assert states == ["reserved", "reserved"]


def test_allocation_respects_project_limit(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=2)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.allocate_call_allowances(store, task_id=task_id, count=2)
    # Adjusting the limit up keeps consumption facts and adds headroom.
    document = store.load_document()
    bumped = bump_revision(
        document,
        {"operation_id": "limit-2", "kind": "policy_update", "description": "raise", "read_set": []},
    )
    bumped["policy"] = {**bumped["policy"], "external_call_limit": 5}
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="limit-2")
    outcome = tasks_mod.allocate_call_allowances(store, task_id=task_id, count=3)
    assert len(outcome["allowance_ids"]) == 3


def test_unknown_settlement_pauses_new_calls(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=3)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    service.task_start(store.project_root, task_id=task_id, execution_ref="exec-a")
    tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1", execution_ref="exec-a")
    # The tool timed out: the Host may only report unknown.
    tasks_mod.call_settle(
        store, task_id=task_id, allowance_id="call-1", outcome="unknown", report_bytes=None
    )
    task = tasks_mod._lookup_task(store.load_document(), task_id, store)
    assert task["call_allowances"][0]["state"] == "unknown"
    # Unknown pauses additional reservations as well as begin.
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1", execution_ref="exec-a")


def test_cancelled_task_cannot_reacquire_calls(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=3)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    service.task_cancel(store.project_root, task_id=task_id, reason="user stop")
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1", execution_ref="exec-a")
    task = tasks_mod._lookup_task(store.load_document(), task_id, store)
    assert task["call_allowances"][0]["state"] == "reserved", (
        "cancel does not release or rewrite allowance facts"
    )


def test_settle_after_unknown_requires_report_for_consumed(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=2)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    service.task_start(store.project_root, task_id=task_id, execution_ref="exec-a")
    tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1", execution_ref="exec-a")
    with pytest.raises(tasks_mod.EnvelopeError):
        tasks_mod.call_settle(
            store, task_id=task_id, allowance_id="call-1", outcome="consumed", report_bytes=None
        )
    report = tmp_path / "real-report.json"
    report.write_text('{"tool": "image-gen", "calls": 1}', encoding="utf-8")
    settled = tasks_mod.call_settle(
        store,
        task_id=task_id,
        allowance_id="call-1",
        outcome="consumed",
        report_bytes=report.read_bytes(),
    )
    assert settled["status"] == "settled"



# ---------------------------------------------------------------------------
# T13.05/T13.06: evidence grading, idempotent/conflicting settlement,
# limit changes, and restore/local-fix call-fact preservation (AC-S12).


def _started_allowance(store, task_id, allowance_id="call-1"):
    service.task_start(store.project_root, task_id=task_id, execution_ref="exec-a")
    tasks_mod.call_begin(store, task_id=task_id, allowance_id=allowance_id, execution_ref="exec-a")


def _allowance(store, task_id, allowance_id="call-1"):
    task = tasks_mod._lookup_task(store.load_document(), task_id, store)
    return next(e for e in task["call_allowances"] if e["allowance_id"] == allowance_id)


def test_settle_grades_host_reported_vs_provider_verified(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=2)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=2)
    report = tmp_path / "host-report.json"
    report.write_text('{"tool": "image-gen", "calls": 1}', encoding="utf-8")
    _started_allowance(store, task_id, "call-1")
    # Host self-report without a tool-issued invocation identity: host_reported.
    tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1", outcome="consumed",
                          report_bytes=report.read_bytes())
    assert _allowance(store, task_id, "call-1")["evidence_level"] == "host_reported"
    # The same report plus a real invocation identity upgrades to provider_verified.
    _started_allowance(store, task_id, "call-2")
    tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-2", outcome="consumed",
                          report_bytes=report.read_bytes(), invocation_ref="inv-7788")
    second = _allowance(store, task_id, "call-2")
    assert second["evidence_level"] == "provider_verified"
    assert second["invocation_ref"] == "inv-7788"


def test_settle_is_idempotent_and_conflicting_outcome_rejected(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=2)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    report = tmp_path / "host-report.json"
    report.write_text('{"calls": 1}', encoding="utf-8")
    _started_allowance(store, task_id)
    first = tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1",
                                  outcome="consumed", report_bytes=report.read_bytes())
    assert first["status"] == "settled"
    replay = tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1",
                                   outcome="consumed", report_bytes=report.read_bytes())
    assert replay["status"] == "already_settled"
    with pytest.raises(tasks_mod.TaskConflict, match="terminal settlement"):
        tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1",
                              outcome="not_sent", report_bytes=None)


def test_duplicate_invocation_ref_rejected_across_allowances(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=3)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=2)
    report = tmp_path / "host-report.json"
    report.write_text('{"calls": 2}', encoding="utf-8")
    _started_allowance(store, task_id, "call-1")
    tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1", outcome="consumed",
                          report_bytes=report.read_bytes(), invocation_ref="inv-dup")
    _started_allowance(store, task_id, "call-2")
    with pytest.raises(tasks_mod.TaskConflict, match="invocation already registered"):
        tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-2", outcome="consumed",
                              report_bytes=report.read_bytes(), invocation_ref="inv-dup")
    # Same execution double-begin stays idempotent instead of a second call.
    again = tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-2", execution_ref="exec-a")
    assert again["status"] == "already_started"


def test_lowering_limit_keeps_consumed_facts(tmp_path: Path) -> None:
    store, task_id = _active_task(tmp_path, call_limit=3)
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    report = tmp_path / "host-report.json"
    report.write_text('{"calls": 1}', encoding="utf-8")
    _started_allowance(store, task_id)
    tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1", outcome="consumed",
                          report_bytes=report.read_bytes())
    # The user lowers the cap below the consumed count: saved, facts kept.
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "limit-down", "kind": "policy_update",
                                      "description": "lower cap", "read_set": []})
    bumped["policy"] = {**bumped["policy"], "external_call_limit": 1}
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="limit-down")
    assert _allowance(store, task_id)["state"] == "consumed"
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)


def test_restore_and_local_format_fix_do_not_reacquire_calls(tmp_path: Path) -> None:
    from deck_master.editing import restore
    store, _ = _active_task(tmp_path)
    envelope = json.loads((Path(__file__).resolve().parents[2] / "docs" / "specs" /
                           "deck-master-rebuild-v1" / "examples" / "roundtrips" /
                           "result-envelope" / "compose.json").read_text("utf-8"))
    task = tasks_mod._lookup_task(store.load_document(), _, store)
    service.accept_result(store.project_root, task_id=_, operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload=envelope)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "limit-1", "kind": "policy_update",
                                      "description": "set limit", "read_set": []})
    bumped["policy"] = {**bumped["policy"], "external_call_limit": 3}
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="limit-1")
    task_id = service.continue_project(store.project_root)["pending_tasks"][0]["task_id"]
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=2)
    report = tmp_path / "host-report.json"
    report.write_text('{"calls": 1}', encoding="utf-8")
    _started_allowance(store, task_id, "call-1")
    tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-1", outcome="consumed",
                          report_bytes=report.read_bytes(), invocation_ref="inv-kept")
    service.task_start(store.project_root, task_id=task_id, execution_ref="exec-a")
    tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-2", execution_ref="exec-a")
    tasks_mod.call_settle(store, task_id=task_id, allowance_id="call-2", outcome="unknown",
                          report_bytes=None)
    settled_revision = store.load_document()["revision_id"]

    # A local content/format edit advances content without touching calls...
    document = store.load_document()
    page_ref = document["pages"][0]["page"]
    page = store.read_object_json(page_ref)
    page["customer_visible"]["title"] = page["customer_visible"]["title"] + "(本地修订)"
    from deck_master.editing import edit_page
    edit_page(store.project_root, page=page, base_revision=document["revision_id"],
              page_hash=page_ref["sha256"], operation_id="local-format-fix")
    # ...and history restore never rolls call facts back.
    current = store.load_document()
    result = restore(store.project_root, revision_id=settled_revision,
                     base_revision=current["revision_id"], operation_id="restore-settled")
    assert result["status"] == "restored"
    final = store.load_document()
    states = {(e["allowance_id"], e["state"]) for e in
              tasks_mod._lookup_task(final, task_id, store)["call_allowances"]}
    assert ("call-1", "consumed") in states and ("call-2", "unknown") in states
    assert _allowance(Store(store.project_root), task_id, "call-1")["evidence_level"] == "provider_verified"
    # Restoring page content also restored the pre-edit title (restore works)...
    restored_page = store.read_object_json(final["pages"][0]["page"])
    assert not restored_page["customer_visible"]["title"].endswith("(本地修订)")
