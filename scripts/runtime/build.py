from __future__ import annotations

import base64
import json
import hashlib
import io
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from runtime.artifact_validator import validate_artifact_manifest
from runtime.builder_backend import backend_render_runtime_ready, builder_backend_status, production_requires_builder_backend
from runtime.events import append_event
from runtime.render_handoff import RENDER_REQUEST_NAME, write_render_request
from runtime.run_state import PREVIEW_MANIFEST_NAME, ensure_run_dirs, load_request, read_json, write_json

BUILD_MANIFEST_SCHEMA_VERSION = "deck_build_manifest.v1"
ARTIFACT_MANIFEST_SCHEMA_VERSION = "deck_artifact_manifest.v1"
RENDER_RESULT_SCHEMA_VERSION = "deck_render_result.v2"

BUILD_DIR = "build"
BUILD_MANIFEST_NAME = "build_manifest.json"
ARTIFACT_MANIFEST_NAME = "artifact_manifest.json"
RENDER_RESULTS_DIR = "render_results"
RENDER_RESULT_NAME = "render_result.json"
CONTRACT_SMOKE_SOURCE_MODE = "contract_smoke"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class BuildError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _safe_source(root: Path, value: Any, *, required: bool = False) -> tuple[Path | None, str]:
    text = str(value or "").strip()
    if not text:
        if required:
            raise BuildError("page source path is required.")
        return None, ""
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise BuildError(f"page source path must be run-relative: {text}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise BuildError(f"page source path escapes run directory: {text}")
    return resolved, text


def _page_order(page: dict[str, Any]) -> int:
    try:
        return int(page.get("order") or 0)
    except (TypeError, ValueError):
        return 0


def _media_type(path: str, kind: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".html":
        return "text/html"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".png":
        return "image/png"
    if suffix == ".pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if kind == "artifact_manifest":
        return "application/json"
    return "application/octet-stream"


def _artifact(
    root: Path,
    *,
    artifact_id: str,
    kind: str,
    path: Path,
    editability: str,
    page_id: str = "",
) -> dict[str, Any]:
    rel = _run_relative(root, path)
    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "path": rel,
        "media_type": _media_type(rel, kind),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
        "validation_status": "validated",
        "editability": editability,
        "source_mode": CONTRACT_SMOKE_SOURCE_MODE,
        "non_client_deliverable": True,
        "page_id": page_id,
        "created_at": _utc_now(),
    }


def _run_mode(request: dict[str, Any]) -> str:
    mode = str(request.get("run_mode") or "production").strip().lower()
    return mode if mode in {"production", "benchmark", "fixture", "dev"} else "production"


def _assert_builder_backend_available(request: dict[str, Any]) -> dict[str, Any]:
    status = builder_backend_status()
    if production_requires_builder_backend(_run_mode(request)) and not status.get("production_capable"):
        raise BuildError("needs_builder_backend: " + str(status.get("blocking_reason") or "PPT Master backend is not ready."))
    if production_requires_builder_backend(_run_mode(request)) and not backend_render_runtime_ready():
        raise BuildError("needs_builder_backend: PPT Master backend is certified but Deck Master render runtime is not wired to the external backend yet.")
    return status


def build_source_fingerprint(run_dir: str | Path) -> str:
    root = Path(run_dir).expanduser().resolve()
    digest = hashlib.sha256()
    refs: list[Path] = [
        Path(PREVIEW_MANIFEST_NAME),
        Path("page_tasks.json"),
        Path("generation_tasks") / "index.json",
    ]
    results_dir = root / "generation_results"
    if results_dir.is_dir():
        refs.extend(path.relative_to(root) for path in sorted(results_dir.glob("*.json")) if path.is_file())
    preview_path = root / PREVIEW_MANIFEST_NAME
    if preview_path.exists():
        try:
            preview = json.loads(preview_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            preview = {}
        for page in _ordered_pages(preview if isinstance(preview, dict) else {}):
            try:
                source_path, source_ref = _safe_source(root, page.get("preview_path") or page.get("source_preview_asset"))
            except BuildError:
                continue
            if source_ref and source_path is not None and source_path.exists() and source_path.is_file():
                rel = source_path.relative_to(root)
                if rel not in refs:
                    refs.append(rel)
    for rel in refs:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        digest.update(str(rel).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _ordered_pages(preview: dict[str, Any]) -> list[dict[str, Any]]:
    pages = [page for page in preview.get("pages", []) if isinstance(page, dict)]
    return sorted(pages, key=_page_order)


def prepare_build(run_dir: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    request = load_request(root)
    backend = builder_backend_status()
    run_id = str(request.get("run_id") or root.name)
    preview_path = root / PREVIEW_MANIFEST_NAME
    if not preview_path.exists():
        raise BuildError("preview_manifest.json is required before build.")
    preview = read_json(preview_path)
    pages = _ordered_pages(preview)
    if not pages:
        raise BuildError("preview_manifest.json must contain at least one page.")

    build_dir = root / BUILD_DIR
    build_dir.mkdir(parents=True, exist_ok=True)
    page_sources: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, page in enumerate(pages, start=1):
        page_id = str(page.get("page_id") or page.get("beat_id") or f"page_{index:03d}")
        source_path, source_ref = _safe_source(root, page.get("preview_path") or page.get("source_preview_asset"))
        if source_ref and source_path is not None and not source_path.exists():
            warnings.append(f"page source missing: {source_ref}")
        page_sources.append(
            {
                "page_id": page_id,
                "beat_id": str(page.get("beat_id") or page_id),
                "order": index,
                "title": str(page.get("title") or page.get("narrative_role") or page_id),
                "source_path": source_ref,
            }
        )

    manifest = {
        "schema_version": BUILD_MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "prepared",
        "run_mode": _run_mode(request),
        "source_mode": CONTRACT_SMOKE_SOURCE_MODE,
        "non_client_deliverable": True,
        "builder_backend": backend,
        "source_fingerprint": build_source_fingerprint(root),
        "page_count": len(page_sources),
        "pages": page_sources,
        "required_outputs": ["deck_html", "deck_pdf", "page_png", "deck_pptx"],
        "warnings": warnings,
        "created_at": _utc_now(),
    }
    write_json(build_dir / BUILD_MANIFEST_NAME, manifest)
    append_event(
        root,
        "build.prepared",
        target=run_id,
        payload_ref=f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        data={"page_count": len(page_sources), "warning_count": len(warnings)},
    )
    return {
        "schema_version": "deck_build_prepare_result.v1",
        "status": "prepared",
        "run_id": run_id,
        "build_manifest": f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        "page_count": len(page_sources),
        "warnings": warnings,
    }


def _load_or_prepare_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / BUILD_DIR / BUILD_MANIFEST_NAME
    if not manifest_path.exists():
        prepare_build(root)
    return read_json(manifest_path)


def _write_html(root: Path, manifest: dict[str, Any]) -> Path:
    build_dir = root / BUILD_DIR
    sections: list[str] = []
    for page in manifest.get("pages", []):
        if not isinstance(page, dict):
            continue
        source = str(page.get("source_path") or "")
        source_note = f"<p class=\"source\">{escape(source)}</p>" if source else ""
        sections.append(
            "<section class=\"page\" data-page-id=\""
            + escape(str(page.get("page_id") or ""))
            + "\">"
            + f"<h2>{escape(str(page.get('order') or ''))}. {escape(str(page.get('title') or 'Untitled'))}</h2>"
            + source_note
            + "</section>"
        )
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Deck Master Build</title>"
        "<style>"
        "body{font-family:Helvetica,Arial,sans-serif;margin:0;background:#f6f3ec;color:#171717;}"
        ".deck{max-width:1180px;margin:0 auto;padding:32px;}"
        ".page{width:960px;min-height:540px;margin:0 auto 28px;padding:44px;"
        "background:#fff;border:1px solid #d8d1c4;box-shadow:0 18px 40px rgba(20,18,14,.12);}"
        ".source{color:#6b6257;font-size:14px;}"
        "</style></head><body><main class=\"deck\">"
        + "\n".join(sections)
        + "</main></body></html>"
    )
    path = build_dir / "deck.html"
    path.write_text(html, encoding="utf-8")
    return path


def _write_pdf(root: Path, manifest: dict[str, Any]) -> Path:
    title = f"Deck Master Build {manifest.get('run_id')}"
    body = f"BT /F1 18 Tf 72 720 Td ({title}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
        f"4 0 obj << /Length {len(body)} >> stream\n{body}\nendstream endobj",
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]
    data = "%PDF-1.4\n" + "\n".join(objects) + "\ntrailer << /Root 1 0 R >>\n%%EOF\n"
    path = root / BUILD_DIR / "deck.pdf"
    path.write_bytes(data.encode("latin-1", errors="replace"))
    return path


def _write_page_pngs(root: Path, manifest: dict[str, Any]) -> list[Path]:
    page_dir = root / BUILD_DIR / "pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for page in manifest.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("page_id") or f"page_{len(paths) + 1:03d}")
        path = page_dir / f"{page_id}.png"
        path.write_bytes(PNG_1X1)
        paths.append(path)
    return paths


def _write_pptx(root: Path, manifest: dict[str, Any]) -> Path:
    pages = [page for page in manifest.get("pages", []) if isinstance(page, dict)]
    path = root / BUILD_DIR / "deck.pptx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as pptx:
        pptx.writestr(
            "[Content_Types].xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
            "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
            "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
            "<Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>"
            + "".join(
                f"<Override PartName=\"/ppt/slides/slide{i}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>"
                for i in range(1, len(pages) + 1)
            )
            + "</Types>",
        )
        pptx.writestr(
            "_rels/.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"ppt/presentation.xml\"/>"
            "</Relationships>",
        )
        slide_ids = "".join(f"<p:sldId id=\"{256 + i}\" r:id=\"rId{i}\"/>" for i in range(1, len(pages) + 1))
        pptx.writestr(
            "ppt/presentation.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<p:presentation xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
            f"<p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx=\"12192000\" cy=\"6858000\"/></p:presentation>",
        )
        rels = "".join(
            f"<Relationship Id=\"rId{i}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{i}.xml\"/>"
            for i in range(1, len(pages) + 1)
        )
        pptx.writestr(
            "ppt/_rels/presentation.xml.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            f"<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">{rels}</Relationships>",
        )
        for i, page in enumerate(pages, start=1):
            title = escape(str(page.get("title") or page.get("page_id") or f"Slide {i}"))
            pptx.writestr(
                f"ppt/slides/slide{i}.xml",
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
                "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
                "<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/>"
                "<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>"
                f"<p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"Title\"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
                f"<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>"
                "</p:spTree></p:cSld></p:sld>",
            )
    return path


def _assert_required_outputs(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists() or path.stat().st_size <= 0]
    if missing:
        raise BuildError(f"required build outputs missing or empty: {', '.join(missing)}")


def run_build(run_dir: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    request = load_request(root)
    backend = _assert_builder_backend_available(request)
    run_id = str(request.get("run_id") or root.name)
    manifest = _load_or_prepare_manifest(root)
    build_dir = root / BUILD_DIR
    build_dir.mkdir(parents=True, exist_ok=True)
    if production_requires_builder_backend(_run_mode(request)):
        render_request_path, render_request = write_render_request(
            root,
            build_dir_name=BUILD_DIR,
            build_manifest_name=BUILD_MANIFEST_NAME,
            render_results_dir=RENDER_RESULTS_DIR,
            render_result_name=RENDER_RESULT_NAME,
            request=request,
            manifest=manifest,
            backend=backend,
        )
        append_event(
            root,
            "build.render_handoff_ready",
            target=run_id,
            payload_ref=str(render_request_path.relative_to(root)),
            data={
                "page_count": int(manifest.get("page_count") or 0),
                "required_outputs": render_request.get("required_outputs", []),
                "expected_render_result": render_request.get("expected_render_result", {}),
            },
        )
        return {
            "schema_version": "deck_build_run_result.v1",
            "status": "awaiting_external_render",
            "handoff_status": "handoff_ready",
            "run_id": run_id,
            "run_dir": str(root),
            "build_manifest": str((build_dir / BUILD_MANIFEST_NAME).relative_to(root)),
            "render_request": str(render_request_path.relative_to(root)),
            "expected_render_result": render_request.get("expected_render_result", {}),
            "page_count": int(manifest.get("page_count") or 0),
            "warnings": manifest.get("warnings", []),
        }

    result_dir = root / RENDER_RESULTS_DIR
    result_dir.mkdir(parents=True, exist_ok=True)
    session_id = "build-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    html_path = _write_html(root, manifest)
    pdf_path = _write_pdf(root, manifest)
    page_pngs = _write_page_pngs(root, manifest)
    pptx_path = _write_pptx(root, manifest)
    _assert_required_outputs([html_path, pdf_path, pptx_path, *page_pngs])

    artifacts = [
        _artifact(root, artifact_id="deck_html", kind="deck_html", path=html_path, editability="native"),
        _artifact(root, artifact_id="deck_pdf", kind="deck_pdf", path=pdf_path, editability="flat_image"),
        _artifact(root, artifact_id="deck_pptx", kind="deck_pptx", path=pptx_path, editability="flat_image"),
    ]
    for page_path in page_pngs:
        artifacts.append(
            _artifact(
                root,
                artifact_id=f"{page_path.stem}_png",
                kind="page_png",
                path=page_path,
                editability="flat_image",
                page_id=page_path.stem,
            )
        )

    artifact_manifest = {
        "schema_version": ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "run_mode": _run_mode(request),
        "source_mode": CONTRACT_SMOKE_SOURCE_MODE,
        "non_client_deliverable": True,
        "builder_backend": backend,
        "source_fingerprint": manifest.get("source_fingerprint"),
        "page_count": manifest.get("page_count"),
        "artifacts": artifacts,
        "warnings": manifest.get("warnings", []),
        "created_at": _utc_now(),
    }
    artifact_validation = validate_artifact_manifest(
        root,
        artifact_manifest,
        expected_source_fingerprint=str(manifest.get("source_fingerprint") or ""),
        allow_contract_smoke=True,
        allow_non_client_deliverable=True,
    )
    artifact_manifest["validation"] = artifact_validation
    if not artifact_validation.get("valid"):
        raise BuildError("artifact validation failed: " + "; ".join(artifact_validation.get("errors", [])))
    artifact_manifest_path = build_dir / ARTIFACT_MANIFEST_NAME
    write_json(artifact_manifest_path, artifact_manifest)

    render_result = {
        "schema_version": RENDER_RESULT_SCHEMA_VERSION,
        "run_id": run_id,
        "session_id": session_id,
        "tool": "ppt-master",
        "status": "completed",
        "run_mode": _run_mode(request),
        "source_mode": CONTRACT_SMOKE_SOURCE_MODE,
        "non_client_deliverable": True,
        "builder_backend": backend,
        "artifact_path": _run_relative(root, html_path),
        "preview_dir": f"{BUILD_DIR}/pages",
        "page_count": int(manifest.get("page_count") or 0),
        "source_fingerprint": manifest.get("source_fingerprint"),
        "build_manifest": f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        "artifact_manifest": f"{BUILD_DIR}/{ARTIFACT_MANIFEST_NAME}",
        "artifacts": artifacts,
        "page_previews": [
            {"page_id": path.stem, "preview_path": _run_relative(root, path)}
            for path in page_pngs
        ],
        "warnings": manifest.get("warnings", []),
        "created_at": _utc_now(),
    }
    render_result_path = result_dir / RENDER_RESULT_NAME
    write_json(render_result_path, render_result)

    append_event(
        root,
        "build.completed",
        target=run_id,
        payload_ref=str(render_result_path.relative_to(root)),
        data={
            "page_count": render_result["page_count"],
            "artifact_count": len(artifacts),
            "warning_count": len(render_result["warnings"]),
        },
    )
    return {
        "schema_version": "deck_build_run_result.v1",
        "status": "completed",
        "run_id": run_id,
        "run_dir": str(root),
        "build_manifest": str((build_dir / BUILD_MANIFEST_NAME).relative_to(root)),
        "artifact_manifest": str(artifact_manifest_path.relative_to(root)),
        "render_result": str(render_result_path.relative_to(root)),
        "artifact_path": str(html_path.relative_to(root)),
        "page_count": render_result["page_count"],
        "artifacts": artifacts,
        "warnings": render_result["warnings"],
    }


def build_status(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest_path = root / BUILD_DIR / BUILD_MANIFEST_NAME
    render_request_path = root / BUILD_DIR / RENDER_REQUEST_NAME
    artifact_manifest_path = root / BUILD_DIR / ARTIFACT_MANIFEST_NAME
    render_result_path = root / RENDER_RESULTS_DIR / RENDER_RESULT_NAME
    build_manifest = read_json(manifest_path) if manifest_path.exists() else {}
    render_request = read_json(render_request_path) if render_request_path.exists() else {}
    render_result = read_json(render_result_path) if render_result_path.exists() else {}
    artifact_manifest = read_json(artifact_manifest_path) if artifact_manifest_path.exists() else {}
    artifact_validation = (
        validate_artifact_manifest(
            root,
            artifact_manifest,
            expected_source_fingerprint=str(artifact_manifest.get("source_fingerprint") or ""),
            allow_contract_smoke=True,
            allow_non_client_deliverable=True,
        )
        if artifact_manifest
        else {}
    )
    if render_result:
        status = "completed"
    elif render_request:
        status = str(render_request.get("status") or "awaiting_external_render")
    else:
        status = "prepared" if manifest_path.exists() else "missing"
    if artifact_validation and not artifact_validation.get("valid"):
        status = "invalid"
    request_pages = ((render_request.get("inputs") or {}).get("pages") or []) if isinstance(render_request.get("inputs"), dict) else []
    page_count = (
        render_result.get("page_count")
        or render_request.get("page_count")
        or (len(request_pages) if isinstance(request_pages, list) else 0)
        or build_manifest.get("page_count")
        or 0
    )
    warnings = render_result.get("warnings") or render_request.get("warnings") or build_manifest.get("warnings") or []
    return {
        "schema_version": "deck_build_status.v1",
        "run_dir": str(root),
        "status": status,
        "build_manifest": str(manifest_path) if manifest_path.exists() else "",
        "render_request": str(render_request_path) if render_request else "",
        "artifact_manifest": str(artifact_manifest_path) if artifact_manifest_path.exists() else "",
        "render_result": str(render_result_path) if render_result else "",
        "artifact_path": str(render_result.get("artifact_path") or ""),
        "page_count": page_count,
        "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        "artifact_validation": artifact_validation,
    }
