"""Review Cockpit F2 — Page Decision Workbench actions.

Implements page-level review actions that write typed events and respect
Quality Gate blocking rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preview.manifest import ManifestError, update_page_review, update_page_source_decision
from runtime.events import append_typed_event
from runtime.run_state import (
    PAGE_TASKS_NAME,
    RunStateError,
    read_json,
    write_json,
)

VALID_ACTIONS = {
    "approve",
    "reject",
    "request_evidence",
    "convert_to_generate",
    "replace_candidate",
    "move_to_appendix",
    "lock_source",
    "create_override",
    "rerun_generation",
    "add_note",
}


class WorkbenchError(ValueError):
    """Raised when a review action is invalid or blocked."""


def _safe_read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except RunStateError:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_task_index(tasks: list[dict[str, Any]], page_id: str) -> int:
    for i, t in enumerate(tasks):
        if isinstance(t, dict) and t.get("beat_id") == page_id:
            return i
    raise WorkbenchError(f"Page not found: {page_id}")


def execute_review_action(
    run_dir: str | Path,
    page_id: str,
    action: str,
    *,
    actor: str = "user",
    reason: str = "",
    note: str = "",
    finding_id: str = "",
    severity: str = "P1",
    approver: str = "",
) -> dict[str, Any]:
    """Execute a page review action.

    All actions write typed events.
    Quality Gate cannot be bypassed by review actions.
    """
    if action not in VALID_ACTIONS:
        raise WorkbenchError(
            f"Invalid action: '{action}'. Valid: {sorted(VALID_ACTIONS)}"
        )

    root = Path(run_dir).expanduser().resolve()
    page_tasks_path = root / PAGE_TASKS_NAME

    if not page_tasks_path.exists():
        raise WorkbenchError("page_tasks.json not found.")

    page_tasks = read_json(page_tasks_path)
    tasks = page_tasks.get("tasks", [])
    idx = _find_task_index(tasks, page_id)
    task = tasks[idx]

    run_id = ""
    req = _safe_read(root / "request.json")
    if req:
        run_id = str(req.get("run_id", ""))

    result: dict[str, Any] = {"status": "ok", "page_id": page_id, "action": action}

    if action == "approve":
        # Check if page has blocking quality findings.
        _check_no_blocking_findings(root, page_id)
        try:
            update_page_review(
                root,
                page_id,
                review_status="approved",
                action_intent="none",
                notes=note,
            )
        except ManifestError as exc:
            raise WorkbenchError(f"Cannot approve page: {exc}") from exc
        task["review_status"] = "approved"
        task["reviewed_at"] = _utc_now()
        task["reviewed_by"] = actor

    elif action == "reject":
        try:
            update_page_review(
                root,
                page_id,
                review_status="rejected",
                action_intent="none",
                notes=reason,
            )
        except ManifestError as exc:
            raise WorkbenchError(f"Cannot reject page: {exc}") from exc
        task["review_status"] = "rejected"
        task["reviewed_at"] = _utc_now()
        task["reviewed_by"] = actor
        task["rejection_reason"] = reason

    elif action == "request_evidence":
        try:
            update_page_review(
                root,
                page_id,
                review_status="needs_evidence",
                action_intent="request_evidence",
                notes=reason,
            )
        except ManifestError as exc:
            raise WorkbenchError(f"Cannot request evidence for page: {exc}") from exc
        task["review_status"] = "needs_evidence"
        task["action_intent"] = "request_evidence"
        task["reviewed_at"] = _utc_now()
        task["reviewed_by"] = actor
        # Create an evidence request finding.
        findings_dir = root / "evidence_requests"
        findings_dir.mkdir(parents=True, exist_ok=True)
        ev_req = {
            "finding_id": f"ev_req_{page_id}_{_utc_now()[:19].replace(':', '').replace('-', '')}",
            "page_id": page_id,
            "requested_by": actor,
            "reason": reason,
            "requested_at": _utc_now(),
            "status": "open",
        }
        write_json(findings_dir / f"ev_req_{page_id}.json", ev_req)
        result["finding_id"] = ev_req["finding_id"]

    elif action == "convert_to_generate":
        try:
            update_page_source_decision(
                root,
                page_id,
                "generate",
                review_status="needs_review",
                action_intent="generate",
                notes=reason or note,
            )
        except ManifestError as exc:
            raise WorkbenchError(f"Cannot convert page to generation: {exc}") from exc
        planning = task.get("planning", {})
        if not isinstance(planning, dict):
            planning = {}
            task["planning"] = planning
        planning["decision_intent"] = "generate"
        task["source_decision"] = "generate"
        task["action_intent"] = "generate"
        task["review_status"] = "needs_review"
        task["reviewed_at"] = _utc_now()
        task["reviewed_by"] = actor

    elif action == "replace_candidate":
        # Mark for re-sourcing; actual candidate selection done by Agent.
        task["source_decision"] = "pending_replacement"
        task["replacement_requested_at"] = _utc_now()

    elif action == "move_to_appendix":
        task["role"] = "appendix"
        task["section"] = "appendix"

    elif action == "lock_source":
        task["locked"] = True
        task["locked_at"] = _utc_now()
        task["locked_by"] = actor

    elif action == "create_override":
        if not finding_id:
            raise WorkbenchError("create_override requires finding_id.")
        if not approver:
            raise WorkbenchError("create_override requires approver.")
        # Delegate to overrides module.
        from quality.overrides import create_override
        override_result = create_override(
            root,
            finding_id=finding_id,
            severity=severity,
            reason=reason,
            approver=approver,
            scope="client_export",
            actor=actor,
        )
        result["override"] = override_result

    elif action == "rerun_generation":
        # Mark generation task for rerun.
        gen_tasks_dir = root / "generation_tasks"
        if gen_tasks_dir.exists():
            for task_file in gen_tasks_dir.glob("*.json"):
                try:
                    gen_task = read_json(task_file)
                    if gen_task.get("beat_id") == page_id:
                        gen_task["status"] = "pending_rerun"
                        gen_task["rerun_requested_at"] = _utc_now()
                        write_json(task_file, gen_task)
                        result["generation_task"] = task_file.name
                        break
                except RunStateError:
                    continue

    elif action == "add_note":
        notes = task.get("review_notes", [])
        notes.append({
            "note": note or reason,
            "author": actor,
            "timestamp": _utc_now(),
        })
        task["review_notes"] = notes

    # Save updated tasks.
    write_json(page_tasks_path, page_tasks)

    # Write typed event.
    append_typed_event(
        root,
        "decision",
        f"page_review.{action}",
        f"Page {page_id}: {action} by {actor}.",
        run_id=run_id,
        refs=[PAGE_TASKS_NAME],
        payload={"page_id": page_id, "action": action, "actor": actor, "reason": reason},
    )

    return result


def _check_no_blocking_findings(run_dir: Path, page_id: str) -> None:
    """Check that no P0 quality findings block this page."""
    quality_dir = run_dir / "quality_reports"
    if not quality_dir.exists():
        return

    for gate_file in quality_dir.glob("*_gate.json"):
        report = _safe_read(gate_file)
        if not report:
            continue
        for f in report.get("findings", []):
            if not isinstance(f, dict):
                continue
            if f.get("severity") == "P0" and f.get("page_id") == page_id:
                raise WorkbenchError(
                    f"Page {page_id} has P0 finding '{f.get('finding_id', '')}'. "
                    "Cannot approve while P0 findings are active. "
                    "Create an override or repair the finding first."
                )
