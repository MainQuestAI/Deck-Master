"""Real SVG/PPT evidence for Q02/Q11/Q12; no professional acceptance claim."""
import json
from pathlib import Path

import pytest
from PIL import Image

from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.compiler.svg import parse_svg
from deck_master.pipeline import executable, run, render_deck, resolve_fonts, readback
from hostenv import resolve_host_font

pytestmark=pytest.mark.render


@pytest.mark.parametrize('case',['tspan-style','tspan-opacity','rgba-fill','split-hidden'])
def test_local_svg_and_actual_ppt_quality(tmp_path, case):
    family=resolve_host_font();body='<rect width="320" height="160" fill="#ffffff"/>'
    page={'page_id':'p1','customer_visible':{},'visual_spec':{'intent':'synthetic proof','reference_mode':'new_design'}}
    if case=='tspan-style':
        body+=f'<text x="10" y="65" font-family="{family}" font-size="24"><tspan style="fill:#ff0000;font-size:40;font-weight:bold">VISIBLE</tspan></text>'
    elif case=='tspan-opacity':
        body+=f'<text x="10" y="65" font-family="{family}" font-size="24"><tspan fill-opacity="0">HIDDEN</tspan></text>'
    elif case=='rgba-fill':
        body+='<rect x="40" y="30" width="120" height="80" fill="#ff000080"/>'
    else:
        page['customer_visible']={'title':'REPORT','body_blocks':[{'id':'b','type':'paragraph','text':'Required body text'}]}
        body+=f'<text x="10" y="30" font-family="{family}" font-size="24">REPORT</text>'
        for y,text in [(75,'Required '),(105,'body text')]:
            body+=f'<text data-atom-id="atom:p1:block:b:text" x="10" y="{y}" font-family="{family}" font-size="18" opacity="0">{text}</text>'
    svg=tmp_path/'source.svg';svg.write_text('<svg viewBox="0 0 320 160">'+body+'</svg>')
    parsed=parse_svg(svg.read_bytes(),page_id='p1');fonts=resolve_fonts([parsed])
    compiled=compile_deck([SvgInput('p1',svg)],CompileOptions(width_px=320,height_px=160,fonts=fonts),tmp_path/'compile')
    run([executable('rsvg-convert'),str(svg),'-o',str(tmp_path/'source.png')])
    rendered=render_deck(compiled.pptx_path,tmp_path/'rendered',fonts=fonts)[0]
    source=Image.open(tmp_path/'source.png').convert('RGB');ppt=Image.open(rendered).convert('RGB')
    def count(image,predicate):return sum(predicate(p) for p in image.getdata())
    if case=='tspan-style':
        for image in (source,ppt):
            assert count(image,lambda p:p[0]>180 and p[1]<100 and p[2]<100)>200
            assert count(image,lambda p:max(p)<100)==0
    elif case=='tspan-opacity':
        assert count(source,lambda p:max(p)<100)==count(ppt,lambda p:max(p)<100)==0
    elif case=='rgba-fill':
        a=source.getpixel((100,70));b=ppt.getpixel((round(100*ppt.width/320),round(70*ppt.height/160)))
        assert max(abs(a[i]-b[i]) for i in range(3))<=2
    report=readback(compiled.pptx_path,[parsed],[page])
    (tmp_path/'readback.json').write_text(json.dumps(report,indent=2))
    assert report['status']==('fail' if case in ('split-hidden','tspan-opacity') else 'pass')
    if case=='tspan-opacity':assert any(f['code']=='hidden_or_tiny_text' for f in report['findings'])
    if case=='split-hidden':assert any(f['code']=='unreadable_text' for f in report['findings'])
