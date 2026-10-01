"""Real-browser regressions for the received design's production adaptations."""
from pathlib import Path
import shutil
import re

import pytest

from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.fixture
def workbench_page(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for real UI geometry and keyboard checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        project = tmp_path / 'sample'
        create_gallery_sample(project, page_count=24, readonly=False)
        server = WorkbenchServer(project)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        try:
            page.goto(server.start())
            page.get_by_role('heading', name='制作总览', exact=True).wait_for()
            yield page
        finally:
            browser.close()
            server.stop()


def test_matrix_title_geometry_and_mobile_navigation(workbench_page):
    page = workbench_page
    for width in (360, 390, 600, 820, 1024, 1280, 1440, 1920):
        page.set_viewport_size({'width': width, 'height': 900})
        # Seven design columns plus a production-only selection column must not
        # squeeze the title into one-character lines or overflow the document.
        dims = page.evaluate('''() => {
          const title = document.querySelector('.matrix .title-button');
          const row = title.closest('tr');
          const head = document.querySelector('.matrix thead tr');
          return {width: innerWidth, scroll: document.documentElement.scrollWidth,
            title: title.getBoundingClientRect().width,
            aligned: [...row.children].every((cell, i) =>
              Math.abs(cell.getBoundingClientRect().x - head.children[i].getBoundingClientRect().x) < 1),
            labels: [...document.querySelectorAll('.nav-label')].every(x => getComputedStyle(x).display !== 'none')};
        }''')
        assert dims['scroll'] <= dims['width'] and dims['title'] >= 280
        assert dims['aligned'] and dims['labels']
    assert page.locator('.brand-logo').evaluate('(image) => image.complete && image.naturalWidth > 0')


def test_page_shortcuts_respect_controls_and_dialogs(workbench_page):
    page = workbench_page
    page.get_by_role('button', name='打开第 01 页', exact=True).click()
    page.get_by_role('heading', name=re.compile(r'^第 1 页')).wait_for()
    url = page.url
    page.locator('main button:not([disabled])').first.press('ArrowRight')
    assert page.url == url
    page.locator('#view-title').focus()
    page.keyboard.press('ArrowRight')
    page.get_by_role('heading', name=re.compile(r'^第 2 页')).wait_for()
    assert page.url != url
    page.get_by_role('button', name='连接状态', exact=True).click()
    url = page.url
    page.keyboard.press('Escape')
    assert page.locator('dialog[open]').count() == 0 and page.url == url
