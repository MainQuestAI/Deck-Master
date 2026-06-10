from __future__ import annotations

from statistics import mean
from typing import Any


DIMENSIONS = [
    "narrative_integrity",
    "page_job_clarity",
    "information_density",
    "evidence_and_specificity",
    "screenshot_and_asset_integration",
    "layout_variety",
    "consulting_style_expression",
    "visual_readiness",
    "delivery_readiness",
]

DIMENSION_LABELS = {
    "narrative_integrity": "Narrative Integrity",
    "page_job_clarity": "Page Job Clarity",
    "information_density": "Information Density",
    "evidence_and_specificity": "Evidence And Specificity",
    "screenshot_and_asset_integration": "Screenshot And Asset Integration",
    "layout_variety": "Layout Variety",
    "consulting_style_expression": "Consulting-Style Expression",
    "visual_readiness": "Visual Readiness",
    "delivery_readiness": "Delivery Readiness",
}

BLOCKING_SEVERITIES = {"P0", "P1"}


def default_scorecard(score: int = 4) -> dict[str, int]:
    return {dimension: score for dimension in DIMENSIONS}


def clamp_score(value: int) -> int:
    return max(1, min(5, value))


def lower_score(scorecard: dict[str, int], dimension: str, score: int) -> None:
    if dimension not in scorecard:
        return
    scorecard[dimension] = min(scorecard[dimension], clamp_score(score))


def decision_from(scorecard: dict[str, int], findings: list[dict[str, Any]]) -> str:
    scores = list(scorecard.values())
    if any(finding.get("severity") in {"P0", "P1"} for finding in findings):
        return "rework_required"
    if any(score <= 2 for score in scores):
        return "rework_required"
    if scores and mean(scores) >= 3.5 and all(score >= 3 for score in scores):
        if findings or any(score == 3 for score in scores):
            return "conditional_pass"
        return "pass"
    return "rework_required"


def blocks_delivery(status: str, findings: list[dict[str, Any]]) -> bool:
    return status == "rework_required" or any(
        finding.get("severity") in BLOCKING_SEVERITIES for finding in findings
    )


def score_summary(scorecard: dict[str, int]) -> dict[str, Any]:
    scores = list(scorecard.values())
    return {
        "average": round(mean(scores), 2) if scores else 0,
        "minimum": min(scores) if scores else 0,
        "dimensions": len(scores),
    }
