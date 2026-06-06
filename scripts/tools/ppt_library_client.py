from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from runtime.events import append_event


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
)


class PPTLibraryClientError(ValueError):
    pass


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
    for beat_id, candidates in by_beat.items():
        (by_beat_dir / f"{beat_id}.json").write_text(
            json.dumps({"beat_id": beat_id, "candidates": candidates}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    payload = {"source": source, "by_beat": by_beat}
    (root / "selection.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def run_library_selection(
    *,
    narrative_plan: dict[str, Any],
    narrative_plan_path: Path,
    request: dict[str, Any],
    run_dir: Path,
    mode: str = "auto",
    command: str = "ppt-lib",
) -> dict[str, Any]:
    if mode not in {"auto", "real", "fixture"}:
        raise PPTLibraryClientError("mode must be auto, real, or fixture.")

    output_path = run_dir / "library_results" / "selection.raw.json"
    can_run_real = mode == "real" or (mode == "auto" and shutil.which(command))
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

    by_beat = {
        str(beat.get("beat_id")): simulated_candidates_for_beat(run_dir, beat)
        for beat in narrative_plan.get("beats", [])
        if isinstance(beat, dict)
    }
    append_event(run_dir, "ppt_library.fixture.completed", status="warning", payload_ref="library_results/selection.json")
    return write_library_results(run_dir, by_beat, source="fixture")
