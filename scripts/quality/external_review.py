"""External Quality Review Contract for Deck Master v0.9.

Implements:
- prepare_quality_review: generate review task for external Agent.
- validate_external_review: validate review result.
- import_external_review: import as quality gate report.
"""

from __future__ import annotations

import hashlib
import json
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
QUALITY_FINDINGS_SCHEMA_VERSION = "deck_master_quality_findings.v1"

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_run_file(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _review_input_binding(root: Path, scope: str) -> dict[str, Any]:
    candidates: set[Path] = set()
    for relative in (
        "request.json",
        "context_manifest.json",
        DECK_BRIEF_NAME,
        "claim_map.json",
        "claim_evidence_graph.json",
        "narrative_plan.json",
        PAGE_TASKS_NAME,
        "preview_manifest.json",
        "render_results/render_result.json",
        "high_density_build/readback/readback_report.json",
    ):
        path = root / relative
        if path.is_file():
            candidates.add(path.resolve())
    for pattern in (
        "page_packages/*.json",
        "high_density_build/content_locks/*.json",
        "high_density_build/scenes/*.json",
        "high_density_build/page_scenes/*.json",
        "high_density_build/svg/*.svg",
        "high_density_build/pptx/*.pptx",
    ):
        candidates.update(path.resolve() for path in root.glob(pattern) if path.is_file())

    render_result_path = root / "render_results" / "render_result.json"
    render_result = read_json(render_result_path) if render_result_path.is_file() else {}
    artifact = _safe_run_file(root, render_result.get("artifact_path"))
    if artifact is not None:
        candidates.add(artifact)

    files = [
        {
            "path": path.relative_to(root.resolve()).as_posix(),
            "sha256": _sha256_file(path),
        }
        for path in sorted(candidates, key=lambda item: item.as_posix())
    ]
    encoded = json.dumps(
        {"scope": scope, "files": files},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    artifact_record = next(
        (item for item in files if item["path"] == artifact.relative_to(root.resolve()).as_posix()),
        None,
    ) if artifact is not None else None
    semantic_targets = [
        item["path"]
        for item in files
        if item["path"] == "preview_manifest.json"
        or item["path"].startswith("page_packages/")
        or item["path"].startswith("high_density_build/content_locks/")
        or item["path"].startswith("high_density_build/scenes/")
        or item["path"].startswith("high_density_build/page_scenes/")
        or item["path"].startswith("high_density_build/svg/")
        or item["path"].endswith(".pptx")
    ]
    visual_targets = [
        path
        for path in semantic_targets
        if path.startswith("high_density_build/svg/") or path.endswith(".pptx")
    ]
    evidence_targets = [
        item["path"]
        for item in files
        if item["path"] in {"context_manifest.json", "claim_map.json", "claim_evidence_graph.json"}
    ]
    if scope == "visual":
        review_targets = visual_targets
    elif scope == "evidence":
        review_targets = evidence_targets
    elif scope == "client-readiness":
        review_targets = [path for path in semantic_targets if path.endswith(".pptx")]
    else:
        review_targets = semantic_targets
    return {
        "scope": scope,
        "input_fingerprint": hashlib.sha256(encoded).hexdigest(),
        "files": files,
        "artifact": artifact_record or {},
        "review_targets": review_targets,
    }


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
        input_binding = _review_input_binding(root, scope)
        if not input_binding["review_targets"]:
            raise ExternalReviewError(
                f"Cannot prepare {scope} review: no current review target exists for that scope."
            )
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
                "page_packages": "page_packages/",
                "preview_manifest": "preview_manifest.json",
                "render_result": "render_results/render_result.json",
                "high_density_visible_outputs": "high_density_build/",
            },
            "input_binding": input_binding,
            "result_requirements": {
                "echo_input_fingerprint": input_binding["input_fingerprint"],
                "inspect_review_targets": input_binding["review_targets"],
                "inspect_actual_visible_output": scope in {"semantic", "visual", "client-readiness"},
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
        "input_fingerprint": payload.get("input_fingerprint", ""),
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
    try:
        run_id = assert_external_result_matches_run(
            root,
            result.get("run_id", ""),
            artifact_name="external quality review",
        )
    except RunStateError as exc:
        raise ExternalReviewError(str(exc)) from exc
    scope = str(result.get("scope", ""))
    reviewer = str(result.get("reviewer", ""))

    task_path = root / TASK_DIR / _scope_to_task_filename(scope)
    review_binding: dict[str, Any] = {}
    if task_path.is_file():
        task = read_json(task_path)
        expected_binding = task.get("input_binding") if isinstance(task.get("input_binding"), dict) else {}
        expected_fingerprint = str(expected_binding.get("input_fingerprint") or "")
        supplied_fingerprint = str(result.get("input_fingerprint") or "")
        current_binding = _review_input_binding(root, scope)
        if not expected_fingerprint:
            raise ExternalReviewError("Prepared review task has no input fingerprint; prepare a fresh review task.")
        if supplied_fingerprint != expected_fingerprint:
            raise ExternalReviewError("External review does not match the prepared task input fingerprint.")
        if current_binding["input_fingerprint"] != expected_fingerprint:
            raise ExternalReviewError("External review task is stale because its input files changed; prepare a fresh review task.")
        review_binding = current_binding

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
        "input_fingerprint": str(review_binding.get("input_fingerprint") or result.get("input_fingerprint") or ""),
        "review_input_binding": review_binding,
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
    artifact_binding = review_binding.get("artifact") if isinstance(review_binding.get("artifact"), dict) else {}
    if artifact_binding.get("path") and artifact_binding.get("sha256"):
        gate_report["artifact_binding"] = {
            "artifact_run_relative": artifact_binding["path"],
            "artifact_sha256": artifact_binding["sha256"],
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
