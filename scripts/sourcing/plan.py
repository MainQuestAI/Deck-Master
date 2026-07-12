"""Canonical Sourcing Plan v2 construction and legacy migration."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "deck_sourcing_plan.v2"

DECISION_REUSE = "reuse"
DECISION_ADAPT = "adapt"
DECISION_GENERATE = "generate"
DECISION_EVIDENCE = "evidence"
DECISION_MANUAL = "manual"
DECISION_BLOCKED = "blocked"
ALL_DECISIONS = (
    DECISION_REUSE,
    DECISION_ADAPT,
    DECISION_GENERATE,
    DECISION_EVIDENCE,
    DECISION_MANUAL,
    DECISION_BLOCKED,
)

PERMISSION_APPROVED = "approved"
PERMISSION_PENDING = "pending"
PERMISSION_RESTRICTED = "restricted"
PERMISSION_BLOCKED = "blocked"
PERMISSION_NOT_REQUIRED = "not_required"

SAFE_SOURCE_FIELDS = (
    "candidate_id",
    "slide_id",
    "asset_key",
    "title",
    "text_summary",
    "page_number",
    "score",
    "confidence",
    "source_asset_id",
    "source_display_name",
    "screenshot_ref",
    "candidate_origin",
    "reuse_policy",
    "slot_id",
    "screenshot_path",
    "win_rate",
    "reuse_count",
    "source_authority",
    "freshness_status",
    "permission_status",
    "reuse_safe",
    "usage_constraints",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _sha(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None or value == "":
        return []
    return [str(value)]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class PageInput:
    page_id: str
    page_task_id: str
    claim_ids: list[str]
    evidence_need: list[str]
    title: str
    order: float
    index: int
    allow_repeat_source: bool
    role: str = ""
    content_goal: str = ""
    generation_brief: str = ""
    visual_need: str = ""
    workspace_refs: list[str] = field(default_factory=list)
    quality_requirements: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateEdge:
    page: PageInput
    candidate: dict[str, Any]
    score: float
    rank: int


def _extract_pages(page_tasks: dict[str, Any] | list[dict[str, Any]]) -> list[PageInput]:
    raw: list[Any] = []
    if isinstance(page_tasks, dict):
        for key in ("pages", "tasks", "beats"):
            if isinstance(page_tasks.get(key), list):
                raw = page_tasks[key]
                break
    elif isinstance(page_tasks, list):
        raw = page_tasks

    out: list[PageInput] = []
    seen_page_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        planning = item.get("planning") if isinstance(item.get("planning"), dict) else {}
        retrieval = item.get("retrieval") if isinstance(item.get("retrieval"), dict) else {}
        page_id = str(item.get("page_id") or item.get("beat_id") or "").strip()
        page_task_id = str(
            item.get("page_task_id")
            or item.get("task_id")
            or item.get("page_id")
            or item.get("beat_id")
            or ""
        ).strip()
        if not page_id:
            raise ValueError(f"page_tasks[{index + 1}] is missing page_id/beat_id")
        if not page_task_id:
            raise ValueError(f"page_tasks[{index + 1}] is missing page_task_id")
        if page_id in seen_page_ids:
            raise ValueError(f"duplicate page_id: {page_id}")
        if page_task_id in seen_task_ids:
            raise ValueError(f"duplicate page_task_id: {page_task_id}")
        seen_page_ids.add(page_id)
        seen_task_ids.add(page_task_id)

        out.append(
            PageInput(
                page_id=page_id,
                page_task_id=page_task_id,
                claim_ids=_string_list(item.get("claim_ids") or planning.get("claim_ids")),
                evidence_need=_string_list(item.get("evidence_need") or planning.get("evidence_need")),
                title=str(item.get("page_title") or item.get("title") or planning.get("page_title") or ""),
                order=_number(item.get("order"), float(index + 1)),
                index=index,
                allow_repeat_source=(
                    item.get("allow_repeat_source") is True
                    or retrieval.get("allow_repeat_source") is True
                ),
                role=str(planning.get("role") or ""),
                content_goal=str(planning.get("content_goal") or ""),
                generation_brief=str(
                    (item.get("generation") or {}).get("generation_brief") or ""
                ),
                visual_need=str(planning.get("visual_need") or ""),
                workspace_refs=_string_list(planning.get("workspace_refs")),
                quality_requirements=_string_list(planning.get("quality_requirements")),
            )
        )
    return out


def _selection_pools(library_results: dict[str, Any]) -> dict[str, tuple[list[Any], dict[str, Any]]]:
    pools: dict[str, tuple[list[Any], dict[str, Any]]] = {}
    selections = library_results.get("selections")
    if isinstance(selections, list):
        for selection in selections:
            if not isinstance(selection, dict):
                continue
            candidates = selection.get("candidates")
            if not isinstance(candidates, list):
                candidates = []
            for identity in (selection.get("beat_id"), selection.get("page_task_id")):
                key = str(identity or "").strip()
                if key:
                    pools[key] = (candidates, selection)

    by_beat = library_results.get("by_beat")
    if isinstance(by_beat, dict):
        for identity, candidates in by_beat.items():
            key = str(identity or "").strip()
            if key and key not in pools and isinstance(candidates, list):
                pools[key] = (candidates, {})
    return pools


def _safe_selected_source(
    candidate: dict[str, Any],
    page: PageInput,
    selection: dict[str, Any],
) -> dict[str, Any] | None:
    asset_key = str(candidate.get("asset_key") or "").strip()
    query_trace_id = str(selection.get("query_trace_id") or candidate.get("query_trace_id") or "").strip()
    if not asset_key or not query_trace_id:
        return None
    safe = {
        key: candidate[key]
        for key in SAFE_SOURCE_FIELDS
        if key in candidate and candidate[key] is not None
    }
    safe["asset_key"] = asset_key
    safe["query_trace_id"] = query_trace_id
    safe["page_task_id"] = page.page_task_id
    safe["retrieval_method"] = str(selection.get("retrieval_method") or "")
    safe["preview_status"] = str(selection.get("preview_status") or "ready")
    for field in ("screenshot_ref", "screenshot_path"):
        value = str(safe.get(field) or "")
        if value and (not value.startswith("preview_assets/") or ".." in value or "\\" in value):
            safe.pop(field, None)
    return safe


def _build_edges(
    pages: list[PageInput],
    library_results: dict[str, Any],
) -> tuple[list[CandidateEdge], list[str]]:
    pools = _selection_pools(library_results)
    edges: list[CandidateEdge] = []
    warnings: list[str] = []
    for page in pages:
        candidates, selection = pools.get(page.page_id) or pools.get(page.page_task_id) or ([], {})
        selection_page_task_id = str(selection.get("page_task_id") or "").strip()
        if selection_page_task_id and selection_page_task_id != page.page_task_id:
            warnings.append(
                f"PAGE_TASK_ID_MISMATCH:{page.page_id}:{selection_page_task_id}:{page.page_task_id}"
            )
            continue
        for rank, raw_candidate in enumerate(candidates):
            if not isinstance(raw_candidate, dict):
                continue
            candidate_page_task_id = str(raw_candidate.get("page_task_id") or "").strip()
            if candidate_page_task_id and candidate_page_task_id != page.page_task_id:
                warnings.append(
                    f"PAGE_TASK_ID_MISMATCH:{page.page_id}:{candidate_page_task_id}:{page.page_task_id}"
                )
                continue
            selected = _safe_selected_source(raw_candidate, page, selection)
            if selected is None:
                code = "CANDIDATE_IDENTITY_MISSING" if not raw_candidate.get("asset_key") else "CANDIDATE_SOURCE_IDENTITY_MISSING"
                warnings.append(f"{code}:{page.page_id}:{rank + 1}")
                continue
            score = _number(raw_candidate.get("score"), _number(raw_candidate.get("confidence")))
            edges.append(CandidateEdge(page=page, candidate=selected, score=score, rank=rank))
    edges.sort(
        key=lambda edge: (
            -edge.score,
            edge.page.order,
            edge.rank,
            edge.page.index,
            str(edge.candidate.get("asset_key")),
        )
    )
    return edges, warnings


def _allocate_candidates(
    pages: list[PageInput],
    library_results: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    edges, warnings = _build_edges(pages, library_results)
    assigned: dict[str, dict[str, Any]] = {}
    used_assets: set[str] = set()
    for edge in edges:
        page = edge.page
        if page.page_id in assigned:
            continue
        asset_key = str(edge.candidate["asset_key"])
        if asset_key in used_assets and not page.allow_repeat_source:
            continue
        assigned[page.page_id] = edge.candidate
        if page.allow_repeat_source:
            warnings.append(f"REPEAT_SOURCE_ALLOWED:{page.page_id}:{asset_key}")
        used_assets.add(asset_key)
    return assigned, sorted(set(warnings))


def _decide_for_page(
    page: PageInput,
    selected: dict[str, Any] | None,
    *,
    permission_default: str,
    allow_generate: bool,
) -> dict[str, Any]:
    if selected:
        reuse_policy = str(selected.get("reuse_policy") or "")
        preview_status = str(selected.get("preview_status") or "ready")
        retrieval_method = str(selected.get("retrieval_method") or "")
        reuse_safe = selected.get("reuse_safe")

        if reuse_policy == "adapt_only":
            decision, reason = DECISION_ADAPT, "POLICY_ADAPT_ONLY"
        elif reuse_policy == "adapt":
            decision, reason = DECISION_ADAPT, "POLICY_ADAPT"
        elif retrieval_method == "semantic_fallback":
            decision, reason = DECISION_ADAPT, "SEMANTIC_FALLBACK_ADAPT"
        elif preview_status in ("missing", "invalid"):
            decision, reason = DECISION_ADAPT, "PREVIEW_MISSING_ADAPT"
        elif reuse_safe is False:
            decision, reason = DECISION_ADAPT, "REUSE_SAFE_FALSE_ADAPT"
        else:
            decision, reason = DECISION_REUSE, "ROLE_SELECTION_PREVIEW_READY"

        source_authority = str(selected.get("source_authority") or "unknown")
        freshness = str(selected.get("freshness_status") or "unknown")
        permission = str(selected.get("permission_status") or permission_default)
        selected_sources = [selected]
        confidence = _number(selected.get("confidence"), _number(selected.get("score"), 0.5))
    else:
        if page.evidence_need and not allow_generate:
            decision, reason = DECISION_EVIDENCE, "NO_CANDIDATE_EVIDENCE"
        elif allow_generate:
            decision, reason = DECISION_GENERATE, "NO_CANDIDATE_GENERATE"
        else:
            decision, reason = DECISION_MANUAL, "NO_CANDIDATE_MANUAL"
        source_authority = "pending"
        freshness = "pending"
        permission = PERMISSION_NOT_REQUIRED
        selected_sources = []
        confidence = 0.3

    if permission == PERMISSION_BLOCKED:
        decision = DECISION_BLOCKED
        reason = "PERMISSION_BLOCKED"

    missing_evidence = list(page.evidence_need) if not selected_sources and page.evidence_need else []
    return {
        "page_id": page.page_id,
        "page_task_id": page.page_task_id,
        "order": int(page.order) if page.order.is_integer() else page.order,
        "page_title": page.title,
        "decision": decision,
        "reason": reason,
        "confidence": round(confidence, 4),
        "claim_ids": list(page.claim_ids),
        "evidence_need": list(page.evidence_need),
        "selected_sources": selected_sources,
        "source_authority": source_authority,
        "freshness_status": freshness,
        "permission_status": permission,
        "usage_constraints": _string_list(selected.get("usage_constraints") if selected else []),
        "missing_evidence": missing_evidence,
        "production_budget_class": _budget_for(decision),
        "role": page.role,
        "content_goal": page.content_goal,
        "generation_brief": page.generation_brief,
        "visual_need": page.visual_need,
        "workspace_refs": list(page.workspace_refs),
        "quality_requirements": list(page.quality_requirements),
        "expected_outputs": ["preview_path", "artifact_path"],
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
    pages_in = _extract_pages(page_tasks)
    library_results = library_results or {}
    allocation, warnings = _allocate_candidates(pages_in, library_results)
    pages = [
        _decide_for_page(
            page,
            allocation.get(page.page_id),
            permission_default=permission_default,
            allow_generate=allow_generate,
        )
        for page in pages_in
    ]

    coverage = _coverage(pages)
    approval_readiness = _approval_readiness(pages)
    status = "blocked" if approval_readiness["blocked_pages"] else (
        "awaiting_approval" if approval_readiness["ready"] else "draft"
    )
    source_fingerprint = _sha({
        "run_id": run_id,
        "pages": [
            {
                "page_id": p["page_id"],
                "decision": p["decision"],
                "asset_key": (p["selected_sources"][0].get("asset_key", "") if p.get("selected_sources") else ""),
                "query_trace_id": (p["selected_sources"][0].get("query_trace_id", "") if p.get("selected_sources") else ""),
            }
            for p in pages
        ],
        "library_source": library_results.get("library_source") or library_results.get("source") or "none",
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": status,
        "source_fingerprint": source_fingerprint,
        "pages": pages,
        "coverage": coverage,
        "approval_readiness": approval_readiness,
        "warnings": warnings,
        "created_at": _utc(now or _now()),
    }


def _coverage(pages: list[dict[str, Any]]) -> dict[str, Any]:
    by_decision: dict[str, int] = {}
    blocked = 0
    missing_evidence_pages = 0
    for page in pages:
        decision = str(page.get("decision") or "")
        by_decision[decision] = by_decision.get(decision, 0) + 1
        blocked += int(decision == DECISION_BLOCKED)
        missing_evidence_pages += int(bool(page.get("missing_evidence")))
    total = len(pages)
    return {
        "total_pages": total,
        "by_decision": by_decision,
        "blocked_pages": blocked,
        "missing_evidence_pages": missing_evidence_pages,
        "complete": total > 0 and blocked == 0 and missing_evidence_pages == 0,
    }


def _approval_readiness(pages: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = [page["page_id"] for page in pages if page.get("decision") == DECISION_BLOCKED]
    pending = [page["page_id"] for page in pages if page.get("permission_status") == PERMISSION_PENDING]
    missing = [page["page_id"] for page in pages if page.get("missing_evidence")]
    return {
        "ready": not blocked and not pending and not missing,
        "blocked_pages": blocked,
        "pending_permission_pages": pending,
        "missing_evidence_pages": missing,
    }


def _legacy_asset_key(candidate: dict[str, Any], run_id: str, page_id: str) -> str:
    if candidate.get("asset_key"):
        asset_key = str(candidate["asset_key"])
        if "/" not in asset_key and "\\" not in asset_key:
            return asset_key
    if candidate.get("slide_id"):
        return f"slide:{candidate['slide_id']}"
    if candidate.get("candidate_id"):
        return f"candidate:{candidate['candidate_id']}"
    return f"legacy:{_sha([run_id, page_id, candidate])}"


def migrate_v1(v1_plan: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy ``decisions[]`` to canonical v2 without writing files."""
    run_id = str(v1_plan.get("run_id") or "")
    decisions = v1_plan.get("decisions") if isinstance(v1_plan.get("decisions"), list) else []
    pages: list[dict[str, Any]] = []
    for index, legacy in enumerate(decisions):
        if not isinstance(legacy, dict):
            continue
        page_id = str(legacy.get("beat_id") or legacy.get("page_id") or f"page_{index + 1}")
        page_task_id = str(legacy.get("page_task_id") or page_id)
        legacy_decision = str(legacy.get("source_decision") or legacy.get("decision") or "").strip().lower()
        if legacy_decision == "manual_placeholder":
            decision = DECISION_MANUAL
        elif legacy_decision in ALL_DECISIONS:
            decision = legacy_decision
        else:
            decision = DECISION_MANUAL

        raw_selected = legacy.get("selected_candidate")
        selected: dict[str, Any] | None = None
        if isinstance(raw_selected, dict):
            migrated_candidate = dict(raw_selected)
            migrated_candidate["asset_key"] = _legacy_asset_key(raw_selected, run_id, page_id)
            migrated_candidate["query_trace_id"] = (
                raw_selected.get("query_trace_id")
                or legacy.get("query_trace_id")
                or _sha(["legacy-query", run_id, page_id])
            )
            page_input = PageInput(
                page_id=page_id,
                page_task_id=page_task_id,
                claim_ids=[],
                evidence_need=[],
                title="",
                order=float(index + 1),
                index=index,
                allow_repeat_source=False,
            )
            selected = _safe_selected_source(migrated_candidate, page_input, {})

        permission = PERMISSION_APPROVED if selected else PERMISSION_NOT_REQUIRED
        if decision == DECISION_BLOCKED:
            permission = PERMISSION_BLOCKED
        pages.append({
            "page_id": page_id,
            "page_task_id": page_task_id,
            "order": legacy.get("order", index + 1),
            "page_title": str(legacy.get("page_title") or ""),
            "decision": decision,
            "reason": str(legacy.get("decision_reason") or f"migrated from v1: {legacy_decision or 'unknown'}"),
            "confidence": _number((selected or {}).get("confidence"), _number(legacy.get("confidence"), 0.5)),
            "claim_ids": _string_list(legacy.get("claim_ids")),
            "evidence_need": _string_list(legacy.get("evidence_need")),
            "selected_sources": [selected] if selected else [],
            "source_authority": str((selected or {}).get("source_authority") or "unknown"),
            "freshness_status": str((selected or {}).get("freshness_status") or "unknown"),
            "permission_status": permission,
            "usage_constraints": _string_list((selected or {}).get("usage_constraints")),
            "missing_evidence": _string_list(legacy.get("missing_evidence")),
            "production_budget_class": _budget_for(decision),
            "generation_brief": str(legacy.get("generation_brief") or ""),
            "role": "",
            "content_goal": "",
            "visual_need": "",
            "workspace_refs": [],
            "quality_requirements": [],
            "expected_outputs": ["preview_path", "artifact_path"],
            "legacy_source_decision": legacy_decision,
        })

    coverage = _coverage(pages)
    approval_readiness = _approval_readiness(pages)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "blocked" if approval_readiness["blocked_pages"] else "draft",
        "source_fingerprint": _sha({"run_id": run_id, "v1": v1_plan.get("source", "")}),
        "pages": pages,
        "coverage": coverage,
        "approval_readiness": approval_readiness,
        "warnings": ["LEGACY_V1_MIGRATED"],
        "created_at": str(v1_plan.get("created_at") or _utc(_now())),
        "migrated_from": "deck_sourcing_plan.v1",
    }


__all__ = ["build_sourcing_plan_v2", "migrate_v1", "SCHEMA_VERSION", "ALL_DECISIONS"]
