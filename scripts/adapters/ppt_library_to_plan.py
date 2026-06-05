from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Input JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid input JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Input JSON must be an object.")
    return payload


def extract_library_slides(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(payload.get("results"), list):
        return [("library", item) for item in payload["results"] if isinstance(item, dict)]

    report = payload.get("report")
    if not isinstance(report, dict):
        report = payload
    roles = report.get("roles") if isinstance(report, dict) else None
    if not isinstance(roles, list):
        raise ValueError("Input must contain either results[] or report.roles[].")

    slides: list[tuple[str, dict[str, Any]]] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        role_name = str(role.get("role") or "library")
        for slide in role.get("slides", []):
            if isinstance(slide, dict):
                slides.append((role_name, slide))
    return slides


def page_id_for(role: str, slide: dict[str, Any], index: int) -> str:
    slide_id = slide.get("slide_id") or slide.get("canonical_slide_id") or index
    safe_role = "".join(char if char.isalnum() or char in "-_" else "_" for char in role)
    return f"{safe_role}_{slide_id}"


def preview_asset_for(slide: dict[str, Any], page_id: str, asset_base_dir: Path | None = None) -> str:
    screenshot = slide.get("screenshot_path")
    if screenshot:
        screenshot_path = Path(str(screenshot)).expanduser()
        if asset_base_dir and not screenshot_path.is_absolute():
            return str((asset_base_dir / screenshot_path).resolve())
        return str(screenshot)
    return f"__missing_previews__/{page_id}.png"


def convert_ppt_library_payload(
    payload: dict[str, Any],
    *,
    run_id: str,
    title: str,
    max_pages: int | None = None,
    asset_base_dir: Path | None = None,
) -> dict[str, Any]:
    slides = extract_library_slides(payload)
    if max_pages is not None:
        slides = slides[:max_pages]
    if not slides:
        raise ValueError("No slides found in PPT Library payload.")

    pages = []
    for index, (role, slide) in enumerate(slides, start=1):
        page_id = page_id_for(role, slide, index)
        source_file = slide.get("source_file") or ""
        page_number = slide.get("page_number")
        confidence = slide.get("confidence")
        if confidence is None:
            confidence = slide.get("score")
        pages.append(
            {
                "page_id": page_id,
                "order": index,
                "title": slide.get("title") or f"PPT Library Slide {index}",
                "source_type": "library_slide",
                "preview_asset": preview_asset_for(slide, page_id, asset_base_dir),
                "source_pptx": source_file,
                "source_slide_index": page_number if page_number is not None else "",
                "narrative_role": slide.get("narrative_role") or slide.get("page_role") or role,
                "reuse_reason": slide.get("importance_reason") or slide.get("text_summary") or "Selected from PPT Library.",
                "confidence": confidence if confidence is not None else 0,
                "ppt_library_slide_id": slide.get("slide_id"),
                "canonical_slide_id": slide.get("canonical_slide_id"),
                "win_rate": slide.get("win_rate"),
                "won_count": slide.get("won_count"),
                "lost_count": slide.get("lost_count"),
                "decision": "needs_review",
                "notes": "",
            }
        )
    return {"run_id": run_id, "title": title, "status": "draft", "pages": pages}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PPT Library JSON output into a Deck Master orchestration plan.")
    parser.add_argument("input", help="ppt-lib search/select-slides JSON output")
    parser.add_argument("--output", required=True, help="Output Deck Master plan JSON")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()

    try:
        input_path = Path(args.input).expanduser().resolve()
        plan = convert_ppt_library_payload(
            load_json(input_path),
            run_id=args.run_id,
            title=args.title,
            max_pages=args.max_pages,
            asset_base_dir=input_path.parent,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": plan["run_id"], "pages": len(plan["pages"]), "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
