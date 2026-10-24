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


def test_v2_mobile_tools_mount_actual_controls(ui):
    from urllib.parse import urlencode
    from playwright.sync_api import expect
    page, base = ui
    info = page.request.get(base+'api/project').json()
    page.set_viewport_size({'width':390,'height':844})
    page.goto(base+'v2/#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p01','layer':'content','revision':info['revision_id']}))
    page.get_by_role('button',name='工具',exact=True).click()
    panel=page.get_by_role('dialog',name='单页工具面板',exact=True)
    expect(panel).to_be_visible()
    expect(panel.get_by_role('button',name='意见',exact=True)).to_be_visible()
    panel.get_by_role('button',name='意见',exact=True).click()
    panel.get_by_role('button',name='整页意见',exact=True).click()
    expect(panel.get_by_role('textbox',name='意见正文',exact=True)).to_be_visible()
    panel.get_by_role('button',name='回到画面',exact=True).click()
    expect(panel).not_to_be_visible()
    expect(page.locator('.page-context-facts')).to_be_visible()
