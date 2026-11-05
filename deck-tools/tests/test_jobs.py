import json
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import Image, PngImagePlugin
from pptx import Presentation
from pptx.util import Inches
from deck_tools.jobs import compile_job, projection
from deck_tools.atoms import visible_atoms
from deck_tools.compiler.native import notes_records
from deck_tools.sanitize import OperationError, pptx
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


def test_exported_rich_text_keeps_url_whose_path_is_bold(tmp_path):
    body = "https://example.com/home/products"
    runs = [("https://example.com", False), ("/home/products", True)]
    result = compile_job(_rich_text_export_job(tmp_path, runs, notes=body))
    assert result["findings"]["status"] == "pass"
    assert body in _slide_paragraphs(result["pptx"])
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    root = ET.fromstring(_part_text(result["pptx"], "ppt/slides/slide1.xml"))
    bold_run = root.find('.//a:r[a:t="/home/products"]', namespace)
    assert bold_run is not None
    assert bold_run.find("a:rPr", namespace).get("b") == "1"


def test_exported_rich_text_keeps_bold_query_path_that_only_looks_local(tmp_path):
    body = "https://example.com/open?src=/Users/x"
    runs = [("https://example.com/open?src=", False), ("/Users/x", True)]
    result = compile_job(_rich_text_export_job(tmp_path, runs))
    assert result["findings"]["status"] == "pass"
    assert body in _slide_paragraphs(result["pptx"])
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    root = ET.fromstring(_part_text(result["pptx"], "ppt/slides/slide1.xml"))
    bold_run = root.find('.//a:r[a:t="/Users/x"]', namespace)
    assert bold_run is not None
    assert bold_run.find("a:rPr", namespace).get("b") == "1"


def test_exported_rich_text_rejects_local_path_after_public_url(tmp_path):
    runs = [("https://example.com/home/products ", False),
            ("/Users/example/document.txt", True)]
    with pytest.raises(OperationError):
        compile_job(_rich_text_export_job(tmp_path, runs))


def _pptx_with_text_boundary(tmp_path, before, after, boundary="br"):
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    text_frame = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2)).text_frame
    paragraph = text_frame.paragraphs[0]
    paragraph.add_run().text = before
    if boundary == "br":
        paragraph.add_line_break()
    elif boundary == "paragraph":
        paragraph = text_frame.add_paragraph()
    elif boundary == "textbox":
        paragraph = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(8), Inches(2)).text_frame.paragraphs[0]
    paragraph.add_run().text = after
    source = tmp_path / "boundary.pptx"
    presentation.save(source)
    return source


# Related counterexamples: test_exported_rich_text_still_rejects_local_path_across_runs
# and test_exported_text_rejects_url_credentials (including notes). Migration tests
# test_cleanup_rejection_names_actual_slide_field_and_rule cover attributes;
# test_url_exemption_preserves_path_and_credential_checks covers link-rule samples.
# Keep hard breaks, paragraphs and textboxes separate so they cannot invent a URL.
@pytest.mark.parametrize("boundary", ["br", "paragraph", "textbox"])
def test_sanitize_does_not_join_url_credentials_across_text_boundaries(tmp_path, boundary):
    fragments = ["https://example.com/open?api_", "key=synthetic_secret"]
    source = _pptx_with_text_boundary(tmp_path, *fragments, boundary=boundary)
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    root = ET.fromstring(_part_text(source, "ppt/slides/slide1.xml"))
    if boundary == "br":
        paragraphs = root.findall(".//a:p", namespace)
        assert len(paragraphs) == 1
        assert [node.tag.rsplit("}", 1)[-1] for node in paragraphs[0]] == ["r", "br", "r"]
    clean = BytesIO(pptx(source.read_bytes(), "boundary.pptx"))
    assert _slide_paragraphs(clean) == fragments
    clean.seek(0)
    root = ET.fromstring(_part_text(clean, "ppt/slides/slide1.xml"))
    assert len(root.findall(".//a:br", namespace)) == (1 if boundary == "br" else 0)


@pytest.mark.parametrize("fragments", [
    ["https://example.com/open?api_key=synthetic_secret", "Public text"],
    ["Public text", "https://example.com/open?api_key=synthetic_secret"],
])
def test_sanitize_rejects_url_credentials_on_either_side_of_hard_break(tmp_path, fragments):
    source = _pptx_with_text_boundary(tmp_path, *fragments)
    with pytest.raises(OperationError):
        pptx(source.read_bytes(), "boundary.pptx")


@pytest.mark.parametrize("runs", [
    [("see ", False), ("/home/products", True)],
    [("C:", False), ("/Users/x", True)],
    [("/ho", False), ("me/products", True)],
])
def test_exported_rich_text_still_rejects_local_path_across_runs(tmp_path, runs):
    with pytest.raises(OperationError):
        compile_job(_rich_text_export_job(tmp_path, runs))


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
