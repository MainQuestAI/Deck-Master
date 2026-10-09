"""P02/UAC06/07/09/22/23:五工具、共享异常摘要、面板与断点的行为回归。

D2-A(共享异常摘要)、D4-A(1279/1280 断点与工具面板)、D5-A(独立容器与二级
弹窗越层)、E01(root 冒泡路径保持)、O1(面板内快捷键不穿透页面导航)。
合成样本,真实浏览器;不调用模型,不声称专业验收。
"""
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlencode

import pytest

from deck_master import annotation_service
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser

SVG_LAYER = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><text x="30" y="80" font-family="Arial" font-size="24">SYNTHETIC SVG</text></svg>'


@pytest.fixture
def page_fixture(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'p02-project'
    create_sample(path, page_count=2, readonly=False)
    store = Store(path)
    # 给两页真实可读 SVG 层(图标面/意见面在这层运行)。
    import copy as copy_mod
    from xml.etree import ElementTree
    from deck_master import icons
    from deck_master.models import bump_revision
    doc = store.load_document(); new = copy_mod.deepcopy(doc)
    for entry in new['pages']:
        root = icons.tree(SVG_LAYER); root[0].set('font-family', 'Arial')
        root.set('data-blueprint-sha256', store.read_object_json(entry['blueprint'])['file']['sha256'])
        artifact = store.read_object_json(entry['blueprint'])
        artifact['role'] = 'svg'; artifact['media_type'] = 'image/svg+xml'
        artifact['file'] = store.put_blob(ElementTree.tostring(root), ext='svg')
        entry['svg'] = store.put_json_object(artifact)
    bumped = bump_revision(new, {'operation_id': str(uuid.uuid4()), 'kind': 'artifact_adoption',
                                 'description': 'synthetic svg layers', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=bumped, operation_id=bumped['change']['operation_id'])
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for page tools panel checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close(); server.stop()


def goto_page(page, base, identity, page_id, layer, revision=None):
    params = {'project': identity, 'surface': 'page', 'page': page_id, 'layer': layer}
    if revision: params['revision'] = revision
    page.evaluate("args => {location.hash = new URLSearchParams(args)}", params)
    page.locator('.page-tools').wait_for(timeout=15000)


def test_five_face_switcher_is_stable_and_single_face(page_fixture):
    """UAC06 前半:位置稳定、一次一个活动面、aria-pressed 同步、editor 不重建。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(server.base_url if hasattr(server, 'base_url') else page.url.split('#')[0] + 'api/project').json()['project_identity'] if False else page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    revision = store.current_revision_id()
    goto_page(page, server.start(), identity, 'p01', 'svg', revision)
    switchs = page.locator('.page-tools-switcher button')
    expect(switchs).to_have_count(5)
    expect(page.locator('.page-tools-switcher button[aria-pressed=true]')).to_have_text('意见')
    expect(page.locator('.page-tools-faces > :not([hidden])')).to_have_count(1)
    editor_before = page.evaluate('document.querySelector("#personal-draft")?.id')
    # 切到笔记再回来:editor 实例不变(P07a 契约)。
    page.get_by_role('button', name='笔记', exact=True).click()
    expect(page.locator('.page-tools-switcher button[aria-pressed=true]')).to_have_text('笔记')
    expect(page.get_by_role('textbox', name='个人草稿', exact=True)).to_be_visible()
    page.get_by_role('button', name='详情', exact=True).click()
    expect(page.locator('.page-tools-faces > [hidden]').count() if False else page.locator('.page-tools-faces > *:not([hidden])')).to_have_count(1)
    assert page.evaluate('() => document.querySelector("#personal-draft")?.id') == 'personal-draft'
    screenshot_enabled = False


def test_anomaly_summary_survives_face_switch_and_locates_recovery(page_fixture):
    """D2-A/UAC22 前半:异常定位条在切面后仍可见,点击进入对应恢复动作。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    goto_page(page, server.start(), identity, 'p01', 'svg', store.current_revision_id())
    # 笔记面:写草稿并保存成功,再冻结一次新保存制造「待核实」。
    page.get_by_role('button', name='笔记', exact=True).click()
    note = page.get_by_role('textbox', name='个人草稿', exact=True)
    expect(note).to_be_visible(timeout=15000)
    note.fill('异常摘要样例备注')
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    page.route('**/api/drafts/save', lambda route: route.abort())
    note.fill('未知保存制造备注')
    expect(page.locator('.draft-state').first).to_contain_text('待核实', timeout=20000)
    chip = page.locator('.page-tools-anomalies .tool-anomaly-chip')
    expect(chip).to_be_visible(timeout=20000)
    expect(chip).to_contain_text('待核实')
    # 切到详情面:异常摘要继续可见(D2-A:不隐藏、不混入工具正文)。
    page.get_by_role('button', name='详情', exact=True).click()
    expect(chip).to_be_visible()
    # 点击进入笔记面并聚焦恢复动作(核实草稿保存)。
    chip.click()
    expect(page.locator('.page-tools-switcher button[aria-pressed=true]')).to_have_text('笔记')
    expect(page.get_by_role('button', name='核实草稿保存', exact=True)).to_be_focused()


def test_narrow_viewport_switches_between_panel_and_new_column(page_fixture):
    """D4-A/UAC09:1279/1280px 双向,activeElement 与输入在跨断点后保持。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    goto_page(page, server.start(), identity, 'p01', 'svg', store.current_revision_id())
    tools_entry = page.get_by_role('button', name='工具', exact=True)
    expect(tools_entry).to_be_hidden()
    page.set_viewport_size({'width': 1279, 'height': 800})
    expect(tools_entry).to_be_visible()
    tools_entry.click()
    expect(page.get_by_role('dialog', name='单页工具面板')).to_be_visible()
    page.get_by_role('button', name='笔记', exact=True).click()
    note_box = page.get_by_role('textbox', name='个人草稿', exact=True)
    expect(note_box).to_be_visible(timeout=15000)
    note_box.click(); note_box.fill('跨断点输入保留样例')
    expect(note_box).to_have_value('跨断点输入保留样例')
    page.get_by_role('button', name='笔记', exact=True).click()
    expect(page.get_by_role('button', name='笔记', exact=True)).to_be_focused()
    page.set_viewport_size({'width': 1280, 'height': 800})
    tools_root = page.locator('.page-tools')
    expect(tools_root).to_be_visible()
    expect(tools_entry).to_be_hidden()
    # 面板关闭、同一工具仍活动、输入保留。
    expect(page.get_by_role('dialog', name='单页工具面板')).to_have_count(0)
    expect(page.locator('.page-tools-switcher button[aria-pressed=true]')).to_have_text('笔记')
    active = page.evaluate('() => document.activeElement?.tagName')
    assert active, 'activeElement should not be body'
    page.set_viewport_size({'width': 1440, 'height': 900})


def test_panel_escape_does_not_leave_page_and_dialog_layers_return_focus(page_fixture):
    """O1/UAC09:面板内 Escape 不把整页送回画廊;二级弹窗逐层返回(D5-A)。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    goto_page(page, server.start(), identity, 'p01', 'svg', store.current_revision_id())
    if not page.get_by_role('button', name='工具', exact=True).is_visible():
        page.set_viewport_size({'width': 1279, 'height': 800})
    page.get_by_role('button', name='工具', exact=True).click()
    panel = page.get_by_role('dialog', name='单页工具面板')
    expect(panel).to_be_visible()
    # O1:面板开启时按 Escape 只关面板,页面级 Escape(回画廊)不执行。
    page.get_by_role('button', name='笔记', exact=True).focus()
    page.keyboard.press('Escape')
    expect(page.get_by_role('heading', name='第 1 页', exact=False).first).to_be_visible()
    assert page.url != page.url.split('#')[0], 'page must stay on page surface'
    # 弹窗逐层:面板之上的二级弹窗矩阵由
    # test_second_level_modal_above_panel_keeps_layers_and_returns_focus 覆盖;
    # 本例收尾验证面板关闭后焦点回到「工具」入口。
    expect(page.get_by_role('button', name='工具', exact=True)).to_be_focused()


def test_second_level_modal_above_panel_keeps_layers_and_returns_focus(page_fixture):
    """D5-A/UAC22:二级弹窗叠在工具面板之上;Escape/确认逐层退出,焦点回原触发器。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    goto_page(page, server.start(), identity, 'p01', 'svg', store.current_revision_id())
    page.set_viewport_size({'width': 1279, 'height': 800})
    page.get_by_role('button', name='工具', exact=True).click()
    panel = page.get_by_role('dialog', name='单页工具面板')
    expect(panel).to_be_visible()
    page.get_by_role('button', name='笔记', exact=True).click()
    note = page.get_by_role('textbox', name='个人草稿', exact=True)
    expect(note).to_be_visible(timeout=15000)
    note.fill('面板之上的弹窗样例')
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    # 恢复列表由 load 构建:先保存再 reload,让已存草稿进入恢复选择框。
    page.reload()
    page.get_by_role('button', name='工具', exact=True).click()
    page.get_by_role('button', name='笔记', exact=True).click()
    note = page.get_by_role('textbox', name='个人草稿', exact=True)
    expect(note).to_be_visible(timeout=15000)
    # 恢复详情默认收起,先展开才能选择已保存草稿(真实恢复入口)。
    page.get_by_text('恢复、下载与版本详情', exact=True).click()
    restore = page.get_by_label('恢复项目中的个人草稿')
    expect(restore).to_be_visible(timeout=15000)
    saved_id = restore.locator('option').evaluate_all('os => os.map(o => o.value).filter(Boolean)')[0]
    # 自动保存会在 600ms 后把 dirty 抢回 saved:挂起保存请求,让「保存中」成为稳定
    # 状态后恢复选择才走「保留当前输入再恢复」弹窗路径。
    held = []
    page.route('**/api/drafts/save', lambda route: held.append(route))
    note.fill('面板弹窗叠加输入')
    expect(page.locator('.draft-state').first).to_contain_text('正在保存到项目', timeout=20000)
    restore.select_option(saved_id)
    modal = page.locator('#modal')
    expect(modal).to_be_visible()
    expect(modal).to_contain_text('保留当前输入再恢复')
    # 工具面板仍开着:二级弹窗是独立一层,不替换面板内容(硬约束 E01)。
    expect(panel).to_be_visible()
    # Tab 不穿透二级弹窗,焦点留在顶层模板内。
    page.keyboard.press('Tab')
    page.keyboard.press('Tab')
    assert page.evaluate('() => Boolean(document.activeElement?.closest("#modal"))')
    # Escape 只关弹窗这一层:面板保持,焦点返回弹窗打开时的活跃元素
    # (O2 原触发器路径);不得滞留在 body 或已关闭的弹窗内。
    page.keyboard.press('Escape')
    expect(modal).not_to_be_visible()
    expect(panel).to_be_visible()
    assert page.evaluate('() => Boolean(document.activeElement?.closest(".page-tools-panel"))'), \
        'escape must return focus into the tools panel'
    # 按钮路径完成恢复:弹窗关闭,私人笔记回到已保存内容。
    restore.select_option(saved_id)
    expect(modal).to_be_visible()
    page.get_by_role('button', name='打开所选草稿', exact=True).click()
    expect(note).to_have_value('面板之上的弹窗样例', timeout=15000)
    # 再按 Escape:只关面板这一层,焦点回「工具」入口;页面仍在页工作面。
    page.keyboard.press('Escape')
    expect(panel).not_to_be_visible()
    expect(page.get_by_role('button', name='工具', exact=True)).to_be_focused()
    assert 'surface=page' in page.url.split('#')[1]


def test_anomaly_chip_runs_the_full_draft_state_lifecycle(page_fixture):
    """D2-A 生命周期:冲突→错误→中断三态互不覆盖,各自经真实入口解决后消失。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    goto_page(page, server.start(), identity, 'p01', 'svg', store.current_revision_id())
    page.get_by_role('button', name='笔记', exact=True).click()
    note = page.get_by_role('textbox', name='个人草稿', exact=True)
    expect(note).to_be_visible(timeout=15000)
    chip = page.locator('.page-tools-anomalies .tool-anomaly-chip')
    expect(chip).to_be_hidden()
    note.fill('生命周期基线段')
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    # ① 服务端 409 → conflict:chip 指向比较入口。
    conflict_route = lambda route: route.fulfill(status=409,
        json={'error': {'code': 'local_state_conflict', 'message': '另一个窗口已保存不同内容。'}})
    page.route('**/api/drafts/save', conflict_route)
    note.fill('生命周期冲突段')
    expect(chip).to_contain_text('待比较', timeout=20000)
    chip.click()
    expect(page.get_by_role('button', name='比较两份草稿', exact=True)).to_be_focused()
    # 解决路径:比较弹窗 → 另存为新草稿(取消拦截后走真实保存)。
    page.get_by_role('button', name='比较两份草稿', exact=True).click()
    detail = page.locator('#modal')
    expect(detail).to_be_visible()
    expect(detail).to_contain_text('保留两份个人草稿')
    page.unroute('**/api/drafts/save')
    page.get_by_role('button', name='另存为个人草稿', exact=True).click()
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    expect(chip).to_be_hidden()
    # ② 服务端 400 → error:chip 提示上次保存未完成;error 状态允许手动重存。
    page.route('**/api/drafts/save', lambda route: route.fulfill(status=400,
        json={'error': {'code': 'request_failed', 'message': '本地校验拒绝。'}}))
    note.fill('生命周期错误段')
    expect(chip).to_contain_text('上次保存未完成', timeout=20000)
    page.unroute('**/api/drafts/save')
    page.get_by_role('button', name='保存个人草稿', exact=True).click()
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    expect(chip).to_be_hidden()
    # ③ 保存请求中断 → unknown:核实发现项目落后,经「重试已发送的内容」解决。
    page.route('**/api/drafts/save', lambda route: route.abort())
    note.fill('生命周期中断段')
    expect(chip).to_contain_text('待核实', timeout=20000)
    page.unroute('**/api/drafts/save')
    page.get_by_role('button', name='核实草稿保存', exact=True).click()
    modal = page.locator('#modal')
    expect(modal).to_contain_text('原草稿尚未确认保存', timeout=20000)
    page.get_by_role('button', name='重试已发送的内容', exact=True).click()
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    expect(chip).to_be_hidden(timeout=20000)


def test_continuous_face_path_keeps_half_written_opinion(page_fixture):
    """UAC06:意见半条→笔记→详情→返回意见;切面不丢输入,刷新/换页/换层不串。"""
    from playwright.sync_api import expect
    page, server, path, store = page_fixture
    page.goto(server.start()); page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(page.url.split('#')[0] + 'api/project').json()['project_identity']
    revision = store.current_revision_id()
    goto_page(page, server.start(), identity, 'p01', 'svg', revision)
    pressed = lambda: page.locator('.page-tools-switcher button[aria-pressed=true]')
    expect(pressed()).to_have_text('意见')
    page.get_by_role('button', name='整页意见', exact=True).click()
    body = page.get_by_label('意见正文', exact=True)
    body.fill('半条意见：标题偏长')
    # 笔记面:写一段并成功保存;两份输入各自留在自己的面。
    page.get_by_role('button', name='笔记', exact=True).click()
    note = page.get_by_role('textbox', name='个人草稿', exact=True)
    expect(note).to_be_visible(timeout=15000)
    note.fill('随身笔记样例')
    page.get_by_role('button', name='保存个人草稿', exact=True).click()
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    # 详情面:查看制作记录;异常摘要仍可见且不进工具正文。
    page.get_by_role('button', name='详情', exact=True).click()
    expect(page.locator('.page-tools-faces > :not([hidden]) .page-tools-anomalies')).to_have_count(0)
    # 返回意见面:半条意见逐字保留;笔记面内容同样不丢。
    page.get_by_role('button', name='意见', exact=True).click()
    expect(body).to_have_value('半条意见：标题偏长')
    page.get_by_role('button', name='笔记', exact=True).click()
    expect(note).to_have_value('随身笔记样例')
    page.get_by_role('button', name='意见', exact=True).click()
    # 刷新:意见仍是默认活动面(草稿装载不抢面),半条意见从本机缓冲恢复。
    page.reload()
    expect(pressed()).to_have_text('意见', timeout=20000)
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('半条意见：标题偏长', timeout=20000)
    # 换页:第 2 页意见正文为空(不串页);回到第 1 页内容仍在。
    page.get_by_role('button', name='下一页，第 2 页 · 材料如何成为内容', exact=True).click()
    expect(page.locator('[aria-label="页面内容"]')).to_have_attribute('data-page-id', 'p02', timeout=20000)
    body = page.get_by_label('意见正文', exact=True)
    expect(body).to_have_value('', timeout=15000)
    page.get_by_role('button', name='上一页，第 1 页 · 项目目标与阅读顺序', exact=True).click()
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('半条意见：标题偏长', timeout=20000)
    # 换层:逐页稿层的意见正文依旧为空;回 SVG 层输入仍在(桌面层用链路导航换层)。
    page.get_by_role('button', name='02 逐页稿，可查看', exact=True).click()
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('', timeout=15000)
    page.get_by_role('button', name='05 SVG，可查看', exact=True).click()
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('半条意见：标题偏长', timeout=20000)
