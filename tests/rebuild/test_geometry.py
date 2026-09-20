import math
import zipfile
import xml.etree.ElementTree as ET
import pytest
from deck_master.compiler.svg import parse_svg, SvgError


def parse(body):
    return parse_svg(f'<svg viewBox="0 0 200 200">{body}</svg>'.encode(), page_id='geometry')['shapes']


NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def compile_slide(tmp_path, body, name='page', fonts=None):
    from deck_master.compiler import compile_deck, CompileOptions, SvgInput
    svg = tmp_path / f'{name}.svg'
    svg.write_text(f'<svg viewBox="0 0 200 100">{body}</svg>')
    result = compile_deck([SvgInput('geometry', svg)],
                          CompileOptions(width_px=200, height_px=100, fonts=fonts or {}),
                          tmp_path / f'{name}-out')
    with zipfile.ZipFile(result.pptx_path) as z:
        return ET.fromstring(z.read('ppt/slides/slide1.xml'))


def slide_shape(root, name):
    for sp in root.iter('{%s}sp' % NS['p']):
        node = sp.find('p:nvSpPr/p:cNvPr', NS)
        if node is not None and node.get('name') == name:
            return sp
    raise AssertionError(f'shape {name} not found in slide XML')


def path_points(sp):
    path = sp.find('p:spPr/a:custGeom/a:pathLst/a:path', NS)
    assert path is not None, 'expected custGeom path in slide XML'
    points = []
    for child in path:
        op = child.tag.rsplit('}', 1)[-1]
        pt = child.find('a:pt', NS)
        points.append((op, None if pt is None else int(pt.get('x')), None if pt is None else int(pt.get('y'))))
    return path, points


def test_rotated_circle_and_ellipse_bounds():
    circle=parse('<circle cx="50" cy="50" r="10" transform="rotate(45 50 50)"/>')[0]
    assert circle['width']==pytest.approx(20)
    assert circle['height']==pytest.approx(20)
    ellipse=parse('<ellipse cx="50" cy="50" rx="20" ry="10" transform="rotate(45 50 50)"/>')[0]
    xs,ys=zip(*ellipse['points'])
    assert max(xs)-min(xs)==pytest.approx(math.sqrt(1000))
    assert max(ys)-min(ys)==pytest.approx(math.sqrt(1000))


def test_nested_use_inherits_style_and_transforms():
    shapes=parse('<defs><symbol id="icon"><path d="M0 0L10 10"/></symbol></defs><g transform="translate(20 30)"><use href="#icon" x="5" fill="none" stroke="#ff0000"/></g>')
    assert shapes[0]['stroke']=='#ff0000'
    assert shapes[0]['commands'][0]['moveTo']=={'x':25,'y':30}


def test_arc_endpoints_and_scaled_stroke():
    shape=parse('<path d="M 10 20 A 20 10 0 0 1 50 20" fill="none" stroke="#000000" stroke-width="2" transform="scale(2)"/>')[0]
    assert shape['commands'][0]['moveTo']=={'x':20,'y':40}
    assert shape['commands'][-1]['lineTo']=={'x':100,'y':40}
    assert shape['stroke_width']==4


def test_referenced_external_use_rejected():
    with pytest.raises(SvgError,match='local use'):
        parse('<use href="https://example.org/icon.svg#x"/>')


def test_rounded_rect_distinct_radii_and_rotation_keeps_geometry():
    shape=parse('<rect x="10" y="20" width="80" height="40" rx="10" ry="5" transform="rotate(90 50 40)"/>')[0]
    pts=[p for command in shape['commands'] for op,p in command.items() if op!='close']
    assert max(p['x'] for p in pts)-min(p['x'] for p in pts)==pytest.approx(40)
    assert max(p['y'] for p in pts)-min(p['y'] for p in pts)==pytest.approx(80)


def test_shear_filled_path_supported_stroked_path_diagnosed():
    shape=parse('<path d="M0 0L10 10L0 10Z" transform="matrix(1 0 1 1 0 0)"/>')[0]
    assert shape['commands'][1]['lineTo']=={'x':20,'y':10}
    with pytest.raises(SvgError,match='stroke'):
        parse('<path d="M0 0L10 10" stroke="red" transform="matrix(1 0 1 1 0 0)"/>')


def test_line_endpoints_and_direction_in_slide_xml(tmp_path):
    # AC-K02: positive-slope and negative-slope/reversed lines keep SVG endpoint
    # order and direction in the actual custGeom path, not just an equal bbox.
    root = compile_slide(tmp_path, '''
      <line id="down" x1="10" y1="15" x2="150" y2="85" stroke="#000000"/>
      <line id="up" x1="180" y1="10" x2="20" y2="90" stroke="#000000"/>
    ''')
    for shape_id, (x1, y1), (x2, y2) in (('down', (10, 15), (150, 85)), ('up', (180, 10), (20, 90))):
        sp = slide_shape(root, shape_id)
        min_x, min_y = min(x1, x2), min(y1, y2)
        _, points = path_points(sp)
        assert points[0] == ('moveTo', round((x1 - min_x) * 9525), round((y1 - min_y) * 9525))
        assert points[1] == ('lnTo', round((x2 - min_x) * 9525), round((y2 - min_y) * 9525))
        assert len(points) == 2


def test_rotated_circle_bounds_unchanged_in_slide_xml(tmp_path):
    # AC-K03: an r=10 circle rotated 45 degrees about its centre stays a 20x20
    # ellipse shape in the real PPT, positioned at the rotated centre.
    root = compile_slide(tmp_path, '<circle id="c" cx="60" cy="40" r="10" transform="rotate(45 60 40)"/>')
    sp = slide_shape(root, 'c')
    geom = sp.find('p:spPr/a:prstGeom', NS)
    assert geom is not None and geom.get('prst') == 'ellipse'
    ext = sp.find('p:spPr/a:xfrm/a:ext', NS)
    assert int(ext.get('cx')) == 20 * 9525
    assert int(ext.get('cy')) == 20 * 9525
    off = sp.find('p:spPr/a:xfrm/a:off', NS)
    assert int(off.get('x')) == 50 * 9525
    assert int(off.get('y')) == 30 * 9525


def test_rotated_ellipse_uses_analytic_extrema_in_slide_xml(tmp_path):
    # AC-K03: a rotated non-uniform ellipse becomes custGeom whose real bounds
    # equal the analytic extrema 2*sqrt((rx*cos)^2+(ry*sin)^2) etc.
    root = compile_slide(tmp_path, '<ellipse id="e" cx="100" cy="50" rx="30" ry="10" transform="rotate(30 100 50)"/>')
    sp = slide_shape(root, 'e')
    theta = math.radians(30)
    expected_w = 2 * math.sqrt((30 * math.cos(theta)) ** 2 + (10 * math.sin(theta)) ** 2)
    expected_h = 2 * math.sqrt((30 * math.sin(theta)) ** 2 + (10 * math.cos(theta)) ** 2)
    path, _ = path_points(sp)
    assert abs(int(path.get('w')) - expected_w * 9525) <= 2
    assert abs(int(path.get('h')) - expected_h * 9525) <= 2
    ext = sp.find('p:spPr/a:xfrm/a:ext', NS)
    assert abs(int(ext.get('cx')) - expected_w * 9525) <= 2
    assert abs(int(ext.get('cy')) - expected_h * 9525) <= 2


def test_uniformly_scaled_rounded_rect_and_icon_stroke_in_slide_xml(tmp_path):
    # AC-K07: rx becomes a path in the SVG layer; uniform scale doubles both the
    # geometry and the stroke width in the real PPT, and a symbol's inner stroked
    # path keeps its stroke (no icon-stroke regression to a bare shape).
    root = compile_slide(tmp_path, '''
      <defs><symbol id="ic" viewBox="0 0 10 10">
        <rect id="ic-bg" width="10" height="10" fill="#00ff00"/>
        <path id="ic-stroke" d="M1 1 L9 9" fill="none" stroke="#0000ff" stroke-width="1"/>
      </symbol></defs>
      <rect id="round2" x="10" y="10" width="40" height="20" rx="5" transform="scale(2)"
            fill="#ff0000" stroke="#000000" stroke-width="2"/>
      <use href="#ic" x="100" y="10" width="20" height="20"/>
    ''')
    rounded = slide_shape(root, 'round2')
    path, _ = path_points(rounded)
    assert int(path.get('w')) == 80 * 9525
    assert int(path.get('h')) == 40 * 9525
    off = rounded.find('p:spPr/a:xfrm/a:off', NS)
    assert int(off.get('x')) == 20 * 9525 and int(off.get('y')) == 20 * 9525
    fill = rounded.find('p:spPr/a:solidFill/a:srgbClr', NS)
    assert fill.get('val') == 'FF0000'
    line = rounded.find('p:spPr/a:ln', NS)
    assert int(line.get('w')) == 4 * 9525
    stroke = line.find('a:solidFill/a:srgbClr', NS)
    assert stroke.get('val') == '000000'
    # Icon keeps its own stroke through symbol scaling (k=2 doubles the width).
    icon = slide_shape(root, 'ic-stroke')
    path_points(icon)
    icon_line = icon.find('p:spPr/a:ln', NS)
    assert int(icon_line.get('w')) == 2 * 9525
    icon_stroke = icon_line.find('a:solidFill/a:srgbClr', NS)
    assert icon_stroke.get('val') == '0000FF'
    assert icon.find('p:spPr/a:noFill', NS) is not None


def test_nonuniform_filled_rounded_rect_scales_in_slide_xml(tmp_path):
    # AC-K07 support boundary: non-uniform scale of a filled (unstroked) rounded
    # rect is kept as exact transformed path geometry in the real PPT.
    root = compile_slide(tmp_path,
                         '<rect id="nu" x="10" y="10" width="40" height="20" rx="5" '
                         'transform="scale(2 1)" fill="#ff0000"/>')
    sp = slide_shape(root, 'nu')
    path, _ = path_points(sp)
    assert int(path.get('w')) == 80 * 9525
    assert int(path.get('h')) == 20 * 9525
    off = sp.find('p:spPr/a:xfrm/a:off', NS)
    assert int(off.get('x')) == 20 * 9525 and int(off.get('y')) == 10 * 9525


def test_nonuniform_stroked_shape_rejected_with_diagnostic(tmp_path):
    # AC-K07 support boundary: a non-uniformly scaled *stroked* shape is an
    # explicit, located SvgError at compile time (no silent approximation).
    from deck_master.compiler import compile_deck, CompileOptions, SvgInput
    svg = tmp_path / 'bad.svg'
    svg.write_text('<svg viewBox="0 0 100 50"><rect width="40" height="20" stroke="#000000" '
                   'stroke-width="2" transform="scale(2 1)"/></svg>')
    with pytest.raises(SvgError, match='nonuniform'):
        compile_deck([SvgInput('geometry', svg)], CompileOptions(width_px=100, height_px=50),
                     tmp_path / 'bad-out')
