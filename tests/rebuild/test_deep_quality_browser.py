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
    a.get_by_text('私人笔记（不进入意见与制作）',exact=True).click()
    field=a.get_by_role('textbox',name='个人草稿',exact=True);expect(field).to_be_editable()
    field.fill('共同初稿');a.get_by_role('button',name='保存个人草稿',exact=True).click()
    expect(a.locator('.draft-state')).to_contain_text('已保存到项目')
    with a.expect_popup() as popup:a.evaluate('(url)=>window.open(url,"_blank")',link)
    b=popup.value;b.get_by_text('私人笔记（不进入意见与制作）',exact=True).click()
    expect(b.get_by_role('textbox',name='个人草稿',exact=True)).to_have_value('共同初稿')
    ctx.route('**/api/drafts/save',lambda r:r.abort('failed'))
    field.fill('窗口 A 独有的修改');b.get_by_role('textbox',name='个人草稿',exact=True).fill('窗口 B 独有的修改')
    expect(a.locator('.draft-state')).to_contain_text('保存结果待核实');expect(b.locator('.draft-state')).to_contain_text('保存结果待核实')
    # Refresh must recover this window's own buffer without claiming an ACK.
    a.reload();a.get_by_text('私人笔记（不进入意见与制作）',exact=True).click()
    expect(a.get_by_role('textbox',name='个人草稿',exact=True)).to_have_value('窗口 A 独有的修改')
    a.close(run_before_unload=True);b.close(run_before_unload=True)
    c=ctx.new_page();c.goto(link);c.get_by_text('私人笔记（不进入意见与制作）',exact=True).click()
    expect(c.get_by_role('textbox',name='个人草稿',exact=True)).to_be_editable()
    texts=c.evaluate('''()=>Object.entries(localStorage).filter(([k])=>k.includes(':draft:')).map(([k,v])=>JSON.parse(v).draft?.content?.text)''')
    assert '窗口 A 独有的修改' in texts and '窗口 B 独有的修改' in texts
    c.get_by_text('恢复、下载与版本详情',exact=True).click()
    choices=c.get_by_label('恢复本机保留的草稿副本')
    expect(choices).to_be_visible()
    assert '窗口 A 独有的修改' in choices.inner_text()
    assert '窗口 B 独有的修改' in choices.inner_text()


def test_old_revision_draft_never_locks_a_new_opinion(workbench):
    page,ctx,store,url,goto,_=workbench
    goto()
    body=page.get_by_role('textbox',name='意见正文',exact=True)
    body.fill('第一条意见的文字')
    page.get_by_role('button',name='整页意见',exact=True).click()
    page.get_by_role('button',name='保存意见',exact=True).click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    # Saving the opinion advanced the revision. Returning to the current one must
    # not adopt the older draft (which would bind this editor to a stale basis and
    # refuse the next save); the older text stays recoverable and is named on screen.
    page.goto(goto())
    fresh=page.get_by_role('textbox',name='意见正文',exact=True)
    expect(fresh).to_have_value('')
    expect(page.locator('.annotation-notice')).to_contain_text('旧版本草稿可从下方恢复')
    page.get_by_role('button',name='整页意见',exact=True).click()
    fresh.fill('第二条意见的文字')
    # A stale basis would keep this disabled no matter what the user types.
    expect(page.get_by_role('button',name='保存意见',exact=True)).to_be_enabled()
    page.get_by_role('button',name='保存意见',exact=True).click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    # Both opinions are independent records of this project, and both drafts kept.
    bodies=[note['annotation']['body'] for note in page.request.get(url.rstrip('/')+'/api/annotations').json()['annotations']]
    assert bodies.count('第一条意见的文字')==1 and bodies.count('第二条意见的文字')==1
    # The older text is recoverable, and copying it forward keeps the text only.
    page.goto(goto())
    page.get_by_text('恢复、下载与版本详情',exact=True).click()
    choices=page.get_by_label('恢复项目中的个人草稿')
    expect(choices).to_be_visible()
    assert '第一条意见的文字' in choices.inner_text()
    choices.select_option(label=[o for o in choices.locator('option').all_inner_texts() if '第一条意见的文字' in o][0])
    restored=page.get_by_role('textbox',name='意见正文',exact=True)
    expect(restored).to_have_value('第一条意见的文字')
    expect(page.locator('.annotation-notice')).to_contain_text('对当前版本写新意见')
    page.get_by_role('button',name='对当前版本写新意见',exact=True).click()
    expect(page.get_by_role('textbox',name='意见正文',exact=True)).to_have_value('第一条意见的文字')
    expect(page.locator('.annotation-notice')).to_be_hidden()
    records=page.request.get(url.rstrip('/')+'/api/annotations').json()['annotations']
    assert len(records)==2, 'copying text forward must not create or rewrite a record'


def test_private_note_stays_out_of_opinions_and_repeat_saves(workbench):
    page,ctx,store,url,goto,_=workbench;goto()
    page.get_by_text('私人笔记（不进入意见与制作）',exact=True).click()
    note=page.get_by_role('textbox',name='个人草稿',exact=True)
    note.fill('这是我自己的备忘，不是给制作的意见。')
    page.get_by_role('button',name='保存个人草稿',exact=True).click()
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    body=page.get_by_role('textbox',name='意见正文',exact=True)
    # The note never becomes the opinion body: the opinion form starts empty and
    # refuses to save until the user writes or explicitly copies something.
    expect(body).to_have_value('')
    page.get_by_role('button',name='整页意见',exact=True).click()
    expect(page.get_by_role('button',name='保存意见',exact=True)).to_be_disabled()
    assert page.request.get(url.rstrip('/')+'/api/annotations').json()['annotations']==[]
    page.get_by_role('button',name='从私人笔记复制',exact=True).click()
    expect(body).to_have_value('这是我自己的备忘，不是给制作的意见。')
    expect(note).to_have_value('这是我自己的备忘，不是给制作的意见。')
    page.get_by_role('button',name='保存意见',exact=True).click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    expect(page.locator('.saved-opinion.is-new')).to_contain_text('本次新增')
    bodies=[item['annotation']['body'] for item in page.request.get(url.rstrip('/')+'/api/annotations').json()['annotations']]
    assert bodies==['这是我自己的备忘，不是给制作的意见。']
    # Unchanged content cannot be saved twice, but the same text on a different
    # legal scope is a new opinion. 「整页意见」saves the page scope, so the
    # second save uses the artwork scope.
    expect(page.get_by_role('button',name='保存意见',exact=True)).to_be_disabled()
    expect(page.locator('.field-error[data-success]')).to_contain_text('不会重复新增')
    page.get_by_label('意见作用范围').select_option('artifact')
    expect(page.get_by_role('button',name='保存意见',exact=True)).to_be_enabled()
    page.get_by_role('button',name='保存意见',exact=True).click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    saved=page.request.get(url.rstrip('/')+'/api/annotations').json()['annotations']
    assert [item['annotation']['scope'] for item in saved]==['page','artifact']


def test_saved_opinions_group_by_scope_and_never_mix_pages(workbench):
    page,ctx,store,url,goto,_=workbench;goto()
    body=page.get_by_role('textbox',name='意见正文',exact=True)
    def write_opinion(text):
        page.get_by_role('button',name='保存意见',exact=True).click()
        expect(page.locator('.field-error[data-success]')).to_be_visible()
        assert text in page.request.get(url.rstrip('/')+'/api/annotations').json()['annotations'][-1]['annotation']['body']
    page.get_by_role('button',name='整页意见',exact=True).click()
    body.fill('这一页要改标题')
    write_opinion('这一页要改标题')
    expect(page.get_by_role('heading',name='本页整页意见（1）',exact=True)).to_be_visible()
    page.get_by_role('button',name='写新意见',exact=True).click()
    page.get_by_role('button',name='整页意见',exact=True).click()
    page.get_by_label('意见作用范围').select_option('artifact')
    body.fill('这张图稿的线宽要收一点')
    write_opinion('这张图稿的线宽要收一点')
    expect(page.get_by_role('heading',name='当前图稿意见 · SVG（1）',exact=True)).to_be_visible()
    page.get_by_role('button',name='写新意见',exact=True).click()
    page.get_by_label('意见作用范围').select_option('project')
    body.fill('整稿方向已认可')
    write_opinion('整稿方向已认可')
    # 整稿认可 is a review record, not a page requirement: it stays in its own
    # collapsed group and cannot be selected into this page's change plan.
    deck=page.locator('details.saved-group').filter(has_text='整稿认可与章节意见')
    expect(deck.locator('summary')).to_contain_text('（1）')
    deck.locator('summary').click()
    expect(deck).to_contain_text('整稿方向已认可')
    expect(deck).to_contain_text('整稿认可不是本页的修改要求')
    expect(deck.get_by_label('选入意见 3')).to_be_disabled()
    # Another page at the current version must not inherit these opinions: they are
    # counted, collapsed and not selectable, with the reason shown. (Saving bumped
    # the revision, so the pinned page is historical until the user returns.)
    link=url+'#'+urlencode({'project':page.request.get(url.rstrip('/')+'/api/project').json()['project_identity'],
                            'surface':'page','page':'p02','layer':'svg','revision':store.current_revision_id()})
    page.goto(link)
    expect(page.get_by_role('heading',name='本页整页意见（0）',exact=True)).to_be_visible()
    other=page.locator('details.saved-group').filter(has_text='其它页面的局部意见')
    expect(other.locator('summary')).to_contain_text('（2）')
    other.locator('summary').click()
    expect(other).to_contain_text('这一页要改标题')
    expect(other).to_contain_text('不能选入本页的修改计划')
    expect(other.get_by_label('选入意见 1')).to_be_disabled()


def test_requirement_is_explicit_and_plans_default_to_trial(workbench):
    import json
    page,ctx,store,url,goto,_=workbench;goto()
    page.get_by_role('button',name='整页意见',exact=True).click()
    page.get_by_role('textbox',name='意见正文',exact=True).fill('标题要更短')
    page.get_by_role('button',name='保存意见',exact=True).click()
    expect(page.locator('.field-error[data-success]')).to_be_visible()
    # Selecting an opinion opens its own requirement area, filled from the opinion
    # text instead of reusing a hidden drafting box.
    page.get_by_label('选入意见 1').check()
    requirement=page.get_by_label('修改要求')
    expect(requirement).to_be_visible(); expect(requirement).to_have_value('标题要更短')
    expect(page.locator('.change-requirement')).to_contain_text('本页整页')
    expect(page.locator('.change-requirement')).to_contain_text('候选')
    # An empty requirement is refused in Chinese before anything is sent.
    requirement.fill('')
    page.get_by_role('button',name='预览修改影响',exact=True).click()
    expect(page.locator('.annotations-panel .field-error[role=status]')).to_contain_text('请先写明修改要求')
    assert page.request.get(url.rstrip('/')+'/api/changes').json()['changes']==[]
    # A written requirement previews as a trial: candidates first, adoption later.
    requirement.fill('把标题缩短到 12 个字，保留正文与图标。')
    with page.expect_request('**/api/changes/plan') as captured:
        page.get_by_role('button',name='预览修改影响',exact=True).click()
    sent=json.loads(captured.value.post_data)['input']
    assert sent['mode']=='trial' and sent['instruction']=='把标题缩短到 12 个字，保留正文与图标。'
    expect(page.locator('.change-plan-preview')).to_contain_text('结果先作为候选返回')
    expect(page.locator('.change-plan-preview')).to_contain_text('未列出的图层与已有记录保持不变')
    expect(page.locator('.change-plan-preview')).to_contain_text('将修改')
    assert page.request.get(url.rstrip('/')+'/api/changes').json()['changes']==[]


def test_page_candidate_compares_its_own_basis_not_the_current_revision(workbench):
    import uuid as _uuid
    from deck_master import changes as changes_mod, service as service_mod
    from test_content_candidates import content_intent, start_task, page_envelope, accept
    page,ctx,store,url,goto,_=workbench
    path=store.project_root
    basis_revision=store.current_revision_id()
    plan=changes_mod.plan(path, input=content_intent(store, 'p01'))
    task_ids=changes_mod.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                                operation_id=str(_uuid.uuid4()))['operation_result']['task_ids']
    task=next(t for t in (store.read_object_json(r) for r in store.load_document()['tasks']) if t['task_id']==task_ids[0])
    start_task(path, task); accept(path, task, page_envelope(store, task))
    candidate_id=store.load_document()['candidates'][0]
    candidate=store.read_object_json(candidate_id)
    assert candidate['result_kind']=='page' and candidate['base_revision']==basis_revision
    # Move the page on: the comparison must keep showing the candidate's own basis.
    doc=store.load_document(); moved=copy.deepcopy(doc); entry=moved['pages'][0]
    body=store.read_object_json(entry['page']); body['customer_visible']['title']='后来的标题'
    moved['pages'][0]['page']=store.put_json_object(body)
    moved=bump_revision(moved,{'operation_id':str(_uuid.uuid4()),'kind':'content_update','description':'later page move','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=moved,operation_id=moved['change']['operation_id'])
    link=url+'#'+urlencode({'project':page.request.get(url.rstrip('/')+'/api/project').json()['project_identity'],
                            'surface':'page','page':'p01','layer':'content','revision':store.current_revision_id(),
                            'candidate':candidate['candidate_id']})
    page.goto(link)
    desk=page.locator('.candidate-desk')
    desk.wait_for()
    # Both sides come from the candidate's own record: the basis it was written
    # against and its result. The later page never leaks into the comparison.
    expect(desk).to_contain_text('当前正文 → 候选正文')
    expect(desk).to_contain_text('(rewritten)')
    assert '后来的标题' not in desk.inner_text(), desk.inner_text()[:400]


def test_escape_ends_the_open_comparison_before_leaving_the_page(workbench):
    page,ctx,store,url,goto,_=workbench;goto()
    page.get_by_role('button',name='比较此页版本',exact=True).click()
    select=page.get_by_label('选择同页比较版本')
    expect(select).to_be_visible()
    assert len(select.locator('option').all_inner_texts())>1, 'this fixture needs a second revision for the page'
    select.select_option(index=1)
    page.get_by_role('button',name='固定比较这个版本',exact=True).click()
    expect(page.locator('.page-columns.with-fixed-compare')).to_be_visible()
    page.keyboard.press('Escape')
    # One keypress closes the topmost layer only: the comparison ends and the work
    # surface stays where it was, with focus back on the entry that opened it.
    expect(page.locator('.page-columns.with-fixed-compare')).to_have_count(0)
    assert 'surface=page' in page.url, page.url
    expect(page.get_by_role('button',name='比较此页版本',exact=True)).to_be_focused()
    assert page.locator('.fixed-compare-controls').is_hidden()


def test_escape_inside_fullscreen_does_not_navigate_the_surface(workbench):
    page,ctx,store,url,goto,_=workbench;goto()
    page.get_by_role('button',name='比较此页版本',exact=True).click()   # user activation for fullscreen
    assert page.evaluate('''async () => { try { await document.querySelector('.page-columns').requestFullscreen(); return true; } catch { return false; } }''')
    expect(page.locator('.page-columns')).to_be_visible()
    assert page.evaluate('() => document.fullscreenElement !== null')
    page.keyboard.press('Escape'); page.wait_for_timeout(200)
    # Leaving fullscreen is the browser's own job. The work surface must not also
    # navigate away on the same keypress. Headless Chromium keeps the element
    # fullscreen (no native UI), so this checks the app-level regression only; the
    # visible exit still needs a headed run.
    assert 'surface=page' in page.url, page.url
    page.evaluate('() => document.exitFullscreen()')


def test_near_field_entry_names_returned_candidates(workbench):
    from test_candidates import dispatch as dispatch_candidate, start as start_candidate, accept as accept_candidate
    page,ctx,store,url,goto,_=workbench
    task=dispatch_candidate(store,'p01',layer='svg'); start_candidate(store,task); accept_candidate(store,task)
    goto()
    # The closed entry still says that something waits here, instead of hiding a
    # returned candidate behind a neutral label.
    summary=page.locator('.page-trial-entry > summary')
    expect(summary).to_contain_text('候选 1')
    expect(summary).to_contain_text('待比较 1')
    expect(page.get_by_text('本页候选与试作',exact=True)).to_be_visible()


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
    text='修正图标间距，保持其它对象。';page.get_by_role('textbox',name='意见正文',exact=True).fill(text)
    page.get_by_role('button',name='保存意见',exact=True).click();page.get_by_label('选入意见 1').check()
    page.get_by_label('修改要求').fill(text)
    doc=store.load_document();new=copy.deepcopy(doc);art=store.read_object_json(new['pages'][0]['svg']);art['limitations']=['concurrent edit']
    new['pages'][0]['svg']=store.put_json_object(art)
    new=bump_revision(new,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'synthetic concurrent writer','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=new,operation_id=new['change']['operation_id'])
    with page.expect_response('**/api/changes/plan') as response:page.get_by_role('button',name='预览修改影响',exact=True).click()
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
