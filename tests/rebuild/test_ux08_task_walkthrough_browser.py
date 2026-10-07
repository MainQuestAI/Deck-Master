"""UX-08b 任务体验走查（重做版，2026-10-07）：五条路径，每条都包含正常结果与一个关键失败/恢复。

深度复审 §8.5 的要求：不能只走 happy path，也不能只记 method/path——
每条路径逐步截图，并把实际请求的 payload 与回执身份（plan_id / revision_id /
task_ids / operation_id / export_id / etag）写进 journal，供核对"操作绑定的是哪个对象"。
功能、视觉与任务体验三类结论分别出具（见 UX-08-ACCEPTANCE.md）。
"""
import json
import re
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_style_content_browser import confirm_recipe, open_style, toggle_phase
from test_ux06_gallery_conflict_browser import gallery_pair, open_gallery  # noqa: F401

pytestmark = pytest.mark.browser

EVIDENCE = Path(__file__).resolve().parents[2] / 'output/playwright/ux-review/ux08'
WATCHED = ('/api/changes/plan', '/api/changes/commit', '/api/styles/propose', '/api/styles/confirm',
           '/api/styles/plan', '/api/content/plan', '/api/content/commit', '/api/exports', '/api/drafts/save')


@pytest.fixture
def walkthrough(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux08-project'
    create_sample(path, page_count=30, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-08 walkthroughs')
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


class Journal:
    """记录每步截图、实际请求 payload 与回执身份（不只是 method/path）。"""

    def __init__(self, page, server, name):
        self.page, self.name = page, name
        self.steps, self.calls = [], []
        base = server.start().rstrip('/')
        self.base = base

        def on_request(request):
            if not request.url.startswith(base) or not any(part in request.url for part in WATCHED):
                return
            entry = {'method': request.method, 'path': request.url.replace(base, '')}
            try:
                entry['payload'] = json.loads(request.post_data or 'null')
            except Exception:
                entry['payload'] = None
            self.calls.append(entry)

        def on_response(response):
            if not response.url.startswith(base) or not any(part in response.url for part in WATCHED):
                return
            try:
                body = response.json()
            except Exception:
                return
            for call in reversed(self.calls):
                if call['path'] == response.url.replace(base, '') and 'receipt' not in call:
                    call['status'] = response.status
                    call['receipt'] = identity_of(body)
                    break

        page.on('request', on_request)
        page.on('response', on_response)

    def shot(self, step):
        target = EVIDENCE / f'{self.name}-{len(self.steps) + 1:02}-{step}.png'
        self.page.screenshot(path=str(target), full_page=False)
        self.steps.append({'step': step, 'screenshot': target.name})

    def flush(self):
        (EVIDENCE / f'{self.name}-journal.json').write_text(
            json.dumps({'steps': self.steps, 'calls': self.calls}, ensure_ascii=False, indent=2), encoding='utf-8')


def identity_of(body):
    """从回执里取对象身份，证明这一步绑定的是哪个计划/版本/任务。"""
    if not isinstance(body, dict):
        return None
    keys = ['plan_id', 'revision_id', 'operation_id', 'export_id', 'recipe_id', 'task_id', 'etag', 'status']
    found = {key: body[key] for key in keys if key in body}
    result = body.get('operation_result') or body.get('result') or {}
    if isinstance(result, dict):
        for key in ('revision_id', 'recipe_id', 'task_id'):
            if key in result:
                found[f'result.{key}'] = result[key]
        if isinstance(result.get('task_ids'), list):
            found['result.task_ids'] = result['task_ids']
    if isinstance(body.get('plan'), dict) and 'plan_id' not in found:
        found['plan.plan_id'] = body['plan'].get('plan_id')
        found['plan.base_revision'] = body['plan'].get('base_revision')
    if isinstance(body.get('task_ids'), list):
        found['task_ids'] = body['task_ids']
    return found or None


# ---------------------------------------------------------------- 1 批量制作

def test_batch_route_normal_result_and_lost_response_recovery(walkthrough):
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'batch')
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        expect(page.locator('.batch-actions .batch-fields')).to_be_hidden()
        journal.shot('empty-selection')

        for index in (2, 28):
            page.get_by_role('checkbox', name=f'选择第 {index:02} 页', exact=True).check()
        bar = page.locator('.overview-selection-bar')
        expect(bar).to_contain_text('已选 2 页用于')
        journal.shot('selected-2-and-28-with-sticky-summary')
        page.get_by_label('所选页的制作要求').fill('统一标题层级，保留正文事实与图标。')
        page.get_by_label('批量图像调用上限').fill('2')

        # 失败腿：计划请求中断 → 原因可见、选择与要求保留；随后重试成功。
        page.route('**/api/changes/plan', lambda route: route.abort())
        page.get_by_role('button', name='预览所选页试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('无法连接', timeout=15000)
        expect(page.get_by_label('所选页的制作要求')).to_have_value('统一标题层级，保留正文事实与图标。')
        journal.shot('plan-request-lost-input-kept')
        page.unroute('**/api/changes/plan')

        page.get_by_role('button', name='预览所选页试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('确认本次范围', timeout=15000)
        expect(page.get_by_role('button', name='保存并交接所选试作', exact=True)).to_be_visible()
        journal.shot('plan-reviewed-handoff-visible')
        page.get_by_role('button', name='保存并交接所选试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('已保存', timeout=20000)
        journal.shot('handoff-saved')
    finally:
        journal.flush()


# ---------------------------------------------------------------- 2 风格校准

def test_style_route_conflict_resolution_trial_plan_and_extension_error(walkthrough):
    """正常结果：冲突取舍→确认规范→单页试作计划→交接动作出现；失败：扩展未选页。"""
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'style')
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        open_style(page, with_targets=True)
        page.get_by_label('风格参考原图').select_option('p01')
        page.get_by_role('checkbox', name='风格目标 第 2 页 · 材料如何成为内容', exact=True).check()
        page.get_by_role('textbox', name='风格短要求').fill('按极简留白处理，但页面本身是高密度信息，保留全部事实。')
        page.get_by_role('button', name='检查风格要求', exact=True).click()
        conflict = page.get_by_role('combobox', name='第 2 页 · 材料如何成为内容 密度取舍', exact=True)
        expect(conflict).to_be_visible(timeout=15000)
        journal.shot('conflict-choice-in-confirm-phase')
        conflict.select_option('keep_target')
        # 复审 P1：取舍后的重新检查入口就在同一确认上下文里（不回阶段 1）。
        page.get_by_role('button', name='按此取舍重新检查要求', exact=True).click()
        expect(page.get_by_role('button', name='确认这版风格要求', exact=True)).to_be_enabled(timeout=15000)
        journal.shot('conflict-resolved-confirm-enabled')

        page.get_by_role('button', name='确认这版风格要求', exact=True).click()
        expect(page.locator('.style-calibration > .style-phase').nth(1)).to_contain_text(re.compile(r'V\d'), timeout=20000)
        toggle_phase(page, 3)
        page.get_by_role('button', name='预览单页试作', exact=True).click()
        handoff = page.locator('.style-plan button').filter(has_text='保存并交接风格试作')
        expect(handoff).to_be_visible(timeout=20000)
        expect(handoff).to_be_enabled()
        journal.shot('trial-plan-ready-handoff-visible')

        # 失败腿：扩展未选页 → 原因就地可见。
        toggle_phase(page, 4)
        page.get_by_role('button', name='预览明确选页的扩展', exact=True).click()
        expect(page.locator('.style-plan .field-error')).to_be_visible(timeout=15000)
        journal.shot('extension-without-pages-error-visible')
    finally:
        journal.flush()


# ---------------------------------------------------------------- 3 正文与来源

def test_content_route_change_list_impact_and_draft_restore(walkthrough):
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'content')
    before = store.current_revision_id()
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        identity = page.request.get(server.start().rstrip('/') + '/api/project').json()['project_identity']
        page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: 'p01', layer: 'content', revision: args[1]})}",
                      [identity, before])
        page.locator('.content-editor summary').click()
        page.get_by_label('页面标题').fill('项目目标与阅读顺序（走查核对）')
        expect(page.locator('.draft-state')).to_contain_text('已保存到项目', timeout=15000)
        journal.shot('edited-with-live-change-list')

        # 失败/恢复腿：不确认就刷新——草稿恢复，比较基准仍是正式原文。
        page.reload()
        page.locator('.content-editor summary').click()
        changes = page.locator('.content-changes')
        expect(changes).to_contain_text('本次具体改动（1）', timeout=15000)
        expect(changes.locator('.content-change-before')).to_contain_text('项目目标与阅读顺序')
        assert store.current_revision_id() == before
        journal.shot('draft-restored-against-formal-baseline')

        page.get_by_role('button', name='预览正文修改影响', exact=True).click()
        expect(page.locator('.content-operation')).to_contain_text('本次影响预览', timeout=15000)
        journal.shot('impact-with-change-list')
        page.get_by_role('button', name='确认内容变更', exact=True).click()
        expect(page.locator('.content-changes')).to_contain_text('本次具体改动（0）', timeout=20000)
        journal.shot('confirmed-and-advanced')
    finally:
        journal.flush()


# ---------------------------------------------------------------- 4 比较与交付

def test_delivery_route_version_identities_files_and_blocked_delivery(walkthrough):
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'delivery')
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        page.get_by_role('button', name='任务与交付', exact=True).click()
        page.get_by_role('button', name='版本', exact=True).click()
        expect(page.locator('.history-identity')).to_contain_text('选中：')
        journal.shot('version-identities')
        page.get_by_role('button', name='文件', exact=True).click()
        files = page.locator('#runs-files')
        expect(files.locator('.export-version')).to_contain_text('本次文件固定为')
        expect(files.locator('details.export-recovery').get_by_role('button', name='生成内部工程包', exact=True)).to_be_hidden()
        journal.shot('file-purposes')

        # 正常结果：审阅包生成成功。
        page.get_by_role('button', name='生成审阅包', exact=True).click()
        expect(files.locator('.export-result .download-link').first).to_be_visible(timeout=30000)
        journal.shot('review-package-generated')

        # 失败腿：正式交付包在未完成的项目上被拒绝，缺项与规则就地列出。
        page.get_by_role('button', name='生成正式交付包', exact=True).click()
        gaps = files.locator('.export-gaps')
        expect(gaps).to_be_visible(timeout=30000)
        # 缺项按"哪条规则、下一步做什么"列出；被拒绝时没有下载链接。
        expect(gaps).to_contain_text('对应产物未记录')
        expect(gaps).to_contain_text('先更新对应预览或编译整稿，再重新检查')
        assert files.locator('.export-result .download-link').count() == 1, '只有审阅包有下载链接，正式交付被拒'
        journal.shot('delivery-blocked-with-gaps')
    finally:
        journal.flush()


# ---------------------------------------------------------------- 5 异常与恢复

def test_recovery_route_real_gallery_conflict_reports_differences(gallery_pair):
    """真实 409（不是中断请求）：两个窗口同选页同层，筛选与位置不同 → 面板报真差异。"""
    from playwright.sync_api import expect
    context, server, path, store = gallery_pair
    url = server.start()
    journal = Journal(open_gallery(context, url, 'first'), server, 'recovery')
    try:
        first = journal.page
        first.get_by_label(re.compile(r'^选择第 1 页 ')).check()
        expect(first.locator('.gallery-save')).to_contain_text('画廊选择已保存', timeout=15000)
        second = open_gallery(context, url, 'second')
        expect(second.locator('.slide-tile').first).to_be_visible()
        second.get_by_label('筛选页面状态').select_option('missing')
        second.wait_for_timeout(500)
        expect(second.locator('.gallery-save')).to_contain_text('画廊选择已保存', timeout=15000)

        first.get_by_label('筛选页面状态').select_option('all')
        first.get_by_label(re.compile(r'^选择第 1 页 ')).uncheck()
        first.get_by_label(re.compile(r'^选择第 2 页 ')).check()
        expect(first.locator('.gallery-save')).to_contain_text('个窗口保存了不同选择', timeout=15000)
        journal.shot('real-409-conflict')
        first.locator('.gallery-save').get_by_role('button', name='比较窗口选择', exact=True).click()
        dialog = first.locator('dialog[open]')
        expect(dialog).not_to_contain_text('字段一致')
        expect(dialog).to_contain_text('筛选：')
        expect(dialog).to_contain_text('阅读位置：')
        expect(dialog.get_by_text('两份完整快照', exact=True)).to_be_visible()
        journal.shot('conflict-panel-real-differences')
        dialog.get_by_role('button', name='关闭', exact=True).click()
        # 恢复：读取项目保存的那一份，选择整份变为另一侧。
        first.locator('.gallery-save').get_by_role('button', name='比较窗口选择', exact=True).click()
        first.locator('dialog[open]').get_by_role('button', name='读取项目保存的选择', exact=True).click()
        # 采用另一侧后，本窗口整份变为那一侧：选择回到项目保存的"只选第 1 页"。
        expect(first.locator('.gallery-save')).to_contain_text('已读取项目保存的选择', timeout=15000)
        # 采用另一侧后冲突解除：状态行说明采用了哪一侧，冲突入口不再出现。
        expect(first.locator('.gallery-save')).to_contain_text('已读取项目保存的选择', timeout=15000)
        expect(first.locator('.gallery-save').get_by_role('button', name='比较窗口选择', exact=True)).to_have_count(0)
        journal.shot('recovered-by-adopting-saved-side')
    finally:
        journal.flush()
