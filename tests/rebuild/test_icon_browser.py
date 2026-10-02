"""Real UI integration; synthetic pages and zero model calls."""
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlencode
import pytest
from deck_master import icons, tasks
from deck_master.web import WorkbenchServer
from test_icon_quality import icon_store, input_for

pytestmark=pytest.mark.browser

@pytest.fixture
def icon_browser(icon_store):
    from playwright.sync_api import sync_playwright
    server=WorkbenchServer(icon_store.project_root);url=server.start()
    with sync_playwright() as runtime:
        executable=shutil.which('chromium') or shutil.which('chromium-browser')
        browser=runtime.chromium.launch(executable_path=executable,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.get_by_role('heading',name='制作总览',exact=True).wait_for()
        info=page.request.get(url.rstrip('/')+'/api/project').json()
        page.goto(url.split('#')[0]+'#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p01','layer':'svg','revision':icon_store.current_revision_id()}))
        page.get_by_role('heading',name='优化图标',exact=True).wait_for()
        try:yield page,icon_store,errors
        finally:browser.close();server.stop()
    assert errors==[]


def test_icon_proposal_compare_confirm_keyboard_and_dispatch(icon_browser,tmp_path):
    from playwright.sync_api import expect
    page,store,errors=icon_browser;before=store.load_document()
    icons.propose(store.project_root,input=input_for(store,method='standard'))
    page.get_by_role('button',name='刷新图标方案',exact=True).click()
    page.get_by_role('button',name='查看 p01 的图标范围',exact=True).wait_for()
    page.get_by_role('button',name='查看 p01 的图标范围',exact=True).focus();page.keyboard.press('Enter')
    dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
    page.locator('.icon-comparison canvas').first.wait_for()
    for width,height in [(1280,800),(1440,900),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        page.get_by_label('显示正常页面尺寸').check()
        page.get_by_label('显示正常页面尺寸').uncheck()
        page.get_by_label('图标局部放大倍数').select_option('4')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(tmp_path/f'icon-{width}.png'))
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
    page.get_by_role('button',name='确认这些图标范围和处理方式',exact=True).click()
    page.get_by_label('选入图标页 p01').wait_for()
    assert store.load_document()['pages']==before['pages']
    expect(page.get_by_label('选入图标页 p01')).not_to_be_checked()
    page.get_by_label('选入图标页 p01').check()
    page.get_by_role('button',name='预览选中页图标试作',exact=True).click()
    page.get_by_role('button',name='确认计划并交接图标修复',exact=True).wait_for()
    page.get_by_role('button',name='确认计划并交接图标修复',exact=True).click()
    page.get_by_role('heading',name='优化图标',exact=True).wait_for(state='hidden')
    doc=store.load_document();new=[store.read_object_json(t) for t in doc['tasks'] if store.read_object_json(t).get('stage_request',{}).get('icon_recipe_ref')]
    assert len(new)==1 and 'icon_repair' in new[0]['required_capabilities']
    assert doc['pages']==before['pages'] and doc['outputs']==before['outputs'] and errors==[]
    snapshot=page.evaluate("async()=> (await import('/v2/images.js')).imagePool.snapshot()")
    assert snapshot['network_peak']<=6 and snapshot['decode_peak']<=2 and snapshot['large_peak']<=4


def test_icon_http_cli_parity_and_origin(icon_store,tmp_path,capsys):
    from deck_master import cli
    from test_web import _get_json,_post_json,_session_token
    server=WorkbenchServer(icon_store.project_root);url=server.start().rstrip('/')
    try:
        token=_session_token(url);value=input_for(icon_store)
        assert _post_json(url+'/api/icons/propose',{'input':value},None,None)[0]==403
        code,result=_post_json(url+'/api/icons/propose',{'input':value},token,url);assert code==200
        inp=tmp_path/'input.json';inp.write_text(json.dumps(value))
        assert cli.main(['icons','propose','--project',str(icon_store.project_root),'--input',str(inp)])==0
        assert json.loads(capsys.readouterr().out)==result
        assert _get_json(url+'/api/icons/inspect?page_id=p01')[2]==icons.inspect(icon_store.project_root,page_id='p01')
        assert _post_json(url+'/api/icons/confirm',{'unknown':True},token,url)[0]==422
    finally:server.stop()


def test_actual_icon_candidate_ppt_comparison_retry_and_adoption(icon_browser,tmp_path):
    from playwright.sync_api import expect
    from deck_master import candidate_preview,candidates
    from test_icon_quality import confirm,dispatch,start,accept
    page,store,errors=icon_browser
    recipe=confirm(store,input_for(store,method='standard'));task=dispatch(store,recipe)[0];start(store,task)
    cid=accept(store,task,icons.draft(store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode())['candidate_ids'][0]
    url=page.url.split('#')[0];info=page.request.get(url.rstrip('/')+'/api/project').json()
    page.goto(url+'#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p01','layer':'svg','revision':store.current_revision_id(),'candidate':cid}))
    page.get_by_role('heading',name='候选图标实际检查',exact=True).wait_for()
    page.get_by_role('button',name='打开局部对照',exact=True).click();page.get_by_label('图标比较产物').select_option('ppt')
    expect(page.get_by_text('此固定基准没有有效的实际 PPT 预览',exact=True)).to_be_visible()
    assert page.locator('.candidate-icon-review canvas').count()==1
    page.get_by_role('button',name='生成或重试实际 PPT 检查',exact=True).click()
    expect(page.locator('.candidate-icon-review [role=status]')).to_contain_text('工程检查通过',timeout=60000)
    expect(page.locator('.candidate-icon-review canvas')).to_have_count(2)
    for width,height in ((1280,800),(1440,900),(390,844)):
        page.set_viewport_size({'width':width,'height':height});page.get_by_label('显示正常页面尺寸').check();page.get_by_label('显示正常页面尺寸').uncheck();page.get_by_label('图标局部放大倍数').select_option('8')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(tmp_path/'actual-icon-ppt-comparison.png'),full_page=True)
    page.get_by_role('button',name='预览采用这个候选',exact=True).click();page.get_by_role('button',name='采用这个候选',exact=True).wait_for()
    page.get_by_role('button',name='采用这个候选',exact=True).click();expect(page.get_by_text(re.compile('这个候选已采用到'))).to_be_visible()
    assert store.load_document()['pages'][0]['svg']==candidates.show(store.project_root,candidate_id=cid)['candidate']['result_ref']
    assert icons.listing(store.project_root)['samples']
    pool=page.evaluate("async()=> (await import('/v2/images.js')).imagePool.snapshot()")
    assert pool['large_peak']<=4 and pool['decode_peak']<=2 and pool['network_peak']<=6 and errors==[]
