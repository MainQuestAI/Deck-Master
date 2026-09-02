"""Review Cockpit F2 — Page Decision Workbench actions.

Implements page-level review actions that write typed events and respect
Quality Gate blocking rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preview.manifest import (
    ManifestError,
    find_page,
    load_manifest,
    migrate_page_to_review_status,
    update_page_review,
    update_page_source_decision,
)
from runtime.events import append_typed_event
from quality.gate_policy import current_artifact, resolve_required_gates
from runtime.run_state import (
    PAGE_TASKS_NAME,
    RunStateError,
    read_json,
    write_json,
)

VALID_ACTIONS = {
    "approve",
    "reject",
    "needs_work",
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


def _infer_source_decision(page: dict[str, Any]) -> str:
    action_intent = str(page.get("action_intent") or "").strip().lower()
    if action_intent in {"reuse", "adapt", "generate", "manual_placeholder"}:
        return action_intent
    if action_intent == "replace":
        return "pending_replacement"
    source_type = str(page.get("source_type") or "").strip().lower()
    return {
        "library_slide": "reuse",
        "generated": "generate",
        "placeholder": "manual_placeholder",
        "manual": "manual_placeholder",
    }.get(source_type, "reuse")


def _bootstrap_page_tasks(root: Path, page_tasks_path: Path) -> dict[str, Any]:
    try:
        preview = load_manifest(root)
    except ManifestError as exc:
        raise WorkbenchError("page_tasks.json not found.") from exc

    tasks: list[dict[str, Any]] = []
    for raw_page in preview.get("pages", []):
        if not isinstance(raw_page, dict):
            continue
        page = migrate_page_to_review_status(dict(raw_page))
        source_decision = str(page.get("source_decision") or _infer_source_decision(page))
        task: dict[str, Any] = {
            "beat_id": str(page.get("page_id") or ""),
            "review_status": str(page.get("review_status") or "needs_review"),
            "source_decision": source_decision,
            "planning": {
                "core_claim": str(page.get("title") or ""),
                "decision_intent": str(page.get("action_intent") or source_decision or "none"),
            },
        }
        if page.get("notes"):
            task["review_notes"] = [{
                "note": str(page.get("notes") or ""),
                "author": "system",
                "timestamp": _utc_now(),
            }]
        tasks.append(task)

    page_tasks = {
        "run_id": str(preview.get("run_id") or root.name),
        "tasks": tasks,
    }
    write_json(page_tasks_path, page_tasks)
    return page_tasks


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
        page_tasks = _bootstrap_page_tasks(root, page_tasks_path)
    else:
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

    elif action == "needs_work":
        try:
            update_page_review(
                root,
                page_id,
                review_status="needs_work",
                action_intent="needs_work",
                notes=reason or note,
            )
        except ManifestError as exc:
            raise WorkbenchError(f"Cannot mark page as needs_work: {exc}") from exc
        task["review_status"] = "needs_work"
        task["action_intent"] = "needs_work"
        task["reviewed_at"] = _utc_now()
        task["reviewed_by"] = actor
        task["work_reason"] = reason or note

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
        note_text = note or reason
        notes = task.get("review_notes", [])
        notes.append({
            "note": note_text,
            "author": actor,
            "timestamp": _utc_now(),
        })
        task["review_notes"] = notes
        try:
            preview = load_manifest(root)
            page = migrate_page_to_review_status(find_page(preview, page_id))
            update_page_review(
                root,
                page_id,
                review_status=str(page.get("review_status") or "needs_review"),
                action_intent=str(page.get("action_intent") or "none"),
                notes=note_text,
            )
        except ManifestError as exc:
            raise WorkbenchError(f"Cannot add note to page: {exc}") from exc

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


def execute_batch_review_action(
    run_dir: str | Path,
    action: str,
    *,
    page_ids: list[str] | None = None,
    actor: str = "user",
    reason: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Execute one review action across many pages without bypassing blockers."""
    if action not in {"approve", "reject", "needs_work", "request_evidence"}:
        raise WorkbenchError("Batch review supports approve, reject, needs_work, and request_evidence.")

    root = Path(run_dir).expanduser().resolve()
    page_tasks_path = root / PAGE_TASKS_NAME
    if not page_tasks_path.exists():
        page_tasks = _bootstrap_page_tasks(root, page_tasks_path)
    else:
        page_tasks = read_json(page_tasks_path)
    tasks = page_tasks.get("tasks", [])
    if not isinstance(tasks, list):
        raise WorkbenchError("page_tasks.json tasks must be a list.")

    selected = list(page_ids or [str(task.get("beat_id") or "") for task in tasks if isinstance(task, dict)])
    if not selected:
        raise WorkbenchError("Batch review requires at least one page.")

    applied: list[str] = []
    blocked: list[dict[str, str]] = []
    for page_id in selected:
        try:
            execute_review_action(
                root,
                page_id,
                action,
                actor=actor,
                reason=reason,
                note=note,
            )
        except WorkbenchError as exc:
            blocked.append({"page_id": page_id, "reason": str(exc)})
            continue
        applied.append(page_id)

    append_typed_event(
        root,
        "decision",
        f"page_review.batch_{action}",
        f"Batch review {action} by {actor}: {len(applied)} applied, {len(blocked)} blocked.",
        refs=[PAGE_TASKS_NAME],
        payload={"action": action, "actor": actor, "applied_pages": applied, "blocked_pages": blocked},
    )
    return {
        "status": "ok" if not blocked else "completed_with_warnings",
        "action": action,
        "applied_pages": applied,
        "blocked_pages": blocked,
        "applied_count": len(applied),
        "blocked_count": len(blocked),
    }


def _page_order_aliases(*payloads: dict[str, Any]) -> dict[int, set[str]]:
    aliases: dict[int, set[str]] = {}
    for payload in payloads:
        pages = payload.get("pages") if isinstance(payload, dict) else None
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, dict):
                continue
            try:
                order = int(page.get("order") or 0)
            except (TypeError, ValueError):
                continue
            page_id = str(page.get("page_id") or page.get("beat_id") or "")
            if order > 0 and page_id:
                aliases.setdefault(order, set()).add(page_id)
    return aliases


def _finding_page_aliases(finding_page_id: str, page_order_aliases: dict[int, set[str]]) -> set[str]:
    if not finding_page_id.startswith("slide_"):
        return {finding_page_id}
    try:
        slide_number = int(finding_page_id.removeprefix("slide_"))
    except ValueError:
        return set()
    return set(page_order_aliases.get(slide_number, set()))


def _check_no_blocking_findings(run_dir: Path, page_id: str) -> None:
    """Check current active quality findings for a page before approval."""
    artifact = current_artifact(run_dir)
    request = _safe_read(run_dir / "request.json") or {}
    build_manifest = _safe_read(run_dir / "build" / "build_manifest.json") or {}
    quality_dir = run_dir / "quality_reports"
    reports: list[dict[str, Any]] = []
    if quality_dir.exists():
        for gate_file in quality_dir.glob("*_gate.json"):
            report = _safe_read(gate_file)
            if report:
                reports.append({
                    **report,
                    "_gate_name": str(report.get("gate") or gate_file.stem.removesuffix("_gate")),
                    "_report_file": gate_file.name,
                })
    policy = resolve_required_gates(
        run_dir,
        artifact,
        builder_profile=str(build_manifest.get("builder_profile") or ""),
        output_profile=str(build_manifest.get("output_profile") or ""),
        run_mode=str(request.get("run_mode") or ""),
        reports=reports,
        include_non_required_blockers=True,
    )
    preview = _safe_read(run_dir / "preview_manifest.json") or {}
    page_tasks_payload = _safe_read(run_dir / PAGE_TASKS_NAME) or {}
    high_density_manifest = _safe_read(run_dir / "high_density_build" / "manifest.json") or {}
    page_order_aliases = _page_order_aliases(preview, build_manifest, high_density_manifest, page_tasks_payload)
    known_page_ids = {
        str(item.get("page_id") or "")
        for item in preview.get("pages", [])
        if isinstance(item, dict) and item.get("page_id")
    }
    known_page_ids.update(
        str(item.get("page_id") or "")
        for item in build_manifest.get("pages", [])
        if isinstance(item, dict) and item.get("page_id")
    )
    known_page_ids.update(
        str(item.get("beat_id") or "")
        for item in page_tasks_payload.get("tasks", [])
        if isinstance(item, dict) and item.get("beat_id")
    )
    known_page_ids.add(page_id)
    active = []
    for item in policy.get("current_blockers") or []:
        if not isinstance(item, dict):
            continue
        finding_page_id = str(item.get("page_id") or "")
        if finding_page_id:
            finding_page_aliases = _finding_page_aliases(finding_page_id, page_order_aliases)
            if page_id not in finding_page_aliases and finding_page_aliases.intersection(known_page_ids):
                continue
        active.append(item)
    if not active:
        return
    p0 = next((item for item in active if str(item.get("severity") or "").upper() == "P0"), active[0])
    raise WorkbenchError(
        f"Page {page_id} has active quality finding '{p0.get('finding_id') or p0.get('code') or ''}' "
        f"({str(p0.get('severity') or 'P1').upper()}). Cannot approve while it is active. "
        "Create an override or repair the finding first."
    )
