"""Service use cases for the rebuilt core (spec 09.1–09.5).

create/continue/task accept are the only entrypoints CLI and Web share.
No rule Planner, no loop claim, no library/workspace prerequisite: a plain
material directory starts a project (AC-C06). Confirmed decisions are never
re-asked; repeating continue returns the same pending tasks (AC-C04).

Dispatch consistency: a Host task records ``dispatch_revision`` (the revision
it was committed in) and ``produced_against`` (the content hash of the parent
revision it was derived from). ``accept`` re-checks both inside the project
lock, so a stale submission is refused with current unchanged (exit 5).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from . import tasks as tasks_mod
from .content import normalize_design_assets
from .models import bump_revision, canonical_json_bytes, new_document, sha256_bytes, validate_document_semantics
from .sources import read_source
from .store import Store, StoreError

AUTO_VIEW = "auto_view_then_production"
CONTINUE_PRODUCTION = "continue_production"


class ServiceError(StoreError):
    """A use-case level failure with the offending field named."""


def _response(
    *,
    status: str,
    document: dict,
    requested_action: str,
    pending_tasks: list | None = None,
    next_action: str | None = None,
    result_refs: list | None = None,
    findings: list | None = None,
    evidence_level: str = "engineering",
) -> dict:
    return {
        "status": status,
        "project_id": document.get("project_id"),
        "revision_id": document.get("revision_id"),
        "requested_action": requested_action,
        "result_refs": result_refs or [],
        "pending_tasks": pending_tasks or [],
        "findings": findings or [],
        "next_action": next_action,
        "review_url": None,  # real loopback URL arrives with the workbench (T05/T14)
        "view_status": "view_arrives_with_workbench",
        "evidence_level": evidence_level,
    }


def _document_hash(document: dict) -> str:
    return sha256_bytes(canonical_json_bytes(document))


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_operation_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def create(
    project_dir: Path | str,
    *,
    brief: str,
    title: str = "",
    sources: list[Path | str] | None = None,
    design: dict | None = None,
    draft: dict | None = None,
    audience: str = "",
    scenario: str = "",
    presentation_mode: str = "live",
    page_limit: int | None = None,
    existing_decisions: list[str] | None = None,
) -> dict:
    """Create the project; register real sources; optionally import a draft."""
    project_dir = Path(project_dir).expanduser()
    store = Store(project_dir)
    store.ensure_layout()
    operation_id = _new_operation_id("create")

    source_entries = []
    for source_path in sources or []:
        extract = read_source(source_path)
        extract_ref = None
        if extract.text:
            extract_ref = store.put_blob(extract.text.encode("utf-8"), ext="txt")
        source_entries.append(
            {
                "source_id": f"src-{len(source_entries) + 1}-{Path(str(source_path)).stem}",
                "name": Path(str(source_path)).name,
                "original_uri": extract.original_uri,
                "original_sha256": extract.original_sha256,
                "format": extract.format,
                "extract": extract_ref,
                "external_use": "unspecified",
                "restriction": "",
                "locator_scheme": {
                    "text": "line",
                    "json": "pointer",
                    "pdf": "page",
                    "docx": "paragraph",
                    "pptx": "slide",
                    "image": "region",
                }.get(extract.format_kind, "none"),
            }
        )

    design = normalize_design_assets(store, design or {}, base_dir=project_dir)
    document = new_document(
        project_id=project_dir.name,
        task={
            "title": title or "Deck task",
            "brief": brief,
            "audience": audience,
            "scenario": scenario,
            "presentation_mode": presentation_mode,
            "page_limit": page_limit,
            "existing_decisions": existing_decisions or [],
        },
        design_context=design,
        sources=source_entries,
        operation_id=operation_id,
    )
    store.init_project(document, operation_id=operation_id)

    if draft:
        document = store.load_document()
        return _response(
            status="created",
            document=document,
            requested_action="create",
            pending_tasks=_pending_host_tasks(document, store),
            next_action=AUTO_VIEW,
        )
    document = store.load_document()
    task = open_compose_task(store, document, operation_id=_new_operation_id("compose"))
    document = store.load_document()
    return _response(
        status="created",
        document=document,
        requested_action="create",
        pending_tasks=[task_summary(store, document, task)],
        next_action="submit_host_results",
    )


def open_compose_task(store: Store, document: dict, *, operation_id: str) -> dict:
    """Open a compose Host task against the current dispatch revision."""
    produced_against = _document_hash(document)
    task = tasks_mod.new_task(
        task_id=uuid.uuid4().hex[:12],
        operation_id=operation_id,
        kind="compose",
        scope_pages=[],
        instruction=(
            "Read every source in Task.sources plus the method resources; derive the "
            "audience's open question and write complete visible copy as Page v2 with "
            "an explicit page order. Same source supports different framings; do not "
            "call a rule planner or fill pages from templates."
        ),
        inputs=[],
        dependencies=[
            {
                "kind": "content",
                "identity": f"document-revision:{document['revision_id']}",
                "sha256": produced_against,
            }
        ],
        dispatch_revision=document["revision_id"],
        produced_against=produced_against,
    )
    task_ref = store.put_json_object(task)
    bumped = bump_revision(
        document,
        {
            "operation_id": f"dispatch-{uuid.uuid4().hex[:12]}",
            "kind": "task_update",
            "description": "compose task opened for Host",
            "read_set": [],
        },
    )
    bumped["tasks"] = list(document.get("tasks") or []) + [task_ref]
    store.commit_change(
        base_revision=document["revision_id"],
        document=bumped,
        operation_id=bumped["change"]["operation_id"],
    )
    return task


def _pending_host_tasks(document: dict, store: Store) -> list[dict]:
    pending = []
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if task.get("status") in ("awaiting_host", "running"):
            pending.append(task_summary(store, document, task))
    return pending


def task_summary(store: Store, document: dict, task: dict) -> dict:
    """The Host work order: identity, inputs, resolved design, method entrypoints."""
    return {
        "task_id": task["task_id"],
        "operation_id": task["operation_id"],
        "kind": task["kind"],
        "status": task["status"],
        "scope_pages": task.get("scope_pages") or [],
        "instruction": task.get("instruction") or "",
        "inputs": task.get("inputs") or [],
        "dispatch_revision": task.get("dispatch_revision"),
        "produced_against": task.get("produced_against"),
        "call_allowances": task.get("call_allowances") or [],
        "sources": document.get("sources") or [],
        "resolved_design_context": document.get("design_context") or {},
        "method_resources": [
            "deck_master://skills/deck-master/references/source-reading.md",
            "deck_master://skills/deck-master/references/content-methods.md",
            "deck_master://skills/deck-master/references/content-examples.md",
        ],
    }


def continue_project(project_dir: Path | str) -> dict:
    """Run runnable local work; return the stable pending Host tasks.

    Already-confirmed decisions and tasks are reused; no duplicate tasks are
    created on repeated continue.
    """
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    pending = _pending_host_tasks(document, store)
    if not pending:
        task = open_compose_task(store, document, operation_id=_new_operation_id("compose"))
        document = store.load_document()
        pending = _pending_host_tasks(document, store)
        assert pending, "compose task must be pending right after creation"
    return _response(
        status="awaiting_host",
        document=document,
        requested_action="continue",
        pending_tasks=pending,
        next_action="submit_host_results",
    )


def accept_result(
    project_dir: Path | str,
    *,
    task_id: str,
    operation_id: str,
    produced_against: str,
    result_path: Path | str | None = None,
    result_payload: dict | None = None,
) -> dict:
    """Receive one Host result envelope; prevalidation is all-or-nothing."""
    store = Store(Path(project_dir).expanduser())
    if result_payload is not None:
        envelope_raw = result_payload
    elif result_path is not None:
        envelope_raw = json.loads(Path(result_path).expanduser().read_text("utf-8"))
    else:
        raise ServiceError("(result)", "provide --result file or inline payload")
    outcome = tasks_mod.accept_result(
        store,
        task_id=task_id,
        operation_id=operation_id,
        produced_against=produced_against,
        envelope_raw=envelope_raw,
    )
    document = store.load_document()
    if outcome["status"] == "already_applied":
        return _response(
            status="already_applied",
            document=document,
            requested_action="task accept",
        )
    return _response(
        status="accepted",
        document=document,
        requested_action="task accept",
        pending_tasks=_pending_host_tasks(document, store),
        next_action=outcome.get("next_action"),
        result_refs=outcome.get("result_refs") or [],
    )


def import_draft(
    project_dir: Path | str,
    *,
    draft_path: Path | str | None = None,
    draft_payload: dict | None = None,
) -> dict:
    """Receive a complete Page list; adopt only if the whole draft validates."""
    if draft_payload is None:
        if draft_path is None:
            raise ServiceError("(draft)", "provide --input draft file or inline payload")
        draft_payload = json.loads(Path(draft_path).expanduser().read_text("utf-8"))
    pages = draft_payload.get("pages") if isinstance(draft_payload, dict) else None
    page_order = draft_payload.get("page_order") if isinstance(draft_payload, dict) else None
    if not isinstance(pages, list) or not pages:
        raise ServiceError("(draft)/pages", "draft must carry a non-empty pages array")

    project_dir = Path(project_dir).expanduser()
    store = Store(project_dir)
    store.ensure_layout()
    if store.current_revision_id() is None:
        # Draft without create: build the Document shell from the draft first.
        document = new_document(
            project_id=project_dir.name,
            task={
                "title": draft_payload.get("title") or "Imported draft",
                "brief": draft_payload.get("brief") or "Draft import.",
            },
            operation_id=_new_operation_id("draft"),
        )
        store.init_project(document, operation_id=document["change"]["operation_id"])
    envelope = {
        "kind": "compose",
        "files": [],
        "pages": pages,
        "page_order": page_order or [page.get("page_id") for page in pages],
        "artifact_specs": draft_payload.get("artifact_specs") or [],
        "reviews": draft_payload.get("reviews") or [],
        "usage_events": [],
        "notes": draft_payload.get("notes") or "import draft",
    }
    document = store.load_document()
    task = open_compose_task(store, document, operation_id=_new_operation_id("draft"))
    outcome = tasks_mod.accept_result(
        store,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        envelope_raw=envelope,
    )
    document = store.load_document()
    return _response(
        status="accepted",
        document=document,
        requested_action="import draft",
        pending_tasks=_pending_host_tasks(document, store),
        next_action=outcome.get("next_action") or AUTO_VIEW,
        result_refs=outcome.get("result_refs") or [],
    )


def import_asset(
    project_dir: Path | str,
    *,
    asset_id: str,
    kind: str,
    file_path: Path | str,
    external_use: str = "allowed",
) -> dict:
    """Store real media as an asset Artifact and register it in design_context."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    source = Path(file_path).expanduser().resolve()
    if not source.is_file():
        raise ServiceError(f"(asset {asset_id})", f"asset file not found: {source}")
    design = dict(document.get("design_context") or {})
    normalized = normalize_design_assets(
        store,
        {
            **design,
            "assets": [
                {
                    "asset_id": asset_id,
                    "kind": kind,
                    "file": str(source),
                    "external_use": external_use,
                }
            ],
        },
        base_dir=source.parent,
    )
    assets = [entry for entry in design.get("assets") or [] if entry.get("asset_id") != asset_id]
    assets += [entry for entry in normalized.get("assets") or [] if entry.get("asset_id") == asset_id]
    allowed = list(design.get("allowed_asset_ids") or [])
    if external_use == "allowed" and asset_id not in allowed:
        allowed.append(asset_id)
    if external_use != "allowed" and asset_id in allowed:
        allowed.remove(asset_id)
    new_design = {**design, "assets": assets, "allowed_asset_ids": allowed}
    operation_id = _new_operation_id("asset")
    new_document = bump_revision(
        document,
        {
            "operation_id": operation_id,
            "kind": "design_update",
            "description": f"asset {asset_id} registered ({kind}, {external_use})",
            "read_set": [],
        },
    )
    new_document["design_context"] = new_design
    from .models import validate_document_semantics

    validate_document_semantics(new_document)
    store.commit_change(
        base_revision=document["revision_id"], document=new_document, operation_id=operation_id
    )
    document = store.load_document()
    return _response(
        status="registered",
        document=document,
        requested_action="import asset",
    )


def task_start(project_dir: Path | str, *, task_id: str, execution_ref: str) -> dict:
    """Actual claim by a named execution; a second executor conflicts."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    if task.get("status") == "running" and task.get("execution_ref") != execution_ref:
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", "another execution already claimed this task"
        )
    if task.get("status") in ("completed", "cancelled", "superseded"):
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", f"task already {task.get('status')}; cannot start"
        )
    updated_task = {
        **task,
        "status": "running",
        "execution_ref": execution_ref,
        "updated_at": _utc_now_iso(),
    }
    return _commit_task_update(store, document, task, updated_task, "task claimed")


def task_cancel(project_dir: Path | str, *, task_id: str, reason: str = "") -> dict:
    """User stop; later submissions are late results, facts stay."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    if task.get("status") in ("completed", "cancelled", "superseded"):
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", f"task already {task.get('status')}; cancel refused"
        )
    updated_task = {**task, "status": "cancelled", "updated_at": _utc_now_iso()}
    response = _commit_task_update(store, document, task, updated_task, reason or "cancelled by user")
    response["status"] = "cancelled"
    return response


def task_status(project_dir: Path | str, *, task_id: str) -> dict:
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    return _response(
        status=task.get("status") or "unknown",
        document=document,
        requested_action="task status",
        pending_tasks=[task_summary(store, document, task)],
    )


def _commit_task_update(
    store: Store, document: dict, old_task: dict, updated_task: dict, description: str
) -> dict:
    from .models import validate_task_semantics

    validate_task_semantics(updated_task)
    task_ref = store.put_json_object(updated_task)
    operation_id = _new_operation_id("task")
    bumped = bump_revision(
        document,
        {
            "operation_id": operation_id,
            "kind": "task_update",
            "description": description,
            "read_set": [],
        },
    )
    bumped = tasks_mod._replace_task_ref(bumped, old_task, task_ref, store)
    store.commit_change(
        base_revision=document["revision_id"], document=bumped, operation_id=operation_id
    )
    refreshed = store.load_document()
    return _response(
        status=updated_task.get("status") or "updated",
        document=refreshed,
        requested_action="task update",
        pending_tasks=_pending_host_tasks(refreshed, store),
    )
