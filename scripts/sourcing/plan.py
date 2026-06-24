"""Sourcing Plan v2 (B2).

Produces ``deck_sourcing_plan.v2`` — one decision per page task, with source
authority, freshness, permission, evidence gaps and a production budget class.
The plan is the Producer's only sourcing input: it must not guess decisions.

A v1 plan (``decisions[]`` keyed by beat) can be safely migrated to v2.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_sourcing_plan.v2"

# Six decision classes (B2 must-implement #2).
DECISION_REUSE = "reuse"
DECISION_ADAPT = "adapt"
DECISION_GENERATE = "generate"
DECISION_EVIDENCE = "evidence"
DECISION_MANUAL = "manual"
DECISION_BLOCKED = "blocked"
ALL_DECISIONS = (
    DECISION_REUSE, DECISION_ADAPT, DECISION_GENERATE,
    DECISION_EVIDENCE, DECISION_MANUAL, DECISION_BLOCKED,
)

PERMISSION_APPROVED = "approved"
PERMISSION_PENDING = "pending"
PERMISSION_RESTRICTED = "restricted"
PERMISSION_BLOCKED = "blocked"
PERMISSION_NOT_REQUIRED = "not_required"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _sha(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class PageInput:
    page_id: str
    page_task_id: str
    claim_ids: list[str]
    evidence_need: list[str]
    title: str = ""


def _extract_pages(page_tasks: dict[str, Any]) -> list[PageInput]:
    """Normalize page_tasks / narrative_plan beats into PageInput list."""
    raw = []
    if isinstance(page_tasks, dict):
        if isinstance(page_tasks.get("pages"), list):
            raw = page_tasks["pages"]
        elif isinstance(page_tasks.get("beats"), list):
            raw = page_tasks["beats"]
    elif isinstance(page_tasks, list):
        raw = page_tasks
    out: list[PageInput] = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            continue
        pid = str(p.get("page_id") or p.get("beat_id") or f"page_{i+1}")
        tid = str(p.get("page_task_id") or p.get("task_id") or pid)
        claims = list(p.get("claim_ids") or p.get("claims") or [])
        evidence = list(p.get("evidence_need") or p.get("evidence_needs") or [])
        out.append(PageInput(pid, tid, claims, evidence, str(p.get("page_title") or p.get("title") or "")))
    return out


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    def score(c: dict[str, Any]) -> float:
        return float(c.get("confidence") or c.get("score") or 0)
    return sorted(candidates, key=score, reverse=True)[0]


def _decide_for_page(
    page: PageInput,
    candidates: list[dict[str, Any]],
    *,
    permission_default: str,
    allow_generate: bool,
) -> dict[str, Any]:
    selected = _select_candidate(candidates)
    if selected:
        decision = DECISION_REUSE if selected.get("reuse_safe", True) else DECISION_ADAPT
        source_authority = str(selected.get("source_authority") or selected.get("authority") or "unknown")
        freshness = str(selected.get("freshness_status") or "unknown")
        permission = str(selected.get("permission_status") or permission_default)
        selected_sources = [selected]
        confidence = float(selected.get("confidence") or selected.get("score") or 0.5)
    else:
        # no candidate: evidence-only page, or generate, or manual
        if page.evidence_need and not allow_generate:
            decision = DECISION_EVIDENCE
        elif allow_generate:
            decision = DECISION_GENERATE
        else:
            decision = DECISION_MANUAL
        source_authority = "pending"
        freshness = "pending"
        permission = PERMISSION_NOT_REQUIRED if decision == DECISION_EVIDENCE else permission_default
        selected_sources = []
        confidence = 0.3

    # permission gate can block
    if permission == PERMISSION_BLOCKED:
        decision = DECISION_BLOCKED

    missing_evidence = []
    if not selected_sources and page.evidence_need:
        missing_evidence = list(page.evidence_need)

    return {
        "page_id": page.page_id,
        "page_task_id": page.page_task_id,
        "decision": decision,
        "reason": f"auto-decided: {decision}",
        "confidence": round(confidence, 4),
        "claim_ids": list(page.claim_ids),
        "evidence_need": list(page.evidence_need),
        "selected_sources": selected_sources,
        "source_authority": source_authority,
        "freshness_status": freshness,
        "permission_status": permission,
        "usage_constraints": list(selected.get("usage_constraints", []) if selected else []),
        "missing_evidence": missing_evidence,
        "production_budget_class": _budget_for(decision),
    }


def _budget_for(decision: str) -> str:
    if decision == DECISION_GENERATE:
        return "medium"
    if decision == DECISION_ADAPT:
        return "low"
    if decision == DECISION_MANUAL:
        return "high"
    return "none"


def build_sourcing_plan_v2(
    *,
    run_id: str,
    page_tasks: dict[str, Any] | list[dict[str, Any]],
    library_results: dict[str, Any] | None = None,
    permission_default: str = PERMISSION_PENDING,
    allow_generate: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    pages_in = _extract_pages(page_tasks if isinstance(page_tasks, (dict, list)) else {})
    lib = library_results or {}
    by_beat = lib.get("by_beat", {}) if isinstance(lib, dict) else {}

    page_decisions: list[dict[str, Any]] = []
    for page in pages_in:
        candidates = by_beat.get(page.page_id) or by_beat.get(page.page_task_id) or []
        if not isinstance(candidates, list):
            candidates = []
        page_decisions.append(
            _decide_for_page(page, candidates, permission_default=permission_default, allow_generate=allow_generate)
        )

    coverage = _coverage(page_decisions)
    approval_readiness = _approval_readiness(page_decisions)
    status = "blocked" if approval_readiness["blocked_pages"] else ("awaiting_approval" if approval_readiness["ready"] else "draft")

    source_fingerprint = _sha({
        "run_id": run_id,
        "pages": [p.page_id for p in pages_in],
        "library_source": lib.get("library_source") or lib.get("source") or "none",
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": status,
        "source_fingerprint": source_fingerprint,
        "pages": page_decisions,
        "coverage": coverage,
        "approval_readiness": approval_readiness,
        "created_at": _utc(now or _now()),
    }


def _coverage(pages: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(pages)
    by_decision: dict[str, int] = {}
    blocked = 0
    missing_evidence_pages = 0
    for p in pages:
        d = p.get("decision")
        by_decision[d] = by_decision.get(d, 0) + 1
        if d == DECISION_BLOCKED:
            blocked += 1
        if p.get("missing_evidence"):
            missing_evidence_pages += 1
    return {
        "total_pages": total,
        "by_decision": by_decision,
        "blocked_pages": blocked,
        "missing_evidence_pages": missing_evidence_pages,
        "complete": total > 0 and blocked == 0 and missing_evidence_pages == 0,
    }


def _approval_readiness(pages: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = [p["page_id"] for p in pages if p.get("decision") == DECISION_BLOCKED]
    pending_permission = [p["page_id"] for p in pages if p.get("permission_status") == PERMISSION_PENDING]
    missing = [p["page_id"] for p in pages if p.get("missing_evidence")]
    ready = not blocked and not pending_permission and not missing
    return {
        "ready": ready,
        "blocked_pages": blocked,
        "pending_permission_pages": pending_permission,
        "missing_evidence_pages": missing,
    }


def migrate_v1(v1_plan: dict[str, Any]) -> dict[str, Any]:
    """Safe migration from a v1 sourcing plan (``decisions[]`` by beat) to v2.

    v1 decision values map: ``manual_placeholder`` -> ``manual``; v1 had no
    ``evidence`` / ``blocked`` classes — those are derived from permission and
    candidate presence. Unknown v1 decisions fall back to ``manual``.
    """
    decisions = v1_plan.get("decisions", []) if isinstance(v1_plan, dict) else []
    pages: list[dict[str, Any]] = []
    for i, d in enumerate(decisions):
        if not isinstance(d, dict):
            continue
        pid = str(d.get("beat_id") or d.get("page_id") or f"page_{i+1}")
        v1_decision = str(d.get("decision") or "").strip().lower()
        if v1_decision == "manual_placeholder":
            decision = DECISION_MANUAL
        elif v1_decision in ALL_DECISIONS:
            decision = v1_decision
        else:
            decision = DECISION_MANUAL
        selected = d.get("selected_candidate") if isinstance(d.get("selected_candidate"), dict) else None
        permission = PERMISSION_APPROVED if selected else PERMISSION_NOT_REQUIRED
        if decision == DECISION_BLOCKED:
            permission = PERMISSION_BLOCKED
        pages.append({
            "page_id": pid,
            "page_task_id": str(d.get("page_task_id") or pid),
            "decision": decision,
            "reason": f"migrated from v1: {v1_decision or 'unknown'}",
            "confidence": float((selected or {}).get("confidence") or 0.5),
            "claim_ids": list(d.get("claim_ids") or []),
            "evidence_need": list(d.get("evidence_need") or []),
            "selected_sources": [selected] if selected else [],
            "source_authority": str((selected or {}).get("source_authority") or "unknown"),
            "freshness_status": str((selected or {}).get("freshness_status") or "unknown"),
            "permission_status": permission,
            "usage_constraints": list((selected or {}).get("usage_constraints", []) or []),
            "missing_evidence": list(d.get("missing_evidence") or []),
            "production_budget_class": _budget_for(decision),
        })
    coverage = _coverage(pages)
    approval_readiness = _approval_readiness(pages)
    status = "blocked" if approval_readiness["blocked_pages"] else "draft"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(v1_plan.get("run_id", "")),
        "status": status,
        "source_fingerprint": _sha({"run_id": v1_plan.get("run_id", ""), "v1": v1_plan.get("source", "")}),
        "pages": pages,
        "coverage": coverage,
        "approval_readiness": approval_readiness,
        "created_at": _utc(_now()),
        "migrated_from": "deck_sourcing_plan.v1",
    }


__all__ = [
    "build_sourcing_plan_v2",
    "migrate_v1",
    "SCHEMA_VERSION",
    "ALL_DECISIONS",
]
