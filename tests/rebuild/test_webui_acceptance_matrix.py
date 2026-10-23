"""Post-PR127 engineering matrix; explicit synthetic fixtures, no approval claims."""
import copy
import json
import shutil
from pathlib import Path
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright, expect
from deck_master import models, ui_journal, method_resources
from deck_master import content_insight as ui, method_library_view as library
from deck_master.web import WorkbenchServer
from test_webui_content_insight import candidate, bytes_at, reviewed_project


def commit_fixture(store, transform, operation='matrix-fixture'):
    old=store.load_document();new=models.bump_revision(old,{'operation_id':operation,'kind':'task_update','description':'explicit synthetic matrix fixture','read_set':[]})
    transform(new)
    store.commit_change(base_revision=old['revision_id'],document=new,operation_id=operation)
    return new


def save_draft(project,store,*,text='旧版本备注',context='method-preparation',extra=None,identity='draft-matrix',revision=None,page_ref=None):
    info=ui_journal.project_info(project)
    value={'schema_version':'ui_draft.v1','project_id':info['project_id'],'project_identity':info['project_identity'],'draft_id':identity,
        'target':{'scope':'page' if page_ref else 'project','page_id':'p1' if page_ref else None,'layer':'notes'},
        'base_revision':revision or store.current_revision_id(),'base_ref':page_ref,'content':{'text':text,'context_key':context,**(extra or {})},'pending':None}
    return ui_journal.save(project,draft=value)['record']


@pytest.fixture
def resource_root(tmp_path,monkeypatch):
    root=tmp_path/'resources';shutil.copytree(method_resources.resolve_root(),root)
    monkeypatch.setattr(method_resources,'resolve_root',lambda:root)
    return root


@pytest.mark.parametrize('damage',['missing','utf8'])
def test_selected_resource_damage_is_partial_not_whole_preview_failure(tmp_path,resource_root,damage):
    project,store,_,_=candidate(tmp_path);_,rows,_=library.catalog()
    mid='case-e04-walkthrough';path=resource_root/rows[mid]['relative_path']
    if damage=='missing':path.unlink()
    else:path.write_bytes(b'\xff\xfe')
    before=bytes_at(project)
    value=library.preview(project,{'context':{'mode':'independent','role':'deck-content','phase':'argument','review_units':[]},'selected_resource_ids':['content-m04',mid]})
    assert value['browse_status']=='partial' and value['explicit_ids']==['content-m04',mid]
    assert not value['handoff']['copy_allowed'] and value['selection_status']=='not_evaluated'
    assert 'content-m04' in [r['id'] for r in value['resolved_manifest']]
    broken=next(r for r in value['entries'] if r['id']==mid)
    assert broken['sha256'] is None and broken['reason_codes'] and not broken['selectable']
    models.validate_schema('ui_method_preview',value)
    assert bytes_at(project)==before


@pytest.mark.browser
def test_method_cross_revision_restore_revalidates_ids_and_keeps_note(tmp_path):
    project,store,_,_=candidate(tmp_path);info=ui_journal.project_info(project);old=store.current_revision_id()
    saved=save_draft(project,store,extra={'method_preparation':{'ids':['content-m04'],'context':{'mode':'independent','role':'deck-content','phase':'argument','review_units':[]}}})
    commit_fixture(store,lambda doc:None);before=store.load_document()
    server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'revision':store.current_revision_id(),'surface':'content','content_area':'methods','layer':'content'}))
            page.get_by_text('保存与恢复个人准备稿',exact=True).click()
            page.get_by_label('恢复项目中的个人草稿',exact=True).select_option(saved['draft']['draft_id'])
            expect(page.get_by_label('方法准备备注')).to_have_value('旧版本备注')
            expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            expect(page.locator('label.method-entry').filter(has_text='M04').locator('input')).to_be_checked()
            page.get_by_role('button',name='对当前版本写新意见',exact=True).click()
            page.get_by_role('button',name='保存方法准备稿',exact=True).click()
            expect(page.locator('.method-draft-state')).to_contain_text('已保存到项目')
            records=ui_journal.list_drafts(project)['records'];new=next(r['draft'] for r in records if r['draft']['base_revision']!=old)
            assert new['content']['method_preparation']['ids']==['content-m04'] and new['content']['context_key']=='method-preparation'
            assert store.load_document()==before
            browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_reassessment_uses_new_effective_decision_identity(tmp_path):
    from deck_master import collaboration
    from test_compose_v2_phases import _instruction
    from test_webui_content_insight_browser import _open_direction
    project,store,_,ref=candidate(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            _open_direction(page,url,info,store,ref)
            d1ref=store.load_document()['collaboration']['decisions'][0];d1=store.read_object_json(d1ref)
            base={k:d1[k] for k in ['topic','subject_refs','scope','value','authority_mode']};base['instruction_evidence']=_instruction(store,'replace-rejected-decision')
            collaboration.record_decision(project,input={**base,'decision_id':d1['decision_id'],'replaces':d1ref,'disposition':'rejected'},base_revision=store.current_revision_id(),operation_id='reject-d1')
            d2=collaboration.record_decision(project,input={**base,'decision_id':'new-effective-identity','disposition':'accepted'},base_revision=store.current_revision_id(),operation_id='accept-d2')['decision_ref']
            admission=ui.argument(project,ref['sha256'])['data']['adoption'];assert admission['can_adopt'] and admission['existing_decision_ref']==d2
            page.reload();page.get_by_role('button',name='核实或查看原方向操作',exact=True).click()
            page.get_by_role('button',name='明确读取当前准入以另建采用请求',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('已读取当前准入')
            with page.expect_request('**/collaboration/proposal-adoptions') as request:
                page.get_by_role('button',name='确认采用此方向',exact=True).click()
            assert request.value.post_data_json['decision_ref']==d2
            expect(page.get_by_role('dialog')).to_contain_text('方向已采用')
            browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_review_single_click_waits_for_blur_save_and_enters_exact_editor(tmp_path):
    import time
    project,store,ref=reviewed_project(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project);before=store.load_document();writes=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':store.current_revision_id(),'layer':'content','review':'reading-review','review_sha256':ref['sha256'],'finding':'f1','finding_index':0}))
            page.get_by_role('button',name='准备范围交接草稿',exact=True).click()
            expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            def delayed(route):
                writes.append(route.request.post_data_json);response=route.fetch();time.sleep(.3);route.fulfill(response=response)
            page.route('**/api/drafts/save',delayed)
            page.get_by_label('审阅交接备注').fill('最后一次输入：保留范围与限定')
            page.get_by_role('button',name='保存草稿后进入原正文编辑',exact=True).click()
            expect(page.get_by_label('正文修改说明',exact=True)).to_have_value('最后一次输入：保留范围与限定')
            assert len(writes)==1 and writes[0]['draft']['content']['text']=='最后一次输入：保留范围与限定'
            assert store.load_document()==before
            browser.close()
    finally:server.stop()


def test_unreachable_cross_project_and_old_snapshot_reject_disk_objects(tmp_path):
    from test_compose_v2_phases import _project,_request,_accept_argument
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    project,store=_project(a);_request(project,store,content_intent='plan_only');old=store.current_revision_id();task,result=_accept_argument(project,store);ref=result['result_refs'][0]
    foreign,other=_project(b)
    copied=other.put_json_object(store.read_object_json(ref));assert copied==ref
    with pytest.raises(ui.InsightError):ui.argument(foreign,ref['sha256'])
    with pytest.raises(ui.InsightError):ui.argument(project,ref['sha256'],revision=old)
    with pytest.raises(ui.InsightError):ui.task_methods(project,task['task_id'],revision=old)
    rev_project,rev_store,review_ref=reviewed_project(tmp_path/'review')
    store.put_json_object(rev_store.read_object_json(review_ref))
    with pytest.raises(ui.InsightError):ui.review_reading(project,'reading-review',review_sha256=review_ref['sha256'])
    from deck_master.snapshots import ReadModelError
    with pytest.raises(ReadModelError):ui.arguments(project,revision=other.current_revision_id())
    # A stored but arbitrary task input is never indexed as an output.
    actual=store.read_object_json(store.load_document()['tasks'][0]);n=store.read_object_json(ref);n['narrative_id']='input-only';hidden=store.put_json_object(n);actual['inputs'].append(hidden)
    commit_fixture(store,lambda doc:doc.update(tasks=[store.put_json_object(actual)]),'input-only-fixture')
    with pytest.raises(ui.InsightError):ui.argument(project,hidden['sha256'])


def test_pagination_remains_fixed_when_current_changes(tmp_path):
    from test_compose_v2_phases import _accept_argument
    project,store,_,ref=candidate(tmp_path)
    for i in range(2):_accept_argument(project,store)
    revision=store.current_revision_id();all_rows=ui.arguments(project,revision=revision)['data']['items'];assert all_rows
    # Distinct current pointer grows the new index; original paging stays fixed.
    n=store.read_object_json(ref);n['narrative_id']='later-current';newref=store.put_json_object(n)
    commit_fixture(store,lambda doc:doc.update(narrative=newref),'new-current')
    collected=[]
    for offset in range(len(all_rows)):
        page=ui.arguments(project,revision=revision,offset=offset,limit=1)
        assert page['revision_id']==revision;collected+=page['data']['items']
    assert collected==all_rows and newref not in [r['ref'] for r in collected]
    assert newref in [r['ref'] for r in ui.arguments(project)['data']['items']]


@pytest.mark.parametrize('old_manifest',[False,True])
def test_task_methods_old_manifest_and_current_drift_are_separate(tmp_path,resource_root,old_manifest):
    project,store,task,_=candidate(tmp_path);doc=store.load_document();task_ref=next(r for r in doc['tasks'] if store.read_object_json(r)['task_id']==task['task_id']);task=store.read_object_json(task_ref)
    expected=copy.deepcopy(task['method_manifest'])
    if old_manifest:
        task.pop('method_manifest');task.pop('method_release',None)
        commit_fixture(store,lambda d:d.update(tasks=[store.put_json_object(task)]),'old-task')
    else:
        (resource_root/expected[0]['relative_path']).unlink()
        (resource_root/expected[1]['relative_path']).write_text('changed',encoding='utf8')
    before=bytes_at(project);value=ui.task_methods(project,task['task_id'],availability='current')['data']
    assert value['frozen_status']==('not_recorded' if old_manifest else 'recorded')
    if old_manifest:assert value['resources']==[] and value['frozen_release'] is None
    else:
        assert [{k:r[k] for k in ('id','relative_path','sha256')} for r in value['resources']]==expected
        assert all(r['display_name'] is None and r['semantic_kind'] is None for r in value['resources'])
        assert {r['reason'] for r in value['availability']['issues']}=={'missing','hash_mismatch'}
        assert ui.task_methods(project,task['task_id'])['data']['availability'] is None
    assert bytes_at(project)==before


@pytest.mark.parametrize('intent',['write_only','speech_only'])
def test_fixed_content_intents_never_reopen_direction(tmp_path,intent):
    project,store,_,ref=candidate(tmp_path)
    commit_fixture(store,lambda doc:doc['collaboration']['request'].update(content_intent=intent),'fixed-intent')
    before=bytes_at(project);a=ui.argument(project,ref['sha256'])['data']['adoption']
    assert not a['can_adopt'] and not a['can_record_direction_decision'] and a['adoption_reason_codes']==['fixed_content_intent']
    assert bytes_at(project)==before


@pytest.mark.parametrize('version',['v1','v2'])
@pytest.mark.parametrize('status',['needs_review','not_evaluated','not_applicable'])
def test_review_versions_preserve_all_states_and_scope(tmp_path,version,status):
    project,store,ref=reviewed_project(tmp_path);r=store.read_object_json(ref);r['schema_version']='deck_review.'+version;r['status']=status
    if version=='v2':r['reviewer'].update(evidence_ref=None,assurance='unverified')
    r['findings']=[{**r['findings'][0],'finding_id':'f'+str(i),'impact':impact,'resolution':resolution}
        for i,(impact,resolution) in enumerate([('must_fix','open'),('needs_judgment','accepted_variance'),('advisory','not_applicable'),('advisory','fixed')])]
    models.validate_schema('review',r);newref=store.put_json_object(r)
    commit_fixture(store,lambda d:d.update(reviews=[newref]),'review-states')
    before=bytes_at(project);value=ui.review_reading(project,'reading-review')['data'];assert value['review']['data']==r
    assert [t['source_index'] for t in value['targets']]==list(range(4))
    assert bytes_at(project)==before
    commit_fixture(store,lambda d:d['collaboration']['request'].update(intent='review_only'),'review-only')
    assert not any(t['repair_allowed'] for t in ui.review_reading(project,'reading-review')['data']['targets'])


def test_review_deck_and_changed_subjects_do_not_guess_locations(tmp_path):
    project,store,ref=reviewed_project(tmp_path);review=store.read_object_json(ref)
    review['findings'].append({**review['findings'][0],'finding_id':'deck','page_id':None,'element_refs':[]})
    changed=store.read_object_json(store.load_document()['pages'][0]['page']);changed['customer_visible']['body_blocks'][0]['text']='新版不能冒充原句';newref=store.put_json_object(changed)
    def change(doc):doc['reviews']=[store.put_json_object(review)];doc['pages'][0]['page']=newref
    commit_fixture(store,change,'review-stale-target')
    targets=ui.review_reading(project,'reading-review')['data']['targets']
    assert targets[0]['locator_status']=='page_only'
    assert targets[-1]['page_ref'] is None and targets[-1]['locator_status']=='unavailable'
    with pytest.raises(ui.InsightError):ui.evidence(project,'p1',element_ref='atom:missing')


def test_requirements_uses_unique_frozen_task_or_explicit_derived_fallback(tmp_path):
    from test_rc3_design_workflows import project as make,confirmed,dispatch
    from deck_master.production import stored_blueprint_request
    project,store,_=make(tmp_path);recipe=confirmed(project,store);task=dispatch(project,store,recipe,['p1'])[0]
    frozen,_=stored_blueprint_request(store,task);before=bytes_at(project)
    value=ui.requirements(project,'p1')['data'];assert value['origin']=='frozen_task' and value['producer_task_id']==task['task_id']
    assert value['content_requirements']==frozen['resolved_design_context']['content_requirements'];assert bytes_at(project)==before
    duplicate=copy.deepcopy(task);duplicate['task_id']='another-frozen-task';duplicate['operation_id']='another-task-op'
    commit_fixture(store,lambda d:d['tasks'].append(store.put_json_object(duplicate)),'two-frozen-tasks')
    before=bytes_at(project);value=ui.requirements(project,'p1');assert value['status']=='partial'
    assert value['data']['origin']=='derived_from_snapshot' and value['data']['producer_task_id'] is None
    assert any(i['code']=='insight_requirements_multiple_tasks' for i in value['issues']);assert bytes_at(project)==before


@pytest.mark.parametrize('role,phase,chosen',[('deck-content','argument',['content-m04','case-e04-walkthrough']),('deck-review','review',['method-review']),('deck-design','production',['blueprint-svg'])])
def test_method_role_phase_revalidation_and_body_limits(tmp_path,resource_root,role,phase,chosen):
    project,store,_,_=candidate(tmp_path);request={'context':{'mode':'independent','role':role,'phase':phase,'review_units':['argument'] if role=='deck-review' else []},'selected_resource_ids':chosen}
    value=library.preview(project,request);assert value['selection_status']=='validated'
    row=value['resolved_manifest'][-1];path=resource_root/row['relative_path'];path.write_bytes(b'x'*(1024*1024+1))
    with pytest.raises(ui.InsightError) as large:library.resource(row['id'],catalog_digest=value['catalog_digest'],sha256=row['sha256'])
    assert large.value.http_status==413
    (resource_root/'resource-catalog.json').write_text('{broken')
    with pytest.raises(ui.InsightError) as broken:library.preview(project,request)
    assert broken.value.http_status==503


def recovery_file(tmp_path,draft,name):
    path=tmp_path/name;path.write_text(json.dumps({'schema_version':'ui_draft_recovery.v1','draft':draft,'digest':ui_journal.digest(draft)},ensure_ascii=False));return path


@pytest.mark.browser
def test_review_restore_project_local_import_and_context_isolation(tmp_path):
    project,store,ref=reviewed_project(tmp_path);info=ui_journal.project_info(project);page_ref=store.load_document()['pages'][0]['page'];rev=store.current_revision_id()
    def context(fid,index):return f"review:{ref['sha256']}:{fid}:{index}"
    def note(fid,index,text,identity):
        return save_draft(project,store,text=text,context=context(fid,index),identity=identity,page_ref=page_ref,extra={'review_handoff':{'review_ref':ref,'revision':rev,'finding_id':fid,'source_index':index,'page_ref':page_ref,'element_refs':[],'repair_layer':'content'}})
    one=note('f1',0,'f1 版本甲','draft-one');two=note('f1',0,'f1 版本乙','draft-two');other=note('f2',1,'f2 不得串入','draft-other')
    imported=recovery_file(tmp_path,other['draft'],'other.json');server=WorkbenchServer(project);url=server.start();before=store.load_document()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            def open_finding(fid,index):
                page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':rev,'layer':'content','review':'reading-review','review_sha256':ref['sha256'],'finding':fid,'finding_index':index}))
                page.get_by_role('button',name='准备范围交接草稿',exact=True).click()
            open_finding('f1',0)
            expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            select=page.get_by_label('恢复项目中的个人草稿',exact=True)
            select.select_option(one['draft']['draft_id'])
            if page.get_by_role('button',name='打开所选草稿',exact=True).count():page.get_by_role('button',name='打开所选草稿',exact=True).click()
            expect(page.get_by_label('审阅交接备注')).to_have_value('f1 版本甲')
            select.select_option(two['draft']['draft_id']);expect(page.get_by_label('审阅交接备注')).to_have_value('f1 版本乙')
            # Importing another context is allowed into the journal, never into f1.
            with page.expect_response('**/api/drafts/import'):page.get_by_label('导入草稿恢复文件',exact=True).set_input_files(imported)
            expect(page.get_by_label('审阅交接备注')).to_have_value('f1 版本乙')
            assert 'f2 不得串入' not in select.inner_text()
            # A local same-context copy can be explicitly restored.
            local=page.get_by_label('恢复本机保留的草稿副本',exact=True)
            options=local.locator('option').evaluate_all('(xs)=>xs.map(x=>({value:x.value,text:x.textContent}))')
            local.select_option(next(x['value'] for x in options if x['text']=='f1 版本甲'))
            expect(page.get_by_label('审阅交接备注')).to_have_value('f1 版本甲')
            # Poison only the current active buffer to exercise its identity guard.
            page.evaluate("other=>{for(const key of Object.keys(localStorage)){if(key.includes(':context:review:')&&key.includes(':f1:0:window:')){const x=JSON.parse(localStorage.getItem(key));x.draft=other;localStorage.setItem(key,JSON.stringify(x));}}}",other['draft'])
            page.reload();page.get_by_role('button',name='准备范围交接草稿',exact=True).click()
            expect(page.get_by_label('审阅交接备注')).not_to_have_value('f2 不得串入')
            page.keyboard.press('Escape');open_finding('f2',1)
            expect(page.get_by_label('审阅交接备注')).to_have_value('f2 不得串入')
            assert store.load_document()==before
            browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_method_and_plain_notes_import_do_not_claim_each_other(tmp_path):
    project,store,_,_=candidate(tmp_path);info=ui_journal.project_info(project)
    method=save_draft(project,store,text='方法备注',extra={'method_preparation':{'ids':['content-m04'],'context':{'mode':'independent','role':'deck-content','phase':'argument','review_units':[]}}})
    plain=save_draft(project,store,text='普通笔记',context=None,identity='draft-plain')
    method_file=recovery_file(tmp_path,method['draft'],'method.json');plain_file=recovery_file(tmp_path,plain['draft'],'plain.json')
    before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            # A small real module host mounts the ordinary notes editor with its
            # real API and recovery behavior, without conflating outline notes.
            page.goto(url+'studio/')
            expect(page.get_by_role('heading',name='内容与页序',exact=True)).to_be_visible()
            page.evaluate("""async info=>{const {DraftEditor}=await import('/v2/drafts.js');const d=new DraftEditor(info,{scope:'project',page_id:null,layer:'notes'},info.revision_id,null,{exactRevision:true});d.onRestore=c=>d.restoreInPlace(c);document.querySelector('main').replaceChildren(d.mount());await d.ready;}""",{**info,'revision_id':store.current_revision_id()})
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('普通笔记')
            with page.expect_response('**/api/drafts/import'):page.get_by_label('导入草稿恢复文件',exact=True).set_input_files(method_file)
            expect(page.get_by_label('个人草稿',exact=True)).to_have_value('普通笔记')
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'revision':store.current_revision_id(),'surface':'content','content_area':'methods','layer':'content'}))
            page.get_by_text('保存与恢复个人准备稿',exact=True).click()
            expect(page.get_by_label('方法准备备注')).to_have_value('方法备注')
            with page.expect_response('**/api/drafts/import'):page.locator('#content-area-methods').get_by_label('导入草稿恢复文件',exact=True).set_input_files(plain_file)
            expect(page.get_by_label('方法准备备注')).to_have_value('方法备注')
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_method_saved_ids_partial_resources_and_copy_drift(tmp_path,resource_root):
    project,store,_,_=candidate(tmp_path);info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copies=(window.copies||[]).concat(text)}}})")
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'revision':store.current_revision_id(),'surface':'content','content_area':'methods','layer':'content'}))
            page.get_by_label('准备上下文').select_option('independent');expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.locator('label.method-entry').filter(has_text='content-m04 ·').locator('input').check()
            expect(page.get_by_role('button',name='阅读 content-m04',exact=True)).to_be_visible()
            page.get_by_role('button',name='重新核对后复制准备要求',exact=True).click();expect(page.get_by_text('已复制，尚未开始。请在制作工具中发送。',exact=True)).to_be_visible()
            assert len(page.evaluate('window.copies'))==1
            _,rows,_=library.catalog();path=resource_root/rows['content-m04']['relative_path'];original=path.read_bytes();path.write_bytes(original+b'\nchanged')
            page.get_by_role('button',name='重新核对后复制准备要求',exact=True).click()
            expect(page.locator('#content-area-methods')).to_contain_text('资源字节已变化')
            assert len(page.evaluate('window.copies'))==1
            page.get_by_role('button',name='重新核对准备',exact=True).click();expect(page.get_by_role('button',name='阅读 content-m04',exact=True)).to_be_visible()
            path.unlink();page.get_by_role('button',name='重新核对准备',exact=True).click();expect(page.locator('#content-area-methods')).to_contain_text('部分资源暂不可读')
            expect(page.get_by_role('button',name='重新核对后复制准备要求',exact=True)).to_be_disabled()
            expect(page.locator('label.method-entry').filter(has_text='content-m04 ·').locator('input')).to_be_checked()
            path.write_bytes(original);page.reload();expect(page.get_by_role('button',name='阅读 content-m04',exact=True)).to_be_visible()
            expect(page.locator('label.method-entry').filter(has_text='M04').locator('input')).to_be_checked()
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_review_forward_copy_preserves_context_but_drops_old_handoff(tmp_path):
    project,store,ref=reviewed_project(tmp_path);info=ui_journal.project_info(project);old=store.current_revision_id();page_ref=store.load_document()['pages'][0]['page'];context=f"review:{ref['sha256']}:f1:0"
    saved=save_draft(project,store,text='仅复制这段意见',context=context,page_ref=page_ref,extra={'review_handoff':{'review_ref':ref,'revision':old,'page_ref':page_ref,'scope':'old-scope'}})
    commit_fixture(store,lambda d:None,'new-review-reading');current=store.current_revision_id();before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':current,'layer':'content','review':'reading-review','review_sha256':ref['sha256'],'finding':'f1','finding_index':0}))
            page.get_by_role('button',name='准备范围交接草稿',exact=True).click();expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            page.get_by_label('恢复项目中的个人草稿',exact=True).select_option(saved['draft']['draft_id'])
            expect(page.get_by_label('审阅交接备注')).to_have_value('仅复制这段意见')
            page.get_by_role('button',name='对当前版本写新意见',exact=True).click()
            page.get_by_role('dialog').get_by_role('button',name='保存个人草稿',exact=True).click();expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            value=next(r['draft'] for r in ui_journal.list_drafts(project)['records'] if r['draft']['base_revision']==current and r['draft']['content']['text']=='仅复制这段意见')
            assert value['content']['context_key']==context and 'review_handoff' not in value['content']
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('intent',['write_only','speech_only'])
def test_narrative_text_alternatives_xss_and_fixed_intent_in_browser(tmp_path,intent):
    project,store,_,ref=candidate(tmp_path);n=store.read_object_json(ref);attack='<img src=x onerror="window.bad=1">'
    n['nodes'][0]['statement']=attack+' 原话必须当文本';n['issues']=[{'issue_id':'i1','question':'条件不足，待核实','impact':'needs_judgment','affected_node_ids':['n1'],'resolution':'open','resolution_ref':None}]
    n['alternatives']=[{'option_id':'a1','description':'方案 A','benefit':'少改动','cost':'保留约束','affected_node_ids':['n1']}]
    models.validate_narrative_semantics(n);nref=store.put_json_object(n)
    def modify(doc):doc['narrative']=nref;doc['collaboration']['request']['content_intent']=intent
    commit_fixture(store,modify,'fixed-xss');info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':store.current_revision_id(),'layer':'content','content_area':'arguments','proposal':nref['sha256']}))
            expect(page.locator('.argument-reading h3')).to_contain_text(attack)
            expect(page.locator('.argument-reading')).to_contain_text('方案 A');expect(page.locator('.argument-reading')).to_contain_text('条件不足，待核实')
            assert page.locator('.argument-reading img').count()==0 and page.evaluate('window.bad') is None
            expect(page.get_by_role('button',name='记录方向决定',exact=True)).to_have_count(0)
            expect(page.get_by_role('button',name='核对并采用此方向',exact=True)).to_have_count(0)
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_late_argument_response_cannot_replace_new_selection(tmp_path):
    from playwright.sync_api import Error
    project,store,_,ref=candidate(tmp_path);n=store.read_object_json(ref);n['nodes'][0]['statement']='新选择的真实主线';n['narrative_id']='new-selected';newref=store.put_json_object(n)
    commit_fixture(store,lambda d:d.update(narrative=newref),'late-response');info=ui_journal.project_info(project);server=WorkbenchServer(project);url=server.start();held=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            def hold(route):held.append((route,route.fetch()))
            page.route('**/api/content/arguments/'+ref['sha256']+'?*',hold)
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':store.current_revision_id(),'layer':'content','content_area':'arguments','proposal':ref['sha256']}))
            expect(page.get_by_role('button',name='阅读当前主线',exact=True)).to_be_visible();assert held
            page.get_by_role('button',name='阅读当前主线',exact=True).click();expect(page.locator('.argument-reading h3')).to_have_text('新选择的真实主线')
            for route,response in held:
                try:route.fulfill(response=response)
                except Error:pass  # Aborted by the disposed reader is also correct.
            expect(page.locator('.argument-reading h3')).to_have_text('新选择的真实主线');expect(page.locator('.argument-reading')).to_have_count(1)
            browser.close()
    finally:server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('old',[False,True])
def test_task_method_ui_old_record_and_damage_do_not_dispatch(tmp_path,resource_root,old):
    project,store,task,_=candidate(tmp_path);doc=store.load_document();row=next(store.read_object_json(r) for r in doc['tasks'] if store.read_object_json(r)['task_id']==task['task_id'])
    if old:
        row.pop('method_manifest',None);row.pop('method_release',None)
        commit_fixture(store,lambda d:d.update(tasks=[store.put_json_object(row)]),'old-method-ui')
    else:
        manifest=row['method_manifest'];(resource_root/manifest[0]['relative_path']).unlink();(resource_root/manifest[1]['relative_path']).write_text('drift')
    before=store.load_document();info=ui_journal.project_info(project);server=WorkbenchServer(project);url=server.start();posts=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':store.current_revision_id(),'layer':'content','task':task['task_id']}))
            expect(page.get_by_role('heading',name='任务方法依据',exact=True)).to_be_visible()
            if old:expect(page.get_by_text('旧任务未记录冻结清单，不套用当前默认方法。',exact=True)).to_be_visible()
            else:
                page.get_by_text('当前安装可用性',exact=True).click();expect(page.locator('.insight-reading')).to_contain_text('hash_mismatch');expect(page.locator('.insight-reading')).to_contain_text('missing')
                page.get_by_text('派发时的版本与字节',exact=True).click();expect(page.locator('.insight-reading')).to_contain_text(manifest[0]['sha256'])
            assert not any(any(x in p for x in ['/continue','/claim','/cancel','/allocate','/begin']) for p in posts)
            assert store.load_document()==before;browser.close()
    finally:server.stop()


def mapped_project(tmp_path):
    from test_rc3_design_requirements import _snapshot
    store,doc,_=_snapshot(tmp_path)
    # The resolver fixture contains paragraph, table cells, labels and qualifiers.
    models.require_writer(doc,'rc3.v1');store.init_project(doc,operation_id='mapped-matrix')
    return store.project_root,store


@pytest.mark.browser
def test_table_atom_keyboard_selection_qualifiers_and_missing_mapping(tmp_path):
    project,store=mapped_project(tmp_path);info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844})
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p1','revision':store.current_revision_id(),'layer':'content'}))
            expect(page.get_by_role('heading',name='正文与证据',exact=True)).to_be_visible()
            card=page.locator('.insight-node').filter(has=page.locator('p.read-text',has_text='12')).first
            expect(card).to_contain_text('仅比较指定记录，不外推节约率。')
            text=card.locator('p.read-text');text.evaluate("n=>{const r=document.createRange();r.selectNodeContents(n);getSelection().removeAllRanges();getSelection().addRange(r)}")
            assert page.evaluate('getSelection().toString()')=='12'
            control=card.get_by_role('button',name='定位这段正文',exact=True);control.focus();page.keyboard.press('Enter')
            expect(page.locator('.insight-node')).to_have_count(1);assert 'atom=' in page.url
            back=page.get_by_role('button',name='查看本页全部原子',exact=True);back.focus();page.keyboard.press('Enter')
            expect(page.locator('.insight-node').filter(has_text='12')).to_have_count(1)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and store.load_document()==before
            browser.close()
    finally:server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('failure',['none','commit_ack','stale','scope'])
def test_review_handoff_real_plan_commit_and_failure_recovery(tmp_path,failure):
    from test_studio_content_browser import authorize_content_edits
    project,store,review_ref=reviewed_project(tmp_path)
    if failure!='scope':authorize_content_edits(project)
    info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start();plans=[];commits=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':store.current_revision_id(),'layer':'content','review':'reading-review','review_sha256':review_ref['sha256'],'finding':'f1','finding_index':0}))
            page.get_by_role('button',name='准备范围交接草稿',exact=True).click();expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            page.get_by_role('button',name='保存草稿后进入原正文编辑',exact=True).click()
            page.get_by_text('编辑本页标题与正文',exact=True).click()
            expect(page.get_by_label('正文修改说明',exact=True)).to_have_value('补充限定条件\n预期：说明适用范围\n实际：未说明')
            page.get_by_label('页面标题',exact=True).fill('补充了限定条件的标题')
            expect(page.locator('.draft-state')).to_contain_text('已保存到项目')
            def plan_request(route):
                plans.append(route.request.post_data_json)
                if failure=='stale':commit_fixture(store,lambda d:None,'concurrent-review-edit')
                route.continue_()
            page.route('**/api/content/plan',plan_request)
            with page.expect_response('**/api/content/plan') as response:page.get_by_role('button',name='预览正文修改影响',exact=True).click()
            assert plans[0]['input']['targets']==[{'page_id':'p1','page_ref':before['pages'][0]['page']}]
            if failure=='stale':
                assert not response.value.ok
                expect(page.get_by_label('页面标题',exact=True)).to_have_value('补充了限定条件的标题')
                assert store.load_document()['pages']==before['pages'] and store.load_document()['reviews']==before['reviews']
            else:
                assert response.value.ok
                def commit_request(route):
                    commits.append(route.request.post_data_json)
                    if failure=='commit_ack':
                        result=route.fetch();assert result.ok;route.abort('failed')
                    else:route.continue_()
                page.route('**/api/content/commit',commit_request)
                if failure=='scope':
                    with page.expect_response('**/api/content/commit') as commit_response:
                        page.get_by_role('button',name='确认内容变更',exact=True).click()
                else:page.get_by_role('button',name='确认内容变更',exact=True).click()
                if failure=='scope':
                    assert not commit_response.value.ok
                    assert store.load_document()['pages']==before['pages']
                    assert store.load_document()['reviews']==before['reviews']
                    expect(page.get_by_label('页面标题',exact=True)).to_have_value('补充了限定条件的标题')
                    assert len(commits)==1 and commits[0]['operation_id']
                    browser.close();return
                if failure=='commit_ack':
                    expect(page.get_by_role('button',name='核实保存结果',exact=True)).to_be_enabled()
                    page.reload();page.get_by_role('button',name='核实保存结果',exact=True).click()
                    expect(page.locator('.business-pending')).to_be_hidden()
                else:expect(page.get_by_role('heading',name='补充了限定条件的标题',exact=True)).to_be_visible()
                assert len(commits)==1
                after=store.load_document();assert after['pages'][0]['page']!=before['pages'][0]['page']
                assert after['reviews']==before['reviews'] and after['tasks']==before['tasks']
                assert store.read_object_json(review_ref)['findings'][0]['resolution']=='open'
            records=ui_journal.list_drafts(project)['records']
            handoffs=[r['draft']['content']['review_handoff'] for r in records if 'review_handoff' in r['draft']['content']]
            assert handoffs and all(h['review_ref']==review_ref and h['finding_id']=='f1' for h in handoffs)
            browser.close()
    finally:server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('kind,repair_layer',[('speech','speech'),('blueprint_content','design'),('content','source')])
def test_review_layer_boundaries_are_not_body_edit_shortcuts(tmp_path,kind,repair_layer):
    project,store,ref=reviewed_project(tmp_path);review=store.read_object_json(ref);review['schema_version']='deck_review.v2';review['reviewer'].update(evidence_ref=None,assurance='unverified');review['kind']=kind
    if repair_layer=='source':review['findings'][0]['kind']='source'
    ref=store.put_json_object(review);commit_fixture(store,lambda d:d.update(reviews=[ref]),'layer-review');before=store.load_document();info=ui_journal.project_info(project);server=WorkbenchServer(project);url=server.start()
    assert ui.review_reading(project,'reading-review')['data']['targets'][0]['repair_layer']==repair_layer
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':store.current_revision_id(),'layer':'content','review':'reading-review','review_sha256':ref['sha256'],'finding':'f1','finding_index':0}))
            page.get_by_role('button',name='准备范围交接草稿',exact=True).click();expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            expect(page.get_by_role('button',name='保存草稿后进入原正文编辑',exact=True)).to_have_count(0)
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('status',['needs_review','not_evaluated','not_applicable'])
def test_review_v2_states_and_deck_location_are_honest_in_browser(tmp_path,status):
    project,store,ref=reviewed_project(tmp_path);review=store.read_object_json(ref);review['schema_version']='deck_review.v2';review['reviewer'].update(evidence_ref=None,assurance='unverified');review['status']=status
    review['findings'][0]['page_id']=None;review['findings'][0]['element_refs']=[];review['findings'][0]['impact']='needs_judgment';review['findings'][0]['resolution']='not_applicable'
    ref=store.put_json_object(review);commit_fixture(store,lambda d:d.update(reviews=[ref]),'deck-review');info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':store.current_revision_id(),'layer':'content','review':'reading-review','review_sha256':ref['sha256'],'finding':'f1','finding_index':0}))
            expect(page.get_by_text({'needs_review':'待审阅','not_evaluated':'未评估','not_applicable':'不适用'}[status],exact=True)).to_be_visible()
            expect(page.locator('.insight-finding')).to_contain_text('needs_judgment');expect(page.locator('.insight-finding')).to_contain_text('解决记录：不适用')
            expect(page.get_by_role('button',name='定位原页面文字',exact=True)).to_have_count(0)
            assert store.load_document()==before;browser.close()
    finally:server.stop()


def keyboard_to(page,locator):
    for _ in range(220):
        if locator.count()==1 and locator.evaluate('(n)=>n===document.activeElement'):return
        page.keyboard.press('Tab')
    raise AssertionError('Keyboard target was unreachable: '+str(locator))


@pytest.mark.browser
@pytest.mark.parametrize('viewport',[(1280,800),(1440,900),(390,844)])
def test_insight_primary_paths_keyboard_focus_and_long_content(tmp_path,viewport):
    project,store,_,ref=candidate(tmp_path);review_project,review_store,review_ref=reviewed_project(tmp_path/'review');info=ui_journal.project_info(project);rinfo=ui_journal.project_info(review_project)
    first=WorkbenchServer(project);second=WorkbenchServer(review_project);url=first.start();rurl=second.start();before=store.load_document();rbefore=review_store.load_document()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':viewport[0],'height':viewport[1]})
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':store.current_revision_id(),'layer':'content','content_area':'arguments','proposal':ref['sha256']}))
            control=page.get_by_role('button',name='记录方向决定',exact=True);expect(control).to_be_visible();keyboard_to(page,control);page.keyboard.press('Enter');expect(page.get_by_role('dialog')).to_be_visible();page.keyboard.press('Escape');expect(control).to_be_focused()
            nav=page.get_by_role('button',name='方法与案例',exact=True);keyboard_to(page,nav);page.keyboard.press('Enter')
            mode=page.get_by_label('准备上下文');keyboard_to(page,mode);page.keyboard.press('ArrowDown');page.keyboard.press('Enter');expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            search=page.get_by_label('筛选方法或案例');keyboard_to(page,search);page.keyboard.type('content-m04')
            check=page.locator('label.method-entry').filter(has_text='content-m04 ·').locator('input');keyboard_to(page,check);page.keyboard.press('Space')
            read=page.get_by_role('button',name='阅读 content-m04',exact=True);expect(read).to_be_visible();keyboard_to(page,read);page.keyboard.press('Enter');expect(page.locator('#content-area-methods > section > pre')).to_be_focused()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.goto(rurl+'studio/#'+urlencode({'project':rinfo['project_identity'],'surface':'runs','revision':review_store.current_revision_id(),'layer':'content','review':'reading-review','review_sha256':review_ref['sha256'],'finding':'f1','finding_index':0}))
            locate=page.get_by_role('button',name='定位原页面文字',exact=True);expect(locate).to_be_visible();keyboard_to(page,locate);page.keyboard.press('Enter')
            back=page.get_by_role('button',name='返回原审阅问题',exact=True);expect(back).to_be_visible();keyboard_to(page,back);page.keyboard.press('Enter')
            draft=page.get_by_role('button',name='准备范围交接草稿',exact=True);expect(draft).to_be_visible();keyboard_to(page,draft);page.keyboard.press('Enter');expect(page.get_by_role('dialog')).to_be_visible();page.keyboard.press('Escape');expect(draft).to_be_focused()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert store.load_document()==before and review_store.load_document()==rbefore
            browser.close()
    finally:first.stop();second.stop()


@pytest.mark.browser
def test_method_role_stage_change_and_catalog_drift_recheck(tmp_path,resource_root):
    project,store,_,_=candidate(tmp_path);info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copies=(window.copies||[]).concat(text)}}})")
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':store.current_revision_id(),'layer':'content','content_area':'methods'}))
            page.get_by_label('准备上下文').select_option('independent');expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.locator('label.method-entry').filter(has_text='content-m04 ·').locator('input').check();expect(page.get_by_role('button',name='阅读 content-m04',exact=True)).to_be_visible()
            page.get_by_label('方法阅读阶段').select_option('page_copy');expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.get_by_label('方法阅读角色').select_option('deck-review');expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.get_by_label('方法阅读阶段').select_option('review');expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            path=resource_root/'resource-catalog.json';path.write_bytes(path.read_bytes()+b'\n')
            page.get_by_role('button',name='重新核对后复制准备要求',exact=True).click();expect(page.locator('#content-area-methods')).to_contain_text('Preparation basis changed')
            assert page.evaluate('window.copies||[]')==[]
            page.get_by_role('button',name='重新核对准备',exact=True).click();expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.get_by_role('button',name='重新核对后复制准备要求',exact=True).click();expect(page.get_by_text('已复制，尚未开始。请在制作工具中发送。',exact=True)).to_be_visible()
            assert len(page.evaluate('window.copies'))==1 and store.load_document()==before;browser.close()
    finally:server.stop()


from test_generation_protocol import flow  # noqa: E402,F401 — synthetic external-call ledger fixture


@pytest.mark.browser
def test_unknown_call_reading_never_allocates_retries_or_dispatches(flow):
    from test_generation_protocol import start,freeze,begin,settle
    from deck_master import generation
    project,store,task,_=flow;start(flow);frozen=freeze(flow);attempt=begin(flow,frozen);settle(flow,attempt,outcome='unknown')
    before=store.load_document();info=ui_journal.project_info(project);server=WorkbenchServer(project);url=server.start();writes=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.on('request',lambda r:writes.append(r.url) if r.method=='POST' and '/api/method-library/preview' not in r.url and '/api/ui-state' not in r.url else None)
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':store.current_revision_id(),'layer':'content','content_area':'methods'}))
            expect(page.get_by_label('准备上下文')).to_be_visible();page.get_by_label('准备上下文').select_option('independent')
            expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.get_by_role('button',name='阅读 source-reading',exact=True).click();expect(page.locator('#content-area-methods > section > pre')).not_to_be_empty()
            assert not writes and store.load_document()==before
            assert generation.show(project,attempt_id=attempt['attempt_id'])['call']['state']=='unknown'
            browser.close()
    finally:server.stop()


def test_method_all_example_variants_and_script_are_data_only(tmp_path):
    project,store,_,_=candidate(tmp_path);before=bytes_at(project);root,rows,_=library.catalog()
    ids=[i for i,r in rows.items() if ('E04' in r['relative_path'] or 'e04' in r['relative_path']) and r['readable']]
    assert len(ids)>=5
    ids.append('helper-case-numbers')
    value=library.preview(project,{'context':{'mode':'independent','role':'deck-content','phase':'argument','review_units':[]},'selected_resource_ids':ids})
    for row in value['resolved_manifest']:
        body=library.resource(row['id'],catalog_digest=value['catalog_digest'],sha256=row['sha256'])
        assert body['content']==(root/row['relative_path']).read_text() and body['preparation_only']
    assert any(rows[i]['kind']=='script' for i in ids)
    assert bytes_at(project)==before


def test_project_method_revision_drift_blocks_old_basis_without_dispatch(tmp_path):
    from test_compose_v2_phases import _project,_request
    project,store=_project(tmp_path);_request(project,store,content_intent='plan_only');revision=store.current_revision_id()
    request={'context':{'mode':'project','revision':revision},'selected_resource_ids':['content-m04']}
    value=library.preview(project,request);commit_fixture(store,lambda d:None,'advance-control');before=bytes_at(project)
    with pytest.raises(ui.InsightError) as error:
        library.preview(project,{**request,'expected_basis':{k:value[k] for k in ['catalog_digest','context_digest']}})
    assert error.value.http_status==409
    fresh=library.preview(project,request)
    assert fresh['explicit_ids']==['content-m04'] and fresh['preparation_only'] and fresh['dispatch_status']=='cannot_dispatch'
    assert 'historical_revision' in fresh['reason_codes'] and not fresh['handoff']['copy_allowed']
    assert bytes_at(project)==before


@pytest.mark.browser
def test_neutral_purpose_keeps_user_input_intent_and_speech_policy(tmp_path):
    project,store,_,_=candidate(tmp_path);info=ui_journal.project_info(project);before=store.load_document();server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'content','revision':store.current_revision_id(),'layer':'content'}))
            page.get_by_role('button',name='修改任务要求',exact=True).click()
            field=page.get_by_label('用途与目标',exact=True);expect(field).not_to_have_value('')
            field.fill('教学、研究与工程评审：不要求商业CTA，保留原口播规则')
            page.get_by_role('button',name='关闭编辑并保留草稿',exact=True).click()
            page.get_by_role('button',name='修改任务要求',exact=True).click();expect(field).to_have_value('教学、研究与工程评审：不要求商业CTA，保留原口播规则')
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_imported_page_missing_mapping_and_invalid_atom_remains_readable(tmp_path):
    project,store,_=reviewed_project(tmp_path)
    manuscript=store.read_object_json(store.load_document()['pages'][0]['page']);manuscript.pop('content_mapping',None)
    ref=store.put_json_object(manuscript)
    commit_fixture(store,lambda d:d['pages'][0].update(page=ref),'old-unmapped-page')
    before=store.load_document();info=ui_journal.project_info(project);server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            route={'project':info['project_identity'],'surface':'page','page':'p1','revision':store.current_revision_id(),'layer':'content'}
            page.goto(url+'studio/#'+urlencode(route));expect(page.get_by_text('此页未记录原子映射，仍可通过页面来源阅读。',exact=True)).to_be_visible()
            expect(page.locator('.insight-node').filter(has_text='明确未知')).to_contain_text('未记录映射')
            page.goto(url+'studio/#'+urlencode({**route,'atom':'atom:p1:invalid'}));expect(page.get_by_role('heading',name='合成教学稿',exact=True)).to_be_visible()
            expect(page.get_by_role('alert').filter(has_text='Text atom is unavailable')).to_be_visible()
            assert store.load_document()==before;browser.close()
    finally:server.stop()


@pytest.mark.browser
def test_long_semantics_and_bullet_atoms_survive_narrow_design_handoff(tmp_path):
    from deck_master.content import visible_atoms
    project,store=mapped_project(tmp_path);doc=store.load_document();manuscript=store.read_object_json(doc['pages'][0]['page'])
    text='保留条件、责任和核实步骤，不推断未提供的效率。'*80
    manuscript['customer_visible']['body_blocks'].append({'id':'steps','type':'bullets','items':[{'id':'verify','text':text}]})
    atom=next(a['atom_id'] for a in visible_atoms(manuscript) if a['text']==text)
    manuscript['content_mapping']['visible_links'].append({'element_ref':atom,'narrative_node_ids':['n1'],'source_links':[]})
    ref=store.put_json_object(manuscript);plan=store.read_object_json(doc['content_plan']);plan['page_links'][0]['page_ref']=ref
    plan_ref=store.put_json_object(plan)
    def update(d):d['pages'][0]['page']=ref;d['content_plan']=plan_ref
    commit_fixture(store,update,'long-bullet');before=store.load_document();info=ui_journal.project_info(project);server=WorkbenchServer(project);url=server.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844})
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p1','revision':store.current_revision_id(),'layer':'content','atom':atom}))
            expect(page.locator('.insight-node p.read-text')).to_have_text(text);expect(page.locator('.insight-node')).to_contain_text('仅比较指定记录，不外推节约率。')
            page.get_by_text('页面职责、限定条件与结构关系',exact=True).click()
            expect(page.get_by_text('保留正文与限定条件。空间不足时请返回内容流程提出修改，不会自动删减或启动生图。',exact=True)).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert store.load_document()==before and store.read_object_json(ref)['customer_visible']['body_blocks'][-1]['items'][0]['text']==text
            browser.close()
    finally:server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('second_result',['saved','unknown','conflict'])
def test_review_single_click_drains_old_and_latest_save(tmp_path,second_result):
    project,store,ref=reviewed_project(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project);before=store.load_document();held=[];writes=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project':info['project_identity'],'surface':'runs','revision':store.current_revision_id(),'layer':'content','review':'reading-review','review_sha256':ref['sha256'],'finding':'f1','finding_index':0}))
            page.get_by_role('button',name='准备范围交接草稿',exact=True).click();expect(page.locator('.review-draft-state')).to_contain_text('已保存到项目')
            def hold(route):
                payload=route.request.post_data_json;writes.append(payload)
                if len(writes)==2 and second_result=='conflict':
                    record=ui_journal.list_drafts(project)['records'][0];other=copy.deepcopy(record['draft']);other['content']['text']='另一窗口的明确修改'
                    ui_journal.save(project,draft=other,expected_etag=record['etag'])
                held.append((route,route.fetch()))
            page.route('**/api/drafts/save',hold)
            note=page.get_by_label('审阅交接备注');note.fill('P1：旧自动保存')
            expect(page.locator('.review-draft-state')).to_contain_text('正在保存到项目')
            # Pump the route handler without releasing its HTTP response.
            page.wait_for_timeout(100);assert len(held)==1
            note.fill('P2：最后文字与原范围')
            page.get_by_role('button',name='保存草稿后进入原正文编辑',exact=True).click()
            expect(page.get_by_role('dialog')).to_be_visible();assert len(writes)==1
            with page.expect_request('**/api/drafts/save'):
                held[0][0].fulfill(response=held[0][1])
            page.wait_for_timeout(100);assert len(held)==2
            expect(page.get_by_role('dialog')).to_be_visible()
            assert writes[1]['draft']['content']['text']=='P2：最后文字与原范围'
            if second_result=='unknown':held[1][0].abort()
            else:held[1][0].fulfill(response=held[1][1])
            if second_result=='saved':
                expect(page.get_by_label('正文修改说明',exact=True)).to_have_value('P2：最后文字与原范围')
            else:
                expect(page.locator('.review-draft-state')).to_contain_text('保存结果待核实' if second_result=='unknown' else '保存冲突')
                expect(page.get_by_role('dialog')).to_be_visible();expect(note).to_have_value('P2：最后文字与原范围')
                expect(page.get_by_label('正文修改说明',exact=True)).to_have_count(0)
            page.wait_for_timeout(700)
            assert len(writes)==2 and store.load_document()==before
            browser.close()
    finally:server.stop()


def test_method_speech_review_uses_existing_resolver_and_rejects_unknown_unit(tmp_path):
    project,store,_,_=candidate(tmp_path);before=bytes_at(project)
    ctx={'mode':'independent','role':'deck-review','phase':'review','review_units':['speech']}
    value=library.preview(project,{'context':ctx,'selected_resource_ids':[]})
    assert value['selection_status']=='validated' and value['preparation_only']
    assert value['default_ids']==['collaboration-routing',*method_resources.method_ids_for('review',review_units=['speech'])]
    explicit=library.preview(project,{'context':ctx,'selected_resource_ids':['writing-profiles']})
    assert explicit['explicit_ids']==['writing-profiles'] and explicit['selection_status']=='validated'
    assert bytes_at(project)==before
    with pytest.raises(ui.InsightError) as error:
        library.preview(project,{'context':{**ctx,'review_units':['invented-unit']},'selected_resource_ids':[]})
    assert error.value.http_status==400 and bytes_at(project)==before


@pytest.mark.browser
def test_explicit_reassessment_allows_new_decision_after_old_rejected_without_replacement(tmp_path):
    from deck_master import collaboration
    from test_compose_v2_phases import _instruction
    from test_webui_content_insight_browser import _open_direction
    project,store,_,ref=candidate(tmp_path);server=WorkbenchServer(project);url=server.start();info=ui_journal.project_info(project)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page()
            _open_direction(page,url,info,store,ref)
            d1ref=store.load_document()['collaboration']['decisions'][0];d1=store.read_object_json(d1ref)
            base={k:d1[k] for k in ['topic','subject_refs','scope','value','authority_mode']};base['instruction_evidence']=_instruction(store,'reject-without-d2')
            collaboration.record_decision(project,input={**base,'decision_id':d1['decision_id'],'replaces':d1ref,'disposition':'rejected'},base_revision=store.current_revision_id(),operation_id='reject-only-d1')
            a=ui.argument(project,ref['sha256'])['data']['adoption'];assert a['can_record_direction_decision'] and not a['can_adopt'] and a['existing_decision_ref'] is None
            before=store.load_document();page.reload();page.get_by_role('button',name='核实或查看原方向操作',exact=True).click()
            page.get_by_role('button',name='明确读取当前准入以另建采用请求',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('已读取当前准入')
            expect(page.get_by_label('确认这份方向的理由')).to_be_enabled();assert store.load_document()==before
            page.get_by_label('确认这份方向的理由').fill('明确重新记录，原拒绝历史保留')
            with page.expect_request('**/collaboration/decisions') as request:
                page.get_by_role('button',name='确认记录方向决定',exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('方向决定已记录，采用尚未完成')
            assert request.value.post_data_json['base_revision']==before['revision_id']
            expect(page.get_by_role('button',name='确认采用此方向',exact=True)).to_be_enabled()
            saved=page.evaluate('(key)=>JSON.parse(localStorage.getItem(key))',f"deck-master:direction:{info['project_identity']}:{ref['sha256']}")
            assert saved['previous_decisions'][0]['decision_ref']==d1ref and saved['decision']['decision_ref']!=d1ref
            page.get_by_role('button',name='确认采用此方向',exact=True).click();expect(page.get_by_role('dialog')).to_contain_text('方向已采用')
            browser.close()
    finally:server.stop()
