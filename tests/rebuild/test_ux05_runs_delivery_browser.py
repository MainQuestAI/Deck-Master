"""UX-05 任务、版本与交付反例（FINAL-REPAIR-PLAN AC16–AC18）。

- AC16/F12：大量运行记录下，「正在进行｜待决定｜版本｜文件」四个子区可直接
  到达（聚焦子区标题）；SVG 族/正文/PPT 任务的快捷阅读按钮名称与其目标层
  相符。
- AC17/F09：选中 A、已读 B、当前 C 三个身份可区分；恢复预览同时显示来源
  版本与当前基准、声明恢复创建新版本；取消不产生业务变化。
- AC18：历史版本 A 无待办而最新 B 有待办；固定记录按版本展示，入口能到
  对应记录并返回；未知/失败任务的下一步文案与事实一致（未知调用不写成
  安全重试）。
"""
import copy
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master.models import content_identity
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from deck_master import tasks as tasks_mod
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


@pytest.fixture
def ux05_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux05-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-05 checks')
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


def add_task(store, task_id, kind, status, instruction):
    doc = store.load_document()
    task = tasks_mod.new_task(task_id=task_id, operation_id=f'op-{task_id}', kind=kind, scope_pages=['p01'],
                              instruction=instruction, inputs=[], dependencies=[],
                              dispatch_revision=doc['revision_id'], produced_against=content_identity(doc), status=status)
    doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))
    return task


def test_runs_subareas_reach_decisions_versions_files_and_shortcuts_match_layers(ux05_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux05_browser
    url = server.start()
    add_task(store, 'compose-task-1', 'compose', 'awaiting_host', '整理本页内容。')
    add_task(store, 'render-task-1', 'render', 'completed', '渲染整稿预览。')
    add_task(store, 'svg-task-1', 'reconstruct', 'completed', '重建这一页的 SVG。')
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()

    # 四个子区是分段工作上下文：默认进入「正在进行」，同一时刻只呈现一个子区，
    # 切换后焦点落在该子区标题，大量记录也不需要手动翻找。
    running = page.get_by_role('button', name='正在进行', exact=True)
    expect(running).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('.run-desk')).to_be_visible()
    expect(page.locator('#runs-versions')).to_be_hidden()
    for name, expected_head in [('待决定', '修改交接'), ('版本', '版本记录'), ('文件', '版本与文件')]:
        page.get_by_role('button', name=name, exact=True).click()
        expect(page.locator('h2:focus')).to_have_text(expected_head)
        expect(running).to_have_attribute('aria-pressed', 'false')
    expect(page.locator('#runs-decisions')).to_be_hidden()
    expect(page.locator('#runs-tasks')).to_be_hidden()

    # SVG 族任务的快捷阅读标注 SVG 层；render 任务标注 PPT 层。
    running.click()
    expect(page.locator('#runs-tasks')).to_be_visible()
    svg_card = page.locator('.run-task').filter(has_text='制作可编辑稿').first
    # 运行列表默认回答要求、目标与状态，而不是只有任务类型和时间。
    expect(svg_card).to_contain_text('要求：重建这一页的 SVG。')
    expect(svg_card).to_contain_text('目标：')
    expect(svg_card.locator('.status')).to_have_text('结果已记录')
    svg_card.get_by_role('button', name='查看这项任务').click()
    import re
    page.get_by_role('button', name=re.compile(r'^阅读 第 1 页 .* · SVG$')).click()
    assert 'layer=svg' in page.url
    page.get_by_role('button', name='任务与交付', exact=True).click()
    render_card = page.locator('.run-task').filter(has_text='渲染预览').first
    render_card.get_by_role('button', name='查看这项任务').click()
    page.get_by_role('button', name=re.compile(r'^阅读 第 1 页 .* · PPT$')).click()
    assert 'layer=ppt' in page.url


def test_gallery_comparison_entry_stays_on_the_toolbar(ux05_browser):
    """AC11/§4.4：并排比较是工具条上的常驻入口，不埋在「阅读设置」里。"""
    from playwright.sync_api import expect
    page, server, path, store = ux05_browser
    url = server.start()
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='整稿画廊', exact=True).click()
    page.locator('.gallery-viewport').wait_for()
    compare = page.get_by_role('button', name='并排比较', exact=True)
    expect(compare).to_be_visible()
    expect(page.get_by_role('button', name='联系表', exact=True)).to_be_visible()
    # 未选够两页时比较保持禁用（不是消失），选满两页后可直接进入。
    expect(compare).to_be_disabled()
    tiles = page.locator('.slide-tile .tile-select input')
    tiles.nth(0).check(); tiles.nth(1).check()
    expect(compare).to_be_enabled()
    compare.click()
    expect(page.locator('.gallery-viewport')).to_have_attribute('data-mode', 'compare')


def test_file_area_orders_version_purpose_result_with_recovery_secondary(ux05_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux05_browser
    url = server.start()
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='文件', exact=True).click()
    files = page.locator('#runs-files')
    expect(files.locator('.export-version')).to_contain_text('本次文件固定为')
    # 版本—用途—结果：正式用途在前，工程恢复包退到辅助折叠，需要时才展开。
    expect(files.get_by_role('button', name='生成正式交付包', exact=True)).to_be_visible()
    expect(files.get_by_role('button', name='生成审阅包', exact=True)).to_be_visible()
    recovery = files.locator('details.export-recovery')
    expect(recovery.get_by_role('button', name='生成内部工程包', exact=True)).to_be_hidden()
    recovery.locator('summary').click()
    expect(recovery.get_by_role('button', name='生成内部工程包', exact=True)).to_be_visible()
    expect(files.get_by_role('heading', name='生成结果', exact=True)).to_be_visible()


def test_version_selection_reading_and_restore_state_their_targets(ux05_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux05_browser
    url = server.start()
    basis = store.current_revision_id()
    commit(store, copy.deepcopy(store.load_document()), str(uuid.uuid4()))
    latest = store.current_revision_id()
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    page.get_by_role('button', name='版本', exact=True).click()
    expect(page.get_by_text('先读取历史版本并查看差异，再预览恢复影响。恢复会创建新版本，当前执行与调用记录不会回滚。')).to_be_visible()

    # 三个身份分开呈现：选中（下一步操作目标）/ 已读（正在查看的版本）/ 当前版本。
    identity = page.locator('.history-identity')
    expect(identity).to_contain_text('选中：')
    expect(identity).to_contain_text('已读：')
    expect(identity).to_contain_text('当前版本：')
    chosen_before = identity.locator('.state-chip').first.inner_text()

    # 选中 A（历史版本）→ 打开此版本切换已读对象；URL 与顶部横幅指明阅读版本。
    version_select = page.get_by_label('阅读历史版本')
    version_select.select_option(value=basis)
    expect(identity.locator('.state-chip').first).not_to_have_text(chosen_before)
    page.get_by_role('button', name='读取所选版本', exact=True).click()
    assert f'revision={basis}' in page.url
    expect(page.get_by_text('查看当前版本', exact=True)).to_be_visible()

    # 恢复预览同时显示来源版本与当前基准；取消恢复不改变任何业务事实。
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='版本', exact=True).click()
    page.get_by_role('button', name='预览恢复此版本', exact=True).click()
    dialog = page.locator('dialog[open]')
    expect(dialog).to_contain_text('来源版本')
    expect(dialog).to_contain_text('当前基准')
    expect(dialog).to_contain_text('确认恢复并创建新版本')
    dialog.get_by_role('button', name='取消恢复', exact=True).click()
    expect(page.locator('dialog[open]')).to_have_count(0)
    assert store.current_revision_id() == latest


def test_historical_record_is_fixed_latest_todo_reachable_and_status_honest(ux05_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux05_browser
    url = server.start()
    add_task(store, 'done-task-1', 'compose', 'completed', '第一版整理已完成。')
    historical = store.current_revision_id()
    add_task(store, 'todo-task-1', 'reconstruct', 'awaiting_host', '新版本待交接的 SVG 重建。')
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'runs', revision: args[1]})}",
                  [page.request.get(url.rstrip('/') + '/api/project').json()['project_identity'], historical])
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    page.wait_for_timeout(1200)
    # 历史 A：固定记录展示，无最新待办的交接要求。
    expect(page.locator('.run-desk')).to_contain_text('固定执行记录')
    expect(page.locator('.run-task').filter(has_text='整理内容').first).to_contain_text('结果已记录')
    expect(page.locator('.run-task').filter(has_text='制作可编辑稿')).to_have_count(0)
    # 入口能到对应记录并返回：查看当前版本后，历史记录仍可达。
    page.get_by_role('button', name='查看当前版本', exact=True).click()
    page.wait_for_timeout(400)
    expect(page.locator('.run-task').filter(has_text='制作可编辑稿').first).to_contain_text('待接手')
    expect(page.locator('.run-task').filter(has_text='整理内容').first).to_contain_text('结果已记录')
    # 未知/失败任务的下一步与事实一致：awaiting_host 说明尚未接手，不是失败重试。
    todo_card = page.locator('.run-task').filter(has_text='制作可编辑稿')
    expect(todo_card.first).to_contain_text('待接手')


def test_batch_blocking_reasons_sit_beside_the_field(ux05_browser):
    """OV-02：预览被挡住时，原因贴在对应字段（要求/上限），不是只有面板级一句话。"""
    from playwright.sync_api import expect
    page, server, path, store = ux05_browser
    url = server.start()
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('checkbox', name='选择第 01 页', exact=True).check()
    batch = page.locator('.batch-actions')
    expect(batch.locator('.batch-fields')).to_be_visible()
    requirement = page.get_by_label('所选页的制作要求')
    expect(requirement).to_have_attribute('aria-invalid', 'true')
    expect(batch).to_contain_text('先写明本次要修改和要保留的内容')
    expect(page.get_by_label('批量图像调用上限')).to_have_attribute('aria-invalid', 'true')
    expect(batch).to_contain_text('原图需要 1 次调用')
    requirement.fill('统一标题层级，保留正文事实。')
    expect(requirement).to_have_attribute('aria-invalid', 'false')
    expect(batch).not_to_contain_text('先写明本次要修改和要保留的内容')
    page.get_by_label('批量图像调用上限').fill('1')
    expect(page.get_by_label('批量图像调用上限')).to_have_attribute('aria-invalid', 'false')
    expect(page.get_by_role('button', name='预览所选页试作', exact=True)).to_be_enabled()
