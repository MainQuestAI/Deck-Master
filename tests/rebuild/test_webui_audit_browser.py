"""AUDIT-F01–F09: synthetic projects through shipped HTTP and Chromium.

Transport failures and queued callbacks are explicit test injections, never
professional approval or production fallbacks. No model calls or HOME install.
"""
import json
import hashlib
import re
from urllib.parse import urlencode, urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import delivery_eligibility
from deck_master import tasks
from deck_master.models import content_identity
from deck_master.samples import create_sample, create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_export import _passing_deck, _set_policy
from test_ui_design_browser import workbench_page  # noqa: F401
from test_workbench_services import launcher_service  # noqa: F401
from test_workbench_actions import commit
from rc3_fixtures import historical_snapshot

pytestmark = pytest.mark.browser


def _base(page):
    parsed = urlsplit(page.url)
    return f'{parsed.scheme}://{parsed.netloc}/'


def test_todo_layers_navigate_without_dispatch(workbench_page):
    page = workbench_page
    before = page.request.get(_base(page)+'api/view/summary').json()['revision_id']
    todos = page.get_by_role('region', name='制作待办')
    expect(todos).to_contain_text('2 页原图待生成')
    expect(todos).to_contain_text('11 页SVG待生成')
    expect(todos).to_contain_text('2 页PPT 预览依据已变化')
    expect(todos).to_contain_text('第 3、14 页')
    expect(todos).to_contain_text('第 1、5、7、9 等共 11 页')
    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method == 'POST'
            and any(part in request.url for part in ('/changes/', '/tasks/', '/candidates/', '/stages/')) else None)
    todos.get_by_role('button', name='查看待补页', exact=True).first.click()
    expect(page.get_by_role('heading', name='待办对象', exact=True)).to_be_visible()
    expect(page.locator('#main')).to_contain_text('共 2 个对象')
    expect(page.locator('#main')).to_contain_text('第 3 页')
    expect(page.locator('#main')).to_contain_text('第 14 页')
    assert page.request.get(_base(page)+'api/view/summary').json()['revision_id'] == before
    assert writes == []


@pytest.mark.parametrize('changed',[False,True])
def test_stored_legacy_import_requirement_is_searchable_and_verbatim_in_detail(tmp_path,changed):
    handle=historical_snapshot(tmp_path,scenario='AUDIT-F02 stored legacy import reader')
    store=Store(handle['project'])
    document=store.load_document()
    instruction=("Read every source in Task.sources plus the method resources; derive the "
        "audience's open question and write complete visible copy as Page v2 with "
        "an explicit page order. Same source supports different framings; do not "
        "call a rule planner or fill pages from templates.")
    if changed:
        instruction+='\n用户追加 API、Page v2 讨论，必须完整保留。'
    task=tasks.new_task(task_id='audit-legacy-import',operation_id='audit-legacy-import-op',
        kind='compose',intent='import_draft',scope_pages=[],inputs=[],dependencies=[],
        dispatch_revision=document['revision_id'],produced_against=content_identity(document),instruction=instruction)
    # Explicit historical import record; current producers freeze RC4 facts.
    task.pop('method_manifest',None)
    task.pop('content_validation_policy',None)
    from deck_master import method_resources
    task['method_release']=method_resources.method_release(method_resources._read_ids(
        method_resources.rc3_method_ids_for(task['kind'],intent=task['intent'])))
    document['tasks']=[store.put_json_object(task)]
    commit(store,document,'record-audit-legacy-import')
    before=store.load_document()
    assert before.get('compatibility')==document.get('compatibility')
    assert before.get('collaboration') is None
    server=WorkbenchServer(store.project_root)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch()
        page=browser.new_page()
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            requirement=page.locator('.run-task .run-requirement')
            expect(requirement).to_contain_text('制作要求见详情' if changed else '阅读全部材料，围绕受众的问题组织完整正文与页面顺序')
            expect(requirement).not_to_contain_text('Read every source')
            assert requirement.get_attribute('title') is None
            search=page.get_by_role('searchbox',name='搜索全部任务')
            search.fill('Read every source')
            search.press('Enter')
            expect(page.locator('.run-task')).to_have_count(1)
            page.get_by_role('button',name='查看这项任务',exact=True).click()
            detail=page.locator('.run-detail')
            detail.get_by_text('制作要求与执行身份',exact=True).click()
            expect(detail).to_contain_text(instruction)
            assert store.load_document()==before
        finally:
            browser.close()
            server.stop()


def test_compare_conditions_use_complete_selection_and_visible_reason(workbench_page):
    page = workbench_page
    page.get_by_role('button', name='整稿画廊', exact=True).click()
    tiles = page.locator('.slide-tile')
    expect(tiles.first).to_be_visible()
    ids = tiles.evaluate_all('nodes=>nodes.slice(0,5).map(node=>node.dataset.pageId)')
    assert len(ids) == 5
    for count in range(6):
        if count:
            page.locator(f'.slide-tile[data-page-id="{ids[count-1]}"] .tile-select input').check()
        compare = page.get_by_role('button', name='并排比较', exact=True)
        reason = page.locator('#'+compare.get_attribute('aria-describedby'))
        expect(reason).to_be_visible()
        if count < 2:
            expect(compare).to_be_disabled()
            expect(reason).to_contain_text('至少选择 2 页')
        elif count <= 4:
            expect(compare).to_be_enabled()
            expect(reason).to_contain_text(f'已选 {count} 页')
        else:
            expect(compare).to_be_disabled()
            expect(reason).to_contain_text('制作范围不受影响')
    page.get_by_role('textbox', name='搜索页面', exact=True).fill('不存在的标题')
    expect(page.locator('.gallery-legend')).to_contain_text('筛选外选中 5 页')
    expect(page.get_by_role('button', name='并排比较', exact=True)).to_be_disabled()
    page.set_viewport_size({'width':390, 'height':844})
    page.get_by_role('button', name=re.compile('^筛选与阅读设置')).click()
    compare = page.get_by_role('button', name='并排比较', exact=True)
    expect(page.locator('#'+compare.get_attribute('aria-describedby'))).to_contain_text('桌面选择 2–4 页')
    page.get_by_role('dialog').get_by_role('button', name='关闭', exact=True).click()
    page.set_viewport_size({'width':1440, 'height':900})
    page.get_by_role('textbox', name='搜索页面', exact=True).fill('')
    expect(page.locator('.gallery-legend')).to_contain_text('已选 5 页')


@pytest.mark.parametrize('mode', ['task', 'add', 'mixed'])
def test_inputs_keep_other_entry_drafts_and_confirm_all_differences(tmp_path, mode):
    project = tmp_path/'sample'
    create_sample(project, page_count=3, readonly=False)
    store = Store(project)
    before = store.load_document()
    source = tmp_path/'additional.md'
    source.write_text('# Explicit synthetic material\nKeep the original task facts.')
    server = WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button', name='内容与页序', exact=True).click()
            editor = page.locator('.materials-adjust-form')
            if mode in ('task', 'mixed'):
                page.get_by_role('button', name='材料与要求', exact=True).click()
                page.get_by_role('button', name='修改任务要求', exact=True).click()
                expect(editor.get_by_label('用途与目标', exact=True)).to_be_visible()
                expect(editor.get_by_label('新增材料完整路径（每行一个）')).to_have_count(0)
                editor.get_by_label('受众', exact=True).fill('新的明确受众')
                editor.get_by_role('button', name='关闭编辑并保留草稿', exact=True).click()
            if mode in ('add', 'mixed'):
                page.get_by_role('button', name='材料与要求', exact=True).click()
                page.get_by_role('button', name='添加材料', exact=True).click()
                expect(editor.get_by_label('用途与目标', exact=True)).to_have_count(0)
                editor.get_by_label('新增材料完整路径（每行一个）').fill(str(source))
                if mode == 'mixed':
                    expect(editor.locator('.retained-inputs')).to_contain_text('还保留了要求修改')
                editor.get_by_role('button', name='关闭编辑并保留草稿', exact=True).click()
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            page.reload()
            page.get_by_role('button', name='材料与要求', exact=True).click()
            page.get_by_role('button', name='修改任务要求' if mode == 'task' else '添加材料', exact=True).click()
            if mode == 'mixed':
                expect(editor.locator('.retained-inputs')).to_contain_text('还保留了要求修改')
                editor.get_by_role('button', name='返回要求修改', exact=True).click()
                expect(editor.get_by_label('受众', exact=True)).to_have_value('新的明确受众')
                expect(editor.locator('.retained-inputs')).to_contain_text('还保留了材料变更')
            editor.get_by_label('本次输入变化说明', exact=True).fill('只确认这次预览列明的输入差异')
            editor.get_by_role('button', name='预览材料与任务变化', exact=True).click()
            if mode in ('task', 'mixed'):
                expect(editor).to_contain_text('→ 新的明确受众')
            if mode in ('add', 'mixed'):
                expect(editor).to_contain_text('新增材料：'+str(source))
            assert store.load_document() == before
            editor.get_by_role('button', name='返回编辑', exact=True).click()
            editor.get_by_role('button', name='预览材料与任务变化', exact=True).click()
            with page.expect_request('**/api/content/inputs') as sent:
                editor.get_by_role('button', name='确认输入并交接判断', exact=True).click()
            payload = sent.value.post_data_json['input']
            assert bool(payload['source_changes']['add']) is (mode != 'task')
            assert payload['source_changes']['remove'] == payload['source_changes']['replace'] == []
            expect(page.get_by_role('heading', name='当前任务', exact=True)).to_be_visible()
            after = store.load_document()
            if mode == 'add':
                assert after['task'] == before['task']
            else:
                assert after['task']['audience'] == '新的明确受众'
            if mode == 'task':
                assert after['sources'] == before['sources']
            else:
                assert len(after['sources']) == len(before['sources'])+1
        finally:
            browser.close()
            server.stop()


@pytest.mark.parametrize('size', [(1440,900), (1280,800), (390,844)])
def test_reading_geometry_keeps_labels_targets_and_same_canvas(workbench_page, size, tmp_path):
    page = workbench_page
    base = _base(page)
    info = page.request.get(base+'api/project').json()
    page.set_viewport_size({'width':size[0], 'height':size[1]})
    page.goto(base+'studio/#'+urlencode({'project':info['project_identity'], 'surface':'page',
        'page':'p01', 'layer':'original_image', 'revision':info['revision_id']}))
    canvas = page.locator('.studio-page-reading canvas.page-image')
    expect(canvas).to_be_visible()
    page.get_by_role('button', name='适应窗口', exact=True).click()
    page.evaluate('''async()=>{scrollTo(0,0);await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);}''')
    box = page.locator('.page-image-viewport').bounding_box()
    assert page.evaluate('scrollY') == 0
    page.screenshot(path=str(tmp_path/f'reading-{size[0]}.png'))
    assert box['y'] <= (580 if size[0] == 390 else 450)
    if size[0] == 1280:
        assert box['height'] >= 320
    for control in page.get_by_role('group', name='单页工具').get_by_role('button').all():
        assert control.bounding_box()['height'] >= (44 if size[0]<=560 else 32) - .01
        assert float(control.evaluate('node=>getComputedStyle(node).fontSize').removesuffix('px')) >= 12
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(tmp_path/f'reading-{size[0]}.png'))
    (tmp_path/f'geometry-{size[0]}.json').write_text(json.dumps(box))


def test_narrow_long_project_title_preserves_control_access(tmp_path):
    project=tmp_path/'long-title'
    create_gallery_sample(project,page_count=24,readonly=False)
    store=Store(project)
    document=store.load_document()
    title='这是用于验证窄屏长项目名称和当前工作控件的合成项目标题。'*4
    document['task']['title']=title
    commit(store,document,'synthetic-long-title')
    before=store.load_document()
    server=WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch()
        try:
            page=browser.new_page(viewport={'width':390,'height':844})
            base=server.start()
            info=page.request.get(base+'api/project').json()
            page.goto(base+'studio/#'+urlencode({'project':info['project_identity'],'surface':'page',
                'page':'p01','layer':'original_image','revision':info['revision_id']}))
            expect(page.locator('.topbar .crumb > strong')).to_have_text(title)
            scope=page.get_by_role('button',name='查看本次工作与范围',exact=True)
            expect(scope).to_be_visible()
            scope.click()
            expect(page.get_by_role('dialog',name='本次工作与范围')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.keyboard.press('Escape')
            expect(scope).to_be_focused()
            assert store.load_document()==before
        finally:
            browser.close()
            server.stop()


@pytest.mark.parametrize('size', [(1440,900), (1280,800), (390,844), (390,500)])
def test_create_dialog_has_fixed_actions_and_scoped_queue_layout(launcher_service, tmp_path, size):
    _, _, state = launcher_service
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        try:
            page = browser.new_page(viewport={'width':size[0], 'height':size[1]})
            page.goto(state['url'])
            trigger = page.get_by_role('button', name='新建项目', exact=True)
            trigger.click()
            dialog = page.get_by_role('dialog', name='新建项目')
            first = dialog.get_by_label('项目名称（必填）')
            first.fill('保留第一份表单')
            def geometry():
                for control in [dialog.get_by_role('heading', name='新建项目'),
                                dialog.get_by_role('button', name='关闭', exact=True),
                                dialog.get_by_role('button', name='创建项目', exact=True)]:
                    expect(control).to_be_in_viewport(ratio=1)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            geometry()
            form = dialog.locator('form')
            assert form.evaluate('node=>node.scrollHeight>node.clientHeight')
            form.evaluate('node=>node.scrollTop=node.scrollHeight')
            geometry()
            dialog.get_by_role('button', name='创建项目', exact=True).click()
            expect(dialog.get_by_label('用途（必填）')).to_be_focused()
            # A callback queues another create dialog behind a protected draft.
            page.evaluate('''()=>[...document.querySelectorAll('button')].find(button=>button.textContent==='新建项目').click()''')
            expect(first).to_have_value('保留第一份表单')
            expect(page.locator('dialog.queued-modal')).to_have_count(1)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            dialog = page.locator('dialog.queued-modal[open]')
            expect(dialog).to_be_visible()
            geometry()
            # Dynamic complete-manuscript preview stays inside the scrolling form.
            source = tmp_path/'confirmed.json'
            from test_rc3_studio_control_browser import manuscript_page
            source.write_text(json.dumps({'pages':[manuscript_page(f'p{i}', '确认稿'+str(i)) for i in range(8)]}))
            dialog.get_by_label('确认稿 JSON 文件（可选）').set_input_files(source)
            expect(dialog).to_contain_text('完整稿件')
            geometry()
            page.screenshot(path=str(tmp_path/f'queued-create-{size[0]}x{size[1]}.png'))
            page.keyboard.press('Escape')
            expect(trigger).to_be_focused()
            page.get_by_role('button', name='选择项目文件夹', exact=True).click()
            other = page.get_by_role('dialog', name='打开项目')
            expect(other).to_be_visible()
            assert other.locator('.launcher-create-form').count() == 0
            assert other.evaluate('node=>getComputedStyle(node).overflowY') != 'hidden'
        finally:
            browser.close()


def test_delivery_loading_error_late_policy_and_real_ready(tmp_path):
    project, store = _passing_deck(tmp_path)
    assert delivery_eligibility.describe(project)['status'] == 'ready'
    server = WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width':1280, 'height':800})
        held = []
        mode = ['hold']
        def intercept(route):
            response = route.fetch()
            if mode[0] == 'hold':
                held.append((route, response))
            elif mode[0] == 'error':
                route.fulfill(status=503, json={'error':{'code':'network_unavailable','message':'核对连接失败，稿件保留。'}})
            else:
                route.fulfill(response=response)
        page.route('**/delivery-eligibility?*', intercept)
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button', name='任务与交付', exact=True).click()
            page.get_by_role('button', name='文件', exact=True).click()
            formal = page.get_by_role('button', name='生成正式交付包', exact=True)
            expect(formal).to_be_disabled()
            expect(page.get_by_role('button', name='生成审阅包', exact=True)).to_be_enabled()
            for _ in range(100):
                if held:
                    break
                page.wait_for_timeout(20)
            assert len(held) == 1
            old = held.pop()
            mode[0] = 'ready'
            page.get_by_label('口播稿保留方式').select_option('pure_reading')
            expect(formal).to_be_enabled()
            old[0].fulfill(response=old[1])
            expect(page.locator('.export-notes-choice').locator('select')).to_have_value('pure_reading')
            expect(page.locator('.export-group [role=status]').first).to_contain_text('本次方式：纯阅读稿')
            mode[0] = 'error'
            page.get_by_role('button', name='重新核对当前控制', exact=True).click()
            expect(formal).to_be_disabled()
            expect(page.locator('.delivery-availability')).to_contain_text('读取失败')
            expect(page.get_by_role('button', name='生成审阅包', exact=True)).to_be_enabled()
            mode[0] = 'ready'
            page.get_by_role('button', name='重读交付判断', exact=True).click()
            expect(formal).to_be_enabled()
            # The positive verdict and actual file generation both use real gates.
            dispatched=[]
            page.on('request',lambda request:dispatched.append(request.post_data_json)
                if request.method=='POST' and request.url.endswith('/api/exports') else None)
            formal.evaluate('node=>{node.click();node.click();}')
            expect(page.locator('.export-results').get_by_role('link', name='下载 ZIP', exact=True)).to_be_visible()
            expect(page.locator('.export-results')).to_contain_text('正式交付包')
            assert len(dispatched)==1
            assert store.current_revision_id() == delivery_eligibility.describe(project)['artifact_revision_id']
            # Export completion starts its own revalidation. Finish that read
            # before holding the next one, or the test intercepts its own prerequisite.
            expect(formal).to_be_enabled()
            # A ready R1 reply cannot enable an R2 surface whose read has failed.
            mode[0]='hold'
            page.get_by_role('button',name='重新核对当前控制',exact=True).click()
            for _ in range(100):
                if held:
                    break
                page.wait_for_timeout(20)
            assert held
            old=held.pop()
            _set_policy(store,professional_review_required_for_delivery=False)
            current=store.current_revision_id()
            info=page.request.get(_base(page)+'api/project').json()
            mode[0]='error'
            page.goto(_base(page)+'studio/#'+urlencode({'project':info['project_identity'],
                'surface':'runs','area':'files','revision':current}))
            expect(page.locator('.delivery-availability')).to_contain_text('读取失败')
            old[0].fulfill(response=old[1])
            expect(page.get_by_role('button',name='生成正式交付包',exact=True)).to_be_disabled()
            expect(page.locator('.studio-files-version')).to_contain_text(current[:8])
        finally:
            browser.close()
            server.stop()


def test_missing_judgement_capability_cannot_enable_delivery(workbench_page):
    page = workbench_page
    def old_health(route):
        response = route.fetch()
        value = response.json()
        value['ui_capabilities'] = [item for item in value['ui_capabilities'] if item != 'delivery_eligibility.v1']
        route.fulfill(response=response, json=value)
    page.route('**/api/health', old_health)
    page.reload()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('button', name='文件', exact=True).click()
    expect(page.get_by_role('button', name='生成正式交付包', exact=True)).to_be_disabled()
    expect(page.locator('.delivery-availability')).to_contain_text('当前核心不支持交付判断')
    expect(page.get_by_role('button', name='生成审阅包', exact=True)).to_be_enabled()


@pytest.mark.parametrize('size', [(1440,900), (1280,800)])
def test_delivery_judgement_named_gaps_and_primary_action_share_first_view(workbench_page, size, tmp_path):
    page=workbench_page
    page.set_viewport_size({'width':size[0],'height':size[1]})
    page.get_by_role('button',name='任务与交付',exact=True).click()
    page.get_by_role('button',name='文件',exact=True).click()
    judgement=page.get_by_label('所选实际文件的交付判断')
    expect(judgement.get_by_role('heading')).to_be_visible()
    page.evaluate('scrollTo(0,0)')
    expect(judgement.get_by_role('heading')).to_be_in_viewport(ratio=1)
    expect(page.get_by_role('button',name='生成正式交付包',exact=True)).to_be_in_viewport(ratio=1)
    expect(judgement.locator('.delivery-named-gaps')).to_be_in_viewport()
    page.screenshot(path=str(tmp_path/f'delivery-first-view-{size[0]}.png'))


@pytest.mark.parametrize('purpose',['delivery','engineering'])
def test_formal_and_engineering_results_share_real_download_integrity(tmp_path,purpose):
    project,store=_passing_deck(tmp_path,notes='Explicit L1 notes retained by the real export.')
    before=store.load_document()
    server=WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch()
        page=browser.new_page()
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            page.get_by_role('button',name='文件',exact=True).click()
            if purpose=='engineering':
                page.get_by_role('button',name='内部工程恢复包',exact=True).click()
                page.get_by_role('dialog',name='内部工程恢复包').get_by_role('button',name='生成内部工程包',exact=True).click()
                page.get_by_role('dialog',name='内部工程恢复包').get_by_role('button',name='关闭',exact=True).click()
            else:
                expect(page.get_by_role('button',name='生成正式交付包',exact=True)).to_be_enabled()
                page.get_by_role('button',name='生成正式交付包',exact=True).click()
            row=page.locator('.export-results > .export-result').first
            link=row.get_by_role('link',name='下载 ZIP',exact=True)
            expect(link).to_be_visible()
            with page.expect_download() as download:
                link.click()
            digest=hashlib.sha256(download.value.path().read_bytes()).hexdigest()
            files=page.locator('#delivery-desk')
            assert not re.search(r'[a-f0-9]{64}|SHA256',files.inner_text())
            assert not re.search(r'[a-f0-9]{64}|SHA256',files.aria_snapshot())
            row.get_by_role('button',name=re.compile('^查看文件与哈希')).click()
            dialog=page.get_by_role('dialog',name='文件清单与完整性校验')
            expect(dialog).to_contain_text('ZIP SHA256 '+digest)
            dialog.get_by_role('button',name='关闭',exact=True).click()
            assert store.load_document()==before
        finally:
            browser.close()
            server.stop()
