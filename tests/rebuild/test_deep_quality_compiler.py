"""Q02/Q11–Q14 counterexamples; native XML checks, no screenshot scores."""
import json
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.compiler.svg import parse_svg, SvgError
from test_readback import compile_and_readback, FAMILY, _atom_page
from hostenv import host_fonts

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


@pytest.mark.parametrize('binding', [True, False])
@pytest.mark.parametrize('style', ['opacity="0"', 'font-size="4"', 'fill-opacity="0"'])
def test_split_required_atom_is_not_decorative(tmp_path, binding, style):
    bind = 'data-atom-id="atom:p1:block:b1:text"' if binding else ''
    body = f'<text x="5" y="20" font-family="{FAMILY}" font-size="18">REPORT</text>'
    for text, y in [('Required ', 50), ('body text', 75)]:
        attrs = style if 'font-size' in style else 'font-size="18" ' + style
        body += f'<text {bind} x="5" y="{y}" font-family="{FAMILY}" {attrs}>{text}</text>'
    report = compile_and_readback(tmp_path, body, _atom_page(['REPORT', 'Required body text']))
    assert report['status'] == 'fail'
    assert any(f['code'] == 'unreadable_text' and f.get('atom_id') == 'atom:p1:block:b1:text' for f in report['findings'])


def test_readable_split_atom_with_small_decoration_passes(tmp_path):
    body = ''.join(f'<text x="5" y="{y}" font-family="{FAMILY}" font-size="{size}">{text}</text>'
                   for y, size, text in [(20,18,'REPORT'),(45,18,'Required '),(70,18,'body text'),(90,4,'decoration')])
    assert compile_and_readback(tmp_path, body, _atom_page(['REPORT','Required body text']))['status'] == 'pass'


def test_tspan_style_and_local_opacity_reach_ir():
    source = f'<svg viewBox="0 0 200 100"><text x="5" y="40" font-family="{FAMILY}" font-size="24"><tspan style="fill:#ff0000;font-size:40;font-weight:bold;opacity:0.5" fill-opacity="0.25">VISIBLE</tspan></text></svg>'
    shape = parse_svg(source.encode(), page_id='p1')['shapes'][0]
    assert (shape['fill'], shape['font_size'], shape['bold'], shape['opacity'], shape['fill_opacity']) == ('#ff0000',40,True,0.5,0.25)


@pytest.mark.parametrize('property', ['filter:blur(2px)', 'font-size:NaN', 'opacity:NaN'])
def test_invalid_tspan_style_is_not_silently_ignored(property):
    with pytest.raises(SvgError):
        parse_svg(f'<svg viewBox="0 0 200 100"><text><tspan style="{property}">T</tspan></text></svg>'.encode(), page_id='p1')


def test_rgba_alpha_multiplies_in_native_fill_stroke_and_text(tmp_path):
    svg = tmp_path/'rgba.svg'
    svg.write_text(f'<svg viewBox="0 0 200 100"><rect width="40" height="40" fill="#ff000080" fill-opacity="0.5" stroke="#0000ff80" stroke-opacity="0.25"/><text x="5" y="80" font-family="{FAMILY}" fill="#00000080">T</text></svg>')
    result = compile_deck([SvgInput('p1',svg)],CompileOptions(width_px=200,height_px=100,fonts=host_fonts()),tmp_path/'out')
    with zipfile.ZipFile(result.pptx_path) as z:root=ET.fromstring(z.read('ppt/slides/slide1.xml'))
    values = [int(e.get('val')) for e in root.findall('.//a:srgbClr/a:alpha',NS)]
    assert round(128/255*.5*100000) in values
    assert round(128/255*.25*100000) in values
    assert round(128/255*100000) in values


@pytest.mark.parametrize('body', ['<rect width="40" height="40"/><rect x="20" width="40" height="40"/>', '<rect width="40" height="40" stroke="#ff0000"/>'])
def test_translucent_group_rejects_multiple_paint_operations(tmp_path, body):
    svg=tmp_path/'group.svg';svg.write_text(f'<svg viewBox="0 0 100 100"><g id="unsafe-group" opacity="0.5">{body}</g></svg>')
    with pytest.raises(SvgError, match='unsafe-group.*opacity'):
        compile_deck([SvgInput('p1',svg)],CompileOptions(width_px=100,height_px=100),tmp_path/'out')
    assert not (tmp_path/'out/deck.pptx').exists()


@pytest.mark.parametrize('width,height',[(400,200),(200,400),(400,300)])
def test_node_contain_transform_matches_canvas(tmp_path,width,height):
    # Exercise the shipped Node emitter with a recording adapter, separately
    # from the real artifact-tool/render acceptance run.
    node=shutil.which('node')
    if not node:pytest.skip('Node runtime is not available')
    adapter=tmp_path/'adapter.mjs';adapter.write_text('''import fs from 'node:fs/promises';
let shapes=[];export const Presentation={create:()=>({slides:{add:()=>({shapes:{add:(s)=>{shapes.push(s);return {}}}})}})};
export const PresentationFile={exportPptx:async()=>({save:async p=>fs.writeFile(p,JSON.stringify(shapes))})};''')
    source=parse_svg(b'<svg viewBox="0 0 400 300"><rect id="bottom" x="20" y="250" width="50" height="40" fill="#ff0000"/></svg>', page_id='p1')
    inp=tmp_path/'input.json';inp.write_text(json.dumps({'width':width,'height':height,'pages':[source]}))
    out=tmp_path/'record.json';script=Path(__file__).resolve().parents[2]/'src/deck_master/resources/compiler/native.mjs'
    subprocess.run([node,str(script),str(adapter),str(inp),str(out)],check=True,capture_output=True)
    position=json.loads(out.read_text())[0]['position']
    scale=min(width/400,height/300)
    assert position['left'] == pytest.approx((width-400*scale)/2+20*scale)
    assert position['top'] == pytest.approx((height-300*scale)/2+250*scale)
    assert position['height'] == pytest.approx(40*scale)
    assert position['top']+position['height']<=height
