from __future__ import annotations

from typing import Any


def claim_for_index(claims: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if not claims:
        return {}
    return claims[(index - 1) % len(claims)]


def _find_claim_ids_for_beat(beat_id: str, claim_graph: dict[str, Any] | None) -> list[str]:
    """Reverse-lookup claim_ids from claim_graph.page_refs for a given beat_id."""
    if not claim_graph:
        return []
    page_refs = claim_graph.get("page_refs", {})
    matched: list[str] = []
    for claim_id, pages in page_refs.items():
        if isinstance(pages, list) and beat_id in pages:
            matched.append(claim_id)
    return matched


def _get_evidence_from_graph(claim_ids: list[str], claim_graph: dict[str, Any] | None) -> dict[str, Any]:
    """Extract evidence info and gaps from claim_graph for given claim_ids."""
    result: dict[str, Any] = {
        "evidence_ids": [],
        "gaps": [],
    }
    if not claim_graph or not claim_ids:
        return result

    # Build lookup maps.
    claims_by_id = {c.get("claim_id"): c for c in claim_graph.get("claims", []) if isinstance(c, dict)}
    evidence_by_id = {e.get("evidence_id"): e for e in claim_graph.get("evidence", []) if isinstance(e, dict)}
    gap_claims = {g.get("claim_id"): g for g in claim_graph.get("gaps", []) if isinstance(g, dict)}

    seen_evidence: set[str] = set()
    for cid in claim_ids:
        claim = claims_by_id.get(cid)
        if not claim:
            continue
        for eid in claim.get("supporting_evidence", []):
            if eid not in seen_evidence:
                seen_evidence.add(eid)
                ev = evidence_by_id.get(eid)
                if ev:
                    result["evidence_ids"].append({
                        "evidence_id": eid,
                        "evidence_type": ev.get("evidence_type", ""),
                        "summary": ev.get("summary", ""),
                    })
        if cid in gap_claims:
            result["gaps"].append(gap_claims[cid])

    return result


def build_page_tasks(
    narrative_plan: dict[str, Any],
    claim_map: dict[str, Any] | None = None,
    claim_graph: dict[str, Any] | None = None,
    judgments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claims = claim_map.get("claims", []) if isinstance(claim_map, dict) else []
    tasks = []
    for index, beat in enumerate(narrative_plan.get("beats", []), start=1):
        if not isinstance(beat, dict):
            continue
        claim = claim_for_index(claims, index)
        risk_flags = list(claim.get("risk_flags", [])) if isinstance(claim, dict) else []

        beat_id = beat.get("beat_id", "")

        # Find associated claim_ids from claim_graph.
        graph_claim_ids = _find_claim_ids_for_beat(beat_id, claim_graph)

        # Get evidence info from claim_graph.
        evidence_info = _get_evidence_from_graph(graph_claim_ids, claim_graph)

        # Build planning block with enhanced fields.
        planning: dict[str, Any] = {
            "page_title": beat.get("page_title", ""),
            "role": beat.get("role", ""),
            "core_claim": beat.get("core_claim") or claim.get("claim") or beat.get("content_goal", ""),
            "content_goal": beat.get("content_goal", ""),
            "evidence_need": beat.get("evidence_need", ""),
            "visual_need": beat.get("visual_need", ""),
            "density": beat.get("density", narrative_plan.get("density", "")),
            "preferred_archetype": beat.get("role", ""),
            "workspace_refs": beat.get("workspace_refs", []),
            "quality_requirements": ["页面必须有主观点", "页面必须说明证据如何支撑判断"],
            "gaps": risk_flags,
        }

        # Enhanced fields from beat (written by narrative_planner v2).
        if beat.get("decision_intent"):
            planning["decision_intent"] = beat["decision_intent"]
        if beat.get("argument_chain"):
            planning["argument_chain"] = beat["argument_chain"]
        if beat.get("evidence_policy"):
            planning["evidence_policy"] = beat["evidence_policy"]
        if beat.get("customer_specificity_level"):
            planning["customer_specificity_level"] = beat["customer_specificity_level"]

        # Associate claim_ids from claim_graph.
        if graph_claim_ids:
            planning["claim_ids"] = graph_claim_ids

        # Enrich evidence from claim_graph.
        if evidence_info["evidence_ids"]:
            planning["available_evidence"] = evidence_info["evidence_ids"]
        if evidence_info["gaps"]:
            planning["evidence_gaps"] = evidence_info["gaps"]

        task: dict[str, Any] = {
            "beat_id": beat_id,
            "order": beat.get("order", index),
            "planning": planning,
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

        # Add claim_ids at task level too for easy access.
        if graph_claim_ids:
            task["claim_ids"] = graph_claim_ids

        tasks.append(task)

    return {
        "run_id": narrative_plan.get("run_id", ""),
        "title": narrative_plan.get("title", ""),
        "tasks": tasks,
    }
