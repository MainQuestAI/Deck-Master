"""T11/AC-K11 render evidence: SVG and PPT are each rendered with the real
toolchain (rsvg-convert; soffice+pdftoppm) and the PNGs are checked for
semantic foreground content, not mere existence."""
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.pipeline import NeedsTool, executable, render_deck, run

REQUIRED_TOOLS = ('rsvg-convert', 'soffice', 'pdftoppm', 'fc-match')


def resolve_font():
    from hostenv import host_fonts
    return host_fonts()


def assert_real_rendering(png_path):
    assert png_path.is_file() and png_path.stat().st_size > 0
    with Image.open(png_path) as image:
        assert image.size[0] > 50 and image.size[1] > 50
        gray = image.convert('L')
        lo, hi = gray.getextrema()
        # Foreground content present: the frame is not a single flat color.
        assert hi - lo > 20, f'{png_path.name} looks blank (extrema {lo},{hi})'
        assert len(image.convert('RGB').getcolors(maxcolors=1_000_000) or []) > 2


@pytest.mark.render
def test_renderers_available_on_this_machine():
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(
        __import__('os').environ.get('DECK_MASTER_' + tool.upper().replace('-', '_'), tool)) is None]
    assert missing == [], f'renderers missing on this machine: {missing}'


@pytest.mark.render
def test_svg_renders_with_rsvg_convert(tmp_path, resolvable_font_family):
    # SVG side of AC-K11: real rasterisation with rsvg-convert.
    svg = tmp_path / 'slide.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
                   '<rect width="200" height="100" fill="#ffffff"/>'
                   '<rect x="20" y="20" width="80" height="60" fill="#c00000"/>'
                   f'<text x="120" y="60" font-family="{resolvable_font_family}" font-size="18">渲染</text>'
                   '</svg>')
    png = tmp_path / 'slide.png'
    run([executable('rsvg-convert'), str(svg), '-o', str(png)])
    assert_real_rendering(png)


@pytest.mark.render
def test_ppt_renders_with_soffice_pdftoppm_chain(tmp_path, resolvable_font_family):
    # PPT side of AC-K11: real compile, then the render_deck chain
    # (soffice -> pdf -> pdftoppm) with semantic PNG evidence per slide.
    fonts = {resolvable_font_family: resolve_font()[resolvable_font_family]}
    svg = tmp_path / 'page.svg'
    svg.write_text('<svg viewBox="0 0 200 100"><rect width="200" height="100" fill="#ffffff"/>'
                   '<rect x="20" y="20" width="80" height="60" fill="#003399"/>'
                   f'<text x="120" y="60" font-family="{resolvable_font_family}" font-size="18">渲染证据</text>'
                   '</svg>')
    compiled = compile_deck([SvgInput('p1', svg)], CompileOptions(width_px=200, height_px=100, fonts=fonts),
                            tmp_path / 'compiled')
    renders = render_deck(compiled.pptx_path, tmp_path / 'rendered', fonts=fonts)
    assert len(renders) == 1
    assert_real_rendering(renders[0])


def test_missing_renderer_is_reported_not_silent(tmp_path, monkeypatch):
    # AC-K11: with renderers unavailable the pipeline reports NeedsTool
    # (recorded upstream as not evaluated) instead of fabricating previews.
    monkeypatch.setenv('PATH', '')
    for tool in REQUIRED_TOOLS:
        with pytest.raises(NeedsTool, match=tool):
            executable(tool)
