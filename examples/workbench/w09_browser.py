"""W09 Chromium against real core APIs; synthetic material and simulated Host only."""
from __future__ import annotations
import argparse
import copy
import json
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master import content_ops
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--chromium-executable',type=Path);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    project=args.out/'project';create_sample(project,page_count=3,readonly=False);store=Store(project)
    base=store.load_document();entry=base['pages'][1];visible=copy.deepcopy(store.read_object_json(entry['page'])['customer_visible'])
    visible['body_blocks']=[{'id':'paragraph','type':'paragraph','text':'Original paragraph'},{'id':'list','type':'bullets','items':[{'id':'item','text':'Original bullet'}]},{'id':'table','type':'table','columns':[{'id':'col','label':'Original column'}],'rows':[{'id':'row','cells':[{'column_id':'col','display_text':'Original cell'}]}]}]
    planned=content_ops.plan(project,input={'schema_version':'content_operation_input.v1','project_id':base['project_id'],'base_revision':base['revision_id'],'content_plan_ref':base['content_plan'],'action':'edit','targets':[{'page_id':'p02','page_ref':entry['page']}],'instruction':'Synthetic structured text fixture','customer_visible':visible})
    content_ops.commit(project,plan_id=planned['plan_id'],base_revision=base['revision_id'],operation_id=str(uuid.uuid4()))
    initial=copy.deepcopy(store.load_document());titles={e['page_id']:store.read_object_json(e['page'])['customer_visible']['title'] for e in initial['pages']}
    checks=[];errors=[];posts=[]
    def check(name,value=True):
        assert value,name
        checks.append(name);print(name,flush=True)
    server=WorkbenchServer(project);url=server.start()
    def open_order(page):
        panel = page.locator('.content-order-panel')
        if not panel.evaluate('(node) => node.open'):
            panel.locator('summary').first.click()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=str(args.chromium_executable) if args.chromium_executable else None);context=browser.new_context(viewport={'width':1440,'height':1050});page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append({'url':r.url.split('/api/')[-1],'body':r.post_data_json}) if r.method=='POST' and '/api/content/' in r.url else None)
            try:
                page.goto(url+'v2/');page.get_by_role('button',name='内容与来源',exact=True).click()
                open_order(page)
                page.get_by_role('button',name='打开内容页 '+titles['p02'],exact=True).click();page.get_by_text('编辑本页标题与正文',exact=True).click()
                title=page.get_by_label('页面标题',exact=True);expect(title).to_be_enabled();title.fill('改后的事实 42');page.get_by_label('正文文字 2',exact=True).fill('Changed paragraph');page.get_by_label('正文文字 3',exact=True).fill('Changed bullet');page.get_by_label('正文文字 5',exact=True).fill('Changed cell')
                page.reload();page.get_by_text('编辑本页标题与正文',exact=True).click();expect(page.get_by_label('页面标题',exact=True)).to_have_value('改后的事实 42');check('body_draft_survives_refresh')
                page.get_by_role('button',name='预览正文修改影响',exact=True).click();expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_enabled();page.get_by_role('button',name='确认内容变更',exact=True).click()
                expect(page.locator('.page-copy>h2')).to_have_text('改后的事实 42');after=store.load_document()
                check('direct_edit_only_selected_page',after['pages'][0]==initial['pages'][0] and after['pages'][2]==initial['pages'][2] and after['pages'][1]['page']!=initial['pages'][1]['page'])
                changed_page=store.read_object_json(after['pages'][1]['page']);blocks=changed_page['customer_visible']['body_blocks'];check('paragraph_list_table_text_and_identities',blocks[0]['text']=='Changed paragraph' and blocks[1]['items'][0]=={'id':'item','text':'Changed bullet'} and blocks[2]['rows'][0]=={'id':'row','cells':[{'column_id':'col','display_text':'Changed cell'}]})
                page.screenshot(path=str(args.out/'03-structured-body.png'),full_page=True)
                check('original_immutable_and_basis_changed',after['pages'][1]['blueprint']==initial['pages'][1]['blueprint'])
                page.get_by_role('button',name='内容与来源',exact=True).click();open_order(page);handle=page.get_by_role('button',name='打开内容页 改后的事实 42',exact=True);expect(handle).to_be_enabled();handle.focus();handle.press('Alt+ArrowUp')
                expect(page.locator('.content-order-row').first).to_have_attribute('data-page-id','p02');check('keyboard_reorder_keeps_focus',handle.evaluate('(e)=>e===document.activeElement'))
                page.get_by_role('button',name='预览页序变更',exact=True).click();expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_enabled();page.get_by_role('button',name='确认内容变更',exact=True).click()
                expect(page.locator('.content-order-row').first).to_have_attribute('data-page-id','p02');page.wait_for_function("() => !document.querySelector('.business-pending:not([hidden])')");expect(page.locator('.topbar .version')).to_contain_text(store.current_revision_id()[:8])
                check('reorder_preserves_all_page_entries',store.load_document()['pages']==[after['pages'][1],after['pages'][0],after['pages'][2]])
                open_order(page)
                page.get_by_role('button',name='向后移动 改后的事实 42',exact=True).click();expect(page.locator('.content-order-row').nth(1)).to_have_attribute('data-page-id','p02');check('mouse_reorder_draft')
                page.get_by_text('编辑内容计划',exact=True).click();page.get_by_label('页面目标 改后的事实 42',exact=True).fill('解释一个明确事实与边界')
                page.get_by_role('button',name='预览内容计划变更',exact=True).click();expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_enabled();page.get_by_role('button',name='确认内容变更',exact=True).click()
                page.wait_for_function("() => !document.querySelector('.business-pending:not([hidden])')");expect(page.locator('.topbar .version')).to_contain_text(store.current_revision_id()[:8])
                page.get_by_text('编辑内容计划',exact=True).click();expect(page.get_by_label('页面目标 改后的事实 42',exact=True)).to_have_value('解释一个明确事实与边界');check('outline_does_not_edit_body',store.load_document()['pages']==[after['pages'][1],after['pages'][0],after['pages'][2]])
                source=args.out/'material.txt';source.write_text('Synthetic source only.\nNo measured outcome supplied.\n')
                page.get_by_text('调整任务要求与材料',exact=True).click();page.get_by_label('新增材料完整路径（每行一个）').fill(str(source.resolve()));page.get_by_label('汇报受众',exact=True).fill('部门管理者');page.get_by_label('既定决定（每行一条）').fill('不声称未经实测的效果');page.get_by_label('本次输入变化说明').fill('补充验证材料并明确管理者受众')
                page.get_by_role('button',name='预览材料与任务变化',exact=True).click();expect(page.get_by_role('button',name='确认输入并交接判断',exact=True)).to_be_enabled();page.get_by_role('button',name='确认输入并交接判断',exact=True).click()
                expect(page.get_by_role('heading',name='当前任务',exact=True)).to_be_visible();check('inputs_dispatch_without_rewriting_pages',store.load_document()['pages']==[after['pages'][1],after['pages'][0],after['pages'][2]])
                page.get_by_role('button',name='内容与来源',exact=True).click();expect(page.get_by_text('输入待协调',exact=True)).to_be_visible();open_order(page);page.get_by_text('调整任务要求与材料',exact=True).click();page.get_by_role('button',name='读取材料原文 material.txt',exact=True).click()
                expect(page.get_by_text('仅定位到材料版本，未找到可核验的精确位置。',exact=True)).to_be_visible();expect(page.locator('#modal')).to_contain_text('Synthetic source only.');page.locator('#modal').get_by_role('button',name='关闭',exact=True).click();check('source_reading_honest_material_only')
                page.screenshot(path=str(args.out/'01-content.png'),full_page=True)
                page.get_by_label('选定内容页 '+titles['p03'],exact=True).check();page.get_by_label('选页调整要求').fill('仅移除当前选定的验证页');page.get_by_role('button',name='预览移除选页',exact=True).click();expect(page.locator('.content-operation')).to_contain_text('1 个旧页身份');page.get_by_role('button',name='确认内容变更',exact=True).click()
                expect(page.locator('.page-reading').first).to_have_attribute('data-page-id','p01');check('remove_focuses_neighbor_and_keeps_history',len(store.load_document()['pages'])==2 and len(store.load_document(initial['revision_id'])['pages'])==3)
                page.get_by_text('编辑本页标题与正文',exact=True).click();expect(page.get_by_label('页面标题',exact=True)).to_be_enabled();page.get_by_label('页面标题',exact=True).fill('响应丢失时保存的标题')
                page.get_by_role('button',name='预览正文修改影响',exact=True).click();expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_enabled()
                def drop(route):
                    route.fetch();route.abort('failed')
                page.route('**/api/content/commit',drop,times=1);page.get_by_role('button',name='确认内容变更',exact=True).click();expect(page.get_by_role('button',name='核实保存结果',exact=True)).to_be_enabled()
                page.get_by_label('页面标题',exact=True).fill('响应丢失后继续写的标题');page.get_by_role('button',name='核实保存结果',exact=True).click();expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停',exact=True)).not_to_be_visible()
                expect(page.get_by_label('页面标题',exact=True)).to_have_value('响应丢失后继续写的标题');check('unknown_save_keeps_later_draft')
                accepted=store.read_object_json(next(e for e in store.load_document()['pages'] if e['page_id']=='p01')['page']);check('unknown_recovery_does_not_resubmit_later_input',accepted['customer_visible']['title']=='响应丢失时保存的标题')
                page.set_viewport_size({'width':1180,'height':820});page.screenshot(path=str(args.out/'02-edit-1180.png'),full_page=True);check('no_horizontal_overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check('no_browser_errors',not errors)
            except Exception:
                page.screenshot(path=str(args.out/'failure.png'),full_page=True);(args.out/'failure.txt').write_text(page.locator('body').inner_text());raise
            finally:context.close();browser.close()
    finally:server.stop()
    (args.out/'checks.json').write_text(json.dumps({'synthetic':True,'actual_model_calls':0,'browser':browser.version,'checks':checks,'errors':errors},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
