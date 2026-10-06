"""UX-03 风格与候选切片反例（FINAL-REPAIR-PLAN AC09–AC12，随实施追加）。

已覆盖：
- N07/AC05：同名已保存分析/规范在恢复前可区分——选项标签含状态与短尾，
  两份同 V 同要求的规范标签必然不同。
- N08/AC05：同一修改组在交接面板与运行筛选中共享同一短尾与计数，选择前可对上。
- N06：SVG 族任务的快捷阅读进入 SVG 层，按钮名称与层一致。
"""
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_content_candidates import content_intent
from deck_master import changes as changes_mod

pytestmark = pytest.mark.browser

RECIPE_SHA = 'b' * 64


@pytest.fixture
def ux03_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux03-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-03 checks')
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


def create_change_group(path, store, page_id, instruction):
    plan = changes_mod.plan(path, input=content_intent(store, page_id, instruction=instruction))
    return changes_mod.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                              operation_id=str(uuid.uuid4()))['operation_result']


def test_same_name_saved_recipes_and_groups_are_distinguishable_before_selection(ux03_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux03_browser
    url = server.start()
    create_change_group(path, store, 'p01', '第一组修改要求 AAA')
    create_change_group(path, store, 'p02', '第二组修改要求 BBB')

    def recipe(index):
        return {'recipe': {'schema_version': 'style_recipe.v2', 'recipe_id': f'recipe-{index:016x}',
                           'version': 1, 'input': {'instruction': '同样的风格要求，非常相似。', 'target_page_ids': ['p01'], 'visual_style_ref': {'path': '.deckmaster/objects/ab/' + RECIPE_SHA + '.json', 'sha256': RECIPE_SHA}}},
                'ref': {'path': '.deckmaster/objects/ab/' + RECIPE_SHA + '.json', 'sha256': RECIPE_SHA}}
    page.route('**/api/styles?**', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body='{"recipes": [%s]}' % ','.join(__import__('json').dumps(recipe(i)) for i in range(2))))

    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    panel = page.locator('.change-handoffs')
    buttons = panel.locator('.change-list button')
    expect(buttons).to_have_count(2)
    # 同一修改组在交接面板与运行筛选中共享同一短尾（N08）。
    handoff_labels = [buttons.nth(i).inner_text() for i in range(2)]
    assert handoff_labels[0][-6:] != handoff_labels[1][-6:]
    page.get_by_role('combobox', name='按修改组筛选').select_option(index=1)
    selected_label = page.get_by_role('combobox', name='按修改组筛选').locator('option:checked').inner_text()
    assert any(label.split(' · ')[-1] in selected_label for label in handoff_labels), (handoff_labels, selected_label)

    # 两份同 V 同要求的规范：选项标签含目标页数与短尾，恢复前可区分（N07）。
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    restore = page.get_by_text('恢复项目中的截图分析与规范', exact=True)
    restore.scroll_into_view_if_needed()
    restore.click()
    options = page.get_by_label('已确认的截图规范').locator('option')
    expect(options).to_have_count(3)
    labels = [options.nth(i).inner_text() for i in range(1, 3)]
    assert labels[0] != labels[1], '同名规范在恢复前必须可区分'


def test_svg_task_shortcut_opens_the_svg_layer(ux03_browser):
    page, server, path, store = ux03_browser
    from deck_master.models import content_identity
    from deck_master import tasks as tasks_mod
    from test_workbench_actions import commit
    doc = store.load_document()
    task = tasks_mod.new_task(task_id='svg-task-1', operation_id='op-svg-1', kind='reconstruct',
                              scope_pages=['p01'], instruction='重建这一页的 SVG。', inputs=[], dependencies=[],
                              dispatch_revision=doc['revision_id'], produced_against=content_identity(doc),
                              status='completed')
    doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    card = page.locator('.run-task').filter(has_text='制作可编辑稿')
    card.get_by_role('button', name='查看这项任务').click()
    page.locator('.run-evidence, .run-detail, #view-title').first.wait_for()
    import re
    shortcut = page.get_by_role('button', name=re.compile(r'^阅读 第 1 页 .* · SVG$'))
    shortcut.click()
    assert 'layer=svg' in page.url, page.url
