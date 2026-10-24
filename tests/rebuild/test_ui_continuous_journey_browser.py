"""Five plan tasks on one real project, with explicit synthetic Host returns.

UI creation, editing and candidate decisions use actual HTTP. Preparation grants
and scripted content returns are L1 fixture actions, never professional review
or image generation evidence. The final ZIP is an actual fixed-version download.
"""
import copy
import hashlib
import json
import re
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import changes, eligibility, exports, local_runtime, tasks
from deck_master.store import Store
from deck_master.eligibility import EligibilityBlocked
from rc3_fixtures import settle_fidelity_review
from test_action_targets_browser import _prepare_browser_project
from test_content_candidates import accept, dispatch_content_trial, page_envelope, start_task
from test_rc3_studio_control_browser import manuscript_page
from test_workbench_services import launcher_service  # noqa: F401

pytestmark = pytest.mark.browser


def test_same_project_create_material_edit_handoff_candidate_and_fixed_export(launcher_service, tmp_path):
    _, _, launcher = launcher_service
    project = tmp_path/'continuous-project'
    source = tmp_path/'manuscript.json'
    source.write_text(json.dumps({'pages': [manuscript_page('p01', '先核对范围'),
                                          manuscript_page('p02', '再确定行动')]}))
    supplement = tmp_path/'supplement.md'
    supplement.write_text('# 合成补充材料\n先核对范围，再确定行动；原稿事实保持。')
    original_sources = [source.read_bytes(), supplement.read_bytes()]
    evidence = tmp_path/'journey-evidence'; evidence.mkdir()
    steps, errors = [], []
    store = Store(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width':1440,'height':900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(launcher['url'])
            page.get_by_role('button', name='新建项目', exact=True).click()
            dialog = page.get_by_role('dialog', name='新建项目')
            dialog.get_by_label('确认稿 JSON 文件（可选）').set_input_files(source)
            expect(dialog).to_contain_text('先核对范围')
            for name, value in [('项目名称（必填）','连续任务验收'), ('用途（必填）','合成稿件的完整连续路径'),
                                ('受众（必填）','验证者'), ('保存到哪个文件夹（必填）',str(tmp_path)),
                                ('新项目文件夹名（必填）',project.name)]:
                dialog.get_by_label(name).fill(value)
            dialog.get_by_label('本次约定产物').select_option('full_deck')
            with page.expect_response('**/api/projects/create') as response:
                dialog.get_by_role('button', name='创建项目', exact=True).click()
            assert response.value.ok
            expect(page.get_by_label('本次工作状态')).to_be_visible()
            base = f'{urlsplit(page.url).scheme}://{urlsplit(page.url).netloc}/'
            identity = page.request.get(base+'api/project').json()['project_identity']

            def goto(surface, **extra):
                page.goto(base+'studio/#'+urlencode({'project':identity,'surface':surface,
                    'revision':store.current_revision_id(), **extra}))

            def record(step, **facts):
                doc = store.load_document()
                steps.append({'step':step,'project_id':doc['project_id'],'revision_id':doc['revision_id'],
                              'page_order':[entry['page_id'] for entry in doc['pages']], **facts})
                page.screenshot(path=str(evidence/f'{len(steps):02d}.png'), full_page=True)

            record('create', source='explicit manuscript', method='browser')
            _prepare_browser_project(project, max_candidate_count=2)
            goto('content')
            page.get_by_role('button', name='材料与要求', exact=True).click()
            page.get_by_role('button', name='添加材料', exact=True).click()
            page.get_by_label('新增材料完整路径（每行一个）', exact=True).fill(str(supplement))
            page.get_by_label('本次输入变化说明', exact=True).fill('加入同范围的合成核对依据，保留原稿。')
            page.get_by_role('button', name='预览材料与任务变化', exact=True).click()
            with page.expect_response('**/api/content/inputs') as response:
                page.get_by_role('button', name='确认输入并交接判断', exact=True).click()
            assert response.value.ok
            doc = store.load_document()
            task = next(store.read_object_json(ref) for ref in reversed(doc['tasks'])
                        if store.read_object_json(ref).get('intent') == 'input_revision')
            start_task(project, task)
            accept(project, task, {'kind':'compose','content_update':{
                'input_digest':task['input_digest'],'upsert_pages':[],'remove_page_ids':[],
                'page_order':['p01','p02'],'impact_summary':'合成补充材料不改变两页事实。',
                'unchanged_reason':'只增加核对依据，无需改写正文。'},
                'content_plan':copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])})
            goto('content')
            page.get_by_role('button', name='材料与来源', exact=True).click()
            expect(page.locator('.studio-material-card')).to_contain_text(supplement.name)
            record('add_material', host='scripted input reconciliation', method='browser and public Host API')

            page.get_by_role('button', name='逐页稿', exact=True).click()
            row = page.locator('.content-order-row').first
            row.get_by_role('button', name='第 1 页操作', exact=True).click()
            row.get_by_role('button', name=re.compile('^向后移动 ')).click()
            page.get_by_role('button', name='预览页序变更', exact=True).click()
            with page.expect_response('**/api/content/commit') as response:
                page.get_by_role('button', name='确认内容变更', exact=True).click()
            assert response.value.ok
            assert [entry['page_id'] for entry in store.load_document()['pages']] == ['p02','p01']
            expect(page).to_have_url(re.compile('revision='+store.current_revision_id()))
            goto('page', page='p01', layer='content')
            expect(page.get_by_role('region', name='页面内容')).to_contain_text('先核对范围')
            page.get_by_role('button', name='编辑本页标题与正文', exact=True).click()
            page.get_by_label('页面标题', exact=True).fill('先核对范围与依据')
            page.get_by_role('button', name='预览正文修改影响', exact=True).click()
            with page.expect_response('**/api/content/commit') as response:
                page.get_by_role('button', name='确认内容变更', exact=True).click()
            assert response.value.ok
            doc = store.load_document()
            expect(page).to_have_url(re.compile('revision='+doc['revision_id']))
            assert store.read_object_json(doc['pages'][1]['page'])['customer_visible']['title'] == '先核对范围与依据'
            assert store.read_object_json(doc['pages'][0]['page'])['customer_visible']['title'] == '再确定行动'
            record('reorder_and_edit', target='p01 now page 2', method='browser')

            # Editing invalidates the earlier manuscript review. Observe the
            # real refusal, then return a fresh explicitly scripted L1 review
            # through its real workorder; do not disable the production gate.
            # PR185 permits zero-call page-copy corrections so a failed review
            # can be repaired. Exercise the visual production gate instead.
            entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
            visual = {'schema_version':'change_intent.v1', 'project_id':doc['project_id'],
                'base_revision':doc['revision_id'], 'intent':'visual',
                'instruction':'L1 gate probe only; do not dispatch an image call',
                'annotation_refs':[], 'max_calls':1, 'mode':'trial',
                'targets':[{'page_id':'p01','page_ref':entry['page'],
                            'layer':'original_image','artifact_ref':entry.get('blueprint')}]}
            planned = changes.plan(project, input=visual)
            before_gate = store.load_document()
            with pytest.raises(EligibilityBlocked) as blocked:
                changes.commit(project, plan_id=planned['plan_id'],
                    base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
            assert 'preproduction_blocked' in blocked.value.decision['reason_codes']
            assert store.load_document() == before_gate
            settle_fidelity_review(project, page_ids=['p02','p01'],
                execution_ref='L1-continuous-after-edit',
                scenario='Synthetic current manuscript check; no professional acceptance')
            reviewed = store.load_document()
            decision = eligibility.evaluate(store, reviewed, reviewed, 'change.commit',
                context={'external_call_page_ids':['p01'], 'count':1, 'candidate_count':1,
                         'targets':{'page_ids':['p01'],'layers':['blueprint']}})
            assert 'preproduction_blocked' not in decision['reason_codes']
            assert not decision['allowed']  # Editorial authority still grants zero image calls.
            task = dispatch_content_trial(project, store, page='p01')
            goto('runs', task=task['task_id'])
            handoff = page.locator('.task-handoff')
            expect(handoff).to_be_visible()
            expect(handoff.get_by_role('button', name='复制交接说明', exact=True)).to_be_enabled()
            # A verified task refresh remounts the handoff asynchronously. An
            # enabled old button does not mean the replacement text has loaded.
            held_handoffs, holding_handoff = [], True
            def hold_handoff(route):
                if holding_handoff:
                    held_handoffs.append(route)
                    page.evaluate('window.pr188HeldHandoff = true')
                else:
                    route.continue_()
            page.route('**/api/changes/*/handoff', hold_handoff)
            try:
                page.locator('.run-detail').get_by_role('button', name='核实原任务', exact=True).click()
                expect(handoff.get_by_role('button', name='复制交接说明', exact=True)).to_be_disabled()
                assert handoff.get_by_label('本任务完整交接说明').input_value() == ''
                page.wait_for_function('window.pr188HeldHandoff === true', timeout=5000)
                assert held_handoffs
            finally:
                holding_handoff = False
                for route in held_handoffs:
                    route.fulfill(response=route.fetch())
                page.unroute('**/api/changes/*/handoff', hold_handoff)
            text = page.wait_for_function('''taskId => {
                const value = document.querySelector('.task-handoff textarea')?.value;
                return value?.includes(taskId) && value.includes('p01') ? value : false;
            }''', arg=task['task_id'], timeout=5000).json_value()
            assert task['task_id'] in text and 'p01' in text
            assert task['scope_pages'] == ['p01'] and not task.get('call_allowances')
            record('selected_page_handoff', task_id=task['task_id'], method='public trial API and browser handoff',
                   handoff_sha256=hashlib.sha256(text.encode()).hexdigest(), external_calls=0)
            before = copy.deepcopy(store.load_document()['pages'])
            start_task(project, task)
            result = accept(project, task, page_envelope(store, task, ' · 候选'))
            cid = result['candidate_ids'][0]
            assert store.load_document()['pages'] == before
            goto('page', page='p01', layer='content', candidate=cid)
            expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id',cid)
            page.get_by_role('button', name='保留当前', exact=True).click()
            expect(page.locator('.candidate-state')).to_contain_text('已保留当前')
            assert store.load_document()['pages'] == before
            page.reload()
            expect(page.locator('.candidate-state')).to_contain_text('已保留当前')
            page.get_by_role('button', name='重新打开候选', exact=True).click()
            page.get_by_role('button', name='预览采用这个候选', exact=True).click()
            with page.expect_response('**/api/candidates/adopt') as response:
                page.get_by_role('button', name='采用这个候选', exact=True).click()
            assert response.value.ok
            expect(page.locator('.candidate-state')).to_contain_text('当前采用')
            final = store.load_document()
            assert final['pages'][0] == before[0]
            assert store.read_object_json(final['pages'][1]['page'])['customer_visible']['title'].endswith(' · 候选')
            page.reload()
            expect(page.locator('.candidate-state')).to_contain_text('当前采用')
            expect(page.locator('.candidate-meta')).to_contain_text('当前稿采用的正文')
            expect(page.locator('.candidate-state')).not_to_contain_text('请按新依据重新试作')
            record('keep_reopen_adopt', candidate_id=cid, method='browser', returned_by='scripted content Host')

            frozen = store.current_revision_id()
            goto('runs')
            page.get_by_role('button', name='待决定', exact=True).click()
            expect(page.locator(f'.candidate-card[data-candidate-id="{cid}"] .status')).to_have_text('当前采用')
            page.get_by_role('button', name='文件', exact=True).click()
            page.get_by_role('button', name='查看此版本的交付缺项与制作证据', exact=True).click()
            dialog = page.get_by_role('dialog', name='此版本的交付缺项与制作证据')
            expect(dialog).to_contain_text('工程检查：')
            assert '未评估' in dialog.inner_text() or '未完成' in dialog.inner_text() or '未通过' in dialog.inner_text()
            dialog.get_by_role('button', name='关闭', exact=True).click()
            with page.expect_request('**/api/exports') as request:
                page.get_by_role('button', name='生成审阅包', exact=True).click()
            assert request.value.post_data_json['revision'] == frozen
            with page.expect_download() as download:
                page.get_by_role('link', name='下载 ZIP', exact=True).click()
            data = Path(download.value.path()).read_bytes()
            packet = exports.show(project, export_id=request.value.post_data_json['export_id'])
            digest = hashlib.sha256(data).hexdigest()
            assert packet['files'][packet['archive']]['sha256'] == digest
            (evidence/'review.zip').write_bytes(data)
            with zipfile.ZipFile(evidence/'review.zip') as bundle:
                name = next(name for name in bundle.namelist() if name.endswith('manifest.json'))
                manifest = json.loads(bundle.read(name))
                assert manifest['revision_id'] == frozen
            assert store.current_revision_id() == frozen
            record('fixed_version_check_and_export', export_revision=frozen, archive_sha256=digest,
                   purpose='review', professional_acceptance=False, method='browser download')
            assert [source.read_bytes(), supplement.read_bytes()] == original_sources
            assert len({step['project_id'] for step in steps}) == 1 and not errors
        finally:
            (evidence/'trace.json').write_text(json.dumps({'steps':steps,'errors':errors,'model_calls':0},
                                                        ensure_ascii=False,indent=2)+'\n')
            (evidence/'last-ui.txt').write_text(page.locator('body').inner_text())
            browser.close()
            if project.exists():local_runtime.stop(local_runtime.descriptor(project=project))
