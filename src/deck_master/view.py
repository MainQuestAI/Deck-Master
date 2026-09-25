"""Read-only project view for the rebuilt core (spec 01.2, 03.8).

``project_view`` derives presentation state directly from the current
Document and its immutable objects — no preview manifest, no parallel ready
logic (AC-U01). Zero pages and failed work are shown as they are; missing
artifact slots are explicit waits, never fake previews. CLI and Web share
this one projection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .content import visible_atoms
from .store import Store


def project_view(project_dir: Path | str, *, revision: str | None = None) -> dict[str, Any]:
    """One shared read-only projection of the current (or a historical) revision."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document(revision)
    pages = []
    for entry in document.get("pages") or []:
        page = None
        atoms = []
        if entry.get("page"):
            try:
                page = store.read_object_json(entry["page"])
                atoms = visible_atoms(page)
            except Exception as exc:  # noqa: BLE001 - broken page shows as broken
                pages.append(_broken_page_entry(entry, f"page unreadable: {exc}"))
                continue
        pages.append(
            {
                "page_id": entry.get("page_id"),
                "title": (page.get("customer_visible") or {}).get("title") if page else None,
                "visible_atoms": atoms,
                "page": page,
                "speaker_notes": (page or {}).get("speaker_notes"),
                "slots": {
                    "content": entry.get("page"),
                    "blueprint": entry.get("blueprint"),
                    "svg": entry.get("svg"),
                    "svg_preview": entry.get("svg_preview"),
                    "ppt_preview": entry.get("ppt_preview"),
                },
            }
        )
    pending_tasks = []
    for ref in document.get("tasks") or []:
        try:
            task = store.read_object_json(ref)
        except Exception as exc:  # noqa: BLE001 - broken task ref shows as unreadable
            pending_tasks.append({"task_id": None, "status": "unreadable", "detail": str(exc)})
            continue
        if task.get("status") in ("awaiting_host", "running"):
            pending_tasks.append(
                {
                    "task_id": task.get("task_id"),
                    "kind": task.get("kind"),
                    "status": task.get("status"),
                    "instruction": task.get("instruction"),
                }
            )
    reviews = []
    for ref in document.get("reviews") or []:
        try:
            review = store.read_object_json(ref)
        except Exception as exc:  # noqa: BLE001
            reviews.append({"review_id": None, "status": "unreadable", "detail": str(exc)})
            continue
        reviews.append(
            {
                "review_id": review.get("review_id"),
                "kind": review.get("kind"),
                "status": review.get("status"),
                "reviewer": (review.get("reviewer") or {}).get("type"),
                "created_at": review.get("created_at"),
                "observations": review.get("observations",[]),
                "findings": review.get("findings",[]),
                "page_ids": [e['page_id'] for e in document['pages'] if e['page'] in review.get('subjects',[])],
                "current_output": bool(document['outputs'].get('pptx') and document['outputs']['pptx'] in review.get('subjects',[])),
            }
        )
    design = document.get("design_context") or {}
    from .models import input_alignment as derive_input_alignment
    alignment = derive_input_alignment(document)
    view = {
        "format": "deck_view.v1",
        "project_id": document.get("project_id"),
        "revision_id": document.get("revision_id"),
        "requested_revision": revision,
        "page_count": len(document.get("pages") or []),
        "pages": pages,
        "pending_tasks": pending_tasks,
        "reviews": reviews,
        "design_context": {
            "canvas": design.get("canvas"),
            "language": design.get("language"),
            "default_style_id": design.get("default_style_id"),
        },
        "outputs": document.get("outputs") or {},
        "policy": document.get("policy") or {},
        "input_alignment": alignment,
        "view_status": derive_view_status(document),
        "evidence_level": "engineering",
    }
    if alignment == "needs_reconciliation":
        # Read-only banner for the workbench; editing waits for reconciliation.
        view["reconciliation"] = {
            "notice": "待按新要求更新",
            "reason": _latest_input_update_reason(store, document),
        }
    from .editing import review_status
    if document['outputs'].get('pptx'):
        view['view_status']='ready_for_export' if review_status(store,document)=='pass' else 'awaiting_review'
    if pending_tasks:
        view['view_status']='running' if any(t.get('status')=='running' for t in pending_tasks) else 'awaiting_host'
    return view


def _broken_page_entry(entry: dict, detail: str) -> dict[str, Any]:
    """A failed page stays visible with its failure reason, not a fake preview."""
    return {
        "page_id": entry.get("page_id"),
        "title": None,
        "broken": True,
        "detail": detail,
        "slots": {
            "content": entry.get("page"),
            "blueprint": entry.get("blueprint"),
            "svg": entry.get("svg"),
            "svg_preview": entry.get("svg_preview"),
            "ppt_preview": entry.get("ppt_preview"),
        },
    }


def _latest_input_update_reason(store: Store, document: dict) -> str | None:
    """Why the inputs moved: the open input_revision work order, else the
    latest committed input_update description."""
    for ref in document.get("tasks") or []:
        try:
            task = store.read_object_json(ref)
        except Exception:  # noqa: BLE001 - unreadable task refs never break the view
            continue
        if task.get("kind") == "compose" and task.get("intent") == "input_revision" \
                and task.get("status") in ("awaiting_host", "running"):
            return task.get("instruction")
    revision = document.get("parent_revision_id")
    visited = set()
    while revision and revision not in visited and len(visited) < 200:
        visited.add(revision)
        try:
            historic = store.load_document(revision)
        except StoreError:
            break
        change = historic.get("change") or {}
        if change.get("kind") == "input_update":
            return change.get("description")
        revision = historic.get("parent_revision_id")
    return None


def derive_view_status(document: dict) -> str:
    """Derived presentation status; never a bare completed claim (spec 03.8)."""
    pages = document.get("pages") or []
    if not pages:
        tasks = [t.get("kind") for t in document.get("tasks") or []]
        return "awaiting_host" if tasks else "initialized"
    all_have_content = all(entry.get("page") for entry in pages)
    if all_have_content:
        return "content_ready_for_review"
    return "partial_content"


def artifact_bytes(store: Store, ref: dict) -> tuple[bytes, str]:
    """Read one artifact's bytes for file serving; the ref must be a project object."""

    data = store.read_object_bytes(ref)
    if ref['path'].endswith('.json'):
        obj = json.loads(data)
        if obj.get('schema_version') == 'deck_artifact.v1':
            return store.read_object_bytes(obj['file']), obj['media_type']
    path = ref["path"]
    ext = path.rpartition(".")[2]
    media = {
        "svg": "image/svg+xml",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "json": "application/json",
        "txt": "text/plain",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(ext, "application/octet-stream")
    return data, media
