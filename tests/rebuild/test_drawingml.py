"""T10/AC-K13 subset evidence: every declared shape family lands as the
expected DrawingML structure in a real PPT, and out-of-subset input still
fails explicitly."""
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.compiler.svg import SvgError

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


from hostenv import host_fonts, resolve_host_font

FAMILY = resolve_host_font()


def resolve_font():
    return host_fonts()


def compile_sample(tmp_path, body, assets=None, name='sample', fonts=None):
    svg = tmp_path / f'{name}.svg'
    svg.write_text(f'<svg viewBox="0 0 200 100">{body}</svg>')
    return compile_deck([SvgInput('p1', svg)],
                        CompileOptions(width_px=200, height_px=100, assets=assets or {},
                                       fonts=fonts or {}),
                        tmp_path / f'{name}-out')


def slide_root(result):
    with zipfile.ZipFile(result.pptx_path) as z:
        return ET.fromstring(z.read('ppt/slides/slide1.xml'))


def named_shape(root, name):
    for sp in root.iter('{%s}sp' % NS['p']):
        node = sp.find('p:nvSpPr/p:cNvPr', NS)
        if node is not None and node.get('name') == name:
            return sp
    raise AssertionError(f'shape {name} not found')


def test_declared_subset_structures_in_slide_xml(tmp_path):
    # AC-K13: line/path/icon/table(pure shape group)/image/gradient each land
    # as the matching DrawingML structure in the actual slide XML.
    asset = tmp_path / 'photo.png'
    Image.new('RGB', (12, 8), (200, 30, 30)).save(asset)
    result = compile_sample(tmp_path, f'''
      <defs><g id="icon"><rect width="10" height="10" fill="#1478ff"/><path d="M1 9 L9 1" stroke="#000000" fill="none"/></g></defs>
      <line id="ln" x1="5" y1="5" x2="60" y2="30" stroke="#000000"/>
      <path id="curve" d="M 70 10 C 90 40, 110 40, 130 10" fill="none" stroke="#0000ff"/>
      <use id="icon-use" href="#icon" x="140" y="5"/>
      <g id="table">
        <rect id="cell-1" x="10" y="50" width="40" height="20" fill="#eeeeee"/>
        <rect id="cell-2" x="50" y="50" width="40" height="20" fill="#dddddd"/>
        <text id="cell-1-text" x="14" y="64" font-family="{FAMILY}" font-size="10">表头一</text>
        <text id="cell-2-text" x="54" y="64" font-family="{FAMILY}" font-size="10">表头二</text>
      </g>
      <image id="photo" href="photo.png" x="150" y="50" width="40" height="40"/>
      <defs><linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#ff0000"/><stop offset="1" stop-color="#0000ff"/>
      </linearGradient></defs>
      <rect id="shaded" x="100" y="50" width="40" height="20" fill="url(#fade)"/>
    ''', assets={'p1': {'photo.png': str(asset)}}, fonts=resolve_font())
    root = slide_root(result)
    # line -> custGeom with moveTo+lnTo
    line_path = named_shape(root, 'ln').find('p:spPr/a:custGeom/a:pathLst/a:path', NS)
    ops = [child.tag.rsplit('}', 1)[-1] for child in line_path]
    assert ops == ['moveTo', 'lnTo']
    # curved path -> flattened custGeom with several lnTo segments
    curve_path = named_shape(root, 'curve').find('p:spPr/a:custGeom/a:pathLst/a:path', NS)
    ops = [child.tag.rsplit('}', 1)[-1] for child in curve_path]
    assert ops[0] == 'moveTo' and ops.count('lnTo') >= 4
    # icon g/use -> member shapes emitted with their own stable ids
    members = {sp.find('p:nvSpPr/p:cNvPr', NS).get('name')
               for sp in root.iter('{%s}sp' % NS['p'])}
    assert 'rect' in members and 'path' in members
    # table -> editable shapes + text runs (not an Office table object)
    named_shape(root, 'cell-1')
    named_shape(root, 'cell-2')
    for sp in (named_shape(root, 'cell-1-text:0'), named_shape(root, 'cell-2-text:0')):
        assert sp.find('p:txBody/a:p/a:r/a:t', NS) is not None
    assert root.find('.//{%s}graphicFrame' % NS['p']) is None
    # image -> picture with embedded blip
    picture = root.find('.//{%s}pic' % NS['p'])
    assert picture is not None
    assert picture.find('.//a:blip', NS).get('{%s}embed' % NS['r'])
    # gradient -> gradFill with two stops on a linear angle
    grad = named_shape(root, 'shaded').find('p:spPr/a:gradFill', NS)
    assert grad is not None
    stops = grad.findall('a:gsLst/a:gs', NS)
    assert len(stops) == 2
    assert grad.find('a:lin', NS) is not None
    # canvas -> slide size follows CompileOptions, no hidden hardcoded page
    with zipfile.ZipFile(result.pptx_path) as z:
        presentation = ET.fromstring(z.read('ppt/presentation.xml'))
    sld_sz = presentation.find('p:sldSz', NS)
    assert int(sld_sz.get('cx')) == 200 * 9525
    assert int(sld_sz.get('cy')) == 100 * 9525


@pytest.mark.parametrize('body', [
    '<rect width="10" height="10" filter="blur(2)"/>',
    '<animate attributeName="x"/>',
    '<foreignObject/>',
])
def test_out_of_subset_input_fails_explicitly_at_compile(tmp_path, body):
    # AC-K13 counter-case: anything outside the declared subset still raises a
    # located SvgError instead of being silently dropped at compile time.
    with pytest.raises(SvgError):
        compile_sample(tmp_path, body, name='out-of-subset')
