"""W05 real Chromium/HTTP proof using explicitly synthetic recorded evidence.

No model or Office invocation. Native collector replay in the isolated fixture
is not a new real Host proof. Raw traces/receipts stay local, never commit them.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

from deck_master import editing, generation, observations, samples, service, tasks, ui_journal, workbench
from deck_master.models import bump_revision, canonical_json_bytes, content_identity
from deck_master.pipeline import artifact
from deck_master.store import Store
from deck_master.web import WorkbenchServer

TEXT = 'A🙂e\u0301\r\n中\n重复摘录🙂\n重复摘录🙂\n👩\u200d💻\n<img src=x onerror="window.injected=true">'


def commit(store, doc, operation):
    base = store.current_revision_id()
    updated = bump_revision({**doc, 'revision_id': base}, {'operation_id': operation, 'kind': 'task_update', 'description': 'Explicit synthetic W05 browser fixture', 'read_set': []})
    store.commit_change(base_revision=base, document=updated, operation_id=operation)
    return updated


def fixture(root):
    project = root / 'synthetic-page-chain'
    manifest = samples.create_gallery_sample(project, readonly=False)
    store = Store(project); original_revision = store.current_revision_id()
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['subtitle'] = TEXT
    editing.edit_page(project, page=page, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='unicode-page')
    doc = store.load_document()
    task = service.open_blueprint_task(store, doc, doc['pages'][0])
    # The native-event fixture is isolated from actual Codex sessions and clearly
    # labeled. It tests UI evidence semantics, not a real model call.
    thread = '11111111-1111-7111-8111-111111111111'; turn = '22222222-2222-7222-8222-222222222222'
    execution = f'codex:{thread}:{turn}'
    service.task_start(project, task_id=task['task_id'], execution_ref=execution, supported_protocols=[generation.PROTOCOL], capabilities=generation.CAPABILITIES)
    value = generation.prepared_input(store, store.load_document(), task)
    value['prompt'] = TEXT; value['parameters'] = {'transparent_background': False}
    frozen = generation.freeze(project, task_id=task['task_id'], input=value, base_revision=store.current_revision_id(), operation_id='synthetic-freeze')
    generation.freeze(project, task_id=task['task_id'], input={**value, 'prompt': '另一份尚未使用的冻结请求', 'parameters': {'model': 'SyntheticRequestedModel', 'seed': 314}, 'references': [{'file': store.read_object_json(doc['pages'][1]['blueprint'])['file'], 'role': 'reference'}]}, base_revision=store.current_revision_id(), operation_id='synthetic-other-freeze')
    attempt = tasks.call_begin(store, task_id=task['task_id'], allowance_id='call-1', execution_ref=execution, request_id=frozen['request_id'])
    old = store.read_object_json(store.load_document()['pages'][0]['blueprint'])
    raw = store.read_object_bytes(old['file'])
    runtime = root / 'synthetic-native-runtime'; saved = runtime / 'generated_images' / thread / 'exec-33333333-3333-7333-8333-333333333333.png'; saved.parent.mkdir(parents=True); saved.write_bytes(raw)
    sessions = runtime / 'sessions'; dated = sessions / '2026/09/28'; dated.mkdir(parents=True)
    record = dated / ('rollout-2026-09-28T00-00-00-' + thread + '.jsonl')
    now = time.time_ns() // 1000000
    event = {'type': 'event_msg', 'payload': {'type': 'item_completed', 'thread_id': thread, 'turn_id': turn, 'started_at_ms': now, 'completed_at_ms': now,
        'item': {'type': 'Extension', 'kind': 'image_gen.generation', 'id': 'exec-33333333-3333-7333-8333-333333333333', 'status': 'completed', 'revisedPrompt': TEXT,
                 'result': base64.b64encode(raw).decode(), 'transparentBackground': False, 'failure': None, 'savedPath': str(saved)}}}
    record.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': thread, 'cli_version': 'synthetic-w05-fixture'}}) + '\n' + json.dumps(event) + '\n')
    original_root = observations._session_root
    try:
        observations._session_root = lambda: sessions
        tasks.call_settle(store, task_id=task['task_id'], allowance_id='call-1', attempt_id=attempt['attempt_id'], outcome='consumed',
            report_bytes=canonical_json_bytes({'source': 'codex_session.v1', 'thread_id': thread, 'turn_id': turn, 'item_id': 'exec-33333333-3333-7333-8333-333333333333'}))
    finally:
        observations._session_root = original_root
    staging = store.staging_dir / task['operation_id']; staging.mkdir(exist_ok=True); (staging / 'result.png').write_bytes(raw)
    service.accept_result(project, result_payload={'kind': 'blueprint', 'files': [{'file_id': 'output', 'path': 'result.png', 'media_type': 'image/png'}],
        'generation_result': {'request_id': frozen['request_id'], 'attempt_id': attempt['attempt_id']},
        'artifact_specs': [{'role': 'blueprint', 'page_id': 'p01', 'file_id': 'output', 'provenance': {'source_type': 'host_generated', 'tool': 'synthetic-ui-fixture'}, 'limitations': ['Synthetic collector replay, not a real Host call']}]},
        **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')})
    doc = store.load_document()
    host = store.read_object_json(doc['pages'][1]['blueprint']); host['provenance']['submitted_prompt'] = store.put_blob(b'Host reported text only', ext='txt')
    doc['pages'][1]['blueprint'] = store.put_json_object(host)
    # Stored report fields are intentionally synthetic, not fake production files.
    ppt_path = root / 'synthetic-metadata-only.pptx'; ppt_path.write_bytes(b'Synthetic W05 metadata fixture. Not an Office document.')
    report_path = root / 'synthetic-render-report.json'; report_path.write_text(json.dumps({'status': 'pass', 'pages': [{'page_id': 'p01', 'text_runs': 7, 'native_shapes': 9}], 'findings': []}))
    entry = doc['pages'][0]
    # Separately drawn synthetic layer previews; no real compiler was run.
    svg_path = root / 'synthetic-page.svg'; svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="#edf3ee"/><text x="80" y="120" font-size="30">Synthetic W05 SVG input</text></svg>')
    entry['svg'] = artifact(store, svg_path, 'svg', page_id='p01')
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (960, 540), '#e3eaf0'); ImageDraw.Draw(image).text((80, 120), 'Synthetic W05 PPT preview; not Office output', fill='#223344')
    preview_path = root / 'synthetic-preview.png'; image.save(preview_path)
    entry['ppt_preview'] = artifact(store, preview_path, 'ppt_preview', page_id='p01')
    trace_path = root / 'synthetic-trace.json'; trace_path.write_text(json.dumps({'pages': [{'page_id': 'p01', 'sha256': store.read_object_json(entry['svg'])['file']['sha256'], 'shapes': [{'kind': 'image'}, {'kind': 'text'}]}], 'fonts': {'SyntheticFont': {'sha256': 'a' * 64}}, 'diagnostics': []}))
    deps = [{'kind': 'svg', 'identity': e['page_id'], 'sha256': e['svg']['sha256']} for e in doc['pages'] if e.get('svg')]
    doc['outputs'] = {'pptx': artifact(store, ppt_path, 'pptx', dependencies=deps), 'render_report': artifact(store, report_path, 'render_report', dependencies=deps), 'trace': artifact(store, trace_path, 'object_trace', dependencies=deps)}
    commit(store, doc, 'synthetic-production-metadata')
    return project, store, {'original_revision': original_revision, 'fixed_revision': store.current_revision_id(), 'fixture': manifest, 'request_id': frozen['request_id'], 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    root = Path(args.out).absolute(); root.mkdir(parents=True, exist_ok=False); shots = root / 'screenshots'; shots.mkdir()
    project, store, manifest = fixture(root); info = ui_journal.project_info(project); fixed = manifest['fixed_revision']
    before = (store.read_current(), content_identity(store.load_document()))
    server = WorkbenchServer(project); url = server.start(); checks = {}; errors = []
    def route(page_id='p01', layer='original_image', revision=fixed, base=url):
        return base + 'v2/#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': page_id, 'layer': layer, 'revision': revision, 'zoom': 1})
    def navigate(page, page_id='p01', layer='original_image', revision=fixed, base=url):
        labels = {'original_image': '原图', 'submitted_prompt': '实际提示词', 'ppt': 'PPT', 'content': '逐页稿'}
        page.goto(route(page_id, layer, revision, base))
        expect(page.get_by_role('navigation', name='页面层').get_by_role('button', name=labels[layer], exact=True)).to_have_attribute('aria-current', 'page')
        expect(page.get_by_label('页面内容', exact=True)).to_have_attribute('data-page-id', page_id)
        expect(page.get_by_label('页面内容', exact=True)).to_have_attribute('data-revision', revision)
    def layer(page, name):
        tab = page.get_by_role('navigation', name='页面层').get_by_role('button', name=name, exact=True)
        tab.click(); expect(tab).to_have_attribute('aria-current', 'page')
    def saved(page): expect(page.get_by_text('已保存到项目，可跨端口恢复', exact=True)).to_be_visible()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); browser_version = browser.version
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='zh-CN'); context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            navigate(page); expect(page.locator('.page-image[data-image-ready="true"]')).to_be_visible()
            expect(page.get_by_text('已绑定这张原图的冻结请求。', exact=True)).to_be_visible()
            page.get_by_role('button', name='查看实际提示词', exact=True).click()
            expect(page.get_by_label('提示词原文', exact=True)).to_have_text(TEXT)
            layer(page, '逐页稿'); expect(page.locator('.page-copy')).to_contain_text('A🙂é')
            checks['original_to_recorded_prompt_and_content_within_three_clicks'] = True
            layer(page, '实际提示词'); original = page.get_by_label('提示词原文', exact=True)
            assert original.text_content() == TEXT and not page.locator('img[onerror]').count()
            assert page.evaluate('window.injected') is None
            page.locator('.text-range-tools summary').click()
            original.evaluate('''node => { const range=document.createRange();range.setStart(node.firstChild,1);range.setEnd(node.firstChild,5);const s=getSelection();s.removeAllRanges();s.addRange(range);node.dispatchEvent(new PointerEvent('pointerup')); }''')
            expect(page.get_by_label('选段起点', exact=True)).to_have_value('1'); expect(page.get_by_label('选段终点', exact=True)).to_have_value('4')
            page.get_by_role('button', name='校验原文选段', exact=True).click()
            expect(page.locator('.range-excerpt')).to_have_text('🙂é')
            page.get_by_label('选段起点', exact=True).fill('4'); page.get_by_label('选段终点', exact=True).fill('6'); page.get_by_role('button', name='校验原文选段', exact=True).click()
            expect(page.locator('.text-range-tools [role=status]')).to_contain_text('[4, 6)')
            assert page.locator('.range-excerpt').text_content() == '\r\n'
            vectors = page.evaluate('''async text => { const m=await import('/v2/text-selection.js'); let rejected=false;try{m.codePointOffset('A🙂é\\r\\n中',2)}catch{rejected=true}return {map:m.boundaries('A🙂é\\r\\n中'),rejected,zwj:m.boundaries('👩‍💻'),range:m.makeRange({text,ref:{},locator:'',text_sha256:''},1,4).excerpt}; }''', TEXT)
            assert vectors == {'map': [0, 1, 3, 4, 5, 6, 7, 8], 'rejected': True, 'zwj': [0, 2, 3, 5], 'range': '🙂é'}
            checks['unicode_dom_utf16_to_codepoints_crlf_combining_zwj'] = vectors
            diffs = page.evaluate("""async () => {const m=await import('/v2/text-diff.js');return {exact:m.diffText('é\\r\\n','é\\n').rows.map(r=>r.kind),large:m.diffText('x'.repeat(200001),'y').mode};}""")
            assert diffs == {'exact': ['removed', 'added'], 'large': 'full_sides'}
            checks['diff_preserves_combining_marks_and_bounds_large_comparison'] = diffs
            page.get_by_label('个人草稿', exact=True).fill('可修改的个人新想法'); saved(page)
            assert workbench.page_lineage(project, 'p01')['prompts']['submitted']['text'] == TEXT
            page.get_by_role('button', name='比较原文与草稿', exact=True).click(); expect(page.get_by_role('dialog')).to_contain_text('个人草稿（未提交）'); page.keyboard.press('Escape')
            checks['draft_does_not_modify_recorded_prompt_or_image'] = True
            page.evaluate('scrollTo(0,0)')
            expect(page.locator('#toast')).not_to_have_class('visible')
            page.screenshot(path=str(shots / 'prompt-selection-draft.png'), full_page=True)
            layer(page, '预备提示词'); select = page.get_by_label('选择草稿绑定的预备提示词', exact=True)
            refs = select.locator('option').evaluate_all('(options)=>options.map(o=>o.value).filter(Boolean)')
            assert len(refs) >= 3
            select.select_option(refs[1]); expect(page.get_by_label('提示词原文', exact=True)).to_have_text('另一份尚未使用的冻结请求')
            page.get_by_text('冻结参数与参考图', exact=True).click(); expect(page.locator('.prompt-workbench')).to_contain_text('SyntheticRequestedModel')
            expect(page.locator('.prompt-workbench .reference-item canvas')).to_be_visible()
            page.get_by_label('个人草稿', exact=True).fill('仅属于第二份冻结请求'); saved(page)
            select.select_option(refs[0]); expect(page.get_by_label('个人草稿', exact=True)).to_have_value('')
            page.get_by_role('button', name='比较预备与实际文本', exact=True).click(); expect(page.locator('.prompt-workbench .prompt-diff')).to_contain_text('原文完全一致')
            select.select_option(refs[-1]); expect(page.get_by_text('可信结构段落', exact=True)).to_be_visible()
            checks['all_prepared_records_exact_basis_switch_trusted_segments_and_diff'] = True
            layer(page, '原图'); page.get_by_text('当次模型、参数与参考图', exact=True).click()
            expect(page.locator('.generation-basis')).to_contain_text('当次参考图：未知')
            expect(page.locator('.generation-basis')).to_contain_text('当次模型未知')
            checks['unknown_actual_parameters_and_references_not_filled_from_frozen_defaults'] = True
            navigate(page, 'p02', 'submitted_prompt'); expect(page.locator('.prompt-workbench .observer-label')).to_contain_text('Host申报')
            navigate(page, 'p04', 'submitted_prompt'); expect(page.get_by_role('heading', name='实际提示词未记录', exact=True)).to_be_visible()
            navigate(page, 'p03', 'original_image'); expect(page.get_by_role('heading', name='原图未生成', exact=True)).to_be_visible()
            checks['host_reported_unknown_and_missing_image_states'] = True
            navigate(page, 'p01', 'submitted_prompt'); expect(page.get_by_label('个人草稿', exact=True)).to_have_value('可修改的个人新想法')
            page.route('**/api/drafts/save', lambda request: request.abort())
            page.get_by_label('个人草稿', exact=True).fill('仅旧端口尚未同步的提示词草稿')
            expect(page.get_by_text('保存结果待核实，后写内容仅在本机保留', exact=True)).to_be_visible()
            with page.expect_download() as download:
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            recovery = root / 'local-only-prompt-recovery.json'; download.value.save_as(str(recovery))
            another = WorkbenchServer(project); second_url = another.start()
            try:
                fresh = context.new_page(); navigate(fresh, 'p01', 'submitted_prompt', base=second_url)
                expect(fresh.get_by_label('个人草稿', exact=True)).to_have_value('可修改的个人新想法')
                fresh.get_by_label('导入草稿恢复文件', exact=True).set_input_files(str(recovery))
                expect(fresh.get_by_label('个人草稿', exact=True)).to_have_value('仅旧端口尚未同步的提示词草稿')
                saved(fresh); fresh.wait_for_load_state('networkidle'); fresh.close()
            finally:
                another.stop()
            page.unroute('**/api/drafts/save')
            checks['prompt_ack_cross_port_offline_not_auto_recovered_explicit_import'] = True
            navigate(page, 'p01', 'ppt'); page.get_by_text('制作与可编辑性', exact=True).click()
            expect(page.locator('.production-detail')).to_contain_text('7（text_runs；不是文本框数量）')
            expect(page.locator('.production-detail')).to_contain_text('9（native_shapes；包含文本形状）')
            expect(page.locator('.production-detail')).to_contain_text('桌面实际编辑：未评估')
            expect(page.locator('.production-detail')).to_contain_text('由输入 SVG hash 匹配的 trace 推导')
            page.evaluate('scrollTo(0,0)')
            expect(page.locator('#toast')).not_to_have_class('visible')
            page.screenshot(path=str(shots / 'production-evidence.png'), full_page=True)
            checks['production_summary_exact_field_semantics_and_unassessed_quality'] = True
            navigate(page); page.get_by_role('button', name='比较此页版本', exact=True).click(); page.get_by_label('选择同页比较版本').select_option(manifest['original_revision']); page.get_by_role('button', name='固定比较这个版本', exact=True).click()
            expect(page.get_by_label('比较版本内容', exact=True)).to_be_visible()
            assert page.locator('.page-reading[data-revision]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.revision)') == [fixed, manifest['original_revision']]
            page.evaluate('scrollTo(0,0)')
            expect(page.locator('#toast')).not_to_have_class('visible')
            page.screenshot(path=str(shots / 'fixed-original-comparison.png'), full_page=True)
            checks['same_page_same_layer_fixed_versions'] = True
            expect(page.locator('.page-image[data-image-ready=true]')).to_have_count(2)
            image_pair = page.locator('.page-image').evaluate_all('(nodes)=>nodes.map(n=>n.toDataURL())')
            assert (store.read_current(), content_identity(store.load_document())) == before
            doc = store.load_document(); changed = store.read_object_json(doc['pages'][0]['page']); changed['customer_visible']['title'] = '后台的新标题'
            editing.edit_page(project, page=changed, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='background-update')
            latest = store.load_document(); other_image = store.read_object_json(latest['pages'][1]['blueprint'])['file']
            latest['pages'][0]['blueprint'] = artifact(store, store.project_root / other_image['path'], 'blueprint', page_id='p01')
            commit(store, latest, 'synthetic-background-new-image')
            expect(page.get_by_text('当前稿已更新；这里的页、图层与比较双方仍固定。', exact=True)).to_be_visible(timeout=10000)
            assert page.locator('.page-reading[data-revision]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.revision)') == [fixed, manifest['original_revision']]
            assert page.locator('.page-image').evaluate_all('(nodes)=>nodes.map(n=>n.toDataURL())') == image_pair
            checks['background_update_only_banner_does_not_replace_comparison'] = True
            page.route('**/api/pages/p01/lineage?revision=*', lambda route: route.abort())
            page.get_by_label('选择同页比较版本').select_option(manifest['original_revision']); page.get_by_role('button', name='固定比较这个版本', exact=True).click()
            expect(page.locator('.fixed-compare-controls [role=status]')).to_contain_text('已读的固定一侧或双方仍保留')
            assert page.locator('.compare-side').get_attribute('data-revision') == manifest['original_revision']
            page.unroute('**/api/pages/p01/lineage?revision=*')
            checks['failed_comparand_keeps_previous_pinned_side'] = True
            page.set_viewport_size({'width': 1100, 'height': 800}); expect(page.get_by_role('button', name='显示比较版本', exact=True)).to_be_visible(); page.get_by_role('button', name='显示比较版本', exact=True).click()
            expect(page.get_by_label('比较版本内容', exact=True)).to_be_visible(); expect(page.get_by_label('页面内容', exact=True)).not_to_be_visible()
            page.set_viewport_size({'width': 1280, 'height': 800}); expect(page.get_by_label('页面内容', exact=True)).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.evaluate('scrollTo(0,0)')
            expect(page.locator('#toast')).not_to_have_class('visible')
            page.screenshot(path=str(shots / 'comparison-1280.png'), full_page=True)
            checks['responsive_comparison_switch_and_no_horizontal_overflow'] = True
            page.locator('.compare-side .generation-basis > summary').click()
            page.locator('.compare-side').get_by_role('button', name='查看预备提示词', exact=True).click()
            expect(page.get_by_role('navigation', name='页面层').get_by_role('button', name='预备提示词', exact=True)).to_have_attribute('aria-current', 'page')
            expect(page.get_by_label('页面内容', exact=True)).to_have_attribute('data-revision', manifest['original_revision'])
            expect(page.get_by_text('历史版本 · 只读', exact=True)).to_be_visible()
            checks['comparand_evidence_link_keeps_its_own_snapshot'] = True
            page.get_by_role('navigation', name='页面层').get_by_role('button', name='来源', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text(manifest['original_revision'][:8])
            page.get_by_role('button', name='回到此版本的内容与来源', exact=True).click()
            expect(page.get_by_role('heading', name='内容与来源', exact=True)).to_be_visible()
            assert manifest['original_revision'] in page.url
            checks['source_return_keeps_fixed_material_snapshot'] = True
            assert not errors, errors
            page.wait_for_load_state('networkidle')
            context.tracing.stop(path=str(root / 'local-only-trace.zip')); browser.close()
        static = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'
        report = {'evidence_level': 'real Chromium / real local HTTP / synthetic recorded evidence', 'checks': checks, 'manifest': manifest,
                  'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'source_assets': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in static.iterdir() if p.is_file()},
                  'environment': {'os': platform.platform(), 'python': platform.python_version(), 'browser': browser_version, 'viewports': ['1440x900', '1280x800', '1100x800']},
                  'real_host_proof': False, 'desktop_editing_verified': False, 'user_acceptance': 'not measured', 'model_calls': 0}
        (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}, ensure_ascii=False))
    finally:
        server.stop()


if __name__ == '__main__':
    main()
