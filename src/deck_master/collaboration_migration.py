"""Explicit migration of a pre-collaboration project to the collaboration
writer boundary (content collaboration v1.2 MIGRATION §3, AC-C04).

describe() is read-only and returns the exact plan digest; apply() verifies
that digest, initialises the single collaboration region, retires legacy
runnable tasks to settle-only, preserves every immutable fact and raises the
minimum writer. Legacy decision strings are never converted into accepted
direct_user decisions, and missing writer metadata is never back-filled.
"""
from __future__ import annotations

from pathlib import Path

from . import collaboration, models, tasks as tasks_mod
from .models import canonical_json_bytes, require_writer, sha256_bytes
from .store import ConflictError, Store, StoreError

_TARGET_WRITER = "collaboration.v1"
_MIGRATION_ACTION = "collaboration.migration"
_RUNNABLE_STATUSES = ("awaiting_host", "running", "queued")


def migration_plan(store, document) -> dict:
    tasks = []
    for ref in document.get("tasks") or []:
        try:
            tasks.append(store.read_object_json(ref))
        except Exception:  # noqa: BLE001 - unreadable tasks are simply not counted
            continue
    runnable = [task for task in tasks if task.get("status") in _RUNNABLE_STATUSES]
    unknown_calls = sum(
        1 for task in tasks for allowance in task.get("call_allowances") or []
        if allowance.get("state") == "unknown"
    )
    pending = []
    for index, text in enumerate((document.get("task") or {}).get("existing_decisions") or []):
        pending.append({"source": "task.existing_decisions", "index": index, "text": text,
                        "disposition": "imported_unknown"})
    if (document.get("task") or {}).get("presentation_mode_source") == "default":
        pending.append({"source": "task.presentation_mode_source",
                        "disposition": "default_not_a_user_choice"})
    pages = document.get("pages") or []
    return {
        "schema_version": "collaboration_migration_plan.v1",
        "current_revision": document["revision_id"],
        "minimum_writer": (document.get("compatibility") or {}).get("minimum_writer"),
        "target_minimum_writer": _TARGET_WRITER,
        "needs_migration": document.get("collaboration") is None,
        "counts": {"pages": len(pages), "sources": len(document.get("sources") or []),
                   "reviews": len(document.get("reviews") or []), "tasks": len(tasks),
                   "runnable_tasks": len(runnable)},
        "tasks_to_supersede": sorted(task["task_id"] for task in runnable),
        "unknown_calls": unknown_calls,
        "pending_decisions": pending,
        "reusable": {
            "page_refs": [entry["page"] for entry in pages if entry.get("page")],
            "output_pptx": bool((document.get("outputs") or {}).get("pptx")),
            "candidates": len(document.get("candidates") or []),
        },
    }


def describe(project) -> dict:
    """Read-only migration projection with the exact plan digest (MIGRATION §3).
    Browsing a project or diagnosing it never writes anything."""
    store = Store(Path(project).expanduser())
    document = store.load_document()
    plan = migration_plan(store, document)
    return {
        "project_id": document["project_id"],
        "revision_id": document["revision_id"],
        "plan": plan,
        "plan_digest": sha256_bytes(canonical_json_bytes(plan)),
    }


def migration_response(plan, superseded_ids):
    return {"preserved": plan["reusable"], "superseded_tasks": sorted(superseded_ids),
            "pending_decisions": plan["pending_decisions"], "unknown_calls": plan["unknown_calls"],
            "note": "content intent is untouched; start a request with this turn's instruction "
                    "before any new production"}


def apply(project, *, base_revision: str, plan_digest: str, operation_id: str) -> dict:
    """Apply the described migration in one transaction (MIGRATION §3).

    Apply only establishes the control region with ``request=null``: a real
    user instruction is required to *create a request* (start_request), so an
    upgrade is never smuggled in as a business approval.
    """
    store = Store(Path(project).expanduser())

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        digest = collaboration.payload_digest(_MIGRATION_ACTION, {"plan_digest": plan_digest})
        # CONTRACTS §6.1: replay-before-CAS, like every other collaboration write.
        replay = collaboration.replay_or_conflict(store, document, operation_id,
                                                  _MIGRATION_ACTION, digest)
        if replay:
            return replay
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        if document.get("collaboration") is not None:
            return {"status": "already_migrated", "revision_id": document["revision_id"]}
        current_plan = migration_plan(store, document)
        if sha256_bytes(canonical_json_bytes(current_plan)) != plan_digest:
            raise ConflictError("plan_digest",
                                "project state changed since describe; run migration describe again")
        # Retire runnable legacy tasks to settle-only. Their allowance facts and
        # every immutable ref are preserved; only the status moves.
        task_refs = []
        superseded_ids = []
        for ref in document.get("tasks") or []:
            task = store.read_object_json(ref)
            if task.get("status") in _RUNNABLE_STATUSES:
                superseded = {**task, "status": "superseded",
                              "error": {"code": "migration_superseded",
                                        "message": "legacy task retired by the collaboration migration; "
                                                   "it may only settle its already-recorded calls",
                                        "next_action": "settle_calls_then_start_new_request"}}
                task_refs.append(store.put_json_object(superseded))
                superseded_ids.append(task["task_id"])
            else:
                task_refs.append(ref)
        region = {
            "schema_version": "collaboration.v1",
            "authority_policy": "traceable",
            "quality_profile": {"content_review_requirement": "independent_model_or_human",
                                "requirement_origin": "default_new_argument",
                                "override_decision_ref": None},
            "request": None,
            "decisions": [],
            "authorizations": [],
        }
        updated = {**document, "collaboration": region, "tasks": task_refs}
        require_writer(updated, _TARGET_WRITER)
        return collaboration.commit_collaboration_change(
            store, document, operation_id=operation_id, action=_MIGRATION_ACTION,
            digest=digest, description="collaboration migration apply", updated=updated,
            response=migration_response(current_plan, superseded_ids))

    return locked(store)
