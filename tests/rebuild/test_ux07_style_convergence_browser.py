"""UX-07b 收敛与三视口视觉验收（FINAL-REPAIR-PLAN AC23 + 补充实施方案）。

覆盖本次迁移的组件：批量配置（UX-02b）、风格阶段组（UX-03b）、任务与交付
子区（UX-05b）。检查项可机读：触点高度 ≥44px、状态不只用颜色表达、配置紧邻
选页工具条；同时按 1440/1280/390 三视口输出 PNG 作为视觉验收证据。
"""
import shutil
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser

EVIDENCE = Path(__file__).resolve().parents[2] / 'output/playwright/ux-review'
# AC23 规范给的是 1440/1280 桌面与 390×844 手机三种视口。
VIEWPORTS = [(1440, 900), (1280, 800), (390, 844)]

MEASURE = """selector => Array.from(document.querySelectorAll(selector))
  .filter(node => node.getClientRects().length && node.getBoundingClientRect().height > 0)
  .map(node => ({text: (node.textContent || '').trim().slice(0, 24), height: node.getBoundingClientRect().height,
                 aria_pressed: node.getAttribute('aria-pressed')}))"""


@pytest.fixture
def ux07_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux07-project'
    create_sample(path, page_count=2, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-07 checks')
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


def assert_touch_targets(page, selector):
    controls = page.evaluate(MEASURE, selector)
    assert controls, f'{selector} 没有可测的控件'
    small = [item for item in controls if item['height'] < 44]
    assert not small, f'{selector} 存在小于 44px 的触点: {small}'


@pytest.mark.parametrize('width,height', VIEWPORTS)
def test_migrated_components_keep_targets_adjacency_and_state_text(ux07_browser, width, height):
    from playwright.sync_api import expect
    page, server, path, store = ux07_browser
    url = server.start()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()

    # 批量配置（UX-02b）：空选只有引导；选一页后配置紧邻选页工具条，触点达标。
    batch = page.locator('.batch-actions')
    expect(batch.locator('.batch-fields')).to_be_hidden()
    page.get_by_label('批量动作').wait_for()
    page.locator('.matrix tbody tr input[type=checkbox]').first.check()
    expect(batch.locator('.batch-fields')).to_be_visible()
    gap = page.evaluate("""() => {
      const toolbar = document.querySelector('.matrix-search');
      const fields = document.querySelector('.batch-actions .batch-fields');
      return fields.getBoundingClientRect().top - toolbar.getBoundingClientRect().bottom;
    }""")
    assert 0 <= gap <= 160, f'配置区与选页工具条的间距过大: {gap}'
    assert_touch_targets(page, '.batch-actions button, .batch-actions select')
    page.screenshot(path=str(EVIDENCE / f'ux07-{width}-overview-batch.png'), full_page=False)

    # 风格阶段组（UX-03b）：阶段摘要触点达标，阶段状态有文字而不是只有颜色。
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    # 项目路线的阶段是 .style-calibration 的直接子节点（截图路线的阶段在 .visual-style 内）。
    assert_touch_targets(page, '.style-calibration > .style-phase > summary')
    phases = page.locator('.style-calibration > .style-phase')
    assert phases.count() == 4
    expect(phases.first).to_contain_text('1 · 参考与目标')
    expect(phases.nth(3)).to_contain_text('4 · 扩展')
    page.screenshot(path=str(EVIDENCE / f'ux07-{width}-style-phases.png'), full_page=False)

    # 任务与交付子区（UX-05b）：分段按钮互斥且有按压状态，触点达标。
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    assert_touch_targets(page, '.runs-subareas button')
    running = page.get_by_role('button', name='正在进行', exact=True)
    expect(running).to_have_attribute('aria-pressed', 'true')
    page.get_by_role('button', name='版本', exact=True).click()
    expect(running).to_have_attribute('aria-pressed', 'false')
    expect(page.get_by_role('button', name='版本', exact=True)).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('.history-identity')).to_contain_text('选中：')
    page.screenshot(path=str(EVIDENCE / f'ux07-{width}-runs-versions.png'), full_page=False)

    # AC23 剩余：受影响消费者一并检查——画廊与内容面同样不能横向溢出，
    # 主要动作触点 ≥44px，字体回退来自 token（中文界面要有中文字族）。
    fonts = page.evaluate('() => getComputedStyle(document.body).fontFamily')
    assert 'PingFang SC' in fonts or 'Noto Sans CJK SC' in fonts or 'Microsoft YaHei' in fonts, fonts
    for surface, slug, selector in [('整稿画廊', 'gallery', '.gallery-controls button'),
                                    ('内容与来源', 'content', '.content-sources button')]:
        page.get_by_role('button', name=surface, exact=True).click()
        page.get_by_role('heading', name=surface, exact=True).wait_for()
        page.wait_for_timeout(300)
        assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth + 1'), f'{surface} 横向溢出'
        assert_touch_targets(page, selector)
        # 证据文件名用 ASCII slug，避免非 ASCII 路径在其它环境/工具链上的兼容问题。
        page.screenshot(path=str(EVIDENCE / f'ux07-{width}-{slug}.png'), full_page=False)
