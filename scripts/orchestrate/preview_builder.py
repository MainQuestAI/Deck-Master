from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from runtime.events import append_event
from runtime.run_state import REQUEST_NAME, read_json

ORCHESTRATE_DIR = Path(__file__).resolve().parent
if str(ORCHESTRATE_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATE_DIR))

from build_run import build_run


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
    blocked = [
        str(decision.get("beat_id") or f"decision_{index}")
        for index, decision in enumerate(sourcing_plan.get("decisions", []), start=1)
        if isinstance(decision, dict) and str(decision.get("source_decision") or "") == "manual_placeholder"
    ]
    if blocked:
        raise ValueError(f"manual_placeholder sourcing is not allowed for {mode} preview builds: {', '.join(blocked)}")


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
            "beat_id",
            "page_title",
            "task_type",
            "source_decision",
            "expected_operation",
            "generation_brief",
            "visual_need",
            "evidence_need",
            "customer_visible_content",
            "speaker_notes",
            "style_constraints",
            "status",
        )
        if key in task
    }


def preview_asset_for(run_dir: Path, decision: dict[str, Any]) -> str:
    selected = decision.get("selected_candidate") if isinstance(decision.get("selected_candidate"), dict) else None
    if selected and selected.get("screenshot_path"):
        return str(selected["screenshot_path"])
    label = str(decision.get("source_decision", "fixture")).upper()
    return str(
        write_status_svg(
            run_dir / "preview_assets" / f"{decision.get('beat_id')}.svg",
            label,
            str(decision.get("page_title") or decision.get("beat_id")),
            str(decision.get("decision_reason") or ""),
        )
        .relative_to(run_dir)
    )


def page_for_decision(run_dir: Path, decision: dict[str, Any], generation_tasks: dict[str, Any] | None = None) -> dict[str, Any]:
    selected = decision.get("selected_candidate") if isinstance(decision.get("selected_candidate"), dict) else {}
    task = None
    if generation_tasks:
        for candidate in generation_tasks.get("tasks", []):
            if candidate.get("beat_id") == decision.get("beat_id"):
                task = candidate
                break
    source_decision = str(decision.get("source_decision"))
    library_source = str(decision.get("library_source") or "none")
    candidate_origin = str(decision.get("candidate_origin") or ("none" if not selected else library_source))
    page = {
        "page_id": str(decision.get("beat_id")),
        "beat_id": decision.get("beat_id"),
        "order": int(decision.get("order") or 0),
        "title": decision.get("page_title") or decision.get("beat_id"),
        "source_type": source_type_for(source_decision),
        "library_source": library_source,
        "candidate_origin": candidate_origin,
        "source_decision": source_decision,
        "preview_asset": preview_asset_for(run_dir, decision),
        "narrative_role": decision.get("role") or "",
        "decision_reason": decision.get("decision_reason", ""),
        "reuse_reason": decision.get("decision_reason", ""),
        "confidence": decision.get("confidence", 0),
        "alternatives": decision.get("alternatives", []),
        "risk_flags": decision.get("risk_flags", []),
        "tool_refs": {"sourcing_plan": "sourcing_plan.json"},
        "generation_task": public_generation_task(task),
        "source_pptx": selected.get("source_file", ""),
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
    _assert_preview_allowed(root, sourcing_plan)
    pages = [
        page_for_decision(root, decision, generation_tasks)
        for decision in sourcing_plan.get("decisions", [])
        if isinstance(decision, dict)
    ]
    plan = {
        "run_id": sourcing_plan.get("run_id", root.name),
        "title": sourcing_plan.get("title", root.name),
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
