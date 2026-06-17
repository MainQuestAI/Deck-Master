from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from runtime.events import append_event
from runtime.import_log import append_import_log
from runtime.run_state import (
    RunStateError,
    assert_external_result_matches_run,
    ensure_run_dirs,
    read_json,
    write_json,
)


SELECTION_SCHEMA_VERSION = "deck_master_ppt_library_selection.v1"

CANONICAL_FIELDS = (
    "slide_id",
    "canonical_slide_id",
    "title",
    "text_summary",
    "source_file",
    "page_number",
    "screenshot_path",
    "confidence",
    "score",
    "win_rate",
    "reuse_count",
    "won_count",
    "lost_count",
    "narrative_role",
    "page_role",
    "importance_reason",
    "candidate_origin",
    "library_source",
)


class PPTLibraryClientError(ValueError):
    pass


def normalize_library_source(source: Any) -> str:
    value = str(source or "").strip().lower().replace("-", "_")
    if value in {"ppt_library", "library", "real"}:
        return "ppt_library"
    if value == "fixture":
        return "fixture"
    if value in {"imported", "external", "ppt_library_import"}:
        return "imported"
    if not value:
        return "none"
    return "imported"


def _selection_error(run_dir: Path, message: str, *, source_path: str | Path | None = None) -> PPTLibraryClientError:
    append_import_log(
        run_dir,
        import_type="ppt_library_selection",
        source="ppt-library",
        status="rejected",
        source_path=source_path,
        errors=[message],
    )
    return PPTLibraryClientError(message)


def build_select_slides_command(
    *,
    command: str,
    plan_path: Path,
    brief: str,
    output_path: Path,
    max_per_role: int = 5,
    ranking: str = "business",
    threshold: float = 0.0,
) -> list[str]:
    return [
        command,
        "select-slides",
        "--plan",
        str(plan_path),
        "--brief",
        brief,
        "--ranking",
        ranking,
        "--max-per-role",
        str(max_per_role),
        "--threshold",
        str(threshold),
        "--output",
        str(output_path),
    ]


def write_review_svg(path: Path, title: str, subtitle: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_subtitle = subtitle.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#f5f1e8"/>
  <rect x="64" y="64" width="1152" height="592" rx="28" fill="#111314"/>
  <text x="112" y="178" font-family="Avenir Next, Helvetica, sans-serif" font-size="34" fill="#d8a725" letter-spacing="4">PPT LIBRARY CANDIDATE</text>
  <text x="112" y="320" font-family="Avenir Next, Helvetica, sans-serif" font-size="64" font-weight="700" fill="#f2eee8">{safe_title}</text>
  <text x="112" y="410" font-family="Avenir Next, Helvetica, sans-serif" font-size="30" fill="#9ca6a6">{safe_subtitle}</text>
  <circle cx="1080" cy="540" r="92" fill="#d8a725"/>
  <text x="1034" y="556" font-family="Avenir Next, Helvetica, sans-serif" font-size="42" font-weight="700" fill="#111314">DM</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return path


def normalize_candidate(slide: dict[str, Any], *, beat_id: str, role: str, index: int) -> dict[str, Any]:
    candidate = {field: slide.get(field) for field in CANONICAL_FIELDS if field in slide}
    confidence = candidate.get("confidence")
    if confidence is None:
        confidence = candidate.get("score", 0)
    try:
        confidence_value = float(confidence or 0)
    except (TypeError, ValueError):
        confidence_value = 0.0
    candidate.update(
        {
            "candidate_id": str(slide.get("slide_id") or slide.get("canonical_slide_id") or f"{beat_id}_{index}"),
            "beat_id": beat_id,
            "role": role,
            "title": str(slide.get("title") or f"Candidate {index}"),
            "confidence": confidence_value,
            "screenshot_path": str(slide.get("screenshot_path") or ""),
            "source_file": str(slide.get("source_file") or ""),
            "page_number": slide.get("page_number", ""),
            "text_summary": str(slide.get("text_summary") or slide.get("importance_reason") or ""),
        }
    )
    return candidate


def extract_slides(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(payload.get("results"), list):
        return [("library", item) for item in payload["results"] if isinstance(item, dict)]
    report = payload.get("report") if isinstance(payload.get("report"), dict) else payload
    roles = report.get("roles") if isinstance(report, dict) else None
    if not isinstance(roles, list):
        return []
    slides: list[tuple[str, dict[str, Any]]] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        role_name = str(role.get("role") or "library")
        for slide in role.get("slides", []):
            if isinstance(slide, dict):
                slides.append((role_name, slide))
    return slides


def split_selection_by_beat(narrative_plan: dict[str, Any], payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    slides_by_role: dict[str, list[dict[str, Any]]] = {}
    for role, slide in extract_slides(payload):
        slides_by_role.setdefault(role, []).append(slide)
    result: dict[str, list[dict[str, Any]]] = {}
    for beat in narrative_plan.get("beats", []):
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id"))
        role = str(beat.get("role") or "")
        candidates = slides_by_role.get(role, []) or slides_by_role.get("library", [])
        result[beat_id] = [
            normalize_candidate(candidate, beat_id=beat_id, role=role, index=index)
            for index, candidate in enumerate(candidates, start=1)
        ]
    return result


def simulated_candidates_for_beat(run_dir: Path, beat: dict[str, Any]) -> list[dict[str, Any]]:
    role = str(beat.get("role") or "")
    title = str(beat.get("page_title") or role)
    beat_id = str(beat.get("beat_id"))
    if role == "case":
        return []
    if role == "architecture":
        return []
    confidence = 0.86 if role in {"opener", "problem"} else 0.62
    screenshot = write_review_svg(
        run_dir / "placeholders" / f"library_{beat_id}.svg",
        title,
        str(beat.get("reuse_query") or ""),
    )
    return [
        {
            "candidate_id": f"fixture_{beat_id}",
            "slide_id": f"fixture_{beat_id}",
            "canonical_slide_id": f"canonical_{beat_id}",
            "beat_id": beat_id,
            "role": role,
            "title": f"历史页候选：{title}",
            "text_summary": str(beat.get("content_goal") or ""),
            "source_file": "/Users/dingcheng/Workspace/_resources/方案库/通用方案/fixture-history-deck.pptx",
            "page_number": int(beat.get("order") or 1),
            "screenshot_path": str(screenshot),
            "confidence": confidence,
            "score": confidence,
            "win_rate": 0.67 if role in {"opener", "problem"} else 0.45,
            "reuse_count": 3 if role in {"opener", "problem"} else 1,
            "won_count": 2 if role in {"opener", "problem"} else 0,
            "lost_count": 1,
            "narrative_role": role,
            "importance_reason": "Fixture candidate produced because PPT Library is unavailable or disabled.",
        }
    ]


def write_library_results(run_dir: Path, by_beat: dict[str, list[dict[str, Any]]], *, source: str) -> dict[str, Any]:
    root = run_dir / "library_results"
    by_beat_dir = root / "by_beat"
    by_beat_dir.mkdir(parents=True, exist_ok=True)
    normalized_source = normalize_library_source(source)
    enriched_by_beat: dict[str, list[dict[str, Any]]] = {}
    for beat_id, candidates in by_beat.items():
        enriched_candidates = []
        for candidate in candidates:
            enriched = dict(candidate)
            enriched.setdefault("library_source", normalized_source)
            enriched.setdefault("candidate_origin", normalized_source)
            enriched_candidates.append(enriched)
        enriched_by_beat[beat_id] = enriched_candidates
        (by_beat_dir / f"{beat_id}.json").write_text(
            json.dumps({"beat_id": beat_id, "source": normalized_source, "candidates": enriched_candidates}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    payload = {"source": normalized_source, "library_source": normalized_source, "by_beat": enriched_by_beat}
    (root / "selection.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _normalize_selection_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") != SELECTION_SCHEMA_VERSION:
        raise PPTLibraryClientError(
            f"schema_version must be '{SELECTION_SCHEMA_VERSION}', got '{payload.get('schema_version')}'."
        )

    if isinstance(payload.get("selections"), list):
        return [item for item in payload["selections"] if isinstance(item, dict)]

    if isinstance(payload.get("by_beat"), dict):
        items: list[dict[str, Any]] = []
        for beat_id, candidates in payload["by_beat"].items():
            items.append({"beat_id": beat_id, "candidates": candidates})
        return items

    if isinstance(payload.get("beats"), list):
        return [item for item in payload["beats"] if isinstance(item, dict)]

    raise PPTLibraryClientError("selection payload must contain selections, by_beat, or beats.")


def validate_library_selection(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}
    if payload.get("schema_version") != SELECTION_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{SELECTION_SCHEMA_VERSION}', got '{payload.get('schema_version')}'."
        )
    if not payload.get("run_id"):
        errors.append("run_id is required.")
    try:
        items = _normalize_selection_payload(payload) if not errors else []
    except PPTLibraryClientError as exc:
        errors.append(str(exc))
        items = []
    if not items and not errors:
        warnings.append("No library selections were provided.")
    for index, item in enumerate(items):
        beat_id = item.get("beat_id") or item.get("page_task_id")
        if not beat_id:
            errors.append(f"selections[{index}].beat_id or page_task_id is required.")
        candidates = item.get("candidates", item.get("slides", item.get("results", [])))
        if candidates is None:
            candidates = []
        if not isinstance(candidates, list):
            errors.append(f"selections[{index}].candidates must be an array.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _selection_to_by_beat(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_beat: dict[str, list[dict[str, Any]]] = {}
    for item in _normalize_selection_payload(payload):
        beat_id = str(item.get("beat_id") or item.get("page_task_id") or "")
        role = str(item.get("role") or item.get("page_role") or "library")
        page_task_id = str(item.get("page_task_id") or beat_id)
        slot_id = str(item.get("slot_id") or "")
        query_trace_id = str(item.get("query_trace_id") or "")
        raw_candidates = item.get("candidates", item.get("slides", item.get("results", [])))
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        candidates: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_candidates, start=1):
            if not isinstance(raw, dict):
                continue
            candidate = normalize_candidate(raw, beat_id=beat_id, role=role, index=index)
            candidate["page_task_id"] = str(raw.get("page_task_id") or page_task_id)
            candidate["slot_id"] = str(raw.get("slot_id") or slot_id)
            candidate["query_trace_id"] = str(raw.get("query_trace_id") or query_trace_id)
            candidates.append(candidate)
        by_beat.setdefault(beat_id, []).extend(candidates)
    return by_beat


def import_library_selection(run_dir: str | Path, input_path: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    source_path = Path(input_path).expanduser().resolve()
    try:
        payload = read_json(source_path)
    except RunStateError as exc:
        raise _selection_error(root, str(exc), source_path=source_path) from exc

    validation = validate_library_selection(payload)
    if not validation["valid"]:
        raise _selection_error(root, "; ".join(validation["errors"]), source_path=source_path)

    try:
        run_id = assert_external_result_matches_run(
            root,
            payload.get("run_id", ""),
            artifact_name="PPT Library selection",
        )
    except RunStateError as exc:
        raise _selection_error(root, str(exc), source_path=source_path) from exc

    by_beat = _selection_to_by_beat(payload)
    legacy = write_library_results(root, by_beat, source="imported")
    canonical = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "run_id": run_id,
        "source": "imported",
        "upstream_source": payload.get("source", ""),
        "by_beat": legacy.get("by_beat", {}),
        "warnings": validation.get("warnings", []),
        "source_schema_version": payload.get("schema_version"),
    }
    canonical_path = write_json(root / "external" / "ppt_library" / "library_results.json", canonical)
    append_import_log(
        root,
        import_type="ppt_library_selection",
        source="ppt-library",
        status="imported",
        source_path=source_path,
        canonical_refs=[str(canonical_path.relative_to(root))],
        legacy_refs=["library_results/selection.json", "library_results/by_beat/"],
        warnings=validation.get("warnings", []),
        payload={"beat_count": len(by_beat), "candidate_count": sum(len(v) for v in by_beat.values())},
    )
    append_event(root, "ppt_library.selection.imported", target="external/ppt_library/library_results.json", payload_ref="library_results/selection.json")
    return {
        "status": "imported",
        "run_id": run_id,
        "beat_count": len(by_beat),
        "candidate_count": sum(len(v) for v in by_beat.values()),
        "canonical_path": str(canonical_path.relative_to(root)),
        "legacy_path": "library_results/selection.json",
        "selection": legacy,
    }


def run_library_selection(
    *,
    narrative_plan: dict[str, Any],
    narrative_plan_path: Path,
    request: dict[str, Any],
    run_dir: Path,
    mode: str = "auto",
    command: str = "ppt-lib",
    allow_fixture_fallback: bool = False,
) -> dict[str, Any]:
    if mode not in {"auto", "real", "fixture"}:
        raise PPTLibraryClientError("mode must be auto, real, or fixture.")

    output_path = run_dir / "library_results" / "selection.raw.json"
    can_run_real = mode == "real" or (mode == "auto" and shutil.which(command))
    run_mode = str(request.get("run_mode") or "").strip().lower()
    production_guard = run_mode == "production" and not allow_fixture_fallback
    fallback_message = (
        "PPT Library fixture fallback blocked for production run. "
        "Use --allow-fixture-library-fallback only for an explicit demo/smoke downgrade."
    )
    if can_run_real:
        cmd = build_select_slides_command(
            command=command,
            plan_path=narrative_plan_path,
            brief=str(request.get("brief") or request.get("business_goal") or ""),
            output_path=output_path,
        )
        append_event(run_dir, "ppt_library.select_slides.started", target=" ".join(cmd))
        completed = subprocess.run(cmd, cwd=run_dir, text=True, capture_output=True, check=False)
        if completed.returncode == 0 and output_path.exists():
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            by_beat = split_selection_by_beat(narrative_plan, payload)
            append_event(run_dir, "ppt_library.select_slides.completed", payload_ref="library_results/selection.raw.json")
            return write_library_results(run_dir, by_beat, source="ppt_library")
        if mode == "real":
            append_event(
                run_dir,
                "ppt_library.select_slides.failed",
                status="error",
                error=completed.stderr.strip() or completed.stdout.strip() or "ppt-lib failed.",
            )
            raise PPTLibraryClientError("PPT Library command failed.")
        append_event(
            run_dir,
            "ppt_library.select_slides.fallback",
            status="warning",
            error=completed.stderr.strip() or completed.stdout.strip() or "ppt-lib failed; using fixture.",
        )
        if production_guard:
            raise PPTLibraryClientError(fallback_message)
    elif production_guard and mode in {"auto", "fixture"}:
        append_event(run_dir, "ppt_library.fixture.blocked", status="error", error=fallback_message)
        raise PPTLibraryClientError(fallback_message)

    by_beat = {
        str(beat.get("beat_id")): simulated_candidates_for_beat(run_dir, beat)
        for beat in narrative_plan.get("beats", [])
        if isinstance(beat, dict)
    }
    append_event(run_dir, "ppt_library.fixture.completed", status="warning", payload_ref="library_results/selection.json")
    return write_library_results(run_dir, by_beat, source="fixture")
