from __future__ import annotations

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
    ensure_run_dirs,
    read_json,
    write_json,
)

SCHEMA_VERSION = "deck_sourcing_plan.v1"
SCHEME_ALLOWED_DECISIONS = {"reuse", "adapt", "generate", "manual_placeholder"}
VALID_FILE_EXTENSIONS = {".json"}
PLAN_PATH = "sourcing_plan.json"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _collect_required_beats(run_dir: Path) -> list[str]:
    required: list[str] = []

    narrative_plan = read_json(run_dir / NARRATIVE_PLAN_NAME)
    for beat in narrative_plan.get("beats", []):
        beat_id = str(beat.get("beat_id") or "").strip()
        if beat_id and beat_id not in required:
            required.append(beat_id)

    page_tasks = read_json(run_dir / PAGE_TASKS_NAME)
    for task in page_tasks.get("tasks", []):
        beat_id = str(task.get("beat_id") or "").strip()
        if beat_id and beat_id not in required:
            required.append(beat_id)

    if not required:
        raise RunStateError(
            "narrative_plan.json and page_tasks.json have no beats/tasks. Run planning first."
        )

    return required


def _required_fields_for_decision(source_decision: str) -> tuple[bool, bool]:
    if source_decision in {"reuse", "adapt"}:
        return True, False
    if source_decision == "generate":
        return False, True
    if source_decision == "manual_placeholder":
        return False, True
    return False, True


def validate_sourcing_payload(payload: dict[str, Any], run_dir: Path) -> list[str]:
    errors: list[str] = []
    request = read_json(run_dir / REQUEST_NAME)
    run_mode = str(request.get("run_mode") or "production").strip().lower()
    strict_mode = run_mode in {"production", "benchmark"}
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        errors.append("run_id is required")

    source = str(payload.get("source") or "").strip()
    if source not in {"human", "agent"}:
        errors.append("source must be human or agent")

    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        errors.append("decisions must be an array")
        return errors
    if not decisions:
        errors.append("decisions cannot be empty")

    required_beats = _collect_required_beats(run_dir)
    decision_by_beat: set[str] = set()

    for index, decision in enumerate(decisions, start=1):
        if not isinstance(decision, dict):
            errors.append(f"decisions[{index}] must be an object")
            continue

        beat_id = str(decision.get("beat_id") or "").strip()
        if not beat_id:
            errors.append(f"decisions[{index}].beat_id is required")
        else:
            decision_by_beat.add(beat_id)

        source_decision = str(decision.get("source_decision") or "").strip()
        if source_decision not in SCHEME_ALLOWED_DECISIONS:
            errors.append(
                f"decisions[{index}].source_decision must be one of "
                f"{sorted(SCHEME_ALLOWED_DECISIONS)}"
            )
        if strict_mode and source_decision == "manual_placeholder":
            errors.append(
                f"decisions[{index}].source_decision=manual_placeholder is not allowed for {run_mode} runs"
            )

        if not str(decision.get("decision_reason") or "").strip():
            errors.append(f"decisions[{index}].decision_reason is required")

        require_selected_candidate, require_generation_brief = _required_fields_for_decision(source_decision)
        if require_selected_candidate:
            selected_candidate = decision.get("selected_candidate")
            if not isinstance(selected_candidate, dict):
                errors.append(
                    f"decisions[{index}].selected_candidate is required for source_decision={source_decision}"
                )
        if require_generation_brief:
            if not str(decision.get("generation_brief") or "").strip():
                errors.append(
                    f"decisions[{index}].generation_brief is required for source_decision={source_decision}"
                )

    missing_beats = [beat_id for beat_id in required_beats if beat_id not in decision_by_beat]
    if missing_beats:
        errors.append("missing decisions for beats: " + ", ".join(missing_beats))

    return errors


def _normalize_decisions(decisions: list[Any]) -> list[dict[str, Any]]:
    return [decision for decision in decisions if isinstance(decision, dict)]


def refresh_preview_sources_summary(run_dir: Path, decisions: list[dict[str, Any]]) -> bool:
    preview_path = run_dir / PREVIEW_MANIFEST_NAME
    if not preview_path.exists():
        return False

    preview = read_json(preview_path)
    pages = preview.get("pages")
    if not isinstance(pages, list):
        return False

    decision_lookup: dict[str, dict[str, Any]] = {}
    source_counts: dict[str, int] = {}
    covered = 0

    for decision in decisions:
        beat_id = str(decision.get("beat_id") or "").strip()
        if not beat_id:
            continue
        decision_lookup[beat_id] = decision
        source = str(decision.get("source_decision") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
        covered += 1

    for page in pages:
        if not isinstance(page, dict):
            continue
        beat_id = str(page.get("beat_id") or page.get("page_id") or "").strip()
        if not beat_id:
            continue
        decision = decision_lookup.get(beat_id)
        if not decision:
            continue
        page["source_decision"] = str(decision.get("source_decision") or page.get("source_decision") or "")
        page["decision_reason"] = str(decision.get("decision_reason") or page.get("decision_reason") or "")
        if decision.get("generation_brief"):
            page["generation_brief"] = str(decision.get("generation_brief"))

    preview["sourcing_summary"] = {
        "schema_version": "deck_sourcing_summary.v1",
        "source_counts": source_counts,
        "total_decisions": covered,
        "total_pages": len(pages),
    }
    preview["source_summary"] = {
        "decisions": len(decisions),
        "by_decision": source_counts,
        "covered_beats": len(decision_lookup),
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
        raise RunStateError("P0 only supports JSON sourcing plans. Use a .json input file.")

    existing = read_json(input_file)
    request = read_json(root / REQUEST_NAME)
    request_run_mode = str(request.get("run_mode") or "production").strip().lower()
    run_id = str(request.get("run_id") or root.name)

    existing["run_id"] = run_id
    existing["source"] = source
    errors = validate_sourcing_payload(existing, root)
    if errors:
        raise RunStateError("Invalid sourcing plan: " + "; ".join(errors))

    backup_dir = root / "overrides" / f"sourcing_{_utc_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    current_plan = root / PLAN_PATH
    if current_plan.exists():
        shutil.copy2(current_plan, backup_dir / PLAN_PATH)

    target = write_json(current_plan, existing)
    decisions = _normalize_decisions(existing.get("decisions", []))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_mode": request_run_mode,
        "source": source,
        "decisions": decisions,
    }
    payload["status"] = "imported"

    preview_refreshed = False
    if (root / PREVIEW_MANIFEST_NAME).exists():
        preview_refreshed = refresh_preview_sources_summary(root, decisions)
        append_event(
            root,
            "preview.manifest.refreshed",
            target=run_id,
            payload_ref=PLAN_PATH,
            data={
                "sourcing_plan": str(target.relative_to(root)),
                "decisions": len(decisions),
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
            "decisions": len(decisions),
            "preview_manifest_refreshed": preview_refreshed,
        },
    )

    return {
        **payload,
        "status": "imported",
        "run_dir": str(root),
        "input": str(input_file),
        "backup_dir": str(backup_dir),
        "decisions": len(decisions),
        "preview_manifest_refreshed": preview_refreshed,
    }


def validate_sourcing(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    plan_path = root / PLAN_PATH
    payload = read_json(plan_path)
    errors = validate_sourcing_payload(payload, root)
    valid = not errors
    request = read_json(root / REQUEST_NAME)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "valid" if valid else "invalid",
        "run_id": str(request.get("run_id") or root.name),
        "run_dir": str(root),
        "errors": errors,
        "decisions": len(payload.get("decisions", []) if isinstance(payload.get("decisions"), list) else []),
    }
