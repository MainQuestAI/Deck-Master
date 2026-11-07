"""D09 source controls: assert delivered DrawingML geometry and table properties."""
from pathlib import Path
import math
import zipfile
import xml.etree.ElementTree as ET

import pytest

from deck_tools.compiler import CompileOptions, SvgInput, compile_deck
from deck_tools.sanitize import pptx
from hostenv import host_fonts, resolve_host_font

FIXTURES = Path(__file__).parent / 'fixtures' / 'd09'
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def compile_control(tmp_path, name, *, scale=1, source=None):
    if source is None:
        source = ET.parse(FIXTURES / f'{name}.svg').getroot()
    # Keep fixed geometry/content while using a font actually present on the host.
    source.set('font-family', resolve_host_font())
    svg = tmp_path / f'{name}.svg'
    svg.write_bytes(ET.tostring(source))
    compiled = compile_deck([SvgInput(name, svg)],
                            CompileOptions(width_px=1280 * scale, height_px=720 * scale,
                                           fonts=host_fonts()), tmp_path / 'compiled')
    delivered = tmp_path / 'delivered.pptx'
    delivered.write_bytes(pptx(compiled.pptx_path.read_bytes(), 'deck.pptx'))
    with zipfile.ZipFile(delivered) as archive:
        return ET.fromstring(archive.read('ppt/slides/slide1.xml'))


def path_vertices(root):
    shape, = [s for s in root.findall('.//p:sp', NS)
              if s.find('p:spPr/a:custGeom', NS) is not None]
    transform = shape.find('p:spPr/a:xfrm', NS)
    off = transform.find('a:off', NS)
    ext = transform.find('a:ext', NS)
    path = shape.find('p:spPr/a:custGeom/a:pathLst/a:path', NS)
    return [((int(off.get('x')) + int(p.get('x')) * int(ext.get('cx')) / int(path.get('w'))) / 9525,
             (int(off.get('y')) + int(p.get('y')) * int(ext.get('cy')) / int(path.get('h'))) / 9525)
            for p in path.findall('./*/a:pt', NS)]


def cubic_samples(controls):
    return [tuple((1 - t) ** 3 * controls[0][axis]
                  + 3 * (1 - t) ** 2 * t * controls[1][axis]
                  + 3 * (1 - t) * t ** 2 * controls[2][axis]
                  + t ** 3 * controls[3][axis] for axis in (0, 1))
            for t in (i / 1000 for i in range(1001))]


def distance_to_polyline(point, vertices):
    distances = []
    for a, b in zip(vertices, vertices[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        along = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length if length else 0
        if 0 < along < length:
            distances.append(abs((point[0] - a[0]) * dy - (point[1] - a[1]) * dx) / length)
        else:
            distances.append(min(math.dist(point, a), math.dist(point, b)))
    return min(distances)


@pytest.mark.parametrize('name,controls', [
    ('curve-backtrack', [(200, 300), (1100, 300), (1100, 300), (400, 300)]),
    ('curve-normal', [(200, 400), (400, 100), (700, 600), (900, 300)]),
])
def test_curve_final_vertices_retain_sampled_range(tmp_path, name, controls):
    root = compile_control(tmp_path, name)
    vertices = path_vertices(root)
    samples = cubic_samples(controls)
    assert vertices[0] == pytest.approx(controls[0], abs=.0002)
    assert vertices[-1] == pytest.approx(controls[-1], abs=.0002)
    for axis in (0, 1):
        assert min(p[axis] for p in vertices) == pytest.approx(min(p[axis] for p in samples), abs=.2)
        assert max(p[axis] for p in vertices) == pytest.approx(max(p[axis] for p in samples), abs=.2)
    assert max(distance_to_polyline(p, vertices) for p in samples) <= .2
    assert len(vertices) > 2
    assert root.find('.//a:blip', NS) is None


@pytest.mark.parametrize('name', ['drawn-grid', 'native-grid'])
@pytest.mark.parametrize('scale', [1, .5])
def test_grid_letter_spacing_survives_delivery_once(tmp_path, name, scale):
    root = compile_control(tmp_path, name, scale=scale)
    tables = root.findall('.//a:tbl', NS)
    assert len(tables) == (1 if name == 'native-grid' else 0)
    runs = [r for r in root.findall('.//a:r', NS) if r.find('a:t', NS).text == 'ABCD']
    run, = runs
    assert run.find('a:rPr', NS).get('spc') == str(round(150 * scale))
    assert [e.get('spc') for e in root.iter() if e.get('spc') is not None] == [str(round(150 * scale))]
    assert [e.text for e in root.findall('.//a:t', NS)] == ['ABCD', '规则']
    if tables:
        assert tables[0].find('a:tr/a:tc/a:txBody/a:p/a:r', NS) is not None
        assert root.findall('.//p:sp/p:txBody', NS) == []


def border_style(cell, side):
    line = cell.find('a:tcPr/a:ln' + side, NS)
    color = line.find('a:solidFill/a:srgbClr', NS)
    return (int(line.get('w')), color.get('val'),
            int(color.find('a:alpha', NS).get('val')))


def assert_grid_borders(root, rows, cols, frame, horizontal, vertical):
    table, = root.findall('.//a:tbl', NS)
    cells = [row.findall('a:tc', NS) for row in table.findall('a:tr', NS)]
    assert len(cells) == rows
    assert all(len(row) == cols for row in cells)
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            # No independent perimeter lines in these controls: only those
            # edges fall back to the frame, including its stroke opacity.
            assert border_style(cell, 'L') == (frame if c == 0 else vertical[c - 1])
            assert border_style(cell, 'R') == (frame if c == cols - 1 else vertical[c])
            assert border_style(cell, 'T') == (frame if r == 0 else horizontal[r - 1])
            assert border_style(cell, 'B') == (frame if r == rows - 1 else horizontal[r])
            if c:
                assert border_style(cell, 'L') == border_style(row[c - 1], 'R')
            if r:
                assert border_style(cell, 'T') == border_style(cells[r - 1][c], 'B')
    return cells


@pytest.mark.parametrize('source_opacity', [None, .4, 0])
def test_native_grid_uses_each_source_edge_paint(tmp_path, source_opacity):
    source = ET.parse(FIXTURES / 'native-grid.svg').getroot()
    if source_opacity is not None:
        for element in source:
            stroke_opacity = {'frame': .5, 'horizontal': .75, 'vertical': .25}.get(element.get('id'))
            if stroke_opacity is not None:
                element.set('opacity', str(source_opacity))
                element.set('stroke-opacity', str(stroke_opacity))
    root = compile_control(tmp_path, 'native-grid', source=source)
    alphas = [50000, 100000, 100000] if source_opacity is None else [
        round(source_opacity * stroke_opacity * 100000) for stroke_opacity in (.5, .75, .25)]
    assert_grid_borders(root, 2, 2, (19050, '52758B', alphas[0]),
                        [(38100, 'FF0000', alphas[1])], [(9525, '0000FF', alphas[2])])


def test_independent_perimeter_rule_takes_precedence_over_frame(tmp_path):
    source = ET.parse(FIXTURES / 'native-grid.svg').getroot()
    ET.SubElement(source, '{http://www.w3.org/2000/svg}line', {
        'x1': '680', 'y1': '100', 'x2': '80', 'y2': '100',
        'stroke': '#00ff00', 'stroke-width': '3', 'opacity': '.5',
        'stroke-opacity': '.5', 'data-table-id': 'table'})
    root = compile_control(tmp_path, 'native-grid', source=source)
    cells = root.findall('.//a:tbl/a:tr/a:tc', NS)
    for cell in cells[:2]:
        assert border_style(cell, 'T') == (28575, '00FF00', 25000)
    # The bottom still has no independent rule and therefore uses the frame.
    for cell in cells[2:]:
        assert border_style(cell, 'B') == (19050, '52758B', 50000)


def test_matrix_keeps_differing_rules_and_number_spacing(tmp_path):
    root = compile_control(tmp_path, '03-matrix')
    cells = assert_grid_borders(root, 12, 5, (19050, '52758B', 50000),
                                [(28575, '16324F', 100000)] + [(9525, '9AABB9', 100000)] * 10,
                                [(9525, '9AABB9', 100000)] * 4)
    assert len(root.findall('.//a:tbl/a:tblGrid/a:gridCol', NS)) == 5
    for r, row in enumerate(cells):
        runs = row[0].findall('.//a:r', NS)
        run, = runs
        assert run.find('a:t', NS).text == ('编号' if r == 0 else f'R{r:02}')
        assert run.find('a:rPr', NS).get('spc') == '150'
    assert len([e for e in root.iter() if e.get('spc') is not None]) == 12
    assert len(root.findall('.//a:tbl//a:t', NS)) == 60
