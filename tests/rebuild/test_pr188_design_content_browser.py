"""Content structure and mobile hierarchy regression."""
import pytest
from test_pr188_reading_browser import ui  # noqa: F401

pytestmark = pytest.mark.browser


from pr188_design_fixtures import manuscript_url  # noqa: F401


def test_content_rows_restore_chapter_and_status(ui):
    from playwright.sync_api import expect
    page, _ = ui
    page.get_by_role('button', name='内容与页序', exact=True).click()
    row = page.locator('.content-order-row').first
    expect(row.locator('.content-row-chapter')).not_to_be_empty()
    expect(row.locator('.content-row-status')).not_to_be_empty()
    expect(row.locator('.content-row-preview')).to_be_visible()


def test_mobile_content_shows_three_rows(manuscript_url, tmp_path):
    from urllib.parse import urlencode
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width':390,'height':844},has_touch=True)
        info = page.request.get(manuscript_url+'api/project').json()
        page.goto(manuscript_url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':info['revision_id']}))
        rows=page.locator('.content-order-row')
        expect(rows).to_have_count(30)
        first,third=rows.first.bounding_box(),rows.nth(2).bounding_box()
        page.screenshot(path=str(tmp_path/'content-390.png'))
        assert first['y'] <= 520, first
        assert third['y']+third['height'] <= 844, third
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.get_by_text('材料与要求',exact=True).click()
        expect(page.get_by_role('button',name='查看输入判断',exact=True)).to_be_visible()
        browser.close()
