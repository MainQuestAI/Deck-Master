"""T10/AC-K01 isolation: compile_deck depends only on the SVG bytes, approved
assets and explicit parameters; input bytes are consistency-checked; a failed
compile never publishes deck.pptx."""
import json
import os
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import ImageFont

import deck_master.compiler.native as native_emit
from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from hostenv import host_fonts, resolve_host_font

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compile_isolated_from_home_cwd_and_repo(monkeypatch, tmp_path):
    # Only SVG bytes + explicit parameters: no HOME/config/env defaults, cwd in
    # an empty directory, and the manifest leaks no repository absolute paths.
    home = tmp_path / 'empty-home'
    home.mkdir()
    for key in ('HOME', 'USERPROFILE', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
                'DECK_MASTER_NODE_EXECUTABLE', 'DECK_MASTER_ARTIFACT_MODULE'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.chdir(tmp_path)
    svg = tmp_path / 'isolated.svg'
    svg.write_text('<svg viewBox="0 0 960 720"><rect width="960" height="720" fill="#102030"/></svg>')
    result = compile_deck([SvgInput('p1', svg)],
                          CompileOptions(width_px=960, height_px=720), tmp_path / 'out')
    assert result.pptx_path.is_file()
    manifest_text = result.manifest_path.read_text()
    assert str(REPO_ROOT) not in manifest_text
    assert json.loads(manifest_text)['pages'][0]['page_id'] == 'p1'


def test_input_bytes_changed_mid_compile_is_rejected(monkeypatch, tmp_path):
    # Compile reads the input up front; if the bytes change during compilation
    # the result is rejected instead of registering a mixed input.
    svg = tmp_path / 'changing.svg'
    svg.write_text('<svg viewBox="0 0 960 720"><rect width="960" height="720"/></svg>')
    original_emit = native_emit.emit

    def mutating_emit(pages, width, height, fonts, output):
        svg.write_text('<svg viewBox="0 0 960 720"><rect width="400" height="200"/></svg>')
        return original_emit(pages, width, height, fonts, output)

    monkeypatch.setattr(native_emit, 'emit', mutating_emit)
    with pytest.raises(ValueError, match='input changed during compilation'):
        compile_deck([SvgInput('p1', svg)], CompileOptions(width_px=960, height_px=720),
                     tmp_path / 'out')
    assert not (tmp_path / 'out' / 'deck.pptx').exists()


def test_failed_compile_publishes_no_pptx(tmp_path):
    # A failed emit (missing required font file) must not leave deck.pptx behind.
    svg = tmp_path / 'text.svg'
    svg.write_text('<svg viewBox="0 0 960 720"><text x="50" y="200" font-family="Noto Sans SC">文字</text></svg>')
    with pytest.raises(ValueError, match='font file not supplied'):
        compile_deck([SvgInput('p1', svg)], CompileOptions(width_px=960, height_px=720, fonts={}),
                     tmp_path / 'out')
    assert not (tmp_path / 'out' / 'deck.pptx').exists()


def test_text_box_slack_does_not_cause_false_slide_overflow(tmp_path):
    family = resolve_host_font()
    fonts = host_fonts()
    size = 16
    glyph_width = ImageFont.truetype(fonts[family], size=1000).getlength('A') / 1000 * size
    x = 200 - glyph_width - 2
    svg = tmp_path / 'near-edge.svg'
    svg.write_text(f'<svg viewBox="0 0 200 100"><text x="{x}" y="50" '
                   f'font-family="{family}" font-size="{size}">A</text></svg>')
    result = compile_deck([SvgInput('p1', svg)],
                          CompileOptions(width_px=200, height_px=100, fonts=fonts),
                          tmp_path / 'near-edge-out')
    ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
          'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    with zipfile.ZipFile(result.pptx_path) as archive:
        slide = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
    shape = slide.find('.//p:sp/p:spPr/a:xfrm', ns)
    off = shape.find('a:off', ns)
    ext = shape.find('a:ext', ns)
    assert int(off.get('x')) + int(ext.get('cx')) <= 200 * 9525
