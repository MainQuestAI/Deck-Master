from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    REQUEST_NAME,
    SOURCING_PLAN_NAME,
    read_json,
)
from runtime.run_state_resolver import resolve_run_state
from runtime.skill_route import route_for_stage

SCHEMA_VERSION = "deck_next_step.v1"

STAGE_STATUS_MAP = {
    "needs_request": "needs_request",
    "needs_context": "needs_context",
    "needs_brief": "needs_brief",
    "needs_claim_map": "needs_claim_map",
    "needs_narrative_plan": "needs_narrative_plan",
    "needs_page_tasks": "needs_page_tasks",
    "needs_sourcing": "needs_sourcing",
    "needs_preview": "needs_preview",
    "needs_generation_session": "needs_generation_session",
    "awaiting_agent_execution": "needs_generation_execution",
    "generation_running": "needs_generation_session",
    "generation_failed": "needs_generation_session",
    "needs_generation_import": "needs_generation_session",
    "needs_preview_refresh": "needs_preview",
    "needs_draft_gate": "needs_draft_gate",
    "needs_builder_backend": "needs_builder_backend",
    "needs_build": "needs_build",
    "needs_render": "needs_render",
    "needs_review": "needs_page_review",
    "ready_for_client_export": "ready_to_export",
    "ready_for_benchmark": "ready_to_export",
    "blocked_workspace": "needs_workspace",
}

MISSING_BY_STAGE = {
    "needs_request": [REQUEST_NAME],
    "needs_context": [CONTEXT_MANIFEST_NAME],
    "needs_brief": [DECK_BRIEF_NAME],
    "needs_claim_map": [CLAIM_MAP_NAME],
    "needs_narrative_plan": [NARRATIVE_PLAN_NAME],
    "needs_page_tasks": [PAGE_TASKS_NAME],
    "needs_sourcing": [SOURCING_PLAN_NAME],
    "needs_preview": [PREVIEW_MANIFEST_NAME],
    "needs_generation_session": ["generation_session.json"],
    "awaiting_agent_execution": ["generation_dispatch/dispatch_package.json"],
    "generation_running": ["generation_session.json"],
    "generation_failed": ["generation_session.json"],
    "needs_generation_import": ["generation_session.json"],
    "needs_preview_refresh": [PREVIEW_MANIFEST_NAME],
    "needs_builder_backend": ["ppt-master production backend"],
    "needs_build": ["build/build_manifest.json"],
    "needs_render": ["render_results/render_result.json"],
}


def _legacy_status(stage: str, reason: str) -> str:
    if stage != "needs_draft_gate":
        return STAGE_STATUS_MAP.get(stage, "needs_request")
    if reason == "missing draft gate":
        return "needs_draft_gate"
    return "needs_quality_review"


def _counts_from_preview(run_dir: Path) -> tuple[int, int]:
    preview = run_dir / PREVIEW_MANIFEST_NAME
    if not preview.exists():
        return 0, 0
    try:
        payload = read_json(preview)
        pages = payload.get("pages")
    except Exception:
        return 0, 0

    if not isinstance(pages, list):
        return 0, 0

    approved = 0
    pending = 0
    for page in pages:
        if not isinstance(page, dict):
            continue
        decision = str(page.get("decision") or "").strip()
        if decision == "approved":
            approved += 1
        elif decision:
            pending += 1
    return approved, pending


def resolve_next_step(
    run_dir: str | Path,
    *,
    cli_workspace: str | None = None,
    run_mode: str | None = None,
    dev_allow_unsetup: bool = False,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    state = resolve_run_state(
        root,
        cli_workspace=cli_workspace,
        run_mode=run_mode,
        dev_allow_unsetup=dev_allow_unsetup,
    )
    stage = state.get("stage", "needs_request")
    reason = str((state.get("blocked_actions") or [{}])[0].get("reason", "")) if state.get("blocked_actions") else ""
    status = _legacy_status(stage, reason)

    run_id = str(state.get("run_id") or root.name)
    request = root / REQUEST_NAME
    if request.exists():
        try:
            payload = json.loads(request.read_text(encoding="utf-8"))
            run_id = str(payload.get("run_id") or run_id)
        except Exception:
            pass

    missing_artifacts = MISSING_BY_STAGE.get(stage, [])
    blocking_issues: list[str] = [entry.get("reason", "") for entry in state.get("blocked_actions", []) if entry.get("reason")]
    route = route_for_stage(
        str(stage),
        reason=blocking_issues[0] if blocking_issues else "",
        next_command=str(state.get("next_command") or ""),
    )

    approved_pages, pending_pages = _counts_from_preview(root)

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": status,
        "next_command": state.get("next_command", ""),
        "runtime_stage": stage,
        "missing_artifacts": missing_artifacts,
        "blocking_issues": blocking_issues,
        "run_mode": state.get("run_mode", ""),
        "recommended_skill": route["recommended_skill"],
        "skill_stage": route["skill_stage"],
        "skill_reason": route["skill_reason"],
        "next_skill_command": route["next_skill_command"],
        "skill_route": route,
    }

    if approved_pages:
        result["approved_pages"] = approved_pages
    if pending_pages:
        result["pending_pages"] = pending_pages

    if status in {"needs_draft_gate", "needs_quality_review", "needs_review", "needs_page_review"}:
        return result

    return result
