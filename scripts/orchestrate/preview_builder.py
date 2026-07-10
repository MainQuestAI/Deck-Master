from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from runtime.events import append_event
from runtime.run_state import REQUEST_NAME, read_json
from sourcing.reader import canonicalize_sourcing_plan

ORCHESTRATE_DIR = Path(__file__).resolve().parent
if str(ORCHESTRATE_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATE_DIR))

from build_run import build_run


PLACEHOLDER_DECISIONS = {"manual", "evidence", "blocked"}
PUBLIC_SOURCE_FIELDS = {
    "candidate_id",
    "slide_id",
    "asset_key",
    "query_trace_id",
    "page_task_id",
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
    "slot_id",
    "win_rate",
    "reuse_count",
    "source_authority",
    "freshness_status",
    "permission_status",
    "reuse_safe",
    "usage_constraints",
}


def _source_decision(page: dict[str, Any]) -> str:
    decision = str(page.get("decision") or "").strip().lower()
    return "manual_placeholder" if decision in PLACEHOLDER_DECISIONS else decision


def _selected_sources(page: dict[str, Any]) -> list[dict[str, Any]]:
    sources = page.get("selected_sources")
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def _safe_screenshot_ref(value: Any) -> str:
    ref = str(value or "").strip()
    if not ref:
        return ""
    path = Path(ref)
    if path.is_absolute() or ".." in path.parts or "\\" in ref or not ref.startswith("preview_assets/"):
        return ""
    return ref


def _resolved_preview_asset(run_dir: Path, screenshot_ref: str) -> Path | None:
    if not screenshot_ref:
        return None
    candidate = (run_dir / screenshot_ref).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None
    return candidate


def _public_source(source: dict[str, Any] | None, run_dir: Path) -> dict[str, Any] | None:
    if not source:
        return None
    public = {key: source[key] for key in PUBLIC_SOURCE_FIELDS if key in source}
    screenshot_ref = _safe_screenshot_ref(public.get("screenshot_ref"))
    if screenshot_ref and _resolved_preview_asset(run_dir, screenshot_ref) is not None:
        public["screenshot_ref"] = screenshot_ref
    else:
        public.pop("screenshot_ref", None)
    return public


def _safe_page_filename(page_id: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-_" else "_" for character in page_id)
    return safe or "page"


def _run_mode(run_dir: Path) -> str:
    request_path = run_dir / REQUEST_NAME
    if not request_path.exists():
        return "production"
    try:
        request = read_json(request_path)
    except Exception:
        return "production"
    mode = str(request.get("run_mode") or "production").strip().lower()
    return mode if mode in {"production", "benchmark", "fixture", "dev"} else "production"


def _assert_preview_allowed(run_dir: Path, sourcing_plan: dict[str, Any]) -> None:
    mode = _run_mode(run_dir)
    if mode not in {"production", "benchmark"}:
        return
    blocked = []
    for index, page in enumerate(sourcing_plan.get("pages", []), start=1):
        if not isinstance(page, dict):
            continue
        decision = str(page.get("decision") or "")
        if decision in {"manual", "blocked"}:
            page_id = str(page.get("page_id") or f"page_{index}")
            blocked.append(f"{page_id} ({decision})")
    if blocked:
        raise ValueError(
            f"manual_placeholder sourcing is not allowed for {mode} preview builds; "
            f"blocked pages: {', '.join(blocked)}"
        )


def write_status_svg(path: Path, label: str, title: str, detail: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_label = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_detail = detail.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#101314"/>
  <rect x="70" y="70" width="1140" height="580" rx="32" fill="#f2eee8"/>
  <text x="120" y="170" font-family="Avenir Next, Helvetica, sans-serif" font-size="32" fill="#7a5b00" letter-spacing="4">{safe_label}</text>
  <text x="120" y="330" font-family="Avenir Next, Helvetica, sans-serif" font-size="68" font-weight="700" fill="#111314">{safe_title}</text>
  <text x="120" y="430" font-family="Avenir Next, Helvetica, sans-serif" font-size="30" fill="#596064">{safe_detail}</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return path


def source_type_for(source_decision: str) -> str:
    if source_decision in {"reuse", "adapt"}:
        return "library_slide"
    if source_decision == "generate":
        return "generated"
    return "placeholder"


def public_generation_task(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        return None
    return {
        key: task.get(key)
        for key in (
            "task_id",
            "page_task_id",
            "page_id",
            "beat_id",
            "page_title",
            "task_type",
            "source_decision",
            "expected_operation",
            "generation_brief",
            "query_trace_id",
            "asset_key",
            "claim_ids",
            "visual_need",
            "evidence_need",
            "customer_visible_content",
            "speaker_notes",
            "style_constraints",
            "status",
        )
        if key in task
    }


def preview_asset_for(run_dir: Path, page: dict[str, Any]) -> str:
    sources = _selected_sources(page)
    selected = sources[0] if sources else None
    screenshot_ref = _safe_screenshot_ref((selected or {}).get("screenshot_ref"))
    preview_asset = _resolved_preview_asset(run_dir, screenshot_ref)
    if preview_asset is not None and preview_asset.is_file():
        return screenshot_ref

    raw_ref = str((selected or {}).get("screenshot_ref") or "").strip()
    invalid_ref = bool(raw_ref and preview_asset is None)
    label = "INVALID PREVIEW" if invalid_ref else "MISSING PREVIEW"
    detail = "Preview reference is invalid." if invalid_ref else "Preview asset is unavailable."
    page_id = str(page.get("page_id") or "page")
    return str(
        write_status_svg(
            run_dir / "preview_assets" / "sourcing_status" / f"{_safe_page_filename(page_id)}.svg",
            label,
            str(page.get("page_title") or page_id),
            detail,
        )
        .relative_to(run_dir)
    )


def page_for_decision(run_dir: Path, decision: dict[str, Any], generation_tasks: dict[str, Any] | None = None) -> dict[str, Any]:
    selected_sources = _selected_sources(decision)
    selected = selected_sources[0] if selected_sources else {}
    public_selected = _public_source(selected, run_dir)
    alternatives = [source for source in (_public_source(item, run_dir) for item in selected_sources[1:]) if source]
    page_id = str(decision.get("page_id") or "")
    page_task_id = str(decision.get("page_task_id") or page_id)
    task = None
    if generation_tasks:
        for candidate in generation_tasks.get("tasks", []):
            if (
                candidate.get("page_task_id") == page_task_id
                or candidate.get("page_id") == page_id
                or candidate.get("beat_id") == page_id
            ):
                task = candidate
                break
    source_decision = _source_decision(decision)
    candidate_origin = str(selected.get("candidate_origin") or decision.get("candidate_origin") or "none")
    library_source = str(decision.get("library_source") or candidate_origin)
    page = {
        "page_id": page_id,
        "page_task_id": page_task_id,
        "beat_id": page_id,
        "order": int(decision.get("order") or 0),
        "title": decision.get("page_title") or page_id,
        "source_type": source_type_for(source_decision),
        "library_source": library_source,
        "candidate_origin": candidate_origin,
        "source_decision": source_decision,
        "preview_asset": preview_asset_for(run_dir, decision),
        "narrative_role": decision.get("role") or "",
        "decision_reason": decision.get("reason", ""),
        "reuse_reason": decision.get("reason", ""),
        "confidence": decision.get("confidence", 0),
        "selected_candidate": public_selected,
        "alternatives": alternatives,
        "query_trace_id": selected.get("query_trace_id", ""),
        "asset_key": selected.get("asset_key", ""),
        "source_asset_id": selected.get("source_asset_id", ""),
        "source_display_name": selected.get("source_display_name", ""),
        "claim_ids": list(decision.get("claim_ids") or []),
        "evidence_need": list(decision.get("evidence_need") or []),
        "risk_flags": decision.get("risk_flags", []),
        "tool_refs": {"sourcing_plan": "sourcing_plan.json"},
        "generation_task": public_generation_task(task),
        "source_slide_index": selected.get("page_number", ""),
        "ppt_library_slide_id": selected.get("slide_id", selected.get("candidate_id", "")),
        "decision": "needs_review",
        "notes": "",
    }
    return page


def build_orchestration_plan_from_sourcing(
    sourcing_plan: dict[str, Any],
    run_dir: str | Path,
    generation_tasks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    canonical_plan = canonicalize_sourcing_plan(sourcing_plan)
    _assert_preview_allowed(root, canonical_plan)
    pages = [
        page_for_decision(root, page, generation_tasks)
        for page in canonical_plan.get("pages", [])
        if isinstance(page, dict)
    ]
    plan = {
        "run_id": canonical_plan.get("run_id", root.name),
        "title": canonical_plan.get("title", root.name),
        "status": "draft",
        "pages": sorted(pages, key=lambda page: page["order"]),
    }
    (root / "orchestration_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_event(root, "preview.orchestration_plan.created", payload_ref="orchestration_plan.json", data={"pages": len(pages)})
    return plan


def build_preview_from_sourcing(
    sourcing_plan: dict[str, Any],
    run_dir: str | Path,
    generation_tasks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    build_orchestration_plan_from_sourcing(sourcing_plan, root, generation_tasks)
    link_mode = "copy" if _run_mode(root) == "fixture" else "symlink"
    manifest = build_run(root / "orchestration_plan.json", root, force=False, link_mode=link_mode, preserve_existing=True)
    append_event(root, "preview.manifest.created", payload_ref="preview_manifest.json", data={"pages": len(manifest["pages"])})
    return manifest
