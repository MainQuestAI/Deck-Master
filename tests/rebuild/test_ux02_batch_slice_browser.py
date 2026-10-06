"""UX-02 批量任务切片反例（FINAL-REPAIR-PLAN AC06–AC08）。

- AC06：30 页样本选第 2 与第 28 页，配置与下一步跨长表格可达；跨工作面返回
  保留选择与要求（F05"返回"）。
- AC07：D1——搜索/筛选保留选择并持续显示"当前筛选外 M 页"；全选只作用于当前
  筛选中可操作对象；空结果时已选页面不受影响；清除选择是唯一整体清空入口。
- AC08：刷新与项目版本前进保留草稿/选择，旧计划失效须重新预览；未知提交沿
  原请求核实由 test_batch_actions_browser 的 lost-commit 反例继续覆盖。
"""
import copy
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_actions import commit

pytestmark = pytest.mark.browser

REQUIREMENT = '跨章节试作：保留事实与数字，统一标题层级。'


@pytest.fixture
def overview30(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'overview-30'
    create_sample(path, page_count=30, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-02 checks')
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


def test_cross_chapter_selection_reaches_config_and_survives_return(overview30):
    from playwright.sync_api import expect
    page, server, path, store = overview30
    before_revision = store.current_revision_id()
    before_tasks = len(store.load_document()['tasks'])
    page.goto(server.start())
    page.get_by_role('checkbox', name='选择第 02 页', exact=True).check()
    page.get_by_role('checkbox', name='选择第 28 页', exact=True).check()
    expect(page.locator('.batch-actions')).to_contain_text('2 页用于原图试作')
    page.get_by_role('textbox', name='所选页的制作要求', exact=True).fill(REQUIREMENT)
    page.get_by_role('button', name='按所选页设置调用上限', exact=True).click()
    page.get_by_role('button', name='预览所选页试作', exact=True).click()
    scope = page.locator('.batch-impact')
    expect(scope.get_by_role('heading', name='确认本次范围')).to_be_visible()
    expect(scope).to_contain_text('2 页 · 原图试作 · 图像调用 2 次')

    # 返回：进入其它工作面再回来，选择与要求保留，且预览未改动任何业务事实。
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    page.get_by_role('button', name='制作总览', exact=True).click()
    expect(page.get_by_role('checkbox', name='选择第 02 页', exact=True)).to_be_checked()
    expect(page.get_by_role('checkbox', name='选择第 28 页', exact=True)).to_be_checked()
    assert page.get_by_role('textbox', name='所选页的制作要求', exact=True).input_value() == REQUIREMENT
    assert store.current_revision_id() == before_revision
    assert len(store.load_document()['tasks']) == before_tasks


def test_filters_keep_selection_and_show_out_of_filter_count(overview30):
    from playwright.sync_api import expect
    page, server, path, store = overview30
    page.goto(server.start())
    page.get_by_role('checkbox', name='选择第 01 页', exact=True).check()
    page.get_by_role('checkbox', name='选择第 02 页', exact=True).check()
    expect(page.get_by_text('已选择 2 页', exact=True)).to_be_visible()

    # 搜索是筛选的一种：选择保留，并显示筛选外计数。
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p30')
    expect(page.get_by_text('已选择 2 页，当前筛选外 2 页')).to_be_visible()
    assert not page.get_by_role('checkbox', name='选择第 01 页', exact=True).count()
    page.get_by_role('searchbox', name='搜索页码或标题').fill('')
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).to_be_checked()
    expect(page.get_by_role('checkbox', name='选择第 02 页', exact=True)).to_be_checked()

    # 空结果：空态说明已选页面不受影响，计数仍然可见。
    page.get_by_role('searchbox', name='搜索页码或标题').fill('没有这样的页面')
    expect(page.get_by_role('heading', name='没有符合条件的页面')).to_be_visible()
    expect(page.get_by_text('已选页面不受筛选影响')).to_be_visible()
    expect(page.get_by_text('已选择 2 页，当前筛选外 2 页')).to_be_visible()
    page.get_by_role('button', name='清除筛选', exact=True).click()
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).to_be_checked()

    # 全选只含当前筛选中可操作对象；清除选择是唯一的整体清空入口。
    page.get_by_role('checkbox', name='选择当前筛选内所有可操作页面').check()
    expect(page.get_by_text('已选择 30 页', exact=True)).to_be_visible()
    page.get_by_role('button', name='清除选择', exact=True).click()
    expect(page.get_by_text('未选择页面', exact=True)).to_be_hidden()
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).not_to_be_checked()


def test_refresh_and_version_advance_keep_draft_and_invalidate_old_plan(overview30):
    from playwright.sync_api import expect
    from deck_master import overview_state
    page, server, path, store = overview30
    page.goto(server.start())
    page.get_by_role('checkbox', name='选择第 01 页', exact=True).check()
    page.get_by_role('checkbox', name='选择第 02 页', exact=True).check()
    page.get_by_role('textbox', name='所选页的制作要求', exact=True).fill(REQUIREMENT)
    page.get_by_role('button', name='按所选页设置调用上限', exact=True).click()
    page.get_by_role('button', name='预览所选页试作', exact=True).click()
    expect(page.locator('.batch-impact').get_by_role('heading', name='确认本次范围')).to_be_visible()
    # 勾选动作确实把选择按版本写入了服务端 ui_overview 记录（不只是本机）；
    # 选择类保存是静默的，不等状态文案，直接轮询记录。
    import time
    deadline = time.time() + 8
    record = None
    while time.time() < deadline:
        record = overview_state.get(path, revision=store.current_revision_id())['record']
        if record and set(record['state']['selected_page_ids']) == {'p01', 'p02'}:
            break
        page.wait_for_timeout(200)
    assert record and set(record['state']['selected_page_ids']) == {'p01', 'p02'}

    # 项目版本前进（经正常入口的另一次提交）。重新打开项目时恢复上次的阅读
    # 位置（旧版本、只读）——选择与要求仍然保留；点「查看当前版本」回到最新
    # 版本继续：旧计划不随新版本提交，必须重新预览。
    commit(store, copy.deepcopy(store.load_document()), str(uuid.uuid4()))
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).to_be_checked()
    expect(page.get_by_role('checkbox', name='选择第 02 页', exact=True)).to_be_checked()
    assert page.get_by_role('textbox', name='所选页的制作要求', exact=True).input_value() == REQUIREMENT
    page.get_by_role('button', name='查看当前版本', exact=True).click()
    page.wait_for_timeout(500)
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).to_be_checked()
    assert page.get_by_role('textbox', name='所选页的制作要求', exact=True).input_value() == REQUIREMENT
    expect(page.locator('.batch-impact')).not_to_contain_text('确认本次范围')
    assert page.get_by_role('button', name='保存并交接所选试作', exact=True).is_disabled()

    page.get_by_role('button', name='按所选页设置调用上限', exact=True).click()
    page.get_by_role('button', name='预览所选页试作', exact=True).click()
    expect(page.locator('.batch-impact').get_by_role('heading', name='确认本次范围')).to_be_visible()
    expect(page.get_by_role('button', name='保存并交接所选试作', exact=True)).to_be_enabled()
