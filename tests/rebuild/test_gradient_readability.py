"""Required gradient text must have nonzero-area paint, not just a stop."""
import json
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from deck_master import pipeline, service
from deck_master.models import bump_revision
from deck_master.readback_text import _run_state
from deck_master.store import Store
from test_external_review_readback import text
from test_readback import _atom_page, compile_and_readback, NS

CASES = [
    ('start-zero', [(0,1),(0,0),(1,0)], 'fail'),
    ('end-zero', [(0,0),(1,0),(1,1)], 'fail'),
    ('interior-zero', [(0,0),(.5,0),(.5,1),(.5,0),(1,0)], 'fail'),
    ('all-start-zero', [(0,1),(0,0)], 'fail'),
    ('all-end-zero', [(1,0),(1,1)], 'fail'),
    ('start-outgoing', [(0,0),(0,1),(1,0)], 'pass'),
    ('end-incoming', [(0,0),(1,1),(1,0)], 'pass'),
    ('interior-incoming', [(0,0),(.5,1),(.5,0),(1,0)], 'pass'),
    ('interior-outgoing', [(0,0),(.5,0),(.5,1),(1,0)], 'pass'),
    ('left-pad', [(.5,1),(.5,0)], 'pass'),
    ('right-pad', [(.5,0),(.5,1)], 'pass'),
    ('partial', [(0,1),(1,0)], 'pass'),
    ('partial-reverse', [(0,0),(1,1)], 'pass'),
    ('transparent', [(0,0),(1,0)], 'fail'),
]


def gradient_body(stops):
    nodes=''.join(f'<stop offset="{position}" stop-opacity="{alpha}"/>' for position,alpha in stops)
    return '<defs><linearGradient id="g">'+nodes+'</linearGradient></defs>'+text('REPORT')+text('Body',60,'fill="url(#g)" data-atom-id="atom:p1:block:b1:text"')


@pytest.mark.parametrize('name,stops,expected', CASES, ids=[case[0] for case in CASES])
def test_native_gradient_checks_actual_intervals(tmp_path,name,stops,expected):
    report=compile_and_readback(tmp_path,gradient_body(stops),_atom_page(['REPORT','Body']))
    assert report['status']==expected
    if expected=='fail':assert any(f['code']=='unreadable_text' for f in report['findings'])


@pytest.mark.parametrize('positions', [['0','-1'],['0','100001'],['50000','0'],['0','NaN'],['0',None],['0','1.5']])
def test_unverifiable_native_stop_positions_cannot_pass(positions):
    props=ET.Element('{'+NS['a']+'}rPr',sz='1800')
    fill=ET.SubElement(props,'{'+NS['a']+'}gradFill');stops=ET.SubElement(fill,'{'+NS['a']+'}gsLst')
    for position in positions:
        stop=ET.SubElement(stops,'{'+NS['a']+'}gs',{} if position is None else {'pos':position})
        ET.SubElement(stop,'{'+NS['a']+'}srgbClr',val='000000')
    assert _run_state(props)=='unverifiable'


@pytest.mark.render
@pytest.mark.parametrize('name,stops,expected', [CASES[0],CASES[1],CASES[11]], ids=['start-zero','end-zero','partial'])
def test_real_gradient_svg_ppt_and_persisted_check(tmp_path,name,stops,expected):
    page={'schema_version':'deck_page_package.v2',**_atom_page(['REPORT','Body'])};project=tmp_path/'project'
    service.create(project,brief='Synthetic gradient interval regression',draft={'pages':[page]},design={'canvas':{'width_px':200,'height_px':100,'slide_width_in':200/96,'slide_height_in':100/96,'fit':'contain'}})
    svg=tmp_path/'source.svg';svg.write_text('<svg viewBox="0 0 200 100"><rect width="200" height="100" fill="#ffffff"/>'+gradient_body(stops)+'</svg>')
    pipeline.run([pipeline.executable('rsvg-convert'),str(svg),'-o',str(tmp_path/'source.png')])
    store=Store(project);doc=store.load_document();updated=bump_revision(doc,{'operation_id':'gradient-proof','kind':'artifact_adoption','description':'synthetic explicit gradient','read_set':[]})
    updated['pages'][0]['svg']=pipeline.artifact(store,svg,'svg',page_id='p1');store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='gradient-proof')
    report=pipeline.produce(project);doc=store.load_document();stored=json.loads(store.read_object_bytes(store.read_object_json(doc['outputs']['render_report'])['file']))
    assert report['status']==stored['status']==expected
    for field,output in [('pptx','actual.pptx')]:
        (tmp_path/output).write_bytes(store.read_object_bytes(store.read_object_json(doc['outputs'][field])['file']))
    (tmp_path/'actual.png').write_bytes(store.read_object_bytes(store.read_object_json(doc['pages'][0]['ppt_preview'])['file']))
    counts={}
    for image_name in ('source','actual'):
        with Image.open(tmp_path/(image_name+'.png')) as im:
            rgb=im.convert('RGB');crop=rgb.crop((0,round(rgb.height*.35),rgb.width,round(rgb.height*.85)));crop.save(tmp_path/(image_name+'-body.png'))
            counts[image_name]=sum(max(pixel)<250 for pixel in crop.getdata())
    if name in ('start-zero','end-zero'):
        # A rasterizer may sample the single boundary point: it must not
        # produce a readable glyph area. Preserve the actual pixel evidence.
        with Image.open(tmp_path/'source-body.png') as im:
            columns=[x for x in range(im.width) if any(max(im.getpixel((x,y)))<250 for y in range(im.height))]
        assert not columns or max(columns)-min(columns)<=1, (name,counts,columns)
    else:
        assert (counts['source']==0 if expected=='fail' else counts['source']>10)
    # LibreOffice can use the first stop's color for text instead of its
    # gradient. Record both real renders; never call that difference a pass.
    if name=='partial':assert counts['actual']>10
    (tmp_path/'checks.json').write_text(json.dumps({'report':stored,'local_pixels':counts,'synthetic':True,'visual_acceptance':'not_evaluated'},indent=2))


def test_radial_endpoint_without_provable_coverage_is_unverifiable():
    props=ET.fromstring('<a:rPr xmlns:a="'+NS['a']+'" sz="1800"><a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="000000"><a:alpha val="0"/></a:srgbClr></a:gs><a:gs pos="100000"><a:srgbClr val="000000"><a:alpha val="0"/></a:srgbClr></a:gs><a:gs pos="100000"><a:srgbClr val="000000"/></a:gs></a:gsLst><a:path path="circle"/></a:gradFill></a:rPr>')
    assert _run_state(props)=='unverifiable'
