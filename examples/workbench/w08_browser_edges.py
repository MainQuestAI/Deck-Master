"""W08 recovery, original excerpts, conflicts and draft tests; synthetic Host only."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master.web import WorkbenchServer
from deck_master.models import bump_revision
from w08_style_transfer import SyntheticStyle


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    flow=SyntheticStyle(args.out);flow.image(flow.dispatch('p01',mode='auto'),1)
    doc=flow.store.load_document();titles={e['page_id']:flow.store.read_object_json(e['page'])['customer_visible']['title'] for e in doc['pages']}
    checks=[];errors=[];posts=[]
    def check(name,value=True):
        assert value,name
        checks.append(name);print(name,flush=True)
    server=WorkbenchServer(flow.project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append({'path':r.url.split('/api/')[-1],'body':r.post_data_json}) if r.method=='POST' and '/api/styles/' in r.url else None)
            page.goto(url+'v2/');page.get_by_role('button',name='风格校准',exact=True).click();expect(page.get_by_label('风格参考原图')).to_be_enabled()
            page.get_by_label('风格参考原图').select_option('p01')
            for pid in ['p02','p03']:page.get_by_label('风格目标 '+titles[pid],exact=True).check()
            page.get_by_label('风格短要求').fill('极简与高密度，请明确取舍。')
            page.get_by_text('高级：借用维度、原文选段与建议',exact=True).click()
            page.get_by_text('实际提交原文',exact=True).click();page.get_by_text('定位原文选段',exact=True).first.click()
            source=page.get_by_label('实际提交原文',exact=True);expect(source).to_be_visible()
            page.get_by_label('选段起点',exact=True).first.fill('0');page.get_by_label('选段终点',exact=True).first.fill('10');page.get_by_role('button',name='校验原文选段',exact=True).first.click()
            expect(page.get_by_text('仅借用已校验选段：',exact=True)).to_be_visible()
            page.get_by_role('button',name='检查风格要求',exact=True).click();expect(page.get_by_label(titles['p02']+' 密度取舍')).to_be_visible()
            confirm=page.get_by_role('button',name='确认这版风格要求',exact=True);expect(confirm).to_be_disabled()
            check('exact_prompt_excerpt_matches_source',posts[-1]['body']['input']['prompt_selection']['selection']['excerpt']==source.text_content()[:10])
            for pid in ['p02','p03']:page.get_by_label(titles[pid]+' 密度取舍').select_option('keep_target')
            page.get_by_role('button',name='检查风格要求',exact=True).click();expect(confirm).to_be_enabled();check('all_conflicts_explicit_before_confirmation')
            lost=[]
            def lose(route):
                response=route.fetch();lost.append(response.status);route.abort()
            page.route('**/api/styles/confirm',lose,times=1)
            confirm.click();expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停',exact=True)).to_be_visible()
            page.get_by_label('风格短要求').fill('确认回包丢失后继续写的新想法，不替换原请求。')
            page.get_by_role('button',name='保存个人草稿',exact=True).click()
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            page.reload();page.get_by_role('button',name='核实保存结果',exact=True).click();expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停',exact=True)).not_to_be_visible()
            check('unknown_confirmation_verified_once',lost==[200] and len(flow.store.load_document()['style_recipes'])==1 and len([p for p in posts if p['path']=='styles/confirm'])==1)
            expect(page.get_by_label('风格短要求')).to_have_value('确认回包丢失后继续写的新想法，不替换原请求。');check('later_draft_preserved_after_recovery')
            refresh=page.get_by_role('button',name='查看当前版本',exact=True)
            if refresh.is_visible():refresh.click();expect(refresh).not_to_be_visible()
            page.get_by_role('button',name='风格校准',exact=True).click()
            recipe=flow.store.read_object_json(flow.store.load_document()['style_recipes'][0]);expect(page.get_by_label('已确认的风格版本').locator('option')).to_have_count(2);page.get_by_label('已确认的风格版本').select_option(recipe['recipe_id'])
            page.get_by_label('先试哪一页').select_option('p03');page.get_by_role('button',name='预览单页试作',exact=True).click();dispatch=page.get_by_role('button',name='保存并交接风格试作',exact=True);expect(dispatch).to_be_enabled()
            doc=flow.store.load_document();changed=copy.deepcopy(doc);facts=flow.store.read_object_json(changed['pages'][2]['page']);facts['customer_visible']['title']+=' explicit fixture edit';changed['pages'][2]['page']=flow.store.put_json_object(facts)
            changed=bump_revision(changed,{'operation_id':'synthetic-style-conflict','kind':'task_update','description':'explicit test concurrent edit','read_set':[]});flow.store.commit_change(base_revision=doc['revision_id'],document=changed,operation_id='synthetic-style-conflict')
            before=copy.deepcopy(flow.store.load_document());dispatch.click();expect(page.get_by_role('dialog')).to_be_visible();check('stale_plan_dispatch_changes_nothing',flow.store.load_document()['pages']==before['pages'] and flow.store.load_document()['tasks']==before['tasks'])
            page.get_by_role('dialog').get_by_role('button',name='关闭',exact=True).click();expect(page.get_by_label('先试哪一页')).to_have_value('p03')
            page.get_by_role('button',name='预览单页试作',exact=True).click();expect(page.locator('.style-calibration .field-error').filter(has_text='风格要求或目标页基准已变化')).to_be_visible();check('per_target_conflict_displayed')
            page.get_by_label('先试哪一页').select_option('p02');page.get_by_role('button',name='预览单页试作',exact=True).click();expect(dispatch).to_be_enabled();check('unaffected_page_can_form_new_explicit_plan')
            page.get_by_role('button',name='保存个人草稿',exact=True).click();expect(page.locator('.draft-state')).to_contain_text('已保存到项目');page.reload()
            expect(page.get_by_label('已确认的风格版本')).to_have_value(recipe['recipe_id']);expect(page.get_by_label('先试哪一页')).to_have_value('p02');check('trial_scope_restores_without_dispatch')
            check('no_browser_errors',not errors);browser.close()
    finally:server.stop()
    (args.out/'checks.json').write_text(json.dumps({'synthetic':True,'actual_model_calls':0,'checks':checks,'errors':errors},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
