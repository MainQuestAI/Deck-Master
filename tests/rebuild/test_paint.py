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
