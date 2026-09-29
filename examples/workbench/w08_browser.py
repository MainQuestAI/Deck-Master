"""W08 browser flow over real APIs and explicitly synthetic Host output. No model calls."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master.web import WorkbenchServer
from w08_style_transfer import SyntheticStyle


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    flow=SyntheticStyle(args.out);checks=[];errors=[];posts=[]
    doc=flow.store.load_document();titles={e['page_id']:flow.store.read_object_json(e['page'])['customer_visible']['title'] for e in doc['pages']}
    def check(name,value=True):
        assert value,name
        checks.append(name);print(name,flush=True)
    server=WorkbenchServer(flow.project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1100});page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append({'url':r.url.split('/api/')[-1],'body':r.post_data_json}) if r.method=='POST' and ('/api/styles/' in r.url or '/api/changes/commit' in r.url) else None)
            page.goto(url+'v2/');page.get_by_role('button',name='风格校准',exact=True).click()
            reference=page.get_by_label('风格参考原图');expect(reference).to_be_enabled();reference.select_option('p01')
            for pid in ['p02','p03']:page.get_by_label('风格目标 '+titles[pid],exact=True).check()
            page.get_by_label('风格短要求').fill('借用参考配色与文字层级，保持标题、事实、数字和构图。')
            page.get_by_role('button',name='检查风格要求',exact=True).click()
            confirm=page.get_by_role('button',name='确认这版风格要求',exact=True);expect(confirm).to_be_enabled()
            check('simple_path_without_advanced',not page.locator('details').filter(has=page.get_by_text('高级：借用维度、原文选段与建议',exact=True)).evaluate('(d)=>d.open'))
            check('default_excludes_composition',set(posts[-1]['body']['input']['dimensions'])=={'palette','typography'})
            before=copy.deepcopy(flow.store.load_document())
            page.screenshot(path=str(args.out/'01-simple-proposal.png'),full_page=True)
            confirm.click();first=page.get_by_role('button',name='预览单页试作',exact=True);expect(first).to_be_enabled()
            after=flow.store.load_document();check('confirm_no_dispatch_or_page_change',before['pages']==after['pages'] and before['tasks']==after['tasks'])
            recipe_id=page.get_by_label('已确认的风格版本').input_value()
            first.click();dispatch=page.get_by_role('button',name='保存并交接风格试作',exact=True);expect(dispatch).to_be_enabled();dispatch.click()
            expect(page.locator('.style-calibration')).to_have_count(0)
            task=flow.store.read_object_json(flow.store.load_document()['tasks'][-1]);check('first_trial_exactly_one_target',task['scope_pages']==['p02'])
            current=copy.deepcopy(flow.store.load_document()['pages']);cid=flow.image(task)['candidate_ids'][0]
            check('trial_return_does_not_replace_current',flow.store.load_document()['pages']==current)
            def current_style():
                page.goto(url+'v2/');expect(page.locator('#view-title')).to_be_visible()
                refresh=page.get_by_role('button',name='查看当前版本',exact=True)
                if refresh.is_visible():
                    refresh.click();expect(refresh).not_to_be_visible()
                page.get_by_role('button',name='风格校准',exact=True).click();expect(page.get_by_label('已确认的风格版本').locator('option')).to_have_count(2)
                page.get_by_label('已确认的风格版本').select_option(recipe_id);expect(page.get_by_role('button',name='预览单页试作',exact=True)).to_be_enabled()
            current_style();compare=page.get_by_role('button',name='比较候选 '+cid[-6:],exact=True);expect(compare).to_be_visible();compare.click()
            expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id',cid)
            page.get_by_role('button',name='预览采用这个候选',exact=True).click();adopt=page.get_by_role('button',name='采用这个候选',exact=True);expect(adopt).to_be_enabled();adopt.click()
            expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停',exact=True)).not_to_be_visible()
            page.wait_for_function("() => document.body.innerText.includes('已采用')")
            check('browser_adoption_only_target',flow.store.load_document()['pages'][0]==current[0] and flow.store.load_document()['pages'][2]==current[2] and flow.store.load_document()['pages'][1]['blueprint']!=current[1]['blueprint'])
            current_style();page.get_by_role('button',name='从此候选扩展',exact=True).click()
            page.get_by_text('采用满意候选后，扩到明确选择的其它页',exact=True).click();page.get_by_label('扩展到 '+titles['p03'],exact=True).check()
            page.get_by_role('button',name='预览明确选页的扩展',exact=True).click();expect(page.get_by_role('button',name='保存并交接风格试作',exact=True)).to_be_enabled()
            check('explicit_expansion_one_page',posts[-1]['body']['input']['page_ids']==['p03'] and posts[-1]['body']['input']['adopted_candidate_id']==cid)
            page.screenshot(path=str(args.out/'02-expansion-plan.png'),full_page=True)
            page.get_by_label('扩展图像调用上限').fill('2');expect(page.get_by_role('button',name='保存并交接风格试作',exact=True)).to_be_disabled();check('changed_scope_invalidates_plan')
            page.get_by_role('button',name='预览明确选页的扩展',exact=True).click();expect(page.get_by_role('button',name='保存并交接风格试作',exact=True)).to_be_enabled()
            page.get_by_role('button',name='保存并交接风格试作',exact=True).click();expect(page.locator('.style-calibration')).to_have_count(0)
            before_expansion=copy.deepcopy(flow.store.load_document()['pages']);task=flow.store.read_object_json(flow.store.load_document()['tasks'][-1]);flow.image(task,2)
            check('expansion_return_keeps_reference_and_adopted_page',flow.store.load_document()['pages']==before_expansion)
            current_style();page.get_by_role('button',name='以此版本修改要求',exact=True).click()
            page.get_by_text('高级：借用维度、原文选段与建议',exact=True).click();expect(page.get_by_label('借用构图',exact=True)).not_to_be_checked()
            page.get_by_label('借用线条',exact=True).check();page.get_by_label('线条要求',exact=True).fill('细实线')
            page.get_by_label('未确认的 Host 风格建议').fill('明确标记为建议，不是实际来源。')
            page.get_by_role('button',name='检查风格要求',exact=True).click();expect(page.get_by_role('button',name='确认这版风格要求',exact=True)).to_be_enabled()
            check('versioned_advanced_suggestion',posts[-1]['body']['input']['parent_recipe_id']==recipe_id and posts[-1]['body']['input']['dimensions']['lines']=='细实线')
            page.set_viewport_size({'width':1180,'height':820});page.screenshot(path=str(args.out/'03-advanced-1180.png'),full_page=True)
            check('no_horizontal_overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            page.get_by_role('button',name='整稿画廊',exact=True).click()
            for pid in ['p01','p03']:page.locator('.gallery-card[data-page-id="'+pid+'"] input[type=checkbox]').check()
            page.get_by_role('button',name='用选页开始风格校准',exact=True).click()
            expect(page.get_by_label('风格目标 '+titles['p03'],exact=True)).to_be_checked();expect(page.get_by_label('风格目标 '+titles['p02'],exact=True)).not_to_be_checked();check('gallery_selection_seeds_reference_and_explicit_targets')
            page.get_by_role('button',name='整稿画廊',exact=True).click();page.locator('.gallery-card[data-page-id="p02"] .gallery-open').click()
            page.get_by_role('button',name='以本页为风格参考',exact=True).click();expect(page.locator('.style-reference')).to_contain_text(titles['p02']);check('page_reference_entry_keeps_fixed_identity')
            check('no_browser_errors',not errors)
            context.close();browser.close()
    finally:server.stop()
    (args.out/'checks.json').write_text(json.dumps({'synthetic':True,'actual_model_calls':0,'checks':checks,'errors':errors},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
