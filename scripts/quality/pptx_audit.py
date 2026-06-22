from __future__ import annotations

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
TEXT_ATTRS = {"descr", "title", "name"}


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
    return bool(scope)


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
) -> dict[str, Any]:
    path = Path(pptx_path).expanduser().resolve()
    forbidden = [term for term in (forbidden_terms or []) if term]
    if not path.exists():
        raise ValueError(f"PPTX not found: {path}")

    slides = []
    text_items: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []
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
                slides.append(
                    {
                        "slide_number": _slide_number(name),
                        "path": name,
                        "title": text[:80],
                        "text_length": len(text),
                        "picture_count": picture_count,
                        "forbidden_terms": slide_hits,
                        "is_sparse": len(text) < 80 and picture_count == 0,
                        "possible_full_slide_image": picture_count == 1 and len(text) < 40,
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
        "text_items": text_items,
        "sparse_pages": [slide for slide in slides if slide["is_sparse"]],
        "possible_full_slide_images": [
            slide for slide in slides if slide["possible_full_slide_image"]
        ],
        "forbidden_hits": forbidden_hits,
    }
