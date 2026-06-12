"""Generation Handoff / Handback Contract for Deck Master v0.9.

Implements:
- prepare_generation_handoff: enhance generation tasks with handoff fields.
- validate_generation_result: validate result from build tool.
- import_generation_result: import completed/failed/partial result.
- refresh_preview_from_generation: update preview_manifest from results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event
from runtime.run_state import (
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    RunStateError,
    ensure_run_dirs,
    read_json,
    write_json,
)

RESULT_SCHEMA_VERSION = "deck_generation_result.v1"
HANDOFF_SCHEMA_VERSION = "deck_generation_task.v1"

RESULTS_DIR = "generation_results"
TASKS_DIR = "generation_tasks"

VALID_STATUSES = {"completed", "partial", "failed"}


class GenerationHandbackError(ValueError):
    """Raised when generation result is invalid or import fails."""


# --------------------------------------------------------------------------- #
# Prepare handoff
# --------------------------------------------------------------------------- #


def prepare_generation_handoff(run_dir: str | Path) -> dict[str, Any]:
    """Enhance generation tasks with handoff fields for build tools.

    Reads existing generation_tasks and adds workspace_refs, quality_requirements,
    claim_ids, evidence_refs where available.
    """
    root = ensure_run_dirs(run_dir)

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        request = read_json(request_path)
        run_id = str(request.get("run_id", ""))

    # Load page tasks for claim/evidence context.
    page_tasks_data: dict[str, Any] = {}
    if (root / PAGE_TASKS_NAME).exists():
        try:
            page_tasks_data = read_json(root / PAGE_TASKS_NAME)
        except RunStateError:
            pass

    beat_planning_map = {
        t.get("beat_id"): t.get("planning", {})
        for t in page_tasks_data.get("tasks", [])
        if isinstance(t, dict)
    }

    # Load existing generation tasks.
    tasks_dir = root / TASKS_DIR
    if not tasks_dir.exists():
        raise GenerationHandbackError(
            "No generation_tasks/ directory found. Run create-generation-tasks first."
        )

    index_path = tasks_dir / "index.json"
    if not index_path.exists():
        raise GenerationHandbackError(
            "generation_tasks/index.json not found. Run create-generation-tasks first."
        )

    index_data = read_json(index_path)
    # task_builder.py writes {"tasks": [...]} with task dicts containing task_id.
    # Fall back to "task_ids" for forward compatibility.
    raw_tasks = index_data.get("tasks", [])
    if raw_tasks and isinstance(raw_tasks[0], dict):
        task_ids = [t.get("task_id", "") for t in raw_tasks if isinstance(t, dict)]
    else:
        task_ids = index_data.get("task_ids", raw_tasks)

    # Load claim-evidence graph for claim_ids / evidence_refs.
    ceg_path = root / "claim_evidence_graph.json"
    ceg: dict[str, Any] = {}
    if ceg_path.exists():
        try:
            ceg = read_json(ceg_path)
        except RunStateError:
            pass

    # Build claim -> beat mapping.
    claim_ids_for_beat: dict[str, list[str]] = {}
    for claim in ceg.get("claims", []):
        if not isinstance(claim, dict):
            continue
        for page_ref in claim.get("page_refs", []):
            claim_ids_for_beat.setdefault(page_ref, []).append(claim.get("claim_id", ""))

    enhanced: list[str] = []
    enhanced_tasks: dict[str, dict[str, Any]] = {}
    for task_id in task_ids:
        task_path = tasks_dir / f"{task_id}.json"
        if not task_path.exists():
            continue
        try:
            task = read_json(task_path)
        except RunStateError:
            continue

        beat_id = task.get("beat_id", "")
        planning = beat_planning_map.get(beat_id, {})

        # Add handoff fields.
        task["schema_version"] = HANDOFF_SCHEMA_VERSION
        task["run_id"] = run_id
        task["claim_ids"] = claim_ids_for_beat.get(beat_id, [])
        task["evidence_refs"] = planning.get("evidence_need", [])
        task["workspace_refs"] = [
            "visual-system/spec_lock.md",
            "structure-assets/page_archetypes.md",
        ]
        task["quality_requirements"] = [
            "页面必须有主观点",
            "必须说明证据如何支撑判断",
        ]
        task["expected_outputs"] = ["preview_path", "artifact_path", "generation_notes"]

        write_json(task_path, task)
        enhanced.append(task_id)
        enhanced_tasks[task_id] = task

    # Sync enhanced task data back into index so external tools reading
    # index.json see the same fields as individual task files.
    raw_tasks = index_data.get("tasks", [])
    if raw_tasks and isinstance(raw_tasks[0], dict):
        index_data["tasks"] = [
            enhanced_tasks.get(t.get("task_id", ""), t)
            for t in raw_tasks
            if isinstance(t, dict)
        ]

    # Update index.
    index_data["schema_version"] = HANDOFF_SCHEMA_VERSION
    index_data["run_id"] = run_id
    index_data["enhanced_at"] = datetime.now(timezone.utc).isoformat()
    write_json(index_path, index_data)

    append_typed_event(
        root,
        "artifact_written",
        "generation_handoff.prepared",
        f"Generation handoff prepared for {len(enhanced)} tasks.",
        run_id=run_id,
        refs=[f"{TASKS_DIR}/index.json"],
        payload={"task_count": len(enhanced)},
    )

    return {"status": "prepared", "task_count": len(enhanced), "run_id": run_id}


# --------------------------------------------------------------------------- #
# Validate result
# --------------------------------------------------------------------------- #


def validate_generation_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate a generation result."""
    errors: list[str] = []

    if not isinstance(result, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}

    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{RESULT_SCHEMA_VERSION}', "
            f"got '{result.get('schema_version')}'."
        )

    if not result.get("run_id"):
        errors.append("run_id is required.")
    if not result.get("tool"):
        errors.append("tool is required.")
    if not result.get("task_id"):
        errors.append("task_id is required.")
    if not result.get("beat_id"):
        errors.append("beat_id is required.")

    status = result.get("status", "")
    if status not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}.")

    if status == "completed":
        if not result.get("artifact_path") and not result.get("preview_path"):
            errors.append("completed result must have artifact_path or preview_path.")

    if status == "failed":
        err_list = result.get("errors", [])
        if not err_list:
            errors.append("failed result must have errors array with at least one entry.")

    return {
        "valid": len(errors) == 0,
        "errors": errors if errors else [],
        "warnings": [],
    }


# --------------------------------------------------------------------------- #
# Import result
# --------------------------------------------------------------------------- #


def import_generation_result(
    run_dir: str | Path,
    result: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Import a generation result into the run."""
    validation = validate_generation_result(result)
    if not validation["valid"]:
        raise GenerationHandbackError(
            "Invalid generation result: " + "; ".join(validation["errors"])
        )

    root = ensure_run_dirs(run_dir)
    run_id = str(result.get("run_id", ""))
    task_id = str(result.get("task_id", ""))
    beat_id = str(result.get("beat_id", ""))
    status = str(result.get("status", ""))

    # Check locked page.
    page_tasks_path = root / PAGE_TASKS_NAME
    if page_tasks_path.exists():
        try:
            page_tasks = read_json(page_tasks_path)
        except RunStateError:
            page_tasks = {}
        for task in page_tasks.get("tasks", []):
            if isinstance(task, dict) and task.get("beat_id") == beat_id:
                if task.get("locked") and not force:
                    raise GenerationHandbackError(
                        f"Page {beat_id} is locked. Use --force to override."
                    )
                break

    # Write result.
    results_dir = root / RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    write_json(results_dir / f"{task_id}.json", result)

    # Update generation task status.
    task_path = root / TASKS_DIR / f"{task_id}.json"
    if task_path.exists():
        try:
            task = read_json(task_path)
            task["status"] = status
            if status == "completed" and result.get("artifact_path"):
                task["artifact_path"] = result["artifact_path"]
            if result.get("preview_path"):
                task["preview_path"] = result["preview_path"]
            write_json(task_path, task)
        except RunStateError:
            pass

    append_typed_event(
        root,
        "artifact_written",
        "generation_result.imported",
        f"Generation result imported: task={task_id}, beat={beat_id}, status={status}.",
        run_id=run_id,
        refs=[f"{RESULTS_DIR}/{task_id}.json", f"{TASKS_DIR}/{task_id}.json"],
        payload={
            "task_id": task_id,
            "beat_id": beat_id,
            "status": status,
            "tool": result.get("tool", ""),
        },
    )

    return {
        "status": "imported",
        "task_id": task_id,
        "beat_id": beat_id,
        "result_status": status,
        "preview_path": result.get("preview_path", ""),
        "artifact_path": result.get("artifact_path", ""),
    }


# --------------------------------------------------------------------------- #
# Refresh preview
# --------------------------------------------------------------------------- #


def refresh_preview_from_generation(run_dir: str | Path) -> dict[str, Any]:
    """Update preview_manifest.json with paths from generation results."""
    root = ensure_run_dirs(run_dir)

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        request = read_json(request_path)
        run_id = str(request.get("run_id", ""))

    # Load preview manifest.
    preview_path = root / PREVIEW_MANIFEST_NAME
    if not preview_path.exists():
        raise GenerationHandbackError(
            "preview_manifest.json not found. Run build-preview first."
        )
    preview = read_json(preview_path)

    # Load generation results.
    results_dir = root / RESULTS_DIR
    if not results_dir.exists():
        return {"status": "no_results", "run_id": run_id}

    updated: list[str] = []
    preview_pages = preview.get("pages", [])

    for result_file in sorted(results_dir.glob("*.json")):
        try:
            result = read_json(result_file)
        except RunStateError:
            continue
        if result.get("status") not in ("completed", "partial"):
            continue
        beat_id = str(result.get("beat_id", ""))
        preview_img = result.get("preview_path", "")

        for page in preview_pages:
            if isinstance(page, dict) and page.get("beat_id") == beat_id:
                if preview_img:
                    page["preview_image"] = preview_img
                    page["source_type"] = "generated"
                if not preview_img and result.get("status") == "partial":
                    page["preview_missing"] = True
                updated.append(beat_id)
                break

    write_json(preview_path, preview)

    append_typed_event(
        root,
        "artifact_written",
        "preview_refreshed_from_generation",
        f"Preview refreshed from generation results: {len(updated)} pages updated.",
        run_id=run_id,
        refs=[PREVIEW_MANIFEST_NAME],
        payload={"updated_beats": updated},
    )

    return {"status": "refreshed", "updated": updated, "run_id": run_id}
