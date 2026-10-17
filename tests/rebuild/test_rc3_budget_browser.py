"""Actual HTTP/UI budget preview and explicit grant; synthetic L1, no tools."""
import shutil

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master.web import WorkbenchServer
from test_rc3_budget_workflow import project


@pytest.mark.browser
@pytest.mark.parametrize('width,height',[(1440,900),(390,844)])
def test_budget_preview_and_normal_grant_keep_scope_and_per_page_credits(tmp_path,width,height):
    path, store = project(tmp_path)
    before = store.load_document()
    server = WorkbenchServer(path)
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':width,'height':height})
        page.on('pageerror',lambda error: errors.append(str(error)))
        try:
            page.goto(server.start())
            page.get_by_role('button',name='查看本次工作与范围',exact=True).click()
            page.get_by_role('button',name='查看制作预算',exact=True).click()
            dialog = page.get_by_role('dialog',name='记录制作预算')
            expect(dialog).to_contain_text('选定 2 页，复用 0 页，首次生成最多 2 次')
            assert store.load_document() == before
            confirm = dialog.get_by_role('button',name='确认记录制作预算',exact=True)
            expect(confirm).to_be_enabled()
            confirm.click()
            assert store.load_document() == before
            dialog.get_by_label('本次明确要求（必填）').fill('Synthetic explicit instruction: produce the fixed two-page deck once; retain all policy and existing costs.')
            confirm.click()
            expect(dialog).to_contain_text('请求已记录')
            current = store.load_document()
            record = store.read_object_json(current['collaboration']['authorizations'][-1])
            assert record['max_external_calls'] == 2
            assert record['adoption_policy'] == 'within_scope'
            assert record['scope']['page_ids'] == ['p1','p2']
            assert len(record['constraints']['fixed_budget']['credits']) == 2
            assert current['policy'] == before['policy']
            assert current['pages'] == before['pages'] and current['tasks'] == before['tasks']
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert errors == []
        finally:
            browser.close()
            server.stop()


@pytest.mark.browser
def test_edit_preview_passes_real_immutable_plan_to_budget_without_manual_id(tmp_path):
    path, store = project(tmp_path,intent='edit')
    before = store.load_document()
    server = WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':900})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(server.start())
            page.get_by_role('checkbox',name='选择第 01 页',exact=True).check()
            page.get_by_role('checkbox',name='选择第 02 页',exact=True).check()
            page.get_by_role('textbox',name='所选页的制作要求',exact=True).fill('Synthetic explicit edit: keep facts, redraw these two fixed pages once and return usable images.')
            page.get_by_role('button',name='按所选页设置调用上限',exact=True).click()
            with page.expect_response(lambda response:response.url.endswith('/api/changes/plan')) as planned:
                page.get_by_role('button',name='预览所选页试作',exact=True).click()
            fixed=planned.value.json()
            page.get_by_role('button',name='查看这次修改的制作预算',exact=True).click()
            dialog=page.get_by_role('dialog',name='记录制作预算')
            expect(dialog).to_contain_text('使用刚才修改影响预览的固定方案')
            expect(dialog).to_contain_text('必须重画 2 页')
            assert dialog.get_by_role('textbox').count() == 1  # Explicit instruction only; no internal ID field.
            assert store.load_document() == before
            dialog.get_by_label('本次明确要求（必填）').fill('Synthetic explicit two-page usable-image edit, candidate comparison first, no automatic adoption.')
            dialog.get_by_role('button',name='确认记录制作预算',exact=True).click()
            expect(dialog).to_contain_text('请求已记录')
            doc=store.load_document();record=store.read_object_json(doc['collaboration']['authorizations'][-1])
            assert record['constraints']['fixed_budget']['change_plan_ref'] == fixed['plan_ref']
            assert record['max_external_calls'] == record['max_candidate_count'] == 2
            assert record['adoption_policy'] == 'candidate_only'
            assert doc['pages'] == before['pages'] and doc['tasks'] == before['tasks']
            expect(dialog).to_contain_text('比较候选上限 2 个')
            dialog.get_by_role('button',name='读取当前版本并重新预览修改',exact=True).click()
            # The fixed current-version navigation remounts the work surface.
            # Wait for that user-visible cycle before setting its new call bound.
            expect(page.locator('#main')).not_to_have_attribute('aria-busy','true')
            try:
                expect(page.get_by_role('spinbutton',name='批量图像调用上限')).to_have_value('0')
            except AssertionError:
                (tmp_path/'budget-navigation-diagnostic.txt').write_text(page.locator('body').inner_text()+'\nPAGE ERRORS: '+repr(errors))
                raise
            page.get_by_role('checkbox',name='选择第 01 页',exact=True).check()
            page.get_by_role('checkbox',name='选择第 02 页',exact=True).check()
            expect(page.get_by_role('textbox',name='所选页的制作要求',exact=True)).to_have_value('Synthetic explicit edit: keep facts, redraw these two fixed pages once and return usable images.')
            page.get_by_role('button',name='按所选页设置调用上限',exact=True).click()
            page.get_by_role('button',name='预览所选页试作',exact=True).click()
            page.get_by_role('heading',name='确认本次范围',exact=True).wait_for()
            page.get_by_role('button',name='保存并交接所选试作',exact=True).click()
            expect(page.locator('.batch-actions')).to_contain_text('已保存 2 项待交接任务，尚未开始制作')
            current=store.load_document()
            added=[store.read_object_json(ref) for ref in current['tasks'] if ref not in before['tasks']]
            assert len(added)==2 and all(task['status']=='awaiting_host' for task in added)
            assert {task['collaboration_binding']['budget_key'] for task in added} == {
                record['request_id']+':rebuild:p1',record['request_id']+':rebuild:p2'}
            assert all(task['collaboration_binding']['adoption_policy']=='candidate_only' for task in added)
            assert all(not task.get('generation_attempts') for task in added)
            assert current['pages']==before['pages']
            assert errors == []
        finally:
            browser.close();server.stop()
