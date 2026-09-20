"""T10 readback evidence: actual slide XML is checked against the input SVG
plus independent Page v2 relations (AC-K08), and readability blockers are
located (AC-K10)."""
import zipfile
import xml.etree.ElementTree as ET

import pytest

from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.compiler.svg import parse_svg
from deck_master.pipeline import readback

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}

DIAGRAM_SVG = '''
  <rect id="node-a" x="10" y="10" width="40" height="30" data-node-ref="n1"/>
  <rect id="node-b" x="120" y="10" width="40" height="30" data-node-ref="n2"/>
  <line id="link" x1="{x1}" y1="25" x2="{x2}" y2="25" stroke="#000000" data-edge-ref="e1"/>
'''


def expected_page(edges=(), nodes=(), title=None):
    visible = {} if title is None else {'title': title}
    return {
        'page_id': 'p1',
        'customer_visible': visible,
        'visual_spec': {
            'intent': 'relation check',
            'reference_mode': 'new_design',
            'nodes': [{'node_id': node} for node in nodes],
            'edges': list(edges),
        },
    }


def resolve_font():
    import shutil
    import subprocess
    if not shutil.which('fc-match'):
        pytest.fail('fc-match unavailable; cannot resolve a real font file')
    output = subprocess.run(['fc-match', '-f', '%{family}\n%{file}', 'Hiragino Sans GB'],
                            capture_output=True, text=True, check=True).stdout.splitlines()
    if len(output) < 2 or 'Hiragino Sans GB' not in output[0]:
        pytest.fail(f'fc-match did not resolve Hiragino Sans GB: {output!r}')
    return {'Hiragino Sans GB': output[1]}


def compile_and_readback(tmp_path, body, page, name='rb'):
    svg = tmp_path / f'{name}.svg'
    svg.write_text(f'<svg viewBox="0 0 200 100">{body}</svg>')
    result = compile_deck([SvgInput('p1', svg)], CompileOptions(width_px=200, height_px=100,
                          fonts=resolve_font() if 'text' in body else {}),
                          tmp_path / f'{name}-out')
    parsed = parse_svg(svg.read_bytes(), page_id='p1')
    return readback(result.pptx_path, [parsed], [page])


def forward_edge():
    return {'edge_id': 'e1', 'from': 'n1', 'to': 'n2', 'direction': 'forward',
            'relationship': 'feeds'}


def test_edges_and_nodes_verified_against_svg_geometry(tmp_path):
    # AC-K08 positive: declared nodes exist in the actual PPT and the edge
    # shape starts at the from-node and ends at the to-node.
    page = expected_page(nodes=('n1', 'n2'), edges=[forward_edge()])
    report = compile_and_readback(tmp_path, DIAGRAM_SVG.format(x1=30, x2=140), page)
    assert report['status'] == 'pass'
    assert report['findings'] == []


def test_reversed_arrow_is_located(tmp_path):
    # AC-K08 counter-case: the same edge drawn from the to-node to the from-node
    # is a located reversed_arrow finding, not a bbox-equivalent pass.
    page = expected_page(nodes=('n1', 'n2'), edges=[forward_edge()])
    report = compile_and_readback(tmp_path, DIAGRAM_SVG.format(x1=140, x2=30), page)
    finding = next(f for f in report['findings'] if f['code'] == 'reversed_arrow')
    assert finding['page_id'] == 'p1'
    assert finding['edge_id'] == 'e1'
    assert finding['from'] == 'n1' and finding['to'] == 'n2'
    assert finding['element'] == 'link'


def test_undirected_edge_skips_direction_but_checks_existence(tmp_path):
    page = expected_page(nodes=('n1', 'n2'),
                         edges=[{'edge_id': 'e1', 'from': 'n1', 'to': 'n2',
                                 'direction': 'undirected', 'relationship': 'related'}])
    report = compile_and_readback(tmp_path, DIAGRAM_SVG.format(x1=140, x2=30), page)
    assert report['status'] == 'pass'


def test_missing_node_and_missing_edge_are_located(tmp_path):
    # AC-K08: a declared node without any bound shape, and a declared edge
    # without any data-edge-ref binding, both produce located findings.
    page = expected_page(nodes=('n1', 'n2'), edges=[forward_edge()])
    body = DIAGRAM_SVG.format(x1=30, x2=140).replace('<rect id="node-b" x="120" y="10" width="40" height="30" data-node-ref="n2"/>', '')
    body = body.replace(' data-edge-ref="e1"', '')
    report = compile_and_readback(tmp_path, body, page, name='missing')
    codes = {f['code'] for f in report['findings']}
    assert 'missing_node' in codes and 'missing_edge' in codes
    node_finding = next(f for f in report['findings'] if f['code'] == 'missing_node')
    assert node_finding['node_id'] == 'n2'
    edge_finding = next(f for f in report['findings'] if f['code'] == 'missing_edge')
    assert edge_finding['edge_id'] == 'e1' and edge_finding['page_id'] == 'p1'


def test_full_text_hidden_or_tiny_layers_are_located(tmp_path):
    # AC-K10: a full-text layer that is entirely transparent or entirely under
    # 6pt cannot pass content coverage.
    transparent = ('<text id="ghost" x="5" y="20" font-family="Hiragino Sans GB" font-size="18" fill="#000000" fill-opacity="0">'
                   '看不见的结论</text>')
    tiny = '<text id="micro" x="5" y="20" font-family="Hiragino Sans GB" font-size="4">看不见的结论</text>'
    for name, body in (('transparent', transparent), ('tiny', tiny)):
        page = expected_page()
        report = compile_and_readback(tmp_path, body, page, name=name)
        finding = next(f for f in report['findings'] if f['code'] == 'hidden_or_tiny_text')
        assert finding['page_id'] == 'p1'


def test_local_decorative_small_run_does_not_fail_page(tmp_path):
    # AC-K10 local exception: one small footnote among normal text is not a
    # coverage blocker and the page still passes.
    body = ('<text id="main" x="5" y="30" font-family="Hiragino Sans GB" font-size="18">正常正文结论</text>'
            '<text id="note" x="5" y="60" font-family="Hiragino Sans GB" font-size="5"> decorative footnote </text>')
    report = compile_and_readback(tmp_path, body, expected_page(), name='decorative')
    assert report['status'] == 'pass'
    assert report['findings'] == []


def test_shape_outside_slide_bounds_is_located(tmp_path):
    # AC-K10: a real overflow (text/shape box leaving the slide) is located by
    # shape name through the geometric xfrm check.
    body = '<rect id="panel" x="150" y="10" width="100" height="40" fill="#ff0000"/>'
    report = compile_and_readback(tmp_path, body, expected_page(), name='overflow')
    finding = next(f for f in report['findings'] if f['code'] == 'shape_outside_slide')
    assert finding['page_id'] == 'p1'
    assert finding['element'] == 'panel'
    assert finding['slide'] == [200 * 9525, 100 * 9525]
