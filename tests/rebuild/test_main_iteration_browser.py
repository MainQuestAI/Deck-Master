"""Real owners, real clear receipts and explicit recovery consent."""
import json

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import service
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


def open_inputs(page):
    page.evaluate("""async () => { const {DraftEditor}=await import('/v2/drafts.js');
      if(!window.observedEditors){window.observedEditors=[];const mount=DraftEditor.prototype.mount;
      DraftEditor.prototype.mount=function(){window.observedEditors.push(this);return mount.call(this);};} }""")
    page.get_by_role('button', name='内容与页序', exact=True).click()
    page.get_by_role('button', name='材料与来源', exact=True).click()
    page.get_by_role('button', name='材料与要求', exact=True).click()
    page.get_by_role('button', name='修改任务要求', exact=True).click()


def project_at(tmp_path):
    source = tmp_path / 'brief.md'
    source.write_text('# synthetic iteration smoke')
    path = tmp_path / 'project'
    service.create(path, brief='formal brief', audience='formal audience', sources=[source], project_format='workbench.v3')
    return path


def test_clear_receipt_updates_real_form_in_both_tabs(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            context = browser.new_context()
            a = context.new_page(); a.goto(server.start() + 'studio/'); open_inputs(a)
            a.get_by_label('用途与目标', exact=True).fill('personal brief')
            a.get_by_label('受众', exact=True).fill('personal audience')
            a.get_by_label('本次输入变化说明', exact=True).fill('personal reason')
            expect(a.locator('.personal-draft .draft-state')).to_contain_text('已保存到项目')
            b = context.new_page(); b.goto(server.start() + 'studio/'); open_inputs(b)
            expect(b.get_by_label('用途与目标', exact=True)).to_have_value('personal brief')
            expect(b.locator('.personal-draft .draft-state')).to_contain_text('已保存到项目')
            b.get_by_role('button', name='项目菜单', exact=True).click()
            b.get_by_role('button', name='个人状态与恢复', exact=True).click()
            panel = b.get_by_role('dialog', name='个人状态与恢复', exact=True)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('已清理')
            panel.get_by_role('button', name='关闭', exact=True).click()
            for page in (a, b):
                expect(page.get_by_label('用途与目标', exact=True)).to_have_value('formal brief')
                expect(page.get_by_label('受众', exact=True)).to_have_value('formal audience')
                expect(page.get_by_label('本次输入变化说明', exact=True)).to_have_value('')
                page.get_by_label('本次输入变化说明', exact=True).fill('new reason')
                # The next edit must not capture retired fields again.
                expect(page.get_by_label('用途与目标', exact=True)).to_have_value('formal brief')
            browser.close()
    finally:
        server.stop()


def test_quota_recovery_requires_explicit_confirmation_and_new_edits_revoke_it(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_inputs(page)
            # Block project save and all browser recovery writes, without changing host settings.
            page.route('**/api/drafts/save', lambda route: route.abort() if route.request.method != 'GET' else route.continue_())
            page.evaluate("""() => { Storage.prototype.setItem = function(){throw new DOMException('quota','QuotaExceededError')}; }""")
            page.get_by_label('用途与目标', exact=True).fill('sent before unknown')
            expect(page.locator('.draft-state')).to_contain_text('待核实')
            page.get_by_label('用途与目标', exact=True).fill('keep exactly this draft')
            page.get_by_role('button', name='制作总览', exact=True).click()
            expect(page.get_by_label('用途与目标', exact=True)).to_have_value('keep exactly this draft')
            page.get_by_role('button', name='更多内容工具', exact=True).click()
            page.get_by_role('button', name='工作笔记', exact=True).click()
            with page.expect_download() as saved:
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            value = json.loads(__import__('pathlib').Path(saved.value.path()).read_text())
            assert value['draft']['content']['content_sources']['brief'] == 'keep exactly this draft'
            assert value['pending_save']['draft']['content']['content_sources']['brief'] == 'sent before unknown'
            assert value['pending_save']['expected_etag'] is None
            assert value['pending_save_digest']
            page.get_by_role('button', name='制作总览', exact=True).click()
            expect(page.get_by_label('用途与目标', exact=True)).to_have_value('keep exactly this draft')
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            page.get_by_label('用途与目标', exact=True).fill('later edit')
            page.get_by_role('button', name='制作总览', exact=True).click()
            expect(page.get_by_label('用途与目标', exact=True)).to_have_value('later edit')
            with page.expect_download():
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            page.get_by_role('button', name='制作总览', exact=True).click()
            expect(page.locator('.content-sources')).to_have_count(0)
            browser.close()
    finally:
        server.stop()


def test_readonly_buffer_can_be_downloaded_confirmed_and_closed_with_escape(tmp_path):
    from deck_master.samples import create_sample
    path = tmp_path / 'readonly'
    create_sample(path, page_count=1, readonly=True)
    server = WorkbenchServer(path)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/')
            page.evaluate("""async () => {const {DraftEditor}=await import('/v2/drafts.js');const mount=DraftEditor.prototype.mount;
              DraftEditor.prototype.mount=function(){window.observedDraft=this;return mount.call(this);};} """)
            page.get_by_role('button', name='任务与交付', exact=True).click()
            page.get_by_role('button', name='待决定', exact=True).click()
            page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()
            expect(page.get_by_label('个人草稿', exact=True)).to_have_js_property('readOnly', True)
            # Seed the browser's previously unsent buffer, then let the real loader own it.
            page.evaluate("""() => {const e=observedDraft;const draft=structuredClone(e.draft);draft.content.text='readonly unsent buffer';
              localStorage.setItem(e.activeKey,JSON.stringify({draft,etag:null,status:'dirty',pendingSave:null}));} """)
            page.reload()
            page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()
            note = page.get_by_label('个人草稿', exact=True)
            expect(note).to_have_value('readonly unsent buffer')
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
            dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            expect(dialog).to_be_visible()
            with page.expect_download() as saved:
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            assert json.loads(__import__('pathlib').Path(saved.value.path()).read_text())['draft']['content']['text'] == 'readonly unsent buffer'
            note.press('Escape')
            expect(dialog).to_be_visible()
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            note.press('Escape')
            expect(dialog).not_to_be_visible()
            expect(page.get_by_role('button', name='个人记录与操作恢复', exact=True)).to_be_focused()
            browser.close()
    finally:
        server.stop()


def test_method_preparation_clear_resets_the_actual_personal_context(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/')
            page.get_by_role('button', name='更多内容工具', exact=True).click()
            page.get_by_role('button', name='方法与案例', exact=True).click()
            mode = page.get_by_label('准备上下文', exact=True)
            role = page.get_by_label('方法阅读角色', exact=True)
            phase = page.get_by_label('方法阅读阶段', exact=True)
            mode.select_option('independent'); role.select_option('deck-review'); phase.select_option('speech')
            expect(page.locator('.method-draft-state')).to_contain_text('已保存到项目')
            page.get_by_role('button', name='项目菜单', exact=True).click()
            page.get_by_role('button', name='个人状态与恢复', exact=True).click()
            panel = page.get_by_role('dialog', name='个人状态与恢复', exact=True)
            panel.get_by_role('button', name='生成清理计划', exact=True).click()
            panel.get_by_role('button', name='确认清理并保留备份', exact=True).click()
            expect(panel).to_contain_text('已清理')
            panel.get_by_role('button', name='关闭', exact=True).click()
            expect(mode).to_have_value('project')
            expect(role).to_have_value('deck-content')
            expect(phase).to_have_value('argument')
            mode.select_option('independent')
            expect(role).to_have_value('deck-content')
            expect(phase).to_have_value('argument')
            browser.close()
    finally:
        server.stop()
