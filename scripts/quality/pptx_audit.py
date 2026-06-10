from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SLIDE_RE = re.compile(r"ppt/slides/slide(\d+)\.xml$")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slide_number(name: str) -> int:
    match = SLIDE_RE.match(name)
    return int(match.group(1)) if match else 0


def _slide_text(root: ElementTree.Element) -> str:
    parts = []
    for node in root.iter():
        if _local_name(node.tag) == "t" and node.text:
            parts.append(node.text.strip())
    return " ".join(part for part in parts if part)


def _picture_count(root: ElementTree.Element) -> int:
    return sum(1 for node in root.iter() if _local_name(node.tag) == "pic")


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
                forbidden_hits = [term for term in forbidden if term in text]
                slides.append(
                    {
                        "slide_number": _slide_number(name),
                        "path": name,
                        "title": text[:80],
                        "text_length": len(text),
                        "picture_count": picture_count,
                        "forbidden_terms": forbidden_hits,
                        "is_sparse": len(text) < 80 and picture_count == 0,
                        "possible_full_slide_image": picture_count == 1 and len(text) < 40,
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
        "sparse_pages": [slide for slide in slides if slide["is_sparse"]],
        "possible_full_slide_images": [
            slide for slide in slides if slide["possible_full_slide_image"]
        ],
        "forbidden_hits": [
            {
                "slide_number": slide["slide_number"],
                "terms": slide["forbidden_terms"],
            }
            for slide in slides
            if slide["forbidden_terms"]
        ],
    }
