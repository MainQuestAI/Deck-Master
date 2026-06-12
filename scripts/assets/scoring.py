from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "deck_sourcing_scoring.v2"

# 权重配置
WEIGHTS = {
    "semantic_match": 0.24,
    "narrative_role_match": 0.14,
    "archetype_match": 0.10,
    "screenshot_available": 0.08,
    "source_credibility": 0.08,
    "win_rate": 0.10,
    "approval_history": 0.08,
    "delivery_history": 0.06,
    "visual_continuity": 0.06,
    "evidence_sufficiency": 0.06,
}

# 惩罚配置
PENALTIES = {
    "high_customer_context_conflict": -0.25,
    "medium_customer_context_conflict": -0.10,
    "missing_screenshot_reuse_cap": 0.69,
    "internal_only_client_export_cap": 0.59,
}

# 决策阈值
THRESHOLDS = {
    "reuse": {"min_score": 0.78, "screenshot_required": True, "max_context_conflict": 0.20},
    "adapt": {"min_score": 0.58, "screenshot_required": False, "max_context_conflict": 0.50},
}


def compute_score_v2(
    candidate: dict[str, Any],
    beat: dict[str, Any],
    *,
    asset_feedback: dict[str, Any] | None = None,
    asset_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """计算可解释的 sourcing score v2。

    返回：
    {
        "total_score": float,
        "dimension_scores": {dimension: score, ...},
        "penalties_applied": [{reason, adjustment}],
        "decision": "reuse" | "adapt" | "generate" | "manual_placeholder",
        "reason": str,
    }
    """
    dimension_scores: dict[str, float] = {}

    # 1. semantic_match: 来自 candidate 的 confidence/score
    dimension_scores["semantic_match"] = _clamp(float(candidate.get("confidence", candidate.get("score", 0))))

    # 2. narrative_role_match: beat role 与 candidate 匹配
    dimension_scores["narrative_role_match"] = _narrative_role_score(beat, candidate)

    # 3. archetype_match: candidate archetypes 与 beat role 匹配
    dimension_scores["archetype_match"] = _archetype_score(beat, candidate)

    # 4. screenshot_available: 是否有截图
    dimension_scores["screenshot_available"] = 1.0 if candidate.get("screenshot_path") else 0.0

    # 5. source_credibility: 来源可信度
    dimension_scores["source_credibility"] = _source_credibility(candidate)

    # 6. win_rate: 历史胜率
    dimension_scores["win_rate"] = _clamp(float(candidate.get("win_rate", 0)))

    # 7. approval_history: 从 asset feedback 获取
    if asset_feedback:
        approval_count = asset_feedback.get("approval_count", 0)
        total = asset_feedback.get("total_events", 0)
        dimension_scores["approval_history"] = (approval_count / max(total, 1)) if total > 0 else 0.5
    else:
        dimension_scores["approval_history"] = 0.5  # 无历史数据时默认中等

    # 8. delivery_history: 交付历史
    if asset_feedback:
        dimension_scores["delivery_history"] = min(1.0, asset_feedback.get("delivered_count", 0) / 3.0)
    else:
        dimension_scores["delivery_history"] = 0.5

    # 9. visual_continuity: 视觉连续性（简化：有截图且来自同一项目得高分）
    dimension_scores["visual_continuity"] = 0.7 if candidate.get("screenshot_path") else 0.3

    # 10. evidence_sufficiency: 证据充分性
    has_evidence = bool(candidate.get("text_summary") or candidate.get("excerpt"))
    dimension_scores["evidence_sufficiency"] = 0.8 if has_evidence else 0.3

    # 加权总分
    total_score = sum(
        dimension_scores[dim] * WEIGHTS.get(dim, 0)
        for dim in dimension_scores
    )

    # 惩罚
    penalties: list[dict[str, Any]] = []
    context_conflict = _estimate_context_conflict(beat, candidate)
    if context_conflict > 0.7:
        total_score += PENALTIES["high_customer_context_conflict"]
        penalties.append({"reason": "high_customer_context_conflict", "adjustment": PENALTIES["high_customer_context_conflict"]})
    elif context_conflict > 0.3:
        total_score += PENALTIES["medium_customer_context_conflict"]
        penalties.append({"reason": "medium_customer_context_conflict", "adjustment": PENALTIES["medium_customer_context_conflict"]})

    total_score = _clamp(total_score)

    # 决策
    decision, reason = _make_decision(total_score, candidate, beat, dimension_scores, context_conflict)

    return {
        "total_score": round(total_score, 4),
        "dimension_scores": {k: round(v, 4) for k, v in dimension_scores.items()},
        "penalties_applied": penalties,
        "decision": decision,
        "reason": reason,
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _narrative_role_score(beat: dict[str, Any], candidate: dict[str, Any]) -> float:
    beat_role = beat.get("role", "")
    candidate_role = candidate.get("role", candidate.get("narrative_role", ""))
    if beat_role and candidate_role and beat_role == candidate_role:
        return 1.0
    if beat_role and candidate_role:
        return 0.3
    return 0.5


def _archetype_score(beat: dict[str, Any], candidate: dict[str, Any]) -> float:
    beat_role = beat.get("role", "")
    archetypes = candidate.get("archetypes", [])
    if beat_role in archetypes:
        return 1.0
    if any(beat_role in str(a) for a in archetypes):
        return 0.6
    return 0.4


def _source_credibility(candidate: dict[str, Any]) -> float:
    project = candidate.get("source_project", "")
    if project:
        return 0.8
    return 0.5


def _estimate_context_conflict(beat: dict[str, Any], candidate: dict[str, Any]) -> float:
    """估计客户语境冲突程度。0 = 无冲突, 1 = 高冲突。"""
    beat_industry = beat.get("industry", "")
    # 直接字段匹配 → 高置信度冲突
    candidate_industry_direct = candidate.get("industry", "")
    if beat_industry and candidate_industry_direct and beat_industry != candidate_industry_direct:
        return 0.8
    # metadata 嵌套字段 → 较低置信度冲突
    candidate_industry_meta = (candidate.get("metadata") or {}).get("industry", "")
    if beat_industry and candidate_industry_meta and beat_industry != candidate_industry_meta:
        return 0.4
    return 0.0


def _make_decision(
    score: float,
    candidate: dict[str, Any],
    beat: dict[str, Any],
    dimension_scores: dict[str, float],
    context_conflict: float,
) -> tuple[str, str]:
    """基于分数和约束做决策。"""
    has_screenshot = bool(candidate.get("screenshot_path"))
    evidence_need = beat.get("evidence_need", "")
    needs_case_evidence = any(kw in evidence_need for kw in ("客户案例", "案例", "收益指标", "成本优化"))
    lacks_evidence = not candidate.get("text_summary") and not candidate.get("excerpt")

    # 硬性约束：需要客户证据但候选完全没有 → manual_placeholder（优先级最高）
    if needs_case_evidence and lacks_evidence:
        return "manual_placeholder", "该页需要客户案例或收益证据，当前信息不足，需要人工确认。"

    # reuse 检查
    reuse_thresh = THRESHOLDS["reuse"]
    if (
        score >= reuse_thresh["min_score"]
        and has_screenshot
        and context_conflict <= reuse_thresh["max_context_conflict"]
    ):
        return "reuse", "历史页匹配度高、截图可用、客户语境一致，可直接复用。"

    # adapt 检查
    adapt_thresh = THRESHOLDS["adapt"]
    if (
        score >= adapt_thresh["min_score"]
        and context_conflict <= adapt_thresh["max_context_conflict"]
    ):
        return "adapt", "历史页结构可复用，需要调整标题、客户语境或叙事角度。"

    return "generate", "历史候选较弱或客户语境冲突较大，建议新生成页面。"


def tie_breaker(candidates_with_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tie-breaker 排序。

    1. evidence_sufficiency 高者优先
    2. approval_history 高者优先
    3. delivery_history 高者优先
    4. canonical_slide_id 字典序靠前者优先
    """
    def sort_key(item: dict[str, Any]) -> tuple[float, float, float, str]:
        scores = item.get("dimension_scores", {})
        return (
            -scores.get("evidence_sufficiency", 0),
            -scores.get("approval_history", 0),
            -scores.get("delivery_history", 0),
            item.get("canonical_slide_id", ""),
        )
    return sorted(candidates_with_scores, key=sort_key)
