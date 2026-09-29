"""Preview and atomically confirm restoration without rolling back execution facts."""

from __future__ import annotations

import copy
import re

from . import operations
from .editing import restore_document
from .local_state import project_path
from .models import input_alignment, validate_schema
from .snapshots import load_snapshot
from .store import Store


def _plan(store, current, past):
    before = {p["page_id"]: p for p in current["pages"]}
    after = {p["page_id"]: p for p in past["pages"]}
    tasks = [store.read_object_json(r) for r in current["tasks"]]
    preview = copy.deepcopy(current)
    for key in ("pages", "sources", "design_context", "outputs"):
        preview[key] = copy.deepcopy(past[key])
    if past.get("content_basis"):
        preview["content_basis"] = copy.deepcopy(past["content_basis"])
    else:
        from .models import compute_input_digest

        preview["content_basis"] = {"input_digest": compute_input_digest(past), "input_revision_id": None, "resolved_by_task_id": None}
    return {
        "schema_version": "restore_plan.v1",
        "project_id": current["project_id"],
        "base_revision": current["revision_id"],
        "source_revision": past["revision_id"],
        "impact": {
            "changed_pages": [pid for pid in after if before.get(pid) != after[pid]],
            "removed_pages": [pid for pid in before if pid not in after],
            "page_order": [p["page_id"] for p in past["pages"]],
            "outputs_changed": current["outputs"] != past["outputs"],
            "superseded_tasks": [t["task_id"] for t in tasks if t["status"] in ("running", "awaiting_host", "blocked")],
            "input_alignment_after": input_alignment(preview),
            "preserved": ["task_facts", "policy", "user_stop", "call_facts", "task_history", "reviews", "candidate_history"],
            "image_calls": 0,
        },
    }


@operations.public
def plan(project, *, revision_id, base_revision):
    store = Store(project_path(project))
    current = load_snapshot(store)
    if current["revision_id"] != base_revision:
        raise operations.OperationError(
            "restore_basis_changed", "base_revision", "project changed; keep both snapshots and plan again", exit_code=5
        )
    past = load_snapshot(store, revision_id)
    value = _plan(store, current, past)
    validate_schema("restore_plan", value)
    ref = store.put_json_object(value)
    return {"plan_id": "restore-plan-" + ref["sha256"], "plan_ref": ref, "plan": value}


@operations.public
def commit(project, *, plan_id, base_revision, operation_id):
    operations.validate_id(operation_id, new=True)
    if not isinstance(plan_id, str) or not re.fullmatch(r"restore-plan-[a-f0-9]{64}", plan_id):
        raise operations.OperationError("invalid_restore_plan", "plan_id", "use the immutable restoration plan ID")
    store = Store(project_path(project))
    digest = plan_id.removeprefix("restore-plan-")
    plan_ref = {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}
    planned = store.read_object_json(plan_ref)
    validate_schema("restore_plan", planned)
    with store._locked():
        current = store.load_document()
        request = operations.request_digest(current, "history.restore", base_revision, {"plan_id": plan_id, "plan": planned})
        previous = operations.recover(store, operation_id, request)
        if previous:
            return previous
        if base_revision != current["revision_id"] or planned["base_revision"] != base_revision:
            raise operations.OperationError(
                "restore_basis_changed", "base_revision", "project changed; keep both snapshots and plan again", exit_code=5
            )
        past = load_snapshot(store, planned["source_revision"])
        if planned != _plan(store, current, past):
            raise operations.OperationError("restore_basis_changed", "plan_id", "restoration impact changed; plan again", exit_code=5)
        updated = restore_document(store, current, past, operation_id)
        return operations.commit_locked(
            store,
            document=updated,
            base_revision=base_revision,
            operation_id=operation_id,
            kind="history.restore",
            digest=request,
            result={
                "status": "restored",
                "revision_id": updated["revision_id"],
                "restored_from": past["revision_id"],
                "plan_ref": plan_ref,
                "impact": planned["impact"],
            },
        )
