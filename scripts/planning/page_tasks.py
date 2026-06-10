from __future__ import annotations

from typing import Any


def claim_for_index(claims: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if not claims:
        return {}
    return claims[(index - 1) % len(claims)]


def build_page_tasks(narrative_plan: dict[str, Any], claim_map: dict[str, Any] | None = None) -> dict[str, Any]:
    claims = claim_map.get("claims", []) if isinstance(claim_map, dict) else []
    tasks = []
    for index, beat in enumerate(narrative_plan.get("beats", []), start=1):
        if not isinstance(beat, dict):
            continue
        claim = claim_for_index(claims, index)
        risk_flags = list(claim.get("risk_flags", [])) if isinstance(claim, dict) else []
        tasks.append(
            {
                "beat_id": beat.get("beat_id"),
                "order": beat.get("order", index),
                "planning": {
                    "page_title": beat.get("page_title", ""),
                    "role": beat.get("role", ""),
                    "core_claim": beat.get("core_claim") or claim.get("claim") or beat.get("content_goal", ""),
                    "content_goal": beat.get("content_goal", ""),
                    "evidence_need": beat.get("evidence_need", ""),
                    "visual_need": beat.get("visual_need", ""),
                    "density": beat.get("density", narrative_plan.get("density", "")),
                    "preferred_archetype": beat.get("role", ""),
                    "workspace_refs": [],
                    "quality_requirements": ["页面必须有主观点", "页面必须说明证据如何支撑判断"],
                    "gaps": risk_flags,
                },
                "retrieval": {
                    "reuse_query": beat.get("reuse_query", ""),
                    "constraints": [],
                },
                "sourcing": {
                    "decision": None,
                    "selected_candidate": None,
                    "alternatives": [],
                    "risk_flags": [],
                    "confidence": None,
                },
                "generation": {
                    "generation_brief": beat.get("generation_brief", ""),
                    "reference_slide": None,
                    "task_path": None,
                    "status": "pending",
                },
            }
        )
    return {
        "run_id": narrative_plan.get("run_id", ""),
        "title": narrative_plan.get("title", ""),
        "tasks": tasks,
    }
