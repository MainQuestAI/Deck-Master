"""UX-06 画廊 409 冲突面板反例（FINAL-REPAIR-PLAN AC19/F11/C09/N10）。

两个窗口先后保存画廊选择：后保存者得到真实 409（ETag CAS）；冲突面板列出
真正不同的阅读字段（不只"选页"一行）、保留两份完整快照与双份下载入口，
采用哪一侧都是明确动作。
"""
import re
import shutil
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.fixture
def gallery_pair(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux19-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for gallery conflict checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        try:
            yield context, server, path, store
        finally:
            browser.close()
            server.stop()


def open_gallery(context, url, name):
    # 恢复的阅读位置可能让新窗口直接落在画廊。
    page = context.new_page()
    page.goto(url)
    if page.locator('#view-title').inner_text() != '整稿画廊':
        page.get_by_role('button', name='整稿画廊', exact=True).click()
        page.get_by_role('heading', name='整稿画廊', exact=True).wait_for()
    return page


def test_conflict_panel_lists_different_fields_and_both_snapshots(gallery_pair):
    from playwright.sync_api import expect
    context, server, path, store = gallery_pair
    url = server.start()
    first = open_gallery(context, url, 'first')
    # 序列 A：第一窗口选择第 1 页并保存成功。
    first.get_by_label(re.compile(r'^选择第 1 页 ')).check()
    expect(first.locator('.gallery-save')).to_contain_text('画廊选择已保存', timeout=15000)
    # 序列 B：第二窗口开启时读入已保存状态（第 1 页选中），清空选页并保存成功。
    second = open_gallery(context, url, 'second')
    expect(second.locator('.slide-tile').first).to_be_visible()
    second.get_by_label(re.compile(r'^选择第 1 页 ')).uncheck()
    expect(second.locator('.gallery-save')).to_contain_text('画廊选择已保存', timeout=15000)
    # 序列 C：第一窗口仍持旧 etag，再改选第 2 页 → 真实 409。
    first.get_by_label(re.compile(r'^选择第 2 页 ')).check()
    expect(first.locator('.gallery-save')).to_contain_text('个窗口保存了不同选择', timeout=15000)
    panel = first.locator('.gallery-save')
    expect(panel.get_by_role('button', name='比较窗口选择', exact=True)).to_be_visible()

    # 冲突面板：字段级差异 + 两份完整快照 + 双份下载（C09/N10）。
    panel.get_by_role('button', name='比较窗口选择', exact=True).click()
    dialog = first.locator('dialog[open]')
    expect(dialog).to_contain_text('两个窗口的画廊阅读状态')
    expect(dialog).to_contain_text('以下阅读状态在两个窗口不同')
    expect(dialog).to_contain_text('选页：第 1 页、第 2 页 ｜ 项目保存：选页：未选页')
    expect(dialog.get_by_text('两份完整快照', exact=True)).to_be_visible()
    expect(dialog.get_by_role('button', name='下载此窗口副本', exact=True)).to_be_visible()
    expect(dialog.get_by_role('button', name='下载项目保存副本', exact=True)).to_be_visible()
