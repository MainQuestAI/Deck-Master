"""Current product screenshots and control semantics from isolated synthetic bytes."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode

import pytest
from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer

pytestmark=pytest.mark.browser


def test_ui_refactor_three_surfaces_and_editor_states(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    project=tmp_path/'screens';create_gallery_sample(project,page_count=30,readonly=False)
    from deck_master.store import Store
    from test_studio_content_browser import authorize_content_edits
    from test_content_ops import commit,value
    authorize_content_edits(project);store=Store(project)
    visible=store.read_object_json(store.load_document()['pages'][1]['page'])['customer_visible']
    visible['body_blocks']=[{'id':'flow','type':'paragraph','text':'材料先进入可追溯的来源清单，再转化为章节目标和逐页稿。每次调整保留所用材料版本，便于核对文字、数字与适用范围。'}, {'id':'steps','type':'bullets','heading':'从来源到稿件','items':[{'id':'a','text':'登记材料：记录原始文件及其固定版本。'},{'id':'b','text':'梳理内容：明确每页回答的问题和引用依据。'},{'id':'c','text':'核对变化：先看具体差异，再确认受影响的页面。'}]}]
    commit(project,store,value(store,ids=('p02',),customer_visible=visible))
    server=WorkbenchServer(project)
    out=Path(os.environ.get('UI_REFACTOR_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True)
    metrics=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page();errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            base=server.start();info=page.request.get(base+'api/project').json()
            def visit(surface,**extra):
                page.goto(base+'studio/#'+urlencode({'project':info['project_identity'],'surface':surface,'layer':'content','revision':info['revision_id'],**extra}))
                expect(page.locator('#view-title')).to_contain_text({'overview':'制作总览','content':'内容与页序','page':'第 2 页','gallery':'整稿画廊','style':'风格校准','runs':'任务与交付'}[surface])
                expect(page.locator('.navigation-status')).to_be_hidden()
            def record(name,width):
                page.evaluate('async()=>{await document.fonts.ready;scrollTo(0,0)}')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name
                assert page.locator('main').evaluate('root=>{const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;while(node=walk.nextNode())if(["false","true","[object Object]"].includes(node.textContent.trim()))return false;return true}'),name
                if name=='overview':page.locator('.matrix-thumbnail [data-image-state=ready]').first.wait_for()
                controls=page.locator('main button:visible').evaluate_all('nodes=>nodes.map(n=>{const s=getComputedStyle(n);return {label:n.getAttribute("aria-label")||n.textContent,font:s.fontSize,line:s.lineHeight,height:n.getBoundingClientRect().height,primary:n.classList.contains("primary")}})')
                metrics.append({'screen':name,'width':width,'controls':controls})
                assert len([row for row in controls if row['primary']])<=1,(name,controls)
                page.screenshot(path=str(out/f'{name}-{width}.png'))
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                visit('overview');record('overview',width)
                visit('content');expect(page.locator('.studio-content-adjust')).to_be_hidden();record('content',width)
                page.locator('.content-order-row').nth(1).get_by_role('checkbox').check()
                expect(page.locator('.studio-content-adjust')).to_be_visible()
                page.locator('.content-order-row').nth(1).get_by_role('checkbox').uncheck()
                visit('page',page='p02');record('page',width)
                page.get_by_role('button',name='编辑本页标题与正文',exact=True).click()
                drawer=page.get_by_role('dialog',name='编辑本页标题与正文',exact=True)
                expect(drawer).to_be_visible()
                field=drawer.get_by_role('textbox',name='页面标题',exact=True)
                assert field.evaluate('n=>getComputedStyle(n).fontSize')=='14px'
                page.screenshot(path=str(out/f'editor-{width}.png'))
                page.keyboard.press('Escape')
                expect(page.get_by_role('button',name='编辑本页标题与正文',exact=True)).to_be_focused()
                for surface in ['gallery','style','runs']:
                    visit(surface);record(surface,width)
            assert not errors
            (out/'computed-controls.json').write_text(json.dumps({'metrics':metrics,'errors':errors},ensure_ascii=False,indent=2)+'\n')
        finally:browser.close();server.stop()


def test_launcher_empty_single_thirty_long_names_and_missing_location(tmp_path):
    import threading
    from deck_master import local_runtime,registry,service
    from playwright.sync_api import sync_playwright,expect
    reg=tmp_path/'projects.json';desc=local_runtime.descriptor(registry=reg)
    server,state=local_runtime.bind_server(desc);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    out=Path(os.environ.get('UI_REFACTOR_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True)
    try:
        with sync_playwright() as runtime:
            browser=runtime.chromium.launch();page=browser.new_page();projects=[]
            try:
                for count in [0,1,30]:
                    for index in range(len(projects),count):
                        project=tmp_path/f'project-{index:02}'
                        service.create(project,brief='Synthetic launcher verification',title=f'{index:02} · '+('跨团队内容规划与固定版本审查 ' * 8),audience='验证者',project_format='workbench.v3')
                        registry.register(reg,project);projects.append(project)
                    page.goto(state['url']);expect(page.locator('.project-card')).to_have_count(count)
                    expect(page.get_by_role('button',name='新建项目',exact=True)).to_be_visible()
                    if count:
                        first=page.locator('.project-card').first
                        expect(first.get_by_role('heading')).to_contain_text('跨团队内容规划')
                        expect(first.get_by_role('button',name='打开项目',exact=True)).to_be_enabled()
                        expect(first.get_by_role('button',name='从列表移除',exact=True)).to_have_count(0)
                    for width,height in [(1440,900),(1280,800),(390,844)]:
                        page.set_viewport_size({'width':width,'height':height});page.evaluate('scrollTo(0,0)')
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        page.screenshot(path=str(out/f'launcher-{count}-{width}.png'))
                projects[-1].rename(tmp_path/'relocated-project')
                page.reload();row=page.locator('.project-card').filter(has_text='位置不可用')
                expect(row).to_have_count(1)
                expect(row.get_by_role('button',name='打开项目',exact=True)).to_be_disabled()
                row.get_by_text('保存位置',exact=True).click()
                expect(row.locator('.path')).to_contain_text('project-29')
            finally:browser.close()
    finally:server.shutdown();server.server_close();thread.join(timeout=3)
