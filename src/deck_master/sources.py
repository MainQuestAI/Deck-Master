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

from .errors import SourceUnreadable, SourceUnsupported, SourceNeedsTool

SUPPORTED_TEXT_FORMATS = {"txt", "md"}
SUPPORTED_STRUCTURED_FORMATS = {"json"}
SUPPORTED_DOCUMENT_FORMATS = {"pdf", "docx", "pptx"}
SUPPORTED_MEDIA_FORMATS = {"png", "jpg", "jpeg", "svg", "webp", "gif"}

SUPPORTED_EXTENSIONS = (
    SUPPORTED_TEXT_FORMATS | SUPPORTED_STRUCTURED_FORMATS
    | SUPPORTED_DOCUMENT_FORMATS | SUPPORTED_MEDIA_FORMATS
)

# Tool/cache directories are never material; a directory merely NAMED like an
# output (e.g. "output/") stays a normal directory (spec v1.1 §4).
TOOL_DIRECTORY_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".deckmaster"}

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


def _read_docx(path: Path) -> SourceExtract:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise SourceUnreadable(str(path), f"unreadable DOCX: {exc}")
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    locators: list[dict] = []
    counter = 0
    has_images=any(e.tag.rsplit("}",1)[-1] in ("drawing","pict") for e in root.iter())
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
        status="pending_visual" if has_images else "read",
        text=text,
        locators=locators,
        tables=[item for item in locators if item["kind"]=="table"],
        image_pages=[{"locator":"document","reason":"embedded drawings require Host visual reading"}] if has_images else [],
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
            detail="python-pptx not installed in this CLI environment",
        )
    try:
        presentation = Presentation(str(path))
    except Exception as exc:  # noqa: BLE001 - python-pptx raises broad errors
        raise SourceUnreadable(str(path), f"unreadable PPTX: {exc}")
    locators: list[dict] = []
    text_parts: list[str] = []
    image_pages=[]
    def shapes_recursive(shapes):
        for shape in shapes:
            yield shape
            if hasattr(shape,"shapes"):yield from shapes_recursive(shape.shapes)
    for index, slide in enumerate(presentation.slides, start=1):
        page_lines = []
        visual=False
        for shape in shapes_recursive(slide.shapes):
            if shape.shape_type in (13,3):visual=True
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
        if slide.has_notes_slide:
            notes=slide.notes_slide.notes_text_frame.text
            if notes.strip():page_lines.append("[speaker notes] "+notes)
        if visual or not page_lines:image_pages.append({"locator":f"slide-{index}","reason":"image/chart or textless slide requires actual visual reading"})
        locators.append({"locator": f"slide-{index}", "kind": "slide", "text": "\n".join(page_lines)})
        text_parts.append("\n".join(page_lines))
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


def read_source_snapshot(path: Path | str) -> tuple[SourceExtract, bytes]:
    """Read a single immutable byte snapshot, or report a material error.

    Parsing and the stored original must describe the same bytes even if the
    user edits the external file while an input transaction is in progress.
    Visual verification remains pending for image-bearing formats.
    """
    import tempfile
    import xml.etree.ElementTree as ET

    path = Path(path).expanduser().absolute()
    if path.suffix.lstrip('.').lower() not in SUPPORTED_EXTENSIONS:
        raise SourceUnsupported(str(path), f'no reader declared for {path.suffix}')
    try:
        data = path.read_bytes()
        with tempfile.TemporaryDirectory(prefix='deck-source-') as directory:
            snapshot = Path(directory) / path.name
            snapshot.write_bytes(data)
            extract = read_source(snapshot)
    except SourceUnreadable as exc:
        raise SourceUnreadable(str(path), exc.detail.replace(str(snapshot), str(path))) from exc
    except (OSError, ValueError, ET.ParseError, subprocess.TimeoutExpired) as exc:
        raise SourceUnreadable(str(path), f'material could not be read: {exc}') from exc
    if extract.status == 'needs_tool':
        raise SourceNeedsTool(str(path), extract.detail)
    if extract.status not in ('read', 'pending_visual'):
        raise SourceUnreadable(str(path), extract.detail or 'material reader did not complete')
    extract.original_uri = str(path)
    extract.original_sha256 = sha256_bytes(data)
    return extract, data


def discover_sources(paths, *, out_dir: Path | str | None = None) -> dict:
    """Expand user-given files and directories into a stable material list.

    Explicitly named files are the user's choice: a missing, unreadable or
    unsupported one raises and the whole create fails before any Document is
    written (exit 2). Directory expansion never raises: tool directories,
    Office lock files, zero-byte temporaries, the project ``--out`` directory
    and symlinks leaving the authorized roots are skipped with a reason, and
    unsupported formats are skipped too — noise never blocks creation.
    Returns ``{"adopted": [Path], "skipped": [{path, reason}],
    "errored": [{path, code, detail}]}`` with adopted sorted stably.
    """
    roots = [Path(p).expanduser() for p in paths]
    def resolve_explicit(root):
        try:
            return root.resolve()
        except (OSError, RuntimeError) as exc:
            raise SourceUnreadable(str(root), f'material path cannot be resolved: {exc}') from exc

    resolved_roots = {root: resolve_explicit(root) for root in roots}
    authorized = {resolved_roots[root] for root in roots if root.exists()}
    exclude = Path(out_dir).expanduser().resolve() if out_dir is not None else None
    adopted: list[Path] = []
    skipped: list[dict] = []
    errored: list[dict] = []
    explicit = {resolved_roots[root] for root in roots if not root.is_dir()}
    visited_directories: set[Path] = set()

    def skip(path: Path, reason: str) -> None:
        skipped.append({"path": str(path), "reason": reason})

    def note_error(path: Path, code: str, detail: str) -> None:
        errored.append({"path": str(path), "code": code, "detail": detail})

    def _within_authorized(target: Path) -> bool:
        return any(target == root or root in target.parents for root in authorized)

    def check_explicit_file(path: Path) -> None:
        if not path.is_file():
            raise SourceUnreadable(f"(source {path})", f"material not found: {path}")
        try:
            path.read_bytes()
        except OSError as exc:
            raise SourceUnreadable(f"(source {path})", f"material cannot be read: {exc}") from exc
        ext = path.suffix.lstrip(".").lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise SourceUnsupported(f"(source {path})", f"no reader declared for .{ext}: {path}")

    def handle_file(path: Path, *, explicit: bool) -> None:
        if explicit:
            check_explicit_file(path)
            adopted.append(path)
            return
        if path.name.startswith("~$"):
            skip(path, "office lock file")
            return
        try:
            size = path.stat().st_size
        except OSError as exc:
            note_error(path, "source_unreadable", str(exc))
            return
        if size == 0:
            skip(path, "zero-byte temporary file")
            return
        ext = path.suffix.lstrip(".").lower()
        if ext not in SUPPORTED_EXTENSIONS:
            skip(path, f"unsupported format .{ext}")
            skipped[-1]['code'] = 'source_unsupported'
            return
        adopted.append(path)

    def walk(directory: Path) -> None:
        try:
            resolved = directory.resolve()
        except (OSError, RuntimeError) as exc:
            skip(directory, f'symlink or path resolution failed: {exc}')
            return
        if resolved in visited_directories:
            skip(directory, 'already visited directory (symlink cycle or duplicate root)')
            return
        visited_directories.add(resolved)
        try:
            entries = sorted(directory.iterdir(), key=lambda p: str(p))
        except OSError as exc:
            note_error(directory, "source_unreadable", str(exc))
            return
        for entry in entries:
            try:
                target = entry.resolve()
            except (OSError, RuntimeError) as exc:
                skip(entry, f'symlink or path resolution failed: {exc}')
                continue
            if exclude is not None and target == exclude:
                skip(entry, "project --out directory")
                continue
            if entry.is_symlink():
                if not target.exists():
                    skip(entry, "broken symlink target")
                    continue
                if not _within_authorized(target):
                    skip(entry, "symlink outside the authorized material roots")
                    continue
            if entry.is_dir():
                if entry.name in TOOL_DIRECTORY_NAMES:
                    skip(entry, "tool directory")
                    continue
                walk(entry)
            else:
                handle_file(entry, explicit=False)

    for root in roots:
        if not root.exists():
            raise SourceUnreadable(f"(source {root})", f"material not found: {root}")
        if exclude is not None and resolved_roots[root] == exclude:
            skip(root, "project --out directory")
            continue
        if root.is_symlink():
            target = resolved_roots[root]
            if not target.exists() or not _within_authorized(target):
                skip(root, "symlink outside the authorized material roots")
                continue
        if root.is_dir():
            if root.name in TOOL_DIRECTORY_NAMES:
                skip(root, "tool directory")
                continue
            walk(root)
        else:
            handle_file(root, explicit=True)
    # Explicit roots keep call order; directory contents are walked in stable
    # lexical order. No global re-sort: the user's naming order is information.
    return {"adopted": adopted, "skipped": skipped, "errored": errored, "explicit": explicit}


def tail_constraint(extract: SourceExtract) -> str:
    """Material tail constraints live at the very end; kept as part of the real input (AC-C01)."""
    if not extract.text:
        return ""
    lines = [line.strip() for line in extract.text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1]
