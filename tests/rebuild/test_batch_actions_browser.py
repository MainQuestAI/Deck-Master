"""U02 real loopback plans/receipts in Chromium; no production/model claims."""
from pathlib import Path
import copy
import shutil
import uuid

import pytest

from deck_master.pipeline import artifact
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


@pytest.fixture
def batch_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'batch-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    doc = store.load_document()
    entry = doc['pages'][1]
    file = store.put_blob(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><rect width="960" height="540"/></svg>', ext='svg')
    entry['svg'] = artifact(store, store.project_root / file['path'], 'svg', page_id=entry['page_id'],
                            dependencies=[{'kind': 'blueprint', 'identity': 'page:' + entry['page_id'], 'sha256': entry['blueprint']['sha256']}],
                            derived_from=[entry['blueprint']])
    commit(store, doc, str(uuid.uuid4()))
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for batch interaction checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close()
            server.stop()


def select(page, *numbers):
    for number in numbers:
        page.get_by_role('checkbox', name=f'选择第 {number:02} 页', exact=True).check()


def preview(page):
    page.get_by_role('textbox', name='所选页的制作要求', exact=True).fill('保留事实与数字，统一标题层级。')
    page.get_by_role('button', name='按所选页设置调用上限', exact=True).click()
    page.get_by_role('button', name='预览所选页试作', exact=True).click()
    page.get_by_role('heading', name='确认本次范围', exact=True).wait_for()


def test_mixed_modes_keep_selection_until_explicit_range_adjustment(batch_browser):
    from playwright.sync_api import expect
    page, server, path, store = batch_browser
    before = store.read_current()
    select(page, 1, 2)
    page.get_by_role('combobox', name='批量动作', exact=True).select_option('repair')
    expect(page.get_by_role('checkbox', name='选择第 01 页', exact=True)).to_be_checked()
    expect(page.get_by_role('checkbox', name='选择第 02 页', exact=True)).to_be_checked()
    expect(page.locator('.batch-actions')).to_contain_text('没有可修复的 SVG')
    assert page.get_by_role('button', name='预览所选页试作', exact=True).is_disabled()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    page.locator('.batch-actions').screenshot(path=str(path.parent / 'batch-mixed-mobile.png'))
    page.get_by_role('button', name='移除列出的受限页', exact=True).click()
    assert not page.get_by_role('checkbox', name='选择第 01 页', exact=True).is_checked()
    page.get_by_role('textbox', name='所选页的制作要求', exact=True).fill('修复选定 SVG 的文字对齐。')
    with page.expect_response(lambda response: '/api/changes/plan' in response.url) as response:
        page.get_by_role('button', name='预览所选页试作', exact=True).click()
    plan = response.value.json()['plan']
    assert [(item['page_id'], item['stage']) for item in plan['actions']] == [('p02', 'repair')]
    assert plan['max_calls'] == 0
    assert store.read_current() == before


def test_explicit_budget_exact_plan_and_duplicate_click_create_one_batch(batch_browser):
    from playwright.sync_api import expect
    page, server, path, store = batch_browser
    before = copy.deepcopy(store.load_document())
    select(page, 1, 3)
    page.get_by_role('textbox', name='所选页的制作要求', exact=True).fill('保留事实与数字，统一标题层级。')
    assert page.get_by_role('spinbutton', name='批量图像调用上限').input_value() == '0'
    assert page.get_by_role('button', name='预览所选页试作', exact=True).is_disabled()
    previews, commits = [], []
    page.on('request', lambda request: previews.append(request.post_data_json) if request.url.endswith('/api/changes/plan') else commits.append(request.post_data_json) if request.url.endswith('/api/changes/commit') else None)
    preview(page)
    assert previews[0]['input']['max_calls'] == 2
    assert [item['page_id'] for item in previews[0]['input']['targets']] == ['p01', 'p03']
    assert store.load_document() == before
    page.get_by_role('button', name='保存并交接所选试作', exact=True).evaluate('(button) => {button.click(); button.click();}')
    expect(page.locator('.batch-impact')).to_contain_text('已保存 2 项待交接任务，尚未开始制作')
    assert len(commits) == 1
    doc = store.load_document()
    tasks = [store.read_object_json(ref) for ref in doc['tasks'] if ref not in before['tasks']]
    assert len(tasks) == 2 and all(task['status'] == 'awaiting_host' for task in tasks)
    assert {task['scope_pages'][0] for task in tasks} == {'p01', 'p03'}
    assert doc['pages'] == before['pages']
    assert all(not task.get('generation_attempts') for task in tasks)
    page.get_by_role('button', name='查看本次交接', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    assert 'task=' not in page.url


def test_lost_commit_response_verify_original_receipt_reload_never_redispatches(batch_browser):
    from playwright.sync_api import expect
    page, server, path, store = batch_browser
    before_tasks = copy.deepcopy(store.load_document()['tasks'])
    select(page, 1, 2)
    preview(page)
    requests = []
    def lose(route):
        requests.append(route.request.post_data_json)
        result = route.fetch()
        assert result.status == 200
        route.abort('failed')
    page.route('**/api/changes/commit', lose)
    page.get_by_role('button', name='保存并交接所选试作', exact=True).click()
    expect(page.locator('.business-pending')).to_contain_text('尚未确认保存结果')
    assert len(store.load_document()['tasks']) == len(before_tasks) + 2
    page.reload()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    expect(page.locator('.business-pending')).to_be_visible()
    assert page.get_by_role('checkbox', name='选择第 01 页', exact=True).is_checked() is False
    assert page.get_by_role('textbox', name='所选页的制作要求').input_value() == ''
    page.get_by_role('button', name='核实保存结果', exact=True).click()
    expect(page.locator('.business-pending')).to_be_hidden()
    assert len(requests) == 1 and len(store.load_document()['tasks']) == len(before_tasks) + 2
    assert not page.get_by_role('button', name='重放已保存的原请求', exact=True).count()


def test_changes_to_range_inputs_filter_version_and_late_preview_invalidate_plan(batch_browser):
    from playwright.sync_api import expect
    page, server, path, store = batch_browser
    before_tasks = copy.deepcopy(store.load_document()['tasks'])
    select(page, 1, 2)
    preview(page)
    page.get_by_role('textbox', name='所选页的制作要求').fill('新的明确要求。')
    assert page.get_by_role('button', name='保存并交接所选试作', exact=True).is_disabled()
    pending = []
    def delay(route):
        pending.append((route, route.fetch()))
    page.route('**/api/changes/plan', delay)
    page.get_by_role('button', name='预览所选页试作', exact=True).click()
    # Completing the request after explicit range adjustment must not resurrect it.
    page.get_by_role('checkbox', name='选择第 02 页', exact=True).uncheck()
    assert pending
    pending[0][0].fulfill(response=pending[0][1])
    expect(page.get_by_role('button', name='预览所选页试作', exact=True)).to_be_enabled()
    assert not page.get_by_role('heading', name='确认本次范围', exact=True).count()
    page.unroute('**/api/changes/plan', delay)
    preview(page)
    page.get_by_role('button', name='只看需要处理 3 页', exact=True).click()
    assert page.get_by_role('button', name='保存并交接所选试作', exact=True).is_disabled()
    select(page, 1)
    preview(page)
    doc = copy.deepcopy(store.load_document())
    doc['policy']['user_stop'] = True
    commit(store, doc, str(uuid.uuid4()))
    # Trigger the actual summary poll's focus handler, without changing the URL.
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    expect(page.locator('.batch-actions')).to_contain_text('项目已有新版本')
    assert page.get_by_role('button', name='保存并交接所选试作', exact=True).is_disabled()
    assert store.load_document()['tasks'] == before_tasks


def test_style_transfer_preserves_exact_context_and_reference_target_conflict(batch_browser):
    from playwright.sync_api import expect
    page, server, path, store = batch_browser
    before = store.read_current()
    page.get_by_role('combobox', name='批量动作', exact=True).select_option('style')
    select(page, 2, 3)
    page.get_by_role('combobox', name='批量固定参考原图', exact=True).select_option('p02')
    expect(page.locator('.batch-actions')).to_contain_text('参考页同时在目标中')
    assert page.get_by_role('checkbox', name='选择第 02 页', exact=True).is_checked()
    page.get_by_role('checkbox', name='选择第 02 页', exact=True).uncheck()
    page.get_by_role('textbox', name='所选页的制作要求').fill('仅借用配色，保留构图。')
    page.get_by_role('button', name='带所选页进入风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    expect(page.get_by_role('textbox', name='风格短要求', exact=True)).to_have_value('仅借用配色，保留构图。')
    expect(page.get_by_role('checkbox', name='风格目标 第 3 页 · 每页保留原图与来源', exact=True)).to_be_checked()
    assert not page.get_by_role('checkbox', name='风格目标 第 1 页 · 项目目标与阅读顺序', exact=True).is_checked()
    page.get_by_role('combobox', name='风格参考原图', exact=True).select_option('p03')
    expect(page.locator('.style-calibration')).to_contain_text('目标未被自动移除')
    assert page.get_by_role('checkbox', name='风格目标 第 3 页 · 每页保留原图与来源', exact=True).is_checked()
    assert page.get_by_role('button', name='检查风格要求', exact=True).is_disabled()
    assert store.read_current() == before
