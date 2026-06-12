from __future__ import annotations

from typing import Any


TARGET_STATUSES = {"pass", "warning", "fail", "pending", "not_applicable"}
DEFAULT_WEIGHTS = {
    "efficiency": 0.35,
    "page_acceptance": 0.20,
    "evidence_readiness": 0.15,
    "asset_reuse": 0.15,
    "quality_governance": 0.15,
}


def evaluate_max_target(value: float | int | None, target: float | int | None) -> str:
    if target is None:
        return "not_applicable"
    if value is None:
        return "pending"
    actual = float(value)
    expected = float(target)
    if actual <= expected:
        return "pass"
    if actual <= expected * 1.25:
        return "warning"
    return "fail"


def evaluate_min_target(value: float | int | None, target: float | int | None) -> str:
    if target is None:
        return "not_applicable"
    if value is None:
        return "pending"
    actual = float(value)
    expected = float(target)
    if actual >= expected:
        return "pass"
    if actual >= expected * 0.8:
        return "warning"
    return "fail"


def evaluate_bool_visible(value: bool | None, required: bool | None) -> str:
    if not required:
        return "not_applicable"
    if value is None:
        return "pending"
    return "pass" if value else "fail"


def build_target_evaluation(
    success_targets: dict[str, Any],
    *,
    efficiency_metrics: dict[str, Any],
    page_metrics: dict[str, Any],
    source_metrics: dict[str, Any],
    quality_metrics: dict[str, Any],
) -> dict[str, str]:
    return {
        "context_to_preview": evaluate_max_target(
            efficiency_metrics.get("created_to_preview_minutes"),
            success_targets.get("context_to_preview_minutes"),
        ),
        "context_to_review_ready": evaluate_max_target(
            efficiency_metrics.get("preview_to_first_quality_gate_minutes"),
            success_targets.get("context_to_review_ready_minutes"),
        ),
        "context_to_approved_queue": evaluate_max_target(
            efficiency_metrics.get("context_to_approved_queue_minutes"),
            success_targets.get("context_to_approved_queue_minutes"),
        ),
        "page_acceptance_rate": evaluate_min_target(
            page_metrics.get("page_acceptance_rate"),
            success_targets.get("page_acceptance_rate_min"),
        ),
        "reuse_adapt_rate": evaluate_min_target(
            source_metrics.get("reuse_adapt_rate"),
            success_targets.get("reuse_adapt_rate_min"),
        ),
        "p0_count": evaluate_max_target(
            quality_metrics.get("p0"),
            success_targets.get("p0_count_max"),
        ),
        "evidence_gap_visible": evaluate_bool_visible(
            quality_metrics.get("evidence_gap_count") is not None,
            success_targets.get("evidence_gap_visible"),
        ),
        "quality_gate": evaluate_bool_visible(
            quality_metrics.get("quality_gate_present"),
            success_targets.get("quality_gate_required"),
        ),
    }


def status_score(status: str) -> float | None:
    return {
        "pass": 1.0,
        "warning": 0.6,
        "fail": 0.0,
    }.get(status)


def _avg_status_score(statuses: list[str]) -> float:
    values = [status_score(status) for status in statuses]
    numeric = [value for value in values if value is not None]
    if not numeric:
        return 0.0
    return round(sum(numeric) / len(numeric), 4)


def _normalize_weights(raw: dict[str, Any] | None) -> dict[str, float]:
    weights = DEFAULT_WEIGHTS.copy()
    if isinstance(raw, dict) and raw:
        parsed: dict[str, float] = {}
        for key, value in raw.items():
            try:
                parsed[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        if parsed:
            weights = {key: value for key, value in parsed.items() if value > 0}
    total = sum(weights.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()
    return {key: value / total for key, value in weights.items()}


def build_score(target_evaluation: dict[str, str], weights: dict[str, Any] | None = None) -> dict[str, float]:
    component_scores = {
        "efficiency": _avg_status_score([
            target_evaluation.get("context_to_preview", "pending"),
            target_evaluation.get("context_to_review_ready", "pending"),
            target_evaluation.get("context_to_approved_queue", "pending"),
        ]),
        "page_acceptance": _avg_status_score([target_evaluation.get("page_acceptance_rate", "pending")]),
        "evidence_readiness": _avg_status_score([target_evaluation.get("evidence_gap_visible", "pending")]),
        "asset_reuse": _avg_status_score([target_evaluation.get("reuse_adapt_rate", "pending")]),
        "quality_governance": _avg_status_score([
            target_evaluation.get("p0_count", "pending"),
            target_evaluation.get("quality_gate", "pending"),
        ]),
    }
    normalized_weights = _normalize_weights(weights)
    overall = 0.0
    for key, weight in normalized_weights.items():
        overall += component_scores.get(key, 0.0) * weight
    return {"overall": round(overall, 4), **component_scores}

