"""W07 trial form, fixed reference, failed image and read-only browser proof."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect
from deck_master import candidates
from deck_master.web import WorkbenchServer
from w07_synthetic import SyntheticW07


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False); flow = SyntheticW07(args.out); checks = []; errors = []
    def check(name, condition=True):
        assert condition, name
        checks.append(name); print(name, flush=True)
    server = WorkbenchServer(flow.project); url = server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); context = browser.new_context(viewport={'width': 1440, 'height': 1100})
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url + 'v2/'); page.get_by_role('button', name='整稿画廊', exact=True).wait_for()
            identity = parse_qs(urlsplit(page.url).fragment)['project'][0]
            initial = flow.store.load_document(); revision = initial['revision_id']
            def open_page(rev):
                page.goto(url + 'v2/#' + urlencode({'project': identity, 'surface': 'page', 'page': 'p01', 'layer': 'original_image', 'revision': rev}))
                page.get_by_text('试作这页原图', exact=True).click()
            open_page(revision)
            text = '保留本页全部事实，沿用第二页分区；这是明确标记的合成短要求。'
            page.get_by_label('本页试作短要求').fill(text); page.get_by_label('固定参考原图').select_option('p02')
            # Allow the actual project journal ACK; no timing-based sleep.
            page.wait_for_function("() => [...document.querySelectorAll('.personal-draft [role=status]')].some(n => n.textContent.includes('已保存到项目'))")
            page.reload(); page.get_by_text('试作这页原图', exact=True).click(); expect(page.get_by_label('本页试作短要求')).to_have_value(text)
            check('trial_short_instruction_and_fixed_reference_survive_reload', page.locator('.trial-reference').inner_text().startswith('p02') or 'p02' in page.locator('.trial-reference').inner_text())
            page.get_by_role('button', name='预览本页试作', exact=True).click(); commit = page.get_by_role('button', name='保存并交接这次试作', exact=True)
            expect(commit).to_be_enabled(); commit.click(); expect(page.get_by_role('button', name='任务与交付', exact=True)).to_have_attribute('aria-current', 'page')
            rows = [flow.store.read_object_json(ref) for ref in flow.store.load_document()['tasks']]
            trial = next(task for task in rows if task.get('stage_request', {}).get('mode') == 'trial')
            check('browser_trial_dispatches_one_explicit_fixed_reference_task', trial['scope_pages'] == ['p01'] and len(trial['stage_request']['references']) == 1)
            before = flow.store.load_document(); result = flow.image(trial, 8); candidate_id = result['candidate_ids'][0]
            check('host_return_keeps_current_slots_untouched', before['pages'] == flow.store.load_document()['pages'])
            page.get_by_role('button', name='刷新候选列表').click(); row = page.locator(f'.candidate-batch-row[data-candidate-id="{candidate_id}"]'); row.wait_for()
            value = candidates.show(flow.project, candidate_id=candidate_id)
            check('browser_short_request_and_reference_reach_frozen_request', text in value['request']['input']['prompt'] and value['reference_sources'][0]['page_id'] == 'p02')
            # Fail only this candidate image's first byte fetch, then retry unchanged identity.
            digest = value['artifact']['file']['sha256']; failure_count = []
            def fail_image(route):
                if parse_qs(urlsplit(route.request.url).query).get('sha256') == [digest]:
                    failure_count.append(1); route.abort()
                else: route.continue_()
            page.route('**/api/file?*', fail_image)
            row.get_by_role('button', name='比较这个候选').click(); expect(page.locator('[data-side=candidate] [data-image-state=failed]')).to_have_count(1)
            check('failed_image_keeps_candidate_identity', page.locator('.candidate-desk').get_attribute('data-candidate-id') == candidate_id)
            page.unroute('**/api/file?*', fail_image); page.locator('[data-side=candidate]').get_by_role('button', name='重试图片').click()
            expect(page.locator('[data-side=candidate] [data-image-state=ready]')).to_have_count(1)
            check('image_retry_restores_same_candidate', bool(failure_count))
            page.get_by_role('button', name='放大固定参考图').click(); expect(page.get_by_role('dialog').locator('[data-image-state=ready]')).to_have_count(1)
            page.keyboard.press('Escape'); expect(page.get_by_role('dialog')).not_to_be_visible()
            stats = page.evaluate("async () => (await import('/v2/images.js')).imagePool.snapshot()")
            check('reference_modal_releases_lease_within_image_limits', stats['large'] <= 4 and stats['thumbnails'] <= 60 and stats['pinned'] <= 3)
            # An explicitly old route remains read-only despite live candidates being visible.
            open_page(revision); expect(page.get_by_label('本页试作短要求')).not_to_be_editable(); expect(page.get_by_role('button', name='预览本页试作', exact=True)).to_be_disabled()
            check('historical_trial_entry_read_only')
            check('no_browser_javascript_errors', not errors)
            context.tracing.stop(path=str(args.out / 'local-only' / 'trace.zip')); browser.close()
    finally:
        server.stop(); (args.out / 'checks.json').write_text(json.dumps({'evidence': 'real browser/services; synthetic Host only', 'checks': checks, 'errors': errors}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__': main()
