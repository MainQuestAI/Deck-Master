"""Material reading for the rebuilt core (spec 04.2).

Sources are read from the user's existing paths; nothing requires moving
files into a library first. Every extract keeps the real measured file hash,
its locators, and the full text. A missing tool is reported as ``needs_tool``
with the format named — never an empty success (AC-C08). Unknown original
hashes never block reading stored media (spec 03.2).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_TEXT_FORMATS = {"txt", "md"}
SUPPORTED_STRUCTURED_FORMATS = {"json"}
SUPPORTED_DOCUMENT_FORMATS = {"pdf", "docx", "pptx"}
SUPPORTED_MEDIA_FORMATS = {"png", "jpg", "jpeg", "svg", "webp", "gif"}

FORMAT_KIND = {
    "txt": "text",
    "md": "text",
    "json": "json",
    "pdf": "pdf",
    "docx": "docx",
    "pptx": "pptx",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class SourceExtract:
    """What was actually read from one material file."""

    original_uri: str
    original_sha256: str | None
    format: str
    format_kind: str
    status: str  # "read" | "needs_tool" | "pending_visual"
    text: str = ""
    locators: list[dict] = field(default_factory=list)  # [{locator, kind, text}]
    tables: list[dict] = field(default_factory=list)  # [{locator, cells}]
    image_pages: list[dict] = field(default_factory=list)  # [{locator, reason}]
    detail: str = ""


def measure_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locators_from_text(text: str) -> list[dict]:
    locators = []
    for index, line in enumerate(text.splitlines(), start=1):
        kind = "line" if line.strip() else "blank"
        locators.append({"locator": f"L{index}", "kind": kind, "text": line})
    return locators


def _read_text(path: Path, ext: str) -> SourceExtract:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return SourceExtract(
            original_uri=str(path),
            original_sha256=None,
            format=ext,
            format_kind="text",
            status="needs_tool",
            detail=f"unreadable encoding: {exc}",
        )
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format=ext,
        format_kind="text",
        status="read",
        text=text,
        locators=_locators_from_text(text),
    )


def measure_hash(path: Path) -> str:
    return measure_file(path)


def _read_json(path: Path) -> SourceExtract:
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return SourceExtract(
            original_uri=str(path),
            original_sha256=digest,
            format="json",
            format_kind="json",
            status="needs_tool",
            detail=f"invalid JSON: {exc}",
        )
    locators: list[dict] = []

    def walk(node, pointer: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")
        else:
            text = _scalar_text(node)
            if text is not None:
                locators.append({"locator": pointer, "kind": "value", "text": text})

    walk(payload, "")
    return SourceExtract(
        original_uri=str(path),
        original_sha256=digest,
        format="json",
        format_kind="json",
        status="read",
        text=json.dumps(payload, ensure_ascii=False, indent=1),
        locators=locators,
    )


def _scalar_text(node) -> str | None:
    if node is None:
        return "null"
    if isinstance(node, bool):
        return "true" if node else "false"
    if isinstance(node, (int, float)):
        return json.dumps(node, ensure_ascii=False, allow_nan=False)
    if isinstance(node, str):
        return node
    return None


def _read_pdf(path: Path) -> SourceExtract:
    tool = shutil.which("pdftotext")
    if tool is None:
        return SourceExtract(
            original_uri=str(path),
            original_sha256=measure_hash(path),
            format="pdf",
            format_kind="pdf",
            status="needs_tool",
            detail="pdftotext not available on this machine",
        )
    result = subprocess.run(
        [tool, "-layout", str(path), "-"],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    )
    if result.returncode != 0:
        return SourceExtract(
            original_uri=str(path),
            original_sha256=measure_hash(path),
            format="pdf",
            format_kind="pdf",
            status="needs_tool",
            detail=f"pdftotext failed: {result.stderr.decode('utf-8', 'replace').strip()}",
        )
    text = result.stdout.decode("utf-8", "replace")
    pages = [block.strip() for block in text.split("\f") if block.strip()]
    locators = [
        {"locator": f"page-{index}", "kind": "page", "text": block[:4000]}
        for index, block in enumerate(pages, start=1)
    ]
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format="pdf",
        format_kind="pdf",
        status="read",
        text=text,
        locators=locators,
    )


def _read_docx(path: Path) -> SourceExtract:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        return SourceExtract(
            original_uri=str(path),
            original_sha256=measure_hash(path),
            format="docx",
            format_kind="docx",
            status="needs_tool",
            detail=f"unreadable DOCX: {exc}",
        )
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    locators: list[dict] = []
    counter = 0
    for element in root.iter():
        tag = element.tag
        if tag == f"{namespace}p":
            text = "".join(node.text or "" for node in element.iter(f"{namespace}t"))
            if text.strip():
                counter += 1
                locators.append({"locator": f"p{counter}", "kind": "paragraph", "text": text})
        elif tag == f"{namespace}tbl":
            counter += 1
            rows = []
            for row in element.findall(f"{namespace}tr"):
                cells = []
                for cell in row.findall(f"{namespace}tc"):
                    cell_text = "".join(
                        node.text or "" for node in cell.iter(f"{namespace}t")
                    )
                    cells.append(cell_text)
                rows.append(cells)
            locators.append({"locator": f"table{counter}", "kind": "table", "rows": rows})
    text = "\n".join(
        item["text"] if "text" in item else json.dumps(item["rows"], ensure_ascii=False)
        for item in locators
    )
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format="docx",
        format_kind="docx",
        status="read",
        text=text,
        locators=locators,
    )


def _read_pptx(path: Path) -> SourceExtract:
    try:
        from pptx import Presentation
    except ImportError:
        return SourceExtract(
            original_uri=str(path),
            original_sha256=measure_hash(path),
            format="pptx",
            format_kind="pptx",
            status="needs_tool",
            detail="python-pptx not installed",
        )
    try:
        presentation = Presentation(str(path))
    except Exception as exc:  # noqa: BLE001 - python-pptx raises broad errors
        return SourceExtract(
            original_uri=str(path),
            original_sha256=measure_hash(path),
            format="pptx",
            format_kind="pptx",
            status="needs_tool",
            detail=f"unreadable PPTX: {exc}",
        )
    locators: list[dict] = []
    text_parts: list[str] = []
    for index, slide in enumerate(presentation.slides, start=1):
        page_lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in paragraph.runs)
                    if text.strip():
                        page_lines.append(text)
            if getattr(shape, "has_table", False):
                rows = [
                    [cell.text for cell in row.cells]
                    for row in shape.table.rows
                ]
                page_lines.append(json.dumps(rows, ensure_ascii=False))
        locators.append({"locator": f"slide-{index}", "kind": "slide", "text": "\n".join(page_lines)})
        text_parts.append("\n".join(page_lines))
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format="pptx",
        format_kind="pptx",
        status="read",
        text="\n\n".join(text_parts),
        locators=locators,
    )


def read_source(path: Path | str) -> SourceExtract:
    """Read one material file by extension; unknown formats are named, not swallowed."""
    source_path = Path(path).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(f"material not found: {source_path}")
    ext = source_path.suffix.lstrip(".").lower()
    if ext in SUPPORTED_TEXT_FORMATS:
        return _read_text(source_path, ext)
    if ext == "json":
        return _read_json(source_path)
    if ext == "pdf":
        return _read_pdf(source_path)
    if ext == "docx":
        return _read_docx(source_path)
    if ext == "pptx":
        return _read_pptx(source_path)
    if ext in SUPPORTED_MEDIA_FORMATS:
        return SourceExtract(
            original_uri=str(source_path),
            original_sha256=measure_hash(source_path),
            format=ext,
            format_kind="image",
            status="pending_visual",
            detail="image page must be read visually by the Host, not by text extraction",
        )
    return SourceExtract(
        original_uri=str(source_path),
        original_sha256=measure_hash(source_path),
        format=ext,
        format_kind="unknown",
        status="needs_tool",
        detail=f"no reader declared for .{ext}",
    )


def tail_constraint(extract: SourceExtract) -> str:
    """Material tail constraints live at the very end; kept as part of the real input (AC-C01)."""
    if not extract.text:
        return ""
    lines = [line.strip() for line in extract.text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1]
