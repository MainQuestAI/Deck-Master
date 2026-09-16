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
    tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-1", execution_ref="exec-a")
    # The tool timed out: the Host may only report unknown.
    tasks_mod.call_settle(
        store, task_id=task_id, allowance_id="call-1", outcome="unknown", report_bytes=None
    )
    task = tasks_mod._lookup_task(store.load_document(), task_id, store)
    assert task["call_allowances"][0]["state"] == "unknown"
    # A second allocation succeeds on paper, but begin is refused project-wide.
    tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    with pytest.raises(tasks_mod.TaskConflict):
        tasks_mod.call_begin(store, task_id=task_id, allowance_id="call-2", execution_ref="exec-b")


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

