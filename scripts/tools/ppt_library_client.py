from __future__ import annotations

import hashlib
import json
import re
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


BRIDGE_PLAN_SCHEMA_VERSION = "deck_master_ppt_library_bridge_plan.v1"
SELECTION_SCHEMA_VERSION_V1 = "deck_master_ppt_library_selection.v1"
SELECTION_SCHEMA_VERSION = "deck_master_ppt_library_selection.v2"

PASSTHROUGH_ROLES = {
    "opener",
    "problem",
    "solution",
    "architecture",
    "case",
    "roi",
    "cta",
    "appendix",
}
MAPPED_ROLES = {
    "business_context": "problem",
    "solution_overview": "solution",
    "capability_matrix": "solution",
    "capability_detail": "solution",
    "solution_detail": "solution",
    "process_flow": "architecture",
}
SEMANTIC_ONLY_ROLES = {
    "executive_summary": "adapt",
    "section_handoff": "adapt_only",
}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SAFE_DISPLAY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()\-]{0,127}$")


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


def _normalize_query(value: Any) -> str:
    return " ".join(str(value or "").split())


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _query_trace_id(run_id: str, beat_id: str, query: str) -> str:
    canonical = json.dumps(
        [run_id, beat_id, _normalize_query(query)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _sha256(canonical)


def _safe_identifier(value: Any, *, field: str) -> str:
    identifier = str(value or "").strip()
    if not identifier or not SAFE_ID_RE.fullmatch(identifier):
        raise PPTLibraryClientError(f"{field} must be a non-empty path-safe identifier.")
    return identifier


def _role_policy(role: str, run_mode: str) -> tuple[str, str | None, str, str]:
    if role in PASSTHROUGH_ROLES:
        return "passthrough", role, "reuse_or_adapt", ""
    if role in MAPPED_ROLES:
        return "mapped", MAPPED_ROLES[role], "reuse_or_adapt", ""
    if role in SEMANTIC_ONLY_ROLES:
        return "semantic_only", None, SEMANTIC_ONLY_ROLES[role], "SEMANTIC_ONLY_ROLE"
    if run_mode in {"production", "benchmark"}:
        raise PPTLibraryClientError(
            f"UNKNOWN_ROLE_BLOCKED: role '{role}' requires an explicit production strategy."
        )
    return "semantic_only", None, "adapt", "UNKNOWN_ROLE_SEMANTIC_FALLBACK"


def _page_task_map(page_tasks: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    tasks = page_tasks.get("tasks", []) if isinstance(page_tasks, dict) else []
    if not isinstance(tasks, list):
        return result
    for task in tasks:
        if not isinstance(task, dict) or not task.get("beat_id"):
            continue
        beat_id = str(task["beat_id"])
        page_task_id = task.get("page_task_id") or task.get("task_id") or task.get("page_id")
        if page_task_id:
            result[beat_id] = str(page_task_id)
    return result


def _beat_query(beats: list[dict[str, Any]], index: int) -> str:
    beat = beats[index]
    if str(beat.get("role") or "") == "section_handoff":
        adjacent_titles: list[str] = []
        if index > 0:
            adjacent_titles.append(str(beats[index - 1].get("page_title") or ""))
        if index + 1 < len(beats):
            adjacent_titles.append(str(beats[index + 1].get("page_title") or ""))
        query = _normalize_query(" ".join(title for title in adjacent_titles if title))
        if query:
            return query
    reuse_query = _normalize_query(beat.get("reuse_query"))
    if reuse_query:
        return reuse_query
    return _normalize_query(f"{beat.get('page_title', '')} {beat.get('content_goal', '')}")


def build_bridge_plan(
    narrative_plan: dict[str, Any],
    page_tasks: dict[str, Any],
    *,
    run_id: str,
    run_mode: str,
) -> dict[str, Any]:
    raw_beats = narrative_plan.get("beats", []) if isinstance(narrative_plan, dict) else []
    beats = [item for item in raw_beats if isinstance(item, dict)]
    task_map = _page_task_map(page_tasks)
    requests: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    normalized_run_mode = str(run_mode or "dev").strip().lower()

    for index, beat in enumerate(beats):
        beat_id = _safe_identifier(beat.get("beat_id"), field="beat_id")
        if beat_id in seen:
            raise PPTLibraryClientError(f"beat_id must be unique: {beat_id}")
        seen.add(beat_id)
        page_task_id = task_map.get(beat_id) or beat_id
        _safe_identifier(page_task_id, field="page_task_id")
        if beat_id not in task_map and "LEGACY_PAGE_TASK_ID_DERIVED" not in warnings:
            warnings.append("LEGACY_PAGE_TASK_ID_DERIVED")
        role_original = str(beat.get("role") or "").strip()
        role_strategy, role_mapped, default_reuse_policy, fallback_reason = _role_policy(
            role_original,
            normalized_run_mode,
        )
        query = _beat_query(beats, index)
        reuse_policy = str(beat.get("reuse_policy") or default_reuse_policy)
        requests.append(
            {
                "beat_id": beat_id,
                "page_task_id": page_task_id,
                "section_id": str(beat.get("section_id") or ""),
                "order": int(beat.get("order") or index + 1),
                "role_original": role_original,
                "role_strategy": role_strategy,
                "role_mapped": role_mapped,
                "query": query,
                "query_trace_id": _query_trace_id(run_id, beat_id, query),
                "reuse_policy": reuse_policy,
                "fallback_reason": fallback_reason,
            }
        )

    return {
        "schema_version": BRIDGE_PLAN_SCHEMA_VERSION,
        "run_id": str(run_id),
        "run_mode": normalized_run_mode,
        "requests": requests,
        "warnings": warnings,
    }


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


def build_search_command(*, command: str, query: str) -> list[str]:
    return [command, "search", query, "--ranking", "business", "--output", "json"]


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


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _confidence(value: Any) -> float:
    return max(0.0, min(1.0, _number(value)))


def _normalized_source_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _source_display_name(source_path: str, source_asset_id: str) -> str:
    basename = source_path.rsplit("/", 1)[-1].strip()
    if basename and basename not in {".", ".."} and ".." not in basename and SAFE_DISPLAY_RE.fullmatch(basename):
        return basename
    return f"PPT Library asset {source_asset_id[:8]}"


def _preview_ref(run_dir: Path, screenshot_path: Any, asset_key: str) -> tuple[str, str]:
    raw_path = str(screenshot_path or "").strip()
    if not raw_path:
        return "", "missing"
    source = Path(raw_path).expanduser()
    if not source.is_absolute():
        source = run_dir / source
    try:
        source = source.resolve()
        if not source.is_file():
            return "", "invalid"
        suffix = source.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,8}", source.suffix.lower()) else ".bin"
        preview_key = f"{asset_key}:{_normalized_source_path(raw_path)}"
        destination = run_dir / "preview_assets" / "ppt_library" / f"{_sha256(preview_key)[:16]}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination.resolve():
            shutil.copy2(source, destination)
        return destination.relative_to(run_dir).as_posix(), "ready"
    except (OSError, ValueError):
        return "", "invalid"


def normalize_candidate(
    slide: dict[str, Any],
    *,
    run_dir: Path,
    reuse_policy: str,
    index: int,
    candidate_origin: str = "ppt_library",
) -> tuple[dict[str, Any], str]:
    canonical_slide_id = str(slide.get("canonical_slide_id") or "").strip()
    slide_id = str(slide.get("slide_id") or "").strip()
    source_path = _normalized_source_path(slide.get("source_file") or slide.get("source_path"))
    page_number = slide.get("page_number", "")
    source_hash = _sha256(source_path) if source_path else ""
    if canonical_slide_id:
        asset_key = f"canonical:{canonical_slide_id}"
    elif source_path and str(page_number) != "":
        asset_key = f"source-page:{source_hash}:{page_number}"
    elif slide_id:
        asset_key = f"slide:{slide_id}"
    else:
        raise PPTLibraryClientError("CANDIDATE_IDENTITY_MISSING")

    source_asset_id = source_hash or _sha256(f"asset:{asset_key}")
    screenshot_ref, preview_status = _preview_ref(run_dir, slide.get("screenshot_path"), asset_key)
    score = _confidence(slide.get("score"))
    confidence = _confidence(slide.get("confidence") if slide.get("confidence") is not None else score)
    candidate_id = slide_id or canonical_slide_id or f"asset-{_sha256(asset_key)[:16]}"
    candidate = {
        "candidate_id": candidate_id,
        "slide_id": slide_id or None,
        "asset_key": asset_key,
        "title": str(slide.get("title") or f"Candidate {index}"),
        "text_summary": str(slide.get("text_summary") or slide.get("importance_reason") or ""),
        "page_number": page_number,
        "score": score,
        "confidence": confidence,
        "source_asset_id": source_asset_id,
        "source_display_name": _source_display_name(source_path, source_asset_id),
        "screenshot_ref": screenshot_ref,
        "candidate_origin": candidate_origin,
        "reuse_policy": reuse_policy,
    }
    return candidate, preview_status


def extract_slides(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        nested = extract_slides(data)
        if nested:
            return nested
    for field in ("results", "slides"):
        values = payload.get(field)
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)]
    report = payload.get("report") if isinstance(payload.get("report"), dict) else payload
    roles = report.get("roles") if isinstance(report, dict) else None
    if not isinstance(roles, list):
        return []
    slides: list[dict[str, Any]] = []
    for role in roles:
        if isinstance(role, dict) and isinstance(role.get("slides"), list):
            slides.extend(item for item in role["slides"] if isinstance(item, dict))
    return slides


def _normalize_candidates(
    slides: list[dict[str, Any]],
    *,
    run_dir: Path,
    reuse_policy: str,
    candidate_origin: str,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    by_asset: dict[str, dict[str, Any]] = {}
    statuses: dict[str, str] = {}
    warnings: list[str] = []
    for index, slide in enumerate(slides, start=1):
        try:
            candidate, preview_status = normalize_candidate(
                slide,
                run_dir=run_dir,
                reuse_policy=reuse_policy,
                index=index,
                candidate_origin=candidate_origin,
            )
        except PPTLibraryClientError as exc:
            if str(exc) == "CANDIDATE_IDENTITY_MISSING":
                warnings.append("CANDIDATE_IDENTITY_MISSING")
                continue
            raise
        asset_key = candidate["asset_key"]
        current = by_asset.get(asset_key)
        if current is None or candidate["score"] > current["score"]:
            by_asset[asset_key] = candidate
            statuses[asset_key] = preview_status
    candidates = sorted(by_asset.values(), key=lambda item: (-item["score"], item["asset_key"]))
    candidate_statuses = [statuses[item["asset_key"]] for item in candidates]
    if not candidates or "missing" in candidate_statuses:
        preview_status = "missing"
    elif "invalid" in candidate_statuses:
        preview_status = "invalid"
    else:
        preview_status = "ready"
    return candidates, preview_status, warnings


def simulated_candidates_for_beat(run_dir: Path, beat: dict[str, Any]) -> list[dict[str, Any]]:
    role = str(beat.get("role") or "")
    title = str(beat.get("page_title") or role)
    beat_id = str(beat.get("beat_id"))
    if role in {"case", "architecture"}:
        return []
    confidence = 0.86 if role in {"opener", "problem"} else 0.62
    screenshot = write_review_svg(
        run_dir / "preview_assets" / f"library_{beat_id}.svg",
        title,
        str(beat.get("reuse_query") or ""),
    )
    return [
        {
            "slide_id": f"fixture_{beat_id}",
            "canonical_slide_id": f"canonical_{beat_id}",
            "title": f"历史页候选：{title}",
            "text_summary": str(beat.get("content_goal") or ""),
            "source_file": "fixture/retail-history-deck.pptx",
            "page_number": int(beat.get("order") or 1),
            "screenshot_path": str(screenshot.relative_to(run_dir)),
            "confidence": confidence,
            "score": confidence,
            "win_rate": 0.67 if role in {"opener", "problem"} else 0.45,
            "reuse_count": 3 if role in {"opener", "problem"} else 1,
        }
    ]


def _selection_record(
    request: dict[str, Any],
    *,
    retrieval_method: str,
    fallback_reason: str,
    preview_status: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "beat_id": request["beat_id"],
        "page_task_id": request["page_task_id"],
        "query_trace_id": request["query_trace_id"],
        "role_original": request["role_original"],
        "role_strategy": request["role_strategy"],
        "role_mapped": request["role_mapped"],
        "retrieval_method": retrieval_method,
        "fallback_reason": fallback_reason,
        "preview_status": preview_status,
        "preview_degraded": preview_status != "ready",
        "candidates": candidates,
    }


def _aggregate_status(selections: list[dict[str, Any]], *, source: str) -> str:
    if not selections:
        return "library_gap"
    if any(item["retrieval_method"] == "none" for item in selections):
        return "library_gap"
    if source == "fixture" or any(
        item["retrieval_method"] == "semantic_fallback" or item["preview_degraded"]
        for item in selections
    ):
        return "library_degraded"
    return "library_ready"


def write_library_results(
    run_dir: Path,
    *,
    run_id: str,
    selections: list[dict[str, Any]],
    source: str,
    status: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    root = run_dir / "library_results"
    by_beat_dir = root / "by_beat"
    by_beat_dir.mkdir(parents=True, exist_ok=True)
    normalized_source = normalize_library_source(source)
    by_beat = {item["beat_id"]: item["candidates"] for item in selections}
    aggregate_status = status or _aggregate_status(selections, source=normalized_source)
    payload = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "run_id": run_id,
        "status": aggregate_status,
        "source": normalized_source,
        "preview_degraded": any(item["preview_degraded"] for item in selections),
        "selections": selections,
        "warnings": list(dict.fromkeys(warnings or [])),
        "by_beat": by_beat,
    }
    for item in selections:
        write_json(by_beat_dir / f"{item['beat_id']}.json", item)
    write_json(root / "selection.json", payload)
    write_json(run_dir / "external" / "ppt_library" / "library_results.v2.json", payload)
    return payload


def _normalize_selection_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    schema_version = payload.get("schema_version")
    if schema_version not in {SELECTION_SCHEMA_VERSION_V1, SELECTION_SCHEMA_VERSION}:
        raise PPTLibraryClientError(
            f"schema_version must be '{SELECTION_SCHEMA_VERSION}' or '{SELECTION_SCHEMA_VERSION_V1}', got '{schema_version}'."
        )
    if isinstance(payload.get("selections"), list):
        return [item for item in payload["selections"] if isinstance(item, dict)]
    if schema_version == SELECTION_SCHEMA_VERSION_V1 and isinstance(payload.get("by_beat"), dict):
        return [
            {"beat_id": beat_id, "candidates": candidates}
            for beat_id, candidates in payload["by_beat"].items()
        ]
    if schema_version == SELECTION_SCHEMA_VERSION_V1 and isinstance(payload.get("beats"), list):
        return [item for item in payload["beats"] if isinstance(item, dict)]
    raise PPTLibraryClientError("selection payload must contain selections, by_beat, or beats.")


def validate_library_selection(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["Result must be a JSON object."], "warnings": []}
    schema_version = payload.get("schema_version")
    if schema_version not in {SELECTION_SCHEMA_VERSION_V1, SELECTION_SCHEMA_VERSION}:
        errors.append(
            f"schema_version must be '{SELECTION_SCHEMA_VERSION}' or '{SELECTION_SCHEMA_VERSION_V1}', got '{schema_version}'."
        )
    if not payload.get("run_id"):
        errors.append("run_id is required.")
    if schema_version == SELECTION_SCHEMA_VERSION:
        for field in ("status", "source", "preview_degraded", "selections", "warnings", "by_beat"):
            if field not in payload:
                errors.append(f"{field} is required.")
    try:
        items = _normalize_selection_payload(payload) if not errors else []
    except PPTLibraryClientError as exc:
        errors.append(str(exc))
        items = []
    if not items and not errors:
        warnings.append("No library selections were provided.")
    for index, item in enumerate(items):
        if not item.get("beat_id") and not (schema_version == SELECTION_SCHEMA_VERSION_V1 and item.get("page_task_id")):
            errors.append(f"selections[{index}].beat_id is required.")
        for field in ("beat_id", "page_task_id"):
            value = item.get(field)
            if value and not SAFE_ID_RE.fullmatch(str(value)):
                errors.append(f"selections[{index}].{field} must be a path-safe identifier.")
        candidates = item.get("candidates", item.get("slides", item.get("results", [])))
        if candidates is None:
            candidates = []
        if not isinstance(candidates, list):
            errors.append(f"selections[{index}].candidates must be an array.")
        if schema_version == SELECTION_SCHEMA_VERSION:
            for field in (
                "page_task_id",
                "query_trace_id",
                "role_original",
                "role_strategy",
                "role_mapped",
                "retrieval_method",
                "fallback_reason",
                "preview_status",
            ):
                if field not in item:
                    errors.append(f"selections[{index}].{field} is required.")
            required_candidate_fields = {
                "candidate_id",
                "slide_id",
                "asset_key",
                "title",
                "text_summary",
                "page_number",
                "score",
                "confidence",
                "source_asset_id",
                "source_display_name",
                "screenshot_ref",
                "candidate_origin",
                "reuse_policy",
            }
            for candidate_index, candidate in enumerate(candidates if isinstance(candidates, list) else []):
                if not isinstance(candidate, dict):
                    errors.append(f"selections[{index}].candidates[{candidate_index}] must be an object.")
                    continue
                for field in sorted(required_candidate_fields - set(candidate)):
                    errors.append(f"selections[{index}].candidates[{candidate_index}].{field} is required.")
                if any(field in candidate for field in ("source_file", "source_path", "screenshot_path")):
                    errors.append(f"selections[{index}].candidates[{candidate_index}] contains a raw path field.")
                screenshot_ref = str(candidate.get("screenshot_ref") or "")
                if screenshot_ref and not _is_run_relative_ref(screenshot_ref):
                    errors.append(f"selections[{index}].candidates[{candidate_index}].screenshot_ref must be run-relative.")
                if re.fullmatch(r"[a-f0-9]{64}", str(candidate.get("source_asset_id") or "")) is None:
                    errors.append(f"selections[{index}].candidates[{candidate_index}].source_asset_id must be a SHA-256 value.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _legacy_role_request(item: dict[str, Any], *, run_id: str, beat_id: str) -> dict[str, Any]:
    role = str(item.get("role") or item.get("page_role") or "opener")
    try:
        strategy, mapped, reuse_policy, _ = _role_policy(role, "dev")
    except PPTLibraryClientError:
        strategy, mapped, reuse_policy = "semantic_only", None, "adapt"
    return {
        "beat_id": beat_id,
        "page_task_id": str(item.get("page_task_id") or beat_id),
        "query_trace_id": _legacy_query_trace_id(run_id, beat_id, item.get("query_trace_id")),
        "role_original": role,
        "role_strategy": strategy,
        "role_mapped": mapped,
        "reuse_policy": reuse_policy,
    }


def _legacy_query_trace_id(run_id: str, beat_id: str, value: Any) -> str:
    trace_id = str(value or "")
    if re.fullmatch(r"[a-f0-9]{64}", trace_id):
        return trace_id
    return _query_trace_id(run_id, beat_id, trace_id)


def _is_run_relative_ref(value: str) -> bool:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    return not path.is_absolute() and ".." not in path.parts and normalized.startswith("preview_assets/")


def _normalize_v2_candidates(
    candidates: list[Any],
    *,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], str]:
    normalized: list[dict[str, Any]] = []
    statuses: list[str] = []
    allowed_fields = {
        "candidate_id",
        "slide_id",
        "asset_key",
        "title",
        "text_summary",
        "page_number",
        "score",
        "confidence",
        "source_asset_id",
        "source_display_name",
        "screenshot_ref",
        "candidate_origin",
        "reuse_policy",
        "page_task_id",
        "slot_id",
        "query_trace_id",
    }
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        candidate = {field: raw[field] for field in allowed_fields if field in raw}
        source_asset_id = str(candidate["source_asset_id"])
        candidate["source_display_name"] = _source_display_name(
            str(candidate.get("source_display_name") or ""),
            source_asset_id,
        )
        candidate["score"] = _confidence(candidate.get("score"))
        candidate["confidence"] = _confidence(candidate.get("confidence"))
        candidate["candidate_origin"] = "ppt_library"
        screenshot_ref = str(candidate.get("screenshot_ref") or "")
        candidate["screenshot_ref"] = screenshot_ref
        if not screenshot_ref:
            statuses.append("missing")
        elif (run_dir / screenshot_ref).is_file():
            statuses.append("ready")
        else:
            statuses.append("invalid")
        normalized.append(candidate)
    if not normalized or "missing" in statuses:
        return normalized, "missing"
    if "invalid" in statuses:
        return normalized, "invalid"
    return normalized, "ready"


def _selection_to_v2(payload: dict[str, Any], *, run_dir: Path, run_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    selections: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in _normalize_selection_payload(payload):
        beat_id = str(item.get("beat_id") or item.get("page_task_id") or "")
        request = _legacy_role_request(item, run_id=run_id, beat_id=beat_id)
        raw_candidates = item.get("candidates", item.get("slides", item.get("results", [])))
        if payload.get("schema_version") == SELECTION_SCHEMA_VERSION:
            candidates, preview_status = _normalize_v2_candidates(
                raw_candidates if isinstance(raw_candidates, list) else [],
                run_dir=run_dir,
            )
            candidate_warnings: list[str] = []
        else:
            candidates, preview_status, candidate_warnings = _normalize_candidates(
                raw_candidates if isinstance(raw_candidates, list) else [],
                run_dir=run_dir,
                reuse_policy=request["reuse_policy"],
                candidate_origin="ppt_library",
            )
            for candidate in candidates:
                candidate["page_task_id"] = request["page_task_id"]
                candidate["slot_id"] = str(item.get("slot_id") or "")
                candidate["query_trace_id"] = str(item.get("query_trace_id") or request["query_trace_id"])
        warnings.extend(candidate_warnings)
        if payload.get("schema_version") == SELECTION_SCHEMA_VERSION:
            request.update(
                {
                    "page_task_id": item["page_task_id"],
                    "query_trace_id": item["query_trace_id"],
                    "role_original": item["role_original"],
                    "role_strategy": item["role_strategy"],
                    "role_mapped": item["role_mapped"],
                }
            )
        selections.append(
            _selection_record(
                request,
                retrieval_method=str(item.get("retrieval_method") or ("role_selection" if candidates else "none")),
                fallback_reason=str(item.get("fallback_reason") or "LEGACY_SELECTION_IMPORTED"),
                preview_status=preview_status,
                candidates=candidates,
            )
        )
    return selections, warnings


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

    selections, candidate_warnings = _selection_to_v2(payload, run_dir=root, run_id=run_id)
    normalized = write_library_results(
        root,
        run_id=run_id,
        selections=selections,
        source="imported",
        warnings=[*validation.get("warnings", []), *candidate_warnings],
    )
    canonical_path = root / "external" / "ppt_library" / "library_results.v2.json"
    append_import_log(
        root,
        import_type="ppt_library_selection",
        source="ppt-library",
        status="imported",
        source_path=source_path,
        canonical_refs=[str(canonical_path.relative_to(root))],
        legacy_refs=["library_results/selection.json", "library_results/by_beat/"],
        warnings=normalized.get("warnings", []),
        payload={
            "beat_count": len(selections),
            "candidate_count": sum(len(item["candidates"]) for item in selections),
        },
    )
    append_event(
        root,
        "ppt_library.selection.imported",
        target="external/ppt_library/library_results.v2.json",
        payload_ref="library_results/selection.json",
    )
    return {
        "status": "imported",
        "run_id": run_id,
        "beat_count": len(selections),
        "candidate_count": sum(len(item["candidates"]) for item in selections),
        "canonical_path": str(canonical_path.relative_to(root)),
        "legacy_path": "library_results/selection.json",
        "selection": normalized,
    }


def _read_json_output(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PPTLibraryClientError("PPT Library returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise PPTLibraryClientError("PPT Library JSON output must be an object.")
    return payload


def _run_role_selection(
    *,
    command: str,
    narrative_plan: dict[str, Any],
    request: dict[str, Any],
    private_root: Path,
    run_dir: Path,
    brief: str,
) -> list[dict[str, Any]]:
    trace_id = request["query_trace_id"]
    role_plan_path = private_root / f"role_plan.{trace_id}.json"
    raw_path = private_root / f"selection.raw.{trace_id}.role.json"
    beat = next(item for item in narrative_plan.get("beats", []) if item.get("beat_id") == request["beat_id"])
    role_beat = dict(beat)
    role_beat["role"] = request["role_mapped"]
    role_plan = dict(narrative_plan)
    role_plan["beats"] = [role_beat]
    write_json(role_plan_path, role_plan)
    cmd = build_select_slides_command(
        command=command,
        plan_path=role_plan_path,
        brief=brief,
        output_path=raw_path,
    )
    completed = subprocess.run(cmd, cwd=run_dir, text=True, capture_output=True, check=False)
    if completed.returncode != 0 or not raw_path.exists():
        raise PPTLibraryClientError(
            completed.stderr.strip() or completed.stdout.strip() or "PPT Library role selection failed."
        )
    return extract_slides(_read_json_output(raw_path))


def _run_semantic_search(
    *,
    command: str,
    request: dict[str, Any],
    private_root: Path,
    run_dir: Path,
) -> list[dict[str, Any]]:
    raw_path = private_root / f"selection.raw.{request['query_trace_id']}.search.json"
    cmd = build_search_command(command=command, query=request["query"])
    completed = subprocess.run(cmd, cwd=run_dir, text=True, capture_output=True, check=False)
    raw_path.write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode != 0:
        raise PPTLibraryClientError(
            completed.stderr.strip() or completed.stdout.strip() or "PPT Library semantic search failed."
        )
    return extract_slides(_read_json_output(raw_path))


def _blocked_result(
    *,
    run_dir: Path,
    run_id: str,
    selections: list[dict[str, Any]],
    request: dict[str, Any],
    error: str,
    warnings: list[str],
) -> None:
    selections.append(
        _selection_record(
            request,
            retrieval_method="none",
            fallback_reason="PPT_LIBRARY_COMMAND_FAILED",
            preview_status="missing",
            candidates=[],
        )
    )
    write_library_results(
        run_dir,
        run_id=run_id,
        selections=selections,
        source="ppt_library",
        status="library_blocked",
        warnings=warnings,
    )
    append_event(run_dir, "ppt_library.bridge.blocked", status="error", error=error)


def _write_early_blocked_result(
    *,
    run_dir: Path,
    run_id: str,
    bridge_requests: list[dict[str, Any]],
    reason: str,
    warnings: list[str],
) -> None:
    selections = [
        _selection_record(
            request,
            retrieval_method="none",
            fallback_reason=reason,
            preview_status="missing",
            candidates=[],
        )
        for request in bridge_requests
    ]
    write_library_results(
        run_dir,
        run_id=run_id,
        selections=selections,
        source="ppt_library",
        status="library_blocked",
        warnings=warnings,
    )


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
    root = ensure_run_dirs(run_dir)
    run_id = str(request.get("run_id") or narrative_plan.get("run_id") or root.name)
    run_mode = str(request.get("run_mode") or "dev").strip().lower()
    strict_mode = run_mode in {"production", "benchmark"}
    private_root = root / "external" / "ppt_library" / "private"
    private_root.mkdir(parents=True, exist_ok=True)
    page_tasks = read_json(root / "page_tasks.json") if (root / "page_tasks.json").exists() else {"tasks": []}
    try:
        bridge_plan = build_bridge_plan(
            narrative_plan,
            page_tasks,
            run_id=run_id,
            run_mode=run_mode,
        )
    except PPTLibraryClientError as exc:
        write_library_results(
            root,
            run_id=run_id,
            selections=[],
            source="ppt_library",
            status="library_blocked",
            warnings=[str(exc).split(":", 1)[0]],
        )
        append_event(root, "ppt_library.bridge.blocked", status="error", error=str(exc))
        raise
    write_json(private_root / "bridge_plan.v1.json", bridge_plan)

    fallback_message = "PPT Library fixture fallback is blocked for production and benchmark runs."
    if strict_mode and (mode == "fixture" or allow_fixture_fallback):
        _write_early_blocked_result(
            run_dir=root,
            run_id=run_id,
            bridge_requests=bridge_plan["requests"],
            reason="FIXTURE_FALLBACK_BLOCKED",
            warnings=list(bridge_plan["warnings"]),
        )
        append_event(root, "ppt_library.fixture.blocked", status="error", error=fallback_message)
        raise PPTLibraryClientError(fallback_message)
    can_run_real = mode == "real" or (mode == "auto" and bool(shutil.which(command)))
    warnings = list(bridge_plan["warnings"])

    if not can_run_real:
        if strict_mode:
            _write_early_blocked_result(
                run_dir=root,
                run_id=run_id,
                bridge_requests=bridge_plan["requests"],
                reason="PPT_LIBRARY_UNAVAILABLE",
                warnings=warnings,
            )
            append_event(root, "ppt_library.fixture.blocked", status="error", error=fallback_message)
            raise PPTLibraryClientError(fallback_message)
        beats_by_id = {str(item.get("beat_id")): item for item in narrative_plan.get("beats", []) if isinstance(item, dict)}
        selections: list[dict[str, Any]] = []
        for bridge_request in bridge_plan["requests"]:
            candidates, preview_status, candidate_warnings = _normalize_candidates(
                simulated_candidates_for_beat(root, beats_by_id[bridge_request["beat_id"]]),
                run_dir=root,
                reuse_policy=bridge_request["reuse_policy"],
                candidate_origin="fixture",
            )
            warnings.extend(candidate_warnings)
            for candidate in candidates:
                candidate["screenshot_path"] = candidate["screenshot_ref"]
                candidate["win_rate"] = 0.67 if bridge_request["role_original"] in {"opener", "problem"} else 0.45
                candidate["reuse_count"] = 3 if bridge_request["role_original"] in {"opener", "problem"} else 1
            selections.append(
                _selection_record(
                    bridge_request,
                    retrieval_method="role_selection" if candidates else "none",
                    fallback_reason="FIXTURE_PREVIEW" if candidates else "FIXTURE_GAP",
                    preview_status=preview_status,
                    candidates=candidates,
                )
            )
        append_event(root, "ppt_library.fixture.completed", status="warning", payload_ref="library_results/selection.json")
        return write_library_results(
            root,
            run_id=run_id,
            selections=selections,
            source="fixture",
            warnings=warnings,
        )

    selections = []
    for bridge_request in bridge_plan["requests"]:
        raw_candidates: list[dict[str, Any]] = []
        retrieval_method = "role_selection"
        fallback_reason = bridge_request["fallback_reason"]
        try:
            if bridge_request["role_strategy"] in {"passthrough", "mapped"}:
                raw_candidates = _run_role_selection(
                    command=command,
                    narrative_plan=narrative_plan,
                    request=bridge_request,
                    private_root=private_root,
                    run_dir=root,
                    brief=str(request.get("brief") or request.get("business_goal") or ""),
                )
            if bridge_request["role_strategy"] == "semantic_only" or not raw_candidates:
                if not raw_candidates and bridge_request["role_strategy"] != "semantic_only":
                    fallback_reason = "ROLE_SELECTION_GAP"
                raw_candidates = _run_semantic_search(
                    command=command,
                    request=bridge_request,
                    private_root=private_root,
                    run_dir=root,
                )
                retrieval_method = "semantic_fallback" if raw_candidates else "none"
                if not raw_candidates:
                    fallback_reason = "SEMANTIC_SEARCH_GAP"
        except (OSError, PPTLibraryClientError) as exc:
            _blocked_result(
                run_dir=root,
                run_id=run_id,
                selections=selections,
                request=bridge_request,
                error=str(exc),
                warnings=warnings,
            )
            raise PPTLibraryClientError("PPT Library command failed; bridge status is library_blocked.") from exc

        candidates, preview_status, candidate_warnings = _normalize_candidates(
            raw_candidates,
            run_dir=root,
            reuse_policy=bridge_request["reuse_policy"],
            candidate_origin="ppt_library",
        )
        warnings.extend(candidate_warnings)
        if not candidates:
            retrieval_method = "none"
            fallback_reason = "SEMANTIC_SEARCH_GAP" if retrieval_method == "none" else fallback_reason
        selections.append(
            _selection_record(
                bridge_request,
                retrieval_method=retrieval_method,
                fallback_reason=fallback_reason,
                preview_status=preview_status,
                candidates=candidates,
            )
        )

    append_event(
        root,
        "ppt_library.bridge.completed",
        payload_ref="external/ppt_library/library_results.v2.json",
    )
    return write_library_results(
        root,
        run_id=run_id,
        selections=selections,
        source="ppt_library",
        warnings=warnings,
    )
