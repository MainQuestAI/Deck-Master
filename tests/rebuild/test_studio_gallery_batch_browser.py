"""Gallery selection hands off to the existing fixed-revision batch transaction."""
import json
import os
import uuid
from pathlib import Path

import pytest
from deck_master import service, gallery_state
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark=pytest.mark.browser


@pytest.mark.parametrize('action',['blueprint','reconstruct','repair','style'])
def test_gallery_selected_pages_enter_real_batch_without_reselection(tmp_path,action):
    from playwright.sync_api import sync_playwright,expect
    project=tmp_path/'project';create_sample(project,page_count=30,readonly=False);store=Store(project)
    revision=store.current_revision_id();before=store.read_current();server=WorkbenchServer(project);calls=[];errors=[]
    out=Path(os.environ.get('DECK_MASTER_BROWSER_EVIDENCE',str(tmp_path/'evidence')))/'gallery-batch'/action;out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:calls.append(request.post_data_json) if request.method=='POST' and '/api/changes/' in request.url else None)
        try:
            page.goto(server.start());page.get_by_role('button',name='整稿画廊',exact=True).click()
            tool=page.locator('.studio-gallery-production');expect(tool).to_be_hidden()
            search=page.get_by_role('textbox',name='搜索页面',exact=True)
            for page_id in ('p02','p06','p12','p22','p28'):
                search.fill(page_id[1:]);page.locator(f'.slide-tile[data-page-id="{page_id}"]').get_by_role('checkbox').check()
            expect(tool.locator('button')).to_have_count(4);expect(tool).to_contain_text('已选 5 页');expect(page.locator('.gallery-legend')).to_contain_text('筛选外选中 4 页')
            expect(page.get_by_role('button',name='并排比较',exact=True)).to_be_disabled()
            if action=='blueprint':page.screenshot(path=str(out/'gallery-selection-1440.png'),full_page=True)
            tool.locator(f'[data-gallery-action="{action}"]').click()
            expect(page.get_by_role('heading',name='制作总览',exact=True)).to_be_visible()
            batch=page.locator('.batch-actions');expect(batch).to_have_attribute('data-selection','selected')
            expect(page.locator(f'[data-batch-action="{action}"]')).to_have_attribute('aria-pressed','true')
            expect(batch).to_contain_text('5 页用于')
            assert f'revision={revision}' in page.url
            expect(page.locator('.overview-selection-summary')).to_contain_text('已选 5 页')
            page.reload();expect(page.locator(f'[data-batch-action="{action}"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('.overview-selection-summary')).to_contain_text('已选 5 页')
            assert 'batchPages=' not in page.url and store.read_current()==before
            batch=page.locator('.batch-actions')
            if action=='repair':
                expect(batch).to_contain_text('没有可修复的 SVG')
                expect(batch.get_by_role('button',name='预览所选页试作',exact=True)).to_be_disabled()
                expect(batch).to_contain_text('未自动忽略任何页')
                assert calls==[]
            elif action=='style':
                batch.get_by_role('button',name='带所选页进入风格校准',exact=True).click()
                expect(page.get_by_role('heading',name='风格校准',exact=True)).to_be_visible()
                chosen = page.locator('.style-targets input[type=checkbox]:checked')
                expect(chosen).to_have_count(5)
                assert all(any(f'第 {n} 页' in label for label in chosen.evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("aria-label"))')) for n in (2,6,12,22,28))
                assert calls==[]
            else:
                batch.get_by_role('textbox',name='所选页的制作要求').fill('只修改明确选中的第2、6、12、22和28页；其它页不变。')
                if action=='blueprint':batch.get_by_role('button',name='按所选页设置调用上限',exact=True).click()
                with page.expect_request('**/api/changes/plan') as plan:
                    batch.get_by_role('button',name='预览所选页试作',exact=True).click()
                payload=plan.value.post_data_json['input']
                assert payload['base_revision']==revision
                assert [target['page_id'] for target in payload['targets']]==['p02','p06','p12','p22','p28']
                assert {target['stage'] for target in payload['targets']}=={action}
                expect(batch.get_by_role('button',name='保存并交接所选试作',exact=True)).to_be_enabled()
                assert store.read_current()==before
                if action=='blueprint':
                    page.screenshot(path=str(out/'overview-config-1440.png'),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    page.screenshot(path=str(out/'overview-config-390.png'),full_page=True)
            assert errors==[]
            (out/f'{action}.json').write_text(json.dumps({'revision':revision,'calls':calls,'errors':errors,'after':store.current_revision_id()},ensure_ascii=False,indent=2))
        finally:browser.close();server.stop()


def test_gallery_production_is_readonly_for_history(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    project=tmp_path/'project';create_sample(project,page_count=3,readonly=False);store=Store(project)
    old=store.current_revision_id()
    service.inputs_update(project,patch={'reason':'new inputs','task_patch':{'audience':'new audience'}},base_revision=old,operation_id=str(uuid.uuid4()))
    server=WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page()
        try:
            page.goto(server.start());page.get_by_role('button',name='整稿画廊',exact=True).click()
            page.goto(page.url.replace(store.current_revision_id(),old))
            page.locator('.slide-tile[data-page-id="p01"]').get_by_role('checkbox').check()
            buttons=page.get_by_role('group',name='画廊选页制作').locator('button');expect(buttons).to_have_count(4)
            for button in buttons.all():expect(button).to_be_disabled()
            assert store.current_revision_id()!=old
        finally:browser.close();server.stop()


def test_gallery_large_selection_persists_but_comparison_stays_two_to_four(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    project=tmp_path/'project';create_sample(project,page_count=5,readonly=False);store=Store(project);before=store.read_current();server=WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900})
        try:
            page.goto(server.start());page.get_by_role('button',name='整稿画廊',exact=True).click()
            search=page.get_by_role('textbox',name='搜索页面',exact=True)
            for n in range(1,6):
                search.fill(f'{n:02}');page.locator(f'.slide-tile[data-page-id="p{n:02}"]').get_by_role('checkbox').check()
            expect(page.get_by_role('group',name='画廊选页制作')).to_contain_text('已选 5 页')
            expect(page.get_by_role('button',name='并排比较',exact=True)).to_be_disabled()
            expect(page.locator('.gallery-save')).to_contain_text('画廊选择已保存')
            saved=gallery_state.get(project)['record'];assert len(saved['state']['selected_page_ids'])==5
            page.reload();expect(page.get_by_role('group',name='画廊选页制作')).to_contain_text('已选 5 页')
            search=page.get_by_role('textbox',name='搜索页面',exact=True)
            for n in (4,5):
                search.fill(f'{n:02}');page.locator(f'.slide-tile[data-page-id="p{n:02}"]').get_by_role('checkbox').uncheck()
            page.get_by_role('button',name='并排比较',exact=True).click()
            expect(page.locator('.gallery.is-comparison .slide-tile')).to_have_count(3)
            expect(page.locator('.gallery-save')).to_contain_text('画廊选择已保存')
            saved=gallery_state.get(project)['record'];assert saved['state']['mode']=='compare' and saved['state']['selected_page_ids']==['p01','p02','p03']
            assert store.read_current()==before
        finally:browser.close();server.stop()
