"""深度复审 §6 重新归类后的剩余义务（实施方可自行完成的部分）。

- F14：主层只写业务语言——不展开折叠时不出现内部标识/证据（词汇与分层见
  docs/design/webui-opendesign-20261001/product-ui-language.md）。
- N09：画廊「用选页开始风格校准」这条既有路径，在此前用过截图来源之后仍应
  正确进入项目内路线并带上选页。
- plan-ready：本地真实服务就能建立单页试作计划——交接主动作应出现且可用。
- N13：顶栏待接手入口与列表一致，历史版本与最新待办的对应可往返。
"""
import re
import shutil
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_deep_review_fixes_browser import project_browser  # noqa: F401  (fixture reuse)
from test_style_content_browser import confirm_recipe, open_style, toggle_phase, prepare_style_project  # noqa: F401
from test_ux05_runs_delivery_browser import add_task  # noqa: F401
from test_candidates import store as candidate_store, dispatch as dispatch_current_task  # noqa: F401

pytestmark = pytest.mark.browser

INTERNAL = {
    '32 位以上十六进制码': re.compile(r'\b[0-9a-f]{32,}\b'),
    '对象路径': re.compile(r'\.deckmaster/'),
    '内部字段名': re.compile(r'\b(operation_id|plan_id|sha256|content_plan_ref|base_revision|artifact_ref|annotation_refs)\b'),
    '原始 JSON 片段': re.compile(r'["\'](schema_version|plan_actions)["\']\s*:'),
}


@pytest.fixture
def obligations_browser(tmp_path):
    yield from project_browser(tmp_path, page_count=30)


@pytest.fixture
def authorized_obligations_browser(tmp_path):
    yield from project_browser(tmp_path, page_count=30,
        prepare=lambda path: prepare_style_project(path, page_ids=['p02', 'p30'], max_calls=2))


@pytest.fixture
def historical_obligations_browser(tmp_path):
    yield from project_browser(tmp_path, page_count=30, historical=True)


@pytest.fixture
def current_obligations_browser(candidate_store):
    from playwright.sync_api import sync_playwright
    server = WorkbenchServer(candidate_store.project_root)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, candidate_store
            assert errors == []
        finally:
            browser.close()
            server.stop()


def visible_text(page):
    # innerText 不含未渲染的子树：闭合的 details 与隐藏面板不计入主层。
    return page.evaluate("() => document.body.innerText")


def test_main_layer_keeps_business_language_on_every_surface(obligations_browser):
    """F14：五个主工作面在默认（不展开折叠）状态下不泄露内部证据。"""
    page, server, path, store = obligations_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    seen = {}
    for name, ready in [('制作总览', '制作总览'), ('内容与页序', '内容与页序'), ('整稿画廊', '整稿画廊'),
                        ('风格校准', '风格校准'), ('任务与交付', '任务与交付')]:
        page.get_by_role('button', name=name, exact=True).click()
        page.get_by_role('heading', name=ready, exact=True).wait_for()
        page.wait_for_timeout(400)
        text = visible_text(page)
        for label, pattern in INTERNAL.items():
            match = pattern.search(text)
            assert not match, f'{name} 主层出现{label}：{match.group(0)!r}'
        seen[name] = len(text)
    assert all(length > 200 for length in seen.values()), seen


def test_selection_to_style_path_works_after_using_the_screenshot_source(obligations_browser):
    """N09：先走过截图来源，再回画廊用选页开始风格校准——仍进入项目内路线并带选页。"""
    from playwright.sync_api import expect
    page, server, path, store = obligations_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_style(page)
    page.get_by_role('group', name='风格参考来源', exact=True).get_by_role('button', name='外部图片', exact=True).click()
    expect(page.locator('.visual-style')).to_be_visible()
    # 项目路线的状态行不残留到截图路线（两条路线各有自己的状态出口）。
    expect(page.locator('.style-calibration > [role="status"]')).to_be_hidden()
    page.get_by_role('button', name='整稿画廊', exact=True).click()
    page.locator('.gallery-viewport').wait_for()
    page.get_by_label(re.compile(r'^选择第 1 页 ')).check()
    page.get_by_label(re.compile(r'^选择第 3 页 ')).check()
    before = store.read_current()
    page.get_by_role('group', name='画廊选页制作', exact=True).locator('[data-gallery-action="style"]').click()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    expect(page.locator('.batch-actions')).to_contain_text('2 页用于风格校准')
    page.get_by_role('combobox', name='批量固定参考原图', exact=True).select_option('p01')
    expect(page.locator('.batch-actions')).to_contain_text('参考页同时在目标中')
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).to_be_checked()
    # 由用户明确解除参考/目标冲突；入口不得隐式删除选页。
    page.get_by_role('checkbox', name='选择第 01 页', exact=True).uncheck()
    page.get_by_role('button', name='带所选页进入风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()

    # 项目内路线：截图路线收起，固定参考是第 1 页，目标是其余选页。
    expect(page.locator('.style-calibration > .style-phase').first).to_be_visible()
    expect(page.get_by_role('group', name='风格参考来源', exact=True).get_by_role('button', name='项目页面', exact=True)).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('.visual-style')).to_be_hidden()
    expect(page.get_by_role('combobox', name='风格参考原图', exact=True).locator('option:checked')).to_have_text(re.compile(r'^第 1 页 .* · R ' + store.current_revision_id()[:8]))
    page.wait_for_function('''async revision => {
      const {records} = await (await fetch('/api/drafts')).json();
      return records.some(r => r.draft.content.style_calibration?.reference?.page_id === 'p01' &&
        r.draft.content.style_calibration.reference.revision_id === revision &&
        JSON.stringify(r.draft.content.style_calibration.targets) === '["p03"]');
    }''', arg=store.current_revision_id())
    expect(page.locator('.style-calibration .style-phase').first).to_contain_text('第 1 页')
    toggle_phase(page, 1)
    expect(page.get_by_role('checkbox', name=re.compile(r'^风格目标 第 3 页')).first).to_be_checked()
    expect(page.get_by_role('checkbox', name=re.compile(r'^风格目标 第 1 页 ')).first).not_to_be_checked()
    assert store.read_current() == before
    assert 'revision=' + store.current_revision_id() in page.url


def test_style_handoff_appears_with_a_real_local_plan(authorized_obligations_browser):
    """plan-ready：本地服务即可建立单页试作计划——交接动作出现且可用（无需 Host）。"""
    from playwright.sync_api import expect
    page, server, path, store = authorized_obligations_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    confirm_recipe(path, store)
    page.reload()
    newer = page.get_by_role('button', name='查看当前版本', exact=True)
    newer.wait_for(timeout=15000)
    newer.click()
    expect(page).to_have_url(re.compile('revision=' + store.current_revision_id()))
    open_style(page)
    toggle_phase(page, 2)
    versions = page.locator('.studio-recipe-card')
    expect(versions).to_have_count(1, timeout=20000)
    versions.get_by_role('button', name='使用这版规范', exact=True).click()
    handoff = page.locator('.style-plan button').filter(has_text='保存并交接风格试作')
    expect(handoff).to_be_hidden()
    toggle_phase(page, 3)
    page.get_by_role('button', name='预览单页试作', exact=True).click()
    expect(handoff).to_be_visible(timeout=20000)
    expect(handoff).to_be_enabled()


@pytest.mark.parametrize('ui', ['studio', 'v2'])
def test_topbar_pending_entry_matches_the_latest_list_and_returns_to_history(current_obligations_browser, ui):
    """N13/AC18：历史 A 无待办、最新 B 有待办；顶栏入口到最新记录，历史仍可返回。"""
    from urllib.parse import urlencode
    from playwright.sync_api import expect
    from deck_master import run_desk, workbench
    page, server, store = current_obligations_browser
    historical = store.current_revision_id()
    historical_task = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                           if store.read_object_json(ref)['status'] == 'completed')
    before = workbench.workbench_summary(store.project_root, protocol='workbench_summary.v2')
    assert not any(action['kind'] == 'handoff' for action in before['next_actions'].get('actions', []))
    # A current request and a public plan/commit supply B's real task binding.
    # A legacy reader-only task without a request cannot model current work.
    task = dispatch_current_task(store)
    current = store.load_document()
    assert task['collaboration_binding']['request_id'] == current['collaboration']['request']['request_id']
    assert run_desk.detail(store.project_root, task_id=task['task_id'])['task']['current_relation']['status'] == 'current'
    latest = workbench.workbench_summary(store.project_root, protocol='workbench_summary.v2')
    handoffs = [action for action in latest['next_actions'].get('actions', []) if action['kind'] == 'handoff' and action['enabled']]
    assert sum(action['object_count'] for action in handoffs) == 1
    targets = workbench.action_targets(store.project_root, handoffs[0]['action_id'], revision=current['revision_id'])['targets']
    assert [target['object_id'] for target in targets] == [task['task_id']]
    url = server.start()
    identity = page.request.get(url + 'api/project').json()['project_identity']
    page.goto(url + ui + '/#' + urlencode({'project': identity, 'surface': 'overview', 'revision': historical}))
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    expect(page.locator('.history-banner')).to_contain_text('历史版本 · 只读')
    expect(page.locator('.topbar .version')).to_have_text('历史稿')
    assert 'revision=' + historical in page.url
    topbar = page.get_by_role('button', name=re.compile(r'^查看待交接任务，(\d+) 项$'))
    expect(topbar).to_have_attribute('aria-label', '查看待交接任务，1 项')
    topbar.click()
    # 顶栏入口落在最新版本的运行列表，且列表里正是那一项待接手任务。
    expect(page.get_by_role('heading', name='任务与交付', exact=True)).to_be_visible(timeout=15000)
    expect(page).to_have_url(re.compile('revision=' + current['revision_id']))
    expect(page.locator('.runs-subareas button[aria-pressed="true"]')).to_have_text('任务记录')
    expect(page.locator(f'.run-task[data-task-id="{task["task_id"]}"]')).to_contain_text('待接手')
    expect(page.locator('.topbar .version')).to_have_text('当前稿')
    expect(topbar).to_have_attribute('aria-label', '查看待交接任务，1 项')

    # 回到历史版本 A：那里没有这项待办，记录按固定版本展示。
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='版本', exact=True).click()
    # 执行记录默认不在"相关记录"里，看执行型修订要先显示全部记录。
    page.get_by_role('checkbox', name='显示全部历史记录', exact=True).check()
    history_select = page.get_by_role('combobox', name='阅读历史版本')
    expect(history_select.locator(f'option[value="{historical}"]')).to_have_count(1, timeout=15000)
    history_select.select_option(value=historical)
    page.get_by_role('button', name='读取所选版本', exact=True).click()
    page.get_by_role('button', name='任务记录', exact=True).click()
    expect(page.locator('.run-desk')).to_contain_text('固定执行记录')
    expect(page.locator(f'.run-task[data-task-id="{task["task_id"]}"]')).to_have_count(0)
    expect(page.locator(f'.run-task[data-task-id="{historical_task["task_id"]}"]')).to_contain_text('结果已记录')
    expect(page.locator('.history-banner')).to_contain_text('历史版本 · 只读')
    expect(page.locator('.topbar .version')).to_have_text('历史稿')
    expect(topbar).to_have_attribute('aria-label', '查看待交接任务，1 项')
    assert 'revision=' + historical in page.url
    assert store.load_document() == current


def test_topbar_pending_entry_always_lands_on_the_task_list(historical_obligations_browser):
    """复审 F2/F4（跨模型一致）：顶栏承诺"查看待交接任务"，不被记住的子区劫持。"""
    from playwright.sync_api import expect
    page, server, path, store = historical_obligations_browser
    add_task(store, 'todo-task-2', 'reconstruct', 'awaiting_host', '待接手任务用于顶栏入口核对。', historical=True)
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    # 先把记住的子区切成「文件」——顶栏入口之后仍必须落在任务列表。
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='文件', exact=True).click()
    page.get_by_role('button', name='制作总览', exact=True).click()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name=re.compile(r'^查看待交接任务，\d+ 项$')).click()
    expect(page.locator('#runs-tasks')).to_be_visible(timeout=15000)
    expect(page.locator('.runs-subareas button[aria-pressed="true"]')).to_have_text('任务记录')
    expect(page.locator('.run-task').filter(has_text='制作可编辑稿').first).to_contain_text('待接手')


def test_area_link_without_the_subarea_falls_back_to_tasks(obligations_browser):
    """复审 F1（跨模型一致）：核心没有 exports.v1 时 area=files 不得把整个面变空白。"""
    from playwright.sync_api import expect
    import json as json_mod
    page, server, path, store = obligations_browser
    url = server.start()

    def strip_exports(route):
        body = json_mod.loads(route.fetch().text())
        caps = [item for item in body.get('ui_capabilities', []) if item != 'exports.v1']
        route.fulfill(status=200, content_type='application/json',
                      body=json_mod.dumps({**body, 'ui_capabilities': caps}))
    page.route('**/api/health', strip_exports)
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'runs', revision: args[1], area: 'files'})}",
                  [identity, store.current_revision_id()])
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    expect(page.locator('#runs-tasks')).to_be_visible()
    expect(page.locator('.runs-subareas button[aria-pressed="true"]')).to_have_text('任务记录')
    # 非法 area 同样回落而不是让整条路由报错。
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'runs', revision: args[1], area: 'bogus'})}",
                  [identity, store.current_revision_id()])
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    expect(page.locator('#runs-tasks')).to_be_visible()


def test_persisting_a_non_task_area_drops_the_hidden_task_route(historical_obligations_browser):
    """复审 F5：任务详情打开时切走子区，链接不得留下"任务已校验但无处显示"的状态。"""
    from playwright.sync_api import expect
    import urllib.parse
    page, server, path, store = historical_obligations_browser
    add_task(store, 'task-route-1', 'reconstruct', 'awaiting_host', '用于子区持久化与任务路由核对。', historical=True)
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.locator('.run-task').first.get_by_role('button', name='查看这项任务').click()
    expect(page.locator('.run-detail')).to_be_visible()
    page.get_by_role('button', name='版本', exact=True).click()
    params = dict(urllib.parse.parse_qsl(page.url.split('#')[1]))
    assert 'task' not in params, params
    page.reload()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    expect(page.locator('#runs-versions')).to_be_visible()
    # 任务路由已随子区持久化放下：详情区为空（.run-detail:empty 折叠）。
    expect(page.locator('.run-detail')).to_be_hidden()
