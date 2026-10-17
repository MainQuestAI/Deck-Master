"""Real browser/HTTP/native-file checks; synthetic content, no model calls."""
import json
import shutil
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import exports
from deck_master.compiler.native import normalize_notes, notes_records
from deck_master.web import WorkbenchServer
from test_rc3_notes_files import TEXTS, _attach_compiled, _project

pytestmark = pytest.mark.browser

LABELS = {
    'pptx_notes': '写入 PPT 备注',
    'separate_script': '单独导出口播稿',
    'both': 'PPT 备注和独立口播稿',
    'pure_reading': '纯阅读稿（不含口播）',
}


@pytest.fixture
def notes_browser(tmp_path):
    project, store, inputs = _project(tmp_path)
    original = _attach_compiled(store, inputs, tmp_path).pptx_path.read_bytes()
    before = store.load_document()
    server = WorkbenchServer(project)
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server.start(), project, store
            assert store.load_document() == before
            artifact = store.read_object_json(before['outputs']['pptx'])
            assert store.read_object_bytes(artifact['file']) == original
            assert errors == []
        finally:
            browser.close()
            server.stop()


def open_files(page, url, ui='studio'):
    page.goto(url + ui + '/')
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='文件', exact=True).click()
    return page.locator('#delivery-desk')


def choose(page, files, policy):
    with page.expect_response(lambda response: '/delivery-eligibility?' in response.url
                              and parse_qs(urlparse(response.url).query).get('notes_policy') == [policy]):
        files.get_by_role('combobox', name='口播稿保留方式').select_option(policy)
    expect(files.locator('.export-group').get_by_role('status')).to_contain_text('本次方式：' + LABELS[policy])


@pytest.mark.parametrize('ui', ['studio', 'v2'])
def test_web_notes_choices_match_preflight_and_actual_files(notes_browser, tmp_path, ui):
    page, url, project, store = notes_browser
    files = open_files(page, url, ui)
    expect(files.get_by_role('combobox', name='口播稿保留方式')).to_have_value('')
    expect(files.locator('.export-group').get_by_role('status')).to_contain_text('本次方式：写入 PPT 备注')
    for policy, label in LABELS.items():
        choose(page, files, policy)
        with page.expect_request(lambda request: request.method == 'POST' and request.url.endswith('/api/exports')) as sent:
            files.get_by_role('button', name='生成审阅包', exact=True).click()
        request = sent.value.post_data_json
        assert request['notes_policy'] == policy
        assert request['revision'] == store.current_revision_id()
        row = files.locator('.export-results > .export-result').first
        expect(row.get_by_role('link', name='下载 ZIP', exact=True)).to_be_visible()
        expect(row.locator('.export-notes-policy')).to_have_text(label)
        packet = exports.show(project, export_id=request['export_id'])
        assert packet['manifest']['notes_policy']['selection'] == policy
        data, _ = exports.download(project, export_id=request['export_id'], filename='deck.pptx')
        expected = [normalize_notes(text) for text in TEXTS] if policy in ('pptx_notes', 'both') else ['', '', '']
        assert [record['notes'] for record in notes_records(data)] == expected
        has_script = policy in ('separate_script', 'both')
        assert ('speaker-script.txt' in packet['files']) == has_script
        expect(row.get_by_role('link', name='下载口播稿', exact=True)).to_have_count(int(has_script))
        if has_script:
            script, _ = exports.download(project, export_id=request['export_id'], filename='speaker-script.json')
            assert [item['notes'] for item in json.loads(script)['pages']] == [normalize_notes(text) for text in TEXTS]
    # The same choice remains keyboard accessible on a narrow screen.
    page.set_viewport_size({'width': 390, 'height': 844})
    choice = files.get_by_role('combobox', name='口播稿保留方式')
    choice.focus()
    expect(choice).to_be_focused()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.screenshot(path=str(tmp_path / f'notes-export-{ui}-390.png'), full_page=True)


@pytest.mark.parametrize('committed', [False, True])
def test_unknown_export_retains_policy_across_reload_and_changed_selection(notes_browser, committed):
    page, url, project, _ = notes_browser
    files = open_files(page, url)
    choose(page, files, 'both')
    requests = []

    def interrupt(route):
        requests.append(route.request.post_data_json)
        if committed:
            route.fetch()  # Real export commits, but its acknowledgement is lost.
        route.abort('failed')

    page.route('**/api/exports', interrupt)
    files.get_by_role('button', name='生成审阅包', exact=True).click()
    expect(files.locator('.export-results')).to_contain_text('生成结果待核实')
    assert len(requests) == 1 and requests[0]['notes_policy'] == 'both'
    page.unroute('**/api/exports', interrupt)
    page.reload()
    files = page.locator('#delivery-desk')
    choose(page, files, 'pure_reading')
    pending = files.locator('.export-results > .export-result').first
    expect(pending.locator('.export-notes-policy')).to_have_text(LABELS['both'])
    pending.get_by_role('button', name='核实这个文件包', exact=True).click()
    if not committed:
        retry = pending.get_by_role('button', name='按原版本重试生成', exact=True)
        expect(retry).to_be_visible()
        with page.expect_request(lambda request: request.method == 'POST' and request.url.endswith('/api/exports')) as sent:
            retry.click()
        assert sent.value.post_data_json == requests[0]
    expect(pending.get_by_role('link', name='下载口播稿', exact=True)).to_be_visible()
    packet = exports.show(project, export_id=requests[0]['export_id'])
    assert packet['manifest']['notes_policy']['selection'] == 'both'
    expect(files.get_by_role('combobox', name='口播稿保留方式')).to_have_value('pure_reading')


def test_late_preflight_cannot_replace_new_notes_selection(notes_browser):
    page, url, _, _ = notes_browser
    files = open_files(page, url)
    delayed = []

    def hold(route):
        delayed.append((route, route.fetch()))

    page.route('**/delivery-eligibility?*notes_policy=pptx_notes', hold)
    files.get_by_role('combobox', name='口播稿保留方式').select_option('pptx_notes')
    choose(page, files, 'pure_reading')
    assert len(delayed) == 1
    route, response = delayed[0]
    route.fulfill(response=response)
    # Wait for the old response to be consumed, then read the visible judgement.
    page.wait_for_load_state('networkidle')
    expect(files.locator('.export-group').get_by_role('status')).to_contain_text(LABELS['pure_reading'])
    detail = files.get_by_label('所选实际文件的交付判断')
    detail.locator('summary').click()
    expect(detail).to_contain_text('pure_reading')
