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
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import SourceUnreadable, SourceUnsupported, SourceNeedsTool

SUPPORTED_TEXT_FORMATS = {"txt", "md"}
SUPPORTED_STRUCTURED_FORMATS = {"json"}
SUPPORTED_DOCUMENT_FORMATS = {"pdf", "docx", "pptx"}
SUPPORTED_MEDIA_FORMATS = {"png", "jpg", "jpeg", "svg", "webp", "gif"}

SUPPORTED_EXTENSIONS = (
    SUPPORTED_TEXT_FORMATS | SUPPORTED_STRUCTURED_FORMATS
    | SUPPORTED_DOCUMENT_FORMATS | SUPPORTED_MEDIA_FORMATS
)


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
        raise SourceUnreadable(str(path), f"unreadable encoding: {exc}")
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
        raise SourceUnreadable(str(path), f"invalid JSON: {exc}")
    locators: list[dict] = []

    def walk(node, pointer: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                escaped=str(key).replace("~","~0").replace("/","~1")
                walk(value, f"{pointer}/{escaped}")
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
            detail="pdftotext not available on PATH; install Poppler or restore PATH",
        )
    result = subprocess.run(
        [tool, "-layout", str(path), "-"],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    )
    if result.returncode != 0:
        raise SourceUnreadable(str(path), f"pdftotext failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    text = result.stdout.decode("utf-8", "replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():pages.pop()
    locators = [
        {"locator": f"page-{index}", "kind": "page", "text": block.strip()}
        for index, block in enumerate(pages, start=1)
    ]
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format="pdf",
        format_kind="pdf",
        status="pending_visual",
        text=text,
        locators=locators,
        image_pages=[{"locator":f"page-{i}","reason":"verify visual layout and graphical meaning; text extraction alone is incomplete"} for i in range(1,len(pages)+1)],
        detail="PDF pages require Host visual verification; page numbers include textless pages",
    )


MAX_ZIP_MEMBER_BYTES = 50 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 200 * 1024 * 1024
MAX_ZIP_RATIO = 100


def _check_zip_limits(archive: zipfile.ZipFile, path: Path, members: list[str] | None = None) -> None:
    entries = [archive.getinfo(name) for name in members] if members is not None else archive.infolist()
    total = 0
    for info in entries:
        if info.file_size > MAX_ZIP_MEMBER_BYTES:
            raise SourceUnreadable(str(path), f"压缩包成员过大，超过安全上限：{info.filename}")
        total += info.file_size
        if total > MAX_ZIP_TOTAL_BYTES:
            raise SourceUnreadable(str(path), "压缩包总解压体积超过安全上限")
        if info.file_size > 1024 * 1024 and info.compress_size > 0:
            if info.file_size / info.compress_size > MAX_ZIP_RATIO:
                raise SourceUnreadable(str(path), f"压缩包压缩比异常，已拒绝读取：{info.filename}")


def _read_docx(path: Path) -> SourceExtract:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as archive:
            _check_zip_limits(archive, path, members=["word/document.xml"])
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise SourceUnreadable(str(path), f"unreadable DOCX: {exc}")
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    locators: list[dict] = []
    counter = 0
    has_images=any(e.tag.rsplit("}",1)[-1] in ("drawing","pict") for e in root.iter())
    def blocks(parent, body_covered=False):
        for child in parent:
            if child.tag == f"{namespace}p":
                if not body_covered:
                    yield child, False
                yield from blocks(child, True)
            elif child.tag == f"{namespace}tbl":
                yield child, body_covered
                yield from blocks(child, True)
            else:
                yield from blocks(child, body_covered)

    def table_parts(parent, wanted):
        for child in parent:
            if child.tag == f"{namespace}{wanted}":
                yield child
            elif child.tag not in {f"{namespace}{tag}" for tag in ("p", "tbl", "tr", "tc")}:
                yield from table_parts(child, wanted)

    def block_text(element):
        parts = []
        def visit(node):
            if node.tag == f"{namespace}t":
                parts.append(node.text or "")
                return
            boundary = node is not element and node.tag in {
                f"{namespace}{name}" for name in ("p", "tbl", "tr", "tc")}
            if boundary:
                parts.append("\n")
            for child in node:
                visit(child)
            if boundary:
                parts.append("\n")
        visit(element)
        return re.sub(r"\n+", "\n", "".join(parts)).strip("\n")

    text_parts = []
    for element, body_covered in blocks(root):
        tag = element.tag
        if tag == f"{namespace}p":
            text = block_text(element)
            if text.strip():
                counter += 1
                locators.append({"locator": f"p{counter}", "kind": "paragraph", "text": text})
                text_parts.append(text)
        elif tag == f"{namespace}tbl":
            counter += 1
            rows = []
            for row in table_parts(element, "tr"):
                cells = []
                for cell in table_parts(row, "tc"):
                    cell_text = block_text(cell)
                    cells.append(cell_text)
                rows.append(cells)
            locators.append({"locator": f"table{counter}", "kind": "table", "rows": rows})
            if not body_covered:
                text_parts.append(json.dumps(rows, ensure_ascii=False))
    text = "\n".join(text_parts)
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format="docx",
        format_kind="docx",
        status="pending_visual" if has_images else "read",
        text=text,
        locators=locators,
        tables=[item for item in locators if item["kind"]=="table"],
        image_pages=[{"locator":"document","reason":"embedded drawings require Host visual reading"}] if has_images else [],
    )


def _read_pptx(path: Path) -> SourceExtract:
    from lxml import etree

    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    ns_p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"

    def resolve_rel_target(base_part: str, target: str) -> str:
        from posixpath import dirname, join, normpath

        cleaned = target.lstrip("/") if target.startswith("/") else normpath(join(dirname(base_part), target))
        return cleaned

    def read_xml(archive: zipfile.ZipFile, part_name: str):
        _check_zip_limits(archive, path, members=[part_name])
        return etree.fromstring(archive.read(part_name), parser=parser)

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            slide_parts: list[str] = []
            if "ppt/presentation.xml" in names and "ppt/_rels/presentation.xml.rels" in names:
                pres = read_xml(archive, "ppt/presentation.xml")
                rels = read_xml(archive, "ppt/_rels/presentation.xml.rels")
                rel_map = {
                    rel.get("Id"): resolve_rel_target("ppt/presentation.xml", rel.get("Target", ""))
                    for rel in rels.findall(f"{{{ns_rel}}}Relationship")
                }
                for sld_id in pres.findall(f".//{{{ns_p}}}sldIdLst/{{{ns_p}}}sldId"):
                    target = rel_map.get(sld_id.get(f"{{{ns_r}}}id"))
                    if target and target in names:
                        slide_parts.append(target)
            if not slide_parts:
                slide_parts = sorted(
                    name for name in names
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                )
            if not slide_parts and "ppt/presentation.xml" not in names:
                raise SourceUnreadable(str(path), "unreadable PPTX: missing presentation.xml")

            locators: list[dict] = []
            text_parts: list[str] = []
            image_pages: list[dict] = []
            for index, slide_part in enumerate(slide_parts, start=1):
                root = read_xml(archive, slide_part)
                page_lines: list[str] = []
                visual = False
                for elem in root.iter():
                    tag = elem.tag
                    if tag in (f"{{{ns_p}}}pic", f"{{{ns_p}}}cxnSp"):
                        visual = True
                    elif tag == f"{{{ns_p}}}graphicFrame":
                        if elem.find(f".//{{{ns_a}}}tbl") is None:
                            visual = True
                    elif tag == f"{{{ns_p}}}sp":
                        nv = elem.find(f"{{{ns_p}}}nvSpPr/{{{ns_p}}}cNvSpPr")
                        is_textbox = nv is not None and nv.get("txBox") in ("1", "true")
                        if not is_textbox and elem.find(f".//{{{ns_a}}}prstGeom") is not None:
                            visual = True
                        if elem.find(f".//{{{ns_a}}}custGeom") is not None:
                            visual = True
                for tx_body in root.findall(f".//{{{ns_p}}}txBody"):
                    for paragraph in tx_body.findall(f"{{{ns_a}}}p"):
                        text = "".join(t.text or "" for t in paragraph.findall(f".//{{{ns_a}}}t"))
                        if text.strip():
                            page_lines.append(text)
                for tbl in root.findall(f".//{{{ns_a}}}tbl"):
                    rows = []
                    for tr in tbl.findall(f"{{{ns_a}}}tr"):
                        row_cells = []
                        for tc in tr.findall(f"{{{ns_a}}}tc"):
                            cell_paras = []
                            for p in tc.findall(f".//{{{ns_a}}}p"):
                                cell_paras.append("".join(t.text or "" for t in p.findall(f".//{{{ns_a}}}t")))
                            row_cells.append("\n".join(cell_paras))
                        rows.append(row_cells)
                    page_lines.append(json.dumps(rows, ensure_ascii=False))
                slide_rels_part = slide_part.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
                if slide_rels_part in names:
                    srels = read_xml(archive, slide_rels_part)
                    for rel in srels.findall(f"{{{ns_rel}}}Relationship"):
                        if (rel.get("Type") or "").endswith("/notesSlide"):
                            notes_part = resolve_rel_target(slide_part, rel.get("Target", ""))
                            if notes_part in names:
                                notes_root = read_xml(archive, notes_part)
                                note_lines = []
                                for sp in notes_root.findall(f".//{{{ns_p}}}sp"):
                                    ph = sp.find(f".//{{{ns_p}}}ph")
                                    if ph is not None and ph.get("type") == "body":
                                        for p in sp.findall(f".//{{{ns_a}}}p"):
                                            note_lines.append("".join(t.text or "" for t in p.findall(f".//{{{ns_a}}}t")))
                                notes = "\n".join(note_lines).strip()
                                if notes:
                                    page_lines.append("[speaker notes] " + notes)
                if visual or not page_lines:
                    image_pages.append({"locator": f"slide-{index}", "reason": "graphical meaning or textless slide requires actual visual reading"})
                locators.append({"locator": f"slide-{index}", "kind": "slide", "text": "\n".join(page_lines)})
                text_parts.append("\n".join(page_lines))
    except SourceUnreadable:
        raise
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError) as exc:
        raise SourceUnreadable(str(path), f"unreadable PPTX: {exc}")
    return SourceExtract(
        original_uri=str(path),
        original_sha256=measure_hash(path),
        format="pptx",
        format_kind="pptx",
        status="pending_visual" if image_pages else "read",
        text="\n\n".join(text_parts),
        locators=locators,
        image_pages=image_pages,
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
