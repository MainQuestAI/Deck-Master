"""T09 text emission evidence: font weight, font matching/fallback, and
multiline Chinese layout, all read back from real slide XML.
"""
import json
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from deck_master.compiler import compile_deck, CompileOptions, SvgInput

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}

FAMILY = 'Hiragino Sans GB'


def _fc_match(query):
    if not shutil.which('fc-match'):
        return None
    output = subprocess.run(['fc-match', '-f', '%{family}\n%{file}', query],
                            capture_output=True, text=True, check=True).stdout.splitlines()
    if len(output) < 2:
        return None
    families, filename = output[0], output[1]
    if Path(filename).exists() and FAMILY in families.split(','):
        return filename
    return None


def resolve_fonts():
    """Resolve real font files for FAMILY; fail loudly if none is available."""
    regular = _fc_match(FAMILY)
    bold = _fc_match(f'{FAMILY}:weight=bold') or regular
    if regular is None:
        # fc-match unavailable or substituted another family: probe known
        # macOS system font locations directly.
        candidates = sorted(Path('/System/Library/Fonts').glob('Hiragino Sans GB*.ttc'))
        if not candidates:
            candidates = [p for p in Path('/System/Library/Fonts').glob('*.ttc')
                          if 'PingFang' in p.name or 'Hiragino' in p.name]
        if not candidates:
            pytest.fail(f'no resolvable real font for {FAMILY}: fc-match unavailable or '
                        'substituted, and no known system CJK font found')
        regular = str(candidates[0])
        bold = regular
    return regular, bold


def compile_slide(tmp_path, body, fonts, name='text'):
    svg = tmp_path / f'{name}.svg'
    svg.write_text(f'<svg viewBox="0 0 400 300">{body}</svg>')
    result = compile_deck([SvgInput('text', svg)],
                          CompileOptions(width_px=400, height_px=300, fonts=fonts),
                          tmp_path / f'{name}-out')
    with zipfile.ZipFile(result.pptx_path) as z:
        root = ET.fromstring(z.read('ppt/slides/slide1.xml'))
    manifest = json.loads((result.manifest_path).read_text())
    return root, manifest


def text_shape(root, name):
    for sp in root.iter('{%s}sp' % NS['p']):
        node = sp.find('p:nvSpPr/p:cNvPr', NS)
        if node is not None and node.get('name') == name:
            return sp
    raise AssertionError(f'text shape {name} not found in slide XML')


def run_props(sp):
    props = sp.find('p:txBody/a:p/a:r/a:rPr', NS)
    assert props is not None, 'expected a:rPr run in slide XML'
    return props


def test_bold_800_900_and_typefaces_in_slide_xml(tmp_path):
    # AC-K04: 800/900 weight must emit b="1" (never normal/omitted) and the
    # declared family must appear on latin/ea/cs typefaces in the real PPT.
    regular, bold = resolve_fonts()
    fonts = {FAMILY: regular, f'{FAMILY}:bold': bold}
    root, manifest = compile_slide(tmp_path, f'''
      <text id="w8" x="10" y="30" font-family="{FAMILY}" font-size="16" font-weight="800">字重八百</text>
      <text id="w9" x="10" y="60" font-family="{FAMILY}" font-size="16" font-weight="900">字重九百</text>
    ''', fonts)
    assert manifest['fonts'][f'{FAMILY}:bold']['sha256']
    assert manifest['fonts'][FAMILY]['sha256']
    for shape_id in ('w8:0', 'w9:0'):
        props = run_props(text_shape(root, shape_id))
        assert props.get('b') == '1', f'{shape_id} must stay bold in slide XML'
        assert props.get('sz') == '1200'
        for tag in ('latin', 'ea', 'cs'):
            node = props.find(f'a:{tag}', NS)
            assert node is not None and node.get('typeface') == FAMILY


def test_font_fallback_to_family_file_still_bold(tmp_path):
    # AC-K04 fallback: without an explicit "family:bold" entry the emitter uses
    # the family file for measuring but must still write b="1" to the slide.
    regular, _ = resolve_fonts()
    root, manifest = compile_slide(tmp_path,
                                   f'<text id="fb" x="10" y="30" font-family="{FAMILY}" '
                                   f'font-size="16" font-weight="800">回退粗体</text>',
                                   {FAMILY: regular})
    assert f'{FAMILY}:bold' not in manifest['fonts']
    props = run_props(text_shape(root, 'fb:0'))
    assert props.get('b') == '1'


def test_missing_font_file_raises_with_location(tmp_path):
    # AC-K04 contract: emit requires real font files from CompileOptions.fonts.
    svg = tmp_path / 'nofont.svg'
    svg.write_text(f'<svg viewBox="0 0 400 300"><text x="10" y="30" font-family="{FAMILY}">缺字体</text></svg>')
    with pytest.raises(ValueError, match='font file not supplied'):
        compile_deck([SvgInput('text', svg)], CompileOptions(width_px=400, height_px=300, fonts={}),
                     tmp_path / 'nofont-out')


def test_multiline_chinese_tspans_preserve_layout_in_slide_xml(tmp_path):
    # AC-K06: each tspan is its own editable run shape in the real PPT with the
    # expected baseline offset, line spacing, bold, center alignment, letter
    # spacing, and ea typeface. Positions are asserted geometrically; a joined
    # string match would not cover layout loss.
    regular, bold = resolve_fonts()
    fonts = {FAMILY: regular, f'{FAMILY}:bold': bold}
    root, _ = compile_slide(tmp_path, f'''
      <text id="t" x="200" y="60" font-family="{FAMILY}" font-size="24" font-weight="800"
            text-anchor="middle" letter-spacing="2">
        <tspan x="200" y="60">季度业务增长</tspan>
        <tspan x="200" dy="40">结构与展望</tspan>
      </text>
    ''', fonts)
    runs = [text_shape(root, 't:0'), text_shape(root, 't:1')]
    off0 = runs[0].find('p:spPr/a:xfrm/a:off', NS)
    off1 = runs[1].find('p:spPr/a:xfrm/a:off', NS)
    ext0 = runs[0].find('p:spPr/a:xfrm/a:ext', NS)
    # Two separate runs, not one merged paragraph.
    assert int(off1.get('y')) - int(off0.get('y')) == 40 * 9525
    # Baseline sits 0.88em above the box top; box height is 1.5em.
    assert int(off0.get('y')) == round((60 - 24 * 0.88) * 9525)
    assert int(ext0.get('cy')) == round(24 * 1.5 * 9525)
    # Anchor=middle: box centre stays on the declared anchor x.
    centre0 = int(off0.get('x')) + int(ext0.get('cx')) / 2
    centre1 = int(off1.get('x')) + int(runs[1].find('p:spPr/a:xfrm/a:ext', NS).get('cx')) / 2
    assert abs(centre0 - 200 * 9525) <= 2
    assert abs(centre1 - 200 * 9525) <= 2
    texts = [t.text for sp in runs for t in sp.iter('{%s}t' % NS['a'])]
    assert texts == ['季度业务增长', '结构与展望']
    for sp in runs:
        props = run_props(sp)
        assert props.get('b') == '1'
        assert props.get('sz') == '1800'
        assert props.get('spc') == '150'
        ea = props.find('a:ea', NS)
        assert ea is not None and ea.get('typeface') == FAMILY
        align = sp.find('p:txBody/a:p/a:pPr', NS)
        assert align is not None and align.get('algn') == 'ctr'


def test_rotated_text_stays_at_ir_anchor_in_slide_xml(tmp_path):
    # Rotation is applied once (sh.rotation); the box stays centred on the IR
    # anchor instead of being pre-rotated and rotated again.
    regular, _ = resolve_fonts()
    root, _ = compile_slide(tmp_path,
                            f'<g transform="rotate(90 0 0)"><text id="rot" x="10" y="20" '
                            f'font-family="{FAMILY}" font-size="10">旋转</text></g>',
                            {FAMILY: regular})
    sp = text_shape(root, 'rot:0')
    xfrm = sp.find('p:spPr/a:xfrm', NS)
    assert xfrm.get('rot') == '5400000'
    off = xfrm.find('a:off', NS)
    # IR anchor after rotation is (-20, 10); the box top-left is anchor minus
    # the 0.88em ascender offset on y only.
    assert int(off.get('x')) == -20 * 9525
    assert int(off.get('y')) == round((10 - 10 * 0.88) * 9525)


def test_letter_spacing_written_exactly_once(tmp_path):
    # The api post-pass owns spc writing; the emitter must not duplicate it.
    regular, _ = resolve_fonts()
    root, _ = compile_slide(tmp_path,
                            '<text id="spc" x="10" y="30" font-family="Hiragino Sans GB" '
                            'font-size="16" letter-spacing="2">间距</text>',
                            {FAMILY: regular})
    props = run_props(text_shape(root, 'spc:0'))
    assert props.get('spc') == '150'
    import zipfile as _zip
    from deck_master.compiler import CompileOptions, SvgInput, compile_deck
    svg = tmp_path / 'once.svg'
    svg.write_text('<svg viewBox="0 0 400 300"><text id="t" x="10" y="30" '
                   'font-family="Hiragino Sans GB" font-size="16" letter-spacing="2">间距</text></svg>')
    result = compile_deck([SvgInput('t', svg)], CompileOptions(width_px=400, height_px=300,
                          fonts={FAMILY: regular}), tmp_path / 'once-out')
    with _zip.ZipFile(result.pptx_path) as archive:
        xml_text = archive.read('ppt/slides/slide1.xml').decode('utf-8')
    assert xml_text.count('spc=') == 1, 'letter spacing appears exactly once in the slide XML'
