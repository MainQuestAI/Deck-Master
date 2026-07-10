from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preview.manifest import write_manifest
from runtime.events import append_event
from runtime.run_state import (
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    REQUEST_NAME,
    RunStateError,
    assert_external_result_matches_run,
    ensure_run_dirs,
    read_json,
    write_json,
)
from sourcing.plan import ALL_DECISIONS, SCHEMA_VERSION
from sourcing.reader import canonicalize_sourcing_plan

VALID_FILE_EXTENSIONS = {".json"}
PLAN_PATH = "sourcing_plan.json"
SCHEMA_NAME = "sourcing-plan.v2.schema.json"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _resolve_sourcing_schema_path(root: Path | None = None) -> Path:
    runtime_root = root or Path(__file__).resolve().parents[2]
    candidates = (
        runtime_root / "docs" / "contracts" / SCHEMA_NAME,
        runtime_root / "contracts" / SCHEMA_NAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    checked = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Sourcing plan schema not found; checked: {checked}")


def _collect_required_pages(run_dir: Path) -> list[tuple[str, str]]:
    page_tasks = read_json(run_dir / PAGE_TASKS_NAME)
    required: list[tuple[str, str]] = []
    for task in page_tasks.get("tasks", []):
        if not isinstance(task, dict):
            continue
        page_id = str(task.get("page_id") or task.get("beat_id") or "").strip()
        page_task_id = str(task.get("page_task_id") or task.get("task_id") or page_id).strip()
        if page_id and page_task_id:
            required.append((page_id, page_task_id))
    if required:
        return required

    narrative_plan = read_json(run_dir / NARRATIVE_PLAN_NAME)
    for beat in narrative_plan.get("beats", []):
        if not isinstance(beat, dict):
            continue
        page_id = str(beat.get("beat_id") or "").strip()
        page_task_id = str(
            beat.get("page_task_id")
            or beat.get("task_id")
            or beat.get("page_id")
            or page_id
        ).strip()
        if page_id and page_task_id:
            required.append((page_id, page_task_id))
    if not required:
        raise RunStateError("narrative_plan.json and page_tasks.json have no beats/tasks. Run planning first.")
    return required


def _align_legacy_page_task_ids(payload: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    if payload.get("migrated_from") != "deck_sourcing_plan.v1":
        return payload
    task_by_page = dict(_collect_required_pages(run_dir))
    for page in payload.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("page_id") or "")
        page_task_id = task_by_page.get(page_id)
        if not page_task_id:
            continue
        page["page_task_id"] = page_task_id
        for source in page.get("selected_sources", []):
            if isinstance(source, dict):
                source["page_task_id"] = page_task_id
    return payload


def _schema_errors(payload: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:  # pragma: no cover - runtime dependency
        return ["jsonschema is required to validate sourcing plans"]

    try:
        schema_path = _resolve_sourcing_schema_path()
    except FileNotFoundError as exc:
        return [str(exc)]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "payload"
        errors.append(f"{location}: {error.message}")
    return errors


def validate_sourcing_payload(payload: dict[str, Any], run_dir: Path) -> list[str]:
    errors = _schema_errors(payload)
    request = read_json(run_dir / REQUEST_NAME)
    run_mode = str(request.get("run_mode") or "production").strip().lower()
    strict_mode = run_mode in {"production", "benchmark"}

    pages = payload.get("pages")
    if not isinstance(pages, list):
        return errors or ["pages must be an array"]

    seen_page_ids: set[str] = set()
    seen_page_task_ids: set[str] = set()
    actual_pairs: set[tuple[str, str]] = set()
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("page_id") or "").strip()
        page_task_id = str(page.get("page_task_id") or "").strip()
        if page_id in seen_page_ids:
            errors.append(f"duplicate page_id: {page_id}")
        if page_task_id in seen_page_task_ids:
            errors.append(f"duplicate page_task_id: {page_task_id}")
        if page_id:
            seen_page_ids.add(page_id)
        if page_task_id:
            seen_page_task_ids.add(page_task_id)
        if page_id and page_task_id:
            actual_pairs.add((page_id, page_task_id))

        decision = str(page.get("decision") or "")
        if decision not in ALL_DECISIONS:
            errors.append(f"pages[{index}].decision is invalid")
        if strict_mode and decision == "manual":
            errors.append(
                f"pages[{index}].decision=manual; manual_placeholder is not allowed for {run_mode} runs"
            )

        selected_sources = page.get("selected_sources")
        if decision in {"reuse", "adapt"} and not selected_sources:
            errors.append(f"pages[{index}].selected_sources is required for decision={decision}")
        if isinstance(selected_sources, list):
            for source_index, source in enumerate(selected_sources, start=1):
                if not isinstance(source, dict):
                    continue
                for field in ("asset_key", "query_trace_id", "page_task_id"):
                    if not str(source.get(field) or "").strip():
                        errors.append(f"pages[{index}].selected_sources[{source_index}].{field} is required")
                source_page_task_id = str(source.get("page_task_id") or "").strip()
                if source_page_task_id and page_task_id and source_page_task_id != page_task_id:
                    errors.append(
                        f"pages[{index}].selected_sources[{source_index}].page_task_id must match page_task_id"
                    )

    required_pairs = set(_collect_required_pages(run_dir))
    missing = sorted(required_pairs - actual_pairs)
    unexpected = sorted(actual_pairs - required_pairs)
    if missing:
        errors.append("missing pages for page tasks: " + ", ".join(f"{page}/{task}" for page, task in missing))
    if unexpected:
        errors.append("unexpected page task identities: " + ", ".join(f"{page}/{task}" for page, task in unexpected))
    return errors


def refresh_preview_sources_summary(run_dir: Path, pages: list[dict[str, Any]]) -> bool:
    preview_path = run_dir / PREVIEW_MANIFEST_NAME
    if not preview_path.exists():
        return False
    preview = read_json(preview_path)
    preview_pages = preview.get("pages")
    if not isinstance(preview_pages, list):
        return False

    page_lookup: dict[str, dict[str, Any]] = {}
    source_counts: dict[str, int] = {}
    for page in pages:
        page_id = str(page.get("page_id") or "").strip()
        if not page_id:
            continue
        page_lookup[page_id] = page
        decision = str(page.get("decision") or "unknown")
        source_counts[decision] = source_counts.get(decision, 0) + 1

    for preview_page in preview_pages:
        if not isinstance(preview_page, dict):
            continue
        page_id = str(preview_page.get("beat_id") or preview_page.get("page_id") or "").strip()
        page = page_lookup.get(page_id)
        if not page:
            continue
        preview_page["source_decision"] = str(page.get("decision") or preview_page.get("source_decision") or "")
        preview_page["decision_reason"] = str(page.get("reason") or preview_page.get("decision_reason") or "")
        if page.get("generation_brief"):
            preview_page["generation_brief"] = str(page["generation_brief"])

    preview["sourcing_summary"] = {
        "schema_version": "deck_sourcing_summary.v1",
        "source_counts": source_counts,
        "total_decisions": len(page_lookup),
        "total_pages": len(preview_pages),
    }
    preview["source_summary"] = {
        "decisions": len(pages),
        "by_decision": source_counts,
        "covered_beats": len(page_lookup),
    }
    preview["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_manifest(run_dir, preview)
    return True


def import_sourcing(
    run_dir: str | Path,
    input_path: str | Path,
    *,
    source: str,
) -> dict[str, Any]:
    if source not in {"human", "agent"}:
        raise RunStateError("--source must be 'human' or 'agent'.")

    root = ensure_run_dirs(run_dir)
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise RunStateError(f"Sourcing plan input not found: {input_file}")
    if input_file.suffix.lower() not in VALID_FILE_EXTENSIONS:
        raise RunStateError("Only JSON sourcing plans are supported. Use a .json input file.")

    request = read_json(root / REQUEST_NAME)
    run_mode = str(request.get("run_mode") or "production").strip().lower()
    raw_payload = read_json(input_file)
    run_id = assert_external_result_matches_run(
        root,
        raw_payload.get("run_id") if isinstance(raw_payload, dict) else None,
        artifact_name="sourcing plan",
    )
    try:
        canonical = canonicalize_sourcing_plan(raw_payload)
    except ValueError as exc:
        raise RunStateError(f"Invalid sourcing plan: {exc}") from exc
    canonical["run_id"] = run_id
    canonical = _align_legacy_page_task_ids(canonical, root)
    errors = validate_sourcing_payload(canonical, root)
    if errors:
        raise RunStateError("Invalid sourcing plan: " + "; ".join(errors))

    backup_dir = root / "overrides" / f"sourcing_{_utc_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    current_plan = root / PLAN_PATH
    if current_plan.exists():
        shutil.copy2(current_plan, backup_dir / PLAN_PATH)
    target = write_json(current_plan, canonical)
    pages = [page for page in canonical.get("pages", []) if isinstance(page, dict)]

    preview_refreshed = False
    if (root / PREVIEW_MANIFEST_NAME).exists():
        preview_refreshed = refresh_preview_sources_summary(root, pages)
        append_event(
            root,
            "preview.manifest.refreshed",
            target=run_id,
            payload_ref=PLAN_PATH,
            data={
                "sourcing_plan": str(target.relative_to(root)),
                "pages": len(pages),
                "source_summary_updated": preview_refreshed,
            },
        )

    append_event(
        root,
        "sourcing.override.imported",
        target=run_id,
        payload_ref=str(target.relative_to(root)),
        data={
            "source": source,
            "input": str(input_file),
            "backup_dir": str(backup_dir),
            "pages": len(pages),
            "preview_manifest_refreshed": preview_refreshed,
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_mode": run_mode,
        "source": source,
        "status": "imported",
        "run_dir": str(root),
        "input": str(input_file),
        "backup_dir": str(backup_dir),
        "pages": len(pages),
        "preview_manifest_refreshed": preview_refreshed,
    }


def validate_sourcing(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    request = read_json(root / REQUEST_NAME)
    try:
        payload = canonicalize_sourcing_plan(read_json(root / PLAN_PATH))
        payload = _align_legacy_page_task_ids(payload, root)
        errors = validate_sourcing_payload(payload, root)
    except ValueError as exc:
        payload = {"pages": []}
        errors = [str(exc)]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "valid" if not errors else "invalid",
        "run_id": str(request.get("run_id") or root.name),
        "run_dir": str(root),
        "errors": errors,
        "pages": len(payload.get("pages", [])) if isinstance(payload.get("pages"), list) else 0,
    }
