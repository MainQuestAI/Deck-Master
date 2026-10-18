"""Studio uses real core transactions; upload receipts are staging, not inputs."""
from http.client import HTTPConnection
import json
from urllib.parse import urlencode, urlsplit
import uuid

import pytest

from deck_master import content_ops, service, source_uploads
from deck_master.operations import OperationError
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def create(path):
    service.create(path, brief='验证文件上传与真实输入', title='隔离 Studio 验收', audience='验证者', project_format='workbench.v3')
    return Store(path)


def request(url, route, body=None, headers=None):
    target=urlsplit(url)
    connection=HTTPConnection(target.hostname,target.port,timeout=10)
    try:
        connection.request('GET' if body is None else 'POST',route,body=body,headers=headers or {})
        response=connection.getresponse(); raw=response.read()
        return response.status,json.loads(raw) if 'json' in response.getheader('Content-Type','') else raw
    finally:
        connection.close()


def test_studio_same_origin_entry_and_upload_auth(tmp_path):
    store=create(tmp_path/'project'); before=store.read_current(); server=WorkbenchServer(store.project_root)
    url=server.start()
    try:
        status,html=request(url,'/studio/')
        assert status==200 and b'data-workbench-ui="studio"' in html
        assert b'/v2/app.js' in html and b'<iframe' not in html
        assert request(url,'/studio/workspace.css')[0]==200
        assert b'data-workbench-ui="studio"' in request(url,'/')[1]
        assert b'data-workbench-ui="studio"' not in request(url,'/v2/')[1]
        assert request(url,'/studio/../web.py')[0]==404
        token=request(url,'/api/session')[1]['token']
        assert 'material_uploads.v1' in request(url,'/api/health')[1]['ui_capabilities']
        upload_id='upload-'+str(uuid.uuid4())
        route='/api/content/uploads?'+urlencode({'upload_id':upload_id,'name':'事实.md'})
        assert request(url,route,b'# actual',{'X-Deck-Token':token,'Origin':'https://unrelated.example'})[0]==403
        status,receipt=request(url,route,b'# actual',{'X-Deck-Token':token,'Origin':url.rstrip('/')})
        assert status==200 and receipt['status']=='uploaded'
        assert request(url,'/api/content/uploads/'+upload_id)==(200,receipt)
        assert store.read_current()==before and store.load_document()['sources']==[]
    finally:
        server.stop()


def test_upload_identity_tamper_and_symlink_protection(tmp_path):
    store=create(tmp_path/'project'); before=store.read_current()
    upload_id='upload-'+str(uuid.uuid4())
    receipt=source_uploads.receive(store.project_root,upload_id=upload_id,name='facts.md',data=b'actual facts')
    assert source_uploads.receive(store.project_root,upload_id=upload_id,name='facts.md',data=b'actual facts')==receipt
    with pytest.raises(OperationError,match='different bytes'):
        source_uploads.receive(store.project_root,upload_id=upload_id,name='facts.md',data=b'changed facts')
    with pytest.raises(OperationError):
        source_uploads.receive(store.project_root,upload_id='../../escape',name='facts.md',data=b'facts')
    with pytest.raises(OperationError):
        source_uploads.receive(store.project_root,upload_id='upload-'+str(uuid.uuid4()),name='../facts.md',data=b'facts')
    path=source_uploads.resolve(store.project_root,upload_id)
    path.write_bytes(b'corrupted')
    with pytest.raises(OperationError,match='uploaded material changed'):
        source_uploads.resolve(store.project_root,upload_id)
    path.unlink(); other=tmp_path/'outside.md'; other.write_text('outside')
    path.symlink_to(other)
    with pytest.raises(Exception,match='symlink'):
        source_uploads.resolve(store.project_root,upload_id)
    assert store.read_current()==before


def test_upload_only_becomes_source_after_confirmation_and_replay_is_recoverable(tmp_path):
    store=create(tmp_path/'project'); base=store.current_revision_id()
    upload_id='upload-'+str(uuid.uuid4()); body='## 材料事实\n第一步收集，第二步核对。'.encode()
    source_uploads.receive(store.project_root,upload_id=upload_id,name='事实.md',data=body)
    patch={'reason':'补入浏览器选中的材料','source_changes':{'add':[{'upload_id':upload_id}]}}
    operation_id=str(uuid.uuid4())
    result=content_ops.inputs(store.project_root,input=patch,base_revision=base,operation_id=operation_id)
    current=store.load_document()
    assert current['revision_id']!=base and len(current['sources'])==1
    source=current['sources'][0]
    assert source['name']=='事实.md'
    extract=store.read_object_json(source['extract'])
    assert '第一步收集' in extract['text']
    source_uploads.resolve(store.project_root,upload_id).unlink()
    assert content_ops.inputs(store.project_root,input=patch,base_revision=base,operation_id=operation_id)==result
    assert store.load_document()==current
    with pytest.raises(OperationError):
        content_ops.inputs(store.project_root,input={**patch,'reason':'different'},base_revision=base,operation_id=operation_id)


def test_upload_changed_between_resolution_and_extraction_does_not_commit(tmp_path,monkeypatch):
    store=create(tmp_path/'project'); before=store.read_current()
    upload_id='upload-'+str(uuid.uuid4())
    source_uploads.receive(store.project_root,upload_id=upload_id,name='facts.md',data=b'original facts')
    original=service._read_patch_material
    def change_then_read(path):
        from pathlib import Path
        Path(path).write_bytes(b'later bytes')
        return original(path)
    monkeypatch.setattr(service,'_read_patch_material',change_then_read)
    with pytest.raises(OperationError,match='changed before confirmation'):
        content_ops.inputs(store.project_root,input={'reason':'testing receipt bound bytes','source_changes':{'add':[{'upload_id':upload_id}]}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    assert store.read_current()==before


def test_material_http_body_limits_and_confirmation_cas(tmp_path):
    store=create(tmp_path/'project');base=store.current_revision_id();server=WorkbenchServer(store.project_root)
    url=server.start()
    try:
        token=request(url,'/api/session')[1]['token'];headers={'Origin':url.rstrip('/'),'X-Deck-Token':token}
        upload_id='upload-'+str(uuid.uuid4());route='/api/content/uploads?'+urlencode({'upload_id':upload_id,'name':'facts.md'})
        assert request(url,route,b'facts',{'Origin':url.rstrip('/')})[0]==403
        assert request(url,route,b'',headers)[0]==422
        assert request(url,route,b'',{**headers,'Content-Length':str(source_uploads.MAX_BYTES+1)})[0]==422
        assert request(url,route,b'facts',headers)[0]==200
        service.inputs_update(store.project_root,patch={'reason':'advance current input','task_patch':{'audience':'新受众'}},base_revision=base,operation_id=str(uuid.uuid4()))
        current=store.read_current()
        patch={'reason':'stale browser source confirmation','source_changes':{'add':[{'upload_id':upload_id}]}}
        status,_=request(url,'/api/content/inputs',json.dumps({'input':patch,'base_revision':base,'operation_id':str(uuid.uuid4())}).encode(),headers)
        assert status==409 and store.read_current()==current and store.load_document()['sources']==[]
    finally:
        server.stop()


def test_material_upload_readonly_sample_has_no_staging_side_effect(tmp_path):
    from deck_master.samples import create_sample
    path=tmp_path/'readonly';create_sample(path,page_count=2,readonly=True);server=WorkbenchServer(path);url=server.start()
    try:
        token=request(url,'/api/session')[1]['token'];upload_id='upload-'+str(uuid.uuid4())
        status,value=request(url,'/api/content/uploads?'+urlencode({'upload_id':upload_id,'name':'facts.md'}),b'facts',{'Origin':url.rstrip('/'),'X-Deck-Token':token})
        assert status==403 and value['error']['code']=='sample_readonly'
        assert not (path/'.deckmaster/workbench/uploads').exists()
    finally:
        server.stop()


def test_studio_launcher_returns_studio_project_and_launcher_urls(tmp_path):
    from deck_master import launcher, local_runtime, registry
    from urllib.parse import parse_qs
    store=create(tmp_path/'project'); reg=tmp_path/'registry.json'
    launch_desc=local_runtime.descriptor(registry=reg); project_desc=local_runtime.descriptor(project=store.project_root)
    try:
        value=launcher.open_workbench(registry_file=reg,open_browser=False)
        assert value['mode']=='studio' and value['url'].endswith('/studio/')
        entry=registry.register(reg,store.project_root)['project']
        token=request(value['url'],'/api/session')[1]['token']
        origin=value['url'].removesuffix('studio/').rstrip('/')
        status,result=request(value['url'],'/api/projects/open',json.dumps({'entry_id':entry['entry_id']}).encode(),{'Origin':origin,'X-Deck-Token':token,'Content-Type':'application/json'})
        assert status==200 and result['mode']=='studio'
        target=urlsplit(result['url'])
        assert target.path=='/studio/' and parse_qs(target.query)['launcher']==[value['url']]
        assert request(result['url'],'/studio/')[0]==200
    finally:
        local_runtime.stop(project_desc);local_runtime.stop(launch_desc)


@pytest.mark.browser
def test_studio_notes_switch_and_narrow_panel_keep_the_same_draft(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    from deck_master.samples import create_sample
    from deck_master import ui_journal
    path=tmp_path/'project';create_sample(path,page_count=2,readonly=False)
    store=Store(path);before=store.current_revision_id();server=WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            url=server.start()+'studio/#'+urlencode({'project':ui_journal.project_info(path)['project_identity'],'surface':'page','page':'p01','layer':'original_image','revision':before})
            page.goto(url);page.get_by_role('button',name='笔记',exact=True).click()
            note=page.get_by_role('textbox',name='个人草稿',exact=True);expect(note).to_be_visible()
            def check_tool_boundary():
                switcher=page.locator('.page-tools-switcher').bounding_box()
                tabs=page.locator('.studio-note-tabs').bounding_box()
                assert tabs['y']-(switcher['y']+switcher['height']) >= 15.5
            check_tool_boundary()
            note.fill('工具切换保留这段本机笔记')
            page.get_by_role('button',name='保存个人草稿',exact=True).click()
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            page.get_by_role('button',name='备份与恢复',exact=True).click()
            expect(note).to_be_hidden()
            with page.expect_download() as download:
                page.get_by_role('button',name='下载草稿恢复文件',exact=True).click()
            data=json.loads(download.value.path().read_text())
            assert '工具切换保留这段本机笔记' in json.dumps(data,ensure_ascii=False)
            page.get_by_role('button',name='写笔记',exact=True).click();expect(note).to_have_value('工具切换保留这段本机笔记')
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name='笔记',exact=True).click()
            expect(page.get_by_role('dialog',name='单页工具面板',exact=True)).to_be_visible()
            expect(note).to_have_value('工具切换保留这段本机笔记')
            assert page.locator('.page-tools-panel .studio-tool-title').inner_text()=='笔记'
            page.get_by_role('button',name='备份与恢复',exact=True).click()
            expect(page.get_by_role('button',name='下载草稿恢复文件',exact=True)).to_be_visible()
            page.get_by_role('button',name='回到画面',exact=True).click()
            expect(page.get_by_role('button',name='笔记',exact=True)).to_be_focused()
            page.get_by_role('button',name='图标优化',exact=True).click()
            expect(page.get_by_role('dialog',name='单页工具面板',exact=True)).to_be_visible()
            expect(page.locator('.page-tools-switcher button[aria-pressed=true]')).to_have_text('图标优化')
            page.keyboard.press('Escape')
            expect(page.get_by_role('button',name='图标优化',exact=True)).to_be_focused()
            assert store.current_revision_id()==before and errors==[]
        finally:
            browser.close();server.stop()


@pytest.mark.browser
def test_studio_browser_upload_lost_response_and_partial_selection(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    store=create(tmp_path/'project'); before=store.current_revision_id(); server=WorkbenchServer(store.project_root)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']); page=browser.new_page(viewport={'width':1280,'height':800})
        errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
        uploads=[]
        def lost_response(route):
            uploads.append(route.request.url); response=route.fetch(); assert response.status==200; route.abort()
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='内容与来源',exact=True).click()
            page.get_by_role('button',name='添加材料',exact=True).click()
            picker=page.get_by_label('选择新增材料文件',exact=True); expect(picker).to_be_enabled()
            page.route('**/api/content/uploads?*',lost_response)
            picker.set_input_files({'name':'已接收但回包丢失.md','mimeType':'text/markdown','buffer':b'# received bytes'})
            expect(page.locator('.material-upload-row')).to_contain_text('文件接收结果待核实')
            page.unroute('**/api/content/uploads?*',lost_response)
            page.reload();page.get_by_role('heading',name='内容与来源',exact=True).wait_for()
            page.get_by_role('button',name='添加材料',exact=True).click()
            page.get_by_role('button',name='核实这份材料',exact=True).click()
            expect(page.locator('.material-upload-row')).to_contain_text('文件已接收')
            assert len(uploads)==1 and store.current_revision_id()==before
            picker=page.get_by_label('选择新增材料文件',exact=True)
            picker.set_input_files([{'name':'第二份.md','mimeType':'text/markdown','buffer':b'# second'}, {'name':'不支持.exe','mimeType':'application/octet-stream','buffer':b'not supported'}])
            expect(page.locator('.material-upload-row')).to_have_count(3)
            expect(page.locator('.material-upload-row').nth(1)).to_contain_text('文件已接收')
            expect(page.locator('.material-upload-row').nth(2)).to_contain_text('文件未接收')
            page.get_by_role('button',name='预览材料与任务变化',exact=True).click()
            expect(page.locator('.material-upload-error')).to_be_visible()
            page.locator('.material-upload-row').nth(2).get_by_role('button',name='从本次选择移除',exact=True).click()
            page.get_by_role('textbox',name='本次输入变化说明',exact=True).fill('保留两份真实材料')
            page.get_by_role('button',name='预览材料与任务变化',exact=True).click()
            page.get_by_role('button',name='确认输入并交接判断',exact=True).click()
            page.get_by_role('heading',name='当前任务',exact=True).wait_for()
            assert {item['name'] for item in store.load_document()['sources']}=={'已接收但回包丢失.md','第二份.md'}
            assert errors==[]
        finally:
            browser.close();server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('held_phase', ['receipt', 'upload'])
def test_studio_reload_during_material_upload_can_verify_and_reselect(tmp_path, held_phase):
    from pathlib import Path
    import os
    import time
    from urllib.parse import parse_qs
    from playwright.sync_api import sync_playwright, expect
    store=create(tmp_path/'project');server=WorkbenchServer(store.project_root)
    before=store.current_revision_id();timeline=[];pending=[];errors=[];failure=None
    started=time.monotonic();document_generation=[0]
    def record(kind, **fields):
        timeline.append({'kind':kind,'at_ms':round((time.monotonic()-started)*1000,3),
                         'document_generation':document_generation[0],**fields})
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page()
        page.on('request',lambda req:record('request',method=req.method,url=req.url))
        page.on('response',lambda res:record('response',status=res.status,url=res.url))
        page.on('requestfailed',lambda req:record('request_failed',url=req.url,failure=req.failure))
        page.on('pageerror',lambda err:errors.append(str(err)))
        def navigated(frame):
            if frame==page.main_frame:
                document_generation[0]+=1;record('document_navigated',url=frame.url)
        page.on('framenavigated',navigated)
        pattern='**/api/content/uploads/*' if held_phase=='receipt' else '**/api/content/uploads?*'
        expected_method='GET' if held_phase=='receipt' else 'POST'
        def matches(request):
            path=urlsplit(request.url).path
            return request.method==expected_method and (path.startswith('/api/content/uploads/') if held_phase=='receipt' else path=='/api/content/uploads')
        def hold(route):
            if not matches(route.request):route.continue_();return
            pending.append(route)
            record('target_intercepted',method=route.request.method,url=route.request.url,pending_count=len(pending))
            # A test-only acknowledgement of the actual route callback, not a
            # shared status label or a timing delay. The request remains held.
            page.evaluate('window.__heldMaterialRequest = true')
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='内容与来源',exact=True).click()
            page.get_by_role('button',name='添加材料',exact=True).click()
            picker=page.get_by_label('选择新增材料文件',exact=True);expect(picker).to_be_enabled()
            page.route(pattern,hold)
            file={'name':'未送达材料.md','mimeType':'text/markdown','buffer':b'# exact original'}
            with page.expect_request(matches):picker.set_input_files(file)
            page.wait_for_function('() => window.__heldMaterialRequest === true')
            assert len(pending)==1
            held_url=urlsplit(pending[0].request.url)
            upload_id=held_url.path.rsplit('/',1)[-1] if held_phase=='receipt' else parse_qs(held_url.query)['upload_id'][0]
            expect(page.locator('.material-upload-row')).to_contain_text('正在核实文件')
            record('reload_requested',url=page.url,pending_count=len(pending),upload_id=upload_id)
            page.reload();page.unroute(pattern,hold)
            record('reload_returned',url=page.url,pending_count=len(pending))
            page.get_by_role('heading',name='内容与来源',exact=True).wait_for()
            page.get_by_role('button',name='添加材料',exact=True).click()
            page.get_by_role('button',name='核实这份材料',exact=True).click()
            expect(page.get_by_role('button',name='重新选择原文件',exact=True)).to_be_visible()
            page.get_by_label('选择新增材料文件',exact=True).set_input_files(file)
            expect(page.locator('.material-upload-row')).to_have_count(1)
            expect(page.locator('.material-upload-row')).to_contain_text('文件已接收')
            sent=[event for event in timeline if event['kind']=='request' and event.get('method')=='POST' and urlsplit(event['url']).path=='/api/content/uploads']
            assert sent and all(parse_qs(urlsplit(event['url']).query)['upload_id']==[upload_id] for event in sent)
            send_count=len(sent)
            page.get_by_label('选择新增材料文件',exact=True).set_input_files(file)
            expect(page.locator('.material-upload-row')).to_have_count(1)
            expect(page.locator('.material-uploads')).to_contain_text('这份文件已经接收，本次选择保留一份')
            assert len([event for event in timeline if event['kind']=='request' and event.get('method')=='POST' and urlsplit(event['url']).path=='/api/content/uploads'])==send_count
            assert store.load_document()['sources']==[] and store.current_revision_id()==before
            assert errors==[]
        except Exception as error:
            failure=repr(error)
            raise
        finally:
            if failure:
                # Preserve the initial failure; a later successful run is not a
                # substitute for its navigation, network, and revision evidence.
                evidence=Path(os.environ.get('STUDIO_UPLOAD_EVIDENCE',str(tmp_path/'upload-evidence')))/held_phase
                evidence.mkdir(parents=True,exist_ok=True)
                snapshot={'phase':held_phase,'failure':failure,'url':page.url,'pending_count':len(pending),
                          'before_revision':before,'after_revision':store.current_revision_id(),
                          'document_generation':document_generation[0],'page_errors':errors,'timeline':timeline}
                try:
                    snapshot['body']=page.locator('body').inner_text(timeout=5000)
                    snapshot['main']=page.locator('main').first.inner_text(timeout=5000) if page.locator('main').count() else None
                    (evidence/'document.html').write_text(page.content())
                    page.screenshot(path=str(evidence/'failure.png'),full_page=True,timeout=5000)
                except Exception as diagnostic_error:snapshot['capture_error']=repr(diagnostic_error)
                (evidence/'failure.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
            browser.close();server.stop()

@pytest.mark.browser
def test_studio_browser_real_file_refresh_and_input_commit(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    from deck_master.samples import create_gallery_sample
    path=tmp_path/'project'; create_gallery_sample(path,page_count=30,readonly=False)
    store=Store(path); before=store.current_revision_id(); server=WorkbenchServer(path)
    errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('heading',name='制作总览',exact=True).wait_for()
            page.get_by_role('button',name='内容与来源',exact=True).click()
            page.get_by_role('button',name='添加材料',exact=True).click()
            picker=page.get_by_label('选择新增材料文件',exact=True)
            expect(picker).to_be_enabled()
            picker.set_input_files({'name':'浏览器材料.md','mimeType':'text/markdown','buffer':'# 实际选入\n只能在确认输入后登记。'.encode()})
            expect(page.locator('.material-upload-row')).to_contain_text('文件已接收')
            assert store.current_revision_id()==before
            page.get_by_role('textbox',name='本次输入变化说明',exact=True).fill('添加浏览器材料用于当前论证')
            page.reload()
            page.get_by_role('heading',name='内容与来源',exact=True).wait_for()
            page.get_by_role('button',name='添加材料',exact=True).click()
            expect(page.locator('.material-upload-row')).to_contain_text('浏览器材料.md')
            expect(page.get_by_role('textbox',name='本次输入变化说明',exact=True)).to_have_value('添加浏览器材料用于当前论证')
            page.get_by_role('button',name='预览材料与任务变化',exact=True).click()
            expect(page.locator('.material-input-impact')).to_contain_text('新增材料：浏览器材料.md')
            page.get_by_role('button',name='确认输入并交接判断',exact=True).click()
            page.get_by_role('heading',name='当前任务',exact=True).wait_for()
            expect(page.get_by_role('button',name='交接这项内容整理',exact=True)).to_be_visible()
            current=store.load_document()
            assert current['revision_id']!=before
            source=next(s for s in current['sources'] if s['name']=='浏览器材料.md')
            assert '只能在确认输入后登记' in store.read_object_json(source['extract'])['text']
            assert any(store.read_object_json(ref)['status']=='awaiting_host' for ref in current['tasks'])
            assert errors==[]
        finally:
            browser.close(); server.stop()
