"""P06/UAC15/X02·X04:画廊画布键盘与虚拟阅读的真实行为证据。

- 画布方向键在瓦片间移动焦点,不触发工作面导航(画廊层事件先处理);
- 虚拟阅读:联系表只渲染可见窗口,滚动到末尾后末页瓦片在列,窗口仍小于总页数;
- 从末尾瓦片按 ↑ 能回到上方瓦片,不报错、不丢焦点。
合成样本,真实浏览器;不调用模型,不声称专业验收。
"""
import shutil
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.fixture
def gallery30(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'gallery-30'
    create_sample(path, page_count=30, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for gallery reading checks')
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


def open_gallery(page, server):
    from playwright.sync_api import expect
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='查看整稿', exact=True).click()
    expect(page.get_by_label('整稿画廊阅读区')).to_be_visible(timeout=15000)


def test_canvas_arrows_move_focus_without_leaving_gallery(gallery30):
    from playwright.sync_api import expect
    page, server, path, store = gallery30
    open_gallery(page, server)
    viewport = page.get_by_label('整稿画廊阅读区')
    first = page.locator('.slide-cover').first
    expect(first).to_be_visible()
    first.focus()
    active_id = page.evaluate("() => document.activeElement.closest('.slide-tile')?.dataset.pageId")
    assert active_id == 'p01'
    page.keyboard.press('ArrowRight')
    expect(page.locator('.slide-tile[data-page-id="p02"] .slide-cover')).to_be_focused()
    page.keyboard.press('ArrowDown')
    active_id = page.evaluate("() => document.activeElement.closest('.slide-tile')?.dataset.pageId")
    assert active_id not in (None, 'p01', 'p02')
    # 焦点仍在画廊瓦片内;工作面没有因方向键跳到别的 surface 或页面。
    assert page.evaluate("() => document.activeElement.closest('.slide-tile') !== null")
    assert 'surface=gallery' in page.url.split('#')[1]
    first_tile = page.locator('.slide-cover').first
    first_tile.focus()
    page.keyboard.press('ArrowLeft')
    expect(page.locator('.slide-tile[data-page-id="p01"] .slide-cover')).to_be_focused()
    assert 'surface=gallery' in page.url.split('#')[1]


def test_continuous_grid_renders_a_window_and_keyboard_recovers_focus(gallery30):
    from playwright.sync_api import expect
    page, server, path, store = gallery30
    open_gallery(page, server)
    viewport = page.get_by_label('整稿画廊阅读区')
    total = page.locator('.slide-tile')
    expect(total.first).to_be_visible()
    # 虚拟窗口:联系表只渲染可见行,而不是一次性 30 页全部上树。
    assert total.count() < 30, total.count()
    # 滚动到末尾:末页瓦片进入窗口;窗口规模仍小于总页数。
    viewport.evaluate('(node) => { node.scrollTop = node.scrollHeight; }')
    expect(page.locator('.slide-tile[data-page-id="p30"]')).to_be_visible(timeout=15000)
    assert total.count() < 30
    # 从末尾瓦片按 ↑:焦点回到上方一行的瓦片,阅读区随行滚动。
    page.locator('.slide-tile[data-page-id="p30"] .slide-cover').focus()
    page.keyboard.press('ArrowUp')
    active_id = page.evaluate("() => document.activeElement.closest('.slide-tile')?.dataset.pageId")
    assert active_id not in (None, 'p30')
    assert 'surface=gallery' in page.url.split('#')[1]
