"""Complete-repair counterexamples over real components and isolated local services."""
import uuid
import json
from pathlib import Path
from contextlib import contextmanager

import pytest

from deck_master import tasks
from deck_master.models import content_identity
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_styles import Flow, confirm, dispatch
from test_visual_styles import image_bytes
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


@contextmanager
def browser_for(project):
    from playwright.sync_api import sync_playwright
    server = WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        evidence = Path('output/playwright/pr103-complete') / project.parent.name
        evidence.mkdir(parents=True, exist_ok=True)
        page.evidence = evidence
        requests = []
        page.on('request', lambda r: requests.append({'method': r.method, 'url': r.url, 'body': r.post_data if 'json' in r.headers.get('content-type', '') else None}) if '/api/' in r.url and r.resource_type in ('fetch', 'xhr') else None)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(server.start())
            yield page, server
            assert errors == []
        finally:
            page.screenshot(path=str(evidence / 'final.png'), full_page=True)
            (evidence / 'requests.json').write_text(json.dumps(requests, ensure_ascii=False, indent=2))
            (evidence / 'page-errors.json').write_text(json.dumps(errors, ensure_ascii=False))
            browser.close()
            server.stop()


def test_saved_task_failure_retries_the_same_group(tmp_path):
    from playwright.sync_api import expect
    from urllib.parse import parse_qs, urlparse
    path = tmp_path / 'pages'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    doc = store.load_document()
    for i in range(65):
        task = tasks.new_task(task_id=f'analysis-{i:02}', operation_id=f'analysis-op-{i:02}',
                              kind='style_analyze', scope_pages=['p01'], instruction=f'分析 {i:02}',
                              inputs=[], dependencies=[], dispatch_revision=doc['revision_id'],
                              produced_against=content_identity(doc), status='completed')
        doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))
    with browser_for(path) as (page, _):
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_label('风格参考来源').select_option('screenshot')
        page.get_by_text('恢复项目中的截图分析与规范', exact=True).click()
        next_button = page.get_by_role('button', name='下一组保存任务', exact=True)
        expect(next_button).to_be_enabled()
        before = page.get_by_label('恢复已保存的截图分析').inner_text()
        requests = []

        def failure(route):
            offset = int(parse_qs(urlparse(route.request.url).query).get('offset', ['0'])[0])
            requests.append(offset)
            if len(requests) == 1:
                route.fulfill(status=503, json={'error': {'code': 'operation_unavailable', 'message': '第二组暂不可读'}})
            else:
                route.continue_()

        page.route('**/api/tasks?*', failure)
        next_button.click()
        expect(page.locator('.visual-style > [role=status]')).to_contain_text('第二组暂不可读')
        assert page.get_by_label('恢复已保存的截图分析').inner_text() == before
        next_button.click()
        expect(page.get_by_text('第 2 组任务', exact=True)).to_be_visible()
        assert requests == [30, 30]


def test_committed_upload_survives_private_note_afterwrite(tmp_path):
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_label('风格参考来源').select_option('screenshot')
        expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
        page.get_by_text('个人草稿与恢复', exact=True).click()
        held = []
        uploads = []
        page.on('request', lambda request: uploads.append(request.url) if '/api/styles/references/import?' in request.url else None)

        def hold(route):
            draft = route.request.post_data_json['draft']
            if draft['content'].get('visual_style', {}).get('ids') and not held:
                held.append((route, route.fetch()))
                page.evaluate('() => window.uploadDraftHeld=true')
            else:
                route.continue_()

        page.route('**/api/drafts/save', hold)
        page.get_by_label('导入参考截图', exact=True).set_input_files(
            {'name': 'valid.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
        page.wait_for_function('() => window.uploadDraftHeld===true')
        text = '上传等待时继续记录的私人笔记'
        page.get_by_label('个人草稿', exact=True).fill(text)
        held[0][0].fulfill(response=held[0][1])
        expect(page.locator('.visual-reference-choice .pooled-image').last).to_have_attribute('data-image-state', 'ready')
        assert len(uploads) == 1
        assert len(flow.store.load_document()['style_references']) == 1
        # The late text remains in a durable draft, even when the result opens a newer revision.
        drafts = page.request.get(page.url.split('#')[0] + 'api/drafts').json()['records']
        assert any(row['draft']['content'].get('text') == text for row in drafts)
        page.reload()
        expect(page.locator('.visual-reference-choice .pooled-image').last).to_have_attribute('data-image-state', 'ready')
        assert len(uploads) == 1


def test_overview_handoff_is_actionable_in_task_context(tmp_path):
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    dispatch(flow, confirm(flow))
    with browser_for(flow.project) as (page, _):
        page.locator('.todo-priority').get_by_role('button', name='去交接', exact=True).click()
        expect(page.locator('#runs-tasks')).to_be_visible()
        expect(page.locator('.run-detail')).to_contain_text('待接手')
        expect(page.locator('#runs-tasks').get_by_role('button', name='复制交接说明', exact=True)).to_be_enabled()
        page.get_by_role('button', name='待决定', exact=True).click()
        expect(page.locator('#runs-decisions .change-handoffs')).to_have_count(0)


@pytest.mark.parametrize('source', ['project', 'screenshot'])
def test_style_ui_trial_adoption_and_successful_expansion(tmp_path, source):
    """Host supplies explicit synthetic results; all planning/adoption is through UI."""
    import re
    from playwright.sync_api import expect
    from deck_master import tasks as core_tasks
    from test_visual_styles import result
    from test_visual_styles_browser import open_visual_phase
    from test_style_content_browser import toggle_phase
    flow = Flow(tmp_path)
    initial = flow.store.load_document()['pages']
    third_title = flow.store.read_object_json(initial[2]['page'])['customer_visible']['title']
    with browser_for(flow.project) as (page, server):
        held, faulted = [], set()
        def afterwrite_save(route):
            visual = route.request.post_data_json['draft']['content'].get('visual_style', {})
            stage = 'dispatch' if visual.get('change_id') else 'confirm' if visual.get('recipe') else 'analyze' if visual.get('task_id') else None
            if source == 'screenshot' and stage and stage not in faulted:
                faulted.add(stage)
                held.append((stage, route, route.fetch()))
                page.evaluate('(stage)=>window.heldBusinessSave=stage', stage)
            else:
                route.continue_()
        def release_afterwrite(stage):
            if source != 'screenshot':
                return
            page.wait_for_function('(stage)=>window.heldBusinessSave===stage', arg=stage)
            note = page.get_by_label('个人草稿', exact=True)
            if not note.is_visible():
                page.get_by_text('个人草稿与恢复', exact=True).click()
            note.fill('分析、规范、试作业务成功期间的私人后写：'+stage)
            _, route, response = next(item for item in held if item[0] == stage)
            route.fulfill(response=response)
        page.route('**/api/drafts/save', afterwrite_save)
        page.get_by_role('button', name='风格校准', exact=True).click()
        if source == 'screenshot':
            page.get_by_label('风格参考来源').select_option('screenshot')
            page.get_by_label('截图风格试作目标').select_option('p02')
            page.get_by_text('预先允许后续扩展的页面（默认不选）', exact=True).click()
            page.get_by_label('允许后续风格扩展到 '+third_title, exact=True).check()
            page.get_by_label('导入参考截图', exact=True).set_input_files(
                {'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
            expect(page.get_by_label('选用参考截图 1', exact=True)).to_be_checked()
            page.get_by_role('button', name='分析截图', exact=True).click()
            release_afterwrite('analyze')
            expect(page.get_by_role('button', name='查看分析结果', exact=True)).to_be_enabled()
            doc = flow.store.load_document()
            analysis = next(flow.store.read_object_json(ref) for ref in reversed(doc['tasks'])
                            if flow.store.read_object_json(ref)['kind'] == 'style_analyze')
            reference = flow.store.read_object_json(doc['style_references'][0])
            flow.start(analysis)
            core_tasks.accept_result(flow.store, task_id=analysis['task_id'], operation_id=analysis['operation_id'],
                                     produced_against=analysis['produced_against'], envelope_raw=result(reference['reference_id']))
            page.get_by_role('button', name='查看分析结果', exact=True).click()
            expect(page.get_by_role('button', name='检查并确认视觉规范', exact=True)).to_be_enabled()
            page.get_by_role('button', name='检查并确认视觉规范', exact=True).click()
            release_afterwrite('confirm')
            expect(page.locator('.visual-style > [role=status]')).not_to_contain_text('无法')
            expect(page.get_by_label('已确认的截图规范').locator('option')).to_have_count(2)
            recipe_id = page.get_by_label('已确认的截图规范').locator('option').nth(1).get_attribute('value')
            open_visual_phase(page, 2)
            dispatch_label = '保存并交接试作'
        else:
            page.get_by_label('风格参考原图', exact=True).select_option('p01')
            page.get_by_label('当前风格试作目标', exact=True).select_option('p02')
            page.get_by_text('其它目标页', exact=True).click()
            page.get_by_label(re.compile(r'^风格目标 第 3 页')).check()
            page.get_by_role('button', name='检查风格要求', exact=True).click()
            page.get_by_role('button', name='确认这版风格要求', exact=True).click()
            expect(page.get_by_label('已确认的风格版本').locator('option')).to_have_count(2)
            recipe_id = page.get_by_label('已确认的风格版本').locator('option').nth(1).get_attribute('value')
            toggle_phase(page, 3)
            dispatch_label = '保存并交接风格试作'
        page.get_by_role('button', name='预览单页试作', exact=True).click()
        page.get_by_role('button', name=dispatch_label, exact=True).click()
        release_afterwrite('dispatch')
        expect(page.locator('#runs-tasks .task-handoff')).to_be_visible()
        trial = next(flow.store.read_object_json(ref) for ref in reversed(flow.store.load_document()['tasks'])
                     if flow.store.read_object_json(ref)['kind'] == 'blueprint')
        assert trial['scope_pages'] == ['p02']
        candidate = flow.image(trial)['candidate_ids'][0]
        # Read the actual returned candidate through the current-version navigation.
        page.reload()
        page.get_by_role('button', name='查看当前版本', exact=True).click()
        page.get_by_role('button', name='待决定', exact=True).click()
        card = page.locator(f'.candidate-batch [data-candidate-id="{candidate}"]')
        card.get_by_role('button', name='比较这个候选', exact=True).click()
        page.get_by_role('button', name='预览采用这个候选', exact=True).click()
        page.get_by_role('button', name='采用这个候选', exact=True).click()
        expect(page.locator('.candidate-state')).to_contain_text('当前采用')
        after_trial = flow.store.load_document()['pages']
        assert after_trial[0] == initial[0] and after_trial[2] == initial[2]
        page.get_by_role('button', name='查看任务与交付', exact=True).click()
        expect(page.get_by_role('heading', name='任务与交付', exact=True)).to_be_visible()
        page.get_by_role('button', name='风格校准', exact=True).click()
        if source == 'screenshot':
            page.get_by_label('风格参考来源').select_option('screenshot')
            page.get_by_text('恢复项目中的截图分析与规范', exact=True).click()
            page.get_by_label('已确认的截图规范').select_option(recipe_id)
            expect(page.locator('.visual-style > [role=status]')).to_contain_text('已打开所选确认规范')
            open_visual_phase(page, 3)
            page.get_by_label('已采用的截图风格样例').select_option(candidate)
            page.get_by_label('本次扩展到 '+third_title, exact=True).check()
            page.get_by_role('button', name='预览所选页扩展', exact=True).click()
        else:
            toggle_phase(page, 2)
            page.get_by_label('已确认的风格版本').select_option(recipe_id)
            toggle_phase(page, 3)
            page.get_by_role('button', name='从此候选扩展', exact=True).click()
            page.get_by_label(re.compile(r'^扩展到 第 3 页')).check()
            page.get_by_role('button', name='预览明确选页的扩展', exact=True).click()
        page.get_by_role('button', name=dispatch_label, exact=True).click()
        expect(page.locator('#runs-tasks .task-handoff')).to_be_visible()
        expansion = next(flow.store.read_object_json(ref) for ref in reversed(flow.store.load_document()['tasks'])
                         if flow.store.read_object_json(ref)['kind'] == 'blueprint')
        assert expansion['task_id'] != trial['task_id'] and expansion['scope_pages'] == ['p03']
        assert flow.store.load_document()['pages'] == after_trial
        page.screenshot(path=str(page.evidence / 'expansion-handoff.png'), full_page=True)
        expanded_candidate = flow.image(expansion)['candidate_ids'][0]
        page.reload()
        page.get_by_role('button', name='查看当前版本', exact=True).click()
        page.get_by_role('button', name='待决定', exact=True).click()
        page.locator(f'.candidate-batch [data-candidate-id="{expanded_candidate}"]').get_by_role('button', name='比较这个候选', exact=True).click()
        page.screenshot(path=str(page.evidence / 'expansion-compare.png'), full_page=True)
        page.get_by_role('button', name='预览采用这个候选', exact=True).click()
        page.get_by_role('button', name='采用这个候选', exact=True).click()
        expect(page.locator('.candidate-state')).to_contain_text('当前采用')
        final = flow.store.load_document()['pages']
        assert final[:2] == after_trial[:2] and final[2] != after_trial[2]
        (page.evidence / 'business-states.json').write_text(json.dumps({'initial': initial, 'trial_adopted': after_trial, 'expansion_adopted': final}, indent=2))
        if source == 'screenshot':
            assert faulted == {'analyze', 'confirm', 'dispatch'}
            records = page.request.get(server.start().rstrip('/')+'/api/drafts').json()['records']
            assert any(row['draft']['content'].get('text', '').endswith(':dispatch') or row['draft']['content'].get('text', '').endswith('：dispatch') for row in records)


def test_partial_upload_keeps_successful_files_and_retries_only_failed_file(tmp_path):
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_label('风格参考来源').select_option('screenshot')
        requests = []
        page.on('request', lambda r: requests.append(r.url) if '/api/styles/references/import?' in r.url else None)
        page.get_by_label('导入参考截图', exact=True).set_input_files([
            {'name': 'first.png', 'mimeType': 'image/png', 'buffer': image_bytes()},
            {'name': 'second.png', 'mimeType': 'image/png', 'buffer': image_bytes()},
            {'name': 'broken.png', 'mimeType': 'image/png', 'buffer': b'not an image'},
        ])
        expect(page.locator('.visual-reference-choice')).to_have_count(2)
        expect(page.get_by_role('button', name='结束失败上传，重新选图', exact=True)).to_be_enabled()
        page.reload()
        expect(page.locator('.visual-reference-choice')).to_have_count(2)
        page.get_by_role('button', name='结束失败上传，重新选图', exact=True).click()
        page.get_by_label('导入参考截图', exact=True).set_input_files(
            {'name': 'third.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
        expect(page.locator('.visual-reference-choice')).to_have_count(3)
        assert len(requests) == 4
        assert len(flow.store.load_document()['style_references']) == 3


def test_upload_success_has_visible_recovery_when_private_save_fails(tmp_path):
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_label('风格参考来源').select_option('screenshot')
        expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
        def reject(route):
            route.fulfill(status=503, json={'error': {'code': 'operation_unavailable', 'message': '草稿服务暂不可用'}})
        page.route('**/api/drafts/save', reject)
        page.get_by_label('导入参考截图', exact=True).set_input_files(
            {'name': 'valid.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
        expect(page.locator('.visual-upload-recovery')).to_contain_text('截图已上传')
        expect(page.get_by_role('button', name='打开已保存的结果', exact=True)).to_be_enabled()
        assert len(flow.store.load_document()['style_references']) == 1
        page.unroute('**/api/drafts/save', reject)
        page.reload()
        page.get_by_role('button', name='打开已保存的结果', exact=True).click()
        expect(page.locator('.visual-reference-choice .pooled-image')).to_have_attribute('data-image-state', 'ready')
        assert len(flow.store.load_document()['style_references']) == 1


@pytest.mark.parametrize('concurrent_advance', [False, True])
def test_three_versions_restore_uses_read_source_and_current_basis(tmp_path, concurrent_advance):
    from test_styles import mutate
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    a = flow.store.current_revision_id()
    mutate(flow, 'p01')
    b = flow.store.current_revision_id()
    mutate(flow, 'p02')
    c = flow.store.current_revision_id()
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='任务与交付', exact=True).click()
        page.get_by_role('button', name='版本', exact=True).click()
        page.get_by_label('阅读历史版本').select_option(b)
        page.get_by_role('button', name='读取所选版本', exact=True).click()
        expect(page.get_by_label('阅读历史版本').locator(f'option[value="{b}"]')).to_contain_text('当前阅读版本')
        page.get_by_label('阅读历史版本').select_option(a)
        expect(page.get_by_role('button', name='预览恢复此版本', exact=True)).to_be_disabled()
        expect(page.locator('.history-identity')).to_contain_text('请先读取所选版本')
        page.get_by_role('button', name='逐页查看与固定比较', exact=True).click()
        expect(page.locator('#view-title')).to_contain_text('第 1 页')
        assert f'revision={b}' in page.url
        page.get_by_role('button', name='任务与交付', exact=True).click()
        page.get_by_role('button', name='文件', exact=True).click()
        with page.expect_request('**/api/exports') as exported:
            page.get_by_role('button', name='生成审阅包', exact=True).click()
        assert exported.value.post_data_json['revision'] == b
        expect(page.get_by_role('link', name='下载 ZIP', exact=True)).to_be_visible()
        page.get_by_role('button', name='版本', exact=True).click()
        page.get_by_label('阅读历史版本').select_option(a)
        requests = []
        page.on('request', lambda r: requests.append(r.post_data_json) if '/api/history/plan-restore' in r.url else None)
        page.get_by_role('button', name='读取所选版本', exact=True).click()
        expect(page.get_by_label('阅读历史版本').locator(f'option[value="{a}"]')).to_contain_text('当前阅读版本')
        page.get_by_role('button', name='预览恢复此版本', exact=True).click()
        dialog = page.locator('dialog[open]')
        expect(dialog).to_contain_text('来源版本')
        assert requests[-1] == {'revision_id': a, 'base_revision': c}
        if concurrent_advance:
            mutate(flow, 'p03')
            current = flow.store.current_revision_id()
        dialog.get_by_role('button', name='确认恢复并创建新版本', exact=True).click()
        if concurrent_advance:
            expect(dialog).to_contain_text('本次未提交，输入已保留')
            expect(dialog).to_contain_text('未恢复或覆盖任何页')
            assert flow.store.current_revision_id() == current
            dialog.get_by_role('button', name='关闭', exact=True).click()
            return
        expect(dialog).to_have_count(0)
        d = flow.store.current_revision_id()
        assert d not in (a, b, c)


def test_147_mixed_tasks_paginate_filter_and_keep_subareas_reachable(tmp_path):
    from playwright.sync_api import expect
    path = tmp_path / 'scale'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    doc = store.load_document()
    doc['tasks'] = []
    for i in range(147):
        task = tasks.new_task(task_id=f'scale-{i:03}', operation_id=f'scale-op-{i:03}',
                              kind=['compose', 'blueprint', 'reconstruct'][i % 3], scope_pages=['p01'],
                              instruction=f'第 {i:03} 条合成规模验证要求', inputs=[], dependencies=[],
                              dispatch_revision=doc['revision_id'], produced_against=content_identity(doc),
                              status=['completed', 'cancelled', 'failed'][i % 3])
        doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))
    with browser_for(path) as (page, _):
        page.get_by_role('button', name='任务与交付', exact=True).click()
        expect(page.locator('.run-notice')).to_contain_text('共 147 项')
        expect(page.locator('.run-task')).to_have_count(30)
        seen = set(page.locator('.run-task').evaluate_all('(rows)=>rows.map(row=>row.dataset.taskId)'))
        for n in range(2, 6):
            page.get_by_role('button', name='下一页任务', exact=True).click()
            expect(page.locator('.run-pagination')).to_contain_text(f'第 {n} 页')
            seen.update(page.locator('.run-task').evaluate_all('(rows)=>rows.map(row=>row.dataset.taskId)'))
        assert len(seen) == 147
        expect(page.get_by_role('button', name='下一页任务', exact=True)).to_be_disabled()
        page.get_by_label('按执行状态筛选').select_option('failed')
        expect(page.locator('.run-notice')).to_contain_text('共 49 项')
        expect(page.locator('.run-pagination')).to_contain_text('第 1 页')
        page.locator('.run-task').first.get_by_role('button', name='查看这项任务', exact=True).click()
        expect(page.locator('.run-detail')).to_contain_text('执行失败')
        expect(page.get_by_role('button', name='核实原任务', exact=True)).to_be_visible()
        for area, selector in [('待决定', '#runs-decisions'), ('版本', '#runs-versions'), ('文件', '#runs-files')]:
            page.get_by_role('button', name=area, exact=True).click()
            expect(page.locator(selector)).to_be_visible()
        page.reload()
        expect(page.locator('#runs-files')).to_be_visible()


def test_handoff_three_groups_and_late_clipboard_keep_original_copy_identity(tmp_path):
    from playwright.sync_api import expect
    from test_ux00_fixes_browser import create_change_group
    flow = Flow(tmp_path)
    groups = [create_change_group(flow.project, flow.store, f'p{i+1:02d}', f'独立交接要求 {name}')['change_id']
              for i, name in enumerate(('AAA', 'BBB', 'CCC'))]
    with browser_for(flow.project) as (page, server):
        page.get_by_role('button', name='任务与交付', exact=True).click()
        page.get_by_text('其它修改组的交接', exact=True).click()
        panel = page.locator('.change-handoffs')
        buttons = panel.locator('.change-list button')
        catalog = page.request.get(server.start().rstrip('/')+'/api/tasks?limit=1').json()['groups']
        order = [row['change_id'] for row in catalog if row.get('change_id')]
        buttons.nth(order.index(groups[0])).click()
        expect(panel.locator('.handoff-detail h3')).to_have_attribute('data-change-id', groups[0])
        delayed = []
        page.route(f'**/api/changes/{groups[1]}/handoff*', lambda route: delayed.append(route))
        buttons.nth(order.index(groups[1])).click()
        expect(panel.get_by_role('button', name='交给 Deck Master Agent', exact=True)).to_be_disabled()
        buttons.nth(order.index(groups[0])).click()
        expect(panel.get_by_role('button', name='交给 Deck Master Agent', exact=True)).to_be_enabled()
        page.evaluate("""() => Object.defineProperty(navigator, 'clipboard', {value: {writeText: text => new Promise(resolve => {window.copiedText=text; window.finishCopy=resolve;})}})""")
        panel.get_by_role('button', name='交给 Deck Master Agent', exact=True).click()
        page.wait_for_function('() => typeof window.finishCopy === "function"')
        buttons.nth(order.index(groups[2])).click()
        for route in delayed:
            route.abort()
        expect(panel.locator('.handoff-detail h3')).to_have_attribute('data-change-id', groups[2])
        page.evaluate('() => window.finishCopy()')
        identity = page.request.get(server.start().rstrip('/')+'/api/project').json()['project_identity']
        key = 'deck-master:v3:copied:'+identity
        page.wait_for_function('(key) => JSON.parse(localStorage.getItem(key)||"[]").length === 1', arg=key)
        assert json.loads(page.evaluate('(key)=>localStorage.getItem(key)', key)) == [groups[0]]
        expected = page.request.get(server.start().rstrip('/')+f'/api/changes/{groups[0]}/handoff').json()['text']
        assert page.evaluate('() => window.copiedText') == expected
        expect(panel.locator('.handoff-detail h3')).not_to_contain_text('已复制')


def test_gallery_conflict_same_selection_and_layer_exposes_reference_difference(tmp_path):
    import re
    from playwright.sync_api import expect
    from test_ux06_gallery_conflict_browser import open_gallery
    flow = Flow(tmp_path)
    with browser_for(flow.project) as (first, server):
        first.get_by_role('button', name='整稿画廊', exact=True).click()
        first.get_by_label(re.compile(r'^选择第 1 页 ')).check()
        expect(first.locator('.gallery-save')).to_contain_text('画廊选择已保存')
        second = open_gallery(first.context, server.start(), 'second')
        second.locator('.slide-tile[data-page-id="p02"]').get_by_role('button', name='☆ 标记参考', exact=True).click()
        expect(second.locator('.gallery-save')).to_contain_text('画廊选择已保存')
        first.locator('.slide-tile[data-page-id="p03"]').get_by_role('button', name='☆ 标记参考', exact=True).click()
        expect(first.locator('.gallery-save')).to_contain_text('个窗口保存了不同选择')
        first.get_by_role('button', name='比较窗口选择', exact=True).click()
        dialog = first.locator('dialog[open]')
        expect(dialog).to_contain_text('固定比较引用：第 3 页')
        expect(dialog).to_contain_text('项目保存：固定比较引用：第 2 页')
        snapshots = {}
        for name, key in [('下载此窗口副本', 'window'), ('下载项目保存副本', 'saved')]:
            with first.expect_download() as downloaded:
                dialog.get_by_role('button', name=name, exact=True).click()
            snapshots[key] = json.loads(Path(downloaded.value.path()).read_text())
        assert snapshots['window']['selected_page_ids'] == snapshots['saved']['selected_page_ids'] == ['p01']
        assert snapshots['window']['layer'] == snapshots['saved']['layer']
        assert snapshots['window']['references'][0]['page_id'] == 'p03'
        assert snapshots['saved']['references'][0]['page_id'] == 'p02'
        first.screenshot(path=str(first.evidence/'reference-conflict.png'), full_page=True)
        (first.evidence/'downloaded-snapshots.json').write_text(json.dumps(snapshots, indent=2))
        dialog.get_by_role('button', name='读取项目保存的选择', exact=True).click()
        expect(first.locator('.slide-tile[data-page-id="p02"] .reference-button')).to_have_attribute('aria-pressed', 'true')
        expect(first.locator('.slide-tile[data-page-id="p03"] .reference-button')).to_have_attribute('aria-pressed', 'false')
        second.close()


@pytest.mark.parametrize('width,height', [(1440,900), (1280,800), (390,844)])
def test_task_handoff_and_subarea_state_remain_readable_at_supported_viewports(tmp_path, width, height):
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    dispatch(flow, confirm(flow))
    with browser_for(flow.project) as (page, _):
        page.set_viewport_size({'width': width, 'height': height})
        page.locator('.todo-priority').get_by_role('button', name='去交接', exact=True).click()
        copy = page.get_by_role('button', name='复制交接说明', exact=True)
        expect(copy).to_be_enabled()
        assert copy.bounding_box()['height'] >= 44
        page.screenshot(path=str(page.evidence/'task-handoff.png'), full_page=True)
        for name in ('待决定', '版本', '文件', '正在进行'):
            control = page.get_by_role('button', name=name, exact=True)
            control.click()
            expect(control).to_have_attribute('aria-pressed', 'true')
            colors = control.evaluate('(el)=>{const s=getComputedStyle(el);return [s.color,s.backgroundColor,s.transitionDuration]}')
            assert colors[0] != colors[1] and colors[2] == '0s'
            assert control.bounding_box()['height'] >= 44
            page.screenshot(path=str(page.evidence/f'area-{name}.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('width,height', [(1440,900), (1280,800)])
def test_first_original_candidate_fit_is_visible_above_decisions_and_has_correct_empty_state(tmp_path, width, height):
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    doc = flow.store.load_document()
    doc['pages'][1]['blueprint'] = None
    commit(flow.store, doc, str(uuid.uuid4()))
    task = flow.dispatch('p02', instruction='仅制作第一份原图，保留正文')
    candidate = flow.image(task)['candidate_ids'][0]
    with browser_for(flow.project) as (page, _):
        page.set_viewport_size({'width':width,'height':height})
        page.get_by_role('button', name='任务与交付', exact=True).click()
        page.get_by_role('button', name='待决定', exact=True).click()
        page.locator(f'.candidate-batch [data-candidate-id="{candidate}"]').get_by_role('button', name='比较这个候选', exact=True).click()
        expect(page.locator('.candidate-column[data-side=candidate] .pooled-image')).to_have_attribute('data-image-state','ready')
        current=page.locator('.candidate-column[data-side=current]')
        expect(current).not_to_contain_text('实际 PPT')
        viewport=page.locator('.candidate-column[data-side=candidate] .comparison-viewport')
        footer=page.locator('.candidate-decisions')
        assert viewport.bounding_box()['y']+viewport.bounding_box()['height'] <= footer.bounding_box()['y']+1
        page.screenshot(path=str(page.evidence/'fit-above-actions.png'),full_page=True)


def test_uploaded_result_finishes_recovery_after_late_draft_verification(tmp_path):
    """A successfully mounted result must retire its continuation after a late draft ACK."""
    from playwright.sync_api import expect
    flow = Flow(tmp_path)
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='风格校准', exact=True).click()
        page.get_by_label('风格参考来源').select_option('screenshot')
        expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
        uploaded = []; lost = []
        def import_image(route):
            response = route.fetch()
            uploaded.append(response.json()['operation_result']['revision_id'])
            route.fulfill(response=response)
        def lose_restored_save(route):
            if uploaded and ('revision=' + uploaded[-1]) in page.url and not lost:
                route.fetch()  # business succeeded, and the restored private selection was saved too
                lost.append(True)
                route.abort()
            else:
                route.continue_()
        page.route('**/api/styles/references/import?*', import_image)
        page.route('**/api/drafts/save', lose_restored_save)
        page.get_by_label('导入参考截图', exact=True).set_input_files(
            {'name': 'late-draft.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
        expect(page.locator('.visual-reference-choice .pooled-image')).to_have_attribute('data-image-state', 'ready')
        expect(page.locator('.visual-upload-recovery')).to_contain_text('已上传')
        page.get_by_text('个人草稿与恢复', exact=True).click()
        expect(page.get_by_role('button', name='核实草稿保存', exact=True)).to_be_visible()
        page.get_by_role('button', name='核实草稿保存', exact=True).click()
        expect(page.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
        expect(page.locator('.visual-upload-recovery')).to_be_empty()
        assert lost and len(uploaded) == 1
        assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('deck-master:visual-style:')&&k.endsWith(':completed')).length") == 0
        page.reload()
        expect(page.locator('.visual-reference-choice .pooled-image')).to_have_attribute('data-image-state', 'ready')
        assert len(uploaded) == 1
