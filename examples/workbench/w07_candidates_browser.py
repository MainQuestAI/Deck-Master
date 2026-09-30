"""Reproducible W07 browser decisions against real services; synthetic Host only.

PYTHONPATH=src python examples/workbench/w07_candidates_browser.py --out /tmp/new-w07
Raw traces remain in local-only and contain local project/session information.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master import candidates
from deck_master.models import bump_revision
from deck_master.web import WorkbenchServer
from w07_synthetic import SyntheticW07


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    flow = SyntheticW07(args.out); checks = []; errors = []; requests = []
    def check(name, condition=True):
        assert condition, name
        checks.append(name); print(name, flush=True)
    def cid(result): return result['candidate_ids'][0]
    first = cid(flow.image(flow.dispatch(reference_page='p02', instruction='First synthetic fixed-reference request'), 1))
    second = cid(flow.image(flow.dispatch(reference_page='p03', instruction='Second synthetic fixed-reference request'), 2))
    third = cid(flow.image(flow.dispatch('p02', reference_page='p01'), 3))
    server = WorkbenchServer(flow.project); url = server.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(); context = browser.new_context(viewport={'width': 1440, 'height': 1100})
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append({'method': request.method, 'url': request.url, 'body': request.post_data}) if request.method == 'POST' and '/api/candidates/' in request.url else None)
            page.goto(url + 'v2/'); page.get_by_role('button', name='任务与交付', exact=True).click()
            page.locator('.candidate-batch-row').first.wait_for()
            def open_candidate(candidate_id, image_count=2):
                row = page.locator(f'.candidate-batch-row[data-candidate-id="{candidate_id}"]')
                row.get_by_role('button', name='比较这个候选').click()
                expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', candidate_id)
                expect(page.locator('.candidate-column [data-image-state="ready"]')).to_have_count(image_count)
            open_candidate(first)
            check('two_main_columns_and_fixed_aux_reference', page.locator('.candidate-column').count() == 2 and page.locator('.candidate-reference').count() == 1)
            expect(page.locator('.candidate-reference [data-image-state=ready]')).to_have_count(1)
            page.screenshot(path=str(args.out / '01-original-candidate.png'), full_page=True)
            page.get_by_text('所选候选的生成依据', exact=True).click()
            expect(page.locator('.prompt-copy').first).to_contain_text('First synthetic fixed-reference request')
            page.get_by_label('选择本页候选').select_option(second)
            expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', second)
            page.get_by_text('所选候选的生成依据', exact=True).click()
            expect(page.locator('.prompt-copy').first).to_contain_text('Second synthetic fixed-reference request')
            expect(page.locator('.candidate-reference h3')).to_have_text('固定参考 p03')
            show = candidates.show(flow.project, candidate_id=second)
            check('candidate_switch_request_attempt_reference_identity', show['attempt']['attempt_id'] in page.locator('.candidate-basis').inner_text() and second in page.locator('.evidence-json').last.text_content())
            page.get_by_text('所选候选的生成依据', exact=True).click()
            page.get_by_role('button', name='预览采用这个候选', exact=True).click()
            adopt = page.get_by_role('button', name='采用这个候选', exact=True); expect(adopt).to_be_enabled()
            fixed_revision = page.locator('[data-side="current"]').get_attribute('data-revision')
            canvas = page.locator('[data-side="current"] canvas'); fixed_pixels = canvas.evaluate('(c) => c.toDataURL()')
            before = copy.deepcopy(flow.store.load_document()['pages'])
            flow.image(flow.dispatch(mode='auto', instruction='Synthetic concurrent automatic production'), 4)
            auto_revision = flow.store.current_revision_id()
            page.get_by_role('button', name='刷新候选与当前状态').click()
            expect(page.get_by_role('button', name='重新预览采用影响')).to_be_visible(); expect(adopt).to_be_disabled()
            check('auto_result_does_not_drift_fixed_comparison', canvas.evaluate('(c) => c.toDataURL()') == fixed_pixels and page.locator('[data-side="current"]').get_attribute('data-revision') == fixed_revision)
            check('auto_current_change_is_separate_from_trial', flow.store.load_document()['pages'][0]['blueprint'] != before[0]['blueprint'])
            page.get_by_role('button', name='重新预览采用影响').click(); expect(adopt).to_be_enabled()
            check('explicit_replan_rebinds_target_without_regeneration', page.locator('[data-side="current"]').get_attribute('data-revision') == auto_revision)
            # Actual commit reaches server; only the response is lost.
            lost = []
            def lose_response(route):
                response = route.fetch(); lost.append({'status': response.status, 'body': route.request.post_data_json}); route.abort()
            page.route('**/api/candidates/adopt', lose_response, times=1)
            before_adoptions = len(flow.store.load_document().get('candidate_adoptions', []))
            adopt.click(); expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停', exact=True)).to_be_visible()
            expect(adopt).to_be_disabled()
            # The banner appears before POST completion; wait for the injected
            # lost response before reloading, otherwise we test a pre-send abort.
            expect(page.locator('.pending-operation')).to_contain_text('尚未确认保存结果', timeout=30000)
            assert len(lost) == 1 and lost[0]['status'] == 200
            page.reload()
            page.get_by_role('button', name='核实保存结果', exact=True).click()
            expect(page.get_by_text('保存结果待核实 · 新的业务提交已暂停', exact=True)).not_to_be_visible()
            check('lost_response_refresh_recovers_original_operation_once', len(lost) == 1 and lost[0]['status'] == 200 and len(flow.store.load_document()['candidate_adoptions']) == before_adoptions + 1)
            adoption_posts = [r for r in requests if r['url'].endswith('/api/candidates/adopt')]
            check('recovery_does_not_post_second_adoption', len(adoption_posts) == 1)
            # A new two-page batch encounters an actual Page basis change after planning.
            page.get_by_role('button', name='查看当前版本', exact=True).click()
            expect(page.get_by_role('button', name='查看当前版本', exact=True)).not_to_be_visible()
            page.get_by_role('button', name='任务与交付', exact=True).click(); page.locator('.candidate-batch-row').first.wait_for()
            for value in (first, third): page.locator(f'[data-candidate-id="{value}"] input').check()
            page.get_by_role('button', name='预览所选候选的采用影响').click()
            batch_adopt = page.get_by_role('button', name='采用所选候选', exact=True); expect(batch_adopt).to_be_enabled()
            doc = flow.store.load_document(); changed = copy.deepcopy(doc)
            facts = flow.store.read_object_json(changed['pages'][1]['page']); facts['customer_visible']['title'] += ' changed by synthetic fixture'
            changed['pages'][1]['page'] = flow.store.put_json_object(facts)
            changed = bump_revision(changed, {'operation_id': 'synthetic-concurrent-page-edit', 'kind': 'task_update', 'description': 'synthetic browser conflict', 'read_set': []})
            flow.store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='synthetic-concurrent-page-edit')
            before_pages = copy.deepcopy(flow.store.load_document()['pages']); batch_adopt.click()
            expect(page.get_by_role('dialog')).to_be_visible()
            check('conflicting_batch_adopts_zero_pages', flow.store.load_document()['pages'] == before_pages)
            page.get_by_role('dialog').get_by_role('button', name='关闭', exact=True).click()
            check('conflicting_batch_preserves_both_choices', page.locator('.candidate-batch-row input:checked').count() == 2)
            page.get_by_role('button', name='预览所选候选的采用影响').click()
            expect(page.locator('.candidate-batch .field-error').filter(has_text='候选的生成依据已变化')).to_be_visible()
            page.locator(f'[data-candidate-id="{third}"] input').uncheck()
            page.get_by_role('button', name='预览所选候选的采用影响').click(); expect(batch_adopt).to_be_enabled(); batch_adopt.click()
            expect(page.locator('.candidate-batch .success-note')).to_contain_text('已整批采用 1 页')
            check('explicit_subset_new_plan_new_operation', flow.store.load_document()['pages'][1] == before_pages[1])
            # SVG repair preserves Page, original, prompt identity and adds no image attempt.
            doc = flow.store.load_document(); page_before = copy.deepcopy(doc['pages'][0]); svg_id = cid(flow.svg(flow.dispatch(stage='repair'), 5))
            after = flow.store.load_document(); check('svg_trial_preserves_current_and_call_count', after['pages'] == doc['pages'] and after.get('call_budget') == doc.get('call_budget'))
            page.get_by_role('button', name='刷新候选列表').click(); open_candidate(svg_id, image_count=1)
            page.get_by_role('button', name='预览采用这个候选').click(); expect(page.get_by_role('button', name='采用这个候选', exact=True)).to_be_enabled()
            page.get_by_role('button', name='采用这个候选', exact=True).click(); expect(page.get_by_text('这个候选已是当前采用', exact=True)).to_be_visible()
            current = flow.store.load_document()['pages'][0]
            check('svg_adoption_retains_page_original_no_fake_ppt_preview', current['page'] == page_before['page'] and current['blueprint'] == page_before['blueprint'] and current['ppt_preview'] is None)
            page.set_viewport_size({'width': 820, 'height': 980}); page.screenshot(path=str(args.out / '02-svg-narrow.png'), full_page=True)
            check('narrow_viewport_no_horizontal_overflow', page.evaluate('() => document.documentElement.scrollWidth <= innerWidth + 1'))
            page.get_by_role('button', name='查看任务与交付', exact=True).click(); page.get_by_text('采用后的整稿制作', exact=True).click()
            page.get_by_role('button', name='更新整稿 PPT', exact=True).click(); expect(page.get_by_role('dialog')).to_be_visible()
            check('assemble_quality_dependency_refusal_visible', flow.store.load_document()['outputs']['pptx'] is None)
            check('no_browser_javascript_errors', not errors)
            context.tracing.stop(path=str(args.out / 'local-only' / 'trace.zip')); browser.close()
    finally:
        server.stop()
        (args.out / 'checks.json').write_text(json.dumps({'evidence': 'real browser and service; synthetic Host/tool events only', 'checks': checks, 'errors': errors}, ensure_ascii=False, indent=2) + '\n')
        (args.out / 'local-only' / 'candidate-requests.json').write_text(json.dumps(requests, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__': main()
