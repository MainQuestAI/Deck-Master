"""External Quality Review Contract for Deck Master v0.9.

Implements:
- prepare_quality_review: generate review task for external Agent.
- validate_external_review: validate review result.
- import_external_review: import as quality gate report.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event
from runtime.import_log import append_import_log
from runtime.run_state import (
    DECK_BRIEF_NAME,
    PAGE_TASKS_NAME,
    RunStateError,
    assert_external_result_matches_run,
    ensure_run_dirs,
    read_json,
    write_json,
)

TASK_SCHEMA_VERSION = "deck_external_quality_review_task.v1"
RESULT_SCHEMA_VERSION = "deck_external_quality_review.v1"
RESULT_SCHEMA_VERSION_V2 = "deck_external_quality_review.v2"
QUALITY_FINDINGS_SCHEMA_VERSION = "deck_master_quality_findings.v1"

# SC-1 C1: the v2 six-dimension rubric (external-quality-review.v2 schema).
REVIEW_DIMENSIONS_V2 = (
    "customer_specificity",
    "solution_validity",
    "evidence_quality",
    "decision_logic",
    "implementation_specificity",
    "expression_quality",
)
VALID_REPORTED_STATUS_V2 = {"pass", "conditional_pass", "rework_required"}

TASK_DIR = "quality_review_tasks"
VALID_SCOPES = {"semantic", "visual", "evidence", "client-readiness"}
VALID_SEVERITIES = {"P0", "P1", "P2"}
VALID_STATUSES = {"pass", "conditional_pass", "rework_required"}
VALID_FINDINGS_GATE_CLASSES = {"semantic", "visual", "evidence", "client-readiness"}


class ExternalReviewError(ValueError):
    """Raised when external review is invalid or import fails."""


def _quality_findings_rejected(
    run_dir: Path,
    message: str,
    *,
    source_path: str | Path | None = None,
) -> ExternalReviewError:
    append_import_log(
        run_dir,
        import_type="quality_findings",
        source="ppt-quality-gate",
        status="rejected",
        source_path=source_path,
        errors=[message],
    )
    return ExternalReviewError(message)


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
# v2 (SC-1 C1): six-dimension rubric, coverage, independence
# --------------------------------------------------------------------------- #


def validate_external_review_v2(result: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed validation of a deck_external_quality_review.v2 report.

    A reviewer string alone is not independence; coverage must be complete or
    explicitly skipped with reasons; every dimension needs an observation; a
    ``pass`` with empty findings is only accepted when coverage is complete
    and all six dimensions were actually observed.
    """

    errors: list[str] = []
    if not isinstance(result, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}
    if result.get("schema_version") != RESULT_SCHEMA_VERSION_V2:
        errors.append(f"schema_version must be '{RESULT_SCHEMA_VERSION_V2}', got '{result.get('schema_version')}'.")
        return {"valid": False, "errors": errors, "warnings": []}

    for field in ("run_id", "scope", "based_on", "review_action_id", "review_kind", "host_execution_ref"):
        if not str(result.get(field) or "").strip():
            errors.append(f"{field} is required.")
    reviewer_session = str(result.get("reviewer_session_id") or "").strip()
    producer_session = str(result.get("producer_session_id") or "").strip()
    if not reviewer_session:
        errors.append("reviewer_session_id is required.")
    if not producer_session:
        errors.append("producer_session_id is required.")
    if reviewer_session and producer_session and reviewer_session == producer_session:
        errors.append("reviewer_session_id must differ from producer_session_id (independence).")

    reviewed_inputs = result.get("reviewed_inputs")
    if not isinstance(reviewed_inputs, dict) or not reviewed_inputs:
        errors.append("reviewed_inputs must record the input artifacts and versions.")

    coverage = result.get("coverage") if isinstance(result.get("coverage"), dict) else {}
    required_ids = [str(item) for item in (coverage.get("required_page_ids") or [])]
    reviewed_ids = set(str(item) for item in (coverage.get("reviewed_page_ids") or []))
    skipped = {str(item.get("ref") or ""): str(item.get("reason") or "") for item in (coverage.get("skipped") or []) if isinstance(item, dict)}
    if not required_ids:
        errors.append("coverage.required_page_ids must not be empty.")
    missing = [page_id for page_id in required_ids if page_id not in reviewed_ids and page_id not in skipped]
    if missing:
        errors.append(f"coverage incomplete; pages neither reviewed nor explicitly skipped: {missing}")
    for ref, reason in skipped.items():
        if ref and not reason:
            errors.append(f"coverage skip of '{ref}' requires a reason.")

    dimension_scores = result.get("dimension_scores") if isinstance(result.get("dimension_scores"), dict) else {}
    observations = result.get("observations") if isinstance(result.get("observations"), list) else []
    observed_dims = {str(item.get("dimension") or "") for item in observations if isinstance(item, dict)}
    for dimension in REVIEW_DIMENSIONS_V2:
        if dimension not in observed_dims:
            errors.append(f"dimension '{dimension}' has no observation; unreviewed content stays unreviewed (no empty pass).")
        score = dimension_scores.get(dimension)
        if not isinstance(score, (int, float)) or not 1 <= float(score) <= 5:
            errors.append(f"dimension_scores.{dimension} must be a number between 1 and 5.")
    unknown_dims = observed_dims - set(REVIEW_DIMENSIONS_V2)
    if unknown_dims:
        errors.append(f"observations carry unknown dimensions: {sorted(unknown_dims)}")
    for index, item in enumerate(observations):
        if not isinstance(item, dict):
            continue
        if not str(item.get("observation") or item.get("message") or "").strip():
            errors.append(f"observations[{index}] needs concrete observation text.")

    findings = result.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array.")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    reported_status = str(summary.get("reported_status") or "")
    if reported_status not in VALID_REPORTED_STATUS_V2:
        errors.append(f"summary.reported_status must be one of {sorted(VALID_REPORTED_STATUS_V2)}.")
    if reported_status == "pass" and findings:
        errors.append("summary.reported_status 'pass' cannot carry open findings; use conditional_pass or rework_required.")
    if reported_status in {"pass", "conditional_pass"} and missing:
        errors.append("cannot report pass with incomplete coverage.")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": []}


def prepare_quality_review_v2(
    run_dir: str | Path,
    *,
    scope: str,
    required_page_ids: list[str],
    review_kind: str = "full_deck",
    run_mode: str = "production",
) -> dict[str, Any]:
    """Emit a v2 review task bound to current input versions (page packages)."""

    root = Path(run_dir).expanduser().resolve()
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope must be one of {sorted(VALID_SCOPES)}")
    task_dir = root / TASK_DIR
    task_dir.mkdir(parents=True, exist_ok=True)
    package_index = root / "page_packages" / "index.json"
    input_version = ""
    if package_index.exists():
        input_version = hashlib.sha256(package_index.read_bytes()).hexdigest()
    try:
        content_fingerprint = _page_packages_content_fingerprint(root)
    except Exception:  # noqa: BLE001
        content_fingerprint = ""
    task = {
        "schema_version": RESULT_SCHEMA_VERSION_V2,
        "run_id": str(root.name),
        "run_mode": run_mode,
        "task_id": f"{scope.replace('-', '_')}_review_v2_{root.name or 'unknown'}",
        "scope": scope,
        "review_kind": review_kind,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "based_on": {
            "page_packages_index_sha256": input_version,
            "content_fingerprint": content_fingerprint,
            "note": "review binds to the current package set; content changes invalidate this review",
        },
        "reviewed_inputs": {
            "page_packages": "page_packages/",
            "claim_evidence_graph": "claim_evidence_graph.json",
            "context_manifest": "context_manifest.json",
        },
        "coverage": {"required_page_ids": [str(item) for item in required_page_ids], "reviewed_page_ids": [], "skipped": []},
        "review_dimensions": list(REVIEW_DIMENSIONS_V2),
        "output_schema": RESULT_SCHEMA_VERSION_V2,
    }
    write_json(task_dir / _scope_to_task_filename(scope), task)
    append_typed_event(
        root,
        "artifact_written",
        "quality_review_task.prepared_v2",
        f"External quality review v2 task prepared for scope: {scope}.",
        run_id=task["run_id"],
        refs=[f"{TASK_DIR}/{_scope_to_task_filename(scope)}"],
        payload={"scope": scope, "required_page_ids": required_page_ids},
    )
    return task


def _map_quality_severity(value: Any, finding: dict[str, Any]) -> str:
    raw = str(value or "").strip()
    if raw in VALID_SEVERITIES:
        return raw
    if raw in {"critical", "fatal"} or str(finding.get("priority") or "") == "P0":
        return "P0"
    if raw in {"blocking", "blocker", "error"}:
        return "P1"
    if raw in {"warning", "warn", "info", ""}:
        return "P2"
    return "P2"


def validate_quality_findings(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}
    if payload.get("schema_version") != QUALITY_FINDINGS_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{QUALITY_FINDINGS_SCHEMA_VERSION}', got '{payload.get('schema_version')}'."
        )
    if not payload.get("run_id"):
        errors.append("run_id is required.")
    gate_class = str(payload.get("gate_class") or payload.get("scope") or "")
    if gate_class not in VALID_FINDINGS_GATE_CLASSES:
        errors.append(f"gate_class must be one of {sorted(VALID_FINDINGS_GATE_CLASSES)}.")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array.")
    else:
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                errors.append(f"findings[{index}] must be an object.")
                continue
            if not (finding.get("finding_id") or finding.get("id")):
                errors.append(f"findings[{index}].finding_id is required.")
            if not (finding.get("message") or finding.get("title")):
                errors.append(f"findings[{index}].message or title is required.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def quality_findings_to_external_review(payload: dict[str, Any]) -> dict[str, Any]:
    gate_class = str(payload.get("gate_class") or payload.get("scope") or "")
    findings: list[dict[str, Any]] = []
    for index, finding in enumerate(payload.get("findings", []), start=1):
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("finding_id") or finding.get("id") or f"quality_{index:03d}")
        message = str(finding.get("message") or finding.get("title") or "")
        repair_instruction = str(
            finding.get("repair_instruction")
            or finding.get("recommendation")
            or finding.get("suggestion")
            or ""
        )
        findings.append(
            {
                "finding_id": finding_id,
                "severity": _map_quality_severity(finding.get("severity"), finding),
                "page_id": str(finding.get("page_id") or finding.get("beat_id") or ""),
                "dimension": str(finding.get("dimension") or finding.get("category") or gate_class),
                "message": message,
                "repair_instruction": repair_instruction,
                "refs": finding.get("refs", []),
            }
        )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": payload.get("run_id", ""),
        "reviewer": payload.get("reviewer", "ppt-quality-gate"),
        "scope": gate_class,
        "created_at": payload.get("created_at", datetime.now(timezone.utc).isoformat()),
        "summary": {"status": "rework_required" if any(f["severity"] in {"P0", "P1"} for f in findings) else "pass"},
        "findings": findings,
    }


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def _gate_filename(scope: str, reviewer: str) -> str:
    """Build gate filename: external_<scope>_<reviewer>_gate.json."""
    safe_scope = scope.replace("-", "_")
    safe_reviewer = reviewer.replace("-", "_").replace(" ", "_")[:20]
    return f"external_{safe_scope}_{safe_reviewer}_gate.json"


def _page_packages_content_fingerprint(root: Path) -> str:
    """Hash over every page package FILE's content (not just the index) —
    editing a package without touching index.json still stales the review."""

    import hashlib

    digest = hashlib.sha256()
    packages_dir = root / "page_packages"
    if not packages_dir.is_dir():
        return ""
    for package_file in sorted(packages_dir.glob("*.json")):
        digest.update(package_file.name.encode("utf-8"))
        digest.update(hashlib.sha256(package_file.read_bytes()).digest())
    return digest.hexdigest()


def import_external_review(
    run_dir: str | Path,
    result: dict[str, Any],
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """Import external quality review (v1 or v2) as a quality gate report."""
    schema_version = str(result.get("schema_version") or "")
    if schema_version == RESULT_SCHEMA_VERSION_V2:
        validation = validate_external_review_v2(result)
        reviewer = str(result.get("reviewer_session_id") or "")
    else:
        validation = validate_external_review(result)
        reviewer = str(result.get("reviewer") or "")
    if not validation["valid"]:
        raise ExternalReviewError(
            "Invalid external review: " + "; ".join(validation["errors"])
        )

    root = ensure_run_dirs(run_dir)
    try:
        run_id = assert_external_result_matches_run(
            root,
            result.get("run_id", ""),
            artifact_name="external quality review",
        )
    except RunStateError as exc:
        raise ExternalReviewError(str(exc)) from exc
    scope = str(result.get("scope", ""))

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
                "repair_instruction": str(f.get("repair_instruction") or f.get("suggested_repair") or ""),
                "refs": f.get("refs", []),
                "source": "external_review",
                "reviewer": reviewer,
            }
            for f in findings
        ],
    }
    if schema_version == RESULT_SCHEMA_VERSION_V2:
        based_on = result.get("based_on") if isinstance(result.get("based_on"), dict) else {}
        gate_report["based_on_sha256"] = str(based_on.get("page_packages_index_sha256") or "")
        # SC-1.1 review round 2 (P1-06): the content fingerprint comes from
        # the REPORT's declared binding (fixed at review dispatch/read time).
        # The importer NEVER recomputes the current value for an arriving
        # report — a stale result cannot be re-bound to current content.
        gate_report["content_fingerprint"] = str(based_on.get("content_fingerprint") or "").strip()
        gate_report["review_kind"] = str(result.get("review_kind") or "")
        gate_report["reviewer_session_id"] = str(result.get("reviewer_session_id") or "")
    else:
        # SC-1.1 P1-06: v1 reports stay readable as history but are marked
        # legacy — they can never satisfy the native production gate.
        gate_report["legacy_v1"] = True

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


def import_quality_findings(
    run_dir: str | Path,
    input_path: str | Path,
    *,
    replace: bool = False,
) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    source_path = Path(input_path).expanduser().resolve()
    try:
        payload = read_json(source_path)
    except RunStateError as exc:
        raise _quality_findings_rejected(root, str(exc), source_path=source_path) from exc

    validation = validate_quality_findings(payload)
    if not validation["valid"]:
        raise _quality_findings_rejected(root, "; ".join(validation["errors"]), source_path=source_path)

    try:
        run_id = assert_external_result_matches_run(
            root,
            payload.get("run_id", ""),
            artifact_name="quality findings",
        )
    except RunStateError as exc:
        raise _quality_findings_rejected(root, str(exc), source_path=source_path) from exc

    review = quality_findings_to_external_review(payload)
    imported = import_external_review(root, review, replace=replace)
    append_import_log(
        root,
        import_type="quality_findings",
        source="ppt-quality-gate",
        status="imported",
        source_path=source_path,
        canonical_refs=[f"quality_reports/{imported['gate_report']}"],
        warnings=validation.get("warnings", []),
        payload={
            "run_id": run_id,
            "gate_class": review.get("scope"),
            "p0_count": imported.get("p0_count", 0),
            "p1_count": imported.get("p1_count", 0),
            "p2_count": imported.get("p2_count", 0),
            "blocks_delivery": imported.get("blocks_delivery", False),
        },
    )
    return {
        **imported,
        "source_schema_version": payload.get("schema_version"),
        "canonical_schema_version": RESULT_SCHEMA_VERSION,
    }
