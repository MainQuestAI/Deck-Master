from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from planning.narrative_planner import build_required_modules_status
from sourcing.plan import (
    ALL_DECISIONS,
    PERMISSION_BLOCKED,
    PERMISSION_PENDING,
    PERMISSION_RESTRICTED,
)


@dataclass
class StageCheckResult:
    valid: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    blocking_summary: list[dict[str, Any]] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    required_modules_status: list[dict[str, Any]] = field(default_factory=list)
    safe_next_action: str = ""
    repair_owner: str = ""


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _planner_checks(root: Path) -> StageCheckResult:
    payload = _safe_read_json(root / "narrative_plan.json")
    beats = payload.get("beats")
    if not isinstance(beats, list):
        return StageCheckResult()

    module_coverage = build_required_modules_status(beats)
    missing_modules = list(module_coverage["missing_modules"])
    required_modules_status = list(module_coverage["required_modules_status"])
    checks = [{
        "check": "required_modules_coverage",
        "status": "pass" if not missing_modules else "fail",
        "missing_modules": missing_modules,
    }]
    if not missing_modules:
        return StageCheckResult(
            valid=True,
            checks=checks,
            required_modules_status=required_modules_status,
        )

    message = "方案规划缺少必备模块：" + "、".join(missing_modules)
    return StageCheckResult(
        valid=False,
        checks=checks,
        blocking=[f"missing_module:{item}" for item in missing_modules],
        blocking_summary=[{
            "code": "coverage_gap",
            "blocking_type": "coverage_gap",
            "message": message,
            "repair_owner": "deck-planner",
        }],
        coverage_gaps=missing_modules,
        required_modules_status=required_modules_status,
        safe_next_action="补齐缺失模块后，再提交方案规划阶段。",
        repair_owner="deck-planner",
    )


def _normalize_sourcing_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("pages"), list):
        return [item for item in payload["pages"] if isinstance(item, dict)]
    if isinstance(payload.get("decisions"), list):
        pages: list[dict[str, Any]] = []
        for item in payload["decisions"]:
            if not isinstance(item, dict):
                continue
            pages.append({
                "page_id": item.get("page_id") or item.get("beat_id") or "",
                "decision": item.get("decision") or item.get("source_decision") or "",
                "reason": item.get("reason") or item.get("reuse_reason") or "",
                "source_authority": item.get("source_authority") or "",
                "freshness_status": item.get("freshness_status") or "",
                "permission_status": item.get("permission_status") or "",
                "selected_sources": [item.get("selected_candidate")] if isinstance(item.get("selected_candidate"), dict) else [],
                "missing_evidence": list(item.get("missing_evidence") or []),
            })
        return pages
    return []


def _is_high_risk_page(page: dict[str, Any]) -> bool:
    decision = str(page.get("decision") or "").strip().lower()
    if decision in {"reuse", "adapt", "evidence"}:
        return True
    if page.get("selected_sources"):
        return True
    return bool(page.get("missing_evidence"))


def _sourcing_checks(root: Path) -> StageCheckResult:
    payload = _safe_read_json(root / "sourcing_plan.json")
    pages = _normalize_sourcing_pages(payload)
    if not pages:
        return StageCheckResult()

    seen: set[str] = set()
    duplicate_pages: list[str] = []
    missing_decision_pages: list[str] = []
    authority_gap_pages: list[str] = []
    freshness_gap_pages: list[str] = []
    permission_gap_pages: list[str] = []
    reason_gap_pages: list[str] = []

    for index, page in enumerate(pages, start=1):
        page_id = str(page.get("page_id") or f"page_{index}")
        decision = str(page.get("decision") or "").strip().lower()
        authority = str(page.get("source_authority") or "").strip().lower()
        freshness = str(page.get("freshness_status") or "").strip().lower()
        permission = str(page.get("permission_status") or "").strip().lower()
        reason = str(page.get("reason") or "").strip()

        if page_id in seen:
            duplicate_pages.append(page_id)
        seen.add(page_id)

        if decision not in ALL_DECISIONS:
            missing_decision_pages.append(page_id)
        if not reason:
            reason_gap_pages.append(page_id)

        if not _is_high_risk_page(page):
            continue
        if authority in {"", "unknown", "pending"}:
            authority_gap_pages.append(page_id)
        if freshness in {"", "unknown", "pending", "stale", "outdated", "expired"}:
            freshness_gap_pages.append(page_id)
        if permission in {PERMISSION_PENDING, PERMISSION_RESTRICTED, PERMISSION_BLOCKED, ""}:
            permission_gap_pages.append(page_id)

    checks = [{
        "check": "sourcing_decision_integrity",
        "status": "pass" if not missing_decision_pages and not duplicate_pages and not reason_gap_pages else "fail",
        "missing_decision_pages": missing_decision_pages,
        "duplicate_pages": duplicate_pages,
        "reason_gap_pages": reason_gap_pages,
    }, {
        "check": "sourcing_risk_closure",
        "status": "pass" if not authority_gap_pages and not freshness_gap_pages and not permission_gap_pages else "fail",
        "authority_gap_pages": authority_gap_pages,
        "freshness_gap_pages": freshness_gap_pages,
        "permission_gap_pages": permission_gap_pages,
    }]

    if not any((duplicate_pages, missing_decision_pages, authority_gap_pages, freshness_gap_pages, permission_gap_pages, reason_gap_pages)):
        return StageCheckResult(valid=True, checks=checks)

    coverage_gaps: list[str] = []
    blocking_summary: list[dict[str, Any]] = []

    if missing_decision_pages or duplicate_pages or reason_gap_pages:
        coverage_gaps.append("每页必须保留唯一且有理由的 sourcing decision")
        blocking_summary.append({
            "code": "sourcing_decision_gap",
            "blocking_type": "coverage_gap",
            "message": "素材来源阶段仍有页面缺少唯一决策或决策理由。",
            "repair_owner": "deck-sourcing",
        })
    if authority_gap_pages:
        coverage_gaps.append("高风险页面的来源权威性未确认")
        blocking_summary.append({
            "code": "sourcing_authority_gap",
            "blocking_type": "coverage_gap",
            "message": "以下页面的来源权威性未确认：" + "、".join(authority_gap_pages),
            "repair_owner": "deck-sourcing",
        })
    if freshness_gap_pages:
        coverage_gaps.append("高风险页面的时效性未确认")
        blocking_summary.append({
            "code": "sourcing_freshness_gap",
            "blocking_type": "coverage_gap",
            "message": "以下页面的时效性未确认：" + "、".join(freshness_gap_pages),
            "repair_owner": "deck-sourcing",
        })
    if permission_gap_pages:
        coverage_gaps.append("高风险页面的复用权限未确认")
        blocking_summary.append({
            "code": "sourcing_permission_gap",
            "blocking_type": "coverage_gap",
            "message": "以下页面的复用权限未确认：" + "、".join(permission_gap_pages),
            "repair_owner": "deck-sourcing",
        })

    return StageCheckResult(
        valid=False,
        checks=checks,
        blocking=[
            *[f"missing_decision:{page_id}" for page_id in missing_decision_pages],
            *[f"duplicate_decision:{page_id}" for page_id in duplicate_pages],
            *[f"authority_gap:{page_id}" for page_id in authority_gap_pages],
            *[f"freshness_gap:{page_id}" for page_id in freshness_gap_pages],
            *[f"permission_gap:{page_id}" for page_id in permission_gap_pages],
            *[f"reason_gap:{page_id}" for page_id in reason_gap_pages],
        ],
        blocking_summary=blocking_summary,
        coverage_gaps=coverage_gaps,
        safe_next_action="先补齐页面来源权威性、时效性、授权和决策理由，再提交素材来源阶段。",
        repair_owner="deck-sourcing",
    )


def evaluate_stage_checks(run_dir: str | Path, stage_id: str) -> StageCheckResult:
    root = Path(run_dir).expanduser().resolve()
    if stage_id == "deck-planner":
        return _planner_checks(root)
    if stage_id == "deck-sourcing":
        return _sourcing_checks(root)
    return StageCheckResult()


__all__ = ["StageCheckResult", "evaluate_stage_checks"]
