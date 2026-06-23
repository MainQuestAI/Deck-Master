"""Generation Handoff / Handback Contract for Deck Master v0.9.

Implements:
- prepare_generation_handoff: enhance generation tasks with handoff fields.
- validate_generation_result: validate result from build tool.
- import_generation_result: import completed/failed/partial result.
- refresh_preview_from_generation: update preview_manifest from results.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preview.manifest import ManifestError, load_manifest, write_manifest
from runtime.artifact_validator import validate_artifact_descriptor
from runtime.events import append_typed_event
from runtime.run_state import (
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    RunStateError,
    assert_external_result_matches_run,
    ensure_run_dirs,
    read_json,
    write_json,
)

RESULT_SCHEMA_VERSION = "deck_generation_result.v2"
LEGACY_RESULT_SCHEMA_VERSION = "deck_generation_result.v1"
DECK_PRO_MAX_RESULT_SCHEMA_VERSION = "ppt_deck_pro_max_generation_result.v1"
HANDOFF_SCHEMA_VERSION = "deck_generation_task.v1"

RESULTS_DIR = "generation_results"
TASKS_DIR = "generation_tasks"

VALID_STATUSES = {"completed", "partial", "failed"}
DECK_PRO_MAX_STATUSES = {"completed", "partial", "failed", "success", "error"}
ARTIFACT_KINDS = {
    "page_html",
    "html_fragment",
    "page_svg",
    "page_png",
    "page_jpeg",
    "page_pptx",
    "deck_html",
    "deck_pdf",
    "deck_pptx",
    "asset_bundle",
    "quality_report",
    "source_snapshot",
}
VALIDATION_STATUSES = {"validated", "invalid", "unvalidated", "stale", "missing"}
EDITABILITY_VALUES = {"native", "hybrid", "flat_image", "not_applicable", "unknown"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
PLACEHOLDER_TOKENS = (
    b"deck-master bundled generation placeholder",
    b"deck-master bundled generation preview",
)


class GenerationHandbackError(ValueError):
    """Raised when generation result is invalid or import fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: Any, *, field_name: str) -> str:
    path_text = str(value or "").strip()
    if not path_text:
        raise GenerationHandbackError(f"{field_name} is required.")
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise GenerationHandbackError(f"{field_name} must be a run-relative path: {path_text}")
    return path_text


def _resolve_run_relative(run_dir: Path, value: str, *, field_name: str) -> Path:
    path_text = _safe_relative_path(value, field_name=field_name)
    resolved = (run_dir / path_text).resolve()
    root_text = str(run_dir.resolve())
    resolved_text = str(resolved)
    if resolved_text != root_text and not resolved_text.startswith(root_text + os.sep):
        raise GenerationHandbackError(f"{field_name} escapes run directory: {path_text}")
    return resolved


def source_fingerprint_for_run(run_dir: str | Path) -> str:
    """Return the current generation source fingerprint for this run."""
    root = Path(run_dir).expanduser().resolve()
    digest = hashlib.sha256()
    for rel in (Path(TASKS_DIR) / "index.json", Path("page_tasks.json"), Path("sourcing_plan.json")):
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        digest.update(str(rel).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _run_mode(run_dir: Path | None) -> str:
    if run_dir is None:
        return "production"
    request_path = run_dir / "request.json"
    if not request_path.exists():
        return "production"
    try:
        request = read_json(request_path)
    except RunStateError:
        return "production"
    mode = str(request.get("run_mode") or "production").strip().lower()
    if mode in {"production", "benchmark", "fixture", "dev"}:
        return mode
    return "production"


def _looks_like_placeholder(path: Path) -> bool:
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return any(token in data for token in PLACEHOLDER_TOKENS)


def _guess_media_type(path: str, kind: str = "") -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".html":
        return "text/html"
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if suffix == ".pdf":
        return "application/pdf"
    if kind == "asset_bundle":
        return "application/octet-stream"
    return "application/octet-stream"


def _legacy_kind(artifact_type: str, path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".html":
        return "page_html"
    if suffix == ".svg":
        return "page_svg"
    if suffix == ".png":
        return "page_png"
    if suffix in {".jpg", ".jpeg"}:
        return "page_jpeg"
    if suffix == ".pptx":
        return "page_pptx"
    if suffix == ".pdf":
        return "deck_pdf"
    if artifact_type in ARTIFACT_KINDS:
        return artifact_type
    return "asset_bundle"


def _artifact_descriptor(
    *,
    run_dir: Path | None,
    path: str,
    artifact_id: str,
    kind: str,
    page_id: str,
    editability: str = "unknown",
) -> dict[str, Any]:
    metadata = {
        "artifact_id": artifact_id,
        "kind": kind,
        "path": _safe_relative_path(path, field_name="artifact.path"),
        "media_type": _guess_media_type(path, kind),
        "sha256": "",
        "bytes": 0,
        "validation_status": "unvalidated",
        "editability": editability if editability in EDITABILITY_VALUES else "unknown",
        "page_id": page_id,
        "created_at": _utc_now(),
    }
    if run_dir is not None:
        resolved = _resolve_run_relative(run_dir, path, field_name="artifact.path")
        if not resolved.exists() or not resolved.is_file():
            raise GenerationHandbackError(f"artifact.path not found: {path}")
        metadata["sha256"] = _sha256(resolved)
        metadata["bytes"] = resolved.stat().st_size
        metadata["validation_status"] = "validated"
    return metadata


def _artifact_path(result: dict[str, Any]) -> str:
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        first = artifacts[0]
        if isinstance(first, dict):
            return str(first.get("path") or "")
    return str(result.get("artifact_path") or "")


def _preview_path(result: dict[str, Any]) -> str:
    preview = result.get("preview")
    if isinstance(preview, dict):
        return str(preview.get("path") or "")
    return str(result.get("preview_path") or "")


def _validate_artifact(
    artifact: dict[str, Any],
    *,
    run_dir: Path | None,
    field_name: str,
    errors: list[str],
    run_mode: str,
) -> None:
    for required in ("artifact_id", "kind", "path", "media_type", "sha256", "bytes", "validation_status"):
        if artifact.get(required) in (None, ""):
            errors.append(f"{field_name}.{required} is required.")
    kind = str(artifact.get("kind") or "")
    if kind and kind not in ARTIFACT_KINDS:
        errors.append(f"{field_name}.kind must be one of {sorted(ARTIFACT_KINDS)}.")
    validation_status = str(artifact.get("validation_status") or "")
    if validation_status and validation_status not in VALIDATION_STATUSES:
        errors.append(f"{field_name}.validation_status must be one of {sorted(VALIDATION_STATUSES)}.")
    editability = str(artifact.get("editability") or "unknown")
    if editability not in EDITABILITY_VALUES:
        errors.append(f"{field_name}.editability must be one of {sorted(EDITABILITY_VALUES)}.")
    path_text = str(artifact.get("path") or "")
    try:
        resolved = _resolve_run_relative(run_dir, path_text, field_name=f"{field_name}.path") if run_dir else None
    except GenerationHandbackError as exc:
        errors.append(str(exc))
        resolved = None
    sha = str(artifact.get("sha256") or "")
    if sha and not SHA256_RE.match(sha):
        errors.append(f"{field_name}.sha256 must be a lowercase SHA-256 hex digest.")
    size = artifact.get("bytes")
    if not isinstance(size, int) or size < 1:
        errors.append(f"{field_name}.bytes must be a positive integer.")
    if resolved is not None:
        if not resolved.exists() or not resolved.is_file():
            errors.append(f"{field_name}.path not found: {path_text}")
            return
        actual_size = resolved.stat().st_size
        actual_sha = _sha256(resolved)
        if size != actual_size:
            errors.append(f"{field_name}.bytes mismatch: got {size}, expected {actual_size}.")
        if sha and sha != actual_sha:
            errors.append(f"{field_name}.sha256 mismatch.")
        if run_mode in {"production", "benchmark"} and _looks_like_placeholder(resolved):
            errors.append(f"{field_name}.path points to bundled placeholder content.")
        artifact_validation = validate_artifact_descriptor(
            run_dir,
            artifact,
            expected_page_count=1 if kind in {"page_pptx", "page_html"} else None,
            allow_contract_smoke=run_mode in {"fixture", "dev"},
            allow_non_client_deliverable=run_mode in {"fixture", "dev"},
        )
        if not artifact_validation.get("valid"):
            for error in artifact_validation.get("errors", []):
                errors.append(f"{field_name}.{error}")


def normalize_generation_result(
    result: dict[str, Any],
    *,
    expected_run_id: str | None = None,
    expected_session_id: str | None = None,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Normalize companion-tool handback into Deck Master's canonical result."""
    if not isinstance(result, dict):
        raise GenerationHandbackError("Result payload must be a JSON object.")
    schema_version = result.get("schema_version")
    if schema_version == RESULT_SCHEMA_VERSION:
        canonical = dict(result)
        run_id = str(canonical.get("run_id") or "")
        if expected_run_id and run_id != expected_run_id:
            raise GenerationHandbackError(
                f"generation result run_id mismatch: got '{run_id}', expected '{expected_run_id}'."
            )
        session_id = str(canonical.get("session_id") or "")
        if expected_session_id and session_id != expected_session_id:
            raise GenerationHandbackError(
                f"generation result session_id mismatch: got '{session_id}', expected '{expected_session_id}'."
            )
        if canonical.get("beat_id") and not canonical.get("page_id"):
            canonical["page_id"] = str(canonical["beat_id"])
        if canonical.get("page_id") and not canonical.get("beat_id"):
            canonical["beat_id"] = str(canonical["page_id"])
        preview_path = _preview_path(canonical)
        artifact_path = _artifact_path(canonical)
        if preview_path:
            canonical["preview_path"] = preview_path
        if artifact_path:
            canonical["artifact_path"] = artifact_path
        producer = canonical.get("producer") if isinstance(canonical.get("producer"), dict) else {}
        canonical["tool"] = str(canonical.get("tool") or producer.get("capability") or "ppt-deck-pro-max")
        return canonical
    if schema_version not in {LEGACY_RESULT_SCHEMA_VERSION, DECK_PRO_MAX_RESULT_SCHEMA_VERSION}:
        raise GenerationHandbackError(
            f"schema_version must be '{RESULT_SCHEMA_VERSION}', '{LEGACY_RESULT_SCHEMA_VERSION}' or "
            f"'{DECK_PRO_MAX_RESULT_SCHEMA_VERSION}', got '{schema_version}'."
        )

    root = Path(run_dir).expanduser().resolve() if run_dir else None
    run_id = str(result.get("run_id") or "")
    if expected_run_id and run_id != expected_run_id:
        raise GenerationHandbackError(
            f"generation result run_id mismatch: got '{run_id}', expected '{expected_run_id}'."
        )
    session_id = str(result.get("session_id") or "")
    if expected_session_id and session_id != expected_session_id:
        raise GenerationHandbackError(
            f"generation result session_id mismatch: got '{session_id}', expected '{expected_session_id}'."
        )

    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    artifact = result.get("artifact") if isinstance(result.get("artifact"), dict) else {}
    preview = result.get("preview") if isinstance(result.get("preview"), dict) else {}
    raw_status = str(result.get("status") or "")
    status_map = {"success": "completed", "error": "failed"}
    status = status_map.get(raw_status, raw_status)
    if status not in VALID_STATUSES:
        raise GenerationHandbackError(f"status must be one of {sorted(DECK_PRO_MAX_STATUSES)}.")

    task_id = str(result.get("task_id") or result.get("task") or "")
    page_id = str(result.get("page_id") or result.get("beat_id") or "")
    beat_id = str(result.get("beat_id") or result.get("page_id") or "")
    artifact_path = str(result.get("artifact_path") or outputs.get("artifact_path") or artifact.get("path") or "")
    preview_path = str(result.get("preview_path") or outputs.get("preview_path") or preview.get("path") or "")
    artifact_type = str(result.get("artifact_type") or artifact.get("type") or "page_pptx")
    source_fingerprint = str(result.get("source_fingerprint") or "")
    if not source_fingerprint and root:
        source_fingerprint = source_fingerprint_for_run(root)
    if not source_fingerprint:
        source_fingerprint = "0" * 64

    artifacts: list[dict[str, Any]] = []
    if artifact_path and status in {"completed", "partial"}:
        artifacts.append(
            _artifact_descriptor(
                run_dir=root,
                path=artifact_path,
                artifact_id=f"{page_id or task_id}_artifact",
                kind=_legacy_kind(artifact_type, artifact_path),
                page_id=page_id,
                editability=str(result.get("editability") or "unknown"),
            )
        )
    preview_descriptor: dict[str, Any] | None = None
    if preview_path and status in {"completed", "partial"}:
        preview_descriptor = _artifact_descriptor(
            run_dir=root,
            path=preview_path,
            artifact_id=f"{page_id or task_id}_preview",
            kind=_legacy_kind("page_png", preview_path),
            page_id=page_id,
            editability="not_applicable",
        )

    canonical = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "source_schema_version": schema_version,
        "run_id": run_id,
        "session_id": session_id,
        "task_id": task_id,
        "beat_id": beat_id,
        "page_id": page_id,
        "producer": {
            "capability": str(result.get("tool") or "ppt-deck-pro-max"),
            "version": str(result.get("producer_version") or result.get("version") or "unknown"),
            "source_ref": str(result.get("source_ref") or result.get("source_sha") or "unknown"),
        },
        "tool": str(result.get("tool") or "ppt-deck-pro-max"),
        "status": status,
        "source_fingerprint": source_fingerprint,
        "artifacts": artifacts,
        "artifact_type": artifact_type,
        "artifact_path": artifact_path,
        "preview_path": preview_path,
        "provenance": result.get("provenance") if isinstance(result.get("provenance"), dict) else {},
        "notes": str(result.get("notes") or result.get("summary") or ""),
        "errors": result.get("errors", []),
        "created_at": str(result.get("created_at") or _utc_now()),
    }
    if preview_descriptor:
        canonical["preview"] = preview_descriptor
    if status == "failed" and not canonical["errors"]:
        canonical["errors"] = [{"code": "external_generation_failed", "message": canonical["notes"] or "Generation failed."}]
    return canonical


# --------------------------------------------------------------------------- #
# Prepare handoff
# --------------------------------------------------------------------------- #


def prepare_generation_handoff(run_dir: str | Path) -> dict[str, Any]:
    """Enhance generation tasks with handoff fields for build tools.

    Reads existing generation_tasks and adds workspace_refs, quality_requirements,
    claim_ids, evidence_refs where available.
    """
    root = ensure_run_dirs(run_dir)

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        request = read_json(request_path)
        run_id = str(request.get("run_id", ""))

    # Load page tasks for claim/evidence context.
    page_tasks_data: dict[str, Any] = {}
    if (root / PAGE_TASKS_NAME).exists():
        try:
            page_tasks_data = read_json(root / PAGE_TASKS_NAME)
        except RunStateError:
            pass

    beat_planning_map = {
        t.get("beat_id"): t.get("planning", {})
        for t in page_tasks_data.get("tasks", [])
        if isinstance(t, dict)
    }

    # Load existing generation tasks.
    tasks_dir = root / TASKS_DIR
    if not tasks_dir.exists():
        raise GenerationHandbackError(
            "No generation_tasks/ directory found. Run create-generation-tasks first."
        )

    index_path = tasks_dir / "index.json"
    if not index_path.exists():
        raise GenerationHandbackError(
            "generation_tasks/index.json not found. Run create-generation-tasks first."
        )

    index_data = read_json(index_path)
    # task_builder.py writes {"tasks": [...]} with task dicts containing task_id.
    # Fall back to "task_ids" for forward compatibility.
    raw_tasks = index_data.get("tasks", [])
    if raw_tasks and isinstance(raw_tasks[0], dict):
        task_ids = [t.get("task_id", "") for t in raw_tasks if isinstance(t, dict)]
    else:
        task_ids = index_data.get("task_ids", raw_tasks)

    # Load claim-evidence graph for claim_ids / evidence_refs.
    ceg_path = root / "claim_evidence_graph.json"
    ceg: dict[str, Any] = {}
    if ceg_path.exists():
        try:
            ceg = read_json(ceg_path)
        except RunStateError:
            pass

    # Build claim -> beat mapping.
    claim_ids_for_beat: dict[str, list[str]] = {}
    for claim in ceg.get("claims", []):
        if not isinstance(claim, dict):
            continue
        for page_ref in claim.get("page_refs", []):
            claim_ids_for_beat.setdefault(page_ref, []).append(claim.get("claim_id", ""))

    enhanced: list[str] = []
    enhanced_tasks: dict[str, dict[str, Any]] = {}
    for task_id in task_ids:
        task_path = tasks_dir / f"{task_id}.json"
        if not task_path.exists():
            continue
        try:
            task = read_json(task_path)
        except RunStateError:
            continue

        beat_id = task.get("beat_id", "")
        planning = beat_planning_map.get(beat_id, {})

        # Add handoff fields.
        task["schema_version"] = HANDOFF_SCHEMA_VERSION
        task["run_id"] = run_id
        task["claim_ids"] = claim_ids_for_beat.get(beat_id, [])
        task["evidence_refs"] = planning.get("evidence_need", [])
        task.setdefault(
            "customer_visible_content",
            {
                "title": task.get("page_title", ""),
                "body_brief": task.get("generation_brief", ""),
                "evidence_summary": planning.get("evidence_need", ""),
            },
        )
        task.setdefault("speaker_notes", "")
        task.setdefault(
            "internal_production_notes",
            {
                "layout_instruction": task.get("visual_need", ""),
                "reference_slide_required": bool(task.get("reference_slide_required")),
                "reference_slide": task.get("reference_slide"),
            },
        )
        task.setdefault(
            "content_boundary",
            {
                "slide_text_source": "customer_visible_content only",
                "speaker_notes_source": "speaker_notes only",
                "never_render_to_slide_text": [
                    "internal_production_notes",
                    "layout_instruction",
                    "reference_slide",
                    "task metadata",
                ],
            },
        )
        task["workspace_refs"] = [
            "visual-system/spec_lock.md",
            "structure-assets/page_archetypes.md",
        ]
        task["quality_requirements"] = [
            "页面必须有主观点",
            "必须说明证据如何支撑判断",
            "PPT 正文只能读取 customer_visible_content，不得渲染 internal_production_notes、布局说明或制作指令",
        ]
        task["expected_outputs"] = [
            "preview_path",
            "artifact_path",
            "generation_notes",
            "customer_visible_content",
        ]

        write_json(task_path, task)
        enhanced.append(task_id)
        enhanced_tasks[task_id] = task

    # Sync enhanced task data back into index so external tools reading
    # index.json see the same fields as individual task files.
    raw_tasks = index_data.get("tasks", [])
    if raw_tasks and isinstance(raw_tasks[0], dict):
        index_data["tasks"] = [
            enhanced_tasks.get(t.get("task_id", ""), t)
            for t in raw_tasks
            if isinstance(t, dict)
        ]

    # Update index.
    index_data["schema_version"] = HANDOFF_SCHEMA_VERSION
    index_data["run_id"] = run_id
    index_data["enhanced_at"] = datetime.now(timezone.utc).isoformat()
    write_json(index_path, index_data)

    append_typed_event(
        root,
        "artifact_written",
        "generation_handoff.prepared",
        f"Generation handoff prepared for {len(enhanced)} tasks.",
        run_id=run_id,
        refs=[f"{TASKS_DIR}/index.json"],
        payload={"task_count": len(enhanced)},
    )

    return {"status": "prepared", "task_count": len(enhanced), "run_id": run_id}


# --------------------------------------------------------------------------- #
# Validate result
# --------------------------------------------------------------------------- #


def validate_generation_result(
    result: dict[str, Any],
    *,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a generation result."""
    errors: list[str] = []

    if not isinstance(result, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}

    root = Path(run_dir).expanduser().resolve() if run_dir else None
    try:
        result = normalize_generation_result(result, run_dir=root)
    except GenerationHandbackError as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": []}

    if not result.get("beat_id") and result.get("page_id"):
        result["beat_id"] = str(result["page_id"])
    if result.get("beat_id") and not result.get("page_id"):
        result["page_id"] = str(result["beat_id"])

    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{RESULT_SCHEMA_VERSION}', "
            f"got '{result.get('schema_version')}'."
        )

    if not result.get("run_id"):
        errors.append("run_id is required.")
    if not result.get("tool"):
        errors.append("tool is required.")
    if not result.get("task_id"):
        errors.append("task_id is required.")
    if not result.get("session_id"):
        errors.append("session_id is required.")
    if not result.get("beat_id") and not result.get("page_id"):
        errors.append("beat_id/page_id is required.")
    producer = result.get("producer")
    if not isinstance(producer, dict):
        errors.append("producer is required.")
    else:
        for field in ("capability", "version", "source_ref"):
            if not producer.get(field):
                errors.append(f"producer.{field} is required.")
    fingerprint = str(result.get("source_fingerprint") or "")
    if not SHA256_RE.match(fingerprint):
        errors.append("source_fingerprint must be a lowercase SHA-256 hex digest.")
    if root is not None and fingerprint and SHA256_RE.match(fingerprint):
        expected_fingerprint = source_fingerprint_for_run(root)
        if fingerprint != expected_fingerprint:
            errors.append("source_fingerprint is stale.")
    if not result.get("created_at"):
        errors.append("created_at is required.")

    status = result.get("status", "")
    if status not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}.")

    run_mode = _run_mode(root)
    if status in {"completed", "partial"}:
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append("completed/partial result must have artifacts.")
        else:
            for index, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    errors.append(f"artifacts[{index}] must be an object.")
                    continue
                _validate_artifact(
                    artifact,
                    run_dir=root,
                    field_name=f"artifacts[{index}]",
                    errors=errors,
                    run_mode=run_mode,
                )
        preview = result.get("preview")
        if not isinstance(preview, dict):
            errors.append("completed/partial result must have preview.")
        else:
            _validate_artifact(
                preview,
                run_dir=root,
                field_name="preview",
                errors=errors,
                run_mode=run_mode,
            )

    if status == "failed":
        err_list = result.get("errors", [])
        if not err_list:
            errors.append("failed result must have errors array with at least one entry.")

    return {
        "valid": len(errors) == 0,
        "errors": errors if errors else [],
        "warnings": [],
    }


# --------------------------------------------------------------------------- #
# Import result
# --------------------------------------------------------------------------- #


def import_generation_result(
    run_dir: str | Path,
    result: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Import a generation result into the run."""
    root = ensure_run_dirs(run_dir)
    try:
        result = normalize_generation_result(result, run_dir=root)
    except GenerationHandbackError:
        raise
    validation = validate_generation_result(result, run_dir=root)
    if not validation["valid"]:
        raise GenerationHandbackError(
            "Invalid generation result: " + "; ".join(validation["errors"])
        )

    try:
        run_id = assert_external_result_matches_run(
            root,
            result.get("run_id", ""),
            artifact_name="generation result",
        )
    except RunStateError as exc:
        raise GenerationHandbackError(str(exc)) from exc
    task_id = str(result.get("task_id", ""))
    beat_id = str(result.get("beat_id", ""))
    status = str(result.get("status", ""))

    # Check locked page.
    page_tasks_path = root / PAGE_TASKS_NAME
    if page_tasks_path.exists():
        try:
            page_tasks = read_json(page_tasks_path)
        except RunStateError:
            page_tasks = {}
        for task in page_tasks.get("tasks", []):
            if isinstance(task, dict) and task.get("beat_id") == beat_id:
                if task.get("locked") and not force:
                    raise GenerationHandbackError(
                        f"Page {beat_id} is locked. Use --force to override."
                    )
                break

    # Write result.
    results_dir = root / RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    write_json(results_dir / f"{task_id}.json", result)

    # Update generation task status.
    task_path = root / TASKS_DIR / f"{task_id}.json"
    if task_path.exists():
        try:
            task = read_json(task_path)
            task["status"] = status
            if status == "completed" and result.get("artifact_path"):
                task["artifact_path"] = result["artifact_path"]
            if result.get("preview_path"):
                task["preview_path"] = result["preview_path"]
            write_json(task_path, task)
        except RunStateError:
            pass

    append_typed_event(
        root,
        "artifact_written",
        "generation_result.imported",
        f"Generation result imported: task={task_id}, beat={beat_id}, status={status}.",
        run_id=run_id,
        refs=[f"{RESULTS_DIR}/{task_id}.json", f"{TASKS_DIR}/{task_id}.json"],
        payload={
            "task_id": task_id,
            "beat_id": beat_id,
            "status": status,
            "tool": result.get("tool", ""),
        },
    )

    return {
        "status": "imported",
        "task_id": task_id,
        "beat_id": beat_id,
        "result_status": status,
        "preview_path": result.get("preview_path", ""),
        "artifact_path": result.get("artifact_path", ""),
    }


# --------------------------------------------------------------------------- #
# Refresh preview
# --------------------------------------------------------------------------- #


def refresh_preview_from_generation(run_dir: str | Path) -> dict[str, Any]:
    """Update preview_manifest.json with paths from generation results."""
    root = ensure_run_dirs(run_dir)

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        request = read_json(request_path)
        run_id = str(request.get("run_id", ""))

    # Load and validate preview manifest.
    if not (root / PREVIEW_MANIFEST_NAME).exists():
        raise GenerationHandbackError(
            "preview_manifest.json not found. Run build-preview first."
        )
    try:
        preview = load_manifest(root)
    except ManifestError as exc:
        raise GenerationHandbackError(f"Cannot read preview_manifest.json: {exc}") from exc

    # Load generation results.
    results_dir = root / RESULTS_DIR
    if not results_dir.exists():
        return {"status": "no_results", "run_id": run_id}

    updated: list[str] = []
    preview_pages = preview.get("pages", [])

    for result_file in sorted(results_dir.glob("*.json")):
        try:
            result = read_json(result_file)
        except RunStateError:
            continue
        if result.get("status") not in ("completed", "partial"):
            continue
        beat_id = str(result.get("beat_id", ""))
        result_preview_path = _preview_path(result)

        for page in preview_pages:
            if not isinstance(page, dict):
                continue
            page_key = page.get("beat_id") or page.get("page_id")
            if page_key == beat_id:
                if result_preview_path:
                    path = Path(result_preview_path)
                    if path.is_absolute() or ".." in path.parts:
                        raise GenerationHandbackError(
                            f"Generation preview_path must be a run-relative path: {result_preview_path}"
                        )
                    resolved = (root / path).resolve()
                    root_text = str(root)
                    resolved_text = str(resolved)
                    if resolved_text != root_text and not resolved_text.startswith(root_text + os.sep):
                        raise GenerationHandbackError(
                            f"Generation preview_path escapes run directory: {result_preview_path}"
                        )
                    if not resolved.exists():
                        raise GenerationHandbackError(
                            f"Generation preview_path does not exist: {result_preview_path}"
                        )
                    previous = page.get("preview_path", "")
                    if previous and previous != result_preview_path:
                        page["previous_preview_path"] = previous
                    page["preview_path"] = result_preview_path
                    page["source_preview_asset"] = result_preview_path
                    page["source_type"] = "generated"
                    page["generation_status"] = result.get("status", "")
                if not result_preview_path and result.get("status") == "partial":
                    page["preview_missing"] = True
                updated.append(beat_id)
                break

    try:
        write_manifest(root, preview)
    except ManifestError as exc:
        raise GenerationHandbackError(f"Cannot write preview_manifest.json: {exc}") from exc

    append_typed_event(
        root,
        "artifact_written",
        "preview_refreshed_from_generation",
        f"Preview refreshed from generation results: {len(updated)} pages updated.",
        run_id=run_id,
        refs=[PREVIEW_MANIFEST_NAME],
        payload={"updated_beats": updated},
    )

    return {"status": "refreshed", "updated": updated, "run_id": run_id}
