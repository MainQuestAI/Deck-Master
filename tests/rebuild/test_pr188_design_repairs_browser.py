"""Browser navigation counterexample from the design review."""
import pytest
from test_pr188_reading_browser import ui  # noqa: F401

pytestmark = pytest.mark.browser


def test_content_explicit_return_preserves_source_and_search(ui):
    from playwright.sync_api import expect
    page, _ = ui
    page.get_by_role('button', name='内容与页序', exact=True).click()
    page.get_by_role('searchbox', name='搜索逐页稿').fill('28 ')
    page.locator('.order-handle').click()
    expect(page.locator('#view-title')).to_contain_text('第 28 页')
    expect(page.locator('.nav [aria-current=page]')).to_contain_text('内容与页序')
    page.reload()
    page.get_by_role('button', name='返回内容与页序', exact=True).click()
    expect(page.get_by_role('searchbox', name='搜索逐页稿')).to_have_value('28 ')
    expect(page.locator('.content-order-row')).to_have_count(1)
