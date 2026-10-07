"""深度复审（DEEP-REVIEW-9c73d86-20261007）断点反例。

每条断言针对"用户在当前上下文能否看到/够到"，不以"文本在 DOM 里"作为通过条件：

- R1 风格新方案、冲突取舍与确认在同一确认上下文。
- R2 计划失败提示不被"没有计划"一起隐藏。
- R3 正文比较基准是所读正式原文，不随个人草稿变动。
- R4 读取版本/刷新/跨面返回后仍留在对应子区。
- §2.1 30 页末尾选完页，选择摘要与配置入口仍在视口内。
- §2.2 截图路线的试作/交接动作按阶段与真实计划归属。
- §2.3 复杂正文的差异清单与影响同屏。
- §2.4 画廊 409 面板报告真实字段差异（筛选/位置/版本/缩放/参考）。
"""
import copy
import re
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master import styles
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_ux06_gallery_conflict_browser import gallery_pair, open_gallery  # noqa: F401  (fixture reuse)
from test_style_content_browser import confirm_recipe, open_style, toggle_phase  # noqa: F401

pytestmark = pytest.mark.browser

EVIDENCE = Path(__file__).resolve().parents[2] / 'output/playwright/ux-review/deep-review'


def project_browser(tmp_path, page_count=3):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'deep-review-project'
    create_sample(path, page_count=page_count, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for deep-review checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close()
            server.stop()


@pytest.fixture
def style_browser(tmp_path):
    yield from project_browser(tmp_path, page_count=30)


@pytest.fixture
def pages_browser(tmp_path):
    yield from project_browser(tmp_path, page_count=30)


def in_viewport(page, locator):
    box = locator.bounding_box()
    assert box is not None, '目标不可见'
    size = page.viewport_size
    return -1 <= box['y'] and box['y'] + box['height'] <= size['height'] + 1


# --------------------------------------------------------------------------- R1

def test_style_conflict_choices_live_with_the_confirm_action(style_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_style(page, with_targets=True)
    page.get_by_label('风格参考原图').select_option('p01')
    page.get_by_role('checkbox', name='风格目标 第 2 页 · 材料如何成为内容', exact=True).check()
    # 真实核心的密度冲突：要求里同时出现"极简"与"高密度"。
    page.get_by_role('textbox', name='风格短要求').fill('按极简留白处理，但页面本身是高密度信息，保留全部事实。')
    page.get_by_role('button', name='检查风格要求', exact=True).click()

    phases = page.locator('.style-calibration > .style-phase')
    confirm = page.get_by_role('button', name='确认这版风格要求', exact=True)
    conflict = page.get_by_role('combobox', name='第 2 页 · 材料如何成为内容 密度取舍', exact=True)
    confirm_phase = phases.nth(1)
    # 确认阶段自动打开；冲突取舍与确认动作在同一个上下文里（此前藏在阶段 1）。
    expect(confirm_phase).to_have_attribute('open', '')
    expect(confirm).to_be_visible()
    expect(conflict).to_be_visible()
    assert confirm_phase.locator('[aria-label="第 2 页 · 材料如何成为内容 密度取舍"]').count() == 1, '冲突选择必须与确认动作同阶段'
    expect(confirm_phase).to_contain_text('本次方案（确认前核对）')
    expect(confirm_phase).to_contain_text('借用：')
    expect(confirm).to_be_disabled()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / 'r1-style-conflict-in-confirm-phase.png'))

    # 明确取舍后在同一阶段内重新检查（复审 P1：不得回到阶段 1 才能解锁确认），
    # 确认动作随后可用；阶段 1 全程保持关闭。
    expect(page.locator('.style-calibration > .style-phase').first).not_to_have_attribute('open', '')
    conflict.select_option('keep_target')
    page.get_by_role('button', name='按此取舍重新检查要求', exact=True).click()
    expect(page.get_by_role('button', name='确认这版风格要求', exact=True)).to_be_enabled(timeout=15000)
    expect(page.locator('.style-calibration > .style-phase').first).not_to_have_attribute('open', '')


# --------------------------------------------------------------------------- R2

def test_style_plan_failure_stays_visible_without_a_plan(style_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    confirm_recipe(path, store)   # 确认一版规范（写在新版本上）
    page.reload()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    newer = page.get_by_role('button', name='查看当前版本', exact=True)
    newer.wait_for(timeout=15000)          # 确认写在新版本上：先回到当前版本再读规范
    newer.click()
    expect(page).to_have_url(re.compile('revision=' + store.current_revision_id()))
    open_style(page)
    toggle_phase(page, 2)
    versions = page.get_by_role('combobox', name='已确认的风格版本')
    expect(versions.locator('option')).to_have_count(2, timeout=20000)
    versions.select_option(index=1)

    # 扩展阶段：不勾选页面直接预览 → 错误必须真的看得见（此前随"没有计划"一起隐藏）。
    toggle_phase(page, 4)
    page.get_by_role('button', name='预览明确选页的扩展', exact=True).click()
    error = page.locator('.style-plan .field-error')
    expect(error).to_be_visible(timeout=15000)
    expect(error).to_contain_text('请明确勾选本次扩展页')
    assert in_viewport(page, error), '失败原因必须在当前视口内'
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / 'r2-style-plan-error-visible.png'))

    # 网络失败同样可见，且输入保留。
    page.route('**/api/styles/plan', lambda route: route.abort())
    toggle_phase(page, 3)
    page.get_by_role('button', name='预览单页试作', exact=True).click()
    expect(page.locator('.style-plan .field-error')).to_be_visible(timeout=15000)
    expect(page.locator('.style-plan .field-error')).to_contain_text('无法连接')


# --------------------------------------------------------------------------- R3

def test_content_change_list_keeps_the_formal_baseline_after_draft_restore(pages_browser):
    from playwright.sync_api import expect
    page, server, path, store = pages_browser
    formal_title = '项目目标与阅读顺序'
    before = store.current_revision_id()
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(server.start().rstrip('/') + '/api/project').json()['project_identity']
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: 'p01', layer: 'content', revision: args[1]})}",
                  [identity, before])
    page.locator('.content-editor summary').click()
    page.get_by_label('页面标题').fill('未提交的草稿标题')
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目', timeout=15000)

    # 刷新后恢复的是草稿；比较基准仍是所读正式原文（R3）。
    page.reload()
    page.locator('.content-editor summary').click()
    changes = page.locator('.content-changes')
    expect(changes).to_contain_text('本次具体改动（1）', timeout=15000)
    row = changes.locator('.content-change-list li').first
    expect(row.locator('.content-change-before')).to_have_text(formal_title)
    expect(row.locator('.content-change-after')).to_have_text('未提交的草稿标题')
    assert store.current_revision_id() == before, '未提交的草稿不得改变业务版本'
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / 'r3-draft-restore-keeps-formal-baseline.png'))


# --------------------------------------------------------------------------- R4

def test_version_area_survives_reading_reload_and_return(pages_browser):
    from playwright.sync_api import expect
    import urllib.parse
    page, server, path, store = pages_browser
    historical = store.current_revision_id()
    doc = copy.deepcopy(store.load_document())
    from test_workbench_actions import commit
    commit(store, doc, str(uuid.uuid4()))
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='版本', exact=True).click()
    page.get_by_role('combobox', name='阅读历史版本').select_option(value=historical)
    page.get_by_role('button', name='读取所选版本', exact=True).click()

    # 读取版本后面仍留在版本工作区（此前跳回"正在进行"）。
    expect(page.locator('.runs-subareas button[aria-pressed="true"]')).to_have_text('版本')
    expect(page.locator('#runs-versions')).to_be_visible()
    params = dict(urllib.parse.parse_qsl(page.url.split('#')[1]))
    assert params.get('area') == 'versions', params
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / 'r4-version-area-after-read.png'))

    # 刷新与跨面返回同样保持。
    page.reload()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    expect(page.locator('#runs-versions')).to_be_visible()
    page.get_by_role('button', name='制作总览', exact=True).click()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    expect(page.locator('#runs-versions')).to_be_visible()

    # 显式打开某项任务时回到「正在进行」，而不是留在版本区。
    page.get_by_role('button', name='正在进行', exact=True).click()
    page.locator('.run-task').first.get_by_role('button', name='查看这项任务').click()
    expect(page.locator('#runs-tasks')).to_be_visible()


# --------------------------------------------------------------------------- §2.1

def test_long_list_keeps_selection_summary_and_config_entry_in_view(style_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('checkbox', name='选择第 02 页', exact=True).check()
    bar = page.locator('.overview-selection-bar')
    expect(bar).to_be_visible()
    # 滚到第 28 页选页（Playwright 会滚动到元素），不再额外回到顶部。
    page.get_by_role('checkbox', name='选择第 28 页', exact=True).check()
    expect(page.locator('.matrix')).to_be_in_viewport()
    expect(bar).to_be_visible()
    assert in_viewport(page, bar), '选完末尾页后选择摘要必须在视口内'
    expect(bar).to_contain_text('已选 2 页用于')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / '2-1-long-list-selection-bar.png'))

    # 配置入口就地可达：点击后回到配置区并聚焦要求输入。
    bar.get_by_role('button', name='配置要求', exact=True).click()
    requirement = page.get_by_label('所选页的制作要求')
    expect(requirement).to_be_focused()
    assert in_viewport(page, page.locator('.batch-actions')), '配置区应进入视口'
    expect(page.get_by_label('批量图像调用上限')).to_be_visible()


# --------------------------------------------------------------------------- §2.2

def test_screenshot_route_actions_follow_stage_and_plan(style_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    open_style(page)
    page.get_by_label('风格参考来源').select_option('screenshot')
    visual = page.locator('.visual-style')
    expect(visual).to_be_visible()

    # 试作动作属于「试作与采用」阶段；交接动作没有当前计划就不出现。
    phases = visual.locator('.style-phase')
    trial = phases.nth(2).get_by_role('button', name='预览单页试作', exact=True)
    assert phases.nth(2).locator('button', has_text='预览单页试作').count() == 1, '试作动作必须属于阶段 3'
    expect(phases.nth(2)).not_to_have_attribute('open', '')
    assert not trial.is_visible(), '阶段 3 未打开时不应看到后续动作'
    assert visual.locator('button', has_text='保存并交接试作').count() == 1
    assert not visual.locator('button', has_text='保存并交接试作').is_visible(), '没有计划时交接动作不出现'
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / '2-2-screenshot-route-actions.png'))


# --------------------------------------------------------------------------- §2.3

def test_complex_body_change_list_and_impact_share_one_screen(pages_browser):
    from playwright.sync_api import expect
    from deck_master import content_ops
    from test_content_ops import commit as ops_commit, value as ops_value
    page, server, path, store = pages_browser
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    visible = copy.deepcopy(store.read_object_json(entry['page'])['customer_visible'])
    visible['body_blocks'] = [{'id': f'b{i}', 'type': 'paragraph', 'text': f'第 {i} 段的原始事实与数字。'} for i in range(1, 11)]
    inp = ops_value(store, ids=('p01',))
    inp['customer_visible'] = visible
    ops_commit(path, store, inp)
    revision = store.current_revision_id()

    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(server.start().rstrip('/') + '/api/project').json()['project_identity']
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: 'p01', layer: 'content', revision: args[1]})}",
                  [identity, revision])
    page.locator('.content-editor summary').click()
    page.get_by_label('正文块 10 · 文字').fill('第 10 段改写：保留数字，换一种说法。')
    page.get_by_role('button', name='预览正文修改影响', exact=True).click()
    impact = page.locator('.content-operation')
    changes = page.locator('.content-changes')
    expect(impact).to_contain_text('本次影响预览')
    # 复杂正文：差异清单与影响/确认同屏（此前隔着 10 个文本框）。
    expect(changes.locator('.content-change-list li')).to_have_count(1)
    assert in_viewport(page, changes), '差异清单必须在当前视口内'
    assert in_viewport(page, impact), '影响与确认必须在同一屏内'
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / '2-3-complex-body-single-screen-check.png'))


# --------------------------------------------------------------------------- §2.4

def test_gallery_conflict_reports_filter_anchor_and_zoom_differences(gallery_pair):
    from playwright.sync_api import expect
    context, server, path, store = gallery_pair
    url = server.start()
    first = open_gallery(context, url, 'first')
    first.get_by_label(re.compile(r'^选择第 1 页 ')).check()
    expect(first.locator('.gallery-save')).to_contain_text('画廊选择已保存', timeout=15000)

    # 第二窗口：同样的选页与图层，但筛选、列数与阅读位置不同。
    second = open_gallery(context, url, 'second')
    expect(second.locator('.slide-tile').first).to_be_visible()
    second.get_by_label('筛选页面状态').select_option('missing')
    second.get_by_text('阅读设置', exact=True).click()
    second.get_by_role('button', name='2 列', exact=True).click()
    second.wait_for_timeout(400)
    expect(second.locator('.gallery-save')).to_contain_text('画廊选择已保存', timeout=15000)

    # 第一窗口仍持旧 etag，再改动 → 真实 409。
    first.get_by_label('筛选页面状态').select_option('all')
    first.get_by_label(re.compile(r'^选择第 1 页 ')).uncheck()
    first.get_by_label(re.compile(r'^选择第 2 页 ')).check()
    expect(first.locator('.gallery-save')).to_contain_text('个窗口保存了不同选择', timeout=15000)
    first.locator('.gallery-save').get_by_role('button', name='比较窗口选择', exact=True).click()
    dialog = first.locator('dialog[open]')
    expect(dialog).to_contain_text('两个窗口的画廊阅读状态')
    # 真差异必须被报告：不得再出现"字段一致"的错误结论。
    expect(dialog).not_to_contain_text('字段一致')
    expect(dialog).to_contain_text('筛选：')
    expect(dialog).to_contain_text('阅读位置：')
    expect(dialog).to_contain_text('列数：')
    rows = dialog.locator('p').filter(has_text='｜ 项目保存：')
    assert rows.count() >= 2
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    first.screenshot(path=str(EVIDENCE / '2-4-gallery-real-differences.png'))
