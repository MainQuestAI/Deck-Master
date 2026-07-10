from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.run_state import read_json
from uat.report import build_check, build_uat_report, write_uat_report


def _run_id(run_dir: Path) -> str:
    request_path = run_dir / "request.json"
    if request_path.exists():
        try:
            return str(read_json(request_path).get("run_id") or run_dir.name)
        except Exception:
            return run_dir.name
    return run_dir.name


def _beats(run_dir: Path, payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_beat = payload.get("by_beat")
    if isinstance(by_beat, dict):
        return {
            str(beat_id): [item for item in candidates if isinstance(item, dict)]
            for beat_id, candidates in by_beat.items()
            if isinstance(candidates, list)
        }
    if isinstance(payload.get("candidates"), list):
        return {"library": [item for item in payload["candidates"] if isinstance(item, dict)]}
    by_beat_dir = run_dir / "library_results" / "by_beat"
    if not by_beat_dir.exists():
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(by_beat_dir.glob("*.json")):
        try:
            item = read_json(path)
        except Exception:
            continue
        candidates = item.get("candidates", [])
        if isinstance(candidates, list):
            result[path.stem] = [candidate for candidate in candidates if isinstance(candidate, dict)]
    return result


def _selection_groups(
    run_dir: Path,
    payload: dict[str, Any],
) -> list[tuple[str, dict[str, Any], list[dict[str, Any]]]]:
    if payload.get("schema_version") == "deck_master_ppt_library_selection.v2":
        selections = payload.get("selections") if isinstance(payload.get("selections"), list) else []
        return [
            (
                str(item.get("beat_id") or f"selection-{index + 1}"),
                item,
                [candidate for candidate in item.get("candidates", []) if isinstance(candidate, dict)],
            )
            for index, item in enumerate(selections)
            if isinstance(item, dict)
        ]
    return [(beat_id, {}, candidates) for beat_id, candidates in _beats(run_dir, payload).items()]


def run_ppt_library_uat(
    run_dir: Path,
    input_path: Path,
    *,
    require_screenshot: bool = False,
    min_candidate_coverage: float = 0.7,
    min_screenshot_coverage: float = 0.8,
    min_confidence: float = 0.4,
    write: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    recommendations: list[str] = []
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        checks.append(build_check("selection_json_readable", True, "error", "selection JSON is readable.", refs=[str(input_path)]))
    except json.JSONDecodeError as exc:
        checks.append(build_check("selection_json_readable", False, "error", f"Bad JSON: {exc.msg}", refs=[str(input_path)]))
        report = build_uat_report(run_dir, "ppt_library", checks, {}, ["Fix selection JSON."])
        return write_uat_report(run_dir, "ppt_library_uat", report) if write else report

    expected_run_id = _run_id(run_dir)
    actual_run_id = str(payload.get("run_id") or expected_run_id)
    checks.append(build_check("run_id_matches", actual_run_id == expected_run_id, "error", f"run_id is {actual_run_id}, expected {expected_run_id}."))

    schema_version = str(payload.get("schema_version") or "")
    is_v2 = schema_version == "deck_master_ppt_library_selection.v2"
    groups = _selection_groups(run_dir, payload)
    candidate_count = sum(len(candidates) for _, _, candidates in groups)
    beat_count = len(groups)
    beats_with_candidates = sum(1 for _, _, candidates in groups if candidates)
    candidate_coverage = round(beats_with_candidates / beat_count, 2) if beat_count else 0.0
    checks.append(
        build_check(
            "candidate_coverage",
            candidate_coverage >= min_candidate_coverage,
            "warning",
            f"candidate coverage {candidate_coverage} below {min_candidate_coverage}.",
        )
    )
    if is_v2:
        checks.append(
            build_check(
                "selection.preview_degraded",
                not bool(payload.get("preview_degraded")),
                "error" if require_screenshot else "warning",
                "selection preview is degraded.",
            )
        )

    screenshot_count = 0
    canonical_count = 0
    confidence_sum = 0.0
    confidence_seen = 0
    missing_screenshot_count = 0
    duplicate_slide_id_count = 0
    seen_slide_ids: set[str] = set()

    for beat_id, selection, candidates in groups:
        page_task_id = str(selection.get("page_task_id") or "")
        query_trace_id = str(selection.get("query_trace_id") or "")
        if is_v2:
            checks.append(build_check(f"{beat_id}.page_task_id", bool(page_task_id), "error", f"{beat_id} missing page_task_id."))
            checks.append(build_check(f"{beat_id}.query_trace_id", bool(query_trace_id), "error", f"{beat_id} missing query_trace_id."))
            degraded = bool(selection.get("preview_degraded"))
            checks.append(
                build_check(
                    f"{beat_id}.preview_degraded",
                    not degraded,
                    "error" if require_screenshot else "warning",
                    f"{beat_id} preview is degraded.",
                )
            )
        for index, candidate in enumerate(candidates):
            ref = f"{beat_id}[{index}]"
            identity = candidate.get("asset_key") if is_v2 else (candidate.get("slide_id") or candidate.get("candidate_id"))
            checks.append(build_check(f"{ref}.identity", bool(identity), "error", f"{ref} missing candidate identity."))
            if identity:
                identity_scope = f"{page_task_id}:{identity}" if is_v2 else str(identity)
                duplicate = identity_scope in seen_slide_ids
                duplicate_slide_id_count += 1 if duplicate else 0
                seen_slide_ids.add(identity_scope)
                checks.append(build_check(f"{ref}.duplicate_identity", not duplicate, "warning", f"{ref} duplicate candidate identity."))
            if is_v2:
                for field in ("candidate_id", "asset_key", "source_asset_id"):
                    checks.append(build_check(f"{ref}.{field}", bool(candidate.get(field)), "error", f"{ref} missing {field}."))
                for field in ("source_file", "source_path"):
                    checks.append(build_check(f"{ref}.raw_{field}_absent", field not in candidate, "error", f"{ref} contains forbidden {field}."))
                candidate_page_task_id = candidate.get("page_task_id")
                candidate_trace_id = candidate.get("query_trace_id")
                if candidate_page_task_id not in {None, ""}:
                    checks.append(build_check(f"{ref}.page_task_id_match", str(candidate_page_task_id) == page_task_id, "error", f"{ref} page_task_id does not match selection."))
                if candidate_trace_id not in {None, ""}:
                    checks.append(build_check(f"{ref}.query_trace_id_match", str(candidate_trace_id) == query_trace_id, "error", f"{ref} query_trace_id does not match selection."))
                if candidate.get("asset_key") and candidate.get("source_asset_id"):
                    canonical_count += 1
            else:
                checks.append(build_check(f"{ref}.source_file", bool(candidate.get("source_file")), "error", f"{ref} missing source_file."))
                if candidate.get("canonical_slide_id"):
                    canonical_count += 1
                else:
                    checks.append(build_check(f"{ref}.canonical_slide_id", False, "warning", f"{ref} missing canonical_slide_id."))
            checks.append(build_check(f"{ref}.page_number", candidate.get("page_number") not in {None, ""}, "warning", f"{ref} missing page_number."))
            if candidate.get("title") and candidate.get("text_summary"):
                checks.append(build_check(f"{ref}.title_text", True, "warning", f"{ref} has title/text_summary."))
            else:
                checks.append(build_check(f"{ref}.title_text", False, "warning", f"{ref} missing title or text_summary."))

            screenshot = str(
                (candidate.get("screenshot_ref") if is_v2 else candidate.get("screenshot_path")) or ""
            )
            screenshot_exists = False
            if screenshot:
                screenshot_path = Path(screenshot)
                run_relative = not screenshot_path.is_absolute() and ".." not in screenshot_path.parts
                if run_relative:
                    screenshot_path = run_dir / screenshot
                    screenshot_exists = screenshot_path.is_file()
            if screenshot_exists:
                screenshot_count += 1
            else:
                missing_screenshot_count += 1
            checks.append(build_check(f"{ref}.screenshot", bool(screenshot) and screenshot_exists, "error" if require_screenshot else "warning", f"{ref} screenshot missing or not found."))

            try:
                confidence = float(candidate.get("confidence", 0))
                confidence_sum += confidence
                confidence_seen += 1
                checks.append(build_check(f"{ref}.confidence_range", 0 <= confidence <= 1, "error", f"{ref} confidence outside 0-1."))
                checks.append(build_check(f"{ref}.confidence_min", confidence >= min_confidence, "warning", f"{ref} confidence below {min_confidence}."))
            except (TypeError, ValueError):
                checks.append(build_check(f"{ref}.confidence_range", False, "error", f"{ref} confidence is not numeric."))

    screenshot_coverage = round(screenshot_count / candidate_count, 2) if candidate_count else 0.0
    checks.append(
        build_check(
            "screenshot_coverage",
            screenshot_coverage >= min_screenshot_coverage,
            "error" if require_screenshot else "warning",
            f"screenshot coverage {screenshot_coverage} below {min_screenshot_coverage}.",
        )
    )
    canonical_id_coverage = round(canonical_count / candidate_count, 2) if candidate_count else 0.0
    avg_confidence = round(confidence_sum / confidence_seen, 2) if confidence_seen else 0.0
    if missing_screenshot_count:
        recommendations.append("补齐 screenshot_ref，确保 Review Cockpit 可预览候选页。" if is_v2 else "补齐 screenshot_path，确保 Review Cockpit 可预览候选页。")
    if not is_v2 and canonical_id_coverage < 1:
        recommendations.append("补齐 canonical_slide_id 以支持长期 asset feedback。")
    metrics = {
        "selection_schema": schema_version,
        "candidate_count": candidate_count,
        "beat_count": beat_count,
        "beats_with_candidates": beats_with_candidates,
        "candidate_coverage": candidate_coverage,
        "screenshot_coverage": screenshot_coverage,
        "canonical_id_coverage": canonical_id_coverage,
        "avg_confidence": avg_confidence,
        "missing_screenshot_count": missing_screenshot_count,
        "duplicate_slide_id_count": duplicate_slide_id_count,
    }
    report = build_uat_report(run_dir, "ppt_library", checks, metrics, recommendations)
    return write_uat_report(run_dir, "ppt_library_uat", report) if write else report
