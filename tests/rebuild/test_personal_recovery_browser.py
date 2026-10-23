"""Real Studio backup/clear/restore and explicit legacy-reading migration."""
import json
import os
from pathlib import Path
import pytest
from deck_master import ui_journal, result_reading
from deck_master.web import WorkbenchServer
from test_result_reading import store

pytestmark=pytest.mark.browser


def test_studio_clear_backup_download_restore_and_legacy_reading(store,tmp_path):
    from playwright.sync_api import sync_playwright,expect
    project=store.project_root;before=store.load_document();reading=result_reading.get(project)
    first,second=[store.read_object_json(ref) for ref in before['tasks'][-2:]]
    draft={'schema_version':'ui_draft.v1','draft_id':'legacy-reading','project_id':before['project_id'],
        'project_identity':reading['project_identity'],'target':{'scope':'project','page_id':None,'layer':'notes'},
        'base_revision':before['revision_id'],'base_ref':None,'pending':None,
        'content':{'text':'待恢复的旧工作记录','run_desk':{'seen':[
            json.dumps([second['task_id'],[r['sha256'] for r in second['result_refs']]]),'invalid legacy receipt']}}}
    ui_journal.save(project,draft=draft)
    server=WorkbenchServer(project);url=server.start()+'studio/';errors=[];requests=[]
    evidence=Path(os.environ.get('DECK_MASTER_BROWSER_EVIDENCE',str(tmp_path/'evidence')))/'personal-recovery';evidence.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch()
        try:
            context=browser.new_context(accept_downloads=True,viewport={'width':1440,'height':900});page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append({'method':r.method,'url':r.url,'body':r.post_data}) if '/api/' in r.url else None)
            page.goto(url);page.get_by_role('button',name='任务与交付',exact=True).click()
            page.locator(f'[data-task-id="{first["task_id"]}"]').get_by_role('button',name='查看这项任务',exact=True).click()
            page.get_by_role('button',name='标记这些结果已读',exact=True).click()
            expect(page.get_by_role('button',name='已标记读过这些结果',exact=True)).to_be_disabled()
            page.get_by_role('button',name='查看全部任务',exact=True).click()
            page.get_by_role('heading',name='任务与交付',exact=True).wait_for()
            page.get_by_role('button',name='待决定',exact=True).click()
            expect(page.get_by_role('button',name='待决定',exact=True)).to_have_attribute('aria-pressed','true')
            page.get_by_role('button',name='个人记录与操作恢复',exact=True).click()
            expect(page.get_by_role('textbox',name='个人草稿',exact=True)).to_have_value('待恢复的旧工作记录')
            with page.expect_download() as download:
                page.get_by_role('button',name='下载草稿恢复文件',exact=True).click()
            recovery=tmp_path/'old-draft.json';download.value.save_as(recovery)
            assert json.loads(recovery.read_text())['draft']['content']['run_desk']['seen']==draft['content']['run_desk']['seen']
            page.get_by_role('dialog',name='个人记录与操作恢复',exact=True).get_by_role('button',name='关闭',exact=True).click()
            page.get_by_role('button',name='任务记录',exact=True).click()
            page.get_by_role('button',name='项目菜单',exact=True).click()
            page.get_by_role('button',name='个人状态与恢复',exact=True).click()
            panel=page.get_by_role('dialog',name='个人状态与恢复',exact=True)
            panel.get_by_role('button',name='生成清理计划',exact=True).click()
            expect(panel).to_contain_text('结果已读记录')
            with page.expect_response('**/api/ui-state/commit-clear') as response:
                panel.get_by_role('button',name='确认清理并保留备份',exact=True).click()
            cleared=response.value.json();assert cleared['status']=='cleared'
            assert result_reading.get(project)['seen']==[] and ui_journal.list_drafts(project)['records']==[]
            assert store.load_document()==before
            panel.get_by_role('button',name='查看清理备份',exact=True).first.click()
            dialog=page.get_by_role('dialog',name='个人状态备份',exact=True);expect(dialog).to_contain_text('个人状态备份')
            with page.expect_download() as download:dialog.get_by_role('link',name='下载清理备份',exact=True).click()
            backup=evidence/'downloaded-backup.json';download.value.save_as(backup)
            value=json.loads(backup.read_text());assert value['manifest_digest']==cleared['manifest_digest']
            assert {r['kind'] for r in value['records']} >= {'draft','result_reading'}
            dialog.get_by_role('button',name='预览恢复这份备份',exact=True).click()
            expect(dialog).to_contain_text('恢复前核对');expect(dialog).to_contain_text('待恢复的旧工作记录')
            page.screenshot(path=str(evidence/'01-restore-review-1440.png'))
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(evidence/'02-restore-review-390.png'))
            dialog.get_by_role('button',name='确认恢复并保留当前记录',exact=True).click()
            expect(dialog.get_by_role('status')).to_contain_text('已恢复')
            assert result_reading.get(project)['seen']==[result_reading.key(first)]
            assert any(r['draft']['content']['text']=='待恢复的旧工作记录' for r in ui_journal.list_drafts(project)['records'])
            context.close()
            # A fresh browser opens the restored project records, without an old local buffer.
            context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append({'method':r.method,'url':r.url,'body':r.post_data}) if '/api/' in r.url else None)
            page.goto(url);page.get_by_role('button',name='任务与交付',exact=True).click()
            page.get_by_role('button',name='核实并导入旧草稿的已读记录',exact=True).click()
            expect(page.get_by_role('status').filter(has_text='已核实导入 1 项旧记录')).to_be_visible()
            assert set(result_reading.get(project)['seen'])=={result_reading.key(first),result_reading.key(second)}
            page.reload();page.get_by_role('heading',name='任务与交付',exact=True).wait_for()
            page.locator(f'[data-task-id="{second["task_id"]}"]').get_by_role('button',name='查看这项任务',exact=True).click()
            expect(page.get_by_role('button',name='已标记读过这些结果',exact=True)).to_be_disabled()
            page.screenshot(path=str(evidence/'03-restored-reading.png'))
            assert store.load_document()==before and errors==[]
            (evidence/'result.json').write_text(json.dumps({'passed':True,'errors':errors,'business_unchanged':True,'reading':result_reading.get(project),'requests':requests},ensure_ascii=False,indent=2))
        finally:browser.close();server.stop()
