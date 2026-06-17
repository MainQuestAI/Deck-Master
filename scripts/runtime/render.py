from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from runtime.events import append_event
from runtime.run_state import PREVIEW_MANIFEST_NAME, ensure_run_dirs, load_request, read_json, write_json

RENDER_SESSION_NAME = "render_session.json"
RENDER_RESULTS_DIR = "render_results"
RENDER_RESULT_NAME = "render_result.json"
CANONICAL_RENDER_RESULT = Path(RENDER_RESULTS_DIR) / RENDER_RESULT_NAME
LEGACY_RENDER_RESULTS = (
    Path("external_results") / RENDER_RESULT_NAME,
    Path(RENDER_RESULT_NAME),
)
RENDER_RESULT_SCHEMA_VERSION = "deck_render_result.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_render_result(run_dir: str | Path) -> tuple[Path | None, dict[str, Any] | None, str]:
    root = Path(run_dir).expanduser().resolve()
    for source, label in ((CANONICAL_RENDER_RESULT, "canonical"), *[(item, "legacy") for item in LEGACY_RENDER_RESULTS]):
        path = root / source
        if path.exists():
            return path, read_json(path), label
    return None, None, "missing"


def render_status(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    path, payload, source = find_render_result(root)
    return {
        "schema_version": "deck_render_status.v1",
        "run_dir": str(root),
        "status": "present" if payload else "missing",
        "source": source,
        "render_result": str(path) if path else "",
        "artifact_path": str((payload or {}).get("artifact_path") or ""),
    }


def render_fixture_html(run_dir: str | Path, *, output_format: str = "html", fixture_safe: bool = False) -> dict[str, Any]:
    if output_format != "html":
        raise ValueError("v0.9.13 render supports --format html only.")
    root = ensure_run_dirs(run_dir)
    request = load_request(root)
    run_id = str(request.get("run_id") or root.name)
    preview_path = root / PREVIEW_MANIFEST_NAME
    preview = read_json(preview_path) if preview_path.exists() else {"run_id": run_id, "pages": []}
    rendered_dir = root / "rendered"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    result_dir = root / RENDER_RESULTS_DIR
    result_dir.mkdir(parents=True, exist_ok=True)
    session_id = "render-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    pages = preview.get("pages") if isinstance(preview.get("pages"), list) else []
    page_blocks = []
    page_previews: list[dict[str, str]] = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("page_id") or page.get("beat_id") or f"page_{index:02d}")
        title = str(page.get("title") or page.get("narrative_role") or page_id)
        source = str(page.get("preview_path") or "")
        page_blocks.append(
            "<section class=\"page\">"
            f"<h2>{escape(str(index))}. {escape(title)}</h2>"
            f"<p>{escape(source)}</p>"
            "</section>"
        )
        page_previews.append({"page_id": page_id, "preview_path": f"rendered/index.html#page-{index}"})

    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Deck Master Render</title>"
        "<style>body{font-family:Arial,sans-serif;margin:32px;}"
        ".page{border:1px solid #ddd;border-radius:8px;padding:20px;margin:16px 0;}"
        "h1,h2{margin:0 0 12px;}</style></head><body>"
        f"<h1>{escape(str(request.get('project_name') or run_id))}</h1>"
        + "\n".join(page_blocks or ["<section class=\"page\"><h2>Empty preview</h2></section>"])
        + "</body></html>"
    )
    artifact = rendered_dir / "index.html"
    artifact.write_text(html, encoding="utf-8")

    session = {
        "schema_version": "deck_render_session.v1",
        "run_id": run_id,
        "session_id": session_id,
        "tool": "ppt-master",
        "status": "completed",
        "fixture_safe": bool(fixture_safe),
        "created_at": utc_now(),
    }
    write_json(root / RENDER_SESSION_NAME, session)
    result = {
        "schema_version": RENDER_RESULT_SCHEMA_VERSION,
        "run_id": run_id,
        "session_id": session_id,
        "tool": "ppt-master",
        "status": "completed",
        "format": "html",
        "artifact_path": str(artifact.relative_to(root)),
        "preview_dir": "rendered",
        "page_count": len(pages),
        "page_previews": page_previews,
        "created_at": utc_now(),
    }
    target = root / CANONICAL_RENDER_RESULT
    write_json(target, result)
    append_event(
        root,
        "render.completed",
        target=run_id,
        payload_ref=str(CANONICAL_RENDER_RESULT),
        data={"artifact_path": result["artifact_path"], "page_count": len(pages)},
    )
    return {
        "schema_version": "deck_render_command_result.v1",
        "status": "completed",
        "run_id": run_id,
        "run_dir": str(root),
        "render_session": str(root / RENDER_SESSION_NAME),
        "render_result": str(target),
        "artifact_path": str(artifact),
    }
