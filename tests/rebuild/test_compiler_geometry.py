"""T10/AC-K14 design authority: the Document's canvas (not any hidden 16:9
default) drives prompt projection and the actual compiled PPT page size."""
import json
import zipfile
import xml.etree.ElementTree as ET

import pytest

from deck_master import service
from deck_master.models import bump_revision
from deck_master.pipeline import artifact, produce
from deck_master.production import project_prompt, resolve_design
from deck_master.store import Store

CANVAS_4_3 = {
    'width_px': 960,
    'height_px': 720,
    'slide_width_in': 10.0,
    'slide_height_in': 7.5,
    'fit': 'contain',
}

PAGE = {
    'schema_version': 'deck_page_package.v2',
    'page_id': 'p1',
    'customer_visible': {'title': '四比三画布', 'body_blocks': []},
    'visual_spec': {'intent': 'canvas authority check', 'reference_mode': 'new_design'},
}

SVG_4_3 = '''<svg viewBox="0 0 960 720">
  <rect width="960" height="720" fill="#ffffff"/>
  <text x="60" y="120" font-family="Hiragino Sans GB" font-size="40">四比三画布</text>
</svg>'''


def create_project(tmp_path):
    service.create(tmp_path / 'project', brief='canvas authority', draft={'pages': [dict(PAGE)]},
                   design={'canvas': dict(CANVAS_4_3)})
    return tmp_path / 'project'


def attach_svg(project, svg_text):
    store = Store(project)
    document = store.load_document()
    svg_file = store.staging_dir / 'page-1.svg'
    svg_file.parent.mkdir(parents=True, exist_ok=True)
    svg_file.write_text(svg_text)
    svg_ref = artifact(store, svg_file, 'svg', page_id='p1')
    updated = bump_revision(document, {'operation_id': 'attach-svg', 'kind': 'task_update',
                                       'description': 'attach svg for produce test', 'read_set': []})
    updated['pages'][0]['svg'] = svg_ref
    store.commit_change(base_revision=document['revision_id'], document=updated,
                        operation_id='attach-svg')
    return store


def slide_size(pptx_bytes):
    with zipfile.ZipFile(__import__('io').BytesIO(pptx_bytes)) as z:
        presentation = ET.fromstring(z.read('ppt/presentation.xml'))
    ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
    sld_sz = presentation.find('p:sldSz', ns)
    return int(sld_sz.get('cx')), int(sld_sz.get('cy'))


def test_document_canvas_is_prompt_and_compile_authority(tmp_path, resolvable_font_family):
    # AC-K14: a 4:3 Document canvas flows into the prompt projection, resolve_design,
    # and the real produced PPT page size; no hidden 16:9 default appears anywhere.
    project = create_project(tmp_path)
    store = attach_svg(project, SVG_4_3.replace("Hiragino Sans GB", resolvable_font_family))
    document = store.load_document()
    assert document['design_context']['canvas'] == CANVAS_4_3
    assert (document['design_context']['canvas']['slide_width_in'],
            document['design_context']['canvas']['slide_height_in']) != (40 / 3, 7.5)

    page = store.read_object_json(document['pages'][0]['page'])
    effective, _ = resolve_design(page, document['design_context'],
                                  document['design_context'].get('assets', []))
    assert effective['canvas'] == CANVAS_4_3
    request = project_prompt(page, document['design_context'],
                             document['design_context'].get('assets', []))
    assert 'Canvas: 960x720 px' in request['prompt']
    assert 'physical size 10.0x7.5 in' in request['prompt']
    assert '1280x720' not in request['prompt']
    assert request['projection']['canvas'] == CANVAS_4_3

    report = produce(project)
    assert report['status'] == 'pass'
    assert report['findings'] == []

    delivered = store.load_document()
    pptx_ref = delivered['outputs']['pptx']
    pptx_bytes = store.read_object_bytes(store.read_object_json(pptx_ref)['file'])
    # 10in x 7.5in at 914400 EMU/in: the actual slide size, not 16:9 12192000 EMU.
    assert slide_size(pptx_bytes) == (9144000, 6858000)
    entry = delivered['pages'][0]
    assert entry['svg_preview'] and entry['ppt_preview']
    render_report = json.loads(store.read_object_bytes(
        store.read_object_json(delivered['outputs']['render_report'])['file']))
    assert render_report['visual_review'] == 'not_evaluated'


def test_default_canvas_only_applies_when_document_says_so(tmp_path):
    # AC-K14 boundary: the built-in default canvas is a creation-time default,
    # not a hidden fallback at prompt/compile time. With no canvas override the
    # Document keeps the default; with an override nothing of 16:9 survives.
    service.create(tmp_path / 'default-project', brief='default canvas',
                   draft={'pages': [dict(PAGE)]})
    default_doc = Store(tmp_path / 'default-project').load_document()
    assert default_doc['design_context']['canvas']['width_px'] == 1600
    assert default_doc['design_context']['canvas']['slide_width_in'] == pytest.approx(40 / 3)

    overridden = create_project(tmp_path)
    canvas = Store(overridden).load_document()['design_context']['canvas']
    assert canvas == CANVAS_4_3
    assert canvas['width_px'] != 1600 and canvas['slide_width_in'] != 40 / 3
