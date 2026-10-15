"""Production defaults and prototype task/file structure retain real snapshot operations."""
import io
import json
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest

from deck_master import service, tasks, run_desk
from deck_master.models import content_identity
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_actions import commit


def task_set(store):
    doc=store.load_document()
    for n in range(147):
        task=tasks.new_task(task_id=f'studio-task-{n:03}',operation_id=f'op-studio-task-{n:03}',
            kind='reconstruct' if n%2 else 'blueprint',scope_pages=[f'p0{n%3+1}'],
            instruction=f'准确保留第 {n+1} 项要求；核对数字与完整正文。',inputs=[],dependencies=[],
            dispatch_revision=doc['revision_id'],produced_against=content_identity(doc),status='completed')
        doc['tasks'].append(store.put_json_object(task))
    commit(store,doc,str(uuid.uuid4()))


def test_task_search_filters_before_pagination_and_fixed_revision(tmp_path):
    path=tmp_path/'project';create_sample(path,page_count=3,readonly=False);store=Store(path);task_set(store)
    frozen=store.current_revision_id();before=store.read_current()
    searched=run_desk.listing(path,revision=frozen,search='第 1 项',limit=30)
    assert [r['task_id'] for r in searched['tasks']]==['studio-task-000']
    assert searched['pagination']['total']==1
    title=store.read_object_json(store.load_document()['pages'][1]['page'])['customer_visible']['title']
    all_page2=run_desk.listing(path,revision=frozen,search=title,limit=100)
    assert len([r for r in all_page2['tasks'] if r['task_id'].startswith('studio-task-')])==49
    assert all(r['scope_pages']==['p02'] for r in all_page2['tasks'])
    service.inputs_update(path,patch={'reason':'after fixed task search','task_patch':{'audience':'新的阅读对象'}},base_revision=frozen,operation_id=str(uuid.uuid4()))
    assert run_desk.listing(path,revision=frozen,search='第 1 项')==searched
    assert store.read_current()!=before
    shown=run_desk.listing(path,search='after fixed task search')
    assert len(shown['tasks'])==1 and shown['tasks'][0]['kind']=='compose'
    with pytest.raises(run_desk.RunReadError):run_desk.listing(path,search='x'*201)


def test_task_list_summary_only_transforms_verified_system_templates(tmp_path):
    path=tmp_path/'project';create_sample(path,page_count=3,readonly=False);store=Store(path)
    reason='保留 API、Page v2 作为用户讨论的原文；\n第二行也必须保留'
    task=service._input_compose_task(store.load_document(),operation_id='input-exact-id',reason=reason)
    raw=task['instruction'];row=run_desk.task_row(task)
    assert row['display_instruction'].startswith(reason+' · ')
    assert 'operation input-exact-id' not in row['display_instruction']
    assert '核对新材料与全稿正文' in row['display_instruction']
    assert row['instruction']==raw and task['instruction']==raw
    trial=' 当前为显式 trial：除 content_update 外还须提交完整 content_plan_input；结果保存为候选，采用前不改动当前正文、页序或产物。'
    task['instruction']+=trial
    assert run_desk.task_row(task)['display_instruction'].endswith('先返回候选，采用前保持当前稿。')
    task['instruction']='输入已更新（operation 不同身份）：用户自由写作，content_update、Page v2 都是讨论内容。'
    assert run_desk.task_row(task)['display_instruction']==task['instruction']
    task['instruction']=raw+' 用户另外添加的完整说明'
    assert run_desk.task_row(task)['display_instruction']==task['instruction']
    task['instruction']='Please preserve this entire English request, including content_update and Page v2.'
    assert run_desk.task_row(task)['display_instruction']==task['instruction']
    # Verify the legacy system template from an explicit historical writer;
    # modern creation correctly opens a framing-only proposal instead.
    from rc3_fixtures import historical_snapshot
    old=Store(historical_snapshot(tmp_path,scenario='Stored legacy compose template reader')['project'])
    historical=old.load_document()
    initial=tasks.new_task(task_id='historical-initial',operation_id='initial-verified',kind='compose',
        intent='initial',scope_pages=[],inputs=[],dependencies=[],dispatch_revision=historical['revision_id'],
        produced_against=content_identity(historical),instruction=(
            'Read every source in Task.sources plus the method resources; derive the '
            "audience's open question and write complete visible copy as Page v2 with "
            'an explicit page order. Same source supports different framings; do not '
            'call a rule planner or fill pages from templates.'))
    historical['tasks']=[old.put_json_object(initial)]
    commit(old,historical,'record-historical-initial-task')
    initial_row=run_desk.task_row(initial)
    assert initial_row['display_instruction']=='阅读全部材料，围绕受众的问题组织完整正文与页面顺序。'
    assert initial_row['instruction'].startswith('Read every source in Task.sources')


def test_actual_modern_input_workorder_summary_preserves_user_reason_and_raw_text(tmp_path):
    path=tmp_path/'project';create_sample(path,page_count=2,readonly=False);store=Store(path)
    reason='用户原文 API、Page v2；保留这一句。\n第二行。'
    service.inputs_update(path,patch={'reason':reason,'task_patch':{'audience':'新的阅读对象'}},
        base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    task=next(store.read_object_json(ref) for ref in store.load_document()['tasks']
        if store.read_object_json(ref).get('intent')=='input_revision')
    original=task['instruction'];row=run_desk.task_row(task)
    assert row['display_instruction'].startswith(reason+' · ')
    assert 'operation ' not in row['display_instruction']
    assert 'compose.v2 input_revision' not in row['display_instruction']
    assert row['instruction']==original and task['instruction']==original
    task['instruction']+=' 用户另外添加的完整说明'
    assert run_desk.task_row(task)['display_instruction']==task['instruction']


@pytest.mark.browser
def test_studio_default_tasks_versions_and_actual_review_zip(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    path=tmp_path/'project';create_sample(path,page_count=3,readonly=False);store=Store(path)
    oldest=store.current_revision_id();task_set(store);reading=store.current_revision_id()
    service.inputs_update(path,patch={'reason':'create independent current revision','task_patch':{'audience':'正式工作台验收'}},base_revision=reading,operation_id=str(uuid.uuid4()))
    current=store.current_revision_id();assert len({oldest,reading,current})==3
    evidence=tmp_path/'evidence';evidence.mkdir(parents=True,exist_ok=True)
    server=WorkbenchServer(path);requests=[];errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:requests.append({'method':req.method,'url':req.url,'body':req.post_data}) if '/api/' in req.url else None)
        try:
            page.goto(server.start())
            expect(page.locator('html')).to_have_attribute('data-workbench-ui','studio')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            rows=page.locator('.studio-task-record');expect(rows).to_have_count(30)
            expect(page.get_by_role('button',name='查询任务',exact=True)).to_be_enabled()
            boxes=rows.first.evaluate("row=>['.studio-task-main','.studio-task-state','.run-task-open'].map(s=>{const b=row.querySelector(s).getBoundingClientRect();return {x:b.x,width:b.width}})")
            main,state,action=boxes
            assert main['x']+main['width']+12<=state['x'] and state['x']+state['width']+12<=action['x']
            expect(page.locator('.studio-task-table-head')).to_be_visible()
            expect(rows.first.locator('.run-requirement')).to_contain_text('create independent current revision')
            expect(rows.first.locator('.run-requirement')).not_to_contain_text('operation ')
            expect(rows.first.locator('.run-requirement')).not_to_contain_text('content_update')
            expect(rows.nth(1).locator('.run-requirement')).to_contain_text('准确保留第 147 项要求；核对数字与完整正文。')
            page.screenshot(path=str(evidence/'tasks-1440.png'),full_page=True)
            search=page.get_by_role('searchbox',name='搜索全部任务');search.fill('第 1 项');search.press('Enter')
            expect(rows).to_have_count(1);expect(rows.first).to_have_attribute('data-task-id','studio-task-000')
            expect(page.locator('.run-pagination')).to_be_hidden()
            expect(page.get_by_role('searchbox',name='搜索全部任务')).to_have_value('第 1 项')
            rows.first.get_by_role('button',name='查看这项任务').click()
            expect(page.locator('.run-detail')).to_contain_text('准确保留第 1 项要求')
            page.get_by_role('button',name='查看全部任务',exact=True).click()
            expect(page.get_by_role('heading',name='任务与交付',exact=True)).to_be_visible()
            expect(page.locator('.run-detail')).to_be_empty()
            page.get_by_role('button',name='版本',exact=True).click()
            choice=page.get_by_role('combobox',name='阅读历史版本')
            page.get_by_role('checkbox',name='显示全部历史记录').check()
            expect(page.locator('.studio-history-desk')).to_contain_text('已显示全部类型的记录')
            expect(choice.locator(f'option[value="{reading}"]')).to_have_count(1)
            choice.select_option(reading)
            expect(page.get_by_role('button',name='预览恢复此版本',exact=True)).to_be_disabled()
            expect(page.locator('.history-identity')).to_contain_text('所选版本与正在阅读的版本不同')
            page.get_by_role('button',name='读取所选版本',exact=True).click()
            expect(page.locator('.studio-version-reading-heading')).to_contain_text(reading[:8])
            choice=page.get_by_role('combobox',name='阅读历史版本');choice.select_option(oldest)
            expect(page.get_by_role('button',name='预览恢复此版本',exact=True)).to_be_disabled()
            expect(page.locator('.history-identity')).to_contain_text('选中：')
            expect(page.locator('.history-identity')).to_contain_text('已读：')
            expect(page.locator('.history-identity')).to_contain_text('当前版本：')
            page.screenshot(path=str(evidence/'versions-1440.png'),full_page=True)
            choice.select_option(reading);page.get_by_role('button',name='预览恢复此版本',exact=True).click()
            dialog=page.get_by_role('dialog');expect(dialog).to_contain_text(reading[:8]);expect(dialog).to_contain_text(current[:8])
            dialog.get_by_role('button',name='取消恢复',exact=True).click();assert store.current_revision_id()==current
            page.get_by_role('button',name='查看此版本文件',exact=True).click()
            expect(page.locator('.studio-files-version')).to_be_visible()
            expect(page.get_by_role('button',name='文件',exact=True)).to_have_attribute('aria-pressed','true')
            expect(page.locator('.studio-files-version')).to_contain_text(reading[:8])
            expect(page.locator('.studio-file-page')).to_have_count(3)
            page.screenshot(path=str(evidence/'files-1440.png'),full_page=True)
            with page.expect_request('**/api/exports') as call:
                page.get_by_role('button',name='生成审阅包',exact=True).click()
            assert call.value.post_data_json['revision']==reading
            link=page.get_by_role('link',name='下载 ZIP',exact=True);expect(link).to_be_visible()
            with page.expect_download() as download:link.click()
            archive=download.value.path();data=Path(archive).read_bytes();(evidence/'review.zip').write_bytes(data)
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                manifests=[name for name in bundle.namelist() if name.endswith('manifest.json')]
                assert manifests
                manifest=json.loads(bundle.read(manifests[0]));assert manifest['revision_id']==reading
            assert store.current_revision_id()==current
            page.set_viewport_size({'width':390,'height':844})
            for area in ['文件','版本','正在进行']:
                page.get_by_role('button',name=area,exact=True).click()
                expect(page.get_by_role('button',name=area,exact=True)).to_have_attribute('aria-pressed','true')
                expect(page.locator({'文件':'.studio-files-version','版本':'.studio-version-reading','正在进行':'.run-filters'}[area])).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                page.screenshot(path=str(evidence/f'{area}-390.png'),full_page=True)
            assert errors==[]
            (evidence/'requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2))
            (evidence/'identities.json').write_text(json.dumps({'A_selected':oldest,'B_reading_exported':reading,'C_current':current,'after':store.current_revision_id(),'errors':errors},indent=2))
        finally:
            (evidence/'last-requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2))
            (evidence/'last-ui.txt').write_text(page.locator('body').inner_text())
            page.screenshot(path=str(evidence/'last-ui.png'),full_page=True)
            browser.close();server.stop()
