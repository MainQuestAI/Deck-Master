"""Mounted single-page image reading: intrinsic pixels, fit, fullscreen, fixed basis."""
import json
import os
import copy
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
import pytest
from deck_master.web import WorkbenchServer
from deck_master.models import bump_revision
from test_icon_quality import icon_store

pytestmark=pytest.mark.browser

@pytest.fixture
def reading_store(icon_store):
    # The normal icon fixture intentionally has a viewBox without pixel width.
    # Give this image an explicit intrinsic size so 100% has a known pixel oracle.
    store=icon_store;before=store.load_document();doc=copy.deepcopy(before)
    entry=doc['pages'][0];artifact=store.read_object_json(entry['svg'])
    root=ET.fromstring(store.read_object_bytes(artifact['file']))
    root.set('width','960');root.set('height','540')
    artifact['file']=store.put_blob(ET.tostring(root),ext='svg');entry['svg']=store.put_json_object(artifact)
    doc=bump_revision(doc,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'synthetic intrinsic image dimensions','read_set':[]})
    store.commit_change(base_revision=before['revision_id'],document=doc,operation_id=doc['change']['operation_id'])
    return store

@pytest.mark.parametrize('size',[(1440,900),(1280,800),(390,844)])
def test_single_page_native_fit_fullscreen_keeps_basis_and_draft(reading_store,size,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    store=reading_store;before=store.load_document();server=WorkbenchServer(store.project_root)
    out=Path(os.environ.get('DECK_MASTER_BROWSER_EVIDENCE',str(tmp_path/'evidence')))/'page-reading';out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':size[0],'height':size[1]});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            base=server.start();identity=page.request.get(base+'api/project').json()['project_identity']
            url=base+'studio/#'+urlencode({'project':identity,'surface':'page','page':'p01','layer':'svg','revision':before['revision_id'],'zoom':1.5})
            page.goto(url);canvas=page.locator('.studio-page-reading canvas.page-image');expect(canvas).to_be_visible()
            controls=page.get_by_role('group',name='单页图稿阅读');viewport=page.locator('.studio-page-reading .page-image-viewport')
            expect(viewport).to_have_attribute('data-reading-mode','legacy')
            expect(controls).to_contain_text('已恢复版面比例 150%')
            # A real note remains mounted while image tools change view state.
            note_tool=page.get_by_role('group',name='单页工具').get_by_role('button',name='笔记',exact=True);note_tool.click()
            note=page.get_by_label('个人草稿',exact=True);note.fill('W06 固定页面草稿，不因全屏或阅读倍率改变')
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            if size[0]<1280:page.get_by_role('dialog',name='单页工具面板').get_by_role('button',name='回到画面',exact=True).click()
            if size[0]==390: controls.get_by_role('button',name='缩放',exact=False).click()
            zoom_scope=page.get_by_role('dialog',name='图稿缩放') if size[0]==390 else controls
            native=zoom_scope.get_by_role('button',name='原生 100% 阅读',exact=True);native.click()
            expect(viewport).to_have_attribute('data-reading-mode','native')
            intrinsic=canvas.evaluate('e=>({width:e.width,height:e.height,box:e.getBoundingClientRect().toJSON()})')
            assert intrinsic['width']==960 and intrinsic['height']==540
            assert intrinsic['box']['width']==960 and intrinsic['box']['height']==540
            for control in zoom_scope.get_by_role('button').all():assert control.bounding_box()['height']>=(44 if size[0]<=560 else 32)
            if size[0]==390: zoom_scope.get_by_role('button',name='关闭',exact=True).click()
            if size[0]==1440:
                for width,height in [(1280,800),(390,844),(1440,900)]:
                    page.set_viewport_size({'width':width,'height':height})
                    expect(viewport).to_have_attribute('data-reading-mode','native')
                    assert canvas.bounding_box()['width']==960 and canvas.bounding_box()['height']==540
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert parse_qs(urlparse(page.url).fragment)==parse_qs(urlparse(url).fragment)
            overlay=page.locator('.studio-page-reading .annotation-overlay')
            expect(overlay).to_be_attached()
            assert abs(overlay.bounding_box()['width']-960)<1
            if size[0]==390: controls.get_by_role('button',name='缩放',exact=False).click()
            zoom_scope=page.get_by_role('dialog',name='图稿缩放') if size[0]==390 else controls
            zoom_scope.get_by_role('button',name='放大图稿',exact=True).click()
            assert canvas.bounding_box()['width']==1200
            zoom_scope.get_by_role('button',name='缩小图稿',exact=True).click()
            assert canvas.bounding_box()['width']==960
            if size[0]==390: zoom_scope.get_by_role('button',name='关闭',exact=True).click()
            controls.get_by_role('button',name='适应窗口',exact=True).click()
            expect(viewport).to_have_attribute('data-reading-mode','fit')
            fitted=viewport.evaluate('e=>{const c=e.querySelector("canvas"),s=getComputedStyle(e);return {width:e.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight),height:e.clientHeight-parseFloat(s.paddingTop)-parseFloat(s.paddingBottom),canvas:c.getBoundingClientRect().toJSON()}}')
            assert fitted['canvas']['width']<=fitted['width']+1 and fitted['canvas']['height']<=fitted['height']+1
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(out/f'fit-{size[0]}.png'))
            enter=controls.get_by_role('button',name='全屏阅读',exact=True);enter.click()
            page.wait_for_function('()=>document.fullscreenElement?.classList.contains("studio-page-reading")')
            exit=controls.get_by_role('button',name='退出全屏',exact=True);expect(exit).to_be_visible()
            expect(page.locator('.studio-reading-identity')).to_contain_text('第 1 页')
            expect(page.locator('.studio-reading-identity')).to_contain_text(before['revision_id'][:8])
            page.wait_for_function('()=>{const c=document.querySelector(".studio-page-reading canvas").getBoundingClientRect();return c.top>=0&&c.bottom<=innerHeight}')
            page.screenshot(path=str(out/f'fullscreen-{size[0]}.png'))
            exit.click();page.wait_for_function('()=>!document.fullscreenElement');expect(enter).to_be_focused()
            assert parse_qs(urlparse(page.url).fragment)==parse_qs(urlparse(url).fragment)
            enter.click();page.wait_for_function('()=>!!document.fullscreenElement');page.keyboard.press('Escape')
            page.wait_for_function('()=>!document.fullscreenElement');expect(enter).to_be_focused();assert parse_qs(urlparse(page.url).fragment)==parse_qs(urlparse(url).fragment)
            note_tool.click();expect(note).to_have_value('W06 固定页面草稿，不因全屏或阅读倍率改变')
            if size[0]<1280:page.get_by_role('dialog',name='单页工具面板').get_by_role('button',name='回到画面',exact=True).click()
            # Existing saved zoom URL keeps its old container-multiplier semantics.
            page.reload();expect(page.locator('.studio-page-reading .page-image-viewport')).to_have_attribute('data-reading-mode','legacy')
            expect(page.get_by_role('group',name='单页图稿阅读')).to_contain_text('已恢复版面比例 150%')
            if size[0]==390: page.get_by_role('button',name='阅读设置',exact=True).click()
            page.get_by_role('button',name='回到整稿画廊',exact=True).click();expect(page.get_by_role('heading',name='整稿画廊',exact=True)).to_be_visible()
            assert store.load_document()==before and errors==[]
            (out/f'result-{size[0]}.json').write_text(json.dumps({'passed':True,'viewport':size,'native':intrinsic,'fit':fitted,'fixed_revision':before['revision_id'],'business_unchanged':True,'errors':errors},ensure_ascii=False,indent=2))
        finally:browser.close();server.stop()

def test_single_page_unreadable_image_retries_without_empty_reading_controls(reading_store):
    from playwright.sync_api import sync_playwright,expect
    store=reading_store;before=store.load_document();server=WorkbenchServer(store.project_root)
    ref=store.read_object_json(before['pages'][0]['svg'])['file'];fail=[True]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            def image(route):
                if ref['sha256'] in route.request.url and fail[0]:route.fulfill(status=503,body='unavailable')
                else:route.continue_()
            page.route('**/api/file?*',image)
            base=server.start();identity=page.request.get(base+'api/project').json()['project_identity']
            page.goto(base+'studio/#'+urlencode({'project':identity,'surface':'page','page':'p01','layer':'svg','revision':before['revision_id']}))
            controls=page.get_by_role('group',name='单页图稿阅读')
            expect(controls).to_contain_text('图片暂不可读')
            for control in controls.get_by_role('button').all():expect(control).to_be_disabled()
            fail[0]=False;page.get_by_role('button',name='重试图片',exact=True).click()
            expect(controls.get_by_role('button',name='原生 100% 阅读',exact=True)).to_be_enabled()
            controls.get_by_role('button',name='原生 100% 阅读',exact=True).click()
            assert page.locator('.studio-page-reading canvas').bounding_box()['width']==960
            # PPT is actually absent in this fixture. No perpetual "loading" toolbar.
            page.get_by_role('button',name='06 PPT 预览，尚未生成',exact=True).click()
            expect(page.get_by_role('heading',name='PPT未生成',exact=True)).to_be_visible()
            expect(page.get_by_role('group',name='单页图稿阅读')).to_have_count(0)
            assert store.load_document()==before and errors==[]
        finally:browser.close();server.stop()
