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
