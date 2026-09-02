from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SLIDE_RE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
NOTES_RE = re.compile(r"ppt/notesSlides/notesSlide(\d+)\.xml$")
MASTER_RE = re.compile(r"ppt/slideMasters/slideMaster(\d+)\.xml$")
LAYOUT_RE = re.compile(r"ppt/slideLayouts/slideLayout(\d+)\.xml$")
COMMENT_RE = re.compile(r"ppt/comments/comment(\d+)\.xml$")
CHART_RE = re.compile(r"ppt/charts/chart(\d+)\.xml$")
DOC_PROPS_RE = re.compile(r"docProps/(?:core|app|custom)\.xml$")
PRESENTATION_RE = re.compile(r"ppt/presentation\.xml$")
TEXT_ATTRS = {"descr", "title"}
SPARSE_ALLOWED_ROLES = {"cover", "section", "section_divider", "divider", "toc", "agenda", "visual", "visual_divider", "image", "image_page"}


def _read_optional_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _normalize_page_role(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _page_role(page: dict[str, Any]) -> str:
    for key in ("page_role", "role", "page_type"):
        value = _normalize_page_role(page.get(key))
        if value:
            return value
    visual_spec = page.get("visual_spec")
    if isinstance(visual_spec, dict):
        for key in ("page_type", "role"):
            value = _normalize_page_role(visual_spec.get(key))
            if value:
                return value
    enrichment = page.get("enrichment")
    if isinstance(enrichment, dict):
        analysis = enrichment.get("analysis")
        if isinstance(analysis, dict):
            value = _normalize_page_role(analysis.get("page_role"))
            if value:
                return value
    return ""


def _add_manifest_roles(roles: dict[int, str], payload: dict[str, Any], *, root: Path) -> None:
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        try:
            slide_number = int(page.get("order") or index)
        except (TypeError, ValueError):
            slide_number = index
        role = _page_role(page)
        scene_ref = str(page.get("page_scene") or "").strip()
        if not role and isinstance(page.get("page_scene"), dict):
            scene_ref = str((page.get("page_scene") or {}).get("path") or "").strip()
        if not role and scene_ref:
            scene = _read_optional_json(root / scene_ref)
            role = _page_role(scene)
        if not role:
            package_ref = str(
                page.get("page_package_path")
                or page.get("page_package_ref")
                or page.get("package_path")
                or ""
            ).strip()
            if package_ref:
                role = _page_role(_read_optional_json(root / package_ref))
        if role:
            roles[slide_number] = role


def load_page_roles(run_dir: str | Path | None) -> dict[int, str]:
    """Load optional slide roles while keeping unknown pages on content rules."""
    if run_dir is None:
        return {}
    root = Path(run_dir).expanduser().resolve()
    roles: dict[int, str] = {}
    # Lower-confidence sources are loaded first; the high-density manifest wins.
    for path in (
        root / "preview_manifest.json",
        root / "page_packages" / "index.json",
        root / "build" / "build_manifest.json",
        root / "high_density_build" / "manifest.json",
        root / "high_density_build" / "high_density_manifest.json",
    ):
        payload = _read_optional_json(path)
        if path.name == "index.json" and path.parent.name == "page_packages":
            pages = payload.get("pages")
            if isinstance(pages, list):
                for index, item in enumerate(pages, start=1):
                    if not isinstance(item, dict):
                        continue
                    package_path = str(item.get("path") or item.get("page_package_path") or "").strip()
                    if not package_path and item.get("page_id"):
                        package_path = f"page_packages/{item['page_id']}.json"
                    if package_path:
                        package = _read_optional_json(root / package_path)
                        if package:
                            item = {**item, **package}
                    try:
                        slide_number = int(item.get("order") or index)
                    except (TypeError, ValueError):
                        slide_number = index
                    role = _page_role(item)
                    if role:
                        roles[slide_number] = role
            continue
        _add_manifest_roles(roles, payload, root=root)
    return roles


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slide_number(name: str) -> int:
    match = SLIDE_RE.match(name)
    return int(match.group(1)) if match else 0


def _scope_for_path(name: str) -> tuple[str, int | None]:
    for scope, pattern in (
        ("slide", SLIDE_RE),
        ("notes", NOTES_RE),
        ("slide_master", MASTER_RE),
        ("slide_layout", LAYOUT_RE),
        ("comment", COMMENT_RE),
        ("chart", CHART_RE),
    ):
        match = pattern.match(name)
        if match:
            return scope, int(match.group(1))
    if DOC_PROPS_RE.match(name):
        return "doc_props", None
    if PRESENTATION_RE.match(name):
        return "presentation", None
    return "", None


def _is_scannable_xml(name: str) -> bool:
    scope, _number = _scope_for_path(name)
    return scope in {"slide", "notes", "comment", "doc_props"}


def _xml_text(root: ElementTree.Element) -> str:
    parts = []
    for node in root.iter():
        if node.text and node.text.strip():
            parts.append(node.text.strip())
        for attr_name, attr_value in node.attrib.items():
            if _local_name(attr_name) in TEXT_ATTRS and attr_value.strip():
                parts.append(attr_value.strip())
    return " ".join(part for part in parts if part)


def _slide_text(root: ElementTree.Element) -> str:
    return _xml_text(root)


def _picture_count(root: ElementTree.Element) -> int:
    return sum(1 for node in root.iter() if _local_name(node.tag) == "pic")


def _term_hits(text: str, forbidden: list[str]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for term in forbidden:
        if term.lower() in lowered and term not in hits:
            hits.append(term)
    return hits


def _excerpt(text: str, term: str, *, radius: int = 42) -> str:
    index = text.lower().find(term.lower())
    if index < 0:
        return text[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def audit_pptx(
    pptx_path: str | Path,
    expected_pages: int | None = None,
    forbidden_terms: list[str] | None = None,
    page_roles: dict[int, str] | list[str] | None = None,
) -> dict[str, Any]:
    path = Path(pptx_path).expanduser().resolve()
    forbidden = [term for term in (forbidden_terms or []) if term]
    if not path.exists():
        raise ValueError(f"PPTX not found: {path}")

    slides = []
    text_items: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []
    missing_page_roles: list[int] = []
    media_files = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            slide_names = sorted(
                [name for name in names if SLIDE_RE.match(name)],
                key=_slide_number,
            )
            media_files = sorted(name for name in names if name.startswith("ppt/media/"))
            for name in slide_names:
                xml = archive.read(name)
                root = ElementTree.fromstring(xml)
                text = _slide_text(root)
                picture_count = _picture_count(root)
                slide_hits = _term_hits(text, forbidden)
                slide_number = _slide_number(name)
                if isinstance(page_roles, dict):
                    page_role = _normalize_page_role(page_roles.get(slide_number))
                elif isinstance(page_roles, list) and slide_number - 1 < len(page_roles):
                    page_role = _normalize_page_role(page_roles[slide_number - 1])
                else:
                    page_role = ""
                if not page_role:
                    if page_roles is not None:
                        missing_page_roles.append(slide_number)
                    page_role = "content"
                sparse_allowed = page_role in SPARSE_ALLOWED_ROLES
                slides.append(
                    {
                        "slide_number": slide_number,
                        "path": name,
                        "page_role": page_role,
                        "title": text[:80],
                        "text_length": len(text),
                        "picture_count": picture_count,
                        "forbidden_terms": slide_hits,
                        "is_sparse": (len(text) < 80 and picture_count == 0) and not sparse_allowed,
                        "possible_full_slide_image": (picture_count == 1 and len(text) < 40) and not sparse_allowed,
                    }
                )
            for name in sorted(name for name in names if _is_scannable_xml(name)):
                xml = archive.read(name)
                root = ElementTree.fromstring(xml)
                scope, number = _scope_for_path(name)
                text = _xml_text(root)
                if not text:
                    continue
                item = {
                    "scope": scope,
                    "package_path": name,
                    "slide_number": number,
                    "text": text,
                    "text_length": len(text),
                }
                text_items.append(item)
                for term in _term_hits(text, forbidden):
                    forbidden_hits.append(
                        {
                            "scope": scope,
                            "package_path": name,
                            "slide_number": number,
                            "term": term,
                            "terms": [term],
                            "excerpt": _excerpt(text, term),
                        }
                    )
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid PPTX package: {path}") from exc
    except ElementTree.ParseError as exc:
        raise ValueError(f"Invalid PPTX slide XML in {path}: {exc}") from exc

    return {
        "artifact": str(path),
        "slide_count": len(slides),
        "expected_pages": expected_pages,
        "page_count_matches": expected_pages is None or expected_pages == len(slides),
        "media_count": len(media_files),
        "media_files": media_files,
        "slides": slides,
        "missing_page_roles": missing_page_roles,
        "text_items": text_items,
        "sparse_pages": [slide for slide in slides if slide["is_sparse"]],
        "possible_full_slide_images": [
            slide for slide in slides if slide["possible_full_slide_image"]
        ],
        "forbidden_hits": forbidden_hits,
    }
