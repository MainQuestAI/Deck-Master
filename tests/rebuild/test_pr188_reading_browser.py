"""Navigation and focus survive refresh/reorder without editing content."""
from urllib.parse import parse_qs, urlparse
import json
from pathlib import Path
import pytest
from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer
from test_studio_content_browser import authorize_content_edits

pytestmark = pytest.mark.browser


@pytest.fixture
def ui(tmp_path):
    from playwright.sync_api import sync_playwright
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=30, readonly=False)
    authorize_content_edits(project)
    server = WorkbenchServer(project)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
        try:
            base = server.start()
            page.goto(base + 'studio/')
            page.locator('.matrix').wait_for()
            yield page, base
        finally:
            browser.close()
            server.stop()


def test_search_survives_page_return_history_and_reload(ui):
    from playwright.sync_api import expect
    page, base = ui
    page.get_by_role('button', name='内容与页序', exact=True).click()
    rows = page.locator('.content-order-row')
    rows.nth(1).get_by_role('checkbox').check()
    rows.nth(27).get_by_role('checkbox').check()
    search = page.get_by_role('searchbox', name='搜索逐页稿')
    search.fill('28 ')
    expect(rows).to_have_count(1)
    assert parse_qs(urlparse(page.url).fragment)['content_q'] == ['28 ']
    assert parse_qs(rows.first.locator('.order-handle').get_attribute('href')[1:])['content_q'] == ['28 ']
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    rows.first.locator('.order-handle').click()
    expect(page.locator('#view-title')).to_contain_text('第 28 页')
    page.go_back()
    expect(search).to_have_value('28 ')
    expect(rows).to_have_count(1)
    page.go_forward()
    expect(page.locator('#view-title')).to_contain_text('第 28 页')
    page.get_by_role('button', name='内容与页序', exact=True).click()
    expect(search).to_have_value('28 ')
    page.reload()
    expect(search).to_have_value('28 ')
    expect(rows).to_have_count(1)
    expect(page.locator('.content-list-toolbar')).to_contain_text('已选 2 页 · 筛选外 1 页')


def test_filtered_reorder_restores_search_focus_and_keeps_selection(ui):
    from playwright.sync_api import expect
    page, base = ui
    page.get_by_role('button', name='内容与页序', exact=True).click()
    rows = page.locator('.content-order-row')
    rows.nth(1).get_by_role('checkbox').check()
    rows.nth(27).get_by_role('checkbox').check()
    search = page.get_by_role('searchbox', name='搜索逐页稿')
    # Search the ordinal plus title prefix, rather than the ordinal in title.
    title = rows.nth(27).locator('.order-handle').inner_text().split(' · ', 1)[1]
    search.fill('28 ' + title[:2])
    expect(rows).to_have_count(1)
    rows.first.locator('.order-handle').focus()
    page.keyboard.press('Alt+ArrowDown')
    expect(search).to_be_focused()
    expect(page.locator('#route-status')).to_have_text('页面已移动，已离开当前筛选结果')
    expect(rows).to_have_count(0)
    expect(page.locator('.content-list-toolbar')).to_contain_text('已选 2 页 · 筛选外 2 页')
    search.fill('')
    expect(rows.nth(28)).to_have_attribute('data-page-id', 'p28')
    expect(rows.nth(28).get_by_role('checkbox')).to_be_checked()
    expect(rows.nth(1).get_by_role('checkbox')).to_be_checked()


@pytest.mark.parametrize('label', ['阅读正文', '核对来源'])
def test_refresh_keeps_semantic_menu_focus(ui, label):
    from playwright.sync_api import expect
    page, base = ui
    trigger = page.get_by_role('button', name='第 01 页操作', exact=True)
    trigger.click()
    item = page.locator('.action-popover:popover-open').get_by_role('button', name=label, exact=True)
    item.focus()
    # Real summary refresh event, with another page's attention changed. The
    # focused action's page/layer/target remain identical.
    page.evaluate('''async () => {
      const summary=await (await fetch('/api/view/summary?personal=1')).json();
      summary.pages[1].attention={items:[{kind:'verify_execution',action_id:'b'.repeat(32),enabled:true}]};
      document.querySelector('#app').dispatchEvent(new CustomEvent('summary-refreshed',{detail:summary}));
    }''')
    expect(page.locator('.action-popover:popover-open').get_by_role('button', name=label, exact=True)).to_be_focused()


def test_changed_menu_action_falls_back_without_focusing_new_action(ui):
    from playwright.sync_api import expect
    page, base = ui
    trigger = page.get_by_role('button', name='第 01 页操作', exact=True)
    trigger.click()
    page.locator('.action-popover:popover-open [data-matrix-next]').focus()
    page.evaluate('''async () => {
      const summary=await (await fetch('/api/view/summary?personal=1')).json();
      summary.pages[0].attention={items:[{kind:'verify_execution',action_id:'a'.repeat(32),enabled:true}]};
      document.querySelector('#app').dispatchEvent(new CustomEvent('summary-refreshed',{detail:summary}));
    }''')
    expect(trigger).to_be_focused()
    expect(page.locator('.action-popover:popover-open')).to_have_count(0)


def test_search_does_not_invalidate_order_preview(ui):
    from playwright.sync_api import expect
    page, base = ui
    page.get_by_role('button', name='内容与页序', exact=True).click()
    page.locator('.content-order-row').first.locator('.order-handle').focus()
    page.keyboard.press('Alt+ArrowDown')
    page.get_by_role('button', name='预览页序变更', exact=True).click()
    confirm = page.get_by_role('button', name='确认内容变更', exact=True)
    expect(confirm).to_be_enabled()
    page.get_by_role('searchbox', name='搜索逐页稿').fill('28')
    expect(confirm).to_be_enabled()
    page.get_by_role('searchbox', name='搜索逐页稿').fill('')
    expect(confirm).to_be_enabled()


@pytest.mark.parametrize('read_outcome', ['success', 'failure', 'buffered', 'undo'])
def test_initial_blank_draft_read_does_not_undo_an_accepted_keyboard_reorder(ui, read_outcome):
    from playwright.sync_api import expect
    import re
    page, base = ui
    if read_outcome == 'buffered':
        page.get_by_role('button', name='内容与页序', exact=True).click()
        page.get_by_role('button', name='材料与要求', exact=True).click()
        page.get_by_role('button', name='修改任务要求', exact=True).click()
        page.get_by_label('用途与目标', exact=True).fill('saved personal brief')
        expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
        original_id = page.request.get(base + 'api/drafts').json()['records'][0]['draft']['draft_id']
    held = []
    page.route(re.compile(r'/api/drafts(?:\?.*)?$'), lambda route: held.append(route))
    if read_outcome == 'buffered':
        page.reload()
    else:
        page.get_by_role('button', name='内容与页序', exact=True).click()
    rows = page.locator('.content-order-row')
    first = rows.nth(0).get_attribute('data-page-id')
    second = rows.nth(1).get_attribute('data-page-id')
    if read_outcome == 'failure':
        page.route('**/api/drafts/save', lambda route: route.abort())
        page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
    rows.first.locator('.order-handle').focus()
    page.keyboard.press('Alt+ArrowDown')
    expect(rows.first).to_have_attribute('data-page-id', second)
    expected_first, expected_second = second, first
    if read_outcome == 'undo':
        rows.nth(1).locator('.order-handle').focus()
        page.keyboard.press('Alt+ArrowUp')
        expect(rows.first).to_have_attribute('data-page-id', first)
        expected_first, expected_second = first, second
    assert held
    for route in held:
        if read_outcome == 'failure':
            route.abort()
        else:
            route.fulfill(response=route.fetch())
    page.unroute(re.compile(r'/api/drafts(?:\?.*)?$'))
    expect(page.locator('.draft-state')).not_to_contain_text('正在读取')
    expect(rows.first).to_have_attribute('data-page-id', expected_first)
    expect(rows.nth(1)).to_have_attribute('data-page-id', expected_second)
    if read_outcome == 'failure':
        expect(page.locator('.draft-state')).to_contain_text('待核实')
        page.get_by_role('button', name='制作总览', exact=True).click()
        expect(page.locator('#app')).to_contain_text('仍保留原工作面')
        expect(rows.first).to_have_attribute('data-page-id', expected_first)
        page.get_by_role('button', name='更多内容工具', exact=True).click()
        page.get_by_role('button', name='工作笔记', exact=True).click()
        with page.expect_download() as saved:
            page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
        recovery = json.loads(Path(saved.value.path()).read_text())
        assert recovery['draft']['content']['content_sources']['order'][:2] == [second, first]
        page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
        page.get_by_role('button', name='制作总览', exact=True).click()
        expect(page.locator('.content-sources')).to_have_count(0)
        return
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    page.get_by_role('button', name='制作总览', exact=True).click()
    page.get_by_role('button', name='内容与页序', exact=True).click()
    expect(rows.first).to_have_attribute('data-page-id', expected_first)
    expect(rows.nth(1)).to_have_attribute('data-page-id', expected_second)
    if read_outcome == 'buffered':
        records = page.request.get(base + 'api/drafts').json()['records']
        record = next(row for row in records if row['draft']['draft_id'] == original_id)
        assert record['draft']['content']['content_sources']['brief'] == 'saved personal brief'


def test_row_leaving_attention_filter_falls_back_to_heading(ui):
    from playwright.sync_api import expect
    page, base = ui
    def initial(route):
        response = route.fetch()
        value = response.json()
        value['pages'][0]['prompt_summary'] = None
        value['pages'][0]['attention'] = {'items': [{'kind': 'review_results', 'action_id': 'c' * 32, 'enabled': True}]}
        route.fulfill(response=response, json=value)
    page.route('**/api/view/summary*', initial)
    page.reload()
    page.get_by_role('button', name='只看需要处理', exact=False).click()
    page.get_by_role('button', name='第 01 页操作', exact=True).click()
    page.locator('.action-popover:popover-open').get_by_role('button', name='阅读正文', exact=True).focus()
    page.evaluate('''async () => {
      const summary=await (await fetch('/api/view/summary?personal=1')).json();
      summary.pages[0].attention={items:[]};
      document.querySelector('#app').dispatchEvent(new CustomEvent('summary-refreshed',{detail:summary}));
    }''')
    expect(page.locator('#view-title')).to_be_focused()
    expect(page.locator('.action-popover:popover-open')).to_have_count(0)
    expect(page.get_by_role('button', name='第 01 页操作', exact=True)).to_have_count(0)


def test_content_query_roundtrip_and_invalid_links(ui):
    page, base = ui
    result = page.evaluate('''async () => {
      const {readRoute,routeHash}=await import('/v2/routes.js');
      const info={project_identity:'identity'}, summary={revision_id:'rev',page_count:30};
      const route={surface:'page',page_id:'p28',layer:'content',revision:'rev',content_q:'28 标题 & 来源/页'};
      const hash=routeHash(info,route);
      const restored=readRoute(info,null,summary,hash);
      const errors=['content_q=a&content_q=b','content_q='+ 'x'.repeat(201),'content_q=%00'].map(q=>{
        try {readRoute(info,null,summary,'#project=identity&surface=content&revision=rev&'+q);return false;} catch{return true;}
      });
      return {query:restored.content_q,errors,empty:readRoute(info,null,summary,'#project=identity&surface=content').content_q};
    }''')
    assert result == {'query': '28 标题 & 来源/页', 'errors': [True, True, True], 'empty': ''}
