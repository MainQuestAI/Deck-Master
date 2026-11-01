import json
from pathlib import Path
import subprocess
import sys
import zipfile

from PIL import Image, PngImagePlugin
from deck_tools.jobs import compile_job, projection
from deck_tools.atoms import visible_atoms
from deck_tools.compiler.native import notes_records
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
