"""U05 seven real work surfaces and transaction recovery, synthetic data only."""
import copy
import json
import re
import uuid

import pytest

from deck_master import candidates, local_runtime, registry, tasks
from deck_master.store import Store
from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer
from test_action_targets_browser import action_browser  # noqa: F401
from test_candidates import accept, candidate, dispatch, envelope, start
from test_ui_design_browser import workbench_page  # noqa: F401
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


def test_seven_surfaces_at_all_acceptance_sizes(workbench_page, tmp_path):
    from playwright.sync_api import expect
    page = workbench_page
    project = tmp_path / 'sample'
    store = Store(project)
    before = store.read_current()
    reg = tmp_path / 'registry.json'
    registry.register(reg, project)
    descriptor = local_runtime.descriptor(registry=reg)
    launcher = local_runtime.ensure(descriptor)
    project_url = page.url
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    checks = []
    try:
        for surface, title in [('launcher', '项目'), ('overview', '制作总览'), ('content', '内容与来源'),
                               ('gallery', '整稿画廊'), ('page', None), ('style', '风格校准'), ('runs', '任务与交付')]:
            if surface == 'launcher':
                page.goto(launcher['url'])
            elif surface == 'overview':
                page.goto(project_url)
            elif surface == 'page':
                page.get_by_role('button', name='制作总览', exact=True).click()
                page.get_by_role('button', name='打开第 01 页', exact=True).click()
            else:
                page.get_by_role('button', name=title, exact=True).focus()
                page.keyboard.press('Enter')
            if title:
                page.get_by_role('heading', name=title, exact=True).wait_for()
            else:
                page.get_by_role('heading', name=re.compile('^第 1 页')).wait_for()
            if surface not in ('launcher', 'overview'):
                expect(page.locator('#view-title')).to_be_focused()
            if surface in ('gallery', 'page'):
                page.locator('[data-image-state="ready"] canvas:visible').first.wait_for()
            for width, height in [(1280, 800), (1440, 900), (390, 844)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.evaluate('() => scrollTo(0,0)')
                dimensions = page.evaluate('() => ({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                assert dimensions['scroll'] <= dimensions['width'], surface
                page.screenshot(path=str(tmp_path / f'{surface}-{width}.png'))
                checks.append({'surface': surface, 'height': height, **dimensions})
        assert len(checks) == 21 and errors == [] and store.read_current() == before
        (tmp_path / 'surface-checks.json').write_text(json.dumps({'checks': checks, 'errors': errors, 'business_revision_unchanged': True}, indent=2))
    finally:
        local_runtime.stop(descriptor)


def test_candidate_keep_reopen_and_lost_adoption_response_use_original_receipt(action_browser):
    from playwright.sync_api import expect
    page, server, path, store = action_browser
    cid = candidate(store)
    before = copy.deepcopy(store.load_document())
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.locator('.candidate-desk').wait_for()
    page.get_by_role('button', name='保留当前', exact=True).click()
    expect(page.locator('.candidate-state')).to_contain_text('已保留当前')
    assert store.load_document()['pages'] == before['pages']
    expect(page.get_by_role('button', name='预览采用这个候选', exact=True)).to_be_disabled()
    page.get_by_role('button', name='重新打开候选', exact=True).click()
    expect(page.get_by_role('button', name='预览采用这个候选', exact=True)).to_be_enabled()
    page.get_by_role('button', name='预览采用这个候选', exact=True).click()
    adopt = page.get_by_role('button', name='采用这个候选', exact=True)
    expect(adopt).to_be_enabled()
    posts = []
    def lose_response(route):
        posts.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 200
        route.abort('failed')
    page.route('**/api/candidates/adopt', lose_response)
    adopt.click()
    expect(page.get_by_role('button', name='核实保存结果', exact=True)).to_be_enabled()
    expect(page.locator('.business-pending')).to_contain_text('保存结果待核实')
    page.get_by_role('button', name='核实保存结果', exact=True).click()
    expect(page.locator('.candidate-state')).to_contain_text('这个候选已是当前采用')
    assert len(posts) == 1
    assert candidates.show(path, candidate_id=cid)['status'] == 'adopted'
    doc = store.load_document()
    assert doc['pages'][0]['svg'] != before['pages'][0].get('svg')
    assert doc['pages'][0]['blueprint'] == before['pages'][0]['blueprint']
    assert doc['pages'][1:] == before['pages'][1:]
    assert doc['tasks'] == before['tasks']


def test_cancel_via_task_desk_rejects_repeated_late_result(action_browser):
    from playwright.sync_api import expect
    page, server, path, store = action_browser
    task = dispatch(store)
    start(store, task)
    payload = envelope(store, task)
    before = copy.deepcopy(store.load_document()['pages'])
    page.goto(server.start())
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.locator(f'.run-task[data-task-id="{task["task_id"]}"]').get_by_role('button', name='查看这项任务').click()
    page.get_by_role('button', name='取消原任务', exact=True).click()
    expect(page.locator('.run-detail')).to_contain_text('已取消')
    for _ in range(2):
        with pytest.raises(tasks.TaskConflict):
            accept(store, task, payload)
    assert store.load_document()['pages'] == before
    assert candidates.listing(path)['candidates'] == []


def test_content_preview_new_version_and_offline_recovery_keep_input(workbench_page, tmp_path):
    from playwright.sync_api import expect
    page = workbench_page
    store = Store(tmp_path / 'sample')
    before = store.read_current()
    page.get_by_role('button', name='打开第 01 页', exact=True).click()
    page.get_by_role('button', name=re.compile('逐页稿')).first.click()
    page.get_by_text('编辑本页标题与正文', exact=True).click()
    field = page.get_by_role('textbox', name='页面标题', exact=True)
    field.fill('保留这段修改，等待新基准确认')
    page.get_by_role('button', name='预览正文修改影响', exact=True).click()
    expect(page.get_by_role('button', name='确认内容变更', exact=True)).to_be_enabled()
    page.context.set_offline(True)
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    expect(page.locator('.runtime-sync')).to_contain_text('同步中断')
    expect(field).to_have_value('保留这段修改，等待新基准确认')
    page.context.set_offline(False)
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    expect(page.locator('.runtime-sync')).to_be_empty()
    assert store.read_current() == before
    doc = copy.deepcopy(store.load_document())
    doc['policy']['user_stop'] = True
    commit(store, doc, str(uuid.uuid4()))
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    expect(page.locator('.runtime-sync')).to_contain_text('项目有新状态')
    expect(page.get_by_role('button', name='确认内容变更', exact=True)).to_be_disabled()
    expect(field).to_have_value('保留这段修改，等待新基准确认')
    field.fill('新版本提示后仍可继续写草稿')
    expect(field).to_have_value('新版本提示后仍可继续写草稿')
    assert store.load_document()['pages'] == doc['pages']


def test_readonly_sample_keeps_business_controls_disabled(workbench_page, tmp_path):
    from playwright.sync_api import expect
    page = workbench_page
    path = tmp_path / 'readonly'
    create_gallery_sample(path, page_count=30, readonly=True)
    store = Store(path)
    before = store.read_current()
    server = WorkbenchServer(path)
    try:
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        expect(page.get_by_text('合成示例 · 只读', exact=True)).to_be_visible()
        page.get_by_role('button', name='风格校准', exact=True).click()
        expect(page.get_by_role('button', name='检查风格要求', exact=True)).to_be_disabled()
        expect(page.get_by_role('combobox', name='风格参考原图')).to_be_disabled()
        page.get_by_role('button', name='内容与来源', exact=True).click()
        expect(page.get_by_role('heading', name='内容与来源', exact=True)).to_be_visible()
        assert page.get_by_role('button', name='添加材料或调整要求', exact=True).count() == 0
        assert store.read_current() == before
    finally:
        server.stop()
