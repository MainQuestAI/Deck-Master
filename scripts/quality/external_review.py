"""External Quality Review Contract for Deck Master v0.9.

Implements:
- prepare_quality_review: generate review task for external Agent.
- validate_external_review: validate review result.
- import_external_review: import as quality gate report.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event
from runtime.run_state import (
    DECK_BRIEF_NAME,
    PAGE_TASKS_NAME,
    RunStateError,
    ensure_run_dirs,
    read_json,
    write_json,
)

TASK_SCHEMA_VERSION = "deck_external_quality_review_task.v1"
RESULT_SCHEMA_VERSION = "deck_external_quality_review.v1"

TASK_DIR = "quality_review_tasks"
VALID_SCOPES = {"semantic", "visual", "evidence", "client-readiness"}
VALID_SEVERITIES = {"P0", "P1", "P2"}
VALID_STATUSES = {"pass", "conditional_pass", "rework_required"}


class ExternalReviewError(ValueError):
    """Raised when external review is invalid or import fails."""


# --------------------------------------------------------------------------- #
# Prepare task
# --------------------------------------------------------------------------- #


def _scope_to_task_filename(scope: str) -> str:
    return f"{scope.replace('-', '_')}_review_task.json"


def _scope_to_gate_filename(scope: str) -> str:
    return f"external_{scope.replace('-', '_')}_gate.json"


def prepare_quality_review(
    run_dir: str | Path,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    """Generate external quality review task artifacts."""
    root = ensure_run_dirs(run_dir)

    # Check required inputs.
    required = [DECK_BRIEF_NAME, PAGE_TASKS_NAME]
    missing = [f for f in required if not (root / f).exists()]
    if missing:
        raise ExternalReviewError(
            f"Cannot prepare quality review task: missing {', '.join(missing)}"
        )

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        request = read_json(request_path)
        run_id = str(request.get("run_id", ""))

    if not scopes:
        scopes = ["semantic"]

    invalid = [s for s in scopes if s not in VALID_SCOPES]
    if invalid:
        raise ExternalReviewError(
            f"Invalid scopes: {invalid}. Valid: {sorted(VALID_SCOPES)}"
        )

    task_dir = root / TASK_DIR
    task_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    for scope in scopes:
        task: dict[str, Any] = {
            "schema_version": TASK_SCHEMA_VERSION,
            "run_id": run_id,
            "task_id": f"{scope.replace('-', '_')}_review_{run_id or 'unknown'}",
            "scope": scope,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inputs": {
                "deck_brief": DECK_BRIEF_NAME,
                "claim_evidence_graph": "claim_evidence_graph.json",
                "page_tasks": PAGE_TASKS_NAME,
                "preview_manifest": "preview_manifest.json",
                "quality_reports": "quality_reports/",
            },
            "review_dimensions": [
                "claim_evidence_alignment",
                "consulting_style_expression",
                "client_readability",
                "page_job_clarity",
                "decision_readiness",
            ],
            "output_schema": RESULT_SCHEMA_VERSION,
        }
        write_json(task_dir / _scope_to_task_filename(scope), task)
        created.append(scope)

    append_typed_event(
        root,
        "artifact_written",
        "quality_review_task.prepared",
        f"External quality review tasks prepared for scopes: {created}.",
        run_id=run_id,
        refs=[f"{TASK_DIR}/{_scope_to_task_filename(s)}" for s in created],
        payload={"scopes": created},
    )

    return {"status": "prepared", "scopes": created, "run_id": run_id}


# --------------------------------------------------------------------------- #
# Validate
# --------------------------------------------------------------------------- #


def validate_external_review(result: dict[str, Any]) -> dict[str, Any]:
    """Validate external quality review result."""
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
    if not result.get("reviewer"):
        errors.append("reviewer is required.")
    if not result.get("scope"):
        errors.append("scope is required.")
    elif result["scope"] not in VALID_SCOPES:
        errors.append(f"scope must be one of {sorted(VALID_SCOPES)}.")

    findings = result.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array.")
    else:
        for i, f in enumerate(findings):
            if not isinstance(f, dict):
                errors.append(f"findings[{i}] must be an object.")
                continue
            if not f.get("finding_id"):
                errors.append(f"findings[{i}].finding_id is required.")
            if not f.get("message"):
                errors.append(f"findings[{i}].message is required.")
            sev = f.get("severity", "P2")
            if sev not in VALID_SEVERITIES:
                errors.append(
                    f"findings[{i}].severity must be one of {sorted(VALID_SEVERITIES)}."
                )

    # Validate summary if present.
    summary = result.get("summary", {})
    if summary and isinstance(summary, dict):
        status = summary.get("status", "")
        if status and status not in VALID_STATUSES:
            errors.append(f"summary.status must be one of {sorted(VALID_STATUSES)}.")

    return {
        "valid": len(errors) == 0,
        "errors": errors if errors else [],
        "warnings": [],
    }


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def _gate_filename(scope: str, reviewer: str) -> str:
    """Build gate filename: external_<scope>_<reviewer>_gate.json."""
    safe_scope = scope.replace("-", "_")
    safe_reviewer = reviewer.replace("-", "_").replace(" ", "_")[:20]
    return f"external_{safe_scope}_{safe_reviewer}_gate.json"


def import_external_review(
    run_dir: str | Path,
    result: dict[str, Any],
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """Import external quality review as a quality gate report."""
    validation = validate_external_review(result)
    if not validation["valid"]:
        raise ExternalReviewError(
            "Invalid external review: " + "; ".join(validation["errors"])
        )

    root = ensure_run_dirs(run_dir)
    run_id = str(result.get("run_id", ""))
    scope = str(result.get("scope", ""))
    reviewer = str(result.get("reviewer", ""))

    quality_dir = root / "quality_reports"
    quality_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = quality_dir / "archive"

    gate_name = _gate_filename(scope, reviewer)
    gate_path = quality_dir / gate_name

    # Archive existing if replacing.
    if gate_path.exists():
        if not replace:
            raise ExternalReviewError(
                f"Report {gate_name} already exists. Use --replace to overwrite. "
                "Old report preserved in archive."
            )
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        archived = archive_dir / f"{stamp}_{gate_name}"
        shutil.copy2(gate_path, archived)

    # Build quality gate report.
    findings = result.get("findings", [])
    p0_count = sum(1 for f in findings if f.get("severity") == "P0")
    p1_count = sum(1 for f in findings if f.get("severity") == "P1")
    p2_count = sum(1 for f in findings if f.get("severity") == "P2")

    # Derive status and blocks_delivery from findings — never trust external summary.
    # An attacker or buggy Agent could send status=pass with P0/P1 findings to bypass
    # export blocking. We compute ground truth from the findings array.
    if p0_count > 0:
        status = "rework_required"
        blocks_delivery = True
    elif p1_count > 0:
        status = "rework_required"
        blocks_delivery = True
    else:
        status = "pass"
        blocks_delivery = False

    gate_report: dict[str, Any] = {
        "schema_version": "deck_quality_report.v1",
        "gate": f"external_{scope.replace('-', '_')}",
        "run_id": run_id,
        "reviewer": reviewer,
        "scope": scope,
        "status": status,
        "blocks_delivery": blocks_delivery,
        "summary": {
            "p0_count": p0_count,
            "p1_count": p1_count,
            "p2_count": p2_count,
        },
        "findings": [
            {
                "finding_id": f.get("finding_id", ""),
                "severity": f.get("severity", "P2"),
                "page_id": f.get("page_id", ""),
                "dimension": f.get("dimension", ""),
                "message": f.get("message", ""),
                "repair_instruction": f.get("repair_instruction", ""),
                "refs": f.get("refs", []),
                "source": "external_review",
                "reviewer": reviewer,
            }
            for f in findings
        ],
    }

    write_json(gate_path, gate_report)

    append_typed_event(
        root,
        "artifact_written",
        "external_quality_review.imported",
        f"External {scope} review from {reviewer} imported: "
        f"{p0_count} P0, {p1_count} P1, {p2_count} P2.",
        run_id=run_id,
        refs=[f"quality_reports/{gate_name}"],
        payload={
            "scope": scope,
            "reviewer": reviewer,
            "p0_count": p0_count,
            "p1_count": p1_count,
            "p2_count": p2_count,
            "replaced": replace,
        },
    )

    return {
        "status": "imported",
        "scope": scope,
        "reviewer": reviewer,
        "gate_report": gate_name,
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "blocks_delivery": blocks_delivery,
    }
