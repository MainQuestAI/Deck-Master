import math
import pytest
from deck_master.compiler.svg import parse_svg, SvgError


def parse(body):
    return parse_svg(f'<svg viewBox="0 0 200 200">{body}</svg>'.encode(), page_id='geometry')['shapes']


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
