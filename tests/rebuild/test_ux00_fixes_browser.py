"""UX-00 明确错误的浏览器反例：对象身份、入口定位、分页边界与范围措辞。

每条用例对应 FINAL-REPAIR-PLAN 的一条 AC 反例，且按 8.1 保留"旧代码失败、
新代码通过"的成对关系（把修复回退后运行本文件，应观察到对应断言失败）：

- AC01/F01：交接组切换读取期间点击复制，剪贴板与本机复制标记都不得
  关联到另一组（N01 的真实竞态：旧实现复制旧组文本并标记新组）。
- AC02/F02：材料新增入口必须打开"调整任务要求与材料"表单并聚焦新增
  材料字段；不得命中第一张材料卡的折叠；历史版本入口禁用（CS-01）。
- AC03/F03：保存任务与参考截图两组分页首尾禁用，请求不越界（N02）。
- AC04/F04：项目范围显示"整稿意见"而非"整稿认可"；候选保留决定的
  短码不得伪装成 R 版本（N05 + 决定摘要）。
"""
import base64
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master import changes as changes_mod, content_ops, tasks as tasks_mod
from deck_master.models import content_identity
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_candidates import candidate
from test_content_candidates import content_intent
from test_workbench_actions import commit

pytestmark = pytest.mark.browser

PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


@pytest.fixture
def ux00_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux00-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-00 checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close()
            server.stop()


def add_materials(path, store, count=2):
    files = []
    for index in range(count):
        file = path.parent / f'material-{index}.md'
        file.write_text(f'合成材料 {index} 的内容。', encoding='utf-8')
        content_ops.inputs(path, input={'reason': f'补充合成材料 {index}', 'source_changes': {'add': [{'path': str(file)}]}},
                           base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
        files.append(file)
    return files


def create_change_group(path, store, page_id, instruction):
    plan = changes_mod.plan(path, input=content_intent(store, page_id, instruction=instruction))
    return changes_mod.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                              operation_id=str(uuid.uuid4()))['operation_result']


def test_handoff_copy_binds_to_the_loaded_group_not_the_pending_selection(ux00_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux00_browser
    url = server.start()
    create_change_group(path, store, 'p01', '第一组修改要求 AAA')
    create_change_group(path, store, 'p02', '第二组修改要求 BBB')
    # 面板默认读取的组与按钮顺序都来自 /api/tasks 的 change 分组（同源同序）。
    groups = [group['change_id'] for group in page.request.get(url.rstrip('/') + '/api/tasks?limit=1').json()['groups']
              if group.get('change_id')]
    assert len(groups) == 2
    latest_group = groups[-1]
    other_index = 1 - groups.index(latest_group)
    # 让默认组从一开始就保持未返回：面板只能显示另一组的内容。
    aborted = []
    page.route(f'**/api/changes/{latest_group}/handoff*', lambda route: (aborted.append(route.request.url), route.abort()))
    page.goto(url)
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    # 其它交接组属于任务区的辅助入口；复制身份断言保持不变。
    page.get_by_text('其它修改组的交接', exact=True).click()
    panel = page.locator('.change-handoffs')
    buttons = panel.locator('.change-list button')
    expect(buttons).to_have_count(2)
    copied_key = 'deck-master:v3:copied:' + page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    copied = lambda: json.loads(page.evaluate('key => localStorage.getItem(key) || "[]"', copied_key))

    # 读入未被隔离的另一组：读取成功，身份明确。
    buttons.nth(other_index).click()
    expect(panel.locator('.handoff-detail h3')).to_have_attribute('data-change-id', groups[other_index])

    # 切到被隔离的默认组：切换即重绘，复制按钮对新对象停用，标签仍指向已读组。
    buttons.nth(groups.index(latest_group)).click()
    expect(panel.locator('.handoff-detail')).to_contain_text('正在读取所选修改组')
    assert panel.locator('.handoff-detail h3').get_attribute('data-change-id') == groups[other_index]
    expect(page.locator('.handoff-detail').get_by_role('button', name='交给 Deck Master Agent', exact=True)).to_be_disabled()
    page.wait_for_timeout(300)
    assert page.evaluate('() => navigator.clipboard.readText()') == '', '等待另一组返回期间不得复制旧组文本'
    assert aborted, '被隔离组的读取请求应被拦截'
    assert copied() == [], '未发生的复制不得写入本机提示'

    # 被隔离组真正返回后，复制作用于它，且提示只属于它。
    page.unroute(f'**/api/changes/{latest_group}/handoff*')
    page.locator('.handoff-detail').get_by_role('button', name='核实执行状态', exact=True).click()
    expect(panel.locator('.handoff-detail h3')).to_have_attribute('data-change-id', latest_group)
    latest_text = page.request.get(url.rstrip('/') + f'/api/changes/{latest_group}/handoff').json()['text']
    page.locator('.handoff-detail').get_by_role('button', name='交给 Deck Master Agent', exact=True).click()
    expect(panel.locator('.handoff-detail h3')).to_contain_text('已复制、未接手')
    assert page.evaluate('() => navigator.clipboard.readText()') == latest_text
    assert copied() == [latest_group]


def test_material_entry_opens_the_adjust_form_not_the_first_material_card(ux00_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux00_browser
    url = server.start()
    basis = store.current_revision_id()
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    add_materials(path, store)
    page.goto(url)
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    expect(page.locator('.source-card')).to_have_count(2)
    assert page.locator('.materials-adjust-form').get_attribute('open') is None

    page.get_by_role('button', name='添加材料或调整要求', exact=True).click()
    assert page.locator('.materials-adjust-form').get_attribute('open') == ''
    assert page.evaluate('() => document.activeElement && document.activeElement.getAttribute("aria-label")') \
        == '新增材料完整路径（每行一个）'
    expect(page.locator('.materials-adjust-form h2')).to_have_text('添加材料')
    expect(page.locator('.source-card textarea, .source-card select')).to_have_count(0)

    # 历史版本不加载当前输入：入口禁用并说明原因，而不是命中不存在的控件。
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'content', revision: args[1]})}",
                  [identity, basis])
    expect(page.locator('.materials-aside span.status')).to_have_text('历史版本')
    assert page.get_by_role('button', name='添加材料或调整要求', exact=True).count() == 0, \
        '历史版本不加载当前输入，添加入口不应出现'


def test_style_saved_task_and_reference_pagers_stay_within_bounds(ux00_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux00_browser
    doc = store.load_document()
    for index in range(31):
        task = tasks_mod.new_task(task_id=f'style-analyze-{index:02}', operation_id=f'op-style-{index:02}',
                                  kind='style_analyze', scope_pages=['p01'], instruction=f'截图分析 {index:02}',
                                  inputs=[], dependencies=[], dispatch_revision=doc['revision_id'],
                                  produced_against=content_identity(doc), status='completed')
        doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))

    # 参考截图列表：13 张合成参考构成两页；预览经缩略图链路返回同一张 1px PNG。
    def reference(index):
        sha = hashlib.sha256(str(index).encode()).hexdigest()
        return {'reference': {'reference_id': f'ref-{index:02}', 'width': 96, 'height': 64},
                'preview': {'schema_version': 'deck_artifact.v1', 'artifact_id': 'reference-' + sha,
                            'file': {'path': f'.deckmaster/objects/ab/{sha}.png', 'sha256': sha}}}
    page.route('**/api/styles/references*', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({'references': [reference(index) for index in range(13)], 'fonts': []})))
    page.route('**/api/thumbnails*', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({'status': 'ready', 'url': '/api/thumbnail-file?cache_key=' + 'a' * 64})))
    page.route('**/api/thumbnail-file*', lambda route: route.fulfill(status=200, content_type='image/png', body=PNG_1PX))

    page.goto(server.start())
    offsets = []
    page.on('request', lambda request: offsets.append(int(request.url.split('offset=')[1].split('&')[0]))
            if '/api/tasks?' in request.url and 'offset=' in request.url else None)
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    page.get_by_text('恢复项目中的截图分析与规范', exact=True).click()

    # 保存任务分页：首组上一页禁用；下一页后下一页禁用；请求从不越界。
    previous = page.get_by_role('button', name='上一组保存任务', exact=True)
    expect(previous).to_be_disabled()
    page.get_by_role('button', name='下一组保存任务', exact=True).click()
    expect(page.get_by_text('第 2 组任务')).to_be_visible()
    expect(previous).to_be_enabled()
    expect(page.get_by_role('button', name='下一组保存任务', exact=True)).to_be_disabled()
    assert offsets and min(offsets) >= 0

    # 参考截图分页：同一边界约束。
    reference_previous = page.get_by_role('button', name='上一组参考', exact=True)
    expect(reference_previous).to_be_disabled()
    page.get_by_role('button', name='下一组参考', exact=True).click()
    expect(page.get_by_text('第 2 / 2 组', exact=False)).to_be_visible()
    expect(reference_previous).to_be_enabled()
    expect(page.get_by_role('button', name='下一组参考', exact=True)).to_be_disabled()


def test_project_scope_reads_as_opinion_and_decision_ref_is_not_a_revision(ux00_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux00_browser
    candidate(store)
    page.goto(server.start())

    # 候选保留决定：短码只作追溯，不得显示为 "R" 版本（F04/AC04）。
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.locator('.candidate-desk').wait_for()
    page.get_by_role('button', name='保留当前', exact=True).click()
    state = page.locator('.candidate-state')
    expect(state).to_contain_text('已保留当前（决定 ')
    text = state.inner_text()
    assert '决定 R ' not in text, '决定摘要不得伪装成版本码'
    assert re.search(r'决定 [0-9a-f]{8}', text), text

    # 项目范围是意见的作用范围，不是认可态度（N05/F04）。在 content 层写意见，
    # 草稿编辑器绑定原文基准后才能保存。
    identity = page.request.get(server.start().rstrip('/') + '/api/project').json()['project_identity']
    page.evaluate("id => {location.hash = new URLSearchParams({project: id, surface: 'page', page: 'p01', layer: 'content'})}",
                  identity)
    page.locator('.annotations-panel').wait_for()
    page.get_by_role('button', name='整页意见', exact=True).click()
    body = page.get_by_role('textbox', name='意见正文', exact=True)
    body.fill('整稿方向说明：保持现有叙事顺序。')
    if not page.get_by_label('意见作用范围').is_visible():
        page.get_by_text('范围与标注工具', exact=True).click()
    page.get_by_label('意见作用范围').select_option('project')
    panel = page.locator('.annotations-panel')
    expect(panel).to_contain_text('整稿意见（项目范围）')
    assert '整稿认可' not in panel.inner_text()
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(panel.locator('details.saved-group').filter(has_text='整稿意见与章节意见')).to_be_visible()
    expect(panel.locator('details.saved-group').filter(has_text='整稿意见与章节意见')).to_contain_text(
        '也不是本页的修改要求')
