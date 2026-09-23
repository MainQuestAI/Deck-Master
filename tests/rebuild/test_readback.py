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


from hostenv import host_fonts, resolve_host_font

FAMILY = resolve_host_font()


def resolve_font():
    return host_fonts()


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
    transparent = (f'<text id="ghost" x="5" y="20" font-family="{FAMILY}" font-size="18" fill="#000000" fill-opacity="0">'
                   '看不见的结论</text>')
    tiny = f'<text id="micro" x="5" y="20" font-family="{FAMILY}" font-size="4">看不见的结论</text>'
    for name, body in (('transparent', transparent), ('tiny', tiny)):
        page = expected_page()
        report = compile_and_readback(tmp_path, body, page, name=name)
        finding = next(f for f in report['findings'] if f['code'] == 'hidden_or_tiny_text')
        assert finding['page_id'] == 'p1'


def test_local_decorative_small_run_does_not_fail_page(tmp_path):
    # AC-K10 local exception: one small footnote among normal text is not a
    # coverage blocker and the page still passes.
    body = (f'<text id="main" x="5" y="30" font-family="{FAMILY}" font-size="18">正常正文结论</text>'
            f'<text id="note" x="5" y="60" font-family="{FAMILY}" font-size="5"> decorative footnote </text>')
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


# ---------------------------------------------------------------------------
# 轮 C / P1-05: per-atom readability and dual-endpoint edge verification.


def _atom_page(title_atoms):
    visible = {'title': title_atoms[0], 'body_blocks': [
        {'id': f'b{i}', 'type': 'paragraph', 'text': text} for i, text in enumerate(title_atoms[1:], 1)]}
    return {
        'page_id': 'p1',
        'customer_visible': visible,
        'visual_spec': {'intent': 'readability', 'reference_mode': 'new_design'},
    }


def test_unreadable_required_atoms_are_located_per_atom(tmp_path):
    # A readable 24pt title does not excuse required body atoms set to 1pt.
    body = ''.join(f'<text x="5" y="{48 + i * 10}" font-family="{FAMILY}" font-size="4">'
                   f'必要职责{i}</text>' for i in range(3))
    svg = (f'<svg viewBox="0 0 200 100">'
           f'<text x="5" y="30" font-family="{FAMILY}" font-size="24">标题</text>{body}</svg>')
    report = compile_and_readback(tmp_path, svg, _atom_page(['标题', '必要职责0', '必要职责1', '必要职责2']))
    finding = next(f for f in report['findings'] if f['code'] == 'unreadable_text')
    assert finding['page_id'] == 'p1'
    assert finding['atom_id'] in ('atom:p1:block:b1:text', 'atom:p1:block:b2:text', 'atom:p1:block:b3:text')
    assert "sz='300'" in finding['detail']
    unreadable_atoms = {f['atom_id'] for f in report['findings'] if f['code'] == 'unreadable_text'}
    assert unreadable_atoms == {'atom:p1:block:b1:text', 'atom:p1:block:b2:text', 'atom:p1:block:b3:text'}
    title_flagged = any(f.get('atom_id') == 'atom:p1:title' for f in report['findings']
                        if f['code'] == 'unreadable_text')
    assert not title_flagged, 'the readable 24pt title must not be flagged'


def test_mixed_sizes_with_readable_required_atoms_pass(tmp_path):
    body = ''.join(f'<text x="5" y="{48 + i * 12}" font-family="{FAMILY}" font-size="12">'
                   f'正常条目{i}</text>' for i in range(3))
    svg = (f'<svg viewBox="0 0 200 100">'
           f'<text x="5" y="30" font-family="{FAMILY}" font-size="24">标题</text>{body}</svg>')
    report = compile_and_readback(tmp_path, svg, _atom_page(['标题', '正常条目0', '正常条目1', '正常条目2']))
    assert report['status'] == 'pass'
    assert report['findings'] == []


def test_short_edge_not_reaching_target_is_located(tmp_path):
    # A stub starting near A but ending far short of B must not pass.
    svg = '''<svg viewBox="0 0 200 100">
      <rect id="node-a" x="10" y="10" width="40" height="30" data-node-ref="n1"/>
      <rect id="node-b" x="150" y="10" width="40" height="30" data-node-ref="n2"/>
      <line id="link" x1="30" y1="25" x2="60" y2="25" stroke="#000000" data-edge-ref="e1"/>
    </svg>'''
    page = expected_page(nodes=('n1', 'n2'), edges=[{
        'edge_id': 'e1', 'from': 'n1', 'to': 'n2', 'direction': 'forward', 'relationship': 'feeds'}])
    report = compile_and_readback(tmp_path, svg, page)
    finding = next(f for f in report['findings'] if f['code'] == 'edge_not_connected')
    assert finding['edge_id'] == 'e1' and finding['from'] == 'n1' and finding['to'] == 'n2'
    assert 'd(end,to)' in finding['detail']


def test_properly_connected_edge_passes_dual_endpoint_check(tmp_path):
    svg = '''<svg viewBox="0 0 200 100">
      <rect id="node-a" x="10" y="10" width="40" height="30" data-node-ref="n1"/>
      <rect id="node-b" x="150" y="10" width="40" height="30" data-node-ref="n2"/>
      <line id="link" x1="30" y1="25" x2="170" y2="25" stroke="#000000" data-edge-ref="e1"/>
    </svg>'''
    page = expected_page(nodes=('n1', 'n2'), edges=[{
        'edge_id': 'e1', 'from': 'n1', 'to': 'n2', 'direction': 'forward', 'relationship': 'feeds'}])
    report = compile_and_readback(tmp_path, svg, page)
    assert report['status'] == 'pass'
    assert report['findings'] == []
