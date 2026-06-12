"""Narrative Advisory Contract for Deck Master v0.9.

Implements:
- prepare_narrative_advice_task: generate task artifact for an external Agent.
- validate_narrative_advice: validate Agent-produced advice result.
- import_narrative_advice: store validated result in run.
- apply_narrative_advice: apply advice to page_tasks, claim graph, quality reports.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event
from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    PAGE_TASKS_NAME,
    RunStateError,
    ensure_run_dirs,
    read_json,
    write_json,
)

TASK_SCHEMA_VERSION = "deck_narrative_advice_task.v1"
RESULT_SCHEMA_VERSION = "deck_narrative_advice.v1"

TASK_DIR = "advisor_tasks"
RESULT_DIR = "advisor_results"
TASK_FILENAME = "narrative_advice_task.json"
RESULT_FILENAME = "narrative_advice.json"
DIFF_FILENAME = "narrative_advice_diff.json"

VALID_PAGE_ACTIONS = {
    "strengthen_claim",
    "add_evidence",
    "move_to_appendix",
    "convert_to_generate",
    "remove",
}


class NarrativeAdviceError(ValueError):
    """Raised when narrative advice is invalid or apply fails."""


# --------------------------------------------------------------------------- #
# Prepare task
# --------------------------------------------------------------------------- #


def prepare_narrative_advice_task(run_dir: str | Path) -> dict[str, Any]:
    """Generate a narrative advice task artifact for an external Agent."""
    root = ensure_run_dirs(run_dir)

    # Check required inputs exist.
    required = [DECK_BRIEF_NAME, CLAIM_MAP_NAME, PAGE_TASKS_NAME]
    missing = [f for f in required if not (root / f).exists()]
    if missing:
        raise NarrativeAdviceError(
            f"Cannot prepare narrative advice task: missing {', '.join(missing)}"
        )

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        request = read_json(request_path)
        run_id = str(request.get("run_id", ""))

    task: dict[str, Any] = {
        "schema_version": TASK_SCHEMA_VERSION,
        "run_id": run_id,
        "task_id": f"narrative_advice_{run_id or 'unknown'}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "request": "request.json",
            "deck_brief": DECK_BRIEF_NAME,
            "claim_map": CLAIM_MAP_NAME,
            "claim_evidence_graph": "claim_evidence_graph.json",
            "page_tasks": PAGE_TASKS_NAME,
            "quality_reports": "quality_reports/",
        },
        "instructions": [
            "识别客户真实业务矛盾。",
            "判断当前 Deck 主线是否成立。",
            "补充或改写 core thesis。",
            "提出 objection handling。",
            "指出哪些页面缺证据。",
            "建议哪些页面应该改为 appendix、generate、reuse 或补证据。",
        ],
        "output_schema": RESULT_SCHEMA_VERSION,
    }

    task_dir = root / TASK_DIR
    task_dir.mkdir(parents=True, exist_ok=True)
    write_json(task_dir / TASK_FILENAME, task)

    append_typed_event(
        root,
        "artifact_written",
        "narrative_advice_task.prepared",
        f"Narrative advice task prepared for run {run_id}.",
        run_id=run_id,
        refs=[f"{TASK_DIR}/{TASK_FILENAME}"],
    )

    return {"status": "prepared", "task_id": task["task_id"], "run_id": run_id}


# --------------------------------------------------------------------------- #
# Validate
# --------------------------------------------------------------------------- #


def validate_narrative_advice(result: dict[str, Any]) -> dict[str, Any]:
    """Validate narrative advice result against deck_narrative_advice.v1."""
    errors: list[str] = []

    if not isinstance(result, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}

    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{RESULT_SCHEMA_VERSION}', "
            f"got '{result.get('schema_version')}'."
        )

    if not result.get("run_id"):
        errors.append("run_id is required.")

    if not result.get("advisor"):
        errors.append("advisor is required.")

    # Validate page_recommendations.
    page_recs = result.get("page_recommendations", [])
    if not isinstance(page_recs, list):
        errors.append("page_recommendations must be an array.")
    else:
        for i, rec in enumerate(page_recs):
            if not isinstance(rec, dict):
                errors.append(f"page_recommendations[{i}] must be an object.")
                continue
            if not rec.get("beat_id"):
                errors.append(f"page_recommendations[{i}].beat_id is required.")
            action = rec.get("action", "")
            if action and action not in VALID_PAGE_ACTIONS:
                errors.append(
                    f"page_recommendations[{i}].action '{action}' "
                    f"must be one of {sorted(VALID_PAGE_ACTIONS)}."
                )

    # Validate deck_level_risks.
    risks = result.get("deck_level_risks", [])
    if not isinstance(risks, list):
        errors.append("deck_level_risks must be an array.")
    else:
        valid_severities = {"P0", "P1", "P2"}
        for i, risk in enumerate(risks):
            if not isinstance(risk, dict):
                errors.append(f"deck_level_risks[{i}] must be an object.")
                continue
            if not risk.get("risk_id"):
                errors.append(f"deck_level_risks[{i}].risk_id is required.")
            if not risk.get("message"):
                errors.append(f"deck_level_risks[{i}].message is required.")
            sev = risk.get("severity", "P2")
            if sev not in valid_severities:
                errors.append(
                    f"deck_level_risks[{i}].severity must be one of {sorted(valid_severities)}."
                )

    # Validate objection_map.
    objections = result.get("objection_map", [])
    if not isinstance(objections, list):
        errors.append("objection_map must be an array.")

    return {
        "valid": len(errors) == 0,
        "errors": errors if errors else [],
        "warnings": [],
    }


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def import_narrative_advice(
    run_dir: str | Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Validate and store narrative advice result."""
    validation = validate_narrative_advice(result)
    if not validation["valid"]:
        raise NarrativeAdviceError(
            "Invalid narrative advice: " + "; ".join(validation["errors"])
        )

    root = ensure_run_dirs(run_dir)
    results_dir = root / RESULT_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    write_json(results_dir / RESULT_FILENAME, result)

    run_id = str(result.get("run_id", ""))
    append_typed_event(
        root,
        "artifact_written",
        "narrative_advice.imported",
        f"Narrative advice imported from {result.get('advisor', 'unknown')}.",
        run_id=run_id,
        refs=[f"{RESULT_DIR}/{RESULT_FILENAME}"],
        payload={"advisor": result.get("advisor", "")},
    )

    return {
        "status": "imported",
        "advisor": result.get("advisor", ""),
        "run_id": run_id,
    }


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #


def _build_diff(
    page_tasks: dict[str, Any],
    claim_graph: dict[str, Any] | None,
    advice: dict[str, Any],
) -> dict[str, Any]:
    """Build a diff showing what apply would change."""
    diff: dict[str, Any] = {
        "page_task_changes": [],
        "claim_graph_gap_changes": [],
        "quality_report_added": "external_narrative_gate.json",
    }

    # Page task changes.
    beat_map = {
        t.get("beat_id"): i
        for i, t in enumerate(page_tasks.get("tasks", []))
        if isinstance(t, dict)
    }

    for rec in advice.get("page_recommendations", []):
        beat_id = rec.get("beat_id", "")
        if beat_id not in beat_map:
            continue
        idx = beat_map[beat_id]
        task = page_tasks["tasks"][idx]
        planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}

        change: dict[str, Any] = {"beat_id": beat_id, "old": {}, "new": {}}
        action = rec.get("action", "")

        # decision_intent change.
        old_intent = planning.get("decision_intent", "")
        if action and old_intent != action:
            change["old"]["decision_intent"] = old_intent
            change["new"]["decision_intent"] = action

        # core_claim change.
        new_claim = rec.get("suggested_core_claim", "")
        if action == "strengthen_claim" and new_claim:
            old_claim = planning.get("core_claim", "")
            if old_claim != new_claim:
                change["old"]["core_claim"] = old_claim
                change["new"]["core_claim"] = new_claim

        # evidence_need change.
        new_evidence = rec.get("evidence_needed", [])
        if new_evidence:
            old_evidence = planning.get("evidence_need", [])
            if old_evidence != new_evidence:
                change["old"]["evidence_need"] = old_evidence
                change["new"]["evidence_need"] = new_evidence

        if change["new"]:
            diff["page_task_changes"].append(change)

    # Claim graph gaps.
    risks = advice.get("deck_level_risks", [])
    if risks and claim_graph is not None:
        old_gaps = claim_graph.get("gaps", [])
        new_gaps = [
            {
                "gap_id": f"narrative_{r.get('risk_id', '')}",
                "claim_id": "",
                "description": r.get("message", ""),
                "severity": r.get("severity", "P2"),
                "source": "narrative_advice",
            }
            for r in risks
        ]
        diff["claim_graph_gap_changes"] = {
            "old_gaps_count": len(old_gaps),
            "new_gaps_to_add": new_gaps,
        }

    return diff


def apply_narrative_advice(
    run_dir: str | Path,
    result: dict[str, Any],
    *,
    dry_run: bool = False,
    apply_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Apply narrative advice to run artifacts.

    Args:
        run_dir: Run directory.
        result: Narrative advice result dict.
        dry_run: If True, only write diff, do not modify artifacts.
        apply_sections: Optional list of sections to apply:
            'core-thesis', 'page-recommendations', 'risks'.
            Defaults to all sections.
    """
    validation = validate_narrative_advice(result)
    if not validation["valid"]:
        raise NarrativeAdviceError(
            "Invalid narrative advice: " + "; ".join(validation["errors"])
        )

    root = ensure_run_dirs(run_dir)
    run_id = str(result.get("run_id", ""))

    # Load artifacts.
    try:
        page_tasks = read_json(root / PAGE_TASKS_NAME)
    except RunStateError as exc:
        raise NarrativeAdviceError(f"Cannot read page_tasks.json: {exc}") from exc

    claim_graph_path = root / "claim_evidence_graph.json"
    claim_graph = None
    if claim_graph_path.exists():
        try:
            claim_graph = read_json(claim_graph_path)
        except RunStateError:
            claim_graph = None

    # Build diff.
    diff = _build_diff(page_tasks, claim_graph, result)
    diff["dry_run"] = dry_run
    diff["applied_sections"] = apply_sections or ["core-thesis", "page-recommendations", "risks"]

    # Write diff.
    results_dir = root / RESULT_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    write_json(results_dir / DIFF_FILENAME, diff)

    if dry_run:
        append_typed_event(
            root,
            "artifact_written",
            "narrative_advice.dry_run",
            "Narrative advice dry-run: diff generated, no artifacts modified.",
            run_id=run_id,
            refs=[f"{RESULT_DIR}/{DIFF_FILENAME}"],
        )
        return {"status": "dry_run", "diff": f"{RESULT_DIR}/{DIFF_FILENAME}", "changes": len(diff["page_task_changes"])}

    sections = set(apply_sections) if apply_sections else {"core-thesis", "page-recommendations", "risks"}
    applied: list[str] = []

    # Apply page recommendations.
    if "page-recommendations" in sections:
        beat_map = {
            t.get("beat_id"): i
            for i, t in enumerate(page_tasks.get("tasks", []))
            if isinstance(t, dict)
        }
        for rec in result.get("page_recommendations", []):
            beat_id = rec.get("beat_id", "")
            if beat_id not in beat_map:
                continue
            idx = beat_map[beat_id]
            task = page_tasks["tasks"][idx]
            planning = task.get("planning", {})
            if not isinstance(planning, dict):
                planning = {}
                task["planning"] = planning

            action = rec.get("action", "")
            if action:
                planning["decision_intent"] = action

            new_claim = rec.get("suggested_core_claim", "")
            if action == "strengthen_claim" and new_claim:
                planning["core_claim"] = new_claim

            new_evidence = rec.get("evidence_needed", [])
            if new_evidence:
                planning["evidence_need"] = new_evidence

            applied.append(beat_id)

        write_json(root / PAGE_TASKS_NAME, page_tasks)

    # Apply risks to claim graph gaps.
    if "risks" in sections and claim_graph is not None:
        risks = result.get("deck_level_risks", [])
        if risks:
            existing_gaps = claim_graph.get("gaps", [])
            for risk in risks:
                gap = {
                    "gap_id": f"narrative_{risk.get('risk_id', '')}",
                    "claim_id": "",
                    "description": risk.get("message", ""),
                    "severity": risk.get("severity", "P2"),
                    "source": "narrative_advice",
                }
                existing_gaps.append(gap)
            claim_graph["gaps"] = existing_gaps
            write_json(claim_graph_path, claim_graph)
            applied.append("claim_evidence_graph.gaps")

    # Write external narrative gate quality report.
    quality_reports_dir = root / "quality_reports"
    quality_reports_dir.mkdir(parents=True, exist_ok=True)
    deck_risks = result.get("deck_level_risks", [])
    p0_count = sum(1 for r in deck_risks if r.get("severity") == "P0")
    p1_count = sum(1 for r in deck_risks if r.get("severity") == "P1")
    p2_count = sum(1 for r in deck_risks if r.get("severity") == "P2")
    status = "pass" if (p0_count + p1_count) == 0 else "rework_required"

    narrative_gate = {
        "schema_version": "deck_quality_report.v1",
        "gate": "external_narrative",
        "run_id": run_id,
        "source": "narrative_advice",
        "advisor": result.get("advisor", ""),
        "status": status,
        "blocks_delivery": p0_count > 0,
        "summary": {
            "p0_count": p0_count,
            "p1_count": p1_count,
            "p2_count": p2_count,
        },
        "findings": [
            {
                "finding_id": f"narrative_{r.get('risk_id', '')}",
                "severity": r.get("severity", "P2"),
                "message": r.get("message", ""),
            }
            for r in deck_risks
        ],
    }
    write_json(quality_reports_dir / "external_narrative_gate.json", narrative_gate)

    append_typed_event(
        root,
        "artifact_written",
        "narrative_advice.applied",
        f"Narrative advice applied: {len(applied)} artifacts updated.",
        run_id=run_id,
        refs=[
            PAGE_TASKS_NAME,
            "claim_evidence_graph.json",
            "quality_reports/external_narrative_gate.json",
            f"{RESULT_DIR}/{DIFF_FILENAME}",
        ],
        payload={"applied": applied},
    )

    return {
        "status": "applied",
        "applied": applied,
        "diff": f"{RESULT_DIR}/{DIFF_FILENAME}",
    }
