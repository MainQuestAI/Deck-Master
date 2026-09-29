"""W09 structural Host handoff and recovery edges; simulated Host, zero model calls."""
from __future__ import annotations
import argparse
import copy
import json
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master import service, content_ops
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def simulated_result(store, task, action):
    doc=store.load_document();entries={p['page_id']:p for p in doc['pages']};ids=task['scope_pages'];outline=copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])
    upserts=[];removed=[]
    if action=='rewrite':
        for pid in ids:
            p=copy.deepcopy(store.read_object_json(entries[pid]['page']));p['customer_visible']['title']+=' Rewritten';upserts.append(p)
        order=list(entries)
    else:
        removed=ids
        for i in range(1 if action=='merge' else 2):
            p=copy.deepcopy(store.read_object_json(entries[ids[0]]['page']));p['page_id']=action+'-new-'+str(i);p['customer_visible']['title']='Synthetic '+action+' '+str(i);upserts.append(p)
        source=next(g for g in outline['goals'] if g['page_id']==ids[0]);outline['goals']=[g for g in outline['goals'] if g['page_id'] not in ids]
        outline['goals'] += [{**copy.deepcopy(source),'goal_id':'goal-'+p['page_id'],'page_id':p['page_id']} for p in upserts]
        outline['chapters']=[{'chapter_id':'derived','title':'Synthetic derivation','goal_ids':[g['goal_id'] for g in outline['goals']]}]
        order=[pid for pid in entries if pid not in ids]+[p['page_id'] for p in upserts]
    return {'kind':'compose','content_update':{'input_digest':task['input_digest'],'upsert_pages':upserts,'remove_page_ids':removed,'page_order':order,'impact_summary':'Explicitly simulated selected-page structural editing; unselected page untouched.'},'content_plan':outline}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    project=args.out/'project';create_sample(project,page_count=3,readonly=False);store=Store(project);checks=[];errors=[];posts=[]
    original=copy.deepcopy(store.load_document());server=WorkbenchServer(project);url=server.start()
    def check(name,value=True):assert value,name;checks.append(name);print(name,flush=True)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:posts.append(r.post_data_json) if r.method=='POST' and '/api/content/commit' in r.url else None)
            def current():
                identity=page.request.get(url+'api/project').json()['project_identity']
                page.goto(url+'v2/#project='+identity+'&surface=content&revision='+store.current_revision_id())
                expect(page.locator('.topbar .version')).to_contain_text(store.current_revision_id()[:8])
            try:
                page.goto(url+'v2/');page.get_by_role('button',name='内容与来源',exact=True).click()
                for action,ids,label in [('merge',['p01','p02'],'合并'),('split',['merge-new-0'],'拆分'),('rewrite',['split-new-0','split-new-1'],'选页改写')]:
                    current();before=copy.deepcopy(store.load_document()['pages'])
                    for pid in ids:page.locator('.content-order-row[data-page-id="'+pid+'"] input').check()
                    page.get_by_label('选页调整要求').fill('Synthetic '+action+' for explicit selected pages only')
                    page.get_by_role('button',name='预览'+('合并选页' if action=='merge' else '拆分选页' if action=='split' else label),exact=True).click();expect(page.get_by_role('button',name='确认并交接内容调整',exact=True)).to_be_enabled();page.get_by_role('button',name='确认并交接内容调整',exact=True).click()
                    expect(page.get_by_role('heading',name='当前任务',exact=True)).to_be_visible();task=store.read_object_json(store.load_document()['tasks'][-1]);check(action+'_explicit_scope_and_no_early_body_write',task['scope_pages']==ids and store.load_document()['pages']==before)
                    service.task_start(project,task_id=task['task_id'],execution_ref='synthetic-w09-browser-host',supported_protocols=['compose.v1'],capabilities=task['required_capabilities'])
                    result=simulated_result(store,task,action);service.accept_result(project,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],result_payload=result)
                    check(action+'_unselected_page_retained',next(p for p in store.load_document()['pages'] if p['page_id']=='p03')==original['pages'][2])
                    if action=='merge':
                        current();page.get_by_role('button',name='打开内容页 Synthetic merge 0',exact=True).click();page.get_by_text('编辑本页标题与正文',exact=True).click();expect(page.get_by_text('本页由合并或拆分产生。旧页意见仍留在旧身份，不会自动迁移到这里。',exact=True)).to_be_visible()
                        page.get_by_role('button',name='查看来源页关系',exact=True).click();page.get_by_role('button',name='打开来源页 p01',exact=True).click();expect(page.get_by_text('历史版本 · 只读',exact=True)).to_be_visible();expect(page.get_by_text('编辑本页标题与正文',exact=True)).to_have_count(0);check('derivation_navigates_immutable_readonly_source')
                current();page.get_by_text('调整任务要求与材料',exact=True).click();page.get_by_label('汇报受众',exact=True).fill('第一次保存的受众');page.get_by_label('本次输入变化说明').fill('明确汇报对象')
                page.get_by_role('button',name='预览材料与任务变化',exact=True).click();expect(page.get_by_role('button',name='确认输入并交接判断',exact=True)).to_be_enabled()
                def drop(route):route.fetch();route.abort('failed')
                page.route('**/api/content/inputs',drop,times=1);page.get_by_role('button',name='确认输入并交接判断',exact=True).click();expect(page.get_by_role('button',name='核实保存结果',exact=True)).to_be_enabled()
                page.get_by_label('汇报受众',exact=True).fill('保存未知后继续写的受众');count=len(store.load_document()['tasks']);page.reload();expect(page.get_by_role('button',name='核实保存结果',exact=True)).to_be_enabled();page.get_by_role('button',name='核实保存结果',exact=True).click();expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停',exact=True)).not_to_be_visible()
                check('input_unknown_recovery_survives_refresh',store.load_document()['task']['audience']=='第一次保存的受众' and len(store.load_document()['tasks'])==count)
                # The stale read stays read-only; newer draft text remains in its own recovery copy.
                page.get_by_text('编辑内容计划',exact=True).click();check('historical_inputs_cannot_write',page.get_by_role('button',name='确认输入并交接判断',exact=True).count()==0)
                current();page.get_by_text('调整任务要求与材料',exact=True).click();expect(page.get_by_label('汇报受众',exact=True)).to_have_value('第一次保存的受众');check('new_input_version_not_shadowed_by_old_draft')
                source=args.out/'locator-material.md';source.write_text('Synthetic source.\nOnly a validation note; no slide facts changed.\n')
                content_ops.inputs(project,input={'reason':'Synthetic exact locator fixture','source_changes':{'add':[{'path':str(source.resolve())}]}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
                task=store.read_object_json(store.load_document()['tasks'][-1]);service.task_start(project,task_id=task['task_id'],execution_ref='synthetic-source-host',supported_protocols=['compose.v1'],capabilities=task['required_capabilities'])
                source_record=store.load_document()['sources'][-1];outline=copy.deepcopy(store.read_object_json(store.load_document()['content_plan'])['input']);outline['goals'][0]['source_links']=[{'source_id':source_record['source_id'],'source_version':{'original_sha256':source_record['original_sha256'],'extract':source_record['extract']},'locator':'L2'}]
                service.accept_result(project,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],result_payload={'kind':'compose','content_update':{'input_digest':task['input_digest'],'upsert_pages':[],'remove_page_ids':[],'page_order':[p['page_id'] for p in store.load_document()['pages']],'unchanged_reason':'Synthetic note L2 adds no page facts; all existing claims retained.'},'content_plan':outline})
                current();expect(page.get_by_text('已采用的 Host 影响判断',exact=True)).to_be_visible();expect(page.get_by_text('Synthetic note L2 adds no page facts; all existing claims retained.',exact=True)).to_be_visible();check('host_unchanged_reason_visible_without_reinventing_it')
                page.get_by_text('编辑内容计划',exact=True).click();page.get_by_role('button',name='查看目标来源 L2',exact=True).click();expect(page.get_by_text('已定位：L2',exact=True)).to_be_visible();expect(page.locator('#modal .read-text').first).to_have_text('Only a validation note; no slide facts changed.');page.locator('#modal').get_by_role('button',name='关闭',exact=True).click();check('source_navigation_exact_version_locator')
                # A different current edit invalidates the already-previewed request, preserving both copies.
                page.get_by_role('button',name='打开内容页 每页保留原图与来源',exact=True).click();page.get_by_text('编辑本页标题与正文',exact=True).click();expect(page.get_by_label('页面标题',exact=True)).to_be_enabled();page.get_by_label('页面标题',exact=True).fill('Local conflicting edit');page.get_by_role('button',name='预览正文修改影响',exact=True).click();expect(page.get_by_role('button',name='确认内容变更',exact=True)).to_be_enabled()
                doc=store.load_document();entry=next(p for p in doc['pages'] if p['page_id']=='p03');visible=copy.deepcopy(store.read_object_json(entry['page'])['customer_visible']);visible['title']='Concurrent server content'
                planned=content_ops.plan(project,input={'schema_version':'content_operation_input.v1','project_id':doc['project_id'],'base_revision':doc['revision_id'],'content_plan_ref':doc['content_plan'],'action':'edit','targets':[{'page_id':'p03','page_ref':entry['page']}],'instruction':'Synthetic concurrent edit','customer_visible':visible})
                content_ops.commit(project,plan_id=planned['plan_id'],base_revision=doc['revision_id'],operation_id=str(uuid.uuid4()))
                page.get_by_role('button',name='确认内容变更',exact=True).click();expect(page.get_by_role('heading',name='本次未提交，输入已保留',exact=True)).to_be_visible();check('stale_plan_refused_and_draft_preserved',store.read_object_json(next(e for e in store.load_document()['pages'] if e['page_id']=='p03')['page'])['customer_visible']['title']=='Concurrent server content')
                page.screenshot(path=str(args.out/'conflict.png'),full_page=True);check('no_browser_errors',not errors)
            except Exception:
                page.screenshot(path=str(args.out/'failure.png'),full_page=True);(args.out/'failure.txt').write_text(page.locator('body').inner_text());raise
            finally:context.close();browser.close()
    finally:server.stop()
    (args.out/'checks.json').write_text(json.dumps({'synthetic':True,'actual_model_calls':0,'checks':checks,'errors':errors},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
