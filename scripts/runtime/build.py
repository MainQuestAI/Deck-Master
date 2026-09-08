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
from page_roles import page_role_with_warning

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
    source_mode: str = CONTRACT_SMOKE_SOURCE_MODE,
    non_client_deliverable: bool = True,
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
        "source_mode": source_mode,
        "non_client_deliverable": non_client_deliverable,
        "page_id": page_id,
        "created_at": _utc_now(),
    }


def _run_mode(request: dict[str, Any]) -> str:
    mode = str(request.get("run_mode") or "production").strip().lower()
    return mode if mode in {"production", "benchmark", "fixture", "dev"} else "production"


def _output_profile(request: dict[str, Any]) -> str:
    profile = str(request.get("output_profile") or "client_delivery").strip().lower()
    return profile if profile in {"client_delivery", "production_pptx"} else "client_delivery"


def _required_outputs_for_profile(output_profile: str) -> list[str]:
    if output_profile == "production_pptx":
        return ["deck_pptx"]
    return ["deck_html", "deck_pdf", "page_png", "deck_pptx"]


def _assert_builder_backend_available(request: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    """SC-1.1 ND-02 (F-N02): the build route resolves BEFORE any external
    backend status query. Native-route runs never touch the external PPT
    Master binding; only an explicit legacy_ppt_master route does."""

    route = build_route(request, run_dir=root)
    if route.get("engine_id") == "deck_native":
        return {"backend_name": "deck_native", "production_capable": True, "engine_route": route}
    status = builder_backend_status()
    if production_requires_builder_backend(_run_mode(request)) and not status.get("production_capable"):
        raise BuildError("needs_builder_backend: " + str(status.get("blocking_reason") or "PPT Master backend is not ready."))
    if production_requires_builder_backend(_run_mode(request)) and not backend_render_runtime_ready():
        raise BuildError("needs_builder_backend: PPT Master backend is certified but Deck Master render runtime is not wired to the external backend yet.")
    return status


def load_persisted_route_local(root: Path) -> dict[str, Any]:
    try:
        from build.build_route import load_persisted_route
    except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
        from scripts.build.build_route import load_persisted_route
    return load_persisted_route(root)


def build_route(request: dict[str, Any], *, run_dir: Path | None = None) -> dict[str, Any]:
    try:
        from build.build_route import resolve_build_route
    except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
        from scripts.build.build_route import resolve_build_route
    return resolve_build_route(request, run_dir=run_dir)


def build_source_fingerprint(run_dir: str | Path) -> str:
    root = Path(run_dir).expanduser().resolve()
    digest = hashlib.sha256()
    refs: list[Path] = [
        Path(PREVIEW_MANIFEST_NAME),
        Path("page_tasks.json"),
        Path("generation_tasks") / "index.json",
    ]
    packages_index = root / "page_packages" / "index.json"
    if packages_index.exists():
        refs.append(packages_index)
        refs.extend(sorted((root / "page_packages").glob("*.json")))
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


def _page_sources_from_packages(root: Path, packages: list[dict[str, Any]], *, production: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """SC-1 B5: standard build consumes the current Page Package content.

    Titles, roles and body content come from the packages; each page entry
    binds the package sha and the exact customer payload sha so downstream
    artifacts are anchored to approved content.
    """

    try:
        from build.manifest import build_manifest_v2, customer_payload_sha256, package_sha256, whitelist_project
    except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
        from scripts.build.manifest import build_manifest_v2, customer_payload_sha256, package_sha256, whitelist_project

    warnings: list[str] = []
    page_sources: list[dict[str, Any]] = []
    ordered = sorted(packages, key=lambda pkg: int(pkg.get("order") or 0))
    for index, package in enumerate(ordered, start=1):
        page_id = str(package.get("page_id") or f"page_{index:03d}")
        status = str(package.get("status") or "draft")
        approved = status in {"ready_for_build", "ready"}  # legacy "ready" mapped (F-N08)
        if production and not approved:
            raise BuildError(
                f"page package {page_id} is not approved for production build (status={status}); "
                "resolve evidence/design basis and approve the package first"
            )
        if not approved:
            warnings.append(f"page {page_id}: package status {status} (non-production build)")
        payload = whitelist_project(package)
        customer_visible = payload.get("customer_visible") or {}
        raw_role = (package.get("visual_spec") or {}).get("page_role") if isinstance(package.get("visual_spec"), dict) else ""
        page_role, role_warning = page_role_with_warning(raw_role)
        if role_warning:
            warnings.append(f"page {page_id}: {role_warning}")
        page_sources.append(
            {
                "page_id": page_id,
                "beat_id": str(package.get("beat_id") or page_id),
                "order": index,
                "title": str(customer_visible.get("title") or page_id),
                "page_role": page_role,
                "source_path": f"page_packages/{page_id}.json",
                "body_blocks": list(customer_visible.get("body_blocks") or []),
                "callouts": list(customer_visible.get("callouts") or []),
                "footnotes": list(customer_visible.get("footnotes") or []),
                "page_package_sha256": package_sha256(package),
                "customer_payload_sha256": customer_payload_sha256(package),
            }
        )
    return page_sources, warnings


def _prepare_build_from_packages(
    root: Path,
    request: dict[str, Any],
    backend: dict[str, Any],
    run_id: str,
    *,
    production: bool,
) -> dict[str, Any]:
    """SC-1 B5: standard build prepared directly from approved Page Packages."""

    try:
        from build.manifest import build_manifest_v2
        from production.page_package import PagePackageIndex
    except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
        from scripts.build.manifest import build_manifest_v2
        from scripts.production.page_package import PagePackageIndex

    packages = PagePackageIndex(root).list_packages()
    if not packages:
        raise BuildError("page_packages/index.json exists but no packages were found.")
    page_sources, warnings = _page_sources_from_packages(root, packages, production=production)

    build_dir = root / BUILD_DIR
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": BUILD_MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "prepared",
        "run_mode": _run_mode(request),
        "output_profile": _output_profile(request),
        "source_mode": "page_packages",
        "non_client_deliverable": True,
        "builder_backend": backend,
        "source_fingerprint": build_source_fingerprint(root),
        "page_count": len(page_sources),
        "pages": page_sources,
        "required_outputs": _required_outputs_for_profile(_output_profile(request)),
        "warnings": warnings,
        "created_at": _utc_now(),
    }
    write_json(build_dir / BUILD_MANIFEST_NAME, manifest)

    # Production runs additionally record the v2 build manifest — the
    # page-package-anchored contract consumed by content locks and readback.
    if production and backend.get("production_capable"):
        manifest_v2 = build_manifest_v2(
            run_id=run_id,
            packages=packages,
            builder_backend={
                "name": str(backend.get("backend_name") or backend.get("name") or "ppt-master"),
                "production_capable": True,
                "contract_versions": ["deck_page_package.v1", RENDER_RESULT_SCHEMA_VERSION],
            },
            output_profile=_output_profile(request),
            required_page_ids=[str(entry["page_id"]) for entry in page_sources],
            required_outputs=manifest["required_outputs"],
            builder_profile="standard",
        )
        write_json(build_dir / "build_manifest.v2.json", manifest_v2)

    append_event(
        root,
        "build.prepared",
        target=run_id,
        payload_ref=f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        data={"page_count": len(page_sources), "warning_count": len(warnings), "source_mode": "page_packages"},
    )
    return {
        "schema_version": "deck_build_prepare_result.v1",
        "status": "prepared",
        "run_id": run_id,
        "build_manifest": f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        "page_count": len(page_sources),
        "source_mode": "page_packages",
        "warnings": warnings,
    }


def prepare_build(run_dir: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    request = load_request(root)
    # Resolve historical evidence before creating any output, then retain the
    # first selection through the shared route lock/CAS transaction. Otherwise
    # our fresh manifest would be mistaken for an unidentified historical run.
    from build.build_route import persist_route
    route = persist_route(root, build_route(request, run_dir=root))
    if route.get("engine_id") == "deck_native":
        from build.native_engine import _assert_brief_conflicts_resolved
        _assert_brief_conflicts_resolved(root)
        backend = {"backend_name": "deck_native", "production_capable": True, "engine_route": route}
    else:
        backend = builder_backend_status()
    run_id = str(request.get("run_id") or root.name)
    packages_index = root / "page_packages" / "index.json"
    production = production_requires_builder_backend(_run_mode(request))
    if packages_index.exists():
        return _prepare_build_from_packages(root, request, backend, run_id, production=production)
    if production and route.get("engine_id") == "deck_native":
        raise BuildError(
            "native production build requires approved page_packages/ (run the producer first); "
            "preview_manifest is not a production input"
        )
    if production:
        # SC-1 B5: production builds consume approved page packages; the raw
        # preview manifest is no longer a production input.
        raise BuildError(
            "production build requires approved page_packages/ (run the producer first); "
            "preview_manifest is not a production input"
        )
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
        raw_page_role = page.get("page_role") or page.get("narrative_role") or page.get("role")
        page_role, role_warning = page_role_with_warning(raw_page_role)
        if role_warning:
            warnings.append(f"page {page_id}: {role_warning}")
        page_sources.append(
            {
                "page_id": page_id,
                "beat_id": str(page.get("beat_id") or page_id),
                "order": index,
                "title": str(page.get("title") or page.get("narrative_role") or page_id),
                "page_role": page_role,
                "source_path": source_ref,
            }
        )

    manifest = {
        "schema_version": BUILD_MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "prepared",
        "run_mode": _run_mode(request),
        "output_profile": _output_profile(request),
        "source_mode": CONTRACT_SMOKE_SOURCE_MODE,
        "non_client_deliverable": True,
        "builder_backend": backend,
        "source_fingerprint": build_source_fingerprint(root),
        "page_count": len(page_sources),
        "pages": page_sources,
        "required_outputs": _required_outputs_for_profile(_output_profile(request)),
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
        body_html = ""
        for block in page.get("body_blocks") or []:
            if not isinstance(block, dict):
                continue
            text = str(block.get("text") or "")
            if not text:
                continue
            kind = str(block.get("type") or "text")
            body_html += f"<p class=\"block-{escape(kind)}\">{escape(text)}</p>"
        sections.append(
            "<section class=\"page\" data-page-id=\""
            + escape(str(page.get("page_id") or ""))
            + "\">"
            + f"<h2>{escape(str(page.get('order') or ''))}. {escape(str(page.get('title') or 'Untitled'))}</h2>"
            + source_note
            + body_html
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


def _run_native_build(root: Path, request: dict[str, Any], run_id: str) -> dict[str, Any]:
    """SC-1.1 P1-01: the native route drives the built-in engine — it never
    writes an external render request or returns awaiting_external_render."""

    try:
        from build import native_engine
    except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
        from scripts.build import native_engine

    from build.native_tasks import approved_svg
    prepared = native_engine.prepare_native_run(root)
    route = native_engine.resolve_build_route(request, run_dir=root)
    authoring = str(route.get("authoring_mode") or "image_blueprint")

    from build.native_tasks import pending_native_task, dispatch_native_task
    pending_task = pending_native_task(root)
    if pending_task:
        pending_ids = {p["page_id"] for p in pending_task["pages"]}
        task = dispatch_native_task(root, pending_task["stage"], [p for p in native_engine._approved_packages(root) if p["page_id"] in pending_ids])
        return {"schema_version": "deck_build_run_result.v1", "status": task["status"],
                "run_id": run_id, "run_dir": str(root), "engine_id": "deck_native", "authoring_mode": authoring,
                "host_task": "build/host_imagegen_task.json", "pages": task["pages"],
                "resume_command": f"deck-master build run --run-dir {root}"}

    if authoring == "image_blueprint":
        # SC-1.1 review round 2 (P1-1): state-machine resume — advance by
        # what ALREADY exists instead of re-dispatching forever.
        approved_pages = [str(page) for page in prepared.get("pages", [])]
        missing_svgs = [page_id for page_id in approved_pages if not approved_svg(root, page_id)]
        if not missing_svgs:
            result = native_engine.run_native_compile(root, run_mode=_run_mode(request))
            backend = {"backend_name": "deck_native", "production_capable": True, "engine_route": route}
            return _finalize_native_build(root, request, result, backend, run_id)

        from build.native_tasks import dispatch_native_task, approved_blueprint
        stage = "reconstruct" if all(approved_blueprint(root, page) is not None for page in approved_pages) else "imagegen"
        pending = [pkg for pkg in native_engine._approved_packages(root)
                   if (approved_blueprint(root, pkg["page_id"]) is None if stage == "imagegen" else pkg["page_id"] in missing_svgs)]
        task = dispatch_native_task(root, stage, pending)
        return {
            "schema_version": "deck_build_run_result.v1", "status": task["status"],
            "run_id": run_id, "run_dir": str(root), "engine_id": "deck_native", "authoring_mode": authoring,
            "host_task": "build/host_imagegen_task.json", "pages": task["pages"],
            "runtime_probe": prepared.get("runtime_probe", {}), "resume_command": f"deck-master build run --run-dir {root}",
        }

    approved_pages = [str(page) for page in prepared.get("pages", [])]
    missing_svgs = [page_id for page_id in approved_pages if not approved_svg(root, page_id)]
    missing_scenes = [page_id for page_id in approved_pages if not (root / "high_density_build" / "page_scenes" / f"{page_id}.json").exists() and not (root / "high_density_build" / "page_scenes" / f"{page_id}.page_scene.json").exists()]
    if missing_svgs or missing_scenes:
        from build.native_tasks import dispatch_native_task
        pending = [pkg for pkg in native_engine._approved_packages(root) if pkg["page_id"] in set(missing_svgs + missing_scenes)]
        task = dispatch_native_task(root, "svg", pending)
        return {
            "schema_version": "deck_build_run_result.v1", "status": "awaiting_svg_authoring", "run_id": run_id,
            "run_dir": str(root), "engine_id": "deck_native", "authoring_mode": authoring,
            "missing_approved_svgs": missing_svgs, "missing_scenes": missing_scenes,
            "host_task": "build/host_imagegen_task.json", "pages": task["pages"],
            "runtime_probe": prepared.get("runtime_probe", {}), "resume_command": f"deck-master build run --run-dir {root}",
        }

    result = native_engine.run_native_compile(root, run_mode=_run_mode(request))
    backend = {"backend_name": "deck_native", "production_capable": True, "engine_route": route}
    return _finalize_native_build(root, request, result, backend, run_id)


def _finalize_native_build(root: Path, request: dict[str, Any], result: dict[str, Any], backend: dict[str, Any], run_id: str) -> dict[str, Any]:
    from workflow.actions import _acquire_run_lock, _release_run_lock, read_current_revision
    lock = _acquire_run_lock(root)
    try:
        if (read_current_revision(root).get("revision_id") or "initial") != result["build_revision"]:
            raise BuildError("native build revision changed during compilation; resume the current revision")
        return _finalize_native_build_locked(root, request, result, backend, run_id)
    finally:
        _release_run_lock(lock)


def _finalize_native_build_locked(
    root: Path,
    request: dict[str, Any],
    result: dict[str, Any],
    backend: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    """Write the standard build artifacts for a native compile so downstream
    consumers (build status, gates, delivery) read ONE chain of record."""

    packages = result["packages"]
    page_sources, warnings = _page_sources_from_packages(root, packages, production=production_requires_builder_backend(_run_mode(request)))
    manifest = {
        "schema_version": BUILD_MANIFEST_SCHEMA_VERSION, "run_id": run_id, "status": "prepared", "run_mode": _run_mode(request),
        "output_profile": _output_profile(request), "source_mode": "page_packages", "non_client_deliverable": True,
        "builder_backend": backend, "source_fingerprint": result["input_fingerprint"], "build_revision": result["build_revision"],
        "page_count": result["page_count"], "pages": page_sources, "required_outputs": _required_outputs_for_profile(_output_profile(request)),
        "warnings": warnings, "created_at": _utc_now(),
    }
    write_json(root / BUILD_DIR / BUILD_MANIFEST_NAME, manifest)
    build_dir = root / BUILD_DIR
    pptx_path = Path(str(result["pptx_path"])).expanduser().resolve()
    # SC-1.1 review round 2 (P1-2): a REAL native compile writes a REAL
    # client-deliverable identity — never the contract-smoke markers. The
    # validator runs in production mode (no smoke/deliverable waivers).
    artifacts = [
        _artifact(
            root,
            artifact_id="deck_pptx",
            kind="deck_pptx",
            path=pptx_path,
            editability="native_shapes",
            source_mode="native_compile",
            non_client_deliverable=False,
        ),
    ]
    rendered = result.get("render") or {}
    page_previews = []
    if rendered.get("status") == "rendered":
        pdf_path = Path(rendered["pdf_path"])
        artifacts.append(_artifact(root, artifact_id="deck_pdf", kind="deck_pdf", path=pdf_path, editability="raster", source_mode="native_compile", non_client_deliverable=False))
        for page in rendered["pages"]:
            page_path = Path(page["path"])
            artifacts.append(_artifact(root, artifact_id=f"page_png_{page['page_id']}", kind="page_png", path=page_path, page_id=page["page_id"], editability="raster", source_mode="native_compile", non_client_deliverable=False))
            page_previews.append({"page_id":page["page_id"],"preview_path":_run_relative(root,page_path)})
        html_path = pdf_path.parent / "index.html"
        html_path.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Presentation</title><style>body{margin:0;background:#202124}img{display:block;width:100%;max-width:1600px;margin:0 auto 16px}</style>' + ''.join(f'<section data-page-id="{escape(page["page_id"], quote=True)}"><img src="{escape(Path(page["path"]).name, quote=True)}" alt="Page {index}"></section>' for index,page in enumerate(rendered["pages"],1)) + '</html>', encoding="utf-8")
        artifacts.append(_artifact(root,artifact_id="deck_html",kind="deck_html",path=html_path,editability="raster",source_mode="native_compile",non_client_deliverable=False))
    artifact_manifest = {
        "schema_version": ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "run_mode": _run_mode(request),
        "source_mode": "native_compile",
        "non_client_deliverable": False,
        "builder_backend": backend,
        "source_fingerprint": manifest.get("source_fingerprint"),
        "build_revision": result["build_revision"],
        "page_count": manifest.get("page_count"),
        "artifacts": artifacts,
        "warnings": manifest.get("warnings", []),
        "created_at": _utc_now(),
    }
    artifact_validation = validate_artifact_manifest(
        root,
        artifact_manifest,
        expected_source_fingerprint=str(manifest.get("source_fingerprint") or ""),
        allow_contract_smoke=False,
        allow_non_client_deliverable=False,
    )
    artifact_manifest["validation"] = artifact_validation
    if not artifact_validation.get("valid"):
        raise BuildError("native artifact validation failed: " + "; ".join(artifact_validation.get("errors", [])))
    write_json(build_dir / ARTIFACT_MANIFEST_NAME, artifact_manifest)

    render_result = {
        "schema_version": RENDER_RESULT_SCHEMA_VERSION,
        "run_id": run_id,
        "session_id": "native-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "tool": "deck_native",
        "status": "completed",
        "run_mode": _run_mode(request),
        "output_profile": str(manifest.get("output_profile") or "client_delivery"),
        "source_mode": "native_compile",
        "non_client_deliverable": False,
        "builder_backend": backend,
        "artifact_path": _run_relative(root, pptx_path),
        "preview_dir": _run_relative(root, Path(rendered["pdf_path"]).parent) if rendered.get("status") == "rendered" else "",
        "page_count": int(manifest.get("page_count") or 0),
        "source_fingerprint": manifest.get("source_fingerprint"),
        "build_revision": result["build_revision"],
        "build_manifest": f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        "artifact_manifest": f"{BUILD_DIR}/{ARTIFACT_MANIFEST_NAME}",
        "artifacts": artifacts,
        "page_previews": page_previews,
        "warnings": manifest.get("warnings", []),
        "created_at": _utc_now(),
    }
    result_dir = root / RENDER_RESULTS_DIR
    result_dir.mkdir(parents=True, exist_ok=True)
    write_json(result_dir / RENDER_RESULT_NAME, render_result)
    append_event(
        root,
        "build.native_completed",
        target=run_id,
        payload_ref=f"{RENDER_RESULTS_DIR}/{RENDER_RESULT_NAME}",
        data={"engine_version": result.get("engine_version", ""), "page_count": render_result["page_count"]},
    )
    return {
        "schema_version": "deck_build_run_result.v1",
        "status": "completed",
        "run_id": run_id,
        "run_dir": str(root),
        "engine_id": "deck_native",
        "build_manifest": f"{BUILD_DIR}/{BUILD_MANIFEST_NAME}",
        "render_result": f"{RENDER_RESULTS_DIR}/{RENDER_RESULT_NAME}",
        "artifact_path": render_result["artifact_path"],
        "page_count": render_result["page_count"],
        "engine_version": result.get("engine_version", ""),
    }


def run_build(run_dir: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    request = load_request(root)
    backend = _assert_builder_backend_available(request, root=root)
    run_id = str(request.get("run_id") or root.name)
    # SC-1.1 P1-01: the native route drives the built-in engine BEFORE any
    # external-render handoff; only legacy routes reach the old request path.
    route = build_route(request, run_dir=root)
    explicit_native = str((request or {}).get("profile") or "").strip().lower().replace("_", "-") in {"native", "direct-svg"} or (
        root / "build" / "route.json"
    ).exists() and (load_persisted_route_local(root).get("engine_id") == "deck_native")
    if route.get("engine_id") == "deck_native" and (production_requires_builder_backend(_run_mode(request)) or explicit_native):
        # SC-1.1: every entry (production, or an explicit native/direct-svg
        # profile, or a persisted native route) drives the same engine.
        return _run_native_build(root, request, run_id)
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
    required_outputs = set(manifest.get("required_outputs") or _required_outputs_for_profile("client_delivery"))

    html_path = _write_html(root, manifest) if "deck_html" in required_outputs else None
    pdf_path = _write_pdf(root, manifest) if "deck_pdf" in required_outputs else None
    page_pngs = _write_page_pngs(root, manifest) if "page_png" in required_outputs else []
    pptx_path = _write_pptx(root, manifest)
    required_paths = [pptx_path]
    if html_path is not None:
        required_paths.append(html_path)
    if pdf_path is not None:
        required_paths.append(pdf_path)
    required_paths.extend(page_pngs)
    _assert_required_outputs(required_paths)

    artifacts = []
    if html_path is not None:
        artifacts.append(_artifact(root, artifact_id="deck_html", kind="deck_html", path=html_path, editability="native"))
    if pdf_path is not None:
        artifacts.append(_artifact(root, artifact_id="deck_pdf", kind="deck_pdf", path=pdf_path, editability="flat_image"))
    artifacts.append(_artifact(root, artifact_id="deck_pptx", kind="deck_pptx", path=pptx_path, editability="flat_image"))
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
        "output_profile": str(manifest.get("output_profile") or "client_delivery"),
        "source_mode": CONTRACT_SMOKE_SOURCE_MODE,
        "non_client_deliverable": True,
        "builder_backend": backend,
        "artifact_path": _run_relative(root, html_path or pptx_path),
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
        "artifact_path": str((html_path or pptx_path).relative_to(root)),
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
    from build.build_route import load_persisted_route
    native_route = load_persisted_route(root).get("engine_id") == "deck_native"
    if native_route and (build_manifest or render_result or artifact_manifest):
        from workflow.actions import read_current_revision
        current_revision = read_current_revision(root).get("revision_id") or "initial"
        if any(record.get("build_revision") != current_revision for record in (build_manifest, render_result, artifact_manifest)):
            status = "stale"
            artifact_validation = {**artifact_validation, "valid": False, "stale_revision": True}
    if native_route and status == "completed":
        from build.native_engine import native_build_fingerprint
        try:
            current_fingerprint = native_build_fingerprint(root)
        except (ValueError, RuntimeError, OSError) as exc:
            status = "invalid"
            artifact_validation = {**artifact_validation, "valid": False, "input_error": str(exc)}
        else:
            if any(record.get("source_fingerprint") != current_fingerprint for record in (build_manifest, render_result, artifact_manifest)):
                status = "stale"
                artifact_validation = {**artifact_validation, "valid": False, "stale_inputs": True}
    request_pages = ((render_request.get("inputs") or {}).get("pages") or []) if isinstance(render_request.get("inputs"), dict) else []
    page_count = (
        render_result.get("page_count")
        or render_request.get("page_count")
        or (len(request_pages) if isinstance(request_pages, list) else 0)
        or build_manifest.get("page_count")
        or 0
    )
    host_task_path = root / "build/host_imagegen_task.json"
    host_task = read_json(host_task_path) if host_task_path.exists() else {}
    if native_route:
        from build.native_tasks import pending_native_task
        pending_task = pending_native_task(root)
        if pending_task and status not in {"stale", "invalid"}:
            status = pending_task["status"]
            host_task = pending_task
    if status in {"missing", "prepared"} and host_task:
        from workflow.actions import action_applied
        pending = [page for page in host_task.get("pages", []) if not action_applied(root, page["action_id"])]
        if pending:
            status = str(host_task.get("status") or "awaiting_agent_execution")
    warnings = render_result.get("warnings") or render_request.get("warnings") or build_manifest.get("warnings") or []
    return {
        "schema_version": "deck_build_status.v1",
        "host_task": host_task,
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
