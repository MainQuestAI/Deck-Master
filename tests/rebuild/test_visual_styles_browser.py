"""Real Chromium + core transactions, synthetic image; no professional acceptance."""
import uuid
import pytest
from deck_master import tasks
from deck_master.web import WorkbenchServer
from test_styles import flow  # noqa: F401
from test_visual_styles import result,image_bytes

pytestmark=pytest.mark.browser


def click_visual_trial(page, timeout=25000):
    """试作动作属于「试作与采用」阶段；确认与恢复会重挂载界面并合上阶段，
    因此"展开阶段再点"需要可重试——否则点的是被卸载的旧实例。"""
    import time as _time
    from playwright.sync_api import expect
    deadline = _time.time() + timeout / 1000
    last = None
    while _time.time() < deadline:
        open_visual_phase(page, 2)
        trial = page.get_by_role('button', name='预览单页试作', exact=True)
        try:
            expect(trial).to_be_enabled(timeout=3000)
            trial.click(timeout=3000)
            return
        except Exception as error:
            last = error
            page.wait_for_timeout(250)
    raise AssertionError(f'试作动作在阶段 3 未就绪：{last}')


def handoff_action(page):
    """交接动作按真实计划出现；用容器定位以便断言"不出现"（role 定位看不到隐藏元素）。"""
    return page.locator('.visual-plan button').filter(has_text='保存并交接试作')


def open_visual_phase(page, index):
    """四阶段组织（UX-03b）：控件在阶段折叠内，核对前先展开该阶段。

    展开动作与真实用户一致（点击阶段摘要）；自动定位仍由产品负责（有规范即
    打开"确认规范"），这里只补"回看阶段一"这一步。
    """
    phase = page.locator('.visual-style .style-phase').nth(index)
    # Read after the first real click has registered the user's choice. Reading
    # before that click races passive hydration and can double-toggle to closed.
    summary = phase.locator(':scope > summary')
    summary.click()
    if not phase.evaluate('node => node.open'):
        summary.click()
    from playwright.sync_api import expect
    expect(phase).to_have_attribute('open', '')
    return phase


def test_screenshot_ui_upload_reasoning_confirmation_dispatch_and_restore(flow):
    from playwright.sync_api import sync_playwright,expect
    server=WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1280,'height':800});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(server.start());page.get_by_role('heading',name='制作总览',exact=True).wait_for()
            page.get_by_role('button',name='风格校准',exact=True).click()
            page.get_by_role('combobox',name='风格参考来源').select_option('screenshot')
            before=flow.store.load_document()['pages']
            page.get_by_role('textbox',name='截图风格要求').fill('Use palette and hierarchy from this screenshot')
            page.get_by_role('combobox',name='截图风格试作目标').select_option('p02')
            page.get_by_label('导入参考截图',exact=True).set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':image_bytes()})
            expect(page.get_by_role('checkbox',name='选用参考截图 1')).to_be_checked()
            page.get_by_role('button',name='分析截图',exact=True).click()
            expect(page.get_by_role('button',name='查看分析结果',exact=True)).to_be_enabled()
            doc=flow.store.load_document();task=next(flow.store.read_object_json(ref) for ref in reversed(doc['tasks']) if flow.store.read_object_json(ref)['kind']=='style_analyze')
            row=flow.store.read_object_json(doc['style_references'][0]);flow.start(task)
            tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=result(row['reference_id']))
            page.reload();page.get_by_role('button',name='查看分析结果',exact=True).click();page.get_by_text('调整借用维度',exact=True).click();page.get_by_role('textbox',name='配色规范').wait_for()
            page.get_by_role('textbox',name='配色规范').fill('Use blue #225588 and white')
            page.get_by_role('button',name='检查并确认视觉规范',exact=True).click()
            # 确认后自动恢复规范并停在"确认规范"；试作动作属于「试作与采用」阶段，
            # 打开该阶段再试作（恢复链路含规范详情与固定依据读取，放宽等待）。
            assert flow.store.load_document()['pages']==before
            click_visual_trial(page)
            expect(handoff_action(page)).to_be_enabled()
            handoff_action(page).click()
            page.get_by_role('heading',name='当前任务',exact=True).wait_for()
            assert flow.store.load_document()['pages']==before
            assert not errors
        finally:
            if errors: print('BROWSER ERRORS', errors)

            browser.close();server.stop()


def test_large_reference_catalog_releases_images_and_preserves_selection(flow):
    from deck_master import visual_styles
    from playwright.sync_api import sync_playwright,expect
    from PIL import Image
    from io import BytesIO
    # Use unique registered bytes so shared image identities cannot mask leaks.
    for i in range(65):
        stream=BytesIO();Image.new('RGB',(64,36),(i,100,200)).save(stream,format='PNG')
        visual_styles.import_reference(flow.project,data=stream.getvalue(),base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))
    server=WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':800})
        try:
            page.goto(server.start());page.get_by_role('heading',name='制作总览',exact=True).wait_for();page.get_by_role('button',name='风格校准',exact=True).click();page.get_by_role('combobox',name='风格参考来源').select_option('screenshot')
            page.get_by_role('checkbox',name='选用参考截图 1',exact=True).check()
            for _ in range(5):page.get_by_role('button',name='下一组参考',exact=True).click()
            expect(page.get_by_role('checkbox',name='选用参考截图 65',exact=True)).to_be_visible()
            expect(page.get_by_role('checkbox',name='选用参考截图 1',exact=True)).to_be_checked()
            assert page.locator('.visual-reference-choice').count()<=17
            page.get_by_role('checkbox',name='选用参考截图 65',exact=True).check()
            for _ in range(5):page.get_by_role('button',name='上一组参考',exact=True).click()
            expect(page.get_by_role('checkbox',name='选用参考截图 65',exact=True)).to_be_checked()
            assert page.locator('.visual-reference-choice').count()<=17
            assert '阅读位已满' not in page.locator('.visual-reference-list').inner_text()
        finally:browser.close();server.stop()


def test_late_reference_catalog_after_leaving_style_does_not_acquire_images(flow):
    """A real delayed catalog must not recreate a target lease after disposal."""
    from playwright.sync_api import sync_playwright, expect
    from urllib.parse import urlencode
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        held = []
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            url = server.start()
            info = page.request.get(url + 'api/project').json()
            page.goto(url + '#' + urlencode({'project': info['project_identity'], 'surface': 'runs',
                'revision': flow.store.current_revision_id(), 'layer': 'original_image'}))
            page.get_by_role('heading', name='运行记录', exact=True).wait_for()
            page.evaluate('''identity => {
                localStorage.setItem('deck-master:style-source:' + identity, 'screenshot');
                localStorage.setItem('deck-master:visual-style:' + identity,
                    JSON.stringify({ids:[], targets:['p02'], instruction:'Synthetic lease disposal probe'}));
            }''', info['project_identity'])
            def delay(route):
                held.append((route, route.fetch()))
                page.evaluate('() => window.referenceRequestHeld = true')
            page.route('**/api/styles/references?*', delay)
            page.get_by_role('button', name='风格校准', exact=True).click()
            page.wait_for_function('() => window.referenceRequestHeld === true')
            page.get_by_role('button', name='任务与交付', exact=True).click()
            page.get_by_role('heading', name='运行记录', exact=True).wait_for()
            snapshot = "async () => (await import('/v2/images.js')).imagePool.snapshot()"
            assert page.evaluate(snapshot)['pinned'] == 0
            held[0][0].fulfill(response=held[0][1])
            # Allow the real fetch response and its microtask continuation to run.
            page.wait_for_timeout(250)
            pool = page.evaluate(snapshot)
            assert pool['pinned'] == 0 and pool['network'] == 0 and pool['decode'] == 0
            expect(page.locator('.visual-style')).to_have_count(0)
            assert errors == []
        finally:
            browser.close()
            server.stop()


def test_screenshot_state_restores_from_project_on_new_origin_and_replaced_editor(flow):
    """Close both browser/service; restore a real project draft with no storage seed."""
    from playwright.sync_api import sync_playwright, expect
    servers = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        try:
            first = WorkbenchServer(flow.project); servers.append(first)
            first_url = first.start()
            page.goto(first_url); page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
            page.get_by_role('textbox', name='截图风格要求').fill('Cross-origin recovery: preserve complete body')
            page.get_by_role('combobox', name='截图风格试作目标').select_option('p02')
            page.get_by_label('导入参考截图', exact=True).set_input_files(
                {'name':'synthetic-recovery.png','mimeType':'image/png','buffer':image_bytes()})
            expect(page.get_by_role('checkbox', name='选用参考截图 1', exact=True)).to_be_checked()
            page.get_by_role('button', name='分析截图', exact=True).click()
            expect(page.get_by_role('button', name='查看分析结果', exact=True)).to_be_enabled()
            doc = flow.store.load_document()
            task = next(flow.store.read_object_json(ref) for ref in reversed(doc['tasks'])
                        if flow.store.read_object_json(ref)['kind'] == 'style_analyze')
            row = flow.store.read_object_json(doc['style_references'][0])
            # Explicit synthetic Host result; real UI/core writes, zero model calls.
            flow.start(task)
            tasks.accept_result(flow.store, task_id=task['task_id'], operation_id=task['operation_id'],
                produced_against=task['produced_against'], envelope_raw=result(row['reference_id']))
            page.get_by_role('button', name='查看分析结果', exact=True).click()
            page.get_by_text('调整借用维度', exact=True).click()
            page.get_by_role('textbox', name='配色规范', exact=True).fill('Keep edited blue #225588 rules')
            page.get_by_role('button', name='检查并确认视觉规范', exact=True).click()
            # 确认后自动恢复规范；试作动作属于「试作与采用」阶段，确认会重挂载界面。
            click_visual_trial(page)
            expect(handoff_action(page)).to_be_hidden()
            # Returned analysis/recipe pointers must already be on disk before navigation settles.
            saved = page.request.get(first_url + 'api/drafts').json()['records']
            state = next(r['draft']['content']['visual_style'] for r in saved
                         if r['draft']['content'].get('visual_style', {}).get('recipe'))
            assert state['task_id'] == task['task_id'] and state['targets'] == ['p02']
            assert state['spec_edits']['dimensions']['palette'] == 'Keep edited blue #225588 rules'
            recipe_id = state['recipe']
            page.locator('summary').filter(has_text='个人草稿与恢复').click()
            page.get_by_role('textbox', name='个人草稿', exact=True).fill('Saved recovery note')
            expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            browser.close(); first.stop()

            second = WorkbenchServer(flow.project); servers.append(second)
            second_url = second.start(); assert second_url != first_url
            browser = runtime.chromium.launch(args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            page.goto(second_url); page.get_by_role('button', name='风格校准', exact=True).click()
            expect(page.get_by_role('combobox', name='风格参考来源')).to_have_value('screenshot')
            # 恢复后定位在「确认规范」；回看阶段一的选择（参考资料与目标页）需展开该阶段，
            # 并等参考列表读取完成（恢复与列表读取是两个独立请求）。
            open_visual_phase(page, 0)
            expect(page.locator('.visual-reference-choice')).to_have_count(1, timeout=15000)
            # 参考选择由草稿恢复写入：整机负载下要比默认等待更宽（状态本身不放松）。
            expect(page.get_by_role('checkbox', name='选用参考截图 1', exact=True)).to_be_checked(timeout=15000)
            expect(page.get_by_role('combobox', name='截图风格试作目标')).to_have_value('p02')
            expect(page.get_by_role('textbox', name='截图风格要求')).to_have_value('Cross-origin recovery: preserve complete body')
            open_visual_phase(page, 1)
            # 规范先读后改：编辑视图按需展开（已保存的编辑内容不丢）。
            spec_editor = page.locator('.visual-style .visual-spec-editor')
            if not spec_editor.evaluate('node => node.open'): spec_editor.locator(':scope > summary').click()
            expect(page.get_by_role('textbox', name='配色规范', exact=True)).to_have_value('Keep edited blue #225588 rules')
            open_visual_phase(page, 2)
            expect(page.get_by_role('button', name='预览单页试作', exact=True)).to_be_enabled(timeout=15000)
            # A frozen plan is deliberately not restored as an executable pending action.
            expect(handoff_action(page)).to_be_hidden()
            page.locator('summary').filter(has_text='个人草稿与恢复').click()
            restore = page.get_by_role('combobox', name='恢复项目中的个人草稿', exact=True)
            option = restore.locator('option').filter(has_text='Saved recovery note')
            restore.select_option(option.get_attribute('value'))
            expect(page.get_by_role('textbox', name='个人草稿', exact=True)).to_have_value('Saved recovery note')
            open_visual_phase(page, 2)
            expect(page.get_by_role('button', name='预览单页试作', exact=True)).to_be_enabled(timeout=15000)
            # Explicit persisted task/recipe selections work without an automatic latest choice.
            page.locator('summary').filter(has_text='恢复项目中的截图分析与规范').click()
            page.get_by_role('combobox', name='恢复已保存的截图分析').select_option(task['task_id'])
            open_visual_phase(page, 1)
            editor = page.locator('.visual-style .visual-spec-editor')
            if not editor.evaluate('node => node.open'): editor.locator(':scope > summary').click()
            expect(page.get_by_role('textbox', name='配色规范', exact=True)).to_be_visible()
            open_visual_phase(page, 2)
            expect(page.get_by_role('button', name='预览单页试作', exact=True)).to_be_disabled()
            page.get_by_role('combobox', name='恢复已确认的截图规范').select_option(recipe_id)
            expect(page.get_by_role('textbox', name='配色规范', exact=True)).to_have_value('Keep edited blue #225588 rules')
            click_visual_trial(page)
            expect(handoff_action(page)).to_be_enabled()
            # This business write must use the replacement DraftEditor, not its disposed predecessor.
            handoff_action(page).click()
            page.get_by_role('heading', name='当前任务', exact=True).wait_for()
            assert any(flow.store.read_object_json(ref).get('change_binding')
                       for ref in flow.store.load_document()['tasks'])
        finally:
            browser.close()
            for server in servers: server.stop()


def test_saved_analysis_selection_binds_its_reference_and_cancelled_task_stays_stopped(flow):
    from deck_master import service
    from test_visual_styles import imported, analysis
    from playwright.sync_api import sync_playwright, expect
    rows = []
    for label in ('RULE-A', 'RULE-B'):
        row, _, _ = imported(flow); task = analysis(flow, [row['reference_id']]); flow.start(task)
        envelope = result(row['reference_id']); envelope['style_analysis']['dimensions']['palette']['summary'] = label
        tasks.accept_result(flow.store, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], envelope_raw=envelope)
        rows.append((row, task))
    cancelled = analysis(flow, [rows[0][0]['reference_id']])
    service.task_cancel(flow.project, task_id=cancelled['task_id'], reason='Synthetic cancelled recovery probe')
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page(viewport={'width':1280,'height':800})
        try:
            page.goto(server.start()); page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
            page.locator('summary').filter(has_text='恢复项目中的截图分析与规范').click()
            selector = page.get_by_role('combobox', name='恢复已保存的截图分析')
            expect(selector).to_be_enabled()
            # Open B first; then A must switch both rules and the immutable reference selection.
            for index in (1, 0):
                selector.select_option(rows[index][1]['task_id'])
                editor = page.locator('.visual-style .visual-spec-editor:visible').first
                expect(editor).to_be_visible(timeout=15000)
                if not editor.evaluate('node => node.open'):
                    editor.locator(':scope > summary').click()
                expect(editor.get_by_role('textbox', name='配色规范', exact=True)).to_have_value(('RULE-A','RULE-B')[index])
                # 阶段一的选择与规范一并切换：回看该阶段的参考资料。
                open_visual_phase(page, 0)
                expect(page.get_by_role('checkbox', name=f'选用参考截图 {index+1}', exact=True)).to_be_checked()
                expect(page.get_by_role('checkbox', name=f'选用参考截图 {2-index}', exact=True)).not_to_be_checked()
            selector.select_option(cancelled['task_id'])
            expect(page.get_by_role('textbox', name='配色规范', exact=True)).to_have_count(0)
            expect(page.locator('.visual-style [role=status]')).to_contain_text('cancelled')
            expect(page.get_by_role('button', name='检查并确认视觉规范', exact=True)).to_be_disabled()
            open_visual_phase(page, 2)
            expect(page.get_by_role('button', name='预览单页试作', exact=True)).to_be_disabled()
            assert flow.task(cancelled['task_id'])['status'] == 'cancelled'
        finally: browser.close(); server.stop()


def test_late_saved_recipe_read_after_leaving_recovery_does_not_acquire_images(flow):
    from deck_master import styles
    from test_visual_styles import completed
    from playwright.sync_api import sync_playwright, expect
    spec_ref, _, _ = completed(flow)
    proposal = styles.propose(flow.project, input={'schema_version':'style_input.v2',
        'project_id':flow.store.load_document()['project_id'], 'base_revision':flow.store.current_revision_id(),
        'visual_style_ref':spec_ref, 'target_page_ids':['p02'], 'instruction':'Saved recovery lease probe'})
    confirmed = styles.confirm(flow.project, proposal_id=proposal['proposal_id'],
        base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page(viewport={'width':1280,'height':800})
        held = []; errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(server.start()); page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
            page.locator('summary').filter(has_text='恢复项目中的截图分析与规范').click()
            selector = page.get_by_role('combobox', name='恢复已确认的截图规范')
            expect(selector).to_be_enabled()
            assert selector.input_value() == ''  # Existing recipes are never silently selected.
            def delay(route):
                held.append((route, route.fetch()))
                page.evaluate('() => window.recipeReadHeld = true')
            page.route('**/api/styles/' + confirmed['recipe_id'] + '?*', delay)
            selector.select_option(confirmed['recipe_id'])
            page.wait_for_function('() => window.recipeReadHeld === true')
            page.get_by_role('button', name='任务与交付', exact=True).click()
            page.get_by_role('heading', name='运行记录', exact=True).wait_for()
            pool = "async () => (await import('/v2/images.js')).imagePool.snapshot()"
            assert page.evaluate(pool)['pinned'] == 0
            held[0][0].fulfill(response=held[0][1]); page.wait_for_timeout(250)
            assert page.evaluate(pool)['pinned'] == 0
            expect(page.locator('.visual-style')).to_have_count(0)
            assert errors == []
        finally: browser.close(); server.stop()


def test_lost_binary_upload_response_verifies_original_operation_without_duplicate_reference(flow):
    from playwright.sync_api import sync_playwright, expect
    from urllib.parse import parse_qs, urlparse
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(); page = browser.new_page(viewport={'width':1280,'height':800})
        uploads = []; verifies = []
        try:
            url = server.start(); page.goto(url)
            page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('combobox', name='风格参考来源').select_option('screenshot')
            def lose_response(route):
                response = route.fetch()  # The real write completes, only the browser response is lost.
                uploads.append({'operation_id':parse_qs(urlparse(route.request.url).query)['operation_id'][0],
                    'response':response.json()})
                route.abort('failed')
            page.route('**/api/styles/references/import?*', lose_response)
            page.on('request', lambda req: verifies.append(req.url) if '/api/operations/' in req.url else None)
            page.get_by_label('导入参考截图', exact=True).set_input_files(
                {'name':'lost-response.png','mimeType':'image/png','buffer':image_bytes()})
            verify = page.get_by_role('button', name='核实原上传', exact=True)
            expect(verify).to_be_visible()
            assert len(uploads) == 1
            doc = flow.store.load_document(); assert len(doc['style_references']) == 1
            original_ref = doc['style_references'][0]
            operation_id = uploads[0]['operation_id']
            verify.click()
            expect(page.get_by_role('checkbox', name='选用参考截图 1', exact=True)).to_be_checked()
            expect(page.get_by_label('导入参考截图', exact=True)).to_be_enabled()
            expect(page.get_by_role('button', name='核实原上传', exact=True)).to_have_count(0)
            assert len(uploads) == 1  # Verification never issues another upload request.
            assert any(value.endswith('/api/operations/' + operation_id) for value in verifies)
            assert flow.store.load_document()['style_references'] == [original_ref]
            assert uploads[0]['response']['operation_id'] == operation_id
            assert page.request.get(url + 'api/styles/references').json()['references'][0]['ref'] == original_ref
        finally: browser.close(); server.stop()
