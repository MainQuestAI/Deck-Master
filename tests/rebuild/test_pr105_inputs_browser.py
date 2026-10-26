"""Late receipts and natural polling must preserve later user choices."""
import uuid
import pytest
from deck_master import service
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_studio_delivery_browser import task_set

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('choice', ['keep', 'remove'])
@pytest.mark.parametrize('verify', [False, True])
def test_upload_receipt_preserves_material_action(tmp_path, choice, verify):
    from playwright.sync_api import sync_playwright, expect
    source = tmp_path/'original.md'
    source.write_text('# Original material')
    path = tmp_path/'project'
    service.create(path, brief='Test material receipt', sources=[source], project_format='workbench.v3')
    server = WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        held = []
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='内容与页序',exact=True).click()
            page.get_by_role('button',name='材料与来源',exact=True).click()
            page.get_by_role('button',name='调整此材料 · original.md',exact=True).click()
            if verify:
                page.route('**/api/content/uploads?*', lambda route: (route.fetch(), route.abort()))
            else:
                page.route('**/api/content/uploads?*', lambda route: held.append((route, route.fetch())))
            page.get_by_label('选择替换材料文件',exact=True).set_input_files({'name':'new.md','mimeType':'text/markdown','buffer':b'# New material'})
            if verify:
                expect(page.locator('.material-upload-row')).to_contain_text('文件接收结果待核实')
                page.route('**/api/content/uploads/*', lambda route: held.append((route, route.fetch())))
                page.get_by_role('button',name='核实这份材料',exact=True).click()
            expect(page.get_by_label('材料操作 original.md')).to_have_value('replace')
            page.get_by_label('材料操作 original.md').select_option(choice)
            for _ in range(50):
                if held: break
                page.wait_for_timeout(100)
            assert held
            route, response = held.pop()
            route.fulfill(response=response)
            expect(page.locator('.material-upload-row')).to_contain_text('文件已接收')
            expect(page.get_by_label('材料操作 original.md')).to_have_value(choice)
            page.get_by_label('本次输入变化说明',exact=True).fill('保留用户最后选择')
            page.get_by_label('材料用途 original.md',exact=True).fill('更新用途以核对提交')
            page.get_by_role('button',name='预览材料与任务变化',exact=True).click()
            with page.expect_request('**/api/content/inputs') as request:
                page.get_by_role('button',name='确认输入并交接判断',exact=True).click()
            payload = request.value.post_data_json
            assert not payload['input']['source_changes']['replace']
            assert bool(payload['input']['source_changes']['remove']) == (choice == 'remove')
        finally:
            browser.close()
            server.stop()


def test_natural_task_poll_preserves_search_and_committed_pagination(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    path=tmp_path/'project'
    create_sample(path,page_count=3,readonly=False)
    store=Store(path)
    task_set(store)
    service.inputs_update(path,patch={'reason':'keep polling active','task_patch':{'audience':'test'}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    server=WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch()
        page=browser.new_page()
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            search=page.get_by_role('searchbox',name='搜索全部任务')
            expect(page.locator('.studio-task-record')).to_have_count(30)
            search.fill('still typing')
            with page.expect_response(lambda r: '/api/tasks?' in r.url, timeout=10000):
                page.wait_for_timeout(3500)
            expect(search).to_have_value('still typing')
            expect(search).to_be_focused()
            search.fill('准确保留')
            search.press('Enter')
            expect(page.locator('.run-notice')).to_contain_text('147')
            search.fill('unsubmitted')
            with page.expect_request(lambda r: '/api/tasks?' in r.url and 'offset=30' in r.url) as req:
                page.locator('.run-pagination').get_by_role('button').last.click()
            from urllib.parse import parse_qs, urlsplit
            assert parse_qs(urlsplit(req.value.url).query)['search']==['准确保留']
            expect(search).to_have_value('unsubmitted')
        finally:
            browser.close()
            server.stop()
