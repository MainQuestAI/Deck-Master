"""Recovery custody uses the same content restrictions as product import."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import ui_journal
from deck_master.samples import create_sample
from deck_master.web import WorkbenchServer
from test_main_iteration_browser import open_operations, project_at

pytestmark = pytest.mark.browser
CONTENT_ERROR = '恢复文件包含当前导入入口不接受的内容，尚不能确认保管并离开'


@pytest.fixture
def portable_browser(tmp_path):
    project = project_at(tmp_path)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            page.goto(server.start() + 'studio/')
            open_operations(page)
            try:
                yield page, project
            finally:
                browser.close()
    finally:
        server.stop()


def fail_saves_and_buffer(page):
    sent = []
    def fail(route):
        sent.append(route.request.post_data_json)
        route.abort()
    page.route('**/api/drafts/save', fail)
    page.evaluate("""() => {Storage.prototype.setItem=function(){
        throw new DOMException('quota', 'QuotaExceededError');
    };}""")
    return sent


def snapshot(page):
    return page.evaluate("""() => ({draft:observedDraft.draft,
        pendingSave:observedDraft.pendingSave, status:observedDraft.status})""")


def rejected_download(page):
    downloads = []
    page.on('download', lambda download: downloads.append(download))
    page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
    expect(page.locator('.personal-draft .field-error')).to_contain_text(CONTENT_ERROR)
    assert downloads == []
    expect(page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True)).to_be_hidden()
    assert page.evaluate('() => [observedDraft.downloadedRecovery, observedDraft.confirmedRecovery]') == [None, None]


@pytest.mark.parametrize('sent,current', [
    ('/help', '/help'),
    ('正常原稿', '/help'),
    ('/help', '当前正常中文😀'),
], ids=['both', 'current-only', 'pending-only'])
def test_unimportable_content_never_grants_recovery_custody(portable_browser, sent, current):
    page, _ = portable_browser
    requests = fail_saves_and_buffer(page)
    note = page.get_by_label('个人草稿', exact=True)
    note.fill(sent)
    expect(page.locator('.draft-state')).to_contain_text('待核实')
    if current != sent:
        note.fill(current)
    before = snapshot(page)
    assert before['pendingSave'] == requests[0]
    downloads = []
    page.on('download', lambda download: downloads.append(download))
    page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
    page.wait_for_function("""message => typeof observedDraft.downloadedRecovery === 'string' ||
        observedDraft.note === message""", arg=CONTENT_ERROR)
    assert downloads == [], 'An unimportable recovery file was downloaded'
    expect(page.locator('.personal-draft .field-error')).to_contain_text(CONTENT_ERROR)
    expect(page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True)).to_be_hidden()
    assert snapshot(page) == before
    expect(note).to_have_value(current)
    dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
    dialog.get_by_role('button', name='关闭', exact=True).click()
    expect(dialog).to_be_visible()
    assert len(requests) == 1


@pytest.mark.parametrize('confirmed', [False, True], ids=['downloaded', 'confirmed'])
def test_invalid_edit_revokes_custody_and_remains_protected(portable_browser, confirmed):
    page, _ = portable_browser
    requests = fail_saves_and_buffer(page)
    note = page.get_by_label('个人草稿', exact=True)
    note.fill('合法原稿中文😀')
    expect(page.locator('.draft-state')).to_contain_text('待核实')
    with page.expect_download():
        page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
    custody = page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True)
    if confirmed:
        custody.click()
    note.fill('/help')
    before = snapshot(page)
    rejected_download(page)
    dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
    dialog.get_by_role('button', name='关闭', exact=True).click()
    expect(dialog).to_be_visible()
    note.press('Escape')
    expect(dialog).to_be_visible()
    original_url = page.url
    page.evaluate('() => {window.recoveryOwner = observedDraft;}')
    page.evaluate('() => history.back()')
    expect(page.locator('.banners .notice')).to_contain_text('本机恢复副本未保存，仍保留原工作面')
    expect(page.locator('#main')).not_to_have_attribute('aria-busy', 'true')
    expect(page).to_have_url(original_url)
    expect(dialog).to_be_visible()
    expect(note).to_have_value('/help')
    # The rejected back replaces its entry with the original route. Forward
    # selects that same route; await the actual traversal, not an early DOM read.
    assert page.evaluate("""() => new Promise(resolve => {
        const hash=location.hash;
        addEventListener('popstate',()=>resolve(location.hash===hash),{once:true});
        history.forward();
    })""")
    expect(page).to_have_url(original_url)
    expect(dialog).to_be_visible()
    assert page.evaluate('() => observedDraft === recoveryOwner && !observedDraft.disposed')
    assert snapshot(page) == before
    assert before['pendingSave'] == requests[0]
    # Returning to the exact earlier body must not resurrect its old consent.
    note.fill('合法原稿中文😀')
    expect(custody).to_be_hidden()
    note.press('Escape')
    expect(dialog).to_be_visible()
    with page.expect_download():
        page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
    custody.click()
    note.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('button', name='个人记录与操作恢复', exact=True)).to_be_focused()
    assert len(requests) == 1


def test_pending_request_change_revokes_custody_without_changing_body(portable_browser):
    page, project = portable_browser
    requests = fail_saves_and_buffer(page)
    note = page.get_by_label('个人草稿', exact=True)
    note.fill('当前个人正文')
    expect(page.locator('.draft-state')).to_contain_text('待核实')
    before = snapshot(page)
    with page.expect_download():
        page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
    page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
    # A separate writer commits a different real journal record. The product's
    # verify request observes that conflict and retires only the pending save.
    original = requests[0]['draft']
    ui_journal.save(project, draft={**original, 'content': {**original['content'], 'text': '另一窗口已保存'}})
    page.get_by_role('button', name='核实草稿保存', exact=True).click()
    expect(page.locator('.draft-state')).to_contain_text('保存冲突')
    after = snapshot(page)
    assert after['draft'] == before['draft'] and after['pendingSave'] is None
    assert page.evaluate('() => [observedDraft.downloadedRecovery, observedDraft.confirmedRecovery]') == [None, None]
    expect(note).to_have_value('当前个人正文')
    dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
    dialog.get_by_role('button', name='关闭', exact=True).click()
    expect(dialog).to_be_visible()


def test_offline_content_rejection_needs_no_http_preflight(portable_browser):
    page, _ = portable_browser
    requests = fail_saves_and_buffer(page)
    note = page.get_by_label('个人草稿', exact=True)
    note.fill('/help')
    expect(page.locator('.draft-state')).to_contain_text('待核实')
    before = snapshot(page)
    outgoing = []
    page.on('request', lambda request: outgoing.append(request.url))
    page.context.set_offline(True)
    rejected_download(page)
    assert snapshot(page) == before
    assert outgoing == []
    assert len(requests) == 1


def test_rejected_recovery_cannot_bypass_beforeunload(portable_browser):
    page, _ = portable_browser
    fail_saves_and_buffer(page)
    note = page.get_by_label('个人草稿', exact=True)
    note.fill('/help')
    expect(page.locator('.draft-state')).to_contain_text('待核实')
    rejected_download(page)
    page.once('dialog', lambda dialog: dialog.dismiss())
    with page.expect_event('dialog') as prompt:
        page.evaluate('() => location.reload()')
    assert prompt.value.type == 'beforeunload' and not page.is_closed()
    expect(note).to_have_value('/help')
    expect(page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)).to_be_visible()


def test_readonly_unsent_buffer_keeps_close_and_escape_protection(tmp_path):
    project = tmp_path / 'readonly'
    create_sample(project, page_count=1, readonly=True)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.goto(server.start() + 'studio/')
            open_operations(page)
            # A previously unsent persisted buffer is fixture input to the real
            # readonly loader; no live DraftEditor fields are overwritten.
            page.evaluate("""() => {const e=observedDraft, draft=structuredClone(e.draft);
                draft.content.text='/help';
                localStorage.setItem(e.activeKey,JSON.stringify({draft,etag:null,status:'dirty',pendingSave:null}));
            }""")
            page.reload()
            page.get_by_role('button', name='个人记录与操作恢复', exact=True).click()
            note = page.get_by_label('个人草稿', exact=True)
            expect(note).to_have_value('/help')
            expect(note).to_have_js_property('readOnly', True)
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError');};}")
            downloads = []
            page.on('download', lambda download: downloads.append(download))
            page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            expect(page.locator('.personal-draft .field-error')).to_contain_text(CONTENT_ERROR)
            assert downloads == []
            expect(page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True)).to_be_hidden()
            dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            expect(dialog).to_be_visible()
            note.press('Escape')
            expect(dialog).to_be_visible()
            expect(note).to_have_value('/help')
            browser.close()
    finally:
        server.stop()


def test_recovery_content_validator_matches_backend_json_rules(portable_browser):
    page, _ = portable_browser
    forbidden = ['token', 'authorization', 'x-deck-token', 'cookie', 'command', 'cwd', 'absolute_path', 'file_path']
    rejected = [{key: 'value'} for key in forbidden] + [{key.upper(): 'value'} for key in forbidden]
    rejected += [
        {'toKen': 'value'},
        {'draft': {'pending': {'payload': [{'CoMmAnD': 'value'}]}}},
        {'pending_save': {'draft': {'content': {'nested': [{'file_path': 'value'}]}}}},
        {'pending_save': {'authorization': 'value', 'draft': {'content': {'text': 'safe'}}}},
        '/help', 'file://fixture', '\\\\fixture', 'C:\\fixture', ':\\fixture',
        'xx:\\fixture', '😀😀:\\fixture', '\n:\\fixture',
        {'pending_save': {'draft': {'content': {'text': '/help'}}}},
    ]
    accepted = [None, True, 0, [], {}, {'Token ': 'value'}, {'tokenized': 'value'},
                ' /help', 'FILE://fixture', '\\fixture', 'xxx:\\fixture',
                '😀😀x:\\fixture', 'normal中文😀', {'nested': [None, 0, {'text': 'a/b'}]}]
    vectors = [(value, False) for value in rejected] + [(value, True) for value in accepted]
    for value, expected in vectors:
        try:
            ui_journal._portable(value)
            backend = True
        except ui_journal.LocalStateError:
            backend = False
        assert backend is expected, repr(value)
    actual = page.evaluate("""async values => {const {validateRecoveryContent}=await import('/v2/drafts.js');
        return values.map(value=>{try {validateRecoveryContent(value);return true;} catch {return false;}});
    }""", [value for value, _ in vectors])
    assert actual == [expected for _, expected in vectors]


@pytest.mark.parametrize('sent,current', [
    ('正常原稿中文😀', '当前中文与emoji😀稿'),
    ('FILE://kept-as-text', '😀😀x:\\kept-as-text'),
], ids=['utf8', 'allowed-near-match'])
def test_portable_recovery_keeps_product_download_import_roundtrip(portable_browser, sent, current):
    page, project = portable_browser
    requests = fail_saves_and_buffer(page)
    note = page.get_by_label('个人草稿', exact=True)
    note.fill(sent)
    expect(page.locator('.draft-state')).to_contain_text('待核实')
    note.fill(current)
    with page.expect_download() as saved:
        page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
    downloaded = Path(saved.value.path())
    recovery = json.loads(downloaded.read_text())
    assert recovery['draft']['content']['text'] == current
    assert recovery['pending_save'] == requests[0]
    assert recovery['digest'] == ui_journal.digest(recovery['draft'])
    assert recovery['pending_save_digest'] == ui_journal.digest(requests[0])
    dialog = page.get_by_role('dialog', name='个人记录与操作恢复', exact=True)
    dialog.get_by_role('button', name='关闭', exact=True).click()
    expect(dialog).to_be_visible()
    page.get_by_role('button', name='我已保管恢复文件，允许离开', exact=True).click()
    dialog.get_by_role('button', name='关闭', exact=True).click()
    expect(dialog).not_to_be_visible()
    importer = page.context.new_page()
    importer.goto(page.url.split('studio/')[0] + 'studio/')
    open_operations(importer)
    posts = []
    importer.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
    with importer.expect_response('**/api/drafts/import') as imported:
        importer.get_by_label('导入草稿恢复文件', exact=True).set_input_files(downloaded)
    result = imported.value.json()
    assert imported.value.status == 200 and result['preserved_pending_save']
    assert result['record']['draft'] == recovery['draft']
    assert len(ui_journal.list_drafts(project)['records']) == 1
    assert not any(url.endswith('/api/drafts/save') for url in posts)
    assert len(requests) == 1
