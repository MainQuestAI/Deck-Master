"""D06a real HTTP/Chromium writes, synthetic legal Runtime objects; no model calls."""
import shutil
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import ui_journal, local_runtime
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_business_framing import proposals
from test_workbench_services import launcher_service

pytestmark = pytest.mark.browser


def visit(page, url, path, store, ref):
    page.goto(url + 'studio/#' + urlencode({'project': ui_journal.project_info(path)['project_identity'],
        'surface': 'content', 'layer': 'content', 'revision': store.current_revision_id(),
        'content_area': 'arguments', 'proposal': ref['sha256']}))


@pytest.mark.parametrize('size', [(1280, 800), (1440, 900), (390, 844)])
def test_read_edit_recover_and_adopt_exact_pair(tmp_path, size):
    path, store, refs = proposals(tmp_path)
    server = WorkbenchServer(path);url = server.start();errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': size[0], 'height': size[1]})
            page.on('pageerror', lambda e: errors.append(str(e)))
            visit(page, url, path, store, refs[0])
            expect(page.locator('.business-frame')).to_contain_text('Explain the actual operating change')
            expect(page.locator('.business-topic')).to_contain_text('说明交出什么以及谁接手')
            page.get_by_role('button', name='修订这份框架', exact=True).click()
            page.get_by_label('主题 1 名称', exact=True).fill('确认条件后接手')
            page.get_by_label('修订理由', exact=True).fill('合成作者修订：明确业务交接含义。')
            page.keyboard.press('Escape');page.reload()
            page.get_by_role('button', name='恢复框架修订草稿', exact=True).click()
            expect(page.get_by_label('主题 1 名称', exact=True)).to_have_value('确认条件后接手')
            def lose(route):
                response = route.fetch();assert response.ok
                route.abort('failed')
            page.route('**/api/content/outline-revisions', lose, times=1)
            page.get_by_role('button', name='保存修订候选', exact=True).click()
            expect(page.get_by_role('button', name='核实原修订操作', exact=True)).to_be_enabled()
            current = store.load_document();task_count = len(current['tasks'])
            assert task_count == 3 and current.get('narrative') is None and not current['pages']
            page.reload();page.get_by_role('button', name='恢复框架修订草稿', exact=True).click()
            page.get_by_role('button', name='核实原修订操作', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('修订候选已保存')
            assert len(store.load_document()['tasks']) == task_count
            revised = store.read_object_json(store.load_document()['tasks'][-1])['result_refs']
            page.get_by_role('button', name='阅读并比较修订候选', exact=True).click()
            expect(page.locator('.business-topic')).to_have_count(2)
            assert page.get_by_role('button', name='采用主线与计划', exact=True).count() == 0
            visit(page, url, path, store, revised[0])
            expect(page.locator('.business-topic')).to_have_count(1)
            expect(page.locator('.business-topic')).to_contain_text('确认条件后接手')
            page.get_by_role('button', name='采用主线与计划', exact=True).click()
            page.get_by_label('采用这份主线与计划的理由', exact=True).fill('合成作者确认这一份修订及匹配计划。')
            page.route('**/collaboration/proposal-adoptions', lose, times=1)
            page.get_by_role('button', name='确认采用主线与计划', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('采用尚未确认完成')
            assert store.load_document()['narrative'] == revised[0]
            assert store.load_document().get('content_plan') != revised[1]
            page.reload();page.get_by_role('button', name='核实原主线与计划采用', exact=True).click()
            page.get_by_role('button', name='核实并继续原采用操作', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('主线与匹配计划已采用')
            current = store.load_document()
            assert current['narrative'] == revised[0] and current['content_plan'] == revised[1]
            assert len(current['collaboration']['decisions']) == 1 and len(current['tasks']) == task_count
            assert not current['pages']
            page.get_by_role('button', name='阅读采用后的固定版本', exact=True).click()
            expect(page.locator('.business-outline-actions')).to_contain_text('当前主线与匹配计划已采用')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path / f'paired-outline-{size[0]}.png'), full_page=True)
            assert not errors
            browser.close()
    finally:server.stop()


def test_launcher_preserves_business_task_without_calling_model(launcher_service, tmp_path, request):
    request.addfinalizer(lambda: local_runtime.stop(local_runtime.descriptor(project=tmp_path / 'commercial-project')))
    _, _, state = launcher_service
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.goto(state['url']);page.get_by_role('button', name='新建项目', exact=True).click()
        dialog = page.get_by_role('dialog', name='新建项目')
        for label, text in [('项目名称（必填）', '业务框架合成验证'), ('用途（必填）', '让客户选择适合当前流程的试点方案'),
            ('受众（必填）', '业务负责人'), ('交流场景（可选）', '首次提案，先说明业务如何使用'),
            ('已有共识与既定框架（可选，每行一条）', '保留人工改善流程作为真实选项\n已确认按使用链说明'),
            ('保存到哪个文件夹（必填）', str(tmp_path)), ('新项目文件夹名（必填）', 'commercial-project')]:
            dialog.get_by_label(label, exact=True).fill(text)
        dialog.get_by_label('本次约定产物', exact=True).select_option('plan_only')
        with page.expect_response('**/api/projects/create') as response:
            dialog.get_by_role('button', name='创建项目', exact=True).click()
        assert response.value.ok, response.value.text()
        result = response.value.json();assert result['model_started'] is False
        store = Store(tmp_path / 'commercial-project');doc = store.load_document()
        assert doc['task']['scenario'] == '首次提案，先说明业务如何使用'
        assert doc['task']['existing_decisions'] == ['保留人工改善流程作为真实选项', '已确认按使用链说明']
        task = store.read_object_json(doc['tasks'][0])
        assert 'business-framing.v1' in task['required_capabilities'] and task['status'] == 'awaiting_host'
        assert not doc['pages']
        browser.close()


def test_concurrent_change_preserves_draft_until_explicit_new_basis(tmp_path):
    from test_workbench_reads import commit
    path, store, refs = proposals(tmp_path);server = WorkbenchServer(path);url = server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page();visit(page, url, path, store, refs[0])
            page.get_by_role('button', name='修订这份框架', exact=True).click()
            page.get_by_label('主题 1 含义', exact=True).fill('已知条件确认后由明确责任人接手')
            page.get_by_label('修订理由', exact=True).fill('并发修改后仍保留作者草稿。')
            changed = store.load_document();changed['task']['title'] = 'Synthetic concurrent title'
            commit(store, changed, 'browser-concurrent-title')
            page.get_by_role('button', name='保存修订候选', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('修订尚未确认完成')
            assert len(store.load_document()['tasks']) == 2
            page.get_by_role('button', name='保留草稿并核对当前版本', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('当前准入已核对')
            expect(page.get_by_label('主题 1 含义', exact=True)).to_have_value('已知条件确认后由明确责任人接手')
            page.get_by_role('button', name='保存修订候选', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('修订候选已保存')
            assert len(store.load_document()['tasks']) == 3 and store.load_document().get('narrative') is None
            browser.close()
    finally:server.stop()


def test_unavailable_local_storage_does_not_publish_unrecoverable_edit(tmp_path):
    path, store, refs = proposals(tmp_path);server = WorkbenchServer(path);url = server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=['--no-sandbox']);page = browser.new_page();errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            visit(page, url, path, store, refs[0]);page.get_by_role('button', name='修订这份框架', exact=True).click()
            page.evaluate("() => {Storage.prototype.setItem=function(){throw new DOMException('quota','QuotaExceededError')};}")
            page.get_by_label('主题 1 名称', exact=True).fill('本机暂存失败仍保留的交接')
            page.get_by_label('修订理由', exact=True).fill('合成存储故障验证。')
            expect(page.get_by_role('dialog')).to_contain_text('本机草稿尚未保存')
            page.get_by_role('button', name='保存修订候选', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('修订尚未确认完成')
            expect(page.get_by_label('主题 1 名称', exact=True)).to_have_value('本机暂存失败仍保留的交接')
            assert len(store.load_document()['tasks']) == 2 and not errors
            browser.close()
    finally:server.stop()
