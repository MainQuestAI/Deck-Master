"""Browser source replacement/removal over an explicit synthetic CLI fixture."""
from __future__ import annotations
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    subprocess.run([sys.executable,str(Path(__file__).with_name('w09_content_inputs.py')),'--out',str(args.out/'fixture')],check=True,capture_output=True)
    project=args.out/'fixture'/'synthetic-project';store=Store(project);before=copy.deepcopy(store.load_document());checks=[];errors=[]
    server=WorkbenchServer(project);url=server.start()
    def check(name,value=True):assert value,name;checks.append(name);print(name,flush=True)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(url+'v2/');page.get_by_role('button',name='内容与来源',exact=True).click();page.get_by_text('调整任务要求与材料',exact=True).click()
                name=before['sources'][0]['name'];page.get_by_label('材料用途 '+name,exact=True).fill('用于核对容量范围，不支持效率承诺');page.get_by_label('本次输入变化说明').fill('补充材料用途')
                page.get_by_role('button',name='预览材料与任务变化',exact=True).click();expect(page.locator('.content-operation')).to_contain_text('更新 1 份材料用途');page.get_by_role('button',name='确认输入并交接判断',exact=True).click();expect(page.get_by_role('heading',name='当前任务',exact=True)).to_be_visible();check('metadata_uses_real_input_transaction',store.load_document()['sources'][0]['usage_note']=='用于核对容量范围，不支持效率承诺')
                page.get_by_role('button',name='内容与来源',exact=True).click();page.get_by_text('调整任务要求与材料',exact=True).click();page.get_by_label('材料操作 '+name,exact=True).select_option('replace')
                source=args.out/'new-material.md';source.write_text('Synthetic replacement.\nCapacity is now 84; Host has not judged impact.\n')
                page.get_by_label('替换路径 '+name,exact=True).fill(str(source.resolve()));page.get_by_label('本次输入变化说明').fill('容量说明替换为新版本')
                page.get_by_role('button',name='预览材料与任务变化',exact=True).click();expect(page.locator('.content-operation')).to_contain_text('替换：'+name);page.get_by_role('button',name='确认输入并交接判断',exact=True).click();expect(page.get_by_role('heading',name='当前任务',exact=True)).to_be_visible();check('replace_preserves_page_entries_pending_host',store.load_document()['pages']==before['pages'] and store.load_document()['sources'][0]['extract']!=before['sources'][0]['extract'])
                page.get_by_role('button',name='内容与来源',exact=True).click();page.get_by_text('编辑内容计划',exact=True).click();page.get_by_role('button',name='查看目标来源 L2',exact=True).click();expect(page.locator('#modal .read-text').first).to_have_text('Capacity is 42.');page.locator('#modal').get_by_role('button',name='关闭',exact=True).click();check('old_goal_reads_exact_old_material_version')
                page.get_by_text('调整任务要求与材料',exact=True).click();page.get_by_label('材料操作 new-material.md',exact=True).select_option('remove');page.get_by_label('本次输入变化说明').fill('从当前输入移除这份材料，历史保留');page.get_by_role('button',name='预览材料与任务变化',exact=True).click();page.get_by_role('button',name='确认输入并交接判断',exact=True).click();expect(page.get_by_role('heading',name='当前任务',exact=True)).to_be_visible();check('source_removal_preserves_history_and_pages',not store.load_document()['sources'] and store.load_document()['pages']==before['pages'] and store.load_document(before['revision_id'])['sources']==before['sources'])
                page.get_by_role('button',name='内容与来源',exact=True).click();page.get_by_text('编辑内容计划',exact=True).click();page.get_by_role('button',name='查看目标来源 L2',exact=True).click();expect(page.locator('#modal .read-text').first).to_have_text('Capacity is 42.');check('removed_source_historical_locator_still_readable')
                page.screenshot(path=str(args.out/'source-version.png'),full_page=True);check('no_browser_errors',not errors)
            except Exception:
                page.screenshot(path=str(args.out/'failure.png'),full_page=True);raise
            finally:context.close();browser.close()
    finally:server.stop()
    (args.out/'checks.json').write_text(json.dumps({'synthetic':True,'actual_model_calls':0,'checks':checks,'errors':errors},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
