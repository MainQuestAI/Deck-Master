"""Real owners, real clear receipts and explicit recovery consent."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import service
from deck_master import ui_journal
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


def open_operations(page):
    page.evaluate("""async () => {const {DraftEditor}=await import('/v2/drafts.js');const mount=DraftEditor.prototype.mount;
      DraftEditor.prototype.mount=function(){window.observedDraft=this;return mount.call(this);};} """)
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='待决定', exact=True).click()
    page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()


@pytest.mark.parametrize('kind', ['ascii', 'near-limit', 'utf8', 'structured'])
def test_complete_recovery_download_import_through_product(tmp_path, kind):
    project = project_at(tmp_path)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_operations(page)
            page.route('**/api/drafts/save', lambda route: route.abort())
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
            note = page.get_by_label('个人草稿', exact=True)
            note.fill('sent original')
            expect(page.locator('.draft-state')).to_contain_text('待核实')
            page.evaluate("""kind => {const e=observedDraft;clearTimeout(e.timer);
              const content= kind==='structured' ? {text:'current', data:Object.fromEntries(Array.from({length:100000},(_,i)=>['k'+String(i).padStart(6,'0'),0]))} :
                {text:kind==='utf8'?'中😀'.repeat(180000):'a'.repeat(1100000)};
              e.draft.content=content;
              if(kind==='near-limit') {e.draft.content.text='';e.draft.content.text='a'.repeat(1998976-new TextEncoder().encode(JSON.stringify(e.draft)).length);}
              e.pendingSave.draft=structuredClone(e.draft);
              e.pendingSave.draft.content.text=e.draft.content.text.slice(0,-2)+'bb';
              e.input.value=e.draft.content.text;e.updateStatus();} """, kind)
            with page.expect_download() as saved:
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            downloaded = Path(saved.value.path())
            raw = downloaded.read_bytes(); recovery = json.loads(raw)
            assert 2_000_000 < len(raw) <= 4_000_000
            assert recovery['digest'] == ui_journal.digest(recovery['draft'])
            assert recovery['pending_save_digest'] == ui_journal.digest(recovery['pending_save'])
            if kind == 'structured':
                assert len((json.dumps(recovery, ensure_ascii=False, indent=2) + '\n').encode()) > 4_000_000
            assert not page.evaluate('() => observedDraft.canLeave()')
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            assert page.evaluate('() => observedDraft.canLeave()')
            # Changing the original unknown request also revokes custody.
            page.evaluate("() => {observedDraft.pendingSave.expected_etag='a'.repeat(64);observedDraft.updateStatus();}")
            assert not page.evaluate('() => observedDraft.canLeave()')
            page.evaluate('() => {observedDraft.pendingSave.expected_etag=null;observedDraft.updateStatus();}')
            with page.expect_download():
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            page.unroute('**/api/drafts/save')
            page.reload()
            page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()
            posts = []
            page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
            with page.expect_response('**/api/drafts/import') as imported:
                page.get_by_label('导入草稿恢复文件', exact=True).set_input_files(downloaded)
            assert imported.value.status == 200
            expect(note).to_have_value(recovery['draft']['content']['text'])
            assert imported.value.json()['preserved_pending_save']
            assert imported.value.json()['record']['draft']['content'] == recovery['draft']['content']
            assert not any(url.endswith('/api/drafts/save') for url in posts)
            records = ui_journal.list_drafts(project)['records']
            assert len(records) == 1 and records[0]['draft']['content'] == recovery['draft']['content']
            browser.close()
    finally:
        server.stop()


def test_recovery_file_limit_and_legacy_core_fallback_never_allow_lossy_custody(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_operations(page)
            requests = []
            page.on('request', lambda request: requests.append(request.url) if request.method == 'POST' else None)
            recovery = page.evaluate("""async () => {const e=observedDraft;const {digest}=await import('/v2/api.js');
              return {schema_version:'ui_draft_recovery.v1',draft:e.draft,digest:await digest(e.draft)};}""")
            content = json.dumps(recovery, ensure_ascii=False).encode()
            for size in (3_999_999, 4_000_000, 4_000_001):
                file = {'name':'boundary.json', 'mimeType':'application/json', 'buffer':content + b' ' * (size-len(content))}
                if size <= 4_000_000:
                    with page.expect_response('**/api/drafts/import') as imported:
                        page.get_by_label('导入草稿恢复文件', exact=True).set_input_files(file)
                    assert imported.value.status == 200
                else:
                    count = len(requests)
                    page.get_by_label('导入草稿恢复文件', exact=True).set_input_files(file)
                    expect(page.locator('.field-error').filter(has_text='恢复文件超过容量限制')).to_be_visible()
                    assert len(requests) == count
            page.evaluate("""() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};
              const e=observedDraft;delete e.info.recovery_limits;e.status='unknown';e.draft.content.text='a'.repeat(1100000);
              e.pendingSave={draft:structuredClone(e.draft),expected_etag:null};e.updateStatus();} """)
            downloads = []
            page.on('download', lambda saved: downloads.append(saved))
            page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            expect(page.locator('.field-error').filter(has_text='完整恢复文件超过容量限制')).to_be_visible()
            assert downloads == [] and not page.evaluate('() => observedDraft.canLeave()')
            expect(page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True)).to_be_hidden()
            page.evaluate('() => {observedDraft.draft.content.text="a".repeat(1998977);}')
            page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            expect(page.locator('.field-error').filter(has_text='单份草稿超过容量限制')).to_be_visible()
            assert page.evaluate('() => observedDraft.pendingSave.draft.content.text.length') == 1100000
            browser.close()
    finally:
        server.stop()


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
                expect(page.locator('.personal-draft .draft-state')).to_contain_text('尚无个人草稿')
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
            page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()
            page.evaluate('() => history.back()')
            expect(dialog).not_to_be_visible()
            expect(page.locator('#view-title')).to_be_focused()
            page.evaluate('() => history.forward()')
            page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()
            expect(note).to_have_value('readonly unsent buffer')
            expect(note).to_have_js_property('readOnly', True)
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


def test_beforeunload_requires_recovery_custody_under_persistent_quota(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_inputs(page)
            page.route('**/api/drafts/save', lambda route: route.abort())
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
            page.get_by_label('用途与目标', exact=True).fill('retain through beforeunload')
            page.once('dialog', lambda dialog: dialog.dismiss())
            with page.expect_event('dialog') as prompt:
                page.evaluate('() => { location.reload(); }')
            assert prompt.value.type == 'beforeunload' and not page.is_closed()
            expect(page.get_by_label('用途与目标', exact=True)).to_have_value('retain through beforeunload')
            page.get_by_role('button', name='更多内容工具', exact=True).click()
            page.get_by_role('button', name='工作笔记', exact=True).click()
            with page.expect_download():
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            with page.expect_event('close'):
                page.close(run_before_unload=True)
            browser.close()
    finally:
        server.stop()


@pytest.mark.parametrize('outcome', ['missing', 'late'])
def test_dynamic_route_import_preserves_the_visible_owner(tmp_path, outcome):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_inputs(page)
            page.get_by_label('用途与目标', exact=True).fill('keep current form owner')
            held = []
            def module(route):
                if outcome == 'missing':
                    route.fulfill(status=404, body='missing module')
                else:
                    held.append(route)
            page.route('**/v2/gallery.js', module)
            with page.expect_request('**/v2/gallery.js'):
                page.get_by_role('button', name='整稿画廊', exact=True).click()
            if outcome == 'late':
                # A real history navigation supersedes the pending module generation.
                page.evaluate('() => history.back()')
                expect(page).to_have_url(__import__('re').compile('surface=content'))
                page.get_by_role('button', name='材料与要求', exact=True).click()
                page.get_by_role('button', name='修改任务要求', exact=True).click()
                expect(page.get_by_label('用途与目标', exact=True)).to_have_value('keep current form owner')
                assert held
                route = held.pop(); response = page.request.get(server.start() + 'v2/gallery.js'); route.fulfill(response=response)
            expect(page.get_by_label('用途与目标', exact=True)).to_have_value('keep current form owner')
            expect(page.locator('.gallery-view')).to_have_count(0)
            if outcome == 'missing':
                page.unroute('**/v2/gallery.js', module)
                with page.expect_request('**/v2/gallery.js'):
                    page.get_by_role('button', name='重新加载工作台', exact=True).click()
                expect(page.locator('.gallery-view')).to_be_visible()
                open_inputs(page)
                expect(page.get_by_label('用途与目标', exact=True)).to_have_value('keep current form owner')
            browser.close()
    finally:
        server.stop()


@pytest.mark.parametrize('dismiss', ['close', 'escape'])
def test_recovery_dialog_belongs_to_committed_work_surface(tmp_path, dismiss):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.start() + 'studio/')
            page.get_by_role('button', name='整稿画廊', exact=True).click()
            expect(page.locator('.gallery-view')).to_be_visible()
            page.get_by_role('button', name='任务与交付', exact=True).click()
            page.get_by_role('button', name='待决定', exact=True).click()
            trigger = page.get_by_role('button', name='个人记录与操作恢复', exact=True)
            trigger.click()
            dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
            expect(dialog).to_be_visible()
            if dismiss == 'close':
                dialog.get_by_role('button', name='关闭', exact=True).click()
            else:
                dialog.get_by_label('个人草稿', exact=True).press('Escape')
            expect(dialog).not_to_be_visible()
            expect(trigger).to_be_focused()
            trigger.click()
            page.evaluate('() => history.back()')
            expect(page.locator('.gallery-view')).to_be_visible()
            expect(dialog).not_to_be_visible()
            expect(page.locator('#view-title')).to_be_focused()
            page.evaluate('() => history.forward()')
            trigger.click()
            dialog.get_by_label('个人草稿', exact=True).fill('saved before closing')
            expect(dialog.locator('.draft-state')).to_contain_text('已保存到项目')
            dialog.get_by_role('button', name='关闭', exact=True).click()
            trigger.click()
            expect(dialog.get_by_label('个人草稿', exact=True)).to_have_value('saved before closing')
            assert errors == []
            browser.close()
    finally:
        server.stop()


def test_recovery_dialog_tracks_replacement_owner_and_blocks_history_under_quota(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.start() + 'studio/'); open_operations(page)
            page.evaluate("""async () => {const {post}=await import('/v2/api.js');const e=observedDraft;await e.ready;
              for(const id of ['one','two']) {const draft=structuredClone(e.draft);draft.draft_id=id;draft.content.text=id;
                await post('/api/drafts/save',{draft});} await e.load();window.previousDraft=e;} """)
            page.get_by_label('恢复项目中的个人草稿', exact=True).select_option('two')
            note = page.get_by_label('个人草稿', exact=True)
            expect(note).to_have_value('two')
            assert page.evaluate('() => previousDraft.disposed && observedDraft !== previousDraft')
            page.route('**/api/drafts/save', lambda route: route.abort())
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
            note.fill('replacement unsent')
            expect(page.locator('.draft-state')).to_contain_text('待核实')
            dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            expect(dialog).to_be_visible()
            note.press('Escape'); expect(dialog).to_be_visible()
            page.evaluate('() => history.back()')
            expect(note).to_have_value('replacement unsent')
            expect(dialog).to_be_visible()
            page.evaluate('() => history.forward()')
            expect(note).to_have_value('replacement unsent')
            expect(dialog).to_be_visible()
            with page.expect_download():
                dialog.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            note.press('Escape'); expect(dialog).to_be_visible()
            dialog.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            page.evaluate('() => history.back()')
            expect(dialog).not_to_be_visible()
            expect(page.locator('#view-title')).to_be_focused()
            assert errors == []
            browser.close()
    finally:
        server.stop()


@pytest.mark.parametrize('failure', ['offline', 'dependency'])
def test_module_recovery_reload_is_guarded_and_rebuilds_module_state(tmp_path, failure):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_inputs(page)
            page.route('**/api/drafts/save', lambda route: route.abort())
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
            page.get_by_label('用途与目标', exact=True).fill('unknown original')
            expect(page.locator('.draft-state')).to_contain_text('待核实')
            page.get_by_label('用途与目标', exact=True).fill('unsent current')
            original = page.request.get(server.start() + 'v2/gallery.js').text()
            def faulty(route):
                if failure == 'offline':
                    route.abort('internetdisconnected')
                else:
                    route.fulfill(content_type='text/javascript', body=original + "\nimport './module-recovery-probe.js';")
            page.route('**/v2/gallery.js', faulty)
            page.route('**/v2/module-recovery-probe.js', lambda route: route.fulfill(content_type='text/javascript', body='throw new Error("dependency failed");'))
            page.get_by_role('button', name='整稿画廊', exact=True).click()
            reload = page.get_by_role('button', name='重新加载工作台', exact=True)
            expect(reload).to_be_visible()
            failed_target = page.url
            page.unroute('**/v2/gallery.js', faulty)
            documents = []
            page.on('request', lambda request: documents.append(request.url) if request.is_navigation_request() else None)
            reload.click()
            expect(page.get_by_label('用途与目标', exact=True)).to_have_value('unsent current')
            assert documents == []
            page.get_by_role('button', name='更多内容工具', exact=True).click()
            page.get_by_role('button', name='工作笔记', exact=True).click()
            with page.expect_download() as saved:
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            recovery = json.loads(Path(saved.value.path()).read_text())
            assert recovery['draft']['content']['content_sources']['brief'] == 'unsent current'
            assert recovery['pending_save']['draft']['content']['content_sources']['brief'] == 'unknown original'
            reload.click()
            assert documents == []
            page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
            writes = []
            page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' else None)
            with page.expect_request('**/v2/gallery.js'):
                reload.click()
            expect(page.locator('.gallery-view')).to_be_visible()
            assert page.url == failed_target
            assert not any(url.endswith('/api/drafts/save') for url in writes)
            # A superseded failure control cannot reload a different surface.
            page.reload()
            expect(page.locator('.gallery-view')).to_be_visible()
            browser.close()
    finally:
        server.stop()


def test_module_failure_control_expires_after_another_target_commits(tmp_path):
    server = WorkbenchServer(project_at(tmp_path))
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(); page.goto(server.start() + 'studio/'); open_inputs(page)
            page.route('**/v2/gallery.js', lambda route: route.fulfill(status=404, body='unavailable'))
            page.get_by_role('button', name='整稿画廊', exact=True).click()
            expect(page.get_by_role('button', name='重新加载工作台', exact=True)).to_be_visible()
            page.evaluate("() => {window.oldModuleReload=[...document.querySelectorAll('button')].find(b=>b.textContent==='重新加载工作台');}")
            # Overview itself imports gallery.js; use an unrelated module graph
            # to prove a successful navigation expires the old failure lease.
            page.get_by_role('button', name='任务与交付', exact=True).click()
            expect(page.locator('#view-title')).to_have_text('任务与交付')
            marker = page.evaluate('() => {window.documentMarker=crypto.randomUUID();return documentMarker;}')
            page.evaluate('() => oldModuleReload.click()')
            assert page.evaluate('() => documentMarker') == marker
            expect(page.locator('#view-title')).to_have_text('任务与交付')
            browser.close()
    finally:
        server.stop()
