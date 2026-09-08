from __future__ import annotations

import re
import copy
from pathlib import Path
from typing import Any


def split_sentences(text: str, limit: int = 5) -> list[str]:
    parts = [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]
    return parts[:limit]


def infer_core_points(request: dict[str, Any], context_manifest: dict[str, Any], conversation: dict[str, Any]) -> list[str]:
    topics = request.get("must_cover_topics") if isinstance(request.get("must_cover_topics"), list) else []
    points = [str(topic) for topic in topics if str(topic).strip()]
    summary = str(context_manifest.get("summary") or request.get("business_goal") or "")
    for sentence in split_sentences(summary):
        if sentence not in points:
            points.append(sentence)
    if not points:
        points.append(str(conversation.get("locked_decisions", {}).get("business_goal") or "明确客户问题并给出解决方案"))
    return points[:8]


AGENT_EXTRACT_REQUIRED_FIELDS = (
    "goal_decision",
    "audience",
    "current_state",
    "key_problems",
    "constraints",
    "non_goals",
    "acceptance",
)


def _agent_extract_complete(agent_extract: dict[str, Any]) -> bool:
    return all(
        str(agent_extract.get(field) or "").strip() or isinstance(agent_extract.get(field), list)
        for field in AGENT_EXTRACT_REQUIRED_FIELDS
    )


def _compile_deck_brief_content(
    request: dict[str, Any],
    context_manifest: dict[str, Any],
    conversation: dict[str, Any],
    agent_extract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the working brief.

    Production runs consume the Agent's structured extraction
    (``agent_extract``); rule-based sentence slicing is the fixture /
    migration fallback and is labelled as such via ``brief_mode``.
    SC-1 B3/S-01: the brief is never a rewrite of the material summary
    passed off as the customer core problem.
    """

    locked = conversation.get("locked_decisions", {}) if isinstance(conversation.get("locked_decisions"), dict) else {}
    if isinstance(agent_extract, dict) and _agent_extract_complete(agent_extract):
        core_points = [str(item).strip() for item in (agent_extract.get("key_problems") or []) if str(item).strip()]
        if not core_points:
            core_points = infer_core_points(request, context_manifest, conversation)
        return {
            "run_id": request.get("run_id", ""),
            "project_name": request.get("project_name", "Deck Master Run"),
            "audience": agent_extract.get("audience") or locked.get("audience") or request.get("audience", "client"),
            "industry": locked.get("industry") or request.get("industry", ""),
            "business_goal": agent_extract.get("goal_decision") or locked.get("business_goal") or request.get("business_goal", ""),
            "core_points": core_points[:8],
            "must_cover_topics": request.get("must_cover_topics", []),
            "source_refs": [source.get("source_id") for source in context_manifest.get("sources", [])],
            "style_preference": request.get("style_preference", ""),
            "target_pages": request.get("target_pages", "auto"),
            "current_state": str(agent_extract.get("current_state") or ""),
            "constraints": [str(item) for item in (agent_extract.get("constraints") or []) if str(item).strip()],
            "non_goals": [str(item) for item in (agent_extract.get("non_goals") or []) if str(item).strip()],
            "acceptance": [str(item) for item in (agent_extract.get("acceptance") or []) if str(item).strip()],
            "source_conflicts": [dict(item) for item in (agent_extract.get("source_conflicts") or []) if isinstance(item, dict)],
            "gaps": [str(item) for item in (agent_extract.get("gaps") or []) if str(item).strip()],
            "brief_mode": "agent_extract",
            "boundaries": [
                "输出第一版可审查客户方案 Deck 草案。",
                "优先做论点、论证、论据和证据链，不追求一次性最终 PPTX。",
                "上下文只做运行时引用，不写入长期知识库。",
            ],
        }

    core_points = infer_core_points(request, context_manifest, conversation)
    return {
        "run_id": request.get("run_id", ""),
        "project_name": request.get("project_name", "Deck Master Run"),
        "audience": locked.get("audience") or request.get("audience", "client"),
        "industry": locked.get("industry") or request.get("industry", ""),
        "business_goal": locked.get("business_goal") or request.get("business_goal", ""),
        "core_points": core_points,
        "must_cover_topics": request.get("must_cover_topics", []),
        "source_refs": [source.get("source_id") for source in context_manifest.get("sources", [])],
        "style_preference": request.get("style_preference", ""),
        "target_pages": request.get("target_pages", "auto"),
        "brief_mode": "fixture_rules",
        "boundaries": [
            "输出第一版可审查客户方案 Deck 草案。",
            "优先做论点、论证、论据和证据链，不追求一次性最终 PPTX。",
            "上下文只做运行时引用，不写入长期知识库。",
        ],
    }


def _reconcile_conflicts(context_manifest, extraction, *, run_dir=None):
    """Preserve declared conflicts; this does not infer natural-language conflicts."""
    from quality.source_binding import evidence_index, source_quote_matches
    declared = [copy.deepcopy(c) for c in context_manifest.get("conflicts", []) if isinstance(c, dict)]
    proposals = {str(c.get("conflict_id") or ""): c for c in extraction.get("source_conflicts", []) if isinstance(c, dict)}
    seen = {str(c.get("conflict_id") or "") for c in declared}
    declared.extend(copy.deepcopy(c) for key, c in proposals.items() if key not in seen)
    index = evidence_index(context_manifest)
    resolved_records, issues = [], []
    for original in declared:
        conflict_id = str(original.get("conflict_id") or "")
        proposed = proposals.get(conflict_id, original)
        record = copy.deepcopy(original)
        reasons = []
        if not conflict_id or len(original.get("evidence_refs", [])) < 2:
            reasons.append("declared conflict lacks identity or opposing evidence refs")
        if proposed.get("description") != original.get("description") or proposed.get("evidence_refs") != original.get("evidence_refs"):
            reasons.append("resolution must preserve the original conflicting statements and evidence refs")
        if proposed.get("status") == "resolved":
            resolution = str(proposed.get("resolution") or "").strip()
            decision_ref = str(proposed.get("decision_ref") or "").strip()
            candidates = index.get(decision_ref, [])
            if not resolution or resolution not in extraction.get("constraints", []):
                reasons.append("resolved constraint must be explicit in Brief constraints")
            if len(candidates) != 1 or not source_quote_matches(*candidates[0], run_dir=run_dir):
                reasons.append("resolution decision_ref must identify a verified original source span")
            elif resolution not in str(candidates[0][1].get("quote") or ""):
                reasons.append("selected constraint must be present in the verified resolution quote")
            if not reasons:
                record.update(status="resolved", resolution=resolution, decision_ref=decision_ref)
        else:
            reasons.append("declared source conflict remains open")
        if reasons:
            record["status"] = "open"
            issues.append({"conflict_id": conflict_id, "code": "declared_source_conflict", "reasons": reasons,
                           "next_action": "review_source_conflict", "question_policy": "Ask the user only if the material cannot resolve an important decision."})
        resolved_records.append(record)
    return resolved_records, issues


def brief_conflict_blockers(brief, context_manifest, *, run_dir=None):
    """Recheck current declared conflicts rather than trusting stored ready flags."""
    return _reconcile_conflicts(context_manifest, brief, run_dir=run_dir)[1]


def compile_deck_brief(request, context_manifest, conversation, agent_extract=None, *, run_dir: str | Path | None = None):
    brief = _compile_deck_brief_content(request, context_manifest, conversation, agent_extract=agent_extract)
    conflicts, blockers = _reconcile_conflicts(context_manifest, agent_extract or {}, run_dir=run_dir)
    brief["source_conflicts"] = conflicts
    brief["conflict_blockers"] = blockers
    brief["status"] = "blocked" if blockers else "brief_ready"
    return brief
