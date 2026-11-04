import json
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import Image, PngImagePlugin
from deck_tools.jobs import compile_job, projection
from deck_tools.atoms import visible_atoms
from deck_tools.compiler.native import notes_records
from deck_tools.sanitize import OperationError
from hostenv import resolve_host_font


def test_rust_nested_bullets_keep_every_visible_atom():
    page = {"id": "p1", "content": {"title": "Main", "body_blocks": [
        {"type": "bullets", "id": "b", "items": [{"id": "i", "text": "Parent", "children": [
            {"id": "child", "text": "Nested"}]}]}]}}
    original = json.dumps(page)
    assert [a["text"] for a in visible_atoms(projection(page))] == ["Main", "Parent", "Nested"]
    assert json.dumps(page) == original


def job_fixture(tmp_path):
    family = resolve_host_font()
    logo = tmp_path / "logo.png"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Source", "/Users/private/source.png")
    Image.new("RGB", (12, 12), "teal").save(logo, pnginfo=metadata)
    svg = tmp_path / "page.svg"
    svg.write_text(f'<svg viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#ffffff"/>'
                   f'<image href="logo" x="1100" y="40" width="60" height="60"/>'
                   f'<text data-atom-id="atom:p1:title" x="60" y="100" font-family="{family}" font-size="36">Main</text></svg>')
    return {"pages": [{"id": "p1", "content": {"title": "Main"}, "notes": "First\n\nLast\n", "svg": str(svg)}],
            "canvas": {"width_px": 1280, "height_px": 720, "slide_width_in": 13.333, "slide_height_in": 7.5},
            "fonts": [family], "assets": {"logo": str(logo)}, "output": str(tmp_path / "out")}


def test_native_build_reads_projection_preserves_notes_and_cleans_asset_metadata(tmp_path):
    result = compile_job(job_fixture(tmp_path))
    assert result["findings"]["status"] == "pass"
    assert notes_records(Path(result["pptx"]))[0]["notes"] == "First\n\nLast\n"
    with zipfile.ZipFile(result["pptx"]) as archive:
        for name in archive.namelist():
            assert b"/Users/private" not in archive.read(name)
        assert "docProps/custom.xml" not in archive.namelist()
        assert any(name.startswith("ppt/media/") for name in archive.namelist())


def test_check_page_compiles_and_returns_readback_without_gating_text_findings(tmp_path, monkeypatch):
    job = job_fixture(tmp_path)
    job["pages"][0]["content"]["title"] = "Changed text"
    preview = tmp_path / "preview.png"
    Image.new("RGB", (16, 9), "white").save(preview)
    monkeypatch.setattr("deck_tools.jobs.render_deck", lambda *a, **kw: [preview])
    result = compile_job(job, preview=True)
    assert result["preview"] == str(preview)
    assert result["findings"]["status"] == "fail"
    assert any(f["code"] == "missing_visible_atom" for f in result["findings"]["findings"])


def _text_export_job(tmp_path, body, notes=""):
    family = resolve_host_font()
    svg = tmp_path / "page.svg"
    svg.write_text(
        '<svg viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#ffffff"/>'
        f'<text data-atom-id="atom:p1:title" x="40" y="80" font-family="{family}" font-size="12">{body}</text></svg>',
        encoding="utf-8",
    )
    return {"pages": [{"id": "p1", "content": {"title": body}, "notes": notes, "svg": str(svg)}],
            "canvas": {"width_px": 1280, "height_px": 720, "slide_width_in": 13.333, "slide_height_in": 7.5},
            "fonts": [family], "assets": {}, "output": str(tmp_path / "out")}


def _part_text(pptx_path, name):
    with zipfile.ZipFile(pptx_path) as archive:
        return archive.read(name).decode("utf-8")


@pytest.mark.parametrize("body", [
    "https://example.com/open?source=file:///Users/synthetic/private/project.txt",
    "https://example.com/open?source=C:\\Users\\synthetic\\private\\project.txt",
    "https://example.com/open?source=file:/Users/synthetic/private/project.txt",
    "https://example.com/open?source=C:/Users/synthetic/private/project.txt",
    "https://example.com/open?source=C:/synthetic/private/project.txt",
])
def test_exported_http_text_rejects_embedded_local_paths(tmp_path, body):
    with pytest.raises(OperationError):
        compile_job(_text_export_job(tmp_path, body, notes="Public note"))


def test_exported_http_text_keeps_ordinary_site_paths(tmp_path):
    body = "https://example.com/home/products"
    result = compile_job(_text_export_job(tmp_path, body, notes=body))
    assert result["findings"]["status"] == "pass"
    assert body in _part_text(result["pptx"], "ppt/slides/slide1.xml")
    assert body in _part_text(result["pptx"], "ppt/notesSlides/notesSlide1.xml")


def test_exported_http_text_keeps_query_paths_that_only_look_local(tmp_path):
    body = "https://example.com/open?src=/Users/x"
    result = compile_job(_text_export_job(tmp_path, body, notes=body))
    assert result["findings"]["status"] == "pass"
    assert body in _part_text(result["pptx"], "ppt/slides/slide1.xml")
    assert body in _part_text(result["pptx"], "ppt/notesSlides/notesSlide1.xml")


@pytest.mark.parametrize("body,notes", [
    ("https://example.com/open?api_key=synthetic_secret", "Public note"),
    ("https://user:password@example.com/home/products", "Public note"),
    ("Visible title", "https://example.com/open?api_key=synthetic_secret"),
    ("Visible title", "https://user:password@example.com/home/products"),
])
def test_exported_text_rejects_url_credentials(tmp_path, body, notes):
    with pytest.raises(OperationError):
        compile_job(_text_export_job(tmp_path, body, notes=notes))


def test_exported_text_keeps_urls_without_credentials(tmp_path):
    body = "https://example.com/open?source=catalog"
    result = compile_job(_text_export_job(tmp_path, body, notes=body))
    assert result["findings"]["status"] == "pass"
    assert body in _part_text(result["pptx"], "ppt/slides/slide1.xml")
    assert body in _part_text(result["pptx"], "ppt/notesSlides/notesSlide1.xml")


def _rich_text_export_job(tmp_path, runs, notes="Public note"):
    """One SVG text box whose tspans compile to styled runs in one paragraph."""
    family = resolve_host_font()
    body = "".join(text for text, _bold in runs)
    first, *rest = runs
    weight = ' font-weight="700"' if first[1] else ""
    tspans = []
    for text, bold in rest:
        span_weight = ' font-weight="700"' if bold else ""
        tspans.append(f'<tspan x="40" dy="0"{span_weight}>{text}</tspan>')
    svg = tmp_path / "page.svg"
    svg.write_text(
        '<svg viewBox="0 0 1280 720"><rect width="1280" height="720" fill="#ffffff"/>'
        f'<text data-atom-id="atom:p1:title" x="40" y="80" font-family="{family}" font-size="18"'
        f' data-text-width="1200" data-text-height="48"{weight}>{first[0]}{"".join(tspans)}</text></svg>',
        encoding="utf-8",
    )
    return {"pages": [{"id": "p1", "content": {"title": body}, "notes": notes, "svg": str(svg)}],
            "canvas": {"width_px": 1280, "height_px": 720, "slide_width_in": 13.333, "slide_height_in": 7.5},
            "fonts": [family], "assets": {}, "output": str(tmp_path / "out")}


def _slide_paragraphs(pptx_path):
    """Visible run text of each slide paragraph, split at hard line breaks."""
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    with zipfile.ZipFile(pptx_path) as archive:
        root = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
    paragraphs = []
    for paragraph in root.findall(".//a:p", namespace):
        segments = []
        chunks = []
        for child in paragraph:
            kind = child.tag.rsplit("}", 1)[-1]
            if kind == "br":
                segments.append("".join(chunks))
                chunks = []
            elif kind in ("r", "fld"):
                chunks.append("".join(node.text or "" for node in child.iter() if node.tag.rsplit("}", 1)[-1] == "t"))
        segments.append("".join(chunks))
        paragraphs.extend(segment for segment in segments if segment)
    return paragraphs


@pytest.mark.parametrize("runs", [
    [("https://example.com/open?api_key=", False), ("synthetic_secret", True)],
    [("https://example.com/open?api_", False), ("key=synthetic_secret", True)],
])
def test_exported_rich_text_rejects_url_credentials_split_across_runs(tmp_path, runs):
    with pytest.raises(OperationError):
        compile_job(_rich_text_export_job(tmp_path, runs))


def test_exported_rich_text_keeps_public_url(tmp_path):
    body = "https://example.com/open?source=catalog"
    runs = [("https://example.com/open?source=", False), ("catalog", True)]
    result = compile_job(_rich_text_export_job(tmp_path, runs, notes=body))
    assert result["findings"]["status"] == "pass"
    assert body in _slide_paragraphs(result["pptx"])
    assert body in _part_text(result["pptx"], "ppt/notesSlides/notesSlide1.xml")


def test_invalid_svg_cli_reports_element_without_publishing_file(tmp_path):
    job = job_fixture(tmp_path)
    Path(job["pages"][0]["svg"]).write_text('<svg viewBox="0 0 1280 720"><rect id="broken" width="40" height="40" class="unsupported"/></svg>')
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job))
    result = subprocess.run([sys.executable, "-m", "deck_tools", "check-page", str(path)], capture_output=True, text=True)
    assert result.returncode == 4
    assert not result.stdout
    assert json.loads(result.stderr)["element_id"] == "broken"
    assert not Path(job["output"]).exists()
