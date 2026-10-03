"""PR97 external R1/R2: distinct required text and actual native paint."""
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pytest

from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.compiler.svg import parse_svg
from deck_master.pipeline import readback
from test_readback import FAMILY, _atom_page, compile_and_readback, resolve_font, NS


def text(value, y=20, attrs='', identity=''):
    return f'<text id="{identity}" x="5" y="{y}" font-family="{FAMILY}" font-size="18" {attrs}>{value}</text>'


@pytest.mark.parametrize('hidden', [True, False])
def test_duplicate_unbound_atoms_need_distinct_readable_locations(tmp_path, hidden):
    body=text('30%',identity='title')+text('30%',60,'opacity="0"' if hidden else '', 'body')
    report=compile_and_readback(tmp_path,body,_atom_page(['30%','30%']))
    assert report['status']==('fail' if hidden else 'pass')
    if hidden:
        assert any(f['code']=='unverifiable_text_mapping' for f in report['findings'])


@pytest.mark.parametrize('words,body', [
    (['30%','30%'],text('30%')),
    (['AB','B'],text('AB')),
    (['aa','aa'],text('aaa')),
])
def test_required_atoms_cannot_share_characters(tmp_path,words,body):
    report=compile_and_readback(tmp_path,body,_atom_page(words))
    assert report['status']=='fail'
    assert any(f['code']=='unverifiable_text_mapping' for f in report['findings'])


def test_partial_binding_reserves_title_from_unbound_body(tmp_path):
    body=text('30%',attrs='data-atom-id="atom:p1:title"')+text('30%',60,'opacity="0"')
    report=compile_and_readback(tmp_path,body,_atom_page(['30%','30%']))
    assert report['status']=='fail'
    assert any(f['code']=='unreadable_text' and f['atom_id']=='atom:p1:block:b1:text' for f in report['findings'])


def test_bound_readable_body_ignores_same_text_decoration(tmp_path):
    body=text('REPORT')+text('Body',50,'data-atom-id="atom:p1:block:b1:text"')+text('Body',80,'opacity="0"')
    assert compile_and_readback(tmp_path,body,_atom_page(['REPORT','Body']))['status']=='pass'


@pytest.mark.parametrize('fill,expected', [('none','fail'),('#00000000','fail'),('#00000080','pass'),('#000000','pass')])
def test_required_text_checks_actual_solid_paint(tmp_path,fill,expected):
    body=text('REPORT')+text('Body',60,f'fill="{fill}" data-atom-id="atom:p1:block:b1:text"')
    report=compile_and_readback(tmp_path,body,_atom_page(['REPORT','Body']))
    assert report['status']==expected
    if expected=='fail':assert any(f['code']=='unreadable_text' for f in report['findings'])


@pytest.mark.parametrize('last_alpha,expected', [('0','fail'),('1','pass')])
def test_gradient_text_requires_all_stops_transparent_to_fail(tmp_path,last_alpha,expected):
    body=f'<defs><linearGradient id="paint"><stop offset="0" stop-opacity="0"/><stop offset="1" stop-opacity="{last_alpha}"/></linearGradient></defs>'
    body+=text('REPORT')+text('Body',60,'fill="url(#paint)" data-atom-id="atom:p1:block:b1:text"')
    report=compile_and_readback(tmp_path,body,_atom_page(['REPORT','Body']))
    assert report['status']==expected


def test_unresolved_native_fill_cannot_default_to_readable(tmp_path):
    svg=tmp_path/'source.svg';svg.write_text('<svg viewBox="0 0 200 100">'+text('REPORT')+text('Body',60,'data-atom-id="atom:p1:block:b1:text"')+'</svg>')
    result=compile_deck([SvgInput('p1',svg)],CompileOptions(width_px=200,height_px=100,fonts=resolve_font()),tmp_path/'compiled')
    patched=tmp_path/'unresolved.pptx'
    with zipfile.ZipFile(result.pptx_path) as src,zipfile.ZipFile(patched,'w') as dst:
        for item in src.infolist():
            data=src.read(item.filename)
            if item.filename=='ppt/slides/slide1.xml':
                root=ET.fromstring(data);props=root.findall('.//a:rPr',NS)[1]
                props.remove(props.find('a:solidFill',NS));data=ET.tostring(root)
            dst.writestr(item,data)
    report=readback(patched,[parse_svg(svg.read_bytes(),page_id='p1')],[_atom_page(['REPORT','Body'])])
    assert report['status']=='fail'
    assert any(f['code']=='unverifiable_text_mapping' for f in report['findings'])


def test_unique_disjoint_substring_allocation_remains_readable(tmp_path):
    body=text('AB')+text('B',60)
    assert compile_and_readback(tmp_path,body,_atom_page(['AB','B']))['status']=='pass'


def test_unbound_split_with_hidden_required_run_is_unreadable(tmp_path):
    body=text('REPORT')+'<text x="5" y="60" font-family="'+FAMILY+'" font-size="18">Bo<tspan x="30" opacity="0">dy</tspan></text>'
    report=compile_and_readback(tmp_path,body,_atom_page(['REPORT','Body']))
    assert report['status']=='fail'
    assert any(f['code']=='unreadable_text' for f in report['findings'])


@pytest.mark.parametrize('fill,expected',[('none','fail'),('#00000000','fail'),('#00000080','pass'),('#000000','pass')])
def test_node_postprocessing_preserves_required_text_paint(tmp_path,monkeypatch,fill,expected):
    # Reproduce the observed exporter defaulting text 'none' to black. The
    # shipped postprocessor must restore source paint before publication.
    import json
    from deck_master.compiler import api, native
    svg=tmp_path/'source.svg';svg.write_text('<svg viewBox="0 0 200 100">'+text('REPORT')+text('Body',60,f'fill="{fill}" data-atom-id="atom:p1:block:b1:text"')+'</svg>')
    fonts=resolve_font()
    def wrong_export(command,**kwargs):
        manifest=json.loads(Path(command[-2]).read_text())
        for page in manifest['pages']:
            for shape in page['shapes']:
                if shape['kind']=='text':shape['fill']='#000000';shape['opacity']=shape['fill_opacity']=1
        native.emit(manifest['pages'],200,100,fonts,Path(command[-1]))
    monkeypatch.setattr(api.subprocess,'run',wrong_export)
    result=compile_deck([SvgInput('p1',svg)],CompileOptions(width_px=200,height_px=100,fonts=fonts,node_executable='fixture-node',artifact_module='fixture-module'),tmp_path/'node')
    report=readback(result.pptx_path,[parse_svg(svg.read_bytes(),page_id='p1')],[_atom_page(['REPORT','Body'])])
    assert report['status']==expected
    if expected=='fail':assert any(f['code']=='unreadable_text' for f in report['findings'])
