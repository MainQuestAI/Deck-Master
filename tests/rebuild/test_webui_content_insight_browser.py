"""Real service + system Chromium; synthetic Runtime objects, no external Host claims."""
import shutil
from urllib.parse import urlencode
import pytest
from playwright.sync_api import sync_playwright, expect
from deck_master import ui_journal
from deck_master.web import WorkbenchServer
from test_webui_content_insight import candidate

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('size', [(1280,800),(1440,900),(390,844)])
def test_zero_page_narrative_methods_and_refresh(tmp_path, size):
    project, store, task, ref = candidate(tmp_path)
    server = WorkbenchServer(project); url = server.start(); errors=[]
    info = ui_journal.project_info(project)
    link = url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','layer':'content','revision':store.current_revision_id(),'content_area':'arguments','proposal':ref['sha256']})
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':size[0],'height':size[1]})
            page.on('pageerror', lambda e:errors.append(str(e)))
            page.goto(link)
            expect(page.locator('.argument-reading h3')).to_contain_text('版本未知')
            expect(page.get_by_role('button',name='记录方向决定',exact=True)).to_be_visible()
            page.reload()
            expect(page.locator('.argument-reading h3')).to_contain_text('版本未知')
            page.get_by_role('button',name='方法与案例',exact=True).click()
            expect(page.locator('#content-area-methods')).to_contain_text('当前没有可准备的新阶段')
            page.get_by_label('准备上下文').select_option('independent')
            expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.locator('label.method-entry').filter(has_text='content-m04 ·').locator('input').check()
            page.get_by_role('button',name='阅读 content-m04',exact=True).click()
            expect(page.locator('#content-area-methods > section > pre')).not_to_be_empty()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/f'webui-{size[0]}.png'),full_page=True)
            assert errors==[]
            browser.close()
    finally: server.stop()


def test_direction_two_independent_operations_without_dispatch(tmp_path):
    project,store,task,ref=candidate(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project)
    before=store.load_document();errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','layer':'content','revision':store.current_revision_id(),'content_area':'arguments','proposal':ref['sha256']}))
            page.get_by_role('button',name='记录方向决定',exact=True).click()
            page.get_by_label('确认这份方向的理由').fill('采用此方向，保留未知版本的限定，不启动制作。')
            page.get_by_role('button',name='确认记录方向决定',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('方向决定已记录，采用尚未完成')
            decision_rev=store.current_revision_id();assert store.load_document().get('narrative') is None
            page.get_by_role('button',name='确认采用此方向',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('方向已采用')
            doc=store.load_document();assert doc['narrative']==ref and doc['revision_id']!=decision_rev
            assert doc['tasks']==before['tasks'] and not doc['pages']
            assert len(doc['collaboration']['decisions'])==1 and errors==[]
            browser.close()
    finally:server.stop()


def test_review_deeplink_refresh_and_no_default_first_finding(tmp_path):
    from test_webui_content_insight import reviewed_project
    project,store,ref=reviewed_project(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project)
    before=store.current_revision_id()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            params={'project':info['project_identity'],'surface':'runs','layer':'content','revision':before,'review':'reading-review','review_sha256':ref['sha256'],'finding':'f2','finding_index':1}
            page.goto(url+'studio/#'+urlencode(params))
            expect(page.locator('.insight-finding h2')).to_have_text('核实原位置')
            page.reload();expect(page.locator('.insight-finding h2')).to_have_text('核实原位置')
            params['finding_index']=0;page.goto(url+'studio/#'+urlencode(params))
            expect(page.get_by_text('原问题定位不匹配，未自动选中其他问题。请返回原审阅记录核对。')).to_be_visible()
            assert store.current_revision_id()==before
            browser.close()
    finally:server.stop()


def test_review_drafts_keep_distinct_finding_identity_and_do_not_write_business(tmp_path):
    from test_webui_content_insight import reviewed_project
    project,store,ref=reviewed_project(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project);before=store.load_document()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            base={'project':info['project_identity'],'surface':'runs','layer':'content','revision':before['revision_id'],'review':'reading-review','review_sha256':ref['sha256']}
            for fid,index,text in [('f1',0,'补充限定条件'),('f2',1,'核实原位置')]:
                page.goto(url+'studio/#'+urlencode({**base,'finding':fid,'finding_index':index}))
                page.get_by_role('button',name='准备范围交接草稿',exact=True).click()
                dialog=page.get_by_role('dialog')
                expect(dialog.get_by_label('审阅交接备注')).to_have_value(__import__('re').compile(text))
                dialog.get_by_role('button',name='保存个人草稿',exact=True).click()
                expect(dialog.locator('.review-draft-state')).to_contain_text('已保存到项目')
                page.keyboard.press('Escape')
            records=page.request.get(url+'api/drafts').json()['records']
            handoffs=[r['draft']['content']['review_handoff'] for r in records if 'review_handoff' in r['draft']['content']]
            assert {h['finding_id'] for h in handoffs}=={'f1','f2'}
            assert store.load_document()==before
            browser.close()
    finally:server.stop()


def test_direction_lost_ack_refresh_lookup_reuses_original_operation(tmp_path):
    project,store,_,ref=candidate(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','layer':'content','revision':store.current_revision_id(),'content_area':'arguments','proposal':ref['sha256']}))
            def lose_once(route):
                response=route.fetch();assert response.ok
                route.abort('failed')
            page.route('**/collaboration/decisions',lose_once,times=1)
            page.get_by_role('button',name='记录方向决定',exact=True).click();page.get_by_label('确认这份方向的理由').fill('合成恢复验证，保留两维度判断。')
            page.get_by_role('button',name='确认记录方向决定',exact=True).click()
            expect(page.get_by_role('button',name='核实原操作',exact=True)).to_be_enabled()
            assert len(store.load_document()['collaboration']['decisions'])==1
            page.reload()
            page.get_by_role('button',name='核实或查看原方向操作',exact=True).click()
            page.get_by_role('button',name='核实原操作',exact=True).click()
            expect(page.get_by_role('button',name='确认采用此方向',exact=True)).to_be_enabled()
            page.get_by_role('button',name='确认采用此方向',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('方向已采用')
            assert len(store.load_document()['collaboration']['decisions'])==1
            assert store.load_document()['narrative']==ref
            browser.close()
    finally:server.stop()


def test_review_page_atom_and_return_keep_fixed_finding(tmp_path):
    from test_webui_content_insight import reviewed_project
    project,store,ref=reviewed_project(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project);revision=store.current_revision_id()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','layer':'content','revision':revision,'review':'reading-review','review_sha256':ref['sha256'],'finding':'f1','finding_index':0}))
            page.get_by_role('button',name='定位原页面文字',exact=True).click()
            expect(page.get_by_role('heading',name='正文与证据',exact=True)).to_be_visible()
            page.reload()
            page.get_by_role('button',name='返回原审阅问题',exact=True).click()
            expect(page.locator('.insight-finding h2')).to_have_text('补充限定条件')
            assert 'finding_index=0' in page.url and ref['sha256'] in page.url
            assert store.current_revision_id()==revision
            browser.close()
    finally:server.stop()
