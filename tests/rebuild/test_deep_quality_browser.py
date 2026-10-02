"""Q01/Q06–Q10: real server + Chromium, only network delay/failure injected."""
import copy
import shutil
import uuid
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import icons
from deck_master.models import bump_revision
from deck_master.web import WorkbenchServer
from test_icon_quality import icon_store, input_for, confirm, dispatch, start, accept

pytestmark=pytest.mark.browser


@pytest.fixture
def workbench(icon_store):
    server=WorkbenchServer(icon_store.project_root);url=server.start()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('chromium-browser'),args=['--no-sandbox'])
        ctx=browser.new_context(viewport={'width':1440,'height':900});page=ctx.new_page();errors=[]
        ctx.on('page',lambda p:p.on('pageerror',lambda e:errors.append(str(e))))
        page.on('pageerror',lambda e:errors.append(str(e)))
        info=page.request.get(url.rstrip('/')+'/api/project').json()
        def goto(surface='page', revision=None):
            link=url+'#'+urlencode({'project':info['project_identity'],'surface':surface,'page':'p01','layer':'svg','revision':revision or icon_store.current_revision_id()})
            page.goto(link)
            return link
        try:yield page,ctx,icon_store,url,goto,errors
        finally:ctx.close();browser.close();server.stop()
        assert errors==[]


@pytest.mark.parametrize('width,height',[(1280,800),(1440,900),(390,844)])
def test_cloned_window_offline_drafts_both_survive(workbench,width,height):
    a,ctx,store,url,goto,_=workbench;a.set_viewport_size({'width':width,'height':height});link=goto()
    field=a.get_by_role('textbox',name='个人草稿',exact=True);expect(field).to_be_editable()
    field.fill('共同初稿');a.get_by_role('button',name='保存个人草稿',exact=True).click()
    expect(a.locator('.draft-state')).to_contain_text('已保存到项目')
    with a.expect_popup() as popup:a.evaluate('(url)=>window.open(url,"_blank")',link)
    b=popup.value;expect(b.get_by_role('textbox',name='个人草稿',exact=True)).to_have_value('共同初稿')
    ctx.route('**/api/drafts/save',lambda r:r.abort('failed'))
    field.fill('窗口 A 独有的修改');b.get_by_role('textbox',name='个人草稿',exact=True).fill('窗口 B 独有的修改')
    expect(a.locator('.draft-state')).to_contain_text('保存结果待核实');expect(b.locator('.draft-state')).to_contain_text('保存结果待核实')
    # Refresh must recover this window's own buffer without claiming an ACK.
    a.reload();expect(a.get_by_role('textbox',name='个人草稿',exact=True)).to_have_value('窗口 A 独有的修改')
    a.close(run_before_unload=True);b.close(run_before_unload=True)
    c=ctx.new_page();c.goto(link);expect(c.get_by_role('textbox',name='个人草稿',exact=True)).to_be_editable()
    texts=c.evaluate('''()=>Object.entries(localStorage).filter(([k])=>k.includes(':draft:')).map(([k,v])=>JSON.parse(v).draft?.content?.text)''')
    assert '窗口 A 独有的修改' in texts and '窗口 B 独有的修改' in texts
    choices=c.get_by_label('恢复本机保留的草稿副本')
    expect(choices).to_be_visible()
    assert '窗口 A 独有的修改' in choices.inner_text()
    assert '窗口 B 独有的修改' in choices.inner_text()


def test_unselected_icon_page_cannot_be_dispatched_by_late_plan(workbench):
    page,ctx,store,url,goto,_=workbench
    confirm(store,input_for(store));before=store.load_document()['tasks'];goto()
    box=page.get_by_label('选入图标页 p01');box.check();held=[]
    page.route('**/api/icons/plan',lambda route:held.append(route))
    page.get_by_role('button',name='预览选中页图标试作',exact=True).click()
    for _ in range(50):
        if held:break
        page.wait_for_timeout(20)
    assert held
    box.uncheck()
    with page.expect_response('**/api/icons/plan'):held[0].fulfill(response=held[0].fetch())
    page.wait_for_timeout(100)
    expect(page.get_by_role('button',name='确认计划并交接图标修复',exact=True)).to_have_count(0)
    assert store.load_document()['tasks']==before
    page.unroute('**/api/icons/plan');box.check()
    page.get_by_role('button',name='预览选中页图标试作',exact=True).click()
    button=page.get_by_role('button',name='确认计划并交接图标修复',exact=True);button.wait_for();button.focus();page.keyboard.press('Enter')
    page.get_by_role('heading',name='当前任务',exact=True).wait_for()
    assert len(store.load_document()['tasks'])==len(before)+1


def test_handoff_navigation_opens_current_task(workbench):
    page,ctx,store,url,goto,_=workbench
    task=dispatch(store,confirm(store,input_for(store)))[0];goto('runs');bad=[]
    page.on('response',lambda r:bad.append(r.url) if 'revision=null' in r.url else None)
    page.get_by_role('button',name='查看任务与调用记录',exact=True).first.click()
    expect(page.locator('.run-detail')).to_be_visible()
    assert task['task_id'] in page.url and 'revision=null' not in page.url and not bad
    # An already copied old link uses the same current-version semantics.
    page.goto(page.url.replace('revision='+store.current_revision_id(),'revision=null') if 'revision=' in page.url else page.url+'&revision=null')
    expect(page.locator('.run-detail')).to_be_visible()
    assert not bad


def test_historical_candidate_list_never_acquires_future_candidate(workbench):
    page,ctx,store,url,goto,_=workbench;old=store.current_revision_id()
    rec=confirm(store,input_for(store,method='standard'));task=dispatch(store,rec)[0];start(store,task)
    accept(store,task,icons.draft(store.project_root,recipe_id=rec['recipe_id'],page_id='p01')['svg'].encode())
    goto('runs',old)
    expect(page.locator('.history-banner')).to_contain_text('历史版本')
    expect(page.get_by_text('还没有候选。单页原图或 SVG 中可保存试作要求；正在运行或失败的任务仍在下方交接面板。',exact=True)).to_be_visible()
    expect(page.locator('.candidate-batch-row')).to_have_count(0)
    goto('runs');expect(page.locator('.candidate-batch-row')).to_have_count(1)


def test_annotation_plan_conflict_keeps_draft_and_opens_recovery(workbench):
    page,ctx,store,url,goto,_=workbench;goto()
    page.get_by_role('button',name='整页意见',exact=True).click()
    text='修正图标间距，保持其它对象。';page.get_by_role('textbox',name='个人草稿',exact=True).fill(text)
    page.get_by_role('button',name='保存意见',exact=True).click();page.get_by_label('选入意见 1').check()
    doc=store.load_document();new=copy.deepcopy(doc);art=store.read_object_json(new['pages'][0]['svg']);art['limitations']=['concurrent edit']
    new['pages'][0]['svg']=store.put_json_object(art)
    new=bump_revision(new,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'synthetic concurrent writer','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=new,operation_id=new['change']['operation_id'])
    with page.expect_response('**/api/changes/plan') as response:page.get_by_role('button',name='加入修改计划',exact=True).click()
    assert response.value.status==409
    expect(page.get_by_role('dialog')).to_be_visible()
    expect(page.get_by_label('未提交的本机草稿')).to_have_value(text)
    expect(page.get_by_role('dialog').get_by_role('button',name='查看新的当前版本',exact=True)).to_be_enabled()


def test_clear_plan_network_failure_allows_retry(workbench):
    page,ctx,store,url,goto,_=workbench;goto('runs')
    page.get_by_text('清理本机个人状态（草稿与阅读设置）',exact=True).click()
    page.route('**/api/ui-state/plan-clear',lambda r:r.abort('failed'))
    btn=page.get_by_role('button',name='生成清理计划',exact=True);btn.click()
    expect(page.locator('.personal-clear')).to_contain_text('本机服务暂时无法连接')
    expect(btn).to_be_enabled();expect(page.get_by_role('button',name='确认清理并保留备份',exact=True)).to_be_disabled()
    page.unroute('**/api/ui-state/plan-clear')
    with page.expect_response('**/api/ui-state/plan-clear') as response:btn.click()
    assert response.value.status==200
    expect(page.locator('.personal-clear')).to_contain_text('将清理')
