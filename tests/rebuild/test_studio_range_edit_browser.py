"""Exact-range replacement uses real Studio content transactions, Unicode offsets and one leaf."""
import copy
import json
import re
from urllib.parse import urlencode
import pytest
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_content_ops import commit, value
from test_studio_content_browser import authorize_content_edits

pytestmark=pytest.mark.browser
SAME='A😀重复e\u0301重复Z'
LEAF='正文块 2 · 重复片段 · 条目 1 · 文字'

@pytest.fixture
def exact_editor(tmp_path):
    from playwright.sync_api import sync_playwright
    project=tmp_path/'range';create_sample(project,page_count=2,readonly=False);store=Store(project)
    authorize_content_edits(project)
    doc=store.load_document();visible=copy.deepcopy(store.read_object_json(doc['pages'][0]['page'])['customer_visible'])
    visible['body_blocks']=[{'id':'first','type':'paragraph','text':SAME},{'id':'second','type':'bullets','heading':'重复片段','items':[{'id':'item1','text':SAME}]}]
    commit(project,store,value(store,ids=('p01',),customer_visible=visible))
    server=WorkbenchServer(project);base=server.start();out=tmp_path/'evidence'/'exact-range';out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        identity=page.request.get(base+'api/project').json()['project_identity']
        url=base+'studio/#'+urlencode({'project':identity,'surface':'page','page':'p01','layer':'content','revision':store.current_revision_id()})
        page.goto(url);page.locator('.content-editor > summary').click()
        try:yield page,store,project,url,out;assert errors==[]
        finally:browser.close();server.stop()

def open_range(page):
    page.get_by_role('button',name='精确修改选段 · '+LEAF.replace(' · ','/'),exact=True).click()
    return page.get_by_role('dialog',name='精确修改选段',exact=True)

def choose(dialog,replacement,start=7,end=8):
    dialog.get_by_label('起始字符（从 1 计）').fill(str(start));dialog.get_by_label('结束字符（含）').fill(str(end))
    dialog.get_by_label('替换文字（留空删除选段）').fill(replacement)
    dialog.get_by_role('button',name='校验替换选段',exact=True).click()
    dialog.get_by_role('button',name='比较选段原文与改文',exact=True).click()

def test_exact_unicode_range_cancel_restore_replace_delete_and_history(exact_editor):
    from playwright.sync_api import expect
    page,store,project,url,out=exact_editor;before=store.load_document();requests=[]
    page.on('request',lambda r:requests.append({'url':r.url,'body':r.post_data}) if '/api/content/' in r.url and r.method=='POST' else None)
    dialog=open_range(page)
    # Read glyph geometry only, then select using actual mouse input. The
    # second repeated phrase starts at UTF-16 offset 7 / Unicode offset 6.
    rect=dialog.get_by_label('选段原文',exact=True).evaluate("el=>{const r=document.createRange();r.setStart(el.firstChild,7);r.setEnd(el.firstChild,9);const b=r.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height}}")
    page.mouse.move(rect['x']+1,rect['y']+rect['height']/2);page.mouse.down();page.mouse.move(rect['x']+rect['width']-1,rect['y']+rect['height']/2,steps=5);page.mouse.up()
    assert page.evaluate('getSelection()?.toString()')=='重复'
    dialog.get_by_role('button',name='使用当前选段',exact=True).click()
    expect(dialog.get_by_label('起始字符（从 1 计）')).to_have_value('7')
    expect(dialog.get_by_label('结束字符（含）')).to_have_value('8')
    dialog.get_by_label('结束字符（含）').fill('999');dialog.get_by_role('button',name='校验替换选段',exact=True).click()
    expect(dialog.get_by_role('button',name='比较选段原文与改文',exact=True)).to_be_disabled()
    assert store.load_document()==before
    choose(dialog,'新')
    expect(dialog).to_contain_text('第 7–8 字 · 其余同文位置保持不变')
    dialog.get_by_role('button',name='取消并保留范围草稿',exact=True).click()
    assert store.load_document()==before
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    page.reload();page.locator('.content-editor > summary').click();dialog=open_range(page)
    expect(dialog.get_by_label('替换文字（留空删除选段）')).to_have_value('新')
    expect(dialog.get_by_label('起始字符（从 1 计）')).to_have_value('7')
    choose(dialog,'新');page.screenshot(path=str(out/'01-range-review-1440.png'))
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'02-range-review-390.png'))
    dialog.get_by_role('button',name='应用到正文草稿并查看影响',exact=True).click()
    expect(page.get_by_label(LEAF,exact=True)).to_have_value('A😀重复e\u0301新Z')
    expect(page.get_by_label('正文块 1 · 文字',exact=True)).to_have_value(SAME)
    expect(page.locator('.content-check')).to_contain_text('修改 1 页')
    assert store.load_document()==before
    with page.expect_response('**/api/content/commit') as receipt:page.get_by_role('button',name='确认内容变更',exact=True).click()
    assert receipt.value.ok
    expect(page).to_have_url(re.compile('revision='+receipt.value.json()['operation_result']['revision_id']))
    page.locator('.content-editor > summary').click()
    after=store.load_document();updated=store.read_object_json(after['pages'][0]['page'])['customer_visible']
    assert updated['body_blocks'][1]['items'][0]['text']=='A😀重复e\u0301新Z'
    assert updated['body_blocks'][0]['text']==SAME and after['pages'][1]==before['pages'][1]
    dialog=open_range(page);choose(dialog,'',2,2)
    expect(dialog).to_contain_text('（删除该选段）')
    dialog.get_by_role('button',name='应用到正文草稿并查看影响',exact=True).click()
    expect(page.get_by_label(LEAF,exact=True)).to_have_value('A重复e\u0301新Z')
    with page.expect_response('**/api/content/commit') as receipt:page.get_by_role('button',name='确认内容变更',exact=True).click()
    assert receipt.value.ok
    expect(page).to_have_url(re.compile('revision='+receipt.value.json()['operation_result']['revision_id']))
    expect(page.locator('.content-editor > summary')).to_be_visible()
    final=store.load_document();assert store.read_object_json(final['pages'][0]['page'])['customer_visible']['body_blocks'][1]['items'][0]['text']=='A重复e\u0301新Z'
    page.goto(url);expect(page.locator('.history-banner')).to_be_visible()
    expect(page.get_by_role('button',name='精确修改选段 · '+LEAF.replace(' · ','/'),exact=True)).to_have_count(0)
    assert store.load_document()==final
    (out/'result.json').write_text(json.dumps({'passed':True,'initial_revision':before['revision_id'],'final_revision':final['revision_id'],'unselected_page_unchanged':final['pages'][1]==before['pages'][1],'requests':requests},ensure_ascii=False,indent=2))

def test_exact_range_later_write_and_stale_plan_are_preserved(exact_editor):
    from playwright.sync_api import expect
    page,store,project,url,out=exact_editor;before=store.load_document()
    dialog=open_range(page);choose(dialog,'新');dialog.get_by_role('button',name='应用到正文草稿并查看影响',exact=True).click()
    confirm=page.get_by_role('button',name='确认内容变更',exact=True);expect(confirm).to_be_enabled()
    field=page.get_by_label(LEAF,exact=True);field.fill('核对后另写，旧计划失效')
    expect(confirm).to_be_disabled();assert store.load_document()==before
    page.get_by_role('button',name='预览正文修改影响',exact=True).click();expect(confirm).to_be_enabled()
    held=[];page.route('**/api/content/commit',lambda route:held.append(route))
    with page.expect_request('**/api/content/commit'):confirm.click()
    field.fill('提交回包前的后写草稿，必须保留')
    assert len(held)==1
    response=held[0].fetch();held[0].fulfill(response=response)
    expect(page.locator('.content-save-receipt')).to_contain_text('后写输入仍保留')
    expect(field).to_have_value('提交回包前的后写草稿，必须保留')
    current=store.load_document();assert store.read_object_json(current['pages'][0]['page'])['customer_visible']['body_blocks'][1]['items'][0]['text']=='核对后另写，旧计划失效'
    assert current['pages'][1]==before['pages'][1]
    page.get_by_role('button',name='预览正文修改影响',exact=True).click()
    expect(confirm).to_be_disabled()
    expect(page.locator('.content-operation-note')).to_contain_text('项目已有新版本')


def test_old_range_preview_does_not_close_reopened_dialog(exact_editor):
    from playwright.sync_api import expect
    page,store,project,url,out=exact_editor;before=store.load_document()
    dialog=open_range(page);choose(dialog,'首次修改')
    held=[];page.route('**/api/content/plan',lambda route:held.append(route))
    with page.expect_request('**/api/content/plan'):
        dialog.get_by_role('button',name='应用到正文草稿并查看影响',exact=True).click()
    dialog.get_by_role('button',name='取消并保留范围草稿',exact=True).click()
    dialog=open_range(page)
    field=dialog.get_by_label('替换文字（留空删除选段）');field.fill('重开的新范围草稿')
    expect(dialog).to_be_visible();response=held[0].fetch()
    with page.expect_response('**/api/content/plan'):held[0].fulfill(response=response)
    expect(dialog).to_be_visible();expect(field).to_have_value('重开的新范围草稿');expect(field).to_be_focused()
    assert store.load_document()==before
    dialog.get_by_role('button',name='取消并保留范围草稿',exact=True).click()
    expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_disabled()
    expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
    page.reload();page.locator('.content-editor > summary').click();dialog=open_range(page)
    expect(dialog.get_by_label('替换文字（留空删除选段）')).to_have_value('重开的新范围草稿')
