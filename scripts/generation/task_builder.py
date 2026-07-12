from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime.events import append_event
from sourcing.reader import canonicalize_sourcing_plan


TASK_DECISIONS = {"generate", "adapt"}
PLACEHOLDER_DECISIONS = {"manual", "evidence", "blocked"}
SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _source_decision(page: dict[str, Any]) -> str:
    decision = str(page.get("decision") or "").strip().lower()
    return "manual_placeholder" if decision in PLACEHOLDER_DECISIONS else decision


def _generation_task_id(page_task_id: str) -> str:
    if SAFE_TASK_ID.fullmatch(page_task_id):
        return f"generation_{page_task_id}"
    digest = hashlib.sha256(page_task_id.encode("utf-8")).hexdigest()[:16]
    return f"generation_task_{digest}"


def _task_semantics(page: dict[str, Any]) -> tuple[str, bool, str]:
    source_decision = _source_decision(page)
    is_adapt = source_decision == "adapt"
    task_type = "adapt" if is_adapt else "generate"
    expected_operation = "rewrite_existing_slide" if is_adapt else "create_new_slide"
    return task_type, is_adapt, expected_operation


def task_for_page(page: dict[str, Any], *, run_id: str = "") -> dict[str, Any]:
    selected_sources = [source for source in page.get("selected_sources", []) if isinstance(source, dict)]
    selected = selected_sources[0] if selected_sources else None
    alternatives = selected_sources[1:]
    task_type, is_adapt, expected_operation = _task_semantics(page)
    page_id = str(page.get("page_id") or "").strip()
    page_task_id = str(page.get("page_task_id") or page_id).strip()
    if not page_task_id:
        raise ValueError("sourcing page is missing page_task_id")
    page_title = page.get("page_title")
    generation_brief = page.get("generation_brief", "")
    visual_need = page.get("visual_need", "")
    evidence_need = page.get("evidence_need", [])
    source_decision = _source_decision(page)
    return {
        "schema_version": "deck_generation_task.v1",
        "run_id": run_id,
        "task_id": _generation_task_id(page_task_id),
        "page_task_id": page_task_id,
        "page_id": page_id,
        "beat_id": page_id,
        "page_title": page_title,
        "task_type": task_type,
        "source_decision": source_decision,
        "reference_slide_required": is_adapt,
        "expected_operation": expected_operation,
        "generation_brief": generation_brief,
        "selected_candidate": selected,
        "reference_slide": selected if is_adapt else None,
        "alternatives": alternatives,
        "query_trace_id": (selected or {}).get("query_trace_id", ""),
        "asset_key": (selected or {}).get("asset_key", ""),
        "claim_ids": list(page.get("claim_ids") or []),
        "visual_need": visual_need,
        "evidence_need": evidence_need,
        "workspace_refs": list(page.get("workspace_refs") or []),
        "quality_requirements": list(page.get("quality_requirements") or []),
        "expected_outputs": list(page.get("expected_outputs") or ["preview_path", "artifact_path"]),
        "customer_visible_content": {
            "title": page_title or "",
            "body_brief": generation_brief,
            "evidence_summary": evidence_need,
        },
        "speaker_notes": "",
        "internal_production_notes": {
            "layout_instruction": visual_need,
            "reference_slide_required": is_adapt,
            "reference_slide": selected if is_adapt else None,
        },
        "content_boundary": {
            "slide_text_source": "customer_visible_content only",
            "speaker_notes_source": "speaker_notes only",
            "never_render_to_slide_text": [
                "internal_production_notes",
                "layout_instruction",
                "reference_slide",
                "task metadata",
            ],
        },
        "style_constraints": "Follow the deck-level style and preserve any selected reference slide structure.",
        "status": "pending",
    }


def create_generation_tasks(sourcing_plan: dict[str, Any], run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    tasks_dir = root / "generation_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    canonical_plan = canonicalize_sourcing_plan(sourcing_plan)
    run_id = str(canonical_plan.get("run_id") or "")
    tasks = [
        task_for_page(page, run_id=run_id)
        for page in canonical_plan.get("pages", [])
        if isinstance(page, dict) and _source_decision(page) in TASK_DECISIONS
    ]
    new_task_ids = {task["task_id"] for task in tasks}
    for old_file in tasks_dir.glob("*.json"):
        if old_file.stem not in new_task_ids and old_file.name != "index":
            old_file.unlink()
    for task in tasks:
        (tasks_dir / f"{task['task_id']}.json").write_text(
            json.dumps(task, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    payload = {
        "schema_version": "deck_generation_task_index.v1",
        "run_id": run_id,
        "deck_pro_max_project": str((root / "deck_pro_max_project").resolve()),
        "tasks": tasks,
    }
    (root / "deck_pro_max_project").mkdir(parents=True, exist_ok=True)
    (tasks_dir / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_event(root, "generation.tasks.created", payload_ref="generation_tasks/index.json", data={"tasks": len(tasks)})
    return payload
