"""Real synthetic candidate records prove bulk selection and all-or-none planning."""
import uuid

import pytest

from deck_master import candidates, changes, service, tasks
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_content_candidates import content_intent, start_task, page_envelope, accept
from test_action_targets_browser import _prepare_browser_project

pytestmark=pytest.mark.browser


def test_bulk_candidates_groups_pagination_ambiguity_and_stale_plan(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    path=tmp_path/'project';create_sample(path,page_count=33,readonly=False);store=Store(path)
    _prepare_browser_project(path, max_candidate_count=34)
    doc=store.load_document();intent=content_intent(store)
    intent['targets']=[{'page_id':p['page_id'],'page_ref':p['page'],'layer':'content','artifact_ref':p['page']} for p in doc['pages']]
    planned=changes.plan(path,input=intent)
    dispatched=changes.commit(path,plan_id=planned['plan_id'],base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    ids={}
    for task_id in dispatched['task_ids']:
        task=tasks._lookup_task(store.load_document(),task_id,store);start_task(path,task)
        ids[task['scope_pages'][0]]=accept(path,task,page_envelope(store,task))['candidate_ids'][0]
    duplicate_plan=changes.plan(path,input=content_intent(store,'p01',instruction='第二个候选，必须人工比较'))
    duplicate_result=changes.commit(path,plan_id=duplicate_plan['plan_id'],base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    duplicate_task=tasks._lookup_task(store.load_document(),duplicate_result['task_ids'][0],store)
    start_task(path,duplicate_task);duplicate=accept(path,duplicate_task,page_envelope(store,duplicate_task,' Alternative'))['candidate_ids'][0]
    revision=store.current_revision_id()
    candidates.decide(path,input={'schema_version':'candidate_decision.v1','project_id':doc['project_id'],'base_revision':revision,'candidate_id':ids['p02'],'decision':'keep_current','expected_decision_ref':None},base_revision=revision,operation_id=str(uuid.uuid4()))
    plan=candidates.plan(path,input={'schema_version':'candidate_selection.v1','project_id':doc['project_id'],'base_revision':store.current_revision_id(),'candidate_ids':[ids['p03']]})['plan']
    candidates.adopt(path,input=plan,base_revision=plan['base_revision'],operation_id=str(uuid.uuid4()))
    rows=candidates.listing(path)['candidates'];assert sum(row['selection_allowed'] for row in rows)==32
    assert next(row for row in rows if row['candidate']['candidate_id']==ids['p02'])['selection_blocked_reason']=='kept_current'
    server=WorkbenchServer(path);errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900});page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(server.start()+'studio/');page.get_by_role('button',name='任务与交付',exact=True).click();page.get_by_role('button',name='待决定',exact=True).click()
            root=page.locator('.candidate-batch');expect(root.locator('.candidate-card')).to_have_count(30)
            expect(root.locator(f'[data-candidate-id="{ids["p02"]}"] input')).to_be_disabled()
            expect(root.locator(f'[data-candidate-id="{ids["p03"]}"] input')).to_be_disabled()
            root.get_by_role('button',name='选本页候选',exact=True).click()
            expect(root.locator('.candidate-card input:checked')).to_have_count(27)
            expect(root.locator('.candidate-selection-message')).to_contain_text('1 页有多个')
            root.get_by_role('button',name='下一页候选',exact=True).click()
            root.get_by_role('button',name='选本页候选',exact=True).click()
            expect(root).to_contain_text('已选 30 个')
            root.get_by_role('button',name='上一页候选',exact=True).click()
            expect(root.locator('.candidate-card input:checked')).to_have_count(27)
            root.get_by_role('button',name='清除选择',exact=True).click()
            root.get_by_role('combobox',name='按修改组查看候选',exact=True).select_option(dispatched['change_id'])
            root.get_by_role('button',name='选本组候选',exact=True).click();expect(root).to_contain_text('已选 30 个')
            root.locator(f'[data-candidate-id="{ids["p01"]}"] input').check()
            root.get_by_role('button',name='选全部候选',exact=True).click();expect(root).to_contain_text('已选 31 个')
            root.get_by_role('combobox',name='按修改组查看候选',exact=True).select_option(duplicate_result['change_id'])
            expect(root.locator('.candidate-card')).to_have_count(1)
            expect(root.locator(f'[data-candidate-id="{duplicate}"] input')).not_to_be_checked()
            with page.expect_request('**/api/candidates/plan') as request:
                root.get_by_role('button',name='预览所选候选的采用影响',exact=True).click()
            sent=request.value.post_data_json['input']['candidate_ids']
            assert len(sent)==31 and ids['p01'] in sent and duplicate not in sent and ids['p02'] not in sent and ids['p03'] not in sent
            expect(root.get_by_role('button',name='采用所选候选',exact=True)).to_be_enabled()
            prior=store.read_current()
            service.inputs_update(path,patch={'reason':'concurrent input change','task_patch':{'audience':'新受众'}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
            current=store.read_current();assert current!=prior
            root.get_by_role('button',name='采用所选候选',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('本次未采用任何页')
            assert store.read_current()==current and errors==[]
        finally:
            browser.close();server.stop()
