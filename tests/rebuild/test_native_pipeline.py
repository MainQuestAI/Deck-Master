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
