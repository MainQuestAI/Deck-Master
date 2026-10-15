"""PR105 recovery uses real journals and candidate adoption, synthetic results."""
import uuid

import pytest
from deck_master import changes, result_reading, tasks, ui_journal
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_content_candidates import content_intent, start_task, page_envelope, accept
from test_action_targets_browser import _prepare_browser_project

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('single', [False, True])
@pytest.mark.parametrize('state', ['saved', 'dirty', 'unknown', 'late'])
def test_candidate_recovery_survives_modal_and_allows_adoption(tmp_path, single, state):
    from playwright.sync_api import sync_playwright, expect
    path = tmp_path/'project'
    create_sample(path, page_count=2, readonly=False)
    _prepare_browser_project(path)
    store = Store(path)
    plan = changes.plan(path, input=content_intent(store))
    dispatched = changes.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']
    task = tasks._lookup_task(store.load_document(), dispatched['task_ids'][0], store)
    start_task(path, task)
    cid = accept(path, task, page_envelope(store, task))['candidate_ids'][0]
    doc = store.load_document()
    for name in ['A', 'B']:
        ui_journal.save(path, draft={'schema_version':'ui_draft.v1','draft_id':'draft-'+name,
            'project_id':doc['project_id'],'project_identity':result_reading.get(path)['project_identity'],
            'target':{'scope':'project','page_id':None,'layer':'notes'},'base_revision':doc['revision_id'],
            'base_ref':None,'pending':None,'content':{'text':name}})
    server = WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            page.get_by_role('button',name='待决定',exact=True).click()
            if single:
                page.locator(f'[data-candidate-id="{cid}"]').get_by_role('button',name='比较这个候选',exact=True).click()
            page.get_by_role('button',name='个人记录与操作恢复',exact=True).click()
            page.get_by_label('恢复项目中的个人草稿',exact=True).select_option('draft-A')
            if page.get_by_role('button',name='打开所选草稿',exact=True).count():
                page.get_by_role('button',name='打开所选草稿',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('A')
            held = []
            if state == 'saved':
                # A failed local archive must leave A usable; then retry normally.
                page.evaluate('() => { window.originalSetItem=Storage.prototype.setItem; Storage.prototype.setItem=function(k,v){if(k.includes(":copy:backup-"))throw new Error("injected storage failure");return window.originalSetItem.call(this,k,v);}; }')
                page.get_by_label('恢复项目中的个人草稿',exact=True).select_option('draft-B')
                if page.get_by_role('button',name='打开所选草稿',exact=True).count():
                    page.get_by_role('button',name='打开所选草稿',exact=True).click()
                expect(page.locator('.storage-error, .field-error').filter(has_text='本机副本未保存')).to_be_visible()
                expect(page.get_by_label('个人草稿',exact=True)).to_have_value('A')
                page.evaluate('() => {Storage.prototype.setItem=window.originalSetItem;}')
            if state != 'saved':
                page.route('**/api/drafts/save', (lambda route: held.append((route, route.fetch()))) if state == 'late' else (lambda route: route.abort()))
                page.get_by_label('个人草稿',exact=True).fill('A changed')
                if state == 'late':
                    expect(page.locator('.draft-state')).to_contain_text('正在保存')
                if state == 'unknown':
                    expect(page.locator('.draft-state')).to_contain_text('待核实')
            page.get_by_label('恢复项目中的个人草稿',exact=True).select_option('draft-B')
            if page.get_by_role('button',name='打开所选草稿',exact=True).count():
                if state != 'saved':
                    page.get_by_role('button',name='取消恢复',exact=True).click()
                    expect(page.get_by_label('个人草稿',exact=True)).to_have_value('A changed')
                    page.get_by_label('恢复项目中的个人草稿',exact=True).select_option('draft-B')
                page.get_by_role('button',name='打开所选草稿',exact=True).click()
            if state != 'saved':
                if state == 'late':
                    assert held
                    route, response = held.pop()
                    route.fulfill(response=response)
                page.unroute('**/api/drafts/save')
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('B')
            page.get_by_label('个人草稿',exact=True).fill('B edited')
            page.get_by_role('button',name='保存个人草稿',exact=True).click()
            expect(page.locator('.draft-state')).to_contain_text('已保存')
            page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).click()
            page.get_by_role('button',name='个人记录与操作恢复',exact=True).click()
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('B edited')
            page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).click()
            if single:
                page.get_by_role('button',name='预览采用这个候选',exact=True).click()
                page.get_by_role('button',name='采用这个候选',exact=True).click()
                expect(page.locator('.candidate-state')).to_contain_text('当前采用')
            else:
                page.locator(f'[data-candidate-id="{cid}"] input').check()
                page.get_by_role('button',name='预览所选候选的采用影响',exact=True).click()
                page.get_by_role('button',name='采用所选候选',exact=True).click()
                expect(page.locator('.candidate-batch')).to_contain_text('已整批采用')
            assert store.current_revision_id() != doc['revision_id']
            assert any(r['draft']['content']['text']=='B edited' for r in ui_journal.list_drafts(path)['records'])
            assert not errors
        finally:
            browser.close()
            server.stop()
