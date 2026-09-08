"""External Quality Review Contract for Deck Master v0.9.

Implements:
- prepare_quality_review: generate review task for external Agent.
- validate_external_review: validate review result.
- import_external_review: import as quality gate report.
"""

from __future__ import annotations

import hashlib
import json
import uuid
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


def _review_task_output(root: Path, scope: str) -> Path:
    folder = root / TASK_DIR
    for parent in (folder, *folder.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ExternalReviewError("Review task directory cannot be a symlink")
    if not folder.resolve().is_relative_to(root.resolve()):
        raise ExternalReviewError("Review task directory escapes run")
    path = folder / _scope_to_task_filename(scope)
    if path.is_symlink():
        raise ExternalReviewError("Review task target cannot be a symlink")
    return path


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
    _review_task_output(root, scopes[0])
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
        write_json(_review_task_output(root, scope), task)
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
    if isinstance(result, dict) and result.get("schema_version") == RESULT_SCHEMA_VERSION_V2:
        return validate_external_review_v2(result)
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


def _validate_schema(payload: dict, filename: str) -> list[str]:
    from jsonschema import Draft202012Validator
    from native_pptx.contracts import SCHEMA_DIR
    schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    return [f"{'.'.join(map(str, error.absolute_path))}: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(payload)]


def _refs_fingerprint(refs: list[dict]) -> str:
    return hashlib.sha256(json.dumps(refs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_external_review_v2(result: dict[str, Any]) -> dict[str, Any]:
    """Validate the canonical result schema, then cross-field review truth."""
    errors = _validate_schema(result, "external-quality-review.v2.schema.json")
    if errors:
        return {"valid": False, "errors": errors, "warnings": []}
    if result["review_kind"] != "independent" or result["reviewer_session_id"] == result["producer_session_id"]:
        errors.append("independence requires a separate reviewer session and independent review kind")
    refs = result["based_on"]["input_refs"]
    if len({r["ref"] for r in refs}) != len(refs):
        errors.append("based_on.input_refs contains duplicate refs")
    if result["based_on"]["input_fingerprint"] != _refs_fingerprint(refs):
        errors.append("based_on.input_fingerprint does not match input_refs")
    if result["reviewed_inputs"] != refs:
        errors.append("reviewed_inputs must match every dispatched input ref and hash")
    coverage = result["coverage"]
    required, reviewed = coverage["required_page_ids"], coverage["reviewed_page_ids"]
    skipped = coverage["skipped"]
    if len(set(required)) != len(required) or len(set(reviewed)) != len(reviewed):
        errors.append("coverage page IDs must be unique")
    if set(reviewed) - set(required):
        errors.append("reviewed pages are outside required coverage")
    missing = set(required) - set(reviewed)
    if missing or skipped:
        # Partial observations may be retained as a rework report, never a
        # passing review. Required pages cannot be waived by a skip reason.
        if result["summary"]["reported_status"] != "rework_required":
            errors.append("coverage incomplete: required pages were skipped or not reviewed")
    dims = {item["dimension"] for item in result["observations"]}
    for dimension in REVIEW_DIMENSIONS_V2:
        if dimension not in dims:
            errors.append(f"dimension '{dimension}' has no observation")
    observed_objects = {ref.split("#", 1)[0] for item in result["observations"] for ref in item["object_refs"]}
    for page in reviewed:
        if page not in observed_objects and f"page_packages/{page}.json" not in observed_objects:
            errors.append(f"reviewed page {page} has no object observation")
    if result["summary"]["reported_status"] == "pass" and result["findings"]:
        errors.append("summary pass cannot carry open findings")
    if result["summary"]["reported_status"] == "pass" and any(o["verdict"] == "fail" for o in result["observations"]):
        errors.append("summary pass conflicts with failed observations")
    return {"valid": not errors, "errors": errors, "warnings": []}


def _review_input_refs(root: Path) -> list[dict]:
    from workflow.actions import revision_read, revision_input_path
    refs = []
    with revision_read(root):
        for directory in ("page_packages", "sources", "diagram_views", "high_density_build/content_locks", "high_density_build/svg", "high_density_build/page_scenes", "high_density_build/scenes", "high_density_build/blueprints"):
            folder = revision_input_path(root, root / directory)
            if folder.is_dir():
                for path in sorted(folder.rglob("*")):
                    if path.is_file():
                        if not path.resolve().is_relative_to(folder.resolve()):
                            raise ExternalReviewError("review input escapes its input directory")
                        refs.append({"ref": directory + "/" + path.relative_to(folder).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for name in ("request.json", "deck_brief.json", "context_manifest.json", "claim_map.json", "claim_evidence_graph.json", "narrative_plan.json", "solution_model.json", "solution_spec.json", "diagram_views.json", "diagram_spec.json", "source_manifest.json", "evidence_graph.json"):
            path = revision_input_path(root, root / name)
            if path.is_file():
                refs.append({"ref": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        # Registered asset paths may live outside a conventional assets folder.
        packages = revision_input_path(root, root / "page_packages")
        for package_path in packages.glob("*.json"):
            package = json.loads(package_path.read_text(encoding="utf-8"))
            for binding in package.get("asset_bindings", []) or []:
                if binding.get("approved") is not True:
                    continue
                relative = str(binding.get("path") or "")
                if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
                    raise ExternalReviewError("review registered asset path is invalid")
                asset = revision_input_path(root, root / relative)
                base = revision_input_path(root, root / "request.json").parent
                if not asset.resolve().is_relative_to(base.resolve()) or not asset.is_file():
                    raise ExternalReviewError("review registered asset is missing or escapes input scope")
                refs.append({"ref": Path(relative).as_posix(), "sha256": hashlib.sha256(asset.read_bytes()).hexdigest()})
    # Render/build outputs are a live selected artifact, not input projections.
    # Freeze their actual bytes at dispatch; later import/currentity recomputes
    # the same set, so a rebuilt PPTX or changed preview requires another review.
    refs.extend(_review_render_refs(root))
    return sorted({item["ref"]: item for item in refs}.values(), key=lambda item: item["ref"])


def _review_render_refs(root: Path) -> list[dict]:
    from runtime.render import CANONICAL_RENDER_RESULT, LEGACY_RENDER_RESULTS
    root = root.resolve()
    refs = {}
    def add(value):
        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = root / path
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ExternalReviewError("review render output is missing or escapes run scope")
        relative = path.resolve().relative_to(root).as_posix()
        content = path.read_bytes()
        refs[relative] = {"ref": relative, "sha256": hashlib.sha256(content).hexdigest()}
        return content
    for relative in (CANONICAL_RENDER_RESULT, *LEGACY_RENDER_RESULTS):
        path = root / relative
        if not path.exists():
            continue
        selection_bytes = add(relative)
        render = json.loads(selection_bytes)
        artifact = render.get("artifact_path") or render.get("artifact")
        if artifact:
            add(artifact)
        if render.get("preview_dir"):
            folder = Path(render["preview_dir"])
            if not folder.is_absolute():
                folder = root / folder
            if not folder.resolve().is_relative_to(root) or not folder.is_dir():
                raise ExternalReviewError("review preview directory is missing or escapes run scope")
            for preview in sorted(folder.iterdir()):
                if preview.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    add(preview)
        for item in render.get("artifacts", []) or []:
            if item.get("path"):
                add(item["path"])
        for item in (render.get("page_previews", []) or []) + (render.get("pages", []) or []):
            if item.get("preview_path"):
                add(item["preview_path"])
        if path.read_bytes() != selection_bytes:
            raise ExternalReviewError("render selection changed during review input capture")
        break
    return list(refs.values())


def _actual_review_pages(root: Path) -> list[str]:
    from workflow.actions import revision_read, revision_input_path
    with revision_read(root):
        folder = revision_input_path(root, root / "page_packages")
        return sorted({str(read_json(p).get("page_id") or p.stem) for p in folder.glob("*.json") if p.name != "index.json"})


def prepare_quality_review_v2(
    run_dir: str | Path, *, scope: str, required_page_ids: list[str],
    review_kind: str = "independent", run_mode: str = "production",
) -> dict[str, Any]:
    """Dispatch a task, never a pre-filled review result or approval."""
    from workflow.actions import revision_read
    root = Path(run_dir).expanduser().resolve()
    if scope not in VALID_SCOPES or review_kind != "independent":
        raise ExternalReviewError("scope and independent review kind are required")
    with revision_read(root):
        pages = _actual_review_pages(root)
        if not pages or sorted(required_page_ids) != pages:
            raise ExternalReviewError("required_page_ids must match every actual Page Package")
        refs = _review_input_refs(root)
        request = read_json(root / "request.json") if (root / "request.json").exists() else {}
        task = {
            "schema_version": "deck_external_quality_review_task.v2",
            "run_id": str(request.get("run_id") or root.name),
            "run_mode": str(request.get("run_mode") or run_mode),
            "task_id": f"{scope.replace('-', '_')}_review_v2_{root.name}",
            "review_action_id": "review_" + uuid.uuid4().hex,
            "scope": scope, "review_kind": "independent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "based_on": {"input_fingerprint": _refs_fingerprint(refs), "input_refs": refs},
            "required_page_ids": pages, "review_dimensions": list(REVIEW_DIMENSIONS_V2),
            "output_schema": RESULT_SCHEMA_VERSION_V2,
        }
        errors = _validate_schema(task, "external-quality-review-task.v2.schema.json")
        if errors:
            raise ExternalReviewError("Invalid review task: " + "; ".join(errors))
        write_json(_review_task_output(root, scope), task)
    append_typed_event(root, "artifact_written", "quality_review_task.prepared_v2",
                       f"External quality review task prepared for {scope}.", run_id=task["run_id"],
                       refs=[f"{TASK_DIR}/{_scope_to_task_filename(scope)}"], payload={"review_action_id": task["review_action_id"]})
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
    # v1 reviewer names are free text; never use their path syntax.
    safe_reviewer = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in reviewer)[:20]
    return f"external_{safe_scope}_{safe_reviewer}_gate.json"


def _page_packages_content_fingerprint(root: Path) -> str:
    """Current canonical review inputs; old ad-hoc v2 hashes become stale."""
    return _refs_fingerprint(_review_input_refs(root))


def validate_review_binding(root: Path, result: dict[str, Any]) -> None:
    """Require the current issued task, source hashes and actual page set."""
    scope = result["scope"]
    from workflow.actions import revision_read
    with revision_read(root):
        task_path = root / TASK_DIR / _scope_to_task_filename(scope)
        task = read_json(task_path) if task_path.is_file() else {}
        if task.get("schema_version") != "deck_external_quality_review_task.v2" or task.get("review_action_id") != result["review_action_id"]:
            raise ExternalReviewError("Review result does not match an issued current v2 task")
        if task["based_on"] != result["based_on"] or result["based_on"]["input_refs"] != _review_input_refs(root):
            raise ExternalReviewError("Review inputs changed or do not match dispatched hashes")
        if result["coverage"]["required_page_ids"] != task["required_page_ids"] or task["required_page_ids"] != _actual_review_pages(root):
            raise ExternalReviewError("Review coverage does not match the actual dispatched pages")
        if result["run_mode"] != task["run_mode"]:
            raise ExternalReviewError("Review run mode differs from dispatched task")


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
    if schema_version == RESULT_SCHEMA_VERSION_V2:
        validate_review_binding(root, result)

    quality_dir = root / "quality_reports"
    if quality_dir.is_symlink() or not quality_dir.resolve().is_relative_to(root.resolve()):
        raise ExternalReviewError("Quality report directory escapes managed output scope")
    quality_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = quality_dir / "archive"
    if archive_dir.is_symlink():
        raise ExternalReviewError("Quality report archive cannot be a symlink")

    gate_name = _gate_filename(scope, reviewer)
    gate_path = quality_dir / gate_name
    if gate_path.is_symlink() or gate_path.parent.resolve() != quality_dir.resolve():
        raise ExternalReviewError("Quality report target escapes managed output scope")

    # Archive existing if replacing.
    if gate_path.exists():
        if not replace:
            raise ExternalReviewError(
                f"Report {gate_name} already exists. Use --replace to overwrite. "
                "Old report preserved in archive."
            )
        previous = json.loads(gate_path.read_text(encoding="utf-8"))
        from quality.gate_freshness import report_currentity
        if report_currentity(root, previous).get("current"):
            previous_blockers = {f["finding_id"]: f["severity"] for f in previous.get("findings", []) if f.get("severity") in {"P0", "P1"}}
            incoming = {f["finding_id"]: f["severity"] for f in result.get("findings", [])}
            ranks = {"P0": 0, "P1": 1, "P2": 2}
            if any(ranks.get(incoming.get(fid), 99) > ranks[severity] for fid, severity in previous_blockers.items()):
                raise ExternalReviewError("Replacement cannot remove or downgrade current blocking findings; retain findings and use the explicit authorized override policy for eligible P1 findings")
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        archived = archive_dir / f"{stamp}_{uuid.uuid4().hex}_{gate_name}"
        if archived.is_symlink() or archived.parent.resolve() != archive_dir.resolve():
            raise ExternalReviewError("Quality report archive target escapes managed output scope")
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

    reported_status = str((result.get("summary") or {}).get("reported_status" if schema_version == RESULT_SCHEMA_VERSION_V2 else "status") or "")
    if reported_status == "rework_required":
        status, blocks_delivery = "rework_required", True
    elif reported_status == "conditional_pass" and not blocks_delivery:
        status = "conditional_pass"
    if schema_version == RESULT_SCHEMA_VERSION_V2 and (result["coverage"]["skipped"] or set(result["coverage"]["required_page_ids"]) != set(result["coverage"]["reviewed_page_ids"]) or any(o["verdict"] == "fail" for o in result["observations"])):
        status, blocks_delivery = "rework_required", True

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
                "refs": f.get("object_refs", f.get("refs", [])),
                "repair_action": f.get("repair_action", ""),
                "allowed_scope_refs": f.get("allowed_scope_refs", []),
                "recheck": f.get("recheck", ""),
                "source": "external_review",
                "reviewer": reviewer,
            }
            for f in findings
        ],
    }
    if schema_version == RESULT_SCHEMA_VERSION_V2:
        based_on = result.get("based_on") if isinstance(result.get("based_on"), dict) else {}
        gate_report["based_on_sha256"] = next((r["sha256"] for r in based_on["input_refs"] if r["ref"] == "page_packages/index.json"), "")
        # SC-1.1 review round 2 (P1-06): the content fingerprint comes from
        # the REPORT's declared binding (fixed at review dispatch/read time).
        # The importer NEVER recomputes the current value for an arriving
        # report — a stale result cannot be re-bound to current content.
        gate_report["content_fingerprint"] = str(based_on["input_fingerprint"])
        gate_report["review_kind"] = str(result.get("review_kind") or "")
        gate_report["reviewer_session_id"] = str(result.get("reviewer_session_id") or "")
        gate_report["canonical_review"] = result
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
