"""Studio page tools use original icon transactions; no Host/model invocation."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
import pytest
from deck_master import icons
from deck_master.web import WorkbenchServer
from test_icon_quality import icon_store, input_for

pytestmark=pytest.mark.browser


def test_studio_icon_cards_catalog_scope_dispatch_and_tool_focus(icon_store,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    store=icon_store;before=store.load_document();server=WorkbenchServer(store.project_root)
    out=Path(os.environ.get('STUDIO_PAGE_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            url=server.start();info=page.request.get(url+'api/project').json()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p01','layer':'svg','revision':before['revision_id']}))
            tool=page.get_by_role('button',name='图标优化',exact=True);tool.click()
            standard=page.get_by_role('button',name=re.compile('^标准替换'))
            expect(standard).to_be_enabled();standard.click()
            catalog=page.get_by_role('group',name='标准图标目录',exact=True)
            expect(catalog).to_be_visible()
            item=page.get_by_role('button',name='选用标准图标 流程',exact=True)
            # Labels and pictures come from the packaged manifest, never guessed placeholders.
            manifest=page.request.get(url+'api/icons/catalog').json()
            expected=next(x for x in manifest['icons'] if x['id']=='workflow')
            item=page.get_by_role('button',name='选用标准图标 '+expected['label'],exact=True)
            expect(item).to_be_enabled();item.click();expect(item).to_have_attribute('aria-pressed','true')
            expect(item.locator('img')).to_be_visible()
            src=item.locator('img').get_attribute('src');assert expected['sha256'] in src
            response=page.request.get(url.rstrip('/')+src);assert response.ok and b'<svg' in response.body()
            expect(page.locator('.studio-icon-reuse')).to_be_hidden()
            assert not page.locator('.icon-workbench select:visible').count()
            page.get_by_role('button',name=re.compile('^忠实重绘')).click();expect(catalog).to_be_hidden()
            standard.click();expect(item).to_have_attribute('aria-pressed','true')
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                if width<1280:tool.click()
                expect(catalog).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('.studio-icon-methods button').evaluate_all('(nodes)=>nodes.every(n=>n.getBoundingClientRect().height>=44)')
                page.screenshot(path=str(out/f'icon-cards-{width}.png'),full_page=True)
                if width<1280:
                    page.keyboard.press('Escape');expect(tool).to_be_focused()
            page.set_viewport_size({'width':1440,'height':900})
            # Explicit synthetic Agent proposal exercises the real comparison and commit UI.
            proposal=icons.propose(store.project_root,input=input_for(store,method='standard'))
            page.get_by_role('button',name='刷新图标方案',exact=True).click()
            page.get_by_role('button',name='查看 p01 的图标范围',exact=True).click()
            expect(page.locator('.icon-comparison canvas').first).to_be_visible()
            page.screenshot(path=str(out/'icon-scope-comparison.png'),full_page=True)
            page.keyboard.press('Escape')
            page.get_by_role('button',name='确认这些图标范围和处理方式',exact=True).click()
            page.get_by_label('选入图标页 p01',exact=True).check()
            page.get_by_role('button',name='预览选中页图标试作',exact=True).click()
            page.get_by_role('button',name='确认计划并交接图标修复',exact=True).click()
            expect(page.get_by_role('heading',name='当前任务',exact=True)).to_be_visible()
            after=store.load_document();icon_tasks=[store.read_object_json(ref) for ref in after['tasks'] if store.read_object_json(ref).get('stage_request',{}).get('icon_recipe_ref')]
            assert len(icon_tasks)==1 and 'icon_repair' in icon_tasks[0]['required_capabilities']
            assert before['pages']==after['pages'] and before['outputs']==after['outputs'] and errors==[]
            (out/'result.json').write_text(json.dumps({'proposal':proposal,'tasks':icon_tasks,'errors':errors},ensure_ascii=False,indent=2))
        finally:
            page.screenshot(path=str(out/'last-state.png'),full_page=True);browser.close();server.stop()


@pytest.mark.parametrize('missing_original',[False,True])
def test_studio_icon_missing_layer_continues_exact_page_without_dispatch(tmp_path,missing_original):
    import copy
    import uuid
    from deck_master.samples import create_sample
    from deck_master.store import Store
    from deck_master.models import bump_revision
    from playwright.sync_api import sync_playwright,expect
    project=tmp_path/'project';create_sample(project,page_count=3,readonly=False);store=Store(project)
    if missing_original:
        before=store.load_document();changed=copy.deepcopy(before);changed['pages'][1]['blueprint']=None
        changed=bump_revision(changed,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'test missing original','read_set':[]})
        store.commit_change(base_revision=before['revision_id'],document=changed,operation_id=changed['change']['operation_id'])
    before=store.read_current();revision=store.current_revision_id();server=WorkbenchServer(project)
    out=Path('output/opendesign-completion/icon-continuation');out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900});writes=[]
        page.on('request',lambda req:writes.append(req.url) if req.method=='POST' and '/api/changes/' in req.url else None)
        try:
            url=server.start();info=page.request.get(url+'api/project').json()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p02','layer':'svg','revision':revision}))
            page.get_by_role('button',name='图标优化',exact=True).click()
            area=page.get_by_role('region',name='继续制作图层')
            expect(area).to_be_visible();expect(area).to_contain_text('原图' if missing_original else 'SVG')
            # No configuration is presented until its real prerequisite exists.
            expect(page.get_by_role('group',name='图标处理方式',exact=True)).to_have_count(0)
            page.screenshot(path=str(out/f'missing-{missing_original}-1440.png'),full_page=True)
            area.get_by_role('button',name='制作本页原图' if missing_original else '制作本页 SVG',exact=True).click()
            expect(page.get_by_role('heading',name='制作总览',exact=True)).to_be_visible()
            action='blueprint' if missing_original else 'reconstruct'
            expect(page.locator(f'[data-batch-action="{action}"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('.overview-selection-summary')).to_contain_text('已选 1 页')
            assert f'revision={revision}' in page.url
            assert page.locator('.matrix tbody input[type=checkbox]:checked').count()==1
            assert page.locator('.matrix tbody tr').filter(has=page.locator('input[type=checkbox]:checked')).inner_text().find('02')>=0
            page.reload();expect(page.locator('.overview-selection-summary')).to_contain_text('已选 1 页')
            assert store.read_current()==before and writes==[]
            # A historical reading cannot navigate to a new production request.
            from deck_master import service
            service.inputs_update(project,patch={'reason':'new current inputs','task_patch':{'audience':'updated audience'}},base_revision=revision,operation_id=str(uuid.uuid4()))
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p02','layer':'svg','revision':revision}))
            page.get_by_role('button',name='图标优化',exact=True).click()
            expect(page.get_by_role('region',name='继续制作图层').get_by_role('button')).to_be_disabled()
            assert writes==[]
        finally:browser.close();server.stop()
