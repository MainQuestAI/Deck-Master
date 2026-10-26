"""RP-10: actual Chromium plan editing and independent evidence states, no Host calls."""
import shutil
import re
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect, sync_playwright
from deck_master import content_insight, ui_journal
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_studio_content_browser import authorize_content_edits
from test_webui_acceptance_matrix import commit_fixture

pytestmark = pytest.mark.browser


def open_plan(page, url, route):
    identity = page.request.get(url + 'api/project').json()['project_identity']
    page.goto(url + route + '/#' + urlencode({'project': identity, 'surface': 'content', 'layer': 'content'}))
    if route == 'studio':
        page.get_by_role('navigation', name='内容工作区').get_by_role('button', name='章节与计划', exact=True).click()
    else:
        page.get_by_text('编辑内容计划', exact=True).click()


@pytest.mark.parametrize('route', ['v2', 'studio'])
def test_plan_editor_mount_save_reopen_and_conflict(tmp_path, route):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    authorize_content_edits(project)
    store = Store(project)
    before = store.load_document()
    original = store.read_object_json(before['content_plan'])['input']
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            open_plan(page, server.start(), route)
            expect(page.locator('body')).not_to_contain_text('[object HTML')
            chapter = page.get_by_label('章节名称 1', exact=True)
            expect(chapter).to_be_visible()
            chapter.fill('RP-10 修改后的章节')
            if route == 'studio':
                page.locator('.studio-goal-card').last.get_by_role('button', name='编辑页面目标', exact=True).click()
            goal = page.get_by_label(re.compile('^页面目标 ')).last
            goal.fill('RP-10 保留原事实的新目标')
            page.get_by_role('button', name='预览内容计划变更', exact=True).click()
            submit = page.get_by_role('button', name='确认内容变更', exact=True)
            expect(submit).to_be_enabled()
            differences = page.get_by_role('list', name='具体字段变更', exact=True)
            expect(differences).to_contain_text(original['chapters'][0]['title'] + ' → RP-10 修改后的章节')
            expect(differences).to_contain_text('第 24 页')
            expect(differences).to_contain_text(original['page_roles'][-1]['intended_takeaway'] + ' → RP-10 保留原事实的新目标')
            assert store.load_document() == before
            # Editing after preview cancels that pending plan in either route.
            chapter.fill('RP-10 修改后的章节（二）')
            expect(submit).to_be_disabled()
            expect(page.get_by_role('list', name='具体字段变更', exact=True)).to_have_count(0)
            assert store.load_document() == before
            page.get_by_role('button', name='预览内容计划变更', exact=True).click()
            expect(submit).to_be_enabled()
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/api/content/commit')) as response:
                submit.click()
            assert response.value.ok
            saved = store.load_document()
            current = store.read_object_json(saved['content_plan'])['input']
            assert current['chapters'][0]['title'] == 'RP-10 修改后的章节（二）'
            assert current['page_roles'][-1]['intended_takeaway'] == 'RP-10 保留原事实的新目标'
            for key in ['page_budget', 'time_budget', 'speech_policy', 'issues', 'tradeoff_issue_ids', 'page_order']:
                assert current[key] == original[key]
            assert current['page_roles'][:-1] == original['page_roles'][:-1]
            assert saved['pages'] == before['pages'] and saved['tasks'] == before['tasks']
            open_plan(page, server.start(), route)
            expect(page.get_by_label('章节名称 1', exact=True)).to_have_value('RP-10 修改后的章节（二）')
            page.get_by_label('章节名称 1', exact=True).fill('不得覆盖并发版本')
            page.get_by_role('button', name='预览内容计划变更', exact=True).click()
            expect(submit).to_be_enabled()
            advanced = commit_fixture(store, lambda d: None, 'rp10-concurrent')
            submit.click()
            expect(page.get_by_role('dialog')).to_be_visible()
            assert store.load_document() == advanced
            assert store.load_document()['content_plan'] == saved['content_plan']
            assert not errors
            page.screenshot(path=str(tmp_path / (route + '-conflict.png')), full_page=True)
            browser.close()
    finally:
        server.stop()


@pytest.mark.parametrize('route', ['v2', 'studio'])
def test_imported_mapping_without_narrative_is_not_missing_mapping(tmp_path, route):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    before = store.load_document()
    page_id = before['pages'][0]['page_id']
    data = content_insight.evidence(project, page_id)['data']
    assert data['alignment'] == 'not_recorded'
    assert any(atom['mapping_status'] == 'recorded' for atom in data['elements'])
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            identity = ui_journal.project_info(project)['project_identity']
            target = {'project': identity, 'surface': 'page', 'page': page_id, 'layer': 'content', 'revision': before['revision_id']}
            page.goto(server.start() + route + '/#' + urlencode(target))
            page.locator('.source-inspector > summary').click()
            expect(page.get_by_role('heading', name='正文与证据', exact=True)).to_be_visible()
            expect(page.get_by_text('此页未绑定论证主线；原子映射和来源关联按下方记录分别展示。', exact=True)).to_be_visible()
            expect(page.locator('.insight-node').first).to_contain_text('已记录映射')
            expect(page.locator('body')).not_to_contain_text('此页未记录原子映射')
            assert store.load_document() == before
            page.screenshot(path=str(tmp_path / (route + '-evidence.png')), full_page=True)
            browser.close()
    finally:
        server.stop()


@pytest.mark.parametrize('route', ['v2', 'studio'])
@pytest.mark.parametrize('has_plan', [False, True])
def test_empty_pages_with_or_without_plan_remain_readable(tmp_path, route, has_plan):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    def clear_pages(document):
        document['pages'] = []
        if not has_plan:
            document.pop('content_plan', None)
    commit_fixture(store, clear_pages, 'rp10-empty-state')
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.start() + route + '/')
            page.get_by_role('button', name='内容与页序', exact=True).click()
            if route == 'studio':
                page.get_by_role('navigation', name='内容工作区').get_by_role('button', name='章节与计划', exact=True).click()
            elif has_plan:
                page.get_by_text('编辑内容计划', exact=True).click()
            expect(page.locator('body')).not_to_contain_text('[object HTML')
            if has_plan:
                expect(page.get_by_label('章节名称 1', exact=True)).to_be_visible()
                expect(page.get_by_label(re.compile('^页面目标 ')).first).to_be_attached()
                if route == 'studio':
                    expect(page.locator('.studio-goal-card').first).to_contain_text('第 1 页')
                    expect(page.locator('.studio-goal-card')).not_to_contain_text(['第 0 页'] * 24)
            else:
                expect(page.get_by_text('尚未记录完整内容计划。', exact=True)).to_be_visible()
            assert not errors and store.load_document() == before
            browser.close()
    finally:
        server.stop()
