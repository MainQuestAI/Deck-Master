"""PR103 regressions through the shipped UI and real loopback core.

Synthetic projects/images and controlled transport faults are explicit; these
checks are not Host generation or professional visual acceptance.
"""
import pytest
import os
from pathlib import Path
from urllib.parse import urlencode

from test_ux04_content_annotations_browser import ux04_browser  # noqa: F401
from test_styles import flow  # noqa: F401
from test_visual_styles import image_bytes
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


def screenshot(page, name):
    destination = os.environ.get('DECK_MASTER_PR103_EVIDENCE_DIR')
    if destination:
        path = Path(destination); path.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path / (name+'.png')), animations='disabled')


@pytest.mark.parametrize('next_opinion', ['new', 'scope'])
def test_saved_opinion_is_still_saved_after_reload(ux04_browser, next_opinion):
    from playwright.sync_api import expect
    page, server, _project, store = ux04_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    info = page.request.get(page.url.split('#')[0] + 'api/project').json()
    page.goto(page.url.split('#')[0] + '#' + urlencode({'project': info['project_identity'], 'surface': 'page',
        'page': 'p01', 'layer': 'original_image', 'revision': store.current_revision_id()}))
    page.get_by_role('button', name='整页意见', exact=True).click()
    body = page.get_by_role('textbox', name='意见正文', exact=True)
    body.fill('PR103 同一草稿保存后刷新，不重复新增')
    save = page.get_by_role('button', name='保存意见', exact=True)
    expect(save).to_be_enabled()
    save.click()
    expect(page.locator('.saved-annotations')).to_contain_text('PR103 同一草稿保存后刷新，不重复新增')
    expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
    expect(save).to_be_disabled()
    page.reload()
    expect(body).to_have_value('PR103 同一草稿保存后刷新，不重复新增')
    page.get_by_role('button', name='整页意见', exact=True).click()
    expect(save).to_be_disabled()
    assert len(store.load_document()['annotations']) == 1
    if next_opinion == 'new':
        page.locator('summary').filter(has_text='草稿操作').click()
        page.get_by_role('button', name='写新意见', exact=True).click()
        body.fill('PR103 同一草稿保存后刷新，不重复新增')
    else:
        page.locator('.annotation-settings > summary').click()
        page.get_by_label('意见作用范围').select_option('artifact')
    expect(save).to_be_enabled()
    save.click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    assert len(store.load_document()['annotations']) == 2


def test_unknown_opinion_receipt_recovers_marker_without_original_callback(ux04_browser):
    from playwright.sync_api import expect
    page, server, _project, store = ux04_browser
    url = server.start(); page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    info = page.request.get(url+'api/project').json()
    page.goto(url+'#'+urlencode({'project':info['project_identity'], 'surface':'page',
        'page':'p01', 'layer':'original_image', 'revision':store.current_revision_id()}))
    def lose_response(route):
        route.fetch()
        route.abort()
    page.route('**/api/annotations/batch', lose_response)
    page.get_by_role('button', name='整页意见', exact=True).click()
    page.get_by_role('textbox', name='意见正文', exact=True).fill('原请求已保存，回包丢失后恢复')
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(page.get_by_role('button', name='核实保存结果', exact=True)).to_be_enabled()
    page.reload()
    page.get_by_role('button', name='核实保存结果', exact=True).click()
    expect(page.locator('.business-pending')).to_be_hidden()
    expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
    page.get_by_role('button', name='整页意见', exact=True).click()
    expect(page.get_by_role('button', name='保存意见', exact=True)).to_be_disabled()
    assert len(store.load_document()['annotations']) == 1


def test_opinion_marker_keeps_text_written_after_the_frozen_request(ux04_browser):
    from playwright.sync_api import expect
    page, server, _project, store = ux04_browser
    url = server.start(); page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    info = page.request.get(url+'api/project').json()
    page.goto(url+'#'+urlencode({'project':info['project_identity'],'surface':'page',
        'page':'p01','layer':'original_image','revision':store.current_revision_id()}))
    held = []
    def delay(route):
        held.append((route,route.fetch()))
        page.evaluate('() => window.pr103OpinionHeld = true')
    page.route('**/api/annotations/batch',delay)
    page.get_by_role('button',name='整页意见',exact=True).click()
    body = page.get_by_role('textbox',name='意见正文',exact=True)
    body.fill('冻结并已提交的意见 A')
    page.get_by_role('button',name='保存意见',exact=True).click()
    page.wait_for_function('() => window.pr103OpinionHeld === true')
    body.fill('等待业务回执时继续写的意见 B')
    expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
    held[0][0].fulfill(response=held[0][1])
    expect(page.locator('.business-pending')).to_be_hidden()
    expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
    page.reload()
    expect(body).to_have_value('等待业务回执时继续写的意见 B')
    page.get_by_role('button',name='整页意见',exact=True).click()
    expect(page.get_by_role('button',name='保存意见',exact=True)).to_be_enabled()
    assert len(store.load_document()['annotations']) == 1


def test_screenshot_analysis_restore_cannot_override_a_manual_phase(flow):
    from playwright.sync_api import sync_playwright, expect
    from test_visual_styles import completed
    _ref, task, _row = completed(flow)
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page();held=[]
        try:
            page.goto(server.start());page.get_by_role('button',name='风格校准',exact=True).click()
            page.get_by_label('风格参考来源').select_option('screenshot')
            page.get_by_text('恢复项目中的截图分析与规范',exact=True).click()
            page.get_by_label('恢复已保存的截图分析').select_option(task['task_id'])
            expect(page.locator('.visual-style p[role=status]')).to_contain_text('分析已返回')
            expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            def delay(route):
                held.append((route,route.fetch()))
                page.evaluate('() => window.pr103ReferencesHeld = true')
            page.route('**/api/styles/references?*',delay)
            page.reload();page.wait_for_function('() => window.pr103ReferencesHeld === true')
            phase=page.locator('.visual-style .style-phase').nth(2)
            phase.locator(':scope > summary').click()
            held[0][0].fulfill(response=held[0][1])
            expect(page.locator('.visual-style p[role=status]')).to_contain_text('分析已返回')
            expect(phase).to_have_attribute('open','')
        finally:
            browser.close();server.stop()


def test_opinion_receipt_draft_conflict_preserves_the_original_request(ux04_browser):
    from playwright.sync_api import expect
    page, server, _project, store = ux04_browser
    url=server.start();page.goto(url)
    page.get_by_role('heading',name='制作总览',exact=True).wait_for()
    info=page.request.get(url+'api/project').json()
    page.goto(url+'#'+urlencode({'project':info['project_identity'],'surface':'page',
        'page':'p01','layer':'original_image','revision':store.current_revision_id()}))
    held=[]
    def delay(route):
        held.append((route,route.fetch(),route.request.post_data_json['operation_id']))
        page.evaluate('() => window.pr103ConflictHeld = true')
    page.route('**/api/annotations/batch',delay)
    page.get_by_role('button',name='整页意见',exact=True).click()
    page.get_by_role('textbox',name='意见正文',exact=True).fill('草稿冲突时仍能恢复的原意见')
    page.get_by_role('button',name='保存意见',exact=True).click()
    page.wait_for_function('() => window.pr103ConflictHeld === true')
    record=page.request.get(url+'api/drafts').json()['records'][0]
    draft=record['draft'];draft['content']['text']='另一个窗口已保存的私人输入'
    page.evaluate("value => import('/v2/api.js').then(({post}) => post('/api/drafts/save',value))",
                  {'draft':draft,'expected_etag':record['etag']})
    held[0][0].fulfill(response=held[0][1])
    expect(page.locator('.draft-state')).to_contain_text('保存冲突')
    expect(page.locator('.business-pending')).to_contain_text('草稿记录仍待确认')
    saved=page.request.get(url+'api/drafts').json()['records'][0]['draft']
    assert saved['pending']['operation_id'] == held[0][2]
    assert saved['content']['text'] == '另一个窗口已保存的私人输入'
    recovery=page.evaluate('key => JSON.parse(localStorage.getItem(key))',
                          'deck-master:v3:pending-business:'+info['project_identity'])
    assert recovery[0]['pending']['operation_id'] == held[0][2]
    assert len(store.load_document()['annotations']) == 1


def test_navigation_uses_url_at_start_not_passive_overview_events(ux04_browser):
    from playwright.sync_api import expect
    page, server, _project, _store = ux04_browser
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    held = []
    def delay(route):
        held.append((route, route.fetch()))
        page.evaluate('() => window.pr103ProjectHeld = true')
    page.route('**/api/project', delay)
    page.evaluate('() => {const p=new URLSearchParams(location.hash.slice(1));p.set("filter","broken");location.hash="#"+p;}')
    page.wait_for_function('() => location.hash.includes("filter=broken")')
    page.wait_for_function('() => window.pr103ProjectHeld === true')
    page.evaluate('() => document.querySelector("#app").dispatchEvent(new CustomEvent("draft-state-changed"))')
    assert 'filter=broken' in page.url
    held[0][0].fulfill(response=held[0][1])
    expect(page.locator('.notice')).to_contain_text('筛选或排序无效')
    expect(page.get_by_role('heading', name='制作总览', exact=True)).to_be_visible()


def test_reference_preview_and_same_file_retry_after_not_found(flow):
    from playwright.sync_api import sync_playwright, expect
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page()
        requests = []
        try:
            page.goto(server.start())
            page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
            upload = page.get_by_label('导入参考截图', exact=True)
            expect(upload).to_be_enabled()
            def drop(route):
                requests.append(route.request.url)
                route.abort()
            page.route('**/api/styles/references/import?*', drop)
            file = {'name': 'same.png', 'mimeType': 'image/png', 'buffer': image_bytes()}
            upload.set_input_files(file)
            expect(upload).to_be_disabled()
            expect(upload).to_have_value('')
            def unrelated_not_found(route):
                route.fulfill(status=404, json={'error':{'code':'other_not_found','message':'未能核实'}})
            page.route('**/api/operations/*', unrelated_not_found)
            page.get_by_role('button', name='核实原上传', exact=True).click()
            expect(page.get_by_role('button', name='核实原上传', exact=True)).to_be_enabled()
            expect(upload).to_be_disabled()
            page.unroute('**/api/operations/*', unrelated_not_found)
            page.get_by_role('button', name='核实原上传', exact=True).click()
            expect(upload).to_be_enabled()
            # Refresh and passive controls must keep the verified replay usable.
            page.reload()
            expect(upload).to_be_enabled()
            upload.set_input_files({'name':'different.png','mimeType':'image/png','buffer':image_bytes()+b'changed'})
            expect(page.locator('.visual-style p[role=status]')).to_contain_text('同一张图片')
            expect(upload).to_be_enabled()
            assert len(requests) == 1
            page.unroute('**/api/styles/references/import?*', drop)
            page.on('request', lambda req: requests.append(req.url)
                    if '/api/styles/references/import?' in req.url else None)
            upload.set_input_files(file)
            expect(page.locator('.visual-reference-choice .pooled-image')).to_have_attribute('data-image-state', 'ready')
            canvas = page.get_by_role('img', name='参考截图 1', exact=True)
            assert canvas.evaluate('node => node.getContext("2d").getImageData(0,0,1,1).data[3]') == 255
            assert requests[0] == requests[1]
            assert len(flow.store.load_document()['style_references']) == 1
            page.reload()
            expect(page.locator('.visual-reference-choice .pooled-image')).to_have_attribute('data-image-state', 'ready')
        finally:
            browser.close()
            server.stop()


@pytest.mark.parametrize('keyboard', [False, True])
def test_delayed_recipe_restore_does_not_close_manually_chosen_phase(flow, keyboard):
    from playwright.sync_api import sync_playwright, expect
    from test_styles import confirm
    recipe = confirm(flow)
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox']); page = browser.new_page()
        held = []
        release = [False]
        try:
            page.goto(server.start());page.get_by_role('button', name='风格校准', exact=True).click()
            page.locator('.style-calibration > .style-phase').nth(1).locator(':scope > summary').click()
            with page.expect_response(lambda response: '/api/drafts/save' in response.url and
                    response.request.post_data_json['draft']['content'].get('style_trial', {}).get('recipe_id') == recipe['recipe_id']) as saved:
                page.get_by_label('已确认的风格版本').select_option(recipe['recipe_id'])
            assert saved.value.ok
            assert saved.value.json()['record']['draft']['content']['style_trial']['recipe_id'] == recipe['recipe_id']
            expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            def delay(route):
                response = route.fetch()
                # Both source panels read the same catalog URL. Release every
                # request after the user choice, not whichever panel won the race.
                if release[0]:
                    route.fulfill(response=response)
                    return
                held.append((route, response))
                page.evaluate('() => window.pr103RecipeHeld = true')
            page.route('**/api/styles?*', delay)
            page.reload();page.wait_for_function('() => window.pr103RecipeHeld === true')
            phase = page.locator('.style-calibration > .style-phase').nth(2)
            summary = phase.locator(':scope > summary')
            if keyboard:
                summary.focus();summary.press('Enter')
            else:
                summary.locator('.style-phase-title').click()
            assert phase.evaluate('node => node.open')
            release[0] = True
            for route, response in held:
                route.fulfill(response=response)
            expect(page.get_by_label('已确认的风格版本')).to_have_value(recipe['recipe_id'])
            expect(phase).to_have_attribute('open', '')
        finally:
            browser.close();server.stop()


@pytest.mark.parametrize('width,height', [(1440,900),(1280,800),(390,844)])
@pytest.mark.parametrize('count', [0,1,2])
def test_material_editor_keeps_preview_confirmation_and_return_in_context(ux04_browser, width, height, count):
    from playwright.sync_api import expect
    from test_ux00_fixes_browser import add_materials
    page, server, project, store = ux04_browser
    add_materials(project, store, count=count)
    page.set_viewport_size({'width':width,'height':height})
    page.goto(server.start());page.get_by_role('button',name='内容与来源',exact=True).click()
    before = store.read_current()
    trigger = page.get_by_role('button', name='修改任务要求', exact=True)
    trigger.evaluate('node => node.addEventListener("click", () => window.pr103ReturnY=scrollY, {capture:true,once:true})')
    trigger.click()
    editor = page.locator('.materials-adjust-form')
    editor.get_by_role('textbox', name='汇报用途', exact=True).fill('PR103 材料上下文中的新用途')
    editor.get_by_role('textbox', name='本次输入变化说明', exact=True).fill('核对用途变化')
    editor.get_by_role('button', name='预览材料与任务变化', exact=True).click()
    expect(editor).to_contain_text('→ PR103 材料上下文中的新用途')
    expect(editor.get_by_role('button',name='确认输入并交接判断',exact=True)).to_be_enabled()
    editor.scroll_into_view_if_needed()
    screenshot(page, f'material-review-{count}-{width}x{height}')
    editor.get_by_role('button',name='返回编辑',exact=True).click()
    expect(editor.get_by_role('textbox',name='汇报用途',exact=True)).to_have_value('PR103 材料上下文中的新用途')
    editor.get_by_role('button',name='关闭编辑并保留草稿',exact=True).click()
    expect(trigger).to_be_focused()
    page.wait_for_function('() => Math.abs(scrollY-window.pr103ReturnY)<2')
    assert store.read_current() == before
    expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
    page.reload(); trigger.click()
    expect(editor.get_by_role('textbox',name='汇报用途',exact=True)).to_have_value('PR103 材料上下文中的新用途')
    expect(editor.locator('.content-operation > button')).to_be_disabled()
    editor.get_by_role('button',name='关闭编辑并保留草稿',exact=True).click()
    if count:
        name = store.load_document()['sources'][0]['name']
        source_trigger=page.get_by_role('button',name='调整此材料 · '+name,exact=True)
        source_trigger.evaluate('node => node.addEventListener("click", () => window.pr103ReturnY=scrollY, {capture:true,once:true})')
        source_trigger.click()
        expect(editor.get_by_role('heading',name='调整材料 · '+name,exact=True)).to_be_visible()
        editor.get_by_role('button',name='关闭编辑并保留草稿',exact=True).click()
        expect(source_trigger).to_be_focused()
        page.wait_for_function('() => Math.abs(scrollY-window.pr103ReturnY)<2')
        source_trigger.click()
        editor.get_by_role('combobox',name='材料操作 '+name).select_option('remove')
        expected_difference = '移除：'+name
    else:
        material = project.parent / 'new-material.txt'
        material.write_text('Synthetic PR103 input, not customer material.',encoding='utf-8')
        page.get_by_role('button',name='添加材料或调整要求',exact=True).click()
        expect(editor.get_by_role('heading',name='添加材料',exact=True)).to_be_visible()
        expect(editor.get_by_label('新增材料完整路径（每行一个）')).to_be_focused()
        editor.get_by_label('新增材料完整路径（每行一个）').fill(str(material))
        expected_difference = '新增材料：'+str(material)
    editor.get_by_role('button',name='预览材料与任务变化',exact=True).click()
    expect(editor).to_contain_text(expected_difference)
    editor.get_by_role('button',name='确认输入并交接判断',exact=True).click()
    page.get_by_role('heading',name='当前任务',exact=True).wait_for()
    assert store.read_current() != before
    assert len(store.load_document()['sources']) == (count-1 if count else 1)


@pytest.mark.parametrize('source', ['project', 'screenshot'])
def test_candidate_cards_show_real_fixed_images_and_release_on_navigation(flow, source):
    from playwright.sync_api import sync_playwright, expect
    from test_styles import confirm, dispatch
    if source == 'screenshot':
        from test_visual_styles import completed
        ref, _, _ = completed(flow)
        recipe = confirm(flow, {'schema_version':'style_input.v2', 'project_id':flow.store.load_document()['project_id'],
            'base_revision':flow.store.current_revision_id(), 'visual_style_ref':ref,
            'target_page_ids':['p02'], 'instruction':'借用截图配色，保留正文'})
    else:
        recipe = confirm(flow)
    first = flow.image(dispatch(flow, recipe), variant=1)
    second = flow.image(dispatch(flow, recipe), variant=2)
    ids = [first['candidate_ids'][0],second['candidate_ids'][0]]
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page()
        try:
            page.goto(server.start());page.get_by_role('button',name='风格校准',exact=True).click()
            if source == 'screenshot':
                page.get_by_label('风格参考来源').select_option('screenshot')
                page.get_by_text('恢复项目中的截图分析与规范',exact=True).click()
                page.get_by_label('已确认的截图规范').select_option(recipe['recipe_id'])
                expect(page.locator('.visual-style p[role=status]')).to_contain_text('已打开所选确认规范')
                phase = page.locator('.visual-style .style-phase').nth(2)
            else:
                page.locator('.style-calibration > .style-phase').nth(1).locator(':scope > summary').click()
                page.get_by_label('已确认的风格版本').select_option(recipe['recipe_id'])
                phase = page.locator('.style-calibration > .style-phase').nth(2)
            phase.locator(':scope > summary').click()
            for id in ids:
                card = phase.locator('[data-candidate-id="'+id+'"]')
                card.scroll_into_view_if_needed()
                expect(card.locator('.pooled-image')).to_have_attribute('data-image-state','ready')
            expect(phase.locator('[data-candidate-page="p02"]')).to_have_count(1)
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                phase.locator('[data-candidate-id="'+ids[0]+'"]').scroll_into_view_if_needed()
                screenshot(page,f'candidate-{source}-{width}x{height}')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            page.get_by_role('button',name='待决定',exact=True).click()
            for id in ids:
                card = page.locator('.candidate-batch [data-candidate-id="'+id+'"]')
                card.scroll_into_view_if_needed()
                expect(card.locator('.pooled-image')).to_have_attribute('data-image-state','ready')
            page.get_by_role('button',name='内容与来源',exact=True).click()
            page.get_by_role('heading',name='内容与来源',exact=True).wait_for()
            assert page.evaluate("async () => (await import('/v2/images.js')).imagePool.snapshot().pinned") == 0
        finally:
            browser.close();server.stop()
