"""UX-08b 任务体验走查（补充实施方案）：五条真实任务路径在同一份最终组合上走完。

走批量制作、风格校准、正文与来源、比较与交付、异常与恢复五条路径，逐步截图
并把实际请求写入 JSON，作为"任务体验"这一类结论的证据；功能行为与视觉质量
分别由套件结果与三视口截图（test_ux07）承担，三类结论不互相替代。
"""
import json
import shutil
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser

EVIDENCE = Path(__file__).resolve().parents[2] / 'output/playwright/ux-review/ux08'


@pytest.fixture
def walkthrough(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux08-project'
    create_sample(path, page_count=3, readonly=False)
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
    def __init__(self, page, server, name):
        self.page, self.server, self.name = page, server, name
        self.steps = []
        self.requests = []
        base = server.start().rstrip('/')
        page.on('request', lambda request: self.requests.append({'method': request.method, 'path': request.url.replace(base, '')})
                if '/api/' in request.url and request.url.startswith(base) else None)

    def shot(self, step):
        target = EVIDENCE / f'{self.name}-{len(self.steps) + 1:02}-{step}.png'
        self.page.screenshot(path=str(target), full_page=False)
        self.steps.append({'step': step, 'screenshot': target.name})

    def flush(self):
        (EVIDENCE / f'{self.name}-journal.json').write_text(
            json.dumps({'steps': self.steps, 'requests': self.requests}, ensure_ascii=False, indent=2), encoding='utf-8')


def test_batch_route_selection_configuration_review_handoff(walkthrough):
    """批量：未选只阅读 → 选页 → 配置 → 核对出现交接主动作 → 交接记录带要求。"""
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'batch')
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        batch = page.locator('.batch-actions')
        expect(batch.locator('.batch-fields')).to_be_hidden()
        journal.shot('empty-selection')

        for index in (1, 2):
            page.locator('.matrix tbody tr').nth(index).locator('input[type=checkbox]').check()
        expect(batch).to_contain_text('2 页用于原图试作')
        journal.shot('selected-two-pages-configure')

        page.get_by_label('所选页的制作要求').fill('统一标题层级，保留正文事实与图标。')
        page.get_by_label('批量图像调用上限').fill('2')
        page.get_by_role('button', name='预览所选页试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('确认本次范围')
        expect(page.get_by_role('button', name='保存并交接所选试作', exact=True)).to_be_visible()
        journal.shot('plan-reviewed-handoff-visible')

        page.get_by_role('button', name='保存并交接所选试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('已保存', timeout=15000)
        journal.shot('handoff-saved')
        assert any('/api/changes/plan' in item['path'] for item in journal.requests)
        assert any('/api/changes/commit' in item['path'] for item in journal.requests)
    finally:
        journal.flush()


def test_style_route_reference_spec_trial_and_adoption(walkthrough):
    """风格：参考与目标 → 确认规范 → 试作与采用 → 扩展，四阶段在真实路径上可达。"""
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'style')
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_role('heading', name='风格校准', exact=True).wait_for()
        # 两条路线共用阶段语义：项目路线的四个阶段是 .style-calibration 的直接子节点，
        # 截图路线的阶段在 .visual-style 内，用容器限定避免混选隐藏节点。
        phases = page.locator('.style-calibration > .style-phase')
        assert phases.count() == 4
        expect(phases.nth(0)).to_contain_text('参考与目标')
        expect(phases.nth(3)).to_contain_text('扩展')
        journal.shot('phase-one')

        page.get_by_label('风格参考来源').select_option('screenshot')
        expect(page.locator('.visual-style')).to_be_visible()
        expect(page.locator('.visual-style .style-phase').first).to_be_visible()
        journal.shot('screenshot-route-phases')
        page.get_by_label('风格参考来源').select_option('page')
        expect(phases.first).to_be_visible()

        phases.nth(1).locator('> summary').click()
        expect(phases.nth(1)).to_have_attribute('open', '')
        journal.shot('phase-two-spec')
        phases.nth(2).locator('> summary').click()
        expect(phases.nth(2)).to_have_attribute('open', '')
        journal.shot('phase-three-trial')
        # 与批量一致：没有当前有效计划时不出现交接主动作（显隐由 plan 状态决定）。
        expect(page.locator('.style-plan')).to_be_hidden()
    finally:
        journal.flush()


def test_content_route_concrete_change_and_impact(walkthrough):
    """正文：读中选节点 → 具体改动清单 → 影响预览同屏 → 确认后版本前进。"""
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
        changes = page.locator('.content-changes')
        expect(changes).to_contain_text('本次具体改动（0）')
        page.get_by_label('页面标题').fill('项目目标与阅读顺序（已核对）')
        expect(changes).to_contain_text('本次具体改动（1）')
        expect(changes.locator('.content-change-after')).to_contain_text('项目目标与阅读顺序（已核对）')
        page.get_by_role('button', name='预览正文修改影响', exact=True).click()
        expect(page.locator('.content-operation')).to_contain_text('本次影响预览')
        journal.shot('change-list-with-impact')
        page.get_by_role('button', name='确认内容变更', exact=True).click()
        # 保存后改文成为新的已保存原文：对照清单归零，页面标题按新版本展示。
        expect(page.locator('.content-changes')).to_contain_text('本次具体改动（0）', timeout=20000)
        expect(page.get_by_role('heading', name='项目目标与阅读顺序（已核对）', exact=True)).to_be_visible(timeout=20000)
        assert any('/api/content/plan' in item['path'] for item in journal.requests)
        journal.shot('confirmed-advanced')
    finally:
        journal.flush()


def test_delivery_route_version_purpose_result(walkthrough):
    """比较与交付：版本—用途—结果；正式用途在前，工程恢复包为辅。"""
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
        expect(files.get_by_role('button', name='生成正式交付包', exact=True)).to_be_visible()
        expect(files.locator('details.export-recovery').get_by_role('button', name='生成内部工程包', exact=True)).to_be_hidden()
        journal.shot('file-purposes')
        page.get_by_role('button', name='生成审阅包', exact=True).click()
        expect(files.locator('.export-result')).to_be_visible(timeout=20000)
        journal.shot('review-package-result')
        assert any('/api/exports' in item['path'] for item in journal.requests)
    finally:
        journal.flush()


def test_recovery_route_conflict_keeps_input_and_names_next_step(walkthrough):
    """异常与恢复：保存冲突后就近说明真实差异与下一步，输入与选择保留。"""
    from playwright.sync_api import expect
    page, server, path, store = walkthrough
    journal = Journal(page, server, 'recovery')
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        page.locator('.matrix tbody tr').nth(1).locator('input[type=checkbox]').check()
        page.get_by_label('所选页的制作要求').fill('保留这段要求，等待响应核实。')
        page.get_by_label('批量图像调用上限').fill('1')
        page.route('**/api/changes/plan', lambda route: route.abort())
        page.get_by_role('button', name='预览所选页试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('无法连接', timeout=15000)
        # 请求失败不改变选择与要求，用户可以就地重试。
        expect(page.get_by_label('所选页的制作要求')).to_have_value('保留这段要求，等待响应核实。')
        expect(page.locator('.batch-actions')).to_contain_text('1 页用于原图试作')
        journal.shot('lost-response-shows-input-kept')
        page.unroute('**/api/changes/plan')
        page.get_by_role('button', name='预览所选页试作', exact=True).click()
        expect(page.locator('.batch-impact')).to_contain_text('确认本次范围', timeout=15000)
        journal.shot('retry-recovers')
    finally:
        journal.flush()
