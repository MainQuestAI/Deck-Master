"""Review Cockpit F1 — Read-only APIs for Deck Master v0.9.

Provides:
- deck_readiness: overall deck readiness status.
- claim_coverage: claim coverage matrix.
- next_actions: prioritised next 5 actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.run_state import (
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    read_json,
)
from runtime.render import CANONICAL_RENDER_RESULT, LEGACY_RENDER_RESULTS
from runtime.run_state_resolver import _draft_gate_blocks, _fresh_draft_gate_for_generation, _pick_first_draft_gate
from sourcing.reader import read_sourcing_plan


def _safe_read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except RunStateError:
        return None


# --------------------------------------------------------------------------- #
# Deck Readiness
# --------------------------------------------------------------------------- #


def _review_status_from_page(page: dict[str, Any]) -> str:
    status = str(page.get("review_status", ""))
    if status:
        return status
    decision = str(page.get("decision", "needs_review"))
    if decision in {"approved", "keep"}:
        return "approved"
    if decision == "rejected":
        return "rejected"
    return "needs_review"


def summarize_sourcing_readiness(
    run_dir: Path,
    *,
    fallback_tasks: list[Any] | None = None,
) -> dict[str, Any]:
    """Summarize canonical Sourcing v2 plus safe Library selection signals."""
    pages: list[dict[str, Any]] = []
    sourcing_path = run_dir / SOURCING_PLAN_NAME
    if sourcing_path.exists():
        try:
            canonical = read_sourcing_plan(sourcing_path)
        except (OSError, ValueError):
            canonical = {}
        raw_pages = canonical.get("pages", []) if isinstance(canonical, dict) else []
        pages = [page for page in raw_pages if isinstance(page, dict)]

    if not pages:
        for index, task in enumerate(fallback_tasks or []):
            if not isinstance(task, dict):
                continue
            planning = task.get("planning") if isinstance(task.get("planning"), dict) else {}
            raw_decision = str(
                task.get("source_decision") or planning.get("decision_intent") or "unknown"
            )
            decision = "manual" if raw_decision == "manual_placeholder" else raw_decision
            page_id = str(task.get("page_id") or task.get("beat_id") or f"page_{index + 1}")
            pages.append(
                {
                    "page_id": page_id,
                    "page_task_id": str(task.get("page_task_id") or page_id),
                    "decision": decision,
                }
            )

    decision_counts: dict[str, int] = {}
    for page in pages:
        decision = str(page.get("decision") or "unknown")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    selection = _safe_read(run_dir / "library_results" / "selection.json") or {}
    raw_selections = selection.get("selections", [])
    selection_by_identity: dict[str, dict[str, Any]] = {}
    if isinstance(raw_selections, list):
        for item in raw_selections:
            if not isinstance(item, dict):
                continue
            for identity in (item.get("beat_id"), item.get("page_task_id")):
                key = str(identity or "").strip()
                if key and key not in selection_by_identity:
                    selection_by_identity[key] = item

    role_selection_count = 0
    semantic_fallback_count = 0
    preview_degradation_count = 0
    for page in pages:
        selection_item = selection_by_identity.get(str(page.get("page_id") or ""))
        if selection_item is None:
            selection_item = selection_by_identity.get(str(page.get("page_task_id") or ""))
        if selection_item is None:
            continue
        retrieval_method = str(selection_item.get("retrieval_method") or "")
        role_selection_count += int(retrieval_method == "role_selection")
        semantic_fallback_count += int(retrieval_method == "semantic_fallback")
        preview_degradation_count += int(bool(selection_item.get("preview_degraded")))

    generate_gap_count = decision_counts.get("generate", 0)
    if not pages:
        status = "pending"
    elif semantic_fallback_count or preview_degradation_count or generate_gap_count:
        status = "degraded"
    else:
        status = "ready"
    return {
        "status": status,
        "total_pages": len(pages),
        "role_selection_count": role_selection_count,
        "semantic_fallback_count": semantic_fallback_count,
        "preview_degradation_count": preview_degradation_count,
        "generate_gap_count": generate_gap_count,
        "decision_counts": decision_counts,
    }


def _generation_tasks_from_index(run_dir: Path, gen_index: dict[str, Any]) -> list[dict[str, Any]]:
    raw_tasks = gen_index.get("tasks", [])
    if isinstance(raw_tasks, list) and raw_tasks and isinstance(raw_tasks[0], dict):
        return [task for task in raw_tasks if isinstance(task, dict)]

    task_ids = gen_index.get("task_ids", raw_tasks if isinstance(raw_tasks, list) else [])
    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        if not isinstance(task_id, str):
            continue
        task = _safe_read(run_dir / "generation_tasks" / f"{task_id}.json")
        if task:
            tasks.append(task)
    return tasks


def compute_deck_readiness(run_dir: Path) -> dict[str, Any]:
    """Compute deck readiness panel data."""
    page_tasks = _safe_read(run_dir / PAGE_TASKS_NAME) or {}
    preview = _safe_read(run_dir / PREVIEW_MANIFEST_NAME) or {}
    claim_graph = _safe_read(run_dir / "claim_evidence_graph.json") or {}

    tasks = page_tasks.get("tasks", [])
    pages = preview.get("pages", [])

    # Page counts.
    page_source = pages if pages else tasks
    total = len(page_source)
    approved = sum(1 for p in page_source if isinstance(p, dict) and _review_status_from_page(p) == "approved")
    rejected = sum(1 for p in page_source if isinstance(p, dict) and _review_status_from_page(p) == "rejected")
    needs_review = total - approved - rejected

    # Source decision counts.
    sourcing_readiness = summarize_sourcing_readiness(run_dir, fallback_tasks=tasks)
    source_counts = sourcing_readiness["decision_counts"]

    # Quality findings.
    quality_dir = run_dir / "quality_reports"
    p0_total = 0
    p1_total = 0
    p2_total = 0
    quality_blocks_delivery = False
    if quality_dir.exists():
        for gate_file in quality_dir.glob("*_gate.json"):
            report = _safe_read(gate_file)
            if not report:
                continue
            if report.get("blocks_delivery"):
                quality_blocks_delivery = True
            summary = report.get("summary", {})
            p0_total += summary.get("p0_count", 0)
            p1_total += summary.get("p1_count", 0)
            p2_total += summary.get("p2_count", 0)
            # Also count from findings array.
            for f in report.get("findings", []):
                if not isinstance(f, dict):
                    continue
                sev = f.get("severity", "")
                if sev == "P0" and summary.get("p0_count") is None:
                    p0_total += 1
                elif sev == "P1" and summary.get("p1_count") is None:
                    p1_total += 1
                elif sev == "P2" and summary.get("p2_count") is None:
                    p2_total += 1

    # Readiness dimensions.
    narrative = "pass" if (run_dir / "deck_brief.json").exists() else "pending"
    evidence = "blocked" if p0_total > 0 else ("conditional_pass" if p1_total > 0 else "pass")
    quality = "blocked" if (p0_total > 0 or quality_blocks_delivery) else ("conditional_pass" if p1_total > 0 else "pass")
    generation_status = "pending"
    generation_required = False
    generation_quality_ready = True
    render_required = False
    render_ready = True
    blocking_reasons: list[str] = []
    gen_tasks_dir = run_dir / "generation_tasks"
    if gen_tasks_dir.exists():
        gen_index = _safe_read(gen_tasks_dir / "index.json")
        if gen_index:
            generation_tasks = _generation_tasks_from_index(run_dir, gen_index)
            generation_required = bool(generation_tasks)
            completed = sum(1 for task in generation_tasks if task.get("status") == "completed")
            if completed == len(generation_tasks) and generation_tasks:
                generation_status = "completed"
            elif completed > 0:
                generation_status = "partial"
            session = _safe_read(run_dir / "generation_session.json") or {}
            session_status = str(session.get("status") or "").strip().lower()
            if session_status:
                generation_status = session_status
            render_required = generation_required
            render_ready = (run_dir / CANONICAL_RENDER_RESULT).exists() or any((run_dir / path).exists() for path in LEGACY_RENDER_RESULTS)
            if session_status == "quality_required":
                generation_quality_ready, freshness_reason = _fresh_draft_gate_for_generation(run_dir, session)
                if freshness_reason:
                    blocking_reasons.append(freshness_reason)
            elif session_status == "preview_refreshed":
                gate = _pick_first_draft_gate(run_dir)
                generation_quality_ready, freshness_reason = _draft_gate_blocks(gate)
                generation_quality_ready = not generation_quality_ready
                if freshness_reason:
                    blocking_reasons.append(freshness_reason)
            else:
                generation_quality_ready = False
                blocking_reasons.append(f"generation session status is {session_status or 'missing'}")
            if not render_ready:
                blocking_reasons.append("render result is missing")

    if approved <= 0:
        blocking_reasons.append("no approved pages")
    if needs_review > 0:
        blocking_reasons.append("pages still need review")
    if evidence == "blocked":
        blocking_reasons.append("evidence gate is blocked")
    if quality == "blocked":
        blocking_reasons.append("quality gate blocks delivery")

    export_ready = evidence == "pass" and quality == "pass" and approved > 0
    if generation_required:
        export_ready = export_ready and generation_quality_ready and render_ready
    overall = (
        "ready" if export_ready
        else "blocked" if (p0_total > 0 or evidence == "blocked")
        else "needs_review"
    )

    return {
        "run_id": _get_run_id(run_dir),
        "deck_readiness": {
            "overall": overall,
            "narrative": narrative,
            "evidence": evidence,
            "generation": generation_status,
            "generation_required": generation_required,
            "generation_quality_ready": generation_quality_ready,
            "render": "ready" if render_ready else "blocked",
            "render_required": render_required,
            "quality": quality,
            "export": "ready" if export_ready else "blocked",
            "blocking_reasons": sorted(set(reason for reason in blocking_reasons if reason)),
        },
        "counts": {
            "pages": total,
            "approved": approved,
            "needs_review": needs_review,
            "rejected": rejected,
            "reuse": source_counts.get("reuse", 0),
            "adapt": source_counts.get("adapt", 0),
            "generate": source_counts.get("generate", 0),
            "manual_placeholder": source_counts.get("manual", 0),
            "p0": p0_total,
            "p1": p1_total,
            "p2": p2_total,
        },
        "sourcing_readiness": sourcing_readiness,
    }


# --------------------------------------------------------------------------- #
# Claim Coverage
# --------------------------------------------------------------------------- #


def compute_claim_coverage(run_dir: Path) -> dict[str, Any]:
    """Compute claim coverage matrix."""
    claim_map = _safe_read(run_dir / "claim_map.json") or {}
    claim_graph = _safe_read(run_dir / "claim_evidence_graph.json") or {}
    page_tasks = _safe_read(run_dir / PAGE_TASKS_NAME) or {}

    raw_claims = claim_map.get("claims", [])
    graph_claims = claim_graph.get("claims", [])
    graph_evidence = claim_graph.get("evidence", [])
    tasks = page_tasks.get("tasks", [])

    # Build evidence_id -> evidence map.
    ev_map = {e.get("evidence_id"): e for e in graph_evidence if isinstance(e, dict)}

    # Build beat -> claim mapping from page_tasks.
    beat_to_claims: dict[str, list[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        planning = task.get("planning", {})
        beat_id = task.get("beat_id", "")
        core_claim = planning.get("core_claim", "") if isinstance(planning, dict) else ""
        if core_claim and beat_id:
            for gc in graph_claims:
                if isinstance(gc, dict) and core_claim in gc.get("statement", ""):
                    beat_to_claims.setdefault(beat_id, []).append(gc.get("claim_id", ""))

    claims_out: list[dict[str, Any]] = []
    for gc in graph_claims:
        if not isinstance(gc, dict):
            continue
        claim_id = gc.get("claim_id", "")
        statement = gc.get("statement", "")
        evidence_ids = gc.get("supporting_evidence", [])
        page_refs = gc.get("page_refs", [])

        # Determine status.
        has_pages = bool(page_refs)
        has_evidence = bool(evidence_ids)
        if has_pages and has_evidence:
            status = "covered"
        elif has_pages and not has_evidence:
            status = "evidence_gap"
        elif not has_pages and has_evidence:
            status = "review_required"
        else:
            status = "uncovered"

        # Check if any evidence is blocked.
        for eid in evidence_ids:
            ev = ev_map.get(eid, {})
            if ev.get("publication_status") == "needs_redaction":
                status = "blocked"
                break

        claims_out.append({
            "claim_id": claim_id,
            "statement": statement,
            "pages": page_refs,
            "evidence": evidence_ids,
            "status": status,
        })

    return {"run_id": _get_run_id(run_dir), "claims": claims_out}


# --------------------------------------------------------------------------- #
# Next Actions
# --------------------------------------------------------------------------- #


def compute_next_actions(run_dir: Path) -> dict[str, Any]:
    """Compute prioritised next 5 actions."""
    page_tasks = _safe_read(run_dir / PAGE_TASKS_NAME) or {}
    claim_graph = _safe_read(run_dir / "claim_evidence_graph.json") or {}
    preview = _safe_read(run_dir / PREVIEW_MANIFEST_NAME) or {}

    tasks = page_tasks.get("tasks", [])
    gaps = claim_graph.get("gaps", [])
    pages = preview.get("pages", [])
    page_title_by_id = {
        str(page.get("page_id") or page.get("beat_id") or ""): str(page.get("title") or page.get("page_id") or "")
        for page in pages
        if isinstance(page, dict)
    }

    actions: list[dict[str, Any]] = []
    priority = 0

    # 1. P0/P1 quality findings.
    quality_dir = run_dir / "quality_reports"
    if quality_dir.exists():
        for gate_file in sorted(quality_dir.glob("*_gate.json")):
            report = _safe_read(gate_file)
            if not report:
                continue
            for f in report.get("findings", []):
                if not isinstance(f, dict):
                    continue
                sev = f.get("severity", "P2")
                if sev in ("P0", "P1"):
                    priority += 1
                    actions.append({
                        "priority": priority,
                        "action_type": "fix_quality_finding",
                        "target": f.get("page_id", ""),
                        "message": f.get("message", ""),
                        "severity": sev,
                        "refs": [f"quality_reports/{gate_file.name}"],
                    })

    # 2. Evidence gaps.
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        priority += 1
        actions.append({
            "priority": priority,
            "action_type": "fix_evidence_gap",
            "target": gap.get("claim_id", ""),
            "message": gap.get("description", ""),
            "refs": ["claim_evidence_graph.json"],
        })

    # 3. Manual placeholders.
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sd = task.get("source_decision", task.get("planning", {}).get("decision_intent", ""))
        if sd == "manual_placeholder":
            priority += 1
            page_id = str(task.get("beat_id", ""))
            page_title = page_title_by_id.get(page_id, page_id or "当前页面")
            actions.append({
                "priority": priority,
                "action_type": "resolve_placeholder",
                "target": page_id,
                "message": f"{page_title} 仍需负责人补充判断。",
                "refs": [PAGE_TASKS_NAME],
            })

    # 4. Generation failed.
    gen_tasks_dir = run_dir / "generation_tasks"
    if gen_tasks_dir.exists():
        gen_index = _safe_read(gen_tasks_dir / "index.json")
        if gen_index:
            for task in _generation_tasks_from_index(run_dir, gen_index):
                if task.get("status") == "failed":
                    priority += 1
                    page_id = str(task.get("beat_id", ""))
                    page_title = page_title_by_id.get(page_id, page_id or "当前页面")
                    actions.append({
                        "priority": priority,
                        "action_type": "rerun_generation",
                        "target": page_id,
                        "message": f"{page_title} 的内容生成失败，需要重新处理。",
                        "refs": [f"generation_tasks/{task.get('task_id', '')}.json"],
                    })

    # 5. No preview asset.
    for page in pages:
        if not isinstance(page, dict):
            continue
        if not page.get("preview_path") and page.get("source_type") != "placeholder":
            priority += 1
            page_id = str(page.get("beat_id") or page.get("page_id") or "")
            page_title = page_title_by_id.get(page_id, page_id or "当前页面")
            actions.append({
                "priority": priority,
                "action_type": "generate_preview",
                "target": page_id,
                "message": f"{page_title} 还没有可审预览。",
                "refs": [PREVIEW_MANIFEST_NAME],
            })

    # 6. Uncovered claims.
    coverage = compute_claim_coverage(run_dir)
    for claim in coverage.get("claims", []):
        if claim.get("status") in ("uncovered", "evidence_gap"):
            priority += 1
            statement = str(claim.get("statement", "")).strip() or str(claim.get("claim_id", "")).strip() or "当前论点"
            actions.append({
                "priority": priority,
                "action_type": "fix_claim_coverage",
                "target": claim.get("claim_id", ""),
                "message": f"{statement} 仍缺少完整依据支撑。",
                "refs": ["claim_evidence_graph.json"],
            })

    # Sort by priority and return top 5.
    actions.sort(key=lambda a: a["priority"])
    for i, a in enumerate(actions[:5], start=1):
        a["priority"] = i

    return {"run_id": _get_run_id(run_dir), "actions": actions[:5]}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _get_run_id(run_dir: Path) -> str:
    req = _safe_read(run_dir / "request.json")
    if req:
        return str(req.get("run_id", ""))
    return run_dir.name
