import zipfile
import xml.etree.ElementTree as ET
from deck_master.compiler import SvgInput, CompileOptions, compile_deck


def test_gradient_zero_stop_and_group_alpha_are_in_actual_ppt(tmp_path):
    svg=tmp_path/'paint.svg'
    svg.write_text('''<svg viewBox="0 0 100 100"><defs><linearGradient id="g"><stop offset="0" stop-color="#ff0000" stop-opacity="0"/><stop offset="1" stop-color="#0000ff"/></linearGradient></defs><g opacity="0.5"><rect width="100" height="100" fill="url(#g)"/></g></svg>''')
    result=compile_deck([SvgInput('paint',svg)],CompileOptions(width_px=100,height_px=100),tmp_path/'result')
    with zipfile.ZipFile(result.pptx_path) as z:
        root=ET.fromstring(z.read('ppt/slides/slide1.xml'))
    ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
    stops=root.findall('.//a:gradFill/a:gsLst/a:gs',ns)
    assert [s.find('a:srgbClr/a:alpha',ns).get('val') for s in stops]==['0','50000']


NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def _slide_root(tmp_path, body):
    from deck_master.compiler import compile_deck, CompileOptions, SvgInput
    svg = tmp_path / 'opacity.svg'
    svg.write_text(f'<svg viewBox="0 0 100 100">{body}</svg>')
    result = compile_deck([SvgInput('paint', svg)], CompileOptions(width_px=100, height_px=100),
                          tmp_path / 'opacity-out')
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(result.pptx_path) as z:
        return ET.fromstring(z.read('ppt/slides/slide1.xml'))


def _shape(root, name):
    for sp in root.iter('{%s}sp' % NS['p']):
        node = sp.find('p:nvSpPr/p:cNvPr', NS)
        if node is not None and node.get('name') == name:
            return sp
    raise AssertionError(f'shape {name} not found in slide XML')


def _fill_alpha(sp):
    alpha = sp.find('p:spPr/a:solidFill/a:srgbClr/a:alpha', NS)
    return None if alpha is None else alpha.get('val')


def _stroke_alpha(sp):
    alpha = sp.find('p:spPr/a:ln/a:solidFill/a:srgbClr/a:alpha', NS)
    return None if alpha is None else alpha.get('val')


def test_zero_fill_and_stroke_opacity_written_to_slide_xml(tmp_path):
    # AC-K05: explicit 0 stays 0 in the real DrawingML; an omitted opacity
    # defaults to full alpha, so None and 0 stay distinguishable on readback.
    root = _slide_root(tmp_path, '''
      <rect id="fill0" width="20" height="20" fill="#ff0000" fill-opacity="0"/>
      <rect id="filldefault" x="30" width="20" height="20" fill="#ff0000"/>
      <line id="stroke0" x1="0" y1="50" x2="20" y2="50" stroke="#0000ff" stroke-opacity="0"/>
      <line id="strokedefault" x1="30" y1="50" x2="50" y2="50" stroke="#0000ff"/>
    ''')
    assert _fill_alpha(_shape(root, 'fill0')) == '0'
    assert _fill_alpha(_shape(root, 'filldefault')) == '100000'
    assert _stroke_alpha(_shape(root, 'stroke0')) == '0'
    assert _stroke_alpha(_shape(root, 'strokedefault')) == '100000'


def test_group_opacity_multiplies_into_slide_xml(tmp_path):
    # AC-K05: group opacity multiplies into both fill and stroke alpha; a fully
    # transparent group still writes alpha val=0 instead of dropping the paint.
    root = _slide_root(tmp_path, '''
      <g opacity="0.5">
        <rect id="half" width="20" height="20" fill="#ff0000"/>
        <rect id="quarter" x="30" width="20" height="20" fill="#ff0000" fill-opacity="0.5"/>
      </g>
      <g opacity="0">
        <rect id="gone" x="60" width="20" height="20" fill="#ff0000"/>
      </g>
      <g opacity="0.5">
        <line id="strokehalf" x1="0" y1="80" x2="20" y2="80" stroke="#0000ff" stroke-opacity="0"/>
      </g>
    ''')
    assert _fill_alpha(_shape(root, 'half')) == '50000'
    assert _fill_alpha(_shape(root, 'quarter')) == '25000'
    assert _fill_alpha(_shape(root, 'gone')) == '0'
    assert _stroke_alpha(_shape(root, 'strokehalf')) == '0'
