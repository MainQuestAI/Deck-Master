import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import pytest
from deck_master.compiler import SvgInput, CompileOptions, compile_deck
from deck_master import service
from deck_master.store import Store, ConflictError
from deck_master.editing import edit_page


def test_python_compiler_zero_alpha_and_reverse_line(tmp_path):
    p=tmp_path/'input.svg'
    p.write_text('<svg viewBox="0 0 100 75"><rect x="0" y="0" width="10" height="10" fill="#000000" opacity="0"/><line x1="90" y1="10" x2="10" y2="60" stroke="#ff0000"/></svg>')
    result=compile_deck([SvgInput('p',p)],CompileOptions(width_px=960,height_px=720),tmp_path/'out')
    with zipfile.ZipFile(result.pptx_path) as z:
        xml=ET.fromstring(z.read('ppt/slides/slide1.xml'));ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        assert any(n.get('val')=='0' for n in xml.findall('.//a:alpha',ns))
        path=xml.find('.//a:path',ns)
        start=path.find('a:moveTo/a:pt',ns);end=path.find('a:lnTo/a:pt',ns)
        assert int(start.get('x'))>int(end.get('x'))
        assert int(start.get('y'))<int(end.get('y'))


def test_edit_invalidates_only_affected_page_and_rejects_conflict(tmp_path):
    page=lambda n:{'schema_version':'deck_page_package.v2','page_id':n,'customer_visible':{'title':n,'body_blocks':[{'id':'b','type':'paragraph','text':'old'}]},'visual_spec':{'intent':'test','reference_mode':'new_design'}}
    service.create(tmp_path/'project',brief='two pages',draft={'pages':[page('p1'),page('p2')]})
    store=Store(tmp_path/'project');doc=store.load_document();changed=store.read_object_json(doc['pages'][0]['page']);changed['customer_visible']['title']='updated'
    result=edit_page(store.project_root,page=changed,base_revision=doc['revision_id'],page_hash=doc['pages'][0]['page']['sha256'],operation_id='edit-one')
    after=store.load_document()
    assert after['pages'][1]==doc['pages'][1]
    assert after['pages'][0]['svg'] is None
    with pytest.raises(ConflictError):edit_page(store.project_root,page=changed,base_revision=doc['revision_id'],page_hash=doc['pages'][0]['page']['sha256'],operation_id='edit-conflicting')


def test_host_feedback_requires_existing_page_and_instruction(tmp_path):
    service.create(tmp_path/'p', brief='test')
    store=Store(tmp_path/'p'); before=store.load_document()
    with pytest.raises(service.ServiceError):
        service.open_host_task(store, kind='repair', page_ids=['missing'], instruction='fix')
    with pytest.raises(service.ServiceError):
        service.open_host_task(store, kind='repair', page_ids=[], instruction='')
    assert store.load_document()==before


def test_workbench_session_token_and_cancel(tmp_path):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from deck_master.web import WorkbenchServer
    service.create(tmp_path/'p', brief='test')
    task=service.continue_project(tmp_path/'p')['pending_tasks'][0]
    server=WorkbenchServer(tmp_path/'p');url=server.start()
    try:
        token=json.load(urlopen(url+'api/session'))['token']
        body=json.dumps({'task_id':task['task_id'],'reason':'test cancellation'}).encode()
        with pytest.raises(HTTPError) as denied:
            urlopen(Request(url+'api/cancel',data=body,headers={'Origin':url.rstrip('/')}))
        assert denied.value.code==403
        result=json.load(urlopen(Request(url+'api/cancel',data=body,headers={'Origin':url.rstrip('/'),'X-Deck-Token':token})))
        assert result['status']=='cancelled'
    finally:
        server.stop()


def test_invalid_draft_does_not_create_project(tmp_path):
    with pytest.raises(Exception):
        service.create(tmp_path/'invalid',brief='test',draft={'pages':[{'page_id':'broken'}]})
    assert not (tmp_path/'invalid').exists()


def test_images_require_explicit_asset_and_embed_original_bytes(tmp_path):
    from PIL import Image
    from deck_master.compiler.svg import SvgError
    asset=tmp_path/'logo.png';Image.new('RGB',(20,10),'red').save(asset)
    svg=tmp_path/'asset.svg';svg.write_text('<svg viewBox="0 0 100 100"><image href="approved-logo" x="0" y="0" width="100" height="100"/></svg>')
    with pytest.raises(SvgError,match='approved'):
        compile_deck([SvgInput('p',svg)],CompileOptions(),tmp_path/'denied')
    result=compile_deck([SvgInput('p',svg)],CompileOptions(assets={'p':{'approved-logo':str(asset)}}),tmp_path/'ok')
    with zipfile.ZipFile(result.pptx_path) as z:
        media=[name for name in z.namelist() if name.startswith('ppt/media/')]
        assert len(media)==1 and z.read(media[0])==asset.read_bytes()


def test_definitions_and_empty_href_use_the_same_approved_image_resolution(tmp_path):
    from PIL import Image
    from deck_master.compiler.svg import parse_svg, SvgError
    from deck_master.pipeline import preview_svg_bytes
    asset = tmp_path / 'approved.png'
    Image.new('RGB', (8, 8), 'blue').save(asset)
    data = (b'<svg viewBox="0 0 100 100" xmlns:xlink="http://www.w3.org/1999/xlink">'
            b'<defs><image id="logo" href="" xlink:href="approved" width="10" height="10"/></defs>'
            b'<use href="#logo"/></svg>')
    parsed = parse_svg(data, page_id='p1', assets={'approved': str(asset)})
    assert len(parsed['shapes']) == 1
    rewritten = preview_svg_bytes(data, page_id='p1', assets={'approved': str(asset)})
    assert asset.as_uri().encode() in rewritten
    assert b'xlink:href="approved"' not in rewritten
    with pytest.raises(SvgError, match='p1/logo.*approved'):
        parse_svg(data, page_id='p1', assets={})


def test_edit_replay_after_later_edit_and_restore_keeps_history(tmp_path):
    from deck_master.editing import restore
    from copy import deepcopy
    page={'schema_version':'deck_page_package.v2','page_id':'p','customer_visible':{'title':'original','body_blocks':[]},'visual_spec':{'intent':'test','reference_mode':'new_design'}}
    service.create(tmp_path/'p',brief='test',draft={'pages':[page]})
    s=Store(tmp_path/'p');original=s.load_document();first=deepcopy(page);first['customer_visible']['title']='first'
    edit_page(s.project_root,page=first,base_revision=original['revision_id'],page_hash=original['pages'][0]['page']['sha256'],operation_id='edit-first')
    middle=s.load_document();second=deepcopy(page);second['customer_visible']['title']='second'
    edit_page(s.project_root,page=second,base_revision=middle['revision_id'],page_hash=middle['pages'][0]['page']['sha256'],operation_id='edit-second')
    before=s.load_document()
    replay=edit_page(s.project_root,page=first,base_revision=original['revision_id'],page_hash=original['pages'][0]['page']['sha256'],operation_id='edit-first')
    assert replay['status']=='already_applied' and s.load_document()==before
    restore(s.project_root,revision_id=original['revision_id'],base_revision=before['revision_id'],operation_id='restore-first')
    after=s.load_document();assert after['revision_id']!=original['revision_id']
    assert after['pages']==original['pages'] and after['parent_revision_id']==before['revision_id']
    assert s.load_document(before['revision_id'])==before


def test_source_paint_feature_never_silently_ignored():
    from deck_master.compiler.svg import parse_svg, SvgError
    with pytest.raises(SvgError,match='stroke-dasharray'):
        parse_svg(b'<svg viewBox="0 0 100 100"><line x1="0" y1="0" x2="50" y2="50" stroke="red" stroke-dasharray="4 2"/></svg>',page_id='p')


def test_approved_image_slice_crops_without_stretch(tmp_path):
    from PIL import Image
    asset=tmp_path/'image.png';Image.new('RGB',(200,100),'blue').save(asset)
    svg=tmp_path/'image.svg';svg.write_text('<svg viewBox="0 0 100 100"><image href="asset" width="100" height="100" preserveAspectRatio="xMidYMid slice"/></svg>')
    result=compile_deck([SvgInput('p',svg)],CompileOptions(assets={'p':{'asset':str(asset)}}),tmp_path/'out')
    with zipfile.ZipFile(result.pptx_path) as z:
        root=ET.fromstring(z.read('ppt/slides/slide1.xml'))
    crop=root.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}srcRect')
    assert crop.get('l')=='25000' and crop.get('r')=='25000'


def test_reconstruction_declared_original_must_match_actual_image():
    from deck_master.tasks import _validate_svg_reference, EnvelopeError
    svg=('<svg data-blueprint-sha256="'+'a'*64+'"/>').encode()
    _validate_svg_reference(svg,'a'*64)
    with pytest.raises(EnvelopeError,match='different original'):
        _validate_svg_reference(svg,'b'*64)


def test_readback_rejects_truncated_or_extra_slides(tmp_path):
    from deck_master.pipeline import readback
    from deck_master.compiler.svg import parse_svg
    svg=tmp_path/'input.svg';svg.write_text('<svg viewBox="0 0 100 100"><rect width="10" height="10"/></svg>')
    compiled=compile_deck([SvgInput('p',svg)],CompileOptions(),tmp_path/'compiled')
    page={'schema_version':'deck_page_package.v2','page_id':'p','customer_visible':{'title':'','body_blocks':[]},'visual_spec':{'intent':'test','reference_mode':'new_design'}}
    report=readback(compiled.pptx_path,[parse_svg(svg.read_bytes(),page_id='p')],[page,page])
    assert report['status']=='fail' and any(f['code']=='slide_count_mismatch' for f in report['findings'])


def test_history_follows_committed_ancestry_not_creation_timestamp(tmp_path):
    from deck_master.editing import history,restore
    from deck_master.models import bump_revision
    from deck_master.store import StoreError
    page={'schema_version':'deck_page_package.v2','page_id':'p','customer_visible':{'title':'original','body_blocks':[]},'visual_spec':{'intent':'test','reference_mode':'new_design'}}
    service.create(tmp_path/'p',brief='test',draft={'pages':[page]});s=Store(tmp_path/'p');before=s.load_document()
    page['customer_visible']['title']='edited';edit_page(s.project_root,page=page,base_revision=before['revision_id'],page_hash=before['pages'][0]['page']['sha256'],operation_id='edit')
    current=s.load_document();records=history(s.project_root)['revisions']
    assert records[0]['revision_id']==current['revision_id'] and records[1]['revision_id']==before['revision_id']
    orphan=bump_revision(current,{'operation_id':'orphan','kind':'restore','description':'uncommitted','read_set':[]})
    (s.revisions_dir/(orphan['revision_id']+'.json')).write_text(json.dumps(orphan))
    assert orphan['revision_id'] not in [r['revision_id'] for r in history(s.project_root)['revisions']]
    with pytest.raises(StoreError,match='committed ancestor'):
        restore(s.project_root,revision_id=orphan['revision_id'],base_revision=current['revision_id'],operation_id='restore-orphan')


def test_pending_host_task_blocks_delivery_readiness(tmp_path):
    from deck_master.editing import review_status
    service.create(tmp_path/'p',brief='test')
    s=Store(tmp_path/'p');service.continue_project(s.project_root);doc=s.load_document()
    # Even an existing PPT cannot make a new, unprocessed Host request ready.
    doc['outputs']['pptx']={'path':'.deckmaster/objects/test.json','sha256':'a'*64}
    assert review_status(s,doc)=='not_evaluated'
    from deck_master.view import project_view
    assert project_view(s.project_root)['view_status']=='awaiting_host'
