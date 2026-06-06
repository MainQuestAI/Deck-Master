from __future__ import annotations

from pathlib import Path
from typing import Any


SOURCE_DECISIONS = {"reuse", "adapt", "generate", "manual_placeholder"}


def candidate_score(candidate: dict[str, Any]) -> float:
    confidence = float(candidate.get("confidence") or candidate.get("score") or 0)
    win_rate = float(candidate.get("win_rate") or 0)
    reuse_count = min(float(candidate.get("reuse_count") or 0), 5.0) / 5.0
    screenshot_bonus = 0.08 if candidate.get("screenshot_path") else 0.0
    return round(confidence * 0.72 + win_rate * 0.16 + reuse_count * 0.04 + screenshot_bonus, 4)


def page_needs_manual_evidence(beat: dict[str, Any]) -> bool:
    text = f"{beat.get('role', '')} {beat.get('evidence_need', '')} {beat.get('page_title', '')}"
    return any(keyword in text for keyword in ("客户案例", "案例", "收益指标", "成本优化"))


def select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(candidates, key=candidate_score, reverse=True)[0]


def decide_for_beat(beat: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best = select_best_candidate(candidates)
    alternatives = sorted(candidates, key=candidate_score, reverse=True)[1:4]
    risk_flags: list[str] = []

    if best:
        score = candidate_score(best)
        if not best.get("screenshot_path"):
            risk_flags.append("missing_screenshot")
        if score >= 0.74 and best.get("screenshot_path"):
            decision = "reuse"
            reason = "历史页匹配度高、截图可用，可直接进入审批。"
        elif score >= 0.45:
            decision = "adapt"
            reason = "历史页结构可复用，但需要调整标题、客户语境或叙事角度。"
        else:
            decision = "generate"
            reason = "历史候选较弱，建议新生成页面。"
    else:
        score = 0.0
        if page_needs_manual_evidence(beat):
            decision = "manual_placeholder"
            reason = "该页需要客户案例或收益证据，当前信息不足，需要人工确认。"
            risk_flags.append("missing_required_evidence")
        else:
            decision = "generate"
            reason = "历史库没有可用候选，建议新生成页面。"

    return {
        "beat_id": beat.get("beat_id"),
        "order": beat.get("order"),
        "page_title": beat.get("page_title"),
        "role": beat.get("role"),
        "source_decision": decision,
        "decision_reason": reason,
        "selected_candidate": best,
        "alternatives": alternatives,
        "risk_flags": risk_flags,
        "confidence": score,
        "generation_brief": beat.get("generation_brief", ""),
        "visual_need": beat.get("visual_need", ""),
        "evidence_need": beat.get("evidence_need", ""),
        "approval_required": bool(beat.get("approval_required")),
    }


def decide_sourcing(narrative_plan: dict[str, Any], library_results: dict[str, Any]) -> dict[str, Any]:
    by_beat = library_results.get("by_beat", {}) if isinstance(library_results, dict) else {}
    decisions = []
    for beat in narrative_plan.get("beats", []):
        if not isinstance(beat, dict):
            continue
        candidates = by_beat.get(str(beat.get("beat_id")), [])
        decisions.append(decide_for_beat(beat, candidates if isinstance(candidates, list) else []))
    return {
        "run_id": narrative_plan.get("run_id", ""),
        "title": narrative_plan.get("title", ""),
        "source": library_results.get("source", ""),
        "decisions": decisions,
    }


def load_library_results(run_dir: str | Path) -> dict[str, Any]:
    import json

    path = Path(run_dir).expanduser().resolve() / "library_results" / "selection.json"
    return json.loads(path.read_text(encoding="utf-8"))
