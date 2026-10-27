"""New-request Workbench trial/budget/Host/explicit adoption; L1, zero calls."""
import shutil
import re
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import collaboration, eligibility, tasks
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from rc3_fixtures import evidence_for, settle_fidelity_review
from candidate_fixtures import start, accept

pytestmark = pytest.mark.browser


def new_request(tmp_path):
    path = tmp_path / 'new-edit'; create_sample(path, page_count=2, readonly=False)
    store = Store(path); doc = store.load_document()
    scope = {**doc['collaboration']['request']['scope'], 'page_ids':['p01','p02']}
    collaboration.start_request(path, input={'intent':'edit', 'scope':scope,
        'replace_request_id':doc['collaboration']['request']['request_id'],
        'instruction_evidence':evidence_for(path, text='L1 new edit request: trial and explicitly compare selected SVG; zero image calls.',
                                          locator='L1:new-edit-request')},
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    settle_fidelity_review(path, page_ids=['p01','p02'], execution_ref='L1-new-edit-review', scenario='Neutral synthetic manuscript')
    doc=store.load_document()
    current=[store.read_object_json(ref) for ref in doc['collaboration']['authorizations']
             if store.read_object_json(ref)['request_id']==doc['collaboration']['request']['request_id']]
    assert current == []
    assert eligibility.covering_authorization_ref(store,doc,'candidate.adopt',{'page_ids':['p01'],'layers':['svg']}) is None
    return path, store


def prepare_candidate(page, store):
    page.get_by_role('checkbox',name='选择第 01 页',exact=True).check()
    page.get_by_role('button',name='SVG 重建',exact=True).click()
    page.get_by_role('textbox',name='所选页的制作要求',exact=True).fill('L1 tighten this one SVG only; keep the other page and original image.')
    page.get_by_role('button',name='预览所选页试作',exact=True).click()
    page.get_by_role('button',name='查看这次修改的制作预算',exact=True).click()
    dialog=page.get_by_role('dialog',name='记录制作预算')
    expect(dialog).to_contain_text('比较候选上限 1 个')
    dialog.get_by_label('本次明确要求（必填）').fill('L1 authorize only this single SVG trial, no image call and candidate comparison before adoption.')
    dialog.get_by_role('button',name='确认记录制作预算',exact=True).click()
    expect(dialog).to_contain_text('请求已记录')
    trial_auth=store.read_object_json(store.load_document()['collaboration']['authorizations'][-1])
    assert trial_auth['adoption_policy']=='candidate_only' and trial_auth['max_external_calls']==0
    assert trial_auth['max_candidate_count']==1 and 'candidate.adopt' not in trial_auth['actions']
    dialog.get_by_role('button',name='读取当前版本并重新预览修改',exact=True).click()
    expect(page.locator('#main')).not_to_have_attribute('aria-busy','true')
    page.get_by_role('checkbox',name='选择第 01 页',exact=True).check()
    page.get_by_role('button',name='预览所选页试作',exact=True).click()
    with page.expect_response('**/api/changes/commit') as committed:
        page.get_by_role('button',name='保存并交接所选试作',exact=True).click()
    result=committed.value.json()['operation_result']
    task=tasks._lookup_task(store.load_document(),result['task_ids'][0],store)
    assert task['collaboration_binding']['adoption_policy']=='candidate_only'
    before=store.load_document()['pages']
    start(store,task); received=accept(store,task)
    assert received['status']=='candidate_ready' and store.load_document()['pages']==before
    return received['candidate_ids'][0]


@pytest.mark.parametrize('batch,width',[(False,1440),(True,390)])
def test_browser_new_request_trial_then_zero_call_explicit_adoption(tmp_path,batch,width):
    path,store=new_request(tmp_path); server=WorkbenchServer(path); errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':900})
        page.set_default_timeout(10000)
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            url=server.start(); page.goto(url)
            cid=prepare_candidate(page,store)
            before=store.load_document(); count=len(before['collaboration']['authorizations'])
            route=dict(parse_qsl(urlsplit(page.url).fragment))
            route.update(revision=before['revision_id'])
            if batch:
                route.update(surface='runs',area='decisions')
                page.goto(url+'#'+urlencode(route))
                root=page.locator('.candidate-batch')
                root.get_by_role('button',name='选全部候选',exact=True).click()
                root.get_by_role('button',name='预览所选候选的采用影响',exact=True).click()
                action=root.get_by_role('button',name='采用所选候选',exact=True)
            else:
                route.update(surface='page',page='p01',layer='svg',candidate=cid)
                page.goto(url+'#'+urlencode(route))
                root=page.locator('.candidate-desk')
                root.get_by_role('button',name='预览采用这个候选',exact=True).click()
                action=root.get_by_role('button',name='采用这个候选',exact=True)
            action.click()
            dialog=page.get_by_role('dialog',name='授权采用所选候选')
            expect(dialog).to_contain_text('图像调用上限 0，新增试作上限 0')
            page.screenshot(path=str(tmp_path/'adoption-confirmation.png'),full_page=True)
            assert store.load_document()==before
            dialog.get_by_role('button',name='关闭',exact=True).click()
            assert store.load_document()==before
            action.click(); dialog=page.get_by_role('dialog',name='授权采用所选候选')
            with page.expect_response('**/api/candidates/adopt') as adopted:
                dialog.get_by_role('button',name='确认授权采用所选候选',exact=True).click()
            assert adopted.value.status==200,adopted.value.json()
            after=store.load_document()
            assert len(after['collaboration']['authorizations'])==count+1
            grant=store.read_object_json(after['collaboration']['authorizations'][-1])
            assert grant['actions']==['candidate.adopt']
            assert grant['scope']['page_ids']==['p01'] and grant['scope']['layers']==['svg']
            assert grant['max_external_calls']==grant['max_candidate_count']==0
            assert not grant['scope']['allow_page_membership_change'] and not grant['scope']['allow_page_order_change']
            assert after['pages'][0]['svg']!=before['pages'][0]['svg']
            assert after['pages'][0]['blueprint']==before['pages'][0]['blueprint']
            assert after['pages'][1]==before['pages'][1]
            assert eligibility.allowance_usage(store,after)['totals']==eligibility.allowance_usage(store,before)['totals']
            expect(page).to_have_url(re.compile('revision='+after['revision_id']))
            page.reload()
            expect(page.locator('.history-banner')).to_have_count(0)
            if batch:
                expect(page.locator(f'[data-candidate-id="{cid}"] input')).to_be_disabled()
            else:
                expect(page.locator('.candidate-state')).to_contain_text('当前采用')
            assert errors==[]
            page.screenshot(path=str(tmp_path/'adoption-completed.png'),full_page=True)
        finally:
            browser.close(); server.stop()


@pytest.mark.parametrize('scenario',['existing','grant_lost','adoption_lost','grant_version','revoke'])
def test_adoption_authority_races_and_uncertain_responses_keep_original_operations(tmp_path,scenario):
    from test_rc3_candidate_adoption_handoff import trial, preview, grant_adoption
    path,store,cid=trial(tmp_path)
    grant=grant_adoption(path,store,preview(path,store,cid)['adoption_authority']['scope']) if scenario in ('existing','revoke') else None
    server=WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
        page=browser.new_page(); page.set_default_timeout(10000)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            url=server.start();page.goto(url)
            page.wait_for_function("() => location.hash.includes('project=')")
            route=dict(parse_qsl(urlsplit(page.url).fragment))
            route.update(surface='page',page='p01',layer='svg',candidate=cid,revision=store.current_revision_id())
            page.goto(url+'#'+urlencode(route))
            root=page.locator('.candidate-desk')
            root.get_by_role('button',name='预览采用这个候选',exact=True).click()
            before=store.load_document();count=len(before['collaboration']['authorizations'])
            calls=[]
            page.on('request',lambda request:calls.append(request.post_data_json) if request.url.endswith('/api/candidates/adopt') else None)
            if scenario=='revoke':
                def revoke_then_continue(route):
                    collaboration.revoke_authorization(path,authorization_id=grant['authorization_id'],reason='L1 race: revoke after preflight',
                        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
                    route.continue_()
                page.route('**/api/candidates/adopt',revoke_then_continue,times=1)
            if scenario=='adoption_lost':
                def lose_adoption(route):
                    response=route.fetch()
                    assert response.status==200,response.text()
                    route.abort()
                page.route('**/api/candidates/adopt',lose_adoption,times=1)
            if scenario=='grant_lost':
                def lose_grant(route):
                    response=route.fetch()
                    assert response.status==200,response.text()
                    route.abort()
                page.route('**/collaboration/authorizations',lose_grant,times=1)
            root.get_by_role('button',name='采用这个候选',exact=True).click()
            if scenario not in ('existing','revoke'):
                dialog=page.get_by_role('dialog',name='授权采用所选候选')
                if scenario=='grant_version':
                    # A separate zero-call grant advances current before confirmation.
                    grant_adoption(path,store,preview(path,store,cid)['adoption_authority']['scope'])
                dialog.get_by_role('button',name='确认授权采用所选候选',exact=True).click()
                if scenario=='grant_lost':
                    retry=dialog.get_by_role('button',name='核实并重试原请求',exact=True)
                    expect(retry).to_be_enabled()
                    assert store.load_document()['pages']==before['pages'] and calls==[]
                    assert len(store.load_document()['collaboration']['authorizations'])==count+1
                    retry.click()
                if scenario=='grant_version':
                    expect(dialog).to_contain_text('当前稿件、可读报告和本次输入均保留')
                    assert calls==[] and store.load_document()['pages']==before['pages']
                    assert len(store.load_document()['collaboration']['authorizations'])==count+1
                    return
            if scenario=='revoke':
                expect(page.get_by_role('dialog')).to_contain_text('本次未采用任何页')
                assert store.load_document()['pages']==before['pages']
                assert len(store.load_document()['collaboration']['authorizations'])==count
                assert len(calls)==1
            else:
                if scenario=='adoption_lost':
                    expect(page.locator('.business-pending')).to_contain_text('尚未确认保存结果')
                    page.get_by_role('button',name='核实保存结果',exact=True).click()
                    expect(page.locator('.business-pending')).to_be_hidden()
                else:
                    expect(root).to_contain_text('已采用')
                assert store.load_document()['pages'][0]['svg']!=before['pages'][0]['svg']
                assert store.load_document()['pages'][1]==before['pages'][1]
                assert len(store.load_document()['collaboration']['authorizations'])==count+(scenario!='existing')
                assert len(calls)==1
            assert errors==[]
        finally:
            browser.close();server.stop()
