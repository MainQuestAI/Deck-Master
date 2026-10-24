"""Normal installed UI policy choice, without a synthetic receipt provider."""
import shutil

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import content_review
from deck_master.web import WorkbenchServer
from test_content_preproduction_review import _deck


@pytest.mark.browser
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
def test_user_can_explicitly_choose_and_restore_content_review_requirement(tmp_path, width, height):
    project, store = _deck(tmp_path)
    before = store.load_document()
    assert content_review.dispatch_preproduction_review(project)['status'] == 'needs_reviewer'
    server = WorkbenchServer(project)
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(server.start())
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            page.get_by_role('button', name='选择内容审阅方式', exact=True).click()
            dialog = page.get_by_role('dialog', name='选择内容审阅方式')
            choice = dialog.get_by_role('combobox', name='内容审阅方式')
            expect(choice).to_have_value('')
            expect(dialog).to_contain_text('不代替正式交付所需的人类专业复核')
            expect(dialog).to_contain_text('2 页')
            assert store.load_document() == before
            choice.select_option('host_self')
            confirm = dialog.get_by_role('button', name='确认选择内容审阅方式', exact=True)
            confirm.click()  # No instruction/reason: browser validation must refuse.
            assert store.load_document() == before
            instruction = dialog.get_by_label('本次明确要求（必填）')
            instruction.fill('本次合成试用的这两页由当前制作工具自审，最终交付的人类要求保持。')
            confirm.click()
            expect(dialog).to_contain_text('请求已记录')
            current = store.load_document()
            assert current['collaboration']['quality_profile']['content_review_requirement'] == 'host_self'
            assert current['policy'] == before['policy']
            assert current['collaboration']['authorizations'] == before['collaboration']['authorizations']
            assert content_review.requirement_state(store, current)['effective'] == 'host_self'
            dialog.get_by_role('button', name='重新读取当前状态', exact=True).click()
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            page.get_by_role('button', name='选择内容审阅方式', exact=True).click()
            dialog = page.get_by_role('dialog', name='选择内容审阅方式')
            dialog.get_by_role('combobox', name='内容审阅方式').select_option('independent_model_or_human')
            dialog.get_by_label('本次明确要求（必填）').fill('恢复默认独立审阅要求，保留当前稿件等待审阅。')
            dialog.get_by_role('button', name='确认选择内容审阅方式', exact=True).click()
            expect(dialog).to_contain_text('请求已记录')
            assert content_review.requirement_state(store, store.load_document())['effective'] == 'independent_model_or_human'
            assert store.load_document()['pages'] == before['pages']
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.screenshot(path=str(tmp_path / f'review-policy-{width}.png'), full_page=True)
            assert errors == []
        finally:
            browser.close()
            server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('width,height', [(1440, 900), (390, 844)])
@pytest.mark.parametrize('read_error', [False, True])
def test_pending_work_surface_read_blocks_control_dialog_and_restores(tmp_path, width, height, read_error):
    """Pending reads block real pointer input to the old control snapshot."""
    project, store = _deck(tmp_path)
    before = store.load_document()
    server = WorkbenchServer(project)
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.on('pageerror', lambda error: errors.append(str(error)))
        held = []
        holding = True
        try:
            page.goto(server.start())
            expect(page.get_by_role('button', name='查看本次工作与范围', exact=True)).to_be_visible()

            def hold_current_control(route):
                response = route.fetch()
                if not holding:
                    route.fulfill(response=response)
                    return
                held.append((route, response))
                page.locator('html').evaluate("node => {node.dataset.heldControlRead = 'ready';}")

            page.route('**/api/project?light=1', hold_current_control)
            page.get_by_role('button', name='制作总览', exact=True).click()
            expect(page.locator('html')).to_have_attribute('data-held-control-read', 'ready')
            slot = page.locator('.current-control-facts')
            expect(slot).to_have_attribute('aria-busy', 'true')
            assert slot.evaluate('node => node.inert')
            control = slot.get_by_role('button', name='查看本次工作与范围', exact=True, include_hidden=True)
            control.scroll_into_view_if_needed()
            box = control.bounding_box()
            assert box is not None
            page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            expect(page.locator('dialog[open]')).to_have_count(0)
            assert store.load_document() == before

            holding = False
            for route, response in held:
                if read_error:
                    route.abort()
                else:
                    route.fulfill(response=response)
            expect(page.locator('.navigation-status')).to_be_hidden()
            page.unroute('**/api/project?light=1', hold_current_control)
            expect(slot).not_to_have_attribute('aria-busy', 'true')
            assert not slot.evaluate('node => node.inert')
            if read_error:
                expect(page.locator('.notice')).to_contain_text('无法连接')
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            expect(page.get_by_role('dialog', name='本次工作与范围')).to_be_visible()
            page.get_by_role('button', name='选择内容审阅方式', exact=True).click()
            expect(page.get_by_role('dialog', name='选择内容审阅方式')).to_be_visible()
            assert store.load_document() == before
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert errors == []
        finally:
            browser.close()
            server.stop()
