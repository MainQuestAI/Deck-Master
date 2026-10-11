"""Formal Studio stages; real core transactions with explicit synthetic Host results."""
import json
import os
from pathlib import Path
import re

import pytest
from deck_master import tasks
from deck_master.web import WorkbenchServer
from test_styles import flow  # noqa: F401
from test_visual_styles import result, image_bytes

pytestmark = pytest.mark.browser


def stage(page, source, number):
    from playwright.sync_api import expect
    selector = '.visual-style' if source == 'screenshot' else '.style-calibration'
    nav = page.locator(selector + ' > .studio-style-stages')
    action = nav.get_by_role('button', name=re.compile(f'^{number} ·'))
    action.click()
    expect(action).to_have_attribute('aria-pressed', 'true')
    assert page.locator(selector + ' > section.style-phase:visible').count() == 1
    assert page.locator(selector + ' > details.style-phase').count() == 0
    return page.locator(selector + ' > section.style-phase').nth(number - 1)


@pytest.mark.parametrize('source', ['page', 'screenshot'])
def test_studio_style_two_routes_compare_adopt_expand_and_review(flow, source, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    out = Path(os.environ.get('STUDIO_STYLE_EVIDENCE', str(tmp_path/'evidence'))) / source
    out.mkdir(parents=True, exist_ok=True)
    server = WorkbenchServer(flow.project)
    initial = flow.store.load_document()['pages']
    third_title = flow.store.read_object_json(initial[2]['page'])['customer_visible']['title']
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':900})
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda r: requests.append({'method':r.method,'url':r.url.split('/api/')[-1],'body':r.post_data}) if '/api/' in r.url and r.method == 'POST' else None)
        try:
            page.goto(server.start()+'studio/')
            page.locator('.sidebar').get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('button',name='项目页面' if source=='page' else '外部图片',exact=True).click()
            stage(page, source, 1)
            if source == 'page':
                page.get_by_label('风格参考原图', exact=True).select_option('p01')
                page.get_by_label('当前风格试作目标', exact=True).select_option('p02')
                expect(page.locator('.style-calibration > .style-primary-phase .studio-style-targets .style-target-card').first).to_be_visible()
                geometry=[]
                for width,height in [(1440,900),(1280,800),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height});page.evaluate('window.scrollTo(0,0)')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    action=page.get_by_role('button',name='检查风格要求',exact=True).bounding_box()
                    reference_box=page.get_by_label('风格参考原图',exact=True).bounding_box()
                    target_box=page.locator('.style-calibration > .style-primary-phase .studio-style-targets .style-target-card').first.bounding_box()
                    assert action['y']+action['height']<=height and reference_box['y']+44<=height
                    if width>=768:assert target_box['y']+44<=height
                    geometry.append({'width':width,'height':height,'reference':reference_box,'target':target_box,'main_action':action})
                    page.screenshot(path=str(out/f'00-selected-first-viewport-{width}.png'))
                (out/'first-viewport.json').write_text(json.dumps(geometry,indent=2))
                page.set_viewport_size({'width':1440,'height':900})
                page.get_by_label(re.compile('^风格目标 第 3 页')).check()
                page.screenshot(path=str(out/'01-reference-target.png'), full_page=True)
                page.get_by_role('button', name='检查风格要求', exact=True).click()
                expect(page.get_by_role('button', name='确认这版风格要求', exact=True)).to_be_enabled()
                stage(page, source, 1)
                assert page.get_by_label('风格参考原图', exact=True).input_value() == 'p01'
                stage(page, source, 2)
                page.screenshot(path=str(out/'02-rules.png'), full_page=True)
                page.get_by_role('button', name='确认这版风格要求', exact=True).click()
                expect(page.get_by_label('已确认的风格版本').locator('option')).to_have_count(2)
                recipe_id=page.get_by_label('已确认的风格版本').locator('option').nth(1).get_attribute('value')
                dispatch_label='保存并交接风格试作'
            else:
                page.get_by_label('截图风格试作目标', exact=True).select_option('p02')
                page.get_by_label('允许后续风格扩展到 '+third_title, exact=True).check()
                page.get_by_label('导入参考截图', exact=True).set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':image_bytes()})
                expect(page.get_by_label('选用参考截图 1', exact=True)).to_be_checked()
                page.screenshot(path=str(out/'01-reference-target.png'), full_page=True)
                page.get_by_role('button', name='分析截图', exact=True).click()
                expect(page.locator('.visual-upload-recovery')).to_be_empty()
                stage(page, source, 2)
                expect(page.get_by_role('button', name='查看分析结果', exact=True)).to_be_enabled()
                doc=flow.store.load_document()
                analysis=next(flow.store.read_object_json(ref) for ref in reversed(doc['tasks']) if flow.store.read_object_json(ref)['kind']=='style_analyze')
                reference=flow.store.read_object_json(doc['style_references'][0]);flow.start(analysis)
                tasks.accept_result(flow.store, task_id=analysis['task_id'], operation_id=analysis['operation_id'], produced_against=analysis['produced_against'], envelope_raw=result(reference['reference_id']))
                page.get_by_role('button', name='查看分析结果', exact=True).click()
                expect(page.locator('.studio-style-rule')).to_have_count(7)
                expect(page.locator('.visual-breakdown')).to_be_visible()
                assert page.locator('.studio-rule-editor:visible').count()==0
                page.get_by_role('button',name='编辑配色',exact=True).click()
                page.get_by_label('配色规范',exact=True).fill('Borrow blue #225588 and white; preserve the complete target text')
                page.get_by_role('button',name='编辑文字层级',exact=True).click()
                expect(page.get_by_label('配色规范',exact=True)).to_be_hidden()
                assert page.locator('.studio-rule-editor:visible').count()==1
                page.get_by_role('button',name='编辑文字层级',exact=True).click()
                expect(page.locator('.studio-style-rule').filter(has=page.get_by_role('heading',name='配色',exact=True))).to_contain_text('Borrow blue #225588')
                for width,height in [(1440,900),(1280,800),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert page.locator('.visual-style > .studio-style-stages button').evaluate_all('(nodes)=>nodes.every(n=>n.getBoundingClientRect().height>=44)')
                    page.screenshot(path=str(out/f'02-rules-{width}.png'),full_page=True)
                page.set_viewport_size({'width':1440,'height':900})
                page.get_by_role('button',name='检查并确认视觉规范',exact=True).click()
                expect(page.get_by_label('已确认的截图规范').locator('option')).to_have_count(2)
                expect(page.locator('.visual-upload-recovery')).to_be_empty()
                recipe_id=page.get_by_label('已确认的截图规范').locator('option').nth(1).get_attribute('value')
                dispatch_label='保存并交接试作'
            # Reading other phases must preserve the actual confirmed recipe.
            stage(page, source, 3)
            trial=page.get_by_role('button',name='预览单页试作',exact=True)
            expect(trial).to_be_enabled()
            page.get_by_role('button',name='外部图片' if source=='page' else '项目页面',exact=True).click()
            page.get_by_role('button',name='项目页面' if source=='page' else '外部图片',exact=True).click()
            expect(trial).to_be_visible()
            page.screenshot(path=str(out/'03-trial.png'),full_page=True)
            trial.click()
            expect(page.get_by_role('button',name=dispatch_label,exact=True)).to_be_enabled()
            page.get_by_role('button',name=dispatch_label,exact=True).click()
            expect(page.locator('#runs-tasks .task-handoff')).to_be_visible()
            task=next(flow.store.read_object_json(ref) for ref in reversed(flow.store.load_document()['tasks']) if flow.store.read_object_json(ref)['kind']=='blueprint')
            assert task['scope_pages']==['p02'] and flow.store.load_document()['pages']==initial
            candidate=flow.image(task)['candidate_ids'][0]
            def adopt(candidate, filename):
                page.reload();page.get_by_role('button',name='查看当前版本',exact=True).click()
                page.get_by_role('button',name='待决定',exact=True).click()
                page.locator(f'.candidate-batch [data-candidate-id="{candidate}"]').get_by_role('button',name='比较这个候选',exact=True).click()
                expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id',candidate)
                page.screenshot(path=str(out/filename),full_page=True)
                page.get_by_role('button',name='预览采用这个候选',exact=True).click()
                page.get_by_role('button',name='采用这个候选',exact=True).click()
                expect(page.locator('.candidate-state')).to_contain_text('当前采用')
            adopt(candidate,'04-compare.png')
            after_trial=flow.store.load_document()['pages']
            assert after_trial[0]==initial[0] and after_trial[2]==initial[2]
            page.get_by_role('button',name='查看任务与交付',exact=True).click()
            expect(page.get_by_role('heading',name='任务与交付',exact=True)).to_be_visible()
            page.locator('.sidebar').get_by_role('button',name='风格校准',exact=True).click()
            page.get_by_role('button',name='项目页面' if source=='page' else '外部图片',exact=True).click()
            if source=='screenshot':
                page.get_by_role('button',name='恢复项目中的截图分析与规范',exact=True).click()
                page.get_by_label('已确认的截图规范').select_option(recipe_id)
                expect(page.locator('.visual-style > [role=status]')).to_contain_text('已打开所选确认规范')
                stage(page,source,4)
                page.get_by_label('已采用的截图风格样例').select_option(candidate)
                page.get_by_label('本次扩展到 '+third_title,exact=True).check()
                page.get_by_role('button',name='预览所选页扩展',exact=True).click()
            else:
                stage(page,source,2)
                page.locator(f'.studio-recipe-card[data-recipe-id="{recipe_id}"]').get_by_role('button').click()
                stage(page,source,3)
                page.get_by_role('button',name='从此候选扩展',exact=True).click()
                page.get_by_label(re.compile('^扩展到 第 3 页')).check()
                page.get_by_role('button',name='预览明确选页的扩展',exact=True).click()
            page.screenshot(path=str(out/'05-expansion-review.png'),full_page=True)
            page.get_by_role('button',name=dispatch_label,exact=True).click()
            expect(page.locator('#runs-tasks .task-handoff')).to_be_visible()
            expansion=next(flow.store.read_object_json(ref) for ref in reversed(flow.store.load_document()['tasks']) if flow.store.read_object_json(ref)['kind']=='blueprint')
            assert expansion['scope_pages']==['p03'] and flow.store.load_document()['pages']==after_trial
            cid=flow.image(expansion)['candidate_ids'][0]
            adopt(cid,'06-expansion-compare.png')
            final=flow.store.load_document()['pages']
            assert final[:2]==after_trial[:2] and final[2]!=after_trial[2]
            assert not errors
            (out/'business-states.json').write_text(json.dumps({'initial':initial,'trial_adopted':after_trial,'expansion_adopted':final,'synthetic_host':True,'errors':errors},indent=2))
        finally:
            (out/'requests.json').write_text(json.dumps(requests,indent=2))
            page.screenshot(path=str(out/'last-state.png'),full_page=True)
            browser.close();server.stop()


def test_studio_recipe_library_search_paging_and_selection_survive_navigation(flow, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    from test_styles import confirm, value
    ids=[]
    for number in range(13):
        ids.append(confirm(flow,value(flow,instruction=f'规范检索 {number+1:02d}：保留完整正文'))['recipe_id'])
    before=flow.store.current_revision_id()
    server=WorkbenchServer(flow.project)
    out=Path(os.environ.get('STUDIO_STYLE_EVIDENCE',str(tmp_path/'evidence'))) / 'recipe-library'
    out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(server.start()+'studio/')
            page.locator('.sidebar').get_by_role('button',name='风格校准',exact=True).click()
            page.get_by_role('button',name='项目页面',exact=True).click()
            stage(page,'page',2)
            expect(page.locator('.studio-recipe-card')).to_have_count(6)
            expect(page.get_by_label('已确认的风格版本')).to_be_hidden()
            chosen=page.locator('.studio-recipe-card').nth(2)
            chosen_id=chosen.get_attribute('data-recipe-id')
            chosen.get_by_role('button').click()
            selected=page.locator('.studio-recipe-current').inner_text()
            page.get_by_role('button',name='下一组规范',exact=True).click()
            expect(page.locator('.studio-recipe-card')).to_have_count(6)
            expect(page.locator('.studio-recipe-current')).to_have_text(selected)
            page.get_by_role('button',name='下一组规范',exact=True).click()
            expect(page.locator('.studio-recipe-card')).to_have_count(1)
            expect(page.get_by_role('button',name='下一组规范',exact=True)).to_be_disabled()
            search=page.get_by_role('searchbox',name='搜索已确认风格规范',exact=True)
            search.fill('规范检索 07')
            expect(page.locator('.studio-recipe-card')).to_have_count(1)
            search.fill('没有此规范')
            expect(page.locator('.studio-recipe-list')).to_contain_text('当前选择保持不变')
            expect(page.locator('.studio-recipe-current')).to_have_text(selected)
            search.fill('')
            expect(page.locator('.studio-recipe-card')).to_have_count(6)
            expect(page.locator(f'.studio-recipe-card[data-recipe-id="{chosen_id}"]').get_by_role('button')).to_have_attribute('aria-pressed','true')
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(out/f'library-{width}.png'),full_page=True)
            stage(page,'page',3)
            expect(page.get_by_role('button',name='预览单页试作',exact=True)).to_be_enabled()
            stage(page,'page',2)
            expect(page.locator('.studio-recipe-current')).to_have_text(selected)
            assert flow.store.current_revision_id()==before and not errors
        finally:
            browser.close();server.stop()


@pytest.mark.parametrize('invalidate', [False, True])
def test_screenshot_plan_freezes_target_and_rejects_late_response(flow, invalidate):
    """Real plan response held while the user reads target controls or leaves."""
    import uuid
    from deck_master import styles
    from test_visual_styles import completed
    from playwright.sync_api import sync_playwright, expect
    ref, _, _ = completed(flow)
    proposed = styles.propose(flow.project, input={'schema_version':'style_input.v2',
        'project_id':flow.store.load_document()['project_id'], 'base_revision':flow.store.current_revision_id(),
        'visual_style_ref':ref, 'target_page_ids':['p02','p03'], 'instruction':'借用配色'})
    rid = styles.confirm(flow.project, proposal_id=proposed['proposal_id'],
        base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']['recipe_id']
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        held = []
        try:
            page.goto(server.start()+'studio/')
            page.locator('.sidebar').get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('button', name='外部图片', exact=True).click()
            page.get_by_role('button', name='恢复项目中的截图分析与规范', exact=True).click()
            page.get_by_label('已确认的截图规范').select_option(rid)
            expect(page.locator('.visual-style > [role=status]')).to_contain_text('已打开所选确认规范')
            stage(page, 'screenshot', 3)
            page.route('**/api/styles/plan', lambda route: held.append((route, route.fetch())))
            page.get_by_role('button', name='预览单页试作', exact=True).click()
            stage(page, 'screenshot', 1)
            expect(page.get_by_label('截图风格试作目标', exact=True)).to_be_disabled()
            expect(page.get_by_role('button', name='先试此页', exact=True).first).to_be_disabled()
            expect(page.get_by_label(re.compile('^允许后续风格扩展到 ')).first).to_be_disabled()
            assert held
            if invalidate:
                page.locator('.sidebar').get_by_role('button', name='制作总览', exact=True).click()
                expect(page.locator('.visual-style')).to_have_count(0)
            route, response = held.pop()
            route.fulfill(response=response)
            if invalidate:
                expect(page.get_by_role('button', name='保存并交接试作', exact=True)).to_have_count(0)
                assert not any(flow.store.read_object_json(r)['kind']=='blueprint' for r in flow.store.load_document()['tasks'])
            else:
                expect(page.locator('.visual-plan')).to_contain_text('第 2 页')
                page.get_by_role('button', name='保存并交接试作', exact=True).click()
                expect(page.locator('#runs-tasks .task-handoff')).to_be_visible()
                task = next(flow.store.read_object_json(r) for r in reversed(flow.store.load_document()['tasks']) if flow.store.read_object_json(r)['kind']=='blueprint')
                assert task['scope_pages'] == ['p02']
        finally:
            browser.close()
            server.stop()
