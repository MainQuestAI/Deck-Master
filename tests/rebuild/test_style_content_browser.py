"""U04 real service/browser interactions; synthetic inputs, zero model calls."""
import copy
from pathlib import Path
import re
import shutil
import uuid

import pytest

from deck_master import service, styles
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


@pytest.fixture
def style_content_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'project'
    create_gallery_sample(path, page_count=30, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for style/content interactions')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type=='error' and 'Content Security Policy' in message.text else None)
        page.add_init_script("window.cspErrors=[];document.addEventListener('securitypolicyviolation',e=>window.cspErrors.push(e.violatedDirective))")
        page.goto(server.start())
        page.get_by_role('heading', name='制作总览', exact=True).wait_for()
        try:
            yield page, server, path, store
            assert errors == []
            assert page.evaluate("window.cspErrors")==[]
        finally:
            browser.close()
            server.stop()


def open_style(page, with_targets=False):
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    if with_targets:
        page.get_by_text('其它目标页', exact=True).click()
        page.get_by_text('查找其它参考页', exact=True).click()


def toggle_phase(page, number):
    phase = page.locator('.style-calibration > .style-phase').nth(number-1)
    if not phase.evaluate('(node) => node.open'):
        phase.locator('summary').first.click()
    return phase


def confirm_recipe(path, store):
    doc = store.load_document()
    proposed = styles.propose(path, input={'schema_version':'style_input.v1','project_id':doc['project_id'],
        'base_revision':doc['revision_id'],'reference':{'page_id':'p01','revision_id':doc['revision_id'],
        'artifact_ref':doc['pages'][0]['blueprint'],'role':'reference'},'target_page_ids':['p02','p30'],
        'instruction':'借用配色，保留事实数字与构图。','dimensions':{'palette':'借用配色'}})
    return styles.confirm(path, proposal_id=proposed['proposal_id'], base_revision=doc['revision_id'],
        operation_id=str(uuid.uuid4()))['operation_result']


def test_thirty_page_mobile_search_counts_missing_images_and_release(style_content_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_content_browser
    before = store.read_current()
    open_style(page, with_targets=True)
    page.set_viewport_size({'width':390,'height':844})
    target = page.get_by_role('searchbox', name='搜索风格目标')
    expect(page.locator('.style-calibration > .style-phase').first).to_have_attribute('open', '')
    assert not page.locator('.style-calibration > .style-phase').nth(1).evaluate('(node) => node.open')
    target.fill('p30')
    expect(page.locator('.style-target-card')).to_have_count(1)
    page.get_by_role('checkbox', name='风格目标 第 30 页 · 交付前查看缺口', exact=True).check()
    expect(page.locator('.style-calibration > .style-phase').first).to_contain_text('已选 1 页')
    target.fill('p03')
    expect(page.locator('.style-target-card')).to_contain_text('未记录原图')
    target.fill('没有这页')
    expect(page.locator('.style-targets').first).to_contain_text('已选目标仍保留')
    target.fill('p30')
    expect(page.get_by_role('checkbox', name='风格目标 第 30 页 · 交付前查看缺口', exact=True)).to_be_checked()
    page.get_by_role('searchbox', name='搜索参考页').fill('p01')
    page.get_by_role('combobox', name='风格参考原图').select_option('p01')
    expect(page.locator('.style-reference canvas')).to_have_count(1)
    page.get_by_role('searchbox', name='搜索参考页').fill('p30')
    assert page.get_by_role('combobox', name='风格参考原图').input_value() == 'p01'
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(path.parent / 'style-mobile.png'))
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    assert page.evaluate("async () => (await import('/v2/images.js')).imagePool.snapshot().pinned") == 0
    assert store.read_current() == before


def test_empty_requirements_dimensions_refresh_and_fixed_reference(style_content_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_content_browser
    before = store.read_current()
    open_style(page, with_targets=True)
    page.get_by_role('combobox', name='风格参考原图').select_option('p01')
    page.get_by_role('checkbox', name='风格目标 第 2 页 · 材料如何成为内容', exact=True).check()
    page.get_by_role('textbox', name='风格短要求', exact=True).fill('')
    page.get_by_text('高级：借用维度、原文选段与建议', exact=True).click()
    page.get_by_role('checkbox', name='借用文字层级', exact=True).uncheck()
    assert not page.get_by_role('checkbox', name='借用构图', exact=True).is_checked()
    page.get_by_text('个人草稿与恢复', exact=True).click()
    page.get_by_role('button', name='保存个人草稿', exact=True).click()
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    page.reload()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    expect(page.get_by_role('textbox', name='风格短要求', exact=True)).to_have_value('')
    page.get_by_text('高级：借用维度、原文选段与建议', exact=True).click()
    assert not page.get_by_role('checkbox', name='借用文字层级', exact=True).is_checked()
    assert not page.get_by_role('checkbox', name='借用构图', exact=True).is_checked()
    assert store.read_current() == before


def test_confirmed_recipe_progression_edits_and_new_revision_invalidate(style_content_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_content_browser
    open_style(page, with_targets=True)
    page.get_by_role('combobox', name='风格参考原图').select_option('p01')
    page.get_by_role('checkbox', name='风格目标 第 2 页 · 材料如何成为内容', exact=True).check()
    page.get_by_role('button', name='检查风格要求', exact=True).click()
    expect(page.get_by_role('button', name='确认这版风格要求', exact=True)).to_be_enabled()
    before_tasks = copy.deepcopy(store.load_document()['tasks'])
    page.get_by_role('button', name='确认这版风格要求', exact=True).click()
    expect(page.locator('.style-calibration > .style-phase').nth(1)).to_have_attribute('open','')
    toggle_phase(page, 3)
    expect(page.get_by_role('button', name='预览单页试作', exact=True)).to_be_enabled()
    assert store.load_document()['tasks'] == before_tasks
    page.get_by_role('button', name='预览单页试作', exact=True).click()
    expect(page.get_by_role('button', name='保存并交接风格试作', exact=True)).to_be_enabled()
    toggle_phase(page, 1)
    page.get_by_role('textbox', name='风格短要求').fill('保留事实，新的明确要求。')
    expect(page.get_by_role('button', name='保存并交接风格试作', exact=True, include_hidden=True)).to_be_disabled()
    expect(page.locator('.style-plan')).to_be_hidden()
    toggle_phase(page, 3)
    page.get_by_role('button', name='预览单页试作', exact=True).click()
    expect(page.get_by_role('button', name='保存并交接风格试作', exact=True)).to_be_enabled()
    doc = copy.deepcopy(store.load_document()); doc['policy']['user_stop'] = True
    commit(store, doc, str(uuid.uuid4()))
    page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_role('button', name='保存并交接风格试作', exact=True, include_hidden=True)).to_be_disabled()
    toggle_phase(page, 1)
    expect(page.get_by_role('textbox', name='风格短要求')).to_have_value('保留事实，新的明确要求。')
    expect(page.locator('.style-calibration > .style-phase').first).to_contain_text('当前项目已有更新')
    assert store.load_document()['tasks'] == before_tasks


def test_late_style_plan_leaving_face_cannot_restore_controls(style_content_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_content_browser
    confirm_recipe(path, store)
    page.reload()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='查看当前版本', exact=True).click()
    expect(page).to_have_url(re.compile('revision=' + store.current_revision_id()))
    open_style(page)
    toggle_phase(page, 2)
    page.get_by_role('combobox', name='已确认的风格版本').select_option(index=1)
    toggle_phase(page, 3)
    held = []
    def delay(route):
        held.append((route,route.fetch()))
        page.locator('html').evaluate("(node) => {node.dataset.heldStyle = 'ready';}")
    page.route('**/api/styles/plan', delay)
    page.get_by_role('button', name='预览单页试作', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-held-style','ready')
    page.get_by_role('button', name='制作总览', exact=True).click()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    held[0][0].fulfill(response=held[0][1])
    open_style(page)
    assert not page.get_by_role('button', name='保存并交接风格试作', exact=True, include_hidden=True).is_enabled()
    assert page.locator('.style-plan').is_hidden()


def add_source(path, store, material):
    result = service.inputs_update(path, patch={'reason':'Add explicitly synthetic material', 'source_changes':{'add':[{'path':str(material)}]}},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    task = next(t for t in result['pending_tasks'] if t['kind'] == 'compose')
    service.task_start(path, task_id=task['task_id'], execution_ref='synthetic-content-browser',
        supported_protocols=['compose.v1'], capabilities=task['required_capabilities'])
    outline = copy.deepcopy(store.read_object_json(store.load_document()['content_plan'])['input'])
    envelope = {'kind':'compose','content_update':{'input_digest':task['project_context']['input_digest'],
        'page_order':[entry['page_id'] for entry in store.load_document()['pages']],
        'impact_summary':'合成材料影响判断：既有示例事实保持。','unchanged_reason':'合成材料只补充背景。'},'content_plan':outline}
    service.accept_result(path, task_id=task['task_id'], operation_id=task['operation_id'],
        produced_against=task['produced_against'], result_payload=envelope)
    return store.load_document()['sources'][0]


def test_material_states_verify_actual_extract_and_preserve_errors(style_content_browser):
    from playwright.sync_api import expect
    page, server, path, store = style_content_browser
    material = path.parent / 'material.md'; material.write_text('Synthetic material, no customer facts.\n')
    source = add_source(path,store,material)
    page.reload()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='查看当前版本', exact=True).click()
    expect(page).to_have_url(re.compile('revision=' + store.current_revision_id()))
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    card = page.locator('.source-card')
    expect(card).to_contain_text('提取：记录待核实')
    expect(card).to_contain_text('影响判断：已有制作工具判断被采用')
    assert '制作工具已读取' not in card.inner_text()
    page.get_by_role('button', name='核实提取状态 material.md', exact=True).click()
    expect(card).to_contain_text('提取：原文可读')
    expect(card).to_contain_text('对齐：内容结果采用了这版输入')
    before = store.read_current()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    assert not page.locator('.content-order-panel').evaluate('(node) => node.open')
    page.screenshot(path=str(path.parent / 'content-mobile.png'))
    extract_path = store.project_root / source['extract']['path']
    original = extract_path.read_bytes()
    try:
        extract_path.write_bytes(b'broken synthetic object')
        page.get_by_role('button', name='核实提取状态 material.md', exact=True).click()
        expect(card).to_contain_text('提取：暂不可读')
        expect(card).to_contain_text('当前输入保留')
        assert '对齐：内容结果采用了这版输入' not in card.inner_text()
        page.get_by_role('button', name='读取材料原文 material.md', exact=True).click()
        expect(page.locator('#modal')).to_contain_text('恢复对应材料版本')
        page.get_by_role('button', name='关闭', exact=True).click()
        assert store.read_current() == before
    finally:
        extract_path.write_bytes(original)


def test_visual_source_remains_unverified_and_late_reads_leave_new_face_alone(style_content_browser):
    from PIL import Image
    from playwright.sync_api import expect
    page, server, path, store = style_content_browser
    material = path.parent / 'diagram.png'
    Image.new('RGB',(24,24),'white').save(material)
    add_source(path,store,material)
    page.reload()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='查看当前版本', exact=True).click()
    expect(page).to_have_url(re.compile('revision=' + store.current_revision_id()))
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    page.get_by_role('button', name='核实提取状态 diagram.png', exact=True).click()
    expect(page.locator('.source-card')).to_contain_text('提取：待制作工具看图')
    assert '提取：原文可读' not in page.locator('.source-card').inner_text()
    assert '对齐：内容结果采用了这版输入' not in page.locator('.source-card').inner_text()
    held = []
    def delay(route):
        held.append((route,route.fetch()))
        page.locator('html').evaluate("(node) => {node.dataset.heldSource = 'ready';}")
    page.route('**/api/content/sources/**',delay)
    page.get_by_role('button', name='读取材料原文 diagram.png', exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-held-source','ready')
    page.get_by_role('button',name='关闭',exact=True).click()
    page.get_by_role('button',name='风格校准',exact=True).click()
    page.get_by_role('heading',name='风格校准',exact=True).wait_for()
    held[0][0].fulfill(response=held[0][1])
    assert not page.locator('#modal').evaluate('(node) => node.open')
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    expect(page.locator('.source-card')).to_contain_text('提取：记录待核实')
    assert not page.locator('#modal').evaluate('(node) => node.open')
