"""Content areas in Studio exercise actual plans/commits; no Host calls."""
import json
import os
from pathlib import Path
import re
import uuid
import pytest
from deck_master import collaboration
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from rc3_fixtures import authorize_scope, evidence_for

pytestmark=pytest.mark.browser


def authorize_content_edits(project):
    """Explicit L1 editorial permission; no image calls or candidate adoption."""
    store = Store(project)
    scope = dict(store.load_document()['collaboration']['request']['scope'])
    scope['layers'] = ['plan', 'page_copy', 'speech', 'review']
    evidence = evidence_for(project,
        text='L1 browser editorial exercise on named Pages ' + ','.join(scope['page_ids']) +
             ': preserve facts and sources; allow explicit order/membership changes; no image calls.',
        locator='L1:content-browser:direction-and-zero-call-grant')
    collaboration.record_decision(project, input={'topic': 'direction', 'disposition': 'accepted',
        'authority_mode': 'direct_user', 'value': 'Preserve the synthetic manuscript facts and source versions.',
        'scope': scope, 'instruction_evidence': evidence, 'subject_refs': []},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    authorize_scope(project, actions=['content.operation'], scope=scope, max_external_calls=0,
        max_candidate_count=0, adoption_policy='within_scope', evidence=evidence)


def test_studio_content_order_preview_cancel_and_plan_commit(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    project=tmp_path/'content-project';create_gallery_sample(project,page_count=24,readonly=False)
    authorize_content_edits(project)
    store=Store(project);initial=store.load_document();assert initial['content_plan']
    server=WorkbenchServer(project)
    out=Path(os.environ.get('STUDIO_CONTENT_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900});errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda r:requests.append({'method':r.method,'url':r.url.split('/api/')[-1],'body':r.post_data}) if '/api/' in r.url and r.method=='POST' else None)
        try:
            page.goto(server.start()+'studio/');page.get_by_role('button',name='内容与页序',exact=True).click()
            nav=page.get_by_role('navigation',name='内容工作区',exact=True)
            expect(page.locator('.studio-content-area:visible')).to_have_count(1)
            expect(page.locator('#content-area-pages')).to_be_visible()
            nav.get_by_role('button',name='更多内容工具',exact=True).click()
            nav.get_by_role('button',name='工作笔记',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_be_visible()
            page.get_by_label('个人草稿',exact=True).fill('Studio 工作笔记：切换工作区后保留')
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            nav.get_by_role('button',name='逐页稿',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_be_hidden()
            nav.get_by_role('button',name='更多内容工具',exact=True).click()
            nav.get_by_role('button',name='工作笔记',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('Studio 工作笔记：切换工作区后保留')
            page.reload()
            nav.get_by_role('button',name='更多内容工具',exact=True).click()
            nav.get_by_role('button',name='工作笔记',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('Studio 工作笔记：切换工作区后保留')
            nav.get_by_role('button',name='逐页稿',exact=True).click()
            order=page.locator('.content-order-row')
            geometry=[]
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.evaluate('window.scrollTo(0,0)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                row=order.first.bounding_box();action=page.get_by_role('button',name='预览页序变更',exact=True).bounding_box()
                handle=order.first.locator('.order-handle').bounding_box();check=order.first.get_by_role('checkbox').bounding_box()
                assert handle['y']+handle['height']<=height and check['y']+check['height']<=height and action['y']+action['height']<=height
                expect(page.locator('.content-impact')).to_be_hidden()
                geometry.append({'width':width,'height':height,'first_row':row,'first_page_button':handle,'first_checkbox':check,'main_action':action})
                page.screenshot(path=str(out/f'00-order-first-viewport-{width}.png'))
            (out/'first-viewport.json').write_text(json.dumps(geometry,indent=2))
            page.set_viewport_size({'width':1440,'height':900})
            page.get_by_role('button',name='查看输入判断',exact=True).click()
            expect(page.get_by_role('dialog',name='输入判断与依据',exact=True)).to_be_visible()
            expect(page.get_by_role('dialog')).to_contain_text('内容整合')
            expect(page.locator('#content-area-pages')).to_be_visible()
            page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).click()
            expect(page.get_by_role('button',name='查看输入判断',exact=True)).to_be_focused()
            old_ids=order.evaluate_all('(rows)=>rows.map(r=>r.dataset.pageId)')
            first=order.first
            first.get_by_role('button',name='第 1 页操作',exact=True).click()
            first.get_by_role('button',name=re.compile('^向后移动 ')).click()
            reordered=order.evaluate_all('(rows)=>rows.map(r=>r.dataset.pageId)')
            assert reordered==[old_ids[1],old_ids[0],*old_ids[2:]]
            page.get_by_role('button',name='预览页序变更',exact=True).click()
            commit=page.get_by_role('button',name='确认内容变更',exact=True)
            expect(commit).to_be_enabled()
            assert store.load_document()==initial
            page.get_by_role('button',name='取消本次核对，保留编辑',exact=True).click()
            expect(commit).to_be_disabled()
            assert order.evaluate_all('(rows)=>rows.map(r=>r.dataset.pageId)')==reordered
            page.get_by_role('button',name='预览页序变更',exact=True).click()
            page.screenshot(path=str(out/'01-order-review.png'),full_page=True)
            with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/content/commit')) as receipt:commit.click()
            assert receipt.value.ok
            revision=receipt.value.json()['operation_result']['revision_id']
            expect(page).to_have_url(re.compile('revision='+revision))
            expect(page.locator('#content-area-pages')).to_be_visible()
            after_order=store.load_document()
            assert [p['page_id'] for p in after_order['pages']]==reordered
            selected=page.locator('.content-order-row').first.get_by_role('checkbox');selected.check()
            requirement=page.get_by_label('选页调整要求',exact=True);requirement.fill('保留事实与数字，调整表达顺序')
            before_tasks=after_order['tasks']
            for action in ['改写','拆分','移除']:
                page.get_by_role('group',name='选页调整方式').get_by_role('button',name=action,exact=True).click()
                if action=='拆分':page.get_by_label('拆分位置与方式',exact=True).fill('在第二个要点后拆分，前半页介绍现状，后半页说明行动。')
                page.get_by_role('button',name={'改写':'预览选页改写','拆分':'预览拆分选页','移除':'预览移除选页'}[action],exact=True).click()
                action_commit=page.locator('.studio-content-review .content-operation > button')
                expect(action_commit).to_be_enabled()
                page.screenshot(path=str(out/f'02-{action}-review.png'),full_page=True)
                page.get_by_role('button',name='取消本次核对，保留编辑',exact=True).click()
                expect(action_commit).to_be_disabled()
                assert store.load_document()['tasks']==before_tasks and store.current_revision_id()==after_order['revision_id']
            page.locator('.content-order-row').nth(1).get_by_role('checkbox').check()
            page.get_by_role('group',name='选页调整方式').get_by_role('button',name='合并',exact=True).click()
            page.get_by_label('合并后的页面标题',exact=True).fill('合并后的事实与行动')
            page.get_by_role('button',name='预览合并选页',exact=True).click()
            expect(page.get_by_role('button',name='确认并交接内容调整',exact=True)).to_be_enabled()
            requirement.fill('核对后又修改要求，旧计划不能提交')
            expect(page.get_by_role('button',name='确认并交接内容调整',exact=True)).to_be_disabled()
            assert store.load_document()['tasks']==before_tasks
            nav.get_by_role('button',name='章节与计划',exact=True).click()
            expect(page.get_by_label('内容整合结论',exact=True)).to_have_attribute('readonly','')
            chapter_name=page.get_by_label('章节名称 1',exact=True);chapter_name.fill('完整内容计划验证：保持全部稳定页面身份')
            card=page.locator('.studio-goal-card').first
            card.get_by_role('button',name='编辑页面目标',exact=True).click()
            expect(card).to_contain_text('尚未登记材料。可以先保留页面目标与待确认事实，登记材料后再关联。')
            expect(card.locator('.studio-goal-source-choices input')).to_have_count(0)
            card.get_by_label(re.compile('^页面目标 ')).fill('页面目标已按正式编辑器调整')
            page.get_by_role('button',name='预览内容计划变更',exact=True).click()
            expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_enabled()
            page.get_by_role('button',name='取消本次核对，保留编辑',exact=True).click()
            assert store.load_document()==after_order
            page.get_by_role('button',name='预览内容计划变更',exact=True).click()
            page.screenshot(path=str(out/'03-plan-review.png'),full_page=True)
            with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/api/content/commit')) as receipt:page.get_by_role('button',name='确认内容变更',exact=True).click()
            revision=receipt.value.json()['operation_result']['revision_id']
            expect(page).to_have_url(re.compile('revision='+revision))
            expect(page.locator('#content-area-plan')).to_be_visible()
            final=store.load_document();saved=store.read_object_json(final['content_plan'])['input']
            assert saved['schema_version']=='content_plan_input.v2'
            assert saved['chapters'][0]['title']=='完整内容计划验证：保持全部稳定页面身份'
            assert any(role['intended_takeaway']=='页面目标已按正式编辑器调整' for role in saved['page_roles'])
            previous_input=store.read_object_json(after_order['content_plan'])['input']
            for key in ['page_budget','time_budget','speech_policy','issues','tradeoff_issue_ids','page_order']:
                assert saved[key]==previous_input[key]
            assert saved['page_roles'][1:]==previous_input['page_roles'][1:]
            assert final['pages']==after_order['pages'] and final['tasks']==after_order['tasks']
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(out/f'04-plan-{width}.png'),full_page=True)
            from urllib.parse import urlencode
            identity=page.request.get(server.start()+'api/project').json()['project_identity']
            page.goto(server.start()+'studio/#'+urlencode({'project':identity,'surface':'content','revision':initial['revision_id'],'layer':'content'}))
            expect(page.get_by_text('此处只读固定版本的内容目标与来源，不混入当前任务要求。',exact=True)).to_be_visible()
            nav.get_by_role('button',name='逐页稿',exact=True).click()
            expect(page.locator('.content-order-row').first.get_by_role('checkbox')).to_be_disabled()
            expect(page.get_by_role('button',name='预览页序变更',exact=True)).to_have_count(0)
            nav.get_by_role('button',name='章节与计划',exact=True).click()
            expect(page.get_by_label('章节名称 1',exact=True)).to_have_attribute('readonly','')
            expect(page.get_by_role('button',name='预览内容计划变更',exact=True)).to_have_count(0)
            nav.get_by_role('button',name='更多内容工具',exact=True).click()
            nav.get_by_role('button',name='工作笔记',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_have_attribute('readonly','')
            assert store.load_document()==final and not errors
            (out/'states.json').write_text(json.dumps({'initial':initial,'after_order':after_order,'final':final,'errors':errors},ensure_ascii=False,indent=2))
        finally:
            (out/'requests.json').write_text(json.dumps(requests,indent=2))
            page.screenshot(path=str(out/'last-state.png'),full_page=True)
            browser.close();server.stop()


def test_studio_content_chapters_and_materials_have_separate_primary_areas(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    from deck_master import content_ops,tasks
    from test_content_candidates import start_task,accept
    import uuid,copy
    project=tmp_path/'overview';create_gallery_sample(project,page_count=24,readonly=False);store=Store(project)
    authorize_content_edits(project)
    material=tmp_path/'范围与事实.md';material.write_text('# 隔离合成材料\n原有章节与页面无需改变。')
    update=content_ops.inputs(project,input={'reason':'隔离界面验证：加入原文材料','source_changes':{'add':[{'path':str(material)}]}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    task=tasks._lookup_task(store.load_document(),update['pending_tasks'][0]['task_id'],store);start_task(project,task)
    doc=store.load_document();impact='新材料补充背景。已有24页事实、范围与章节顺序保持不变。'
    accept(project,task,{'kind':'compose','content_update':{'input_digest':task['input_digest'],'upsert_pages':[],'remove_page_ids':[],'page_order':[p['page_id'] for p in doc['pages']],'impact_summary':impact,'unchanged_reason':'新增材料仅用于核对原事实，不需要重写页面。'},'content_plan':copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])})
    before=store.load_document();server=WorkbenchServer(project);out=Path(os.environ.get('STUDIO_CONTENT_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True)
    geometry=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(server.start()+'studio/');page.get_by_role('button',name='内容与页序',exact=True).click()
            nav=page.get_by_role('navigation',name='内容工作区',exact=True)
            nav.get_by_role('button',name='章节与计划',exact=True).click()
            chapter=page.locator('#content-area-plan .outline-block').first
            material_card=page.locator('.studio-material-card').first
            expect(chapter).to_be_visible();expect(material_card).to_be_hidden();expect(page.locator('.content-impact')).to_have_count(0)
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.evaluate('scrollTo(0,0)')
                nav.get_by_role('button',name='章节与计划',exact=True).click();page.evaluate('scrollTo(0,0)')
                chapter_box=chapter.bounding_box()
                assert chapter_box['y']+44<=height
                nav.get_by_role('button',name='材料与来源',exact=True).click();page.evaluate('scrollTo(0,0)')
                material_box=material_card.bounding_box()
                assert material_box['y']+44<=height
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(out/f'overview-first-{width}.png'),full_page=True)
                geometry.append({'width':width,'height':height,'chapter':chapter_box,'material':material_box})
            button=page.get_by_role('button',name='查看输入判断',exact=True);button.click()
            dialog=page.get_by_role('dialog',name='输入判断与依据',exact=True)
            expect(dialog).to_contain_text(impact)
            expect(dialog).to_contain_text('无正文变化依据：新增材料仅用于核对原事实，不需要重写页面。')
            expect(dialog).to_contain_text('内容整合')
            page.screenshot(path=str(out/'overview-input-judgment.png'),full_page=True)
            dialog.get_by_role('button',name='关闭',exact=True).click();expect(button).to_be_focused();expect(material_card).to_be_visible()
            assert store.load_document()==before and errors==[]
            (out/'overview-first.json').write_text(json.dumps({'geometry':geometry,'errors':errors,'unchanged_revision':store.current_revision_id()},ensure_ascii=False,indent=2))
        finally:browser.close();server.stop()


def test_studio_goal_material_links_keep_fixed_source_versions_and_recover(tmp_path):
    """Choose actual extracted locations, cancel/reload draft, commit, reject stale plan."""
    import copy,uuid
    from playwright.sync_api import sync_playwright,expect
    from deck_master import content_ops,tasks
    from test_content_candidates import start_task,accept
    project=tmp_path/'goal-links';create_gallery_sample(project,page_count=24,readonly=False);store=Store(project)
    authorize_content_edits(project)
    materials=[]
    for name,text in [('业务事实.md','# 已登记的事实\n第一条事实。\n第二条事实。'),('范围约束.md','# 范围约束\n保留全部页面身份。')]:
        path=tmp_path/name;path.write_text(text);materials.append(path)
    result=content_ops.inputs(project,input={'reason':'隔离材料关联验收','source_changes':{'add':[{'path':str(p)} for p in materials]}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    task=tasks._lookup_task(store.load_document(),result['pending_tasks'][0]['task_id'],store);start_task(project,task);doc=store.load_document()
    accept(project,task,{'kind':'compose','content_update':{'input_digest':task['input_digest'],'upsert_pages':[],'remove_page_ids':[],'page_order':[p['page_id'] for p in doc['pages']],'impact_summary':'隔离样例加入材料；页面不变。','unchanged_reason':'仅登记验证依据。'},'content_plan':copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])})
    before=store.load_document();server=WorkbenchServer(project)
    out=Path(os.environ.get('STUDIO_CONTENT_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True)
    requests=[];errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append({'method':r.method,'url':r.url.split('/api/')[-1],'body':r.post_data}) if '/api/' in r.url and r.method=='POST' else None)
        try:
            base=server.start();page.goto(base+'studio/');page.get_by_role('button',name='内容与页序',exact=True).click()
            page.get_by_role('navigation',name='内容工作区').get_by_role('button',name='章节与计划',exact=True).click()
            card=page.locator('.studio-goal-card').first
            # A controlled read failure leaves the source unselectable and offers retry.
            def fail_read(route):
                route.fulfill(status=503,content_type='application/json',body=json.dumps({'error':{'code':'test_read_unavailable','message':'隔离验证读取失败'}}))
            page.route('**/api/content/sources/*',fail_read)
            card.get_by_role('button',name='编辑页面目标',exact=True).click()
            expect(card.get_by_role('button',name='重试读取材料位置 业务事实.md',exact=True)).to_be_visible()
            assert store.load_document()==before
            page.unroute('**/api/content/sources/*',fail_read)
            for name in ['业务事实.md','范围约束.md']:card.get_by_role('button',name='重试读取材料位置 '+name,exact=True).click()
            checks=card.locator('.studio-goal-source-choice input[type=checkbox]');expect(checks).to_have_count(2)
            check=card.get_by_label('关联材料 业务事实.md 到第 1 页',exact=True);expect(check).not_to_be_checked()
            location=card.get_by_label('材料位置 业务事实.md · 第 1 页',exact=True)
            values=location.locator('option').evaluate_all('(opts)=>opts.map(o=>o.value)');assert len(values)>=2
            location.select_option(values[1]);expect(check).to_be_checked()
            card.get_by_label('关联材料 范围约束.md 到第 1 页',exact=True).check()
            expect(card.locator('.studio-goal-linked button')).to_have_count(2)
            page.get_by_role('button',name='预览内容计划变更',exact=True).click();submit=page.get_by_role('button',name='确认内容变更',exact=True);expect(submit).to_be_enabled()
            posted=json.loads(next(r['body'] for r in reversed(requests) if r['url']=='content/plan'))['input']
            assert posted['content_plan']['schema_version']=='content_plan_input.v2'
            links=posted['content_plan']['page_roles'][0]['source_links'];assert len(links)==2
            sources={s['source_id']:s for s in before['sources']}
            for link in links:
                source=sources[link['source_id']];assert link['source_version']=={'original_sha256':source.get('original_sha256'),'extract':source.get('extract')}
                extracted=store.read_object_json(source['extract']);assert link['locator'] in {r['locator'] for r in extracted['locators']}
            page.get_by_role('button',name='取消本次核对，保留编辑',exact=True).click();expect(submit).to_be_disabled();assert store.load_document()==before
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            page.reload();page.get_by_role('navigation',name='内容工作区').get_by_role('button',name='章节与计划',exact=True).click()
            card=page.locator('.studio-goal-card').first;card.get_by_role('button',name='编辑页面目标',exact=True).click()
            expect(card.get_by_label('关联材料 业务事实.md 到第 1 页',exact=True)).to_be_checked();expect(card.get_by_label('关联材料 范围约束.md 到第 1 页',exact=True)).to_be_checked()
            expect(card.get_by_label('材料位置 业务事实.md · 第 1 页',exact=True)).to_have_value(values[1])
            card.get_by_role('button',name=re.compile('^查看目标来源 业务事实.md')).click()
            expect(page.get_by_role('dialog')).to_contain_text('已定位：'+values[1]);page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).click()
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});card.scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(out/f'goal-materials-{width}.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':900});page.get_by_role('button',name='预览内容计划变更',exact=True).click();expect(submit).to_be_enabled()
            old_card=card.element_handle()
            with page.expect_response(lambda r:r.url.endswith('/api/content/commit') and r.request.method=='POST') as receipt:submit.click()
            assert receipt.value.ok;revision=receipt.value.json()['operation_result']['revision_id'];expect(page).to_have_url(re.compile('revision='+revision))
            page.wait_for_function('(el)=>!el.isConnected',arg=old_card)
            saved=store.load_document();saved_input=store.read_object_json(saved['content_plan'])['input']
            assert saved_input['page_roles'][0]['source_links']==links
            before_input=store.read_object_json(before['content_plan'])['input']
            for key in ['chapters','page_order','page_budget','time_budget','speech_policy','issues','tradeoff_issue_ids']:
                assert saved_input[key]==before_input[key]
            assert saved['pages']==before['pages'] and saved['sources']==before['sources']
            # A material update between preview and commit must reject the old binding.
            card=page.locator('.studio-goal-card').first;card.get_by_role('button',name='编辑页面目标',exact=True).click()
            card.get_by_label('关联材料 范围约束.md 到第 1 页',exact=True).uncheck();page.get_by_role('button',name='预览内容计划变更',exact=True).click();expect(submit).to_be_enabled()
            state={}
            def advance_then_submit(route):
                changed=tmp_path/'新业务事实.md';changed.write_text('# 新版事实\n必须重新核对的版本。')
                state['revision']=content_ops.inputs(project,input={'reason':'隔离并发材料替换','source_changes':{'replace':[{'source_id':links[0]['source_id'],'path':str(changed)}]}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']['revision_id']
                route.continue_()
            page.route('**/api/content/commit',advance_then_submit)
            with page.expect_response(lambda r:r.url.endswith('/api/content/commit') and r.request.method=='POST') as rejected:submit.click()
            assert rejected.value.status==409
            assert store.current_revision_id()==state['revision'] and store.load_document()['content_plan']==saved['content_plan']
            expect(submit).to_be_disabled();assert not errors
            page.screenshot(path=str(out/'goal-materials-stale-rejected.png'),full_page=True)
            (out/'goal-materials-state.json').write_text(json.dumps({'before':before['revision_id'],'committed':revision,'links':links,'stale_status':rejected.value.status,'concurrent_revision':state['revision'],'errors':errors},ensure_ascii=False,indent=2))
        finally:
            (out/'goal-materials-requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2));browser.close();server.stop()


@pytest.mark.parametrize('action,label,field,value,count',[
    ('split','拆分','拆分位置与方式','在第二个要点后拆分：前页保留问题，后页讲行动与验证。',1),
    ('merge','合并','合并后的页面标题','问题、行动与验证',2),
])
def test_studio_split_merge_fields_preview_cancel_refresh_and_dispatch(tmp_path,action,label,field,value,count):
    from playwright.sync_api import sync_playwright,expect
    from deck_master import tasks
    project=tmp_path/action;create_gallery_sample(project,page_count=24,readonly=False);store=Store(project)
    authorize_content_edits(project)
    before=store.load_document();server=WorkbenchServer(project)
    out=Path(os.environ.get('STUDIO_CONTENT_EVIDENCE',str(tmp_path/'evidence')));out.mkdir(parents=True,exist_ok=True);requests=[];errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append({'url':r.url.split('/api/')[-1],'body':r.post_data}) if '/api/' in r.url and r.method=='POST' else None)
        try:
            page.goto(server.start()+'studio/');page.get_by_role('button',name='内容与页序',exact=True).click()
            nav=page.get_by_role('navigation',name='内容工作区');nav.get_by_role('button',name='逐页稿',exact=True).click()
            for index in range(count):page.locator('.content-order-row').nth(index).get_by_role('checkbox').check()
            mode=page.get_by_role('group',name='选页调整方式').get_by_role('button',name=label,exact=True);mode.click();expect(mode).to_have_attribute('aria-pressed','true')
            preview=page.get_by_role('button',name='预览'+label+'选页',exact=True);field_input=page.get_by_label(field,exact=True)
            preview.click();expect(field_input).to_have_attribute('aria-invalid','true');assert not any(r['url']=='content/plan' for r in requests)
            field_input.fill(value);page.get_by_label('选页调整要求',exact=True).fill('完整保留业务事实、数字与来源，未选页保持。')
            preview.click();submit=page.get_by_role('button',name='确认并交接内容调整',exact=True);expect(submit).to_be_enabled()
            expect(page.locator('.content-request-review')).to_contain_text(field+'：'+value)
            expect(page.locator('.content-request-review')).to_contain_text('制作工具返回并通过校验后才产生新稿')
            posted=json.loads(next(r['body'] for r in reversed(requests) if r['url']=='content/plan'))['input']
            assert posted['action']==action and posted['instruction']==field+'：'+value+'\n完整保留业务事实、数字与来源，未选页保持。'
            assert posted['targets']==[{'page_id':p['page_id'],'page_ref':p['page']} for p in before['pages'][:count]]
            page.get_by_role('button',name='取消本次核对，保留编辑',exact=True).click();expect(submit).to_be_disabled();expect(page.locator('.content-request-review')).to_have_count(0)
            assert store.load_document()==before;expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            page.reload();nav.get_by_role('button',name='逐页稿',exact=True).click()
            expect(mode).to_have_attribute('aria-pressed','true');expect(field_input).to_have_value(value)
            for index in range(count):expect(page.locator('.content-order-row').nth(index).get_by_role('checkbox')).to_be_checked()
            preview.click();expect(submit).to_be_enabled()
            field_input.fill(value+'（后写）');expect(submit).to_be_disabled();expect(page.locator('.content-request-review')).to_have_count(0)
            field_input.fill(value);preview.click();expect(submit).to_be_enabled()
            for width,height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.locator('.studio-content-adjust').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(out/f'{action}-fields-{width}.png'))
            with page.expect_response(lambda r:r.url.endswith('/api/content/commit') and r.request.method=='POST') as receipt:submit.click()
            assert receipt.value.ok;result=receipt.value.json()['operation_result'];assert result['task_ids']
            task=tasks._lookup_task(store.load_document(),result['task_ids'][0],store)
            assert task['scope_pages']==[p['page_id'] for p in before['pages'][:count]]
            assert posted['instruction'] in task['instruction']
            frozen=store.read_object_json(task['content_operation_ref']);assert frozen['input']==posted
            after=store.load_document();assert after['pages']==before['pages'] and after['content_plan']==before['content_plan']
            expect(page).to_have_url(re.compile('surface=runs'));expect(page).to_have_url(re.compile('task='+task['task_id']))
            page.screenshot(path=str(out/f'{action}-task-dispatched.png'),full_page=True)
            assert errors==[]
            (out/f'{action}-state.json').write_text(json.dumps({'before':before['revision_id'],'after':after['revision_id'],'frozen_input':frozen['input'],'task_id':task['task_id'],'pages_unchanged':after['pages']==before['pages'],'errors':errors},ensure_ascii=False,indent=2))
        finally:
            (out/f'{action}-requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2));browser.close();server.stop()


@pytest.mark.parametrize('old_poll_error', [False, True])
def test_old_poll_cannot_invalidate_newly_read_content_plan(tmp_path, old_poll_error):
    """A delayed poll cannot roll back a newer route's basis or show stale errors."""
    from playwright.sync_api import sync_playwright, expect
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    authorize_content_edits(project)
    store = Store(project)
    server = WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        held, errors = [], []
        block_following = [False]
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(server.start())
            page.get_by_role('button', name='内容与页序', exact=True).click()
            page.get_by_role('button', name='逐页稿', exact=True).click()
            page.locator('.content-order-row').first.get_by_role('button',name='第 1 页操作',exact=True).click()
            page.locator('.content-order-row').first.get_by_role('button', name=re.compile('^向后移动 ')).click()
            page.get_by_role('button', name='预览页序变更', exact=True).click()
            commit = page.get_by_role('button', name='确认内容变更', exact=True)
            expect(commit).to_be_enabled()
            old_revision = store.current_revision_id()

            def hold_poll(route):
                if not held:
                    response = route.fetch()
                    assert response.json()['revision_id'] == old_revision
                    held.append((route, response))
                    page.evaluate('() => { window.__heldContentPoll = true; }')
                elif block_following[0]:
                    # Do not let a subsequent fresh poll conceal the stale one.
                    held.append((route, None))
                else:
                    route.continue_()

            page.route('**/api/view/summary?personal=1', hold_poll)
            page.evaluate('() => window.dispatchEvent(new Event("focus"))')
            page.wait_for_function('() => window.__heldContentPoll === true')
            with page.expect_response(lambda response: response.url.endswith('/api/content/commit')) as receipt:
                commit.click()
            current = receipt.value.json()['operation_result']['revision_id']
            assert current != old_revision
            expect(page).to_have_url(re.compile('revision=' + current))
            expect(page.locator('#content-area-pages')).to_be_visible()
            page.locator('.content-order-row').first.get_by_role('checkbox').check()
            page.get_by_label('选页调整要求', exact=True).fill('保留事实，调整这一页表达')
            block_following[0] = True
            if old_poll_error:
                held[0][0].fulfill(status=503, content_type='application/json', body=json.dumps({'error': {'message': 'old poll failure'}}))
            else:
                held[0][0].fulfill(response=held[0][1])
            page.evaluate('() => new Promise(resolve => requestAnimationFrame(resolve))')
            page.get_by_role('button', name='预览选页改写', exact=True).click()
            expect(page.get_by_role('button', name='确认并交接内容调整', exact=True)).to_be_enabled()
            expect(page.locator('.runtime-sync-row')).to_be_hidden()
            assert store.current_revision_id() == current and errors == []
        finally:
            page.unroute_all(behavior='ignoreErrors')
            browser.close()
            server.stop()


def test_content_selection_survives_filter_and_select_all_is_visible_only(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    project=tmp_path/'selection';create_gallery_sample(project,page_count=30,readonly=False)
    authorize_content_edits(project)
    server=WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(server.start()+'studio/');page.get_by_role('button',name='内容与页序',exact=True).click()
            nav=page.get_by_role('navigation',name='内容工作区')
            expect(nav.locator(':scope > button')).to_have_count(3)
            expect(page.locator('.studio-content-adjust')).to_be_hidden()
            rows=page.locator('.content-order-row')
            identities=rows.evaluate_all('(rows)=>rows.map(r=>r.dataset.pageId)')
            rows.nth(1).get_by_role('checkbox').check();rows.nth(27).get_by_role('checkbox').check()
            expect(page.locator('.studio-content-adjust')).to_be_visible()
            search=page.get_by_role('searchbox',name='搜索逐页稿')
            search.fill('28 ')
            expect(rows).to_have_count(1)
            expect(page.locator('.content-list-toolbar')).to_contain_text('已选 2 页 · 筛选外 1 页')
            search.fill('29 ')
            page.get_by_role('checkbox',name='选定当前筛选结果',exact=True).check()
            expect(page.locator('.content-list-toolbar')).to_contain_text('已选 3 页 · 筛选外 2 页')
            search.fill('')
            actual=rows.filter(has=page.locator('input:checked')).evaluate_all('(rows)=>rows.map(r=>r.dataset.pageId)')
            assert actual==[identities[1],identities[27],identities[28]]
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            page.reload()
            expect(rows).to_have_count(30)
            actual=rows.filter(has=page.locator('input:checked')).evaluate_all('(rows)=>rows.map(r=>r.dataset.pageId)')
            assert actual==[identities[1],identities[27],identities[28]]
            rows.first.locator('.order-handle').focus();page.keyboard.press('Alt+ArrowDown')
            assert rows.nth(1).get_attribute('data-page-id')==identities[0]
            expect(rows.nth(1).locator('.order-handle')).to_be_focused()
            assert not errors
        finally:browser.close();server.stop()
