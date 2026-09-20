"""T08 whole-card tests: full positive coverage of the declared SVG subset
(spec 06.2) plus parameterized unsupported/unsafe rejection cases.

Tests call only the pure parsing layer (parse_svg / SvgError); rendering and
PPT output are T09/T10 territory.
"""
import math

import pytest
from PIL import Image

from deck_master.compiler.svg import parse_svg, SvgError


def parse(body, page_id='p1', **kwargs):
    data = body if isinstance(body, bytes) else f'<svg viewBox="0 0 200 100">{body}</svg>'.encode()
    return parse_svg(data, page_id=page_id, **kwargs)['shapes']


def by_id(shapes, shape_id):
    return next(shape for shape in shapes if shape['id'] == shape_id)


def test_svg_to_ir(tmp_path):
    png_path = tmp_path / 'approved.png'
    Image.new('RGB', (8, 6), (10, 120, 200)).save(png_path)
    svg = f'''<svg viewBox="0 0 400 300">
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#ff0000" stop-opacity="0"/>
          <stop offset="1" stop-color="#0000ff"/>
        </linearGradient>
        <radialGradient id="rg">
          <stop offset="0" stop-color="#ffffff"/>
          <stop offset="1" stop-color="#000000" stop-opacity="0.5"/>
        </radialGradient>
        <symbol id="icon" viewBox="0 0 20 20">
          <rect id="icon-body" x="2" y="2" width="16" height="16"/>
          <line id="icon-mark" x1="2" y1="2" x2="18" y2="18" stroke="#000000"/>
        </symbol>
        <g id="badge">
          <circle id="badge-disc" cx="8" cy="8" r="8"/>
          <polygon id="badge-tri" points="8,0 16,16 0,16"/>
        </g>
      </defs>
      <rect id="bg" x="0" y="0" width="400" height="300" fill="url(#lg)"/>
      <circle id="sun" cx="320" cy="60" r="40" fill="url(#rg)"/>
      <ellipse id="orbit" cx="100" cy="80" rx="60" ry="30" fill="none" stroke="#00ff00" stroke-width="2"/>
      <line id="axis" x1="10" y1="290" x2="390" y2="290" stroke="#333333"/>
      <polyline id="trend" points="0,250 50,200 100,230" fill="none" stroke="#ff6600"/>
      <g id="nested" transform="translate(40 20)">
        <g transform="scale(1.5)">
          <rect id="scaled" x="10" y="10" width="20" height="10" transform="rotate(90 20 15)"/>
        </g>
      </g>
      <g id="matx" transform="matrix(1 0 0 1 7 8)">
        <rect id="moved" x="1" y="2" width="3" height="4"/>
      </g>
      <text id="title" x="200" y="40" font-family="Noto Sans SC, sans-serif" font-size="28"
            font-weight="bold" text-anchor="middle" letter-spacing="2" data-atom-id="atom-title">
        <tspan x="200" y="40">季度增长报告</tspan>
        <tspan x="200" dy="36">第二行副标题</tspan>
      </text>
      <use id="icon-use" href="#icon" x="300" y="180" width="60" height="60"/>
      <use id="badge-use" href="#badge" x="20" y="20"/>
      <image id="photo" href="approved.png" x="20" y="150" width="80" height="80"/>
      <image id="photo-slice" href="approved.png" x="120" y="150" width="80" height="80" preserveAspectRatio="xMidYMid slice"/>
      <image id="photo-stretch" href="approved.png" x="220" y="150" width="80" height="80" preserveAspectRatio="none"/>
      <path id="all-commands" d="M 5 5 h 30 v 10 s 5 5 10 0 t 5 -5 q 2 -2 4 0 a 6 6 0 0 1 6 6 z"
            fill="none" stroke="#000000" data-atom-id="atom-path" data-pptx-bounds="5,5,61,21"/>
      <rect id="ignored-data" x="1" y="1" width="2" height="2" data-pptx-bounds="0,0,2,2" data-random="ok"/>
    </svg>'''
    page = parse_svg(svg.encode(), page_id='deck', assets={'approved.png': str(png_path)})
    assert page['page_id'] == 'deck'
    assert page['width'] == 400 and page['height'] == 300
    shapes = page['shapes']

    # Linear gradient with zero stop-opacity at offset 0 and full stop at 1.
    bg = by_id(shapes, 'bg')
    assert bg['fill'] == {'kind': 'linear', 'angle': 90.0, 'stops': [
        {'offset': 0.0, 'color': '#ff0000', 'opacity': 0.0},
        {'offset': 1.0, 'color': '#0000ff', 'opacity': 1.0},
    ]}
    # Radial gradient keeps stop-opacity.
    sun = by_id(shapes, 'sun')
    assert sun['fill']['kind'] == 'radial'
    assert sun['fill']['stops'][1] == {'offset': 1.0, 'color': '#000000', 'opacity': 0.5}
    assert (sun['x'], sun['y'], sun['width'], sun['height']) == (280.0, 20.0, 80.0, 80.0)
    # Untransformed ellipse keeps analytic bounds and stroke paint.
    orbit = by_id(shapes, 'orbit')
    assert orbit['kind'] == 'ellipse'
    assert (orbit['x'], orbit['y'], orbit['width'], orbit['height']) == (40.0, 50.0, 120.0, 60.0)
    assert orbit['stroke'] == '#00ff00' and orbit['stroke_width'] == 2 and orbit['fill'] == 'none'
    # Line endpoints and direction survive untouched.
    axis = by_id(shapes, 'axis')
    assert axis['kind'] == 'line' and axis['points'] == [[10.0, 290.0], [390.0, 290.0]]
    # Polyline stays distinct from polygon.
    trend = by_id(shapes, 'trend')
    assert trend['kind'] == 'polyline'
    assert trend['points'] == [[0.0, 250.0], [50.0, 200.0], [100.0, 230.0]]
    # Nested translate > scale > rotate(cx cy): analytic polygon, scaled stroke.
    scaled = by_id(shapes, 'scaled')
    assert scaled['kind'] == 'polygon'
    xs, ys = zip(*scaled['points'])
    assert min(xs) == pytest.approx(62.5) and max(xs) == pytest.approx(77.5)
    assert min(ys) == pytest.approx(27.5) and max(ys) == pytest.approx(57.5)
    assert scaled['stroke_width'] == pytest.approx(1.5)
    # matrix() translate composition.
    moved = by_id(shapes, 'moved')
    assert (moved['x'], moved['y'], moved['width'], moved['height']) == (8.0, 10.0, 3.0, 4.0)
    # Chinese multiline text: per-run baseline, letter-spacing, anchor, bold, atom binding.
    first, second = by_id(shapes, 'title:0'), by_id(shapes, 'title:1')
    assert first['text'] == '季度增长报告' and second['text'] == '第二行副标题'
    assert (first['x'], first['y']) == (200.0, 40.0)
    assert (second['x'], second['y']) == (200.0, 76.0)
    assert first['font_size'] == 28 and first['font_family'] == 'Noto Sans SC'
    assert first['bold'] is True and first['anchor'] == 'middle' and first['letter_spacing'] == 2
    assert first['atom_id'] == 'atom-title'
    # symbol/use with viewBox scaling: k=3, centered, stable inner ids.
    body = by_id(shapes, 'icon-body')
    assert (body['x'], body['y'], body['width'], body['height']) == (306.0, 186.0, 48.0, 48.0)
    mark = by_id(shapes, 'icon-mark')
    assert mark['points'] == [[306.0, 186.0], [354.0, 234.0]]
    # use of a plain group keeps both member shapes with the use offset.
    disc = by_id(shapes, 'badge-disc')
    assert (disc['x'], disc['y'], disc['width'], disc['height']) == (20.0, 20.0, 16.0, 16.0)
    tri = by_id(shapes, 'badge-tri')
    assert tri['points'] == [[28.0, 20.0], [36.0, 36.0], [20.0, 36.0]]
    # Approved PNG images map all three preserveAspectRatio fits.
    photo = by_id(shapes, 'photo')
    assert photo['kind'] == 'image' and photo['asset_path'] == str(png_path)
    assert (photo['x'], photo['y'], photo['width'], photo['height']) == (20.0, 150.0, 80.0, 80.0)
    assert photo['fit'] == 'contain'
    assert by_id(shapes, 'photo-slice')['fit'] == 'cover'
    assert by_id(shapes, 'photo-stretch')['fit'] == 'stretch'
    # Full path command vocabulary, flattened, atom id bound, unrelated data-* tolerated.
    path = by_id(shapes, 'all-commands')
    assert path['atom_id'] == 'atom-path'
    assert path['commands'][0] == {'moveTo': {'x': 5.0, 'y': 5.0}}
    assert {'lineTo': {'x': 35.0, 'y': 5.0}} in path['commands']
    assert {'lineTo': {'x': 35.0, 'y': 15.0}} in path['commands']
    assert path['commands'][-1] == {'close': {}}
    # Unrelated data-* attributes do not break parsing.
    assert by_id(shapes, 'ignored-data')['width'] == 2.0


UNSUPPORTED_CASES = [
    ('script element', '<script/>', 'unsupported script'),
    ('foreignObject element', '<foreignObject/>', 'unsupported foreignObject'),
    ('onload handler', '<rect width="5" height="5" onload="x()"/>', 'unsupported onload'),
    ('onclick handler', '<rect width="5" height="5" onclick="x()"/>', 'unsupported onclick'),
    ('javascript use href', '<use href="javascript:alert(1)"/>', 'local use'),
    ('external use href', '<use href="http://example.org/icon.svg#x"/>', 'local use'),
    ('unapproved image', '<image href="evil.png" width="4" height="4"/>', 'approved asset'),
    ('doctype', b'<!DOCTYPE svg><svg viewBox="0 0 10 10"/>', 'DOCTYPE'),
    ('entity expansion',
     b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
     b'<svg viewBox="0 0 10 10"><text>&xxe;</text></svg>', 'DOCTYPE'),
    ('filter attribute', '<rect width="5" height="5" filter="blur(2)"/>', 'unsupported filter'),
    ('mask attribute', '<rect width="5" height="5" mask="url(#m)"/>', 'unsupported mask'),
    ('clip-path attribute', '<rect width="5" height="5" clip-path="url(#c)"/>', 'unsupported clip-path'),
    ('filter element', '<filter/>', 'unsupported filter'),
    ('animate element', '<animate attributeName="x"/>', 'unsupported animate'),
    ('video element', '<video/>', 'unsupported video'),
    ('unknown attribute', '<rect width="5" height="5" foo="1"/>', 'unsupported attribute foo'),
    ('style outside whitelist', '<rect width="5" height="5" style="display:none"/>', 'unsupported style property'),
    ('nested tspan', '<text><tspan><tspan>x</tspan></tspan></text>', 'nested tspan'),
    ('orphan tspan', '<tspan>x</tspan>', 'orphan tspan'),
    ('unresolved local use', '<use href="#missing"/>', 'local use'),
    ('cyclic local use', '<g id="loop"><use href="#loop"/></g>', 'local use'),
    ('paint reference not a gradient',
     '<rect id="plain" width="5" height="5"/><rect width="5" height="5" fill="url(#plain)"/>',
     'not a gradient'),
    ('gradientTransform',
     '<defs><linearGradient id="g" gradientTransform="rotate(45)">'
     '<stop offset="0" stop-color="#f00"/><stop offset="1" stop-color="#00f"/></linearGradient></defs>'
     '<rect width="5" height="5" fill="url(#g)"/>', 'gradientTransform'),
    ('userSpaceOnUse units',
     '<defs><linearGradient id="g" gradientUnits="userSpaceOnUse">'
     '<stop offset="0" stop-color="#f00"/><stop offset="1" stop-color="#00f"/></linearGradient></defs>'
     '<rect width="5" height="5" fill="url(#g)"/>', 'objectBoundingBox'),
    ('repeating spread',
     '<defs><linearGradient id="g" spreadMethod="reflect">'
     '<stop offset="0" stop-color="#f00"/><stop offset="1" stop-color="#00f"/></linearGradient></defs>'
     '<rect width="5" height="5" fill="url(#g)"/>', 'spread'),
    ('single stop gradient',
     '<defs><linearGradient id="g"><stop offset="0" stop-color="#f00"/></linearGradient></defs>'
     '<rect width="5" height="5" fill="url(#g)"/>', 'at least two stops'),
    ('arc flag out of range', '<path d="M0 0 A 5 5 0 2 1 10 10"/>', 'arc flags'),
    ('arc flag non-integer', '<path d="M0 0 A 5 5 0 0.5 1 10 10"/>', 'arc flags'),
    ('missing viewBox', b'<svg><rect width="5" height="5"/></svg>', 'viewBox'),
    ('negative viewBox', b'<svg viewBox="0 0 -10 10"><rect width="5" height="5"/></svg>', 'viewBox'),
    ('nonzero viewBox origin', b'<svg viewBox="5 5 10 10"><rect width="5" height="5"/></svg>', 'viewBox'),
    ('non-finite geometry', '<rect width="1e999" height="5"/>', 'unitless'),
    ('non-finite text position', '<text x="0" y="nan">a</text>', 'unitless'),
    ('opacity out of range', '<rect width="5" height="5" opacity="1.5"/>', 'invalid opacity'),
    ('transformed gradient',
     '<defs><linearGradient id="g"><stop offset="0" stop-color="#f00"/>'
     '<stop offset="1" stop-color="#00f"/></linearGradient></defs>'
     '<g transform="scale(2)"><rect width="5" height="5" fill="url(#g)"/></g>',
     'transformed gradient'),
    ('nonuniform text scaling',
     '<g transform="scale(2 1)"><text x="1" y="2">a</text></g>', 'nonuniform text scaling'),
]


@pytest.mark.parametrize('name,body,match', UNSUPPORTED_CASES, ids=[c[0] for c in UNSUPPORTED_CASES])
def test_unsupported_and_unsafe(name, body, match):
    data = body if isinstance(body, bytes) else f'<svg viewBox="0 0 100 100">{body}</svg>'.encode()
    with pytest.raises(SvgError, match=match) as excinfo:
        parse_svg(data, page_id='p1')
    message = str(excinfo.value)
    assert 'p1' in message
    diagnostic = excinfo.value.diagnostic
    assert diagnostic['code'] == 'unsupported_or_invalid_svg'
    assert 'p1' in diagnostic['location']
    assert diagnostic['recovery']


def test_rotated_circle_bbox_is_invariant():
    circle = parse('<circle cx="60" cy="40" r="10" transform="rotate(30 60 40)"/>')[0]
    assert circle['kind'] == 'circle'
    assert (circle['x'], circle['y']) == (50.0, 30.0)
    assert circle['width'] == pytest.approx(20)
    assert circle['height'] == pytest.approx(20)


def test_rotated_ellipse_bbox_matches_analytic_extrema():
    shape = parse('<ellipse cx="100" cy="50" rx="30" ry="10" transform="rotate(30 100 50)"/>')[0]
    theta = math.radians(30)
    expected_w = 2 * math.sqrt((30 * math.cos(theta)) ** 2 + (10 * math.sin(theta)) ** 2)
    expected_h = 2 * math.sqrt((30 * math.sin(theta)) ** 2 + (10 * math.cos(theta)) ** 2)
    xs, ys = zip(*shape['points'])
    assert max(xs) - min(xs) == pytest.approx(expected_w, abs=1e-6)
    assert max(ys) - min(ys) == pytest.approx(expected_h, abs=1e-6)


def test_negative_slope_line_endpoints_and_direction():
    line = parse('<line x1="180" y1="15" x2="20" y2="85" stroke="#000000"/>')[0]
    assert line['kind'] == 'line'
    assert line['points'] == [[180.0, 15.0], [20.0, 85.0]]
    moved = parse('<g transform="translate(5 5)"><line x1="180" y1="15" x2="20" y2="85" stroke="#000000"/></g>')[0]
    assert moved['points'] == [[185.0, 20.0], [25.0, 90.0]]


def test_zero_opacity_values_are_preserved():
    rect, line = parse(
        '<g opacity="0.5">'
        '<rect width="10" height="10" opacity="0.8" fill-opacity="0" stroke="#000000" stroke-opacity="0"/>'
        '<line x1="0" y1="0" x2="1" y2="1" stroke="#000000" stroke-width="0"/>'
        '</g>')
    assert rect['opacity'] == 0.4
    assert rect['fill_opacity'] == 0
    assert rect['stroke_opacity'] == 0
    assert line['stroke_width'] == 0
    invisible = parse('<g opacity="0"><rect width="4" height="4"/></g>')[0]
    assert invisible['opacity'] == 0


def test_arc_reaches_target_exactly_under_uniform_rotation():
    shape = parse('<path d="M 20 10 A 30 30 0 0 1 80 70" fill="none" stroke="#000000" stroke-width="3" '
                  'transform="rotate(15)"/>')[0]
    assert shape['stroke_width'] == 3
    theta = math.radians(15)

    def rotate(x, y):
        return (x * math.cos(theta) - y * math.sin(theta), x * math.sin(theta) + y * math.cos(theta))

    first = shape['commands'][0]['moveTo']
    last = shape['commands'][-1]['lineTo']
    assert (first['x'], first['y']) == pytest.approx(rotate(20, 10))
    assert (last['x'], last['y']) == pytest.approx(rotate(80, 70))


def test_text_typography_fields_and_rotation():
    run = parse('<g transform="rotate(90 0 0)"><text x="10" y="20" font-family="Source Han Sans SC, sans-serif" '
                'font-size="16" font-weight="800" text-anchor="end" letter-spacing="1.5">标题</text></g>')[0]
    assert run['text'] == '标题'
    assert run['bold'] is True
    assert run['anchor'] == 'end'
    assert run['letter_spacing'] == 1.5
    assert run['font_family'] == 'Source Han Sans SC'
    assert run['font_size'] == 16
    assert run['rotation'] == pytest.approx(90)
    assert (run['x'], run['y']) == pytest.approx((-20.0, 10.0))
