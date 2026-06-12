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
    RunStateError,
    read_json,
)


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


def compute_deck_readiness(run_dir: Path) -> dict[str, Any]:
    """Compute deck readiness panel data."""
    page_tasks = _safe_read(run_dir / PAGE_TASKS_NAME) or {}
    preview = _safe_read(run_dir / PREVIEW_MANIFEST_NAME) or {}
    claim_graph = _safe_read(run_dir / "claim_evidence_graph.json") or {}

    tasks = page_tasks.get("tasks", [])
    pages = preview.get("pages", [])

    # Page counts.
    total = len(tasks)
    approved = sum(1 for t in tasks if isinstance(t, dict) and t.get("review_status") == "approved")
    rejected = sum(1 for t in tasks if isinstance(t, dict) and t.get("review_status") == "rejected")
    needs_review = total - approved - rejected

    # Source decision counts.
    source_counts: dict[str, int] = {}
    for t in tasks:
        if not isinstance(t, dict):
            continue
        sd = t.get("source_decision", t.get("planning", {}).get("decision_intent", "unknown"))
        source_counts[sd] = source_counts.get(sd, 0) + 1

    # Quality findings.
    quality_dir = run_dir / "quality_reports"
    p0_total = 0
    p1_total = 0
    p2_total = 0
    if quality_dir.exists():
        for gate_file in quality_dir.glob("*_gate.json"):
            report = _safe_read(gate_file)
            if not report:
                continue
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
    quality = "blocked" if p0_total > 0 else ("conditional_pass" if p1_total > 0 else "pass")
    generation_status = "pending"
    gen_tasks_dir = run_dir / "generation_tasks"
    if gen_tasks_dir.exists():
        gen_index = _safe_read(gen_tasks_dir / "index.json")
        if gen_index:
            task_ids = gen_index.get("task_ids", [])
            completed = 0
            for tid in task_ids:
                task = _safe_read(gen_tasks_dir / f"{tid}.json")
                if task and task.get("status") == "completed":
                    completed += 1
            if completed == len(task_ids) and task_ids:
                generation_status = "completed"
            elif completed > 0:
                generation_status = "partial"

    export_ready = (
        evidence == "pass"
        and quality == "pass"
        and approved > 0
    )
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
            "quality": quality,
            "export": "ready" if export_ready else "blocked",
        },
        "counts": {
            "pages": total,
            "approved": approved,
            "needs_review": needs_review,
            "rejected": rejected,
            "reuse": source_counts.get("reuse", 0),
            "adapt": source_counts.get("adapt", 0),
            "generate": source_counts.get("generate", 0),
            "manual_placeholder": source_counts.get("manual_placeholder", 0),
            "p0": p0_total,
            "p1": p1_total,
            "p2": p2_total,
        },
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
            actions.append({
                "priority": priority,
                "action_type": "resolve_placeholder",
                "target": task.get("beat_id", ""),
                "message": f"Page {task.get('beat_id', '')} requires human expert input.",
                "refs": [PAGE_TASKS_NAME],
            })

    # 4. Generation failed.
    gen_tasks_dir = run_dir / "generation_tasks"
    if gen_tasks_dir.exists():
        gen_index = _safe_read(gen_tasks_dir / "index.json")
        if gen_index:
            for tid in gen_index.get("task_ids", []):
                task = _safe_read(gen_tasks_dir / f"{tid}.json")
                if task and task.get("status") == "failed":
                    priority += 1
                    actions.append({
                        "priority": priority,
                        "action_type": "rerun_generation",
                        "target": task.get("beat_id", ""),
                        "message": f"Generation failed for {task.get('beat_id', '')}.",
                        "refs": [f"generation_tasks/{tid}.json"],
                    })

    # 5. No preview asset.
    for page in pages:
        if not isinstance(page, dict):
            continue
        if not page.get("preview_image") and page.get("source_type") != "placeholder":
            priority += 1
            actions.append({
                "priority": priority,
                "action_type": "generate_preview",
                "target": page.get("beat_id", ""),
                "message": f"No preview for {page.get('beat_id', '')}.",
                "refs": [PREVIEW_MANIFEST_NAME],
            })

    # 6. Uncovered claims.
    coverage = compute_claim_coverage(run_dir)
    for claim in coverage.get("claims", []):
        if claim.get("status") in ("uncovered", "evidence_gap"):
            priority += 1
            actions.append({
                "priority": priority,
                "action_type": "fix_claim_coverage",
                "target": claim.get("claim_id", ""),
                "message": f"Claim '{claim.get('statement', '')[:60]}' has status: {claim.get('status')}.",
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
