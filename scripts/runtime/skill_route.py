from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "deck_skill_route.v1"

SKILL_META: dict[str, dict[str, Any]] = {
    "deck-master": {
        "skill_stage": "orchestration",
        "label": "Deck Master",
        "backend_dependency": "",
        "compat_skills": [],
    },
    "deck-setup": {
        "skill_stage": "setup",
        "label": "Setup",
        "backend_dependency": "",
        "compat_skills": [],
    },
    "deck-upgrade": {
        "skill_stage": "upgrade",
        "label": "Upgrade",
        "backend_dependency": "",
        "compat_skills": [],
    },
    "deck-doctor": {
        "skill_stage": "diagnostics",
        "label": "Doctor",
        "backend_dependency": "",
        "compat_skills": [],
    },
    "deck-init": {
        "skill_stage": "workspace",
        "label": "Init",
        "backend_dependency": "",
        "compat_skills": ["init-workspace"],
    },
    "deck-brief": {
        "skill_stage": "briefing",
        "label": "Brief",
        "backend_dependency": "",
        "compat_skills": ["build-brief"],
    },
    "deck-planner": {
        "skill_stage": "planning",
        "label": "Planning",
        "backend_dependency": "",
        "compat_skills": ["autoplan"],
    },
    "deck-sourcing": {
        "skill_stage": "sourcing",
        "label": "Sourcing",
        "backend_dependency": "ppt-library",
        "compat_skills": ["ppt-library"],
    },
    "deck-producer": {
        "skill_stage": "production",
        "label": "Producer",
        "backend_dependency": "ppt-deck-pro-max",
        "compat_skills": ["ppt-deck-pro-max"],
    },
    "deck-builder": {
        "skill_stage": "build",
        "label": "Builder",
        "backend_dependency": "ppt-master",
        "compat_skills": ["ppt-master", "render"],
    },
    "deck-quality": {
        "skill_stage": "quality",
        "label": "Quality",
        "backend_dependency": "ppt-quality-gate",
        "compat_skills": ["ppt-quality-gate"],
    },
    "deck-review": {
        "skill_stage": "review",
        "label": "Review",
        "backend_dependency": "",
        "compat_skills": ["export", "final-readiness"],
    },
    "deck-learn": {
        "skill_stage": "learning",
        "label": "Learn",
        "backend_dependency": "",
        "compat_skills": ["build-learning-pack"],
    },
    "deck-autopilot": {
        "skill_stage": "workflow",
        "label": "Autopilot",
        "backend_dependency": "",
        "compat_skills": ["autopilot-v1"],
    },
}

STAGE_TO_SKILL = {
    "blocked_setup": "deck-setup",
    "blocked_suite": "deck-setup",
    "blocked_workspace": "deck-init",
    "needs_request": "deck-init",
    "needs_context": "deck-brief",
    "needs_brief": "deck-brief",
    "needs_claim_map": "deck-planner",
    "needs_narrative_plan": "deck-planner",
    "needs_page_tasks": "deck-planner",
    "needs_sourcing": "deck-sourcing",
    "needs_preview": "deck-sourcing",
    "needs_generation_session": "deck-producer",
    "awaiting_agent_execution": "deck-producer",
    "generation_running": "deck-producer",
    "generation_failed": "deck-producer",
    "needs_generation_import": "deck-producer",
    "needs_preview_refresh": "deck-producer",
    "needs_draft_gate": "deck-quality",
    "needs_builder_backend": "deck-builder",
    "needs_build": "deck-builder",
    "needs_render": "deck-builder",
    "needs_review": "deck-review",
    "ready_for_client_export": "deck-review",
    "ready_for_benchmark": "deck-review",
}

INPUT_TYPE_TO_SKILL = {
    "first_run_setup": "deck-setup",
    "suite_install": "deck-setup",
    "deck_workflow": "deck-master",
    "run_state": "deck-master",
    "review_cockpit": "deck-master",
    "upgrade": "deck-upgrade",
    "rollback": "deck-upgrade",
    "release_tree": "deck-upgrade",
    "setup_issue": "deck-doctor",
    "suite_issue": "deck-doctor",
    "run_issue": "deck-doctor",
    "new_workspace": "deck-init",
    "raw_materials_directory": "deck-init",
    "project_start": "deck-init",
    "raw_materials": "deck-brief",
    "deep_research_report": "deck-brief",
    "meeting_notes": "deck-brief",
    "deck_brief": "deck-planner",
    "claim_map": "deck-planner",
    "narrative_request": "deck-planner",
    "page_tasks": "deck-sourcing",
    "asset_request": "deck-sourcing",
    "historical_slide_search": "deck-sourcing",
    "generation_session": "deck-producer",
    "dispatch_package": "deck-producer",
    "approved_preview": "deck-builder",
    "build_manifest": "deck-builder",
    "render_request": "deck-builder",
    "draft_review": "deck-quality",
    "render_artifact": "deck-quality",
    "delivery_artifact": "deck-quality",
    "pptx_package": "deck-quality",
    "quality_report": "deck-review",
    "final_readiness": "deck-review",
    "review_workspace": "deck-review",
    "delivery_outcome": "deck-learn",
    "library_feedback": "deck-learn",
    "benchmark_result": "deck-learn",
    "repair_request": "deck-autopilot",
    "review_request": "deck-autopilot",
}


def _route_payload(
    *,
    skill: str,
    reason: str,
    next_command: str = "",
    source: str,
    stage: str = "",
    input_type: str = "",
) -> dict[str, Any]:
    meta = SKILL_META.get(skill, SKILL_META["deck-master"] if "deck-master" in SKILL_META else {})
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "runtime_stage": stage,
        "input_type": input_type,
        "recommended_skill": skill,
        "skill_stage": str(meta.get("skill_stage") or ""),
        "skill_label": str(meta.get("label") or skill),
        "skill_reason": reason,
        "next_skill_command": next_command,
        "backend_dependency": str(meta.get("backend_dependency") or ""),
        "compat_skills": list(meta.get("compat_skills") or []),
    }


def route_for_stage(stage: str, *, reason: str = "", next_command: str = "") -> dict[str, Any]:
    normalized_stage = str(stage or "needs_request").strip()
    skill = STAGE_TO_SKILL.get(normalized_stage, "deck-master")
    route_reason = reason or f"runtime stage is {normalized_stage}"
    return _route_payload(
        skill=skill,
        reason=route_reason,
        next_command=next_command,
        source="runtime_stage",
        stage=normalized_stage,
    )


def route_for_input_type(input_type: str, *, reason: str = "", next_command: str = "") -> dict[str, Any]:
    normalized = str(input_type or "").strip().lower().replace("-", "_")
    skill = INPUT_TYPE_TO_SKILL.get(normalized, "deck-master")
    route_reason = reason or f"input type is {normalized or 'unknown'}"
    return _route_payload(
        skill=skill,
        reason=route_reason,
        next_command=next_command,
        source="input_type",
        input_type=normalized,
    )
