"""Reading should not enter opinion editing implicitly."""
import pytest
from test_pr188_reading_browser import ui  # noqa: F401

pytestmark = pytest.mark.browser


def test_reading_defaults_to_context_not_opinion_form(ui):
    from playwright.sync_api import expect
    page, _ = ui
    page.get_by_role('button', name='内容与页序', exact=True).click()
    page.locator('.order-handle').first.click()
    expect(page.locator('#view-title')).to_contain_text('第 1 页')
    expect(page.locator('.page-context-facts')).to_be_visible()
    expect(page.get_by_role('textbox', name='意见正文', exact=True)).not_to_be_visible()
    expect(page.locator('.page-manuscript .content-edit-trigger')).to_be_visible()
