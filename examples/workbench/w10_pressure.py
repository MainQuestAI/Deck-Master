"""W10/W04 sustained browser pressure using the exact W01 manifest.

Default 1,200 seconds. --smoke runs 100 seconds and NEVER qualifies the gate.
No forced GC. Windows are elapsed [300,600) and [900,1200] seconds: the
sixth through tenth and sixteenth through twentieth one-minute intervals.
Synthetic background transitions use existing reserved fixture tasks only.
"""
import argparse
import json
import platform
import re
import statistics
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, expect
from deck_master import service, ui_journal, icons
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def wait_dom(page, selector):
    # Chromium 149 / Playwright locator.wait_for retains target DOM handles in
    # DevTools Global handles. A boolean predicate avoids measuring the driver.
    # No console clearing, explicit GC, page reload, or cache purge is used.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if page.evaluate('(selector) => Boolean(document.querySelector(selector))', selector):
            return
        page.wait_for_timeout(50)
    raise AssertionError('DOM did not become ready: ' + selector)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-commit', help='Installed candidate source SHA; otherwise use checkout HEAD')
    parser.add_argument('--chromium-executable', type=Path)
    parser.add_argument('--icon-proposal', type=Path, help='Explicit synthetic proposal JSON; add local icon comparison to the same sustained gate')
    parser.add_argument('--smoke', action='store_true'); args = parser.parse_args()
    manifest = json.loads((args.fixture / 'manifest.json').read_text())
    assert manifest['factory'] == 'w01-pressure.v1' and manifest['candidate_count'] == 1500 and manifest['attempt_count'] == 4500
    args.out.mkdir(parents=True, exist_ok=False); project = args.fixture / 'project'; store = Store(project)
    info = ui_journal.project_info(project); doc = store.load_document()
    # Inspect the same snapshot once; looking up each of 150 reserved tasks
    # separately otherwise scans and parses the 1,650-record graph 150 times.
    task_status = {task['task_id']: task['status'] for ref in doc['tasks'] if (task := store.read_object_json(ref))}
    assert all(tid in task_status for tid in manifest['background_task_ids'])
    available = [tid for tid in manifest['background_task_ids'] if task_status[tid] == 'awaiting_host']
    assert available, 'No remaining background fixture tasks; preserve this manifest and explicitly replenish via factory before running.'
    icon_columns = None
    if args.icon_proposal:
        supplied=json.loads(args.icon_proposal.read_text());pid=supplied['page_id'];proposal=supplied['result'];target=proposal['proposal']['input']['targets'][0];entry=next(e for e in doc['pages'] if e['page_id']==pid);region=target['icons'][0]['svg_region']
        proposed=icons.preview(project,proposal_id=proposal['proposal_id'],page_id=pid)
        icon_columns=[{'title':'合成原图','file':store.read_object_json(entry['blueprint'])['file'],'region':region},{'title':'合成当前 SVG','file':store.read_object_json(entry['svg'])['file'],'region':region},{'title':'合成标准替换建议','file':proposed['file'],'region':region}]
    pending = None; updates = []; rows = []; errors = []; posts = []; request_counts = {}; recent = []
    duration = 100 if args.smoke else 1200; server = WorkbenchServer(project)
    try:
        url = server.start() + 'v2/#' + urlencode({'project': info['project_identity'], 'surface': 'gallery', 'layer': 'original_image', 'revision': doc['revision_id'], 'zoom': 1})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=str(args.chromium_executable) if args.chromium_executable else None); context = browser.new_context(viewport={'width': 1440, 'height': 900}, record_har_path=str(args.out / 'local-only.har'), record_har_content='omit')
            try:
                page = context.new_page(); page.set_default_timeout(60000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
                def requested(request):
                    recent.append({'elapsed': time.monotonic(), 'method': request.method, 'url': request.url}); del recent[:-100]
                    if request.method == 'POST': posts.append(request.url.split('/api/')[-1])
                    elif '/api/' in request.url:
                        key = request.url.split('/api/')[1].split('?')[0]
                        request_counts[key] = request_counts.get(key, 0) + 1
                page.on('request', requested); page.goto(url)
                wait_dom(page, '.slide-tile')
                cdp = context.new_cdp_session(page); cdp.send('Performance.enable')
                start = time.monotonic(); step = 0
                def gallery():
                    if not page.locator('.gallery-viewport').count():
                        page.get_by_role('button', name='整稿画廊', exact=True).click()
                        wait_dom(page, '.gallery-viewport')
                while time.monotonic() - start < duration:
                    phase = step % (10 if icon_columns else 8)
                    if phase == 0:
                        gallery()
                        page.locator('.gallery-viewport').evaluate('(node, fraction)=>node.scrollTop=(node.scrollHeight-node.clientHeight)*fraction', ((step // 6) % 10) / 10)
                    elif phase == 1:
                        gallery(); page.get_by_role('group', name='画廊图层').get_by_role('button', name=re.compile(r'^SVG ')).click()
                        expect(page.get_by_role('group', name='画廊图层').get_by_role('button', name=re.compile(r'^SVG '))).to_have_attribute('aria-pressed', 'true')
                    elif phase == 2:
                        page.locator('.slide-cover').first.click(); wait_dom(page, '.page-reading')
                        if page.get_by_role('combobox', name='阅读缩放').count(): page.get_by_role('combobox', name='阅读缩放').select_option('1.25')
                    elif phase == 3:
                        gallery(); page.get_by_role('group', name='画廊图层').get_by_role('button', name=re.compile(r'^原图 ')).click()
                        expect(page.get_by_role('group', name='画廊图层').get_by_role('button', name=re.compile(r'^原图 '))).to_have_attribute('aria-pressed', 'true')
                    elif phase == 4:
                        page.get_by_role('button', name='任务与交付', exact=True).click()
                        wait_dom(page, '.candidate-batch-row'); page.locator('.candidate-batch-row').first.get_by_role('button', name='比较这个候选').click()
                        wait_dom(page, '.candidate-desk'); wait_dom(page, '.candidate-column [data-image-state=ready]')
                    elif phase == 5:
                        chooser = page.get_by_role('combobox', name='选择本页候选'); values = chooser.locator('option').evaluate_all('(nodes)=>nodes.map(node=>node.value)')
                        chooser.select_option(values[(step // 6) % len(values)])
                        wait_dom(page, '.candidate-column [data-image-state=ready]'); gallery()
                    elif phase == 6 and icon_columns:
                        gallery()
                        page.evaluate('''async ({identity,columns})=>{const {iconComparison}=await import('/v2/icon-workbench.js');const {modal}=await import('/v2/dom.js');window.pressureIconView=iconComparison({info:{project_identity:identity}},columns);window.pressureIconDialog=modal('合成图标局部对照压力',window.pressureIconView.node);}''',{'identity':info['project_identity'],'columns':icon_columns})
                        wait_dom(page,'.icon-comparison canvas');page.get_by_label('显示正常页面尺寸').check();page.get_by_label('显示正常页面尺寸').uncheck();page.get_by_label('图标局部放大倍数').select_option('4')
                    elif phase == 7 and icon_columns:
                        page.evaluate('''()=>{window.pressureIconView.dispose();window.pressureIconDialog.close();delete window.pressureIconView;delete window.pressureIconDialog;}''')
                        gallery()
                    elif phase == (8 if icon_columns else 6):
                        page.get_by_role('button',name='制作总览',exact=True).click();wait_dom(page,'.matrix')
                        page.locator('.overview-todos').get_by_role('button',name='比较候选',exact=True).first.click();wait_dom(page,'.action-targets')
                    else:
                        page.get_by_role('button',name='下一页对象',exact=True).click();wait_dom(page,'.action-target');gallery()
                    if step % 2 == 0:
                        if pending:
                            value = service.task_cancel(project, task_id=pending, reason='W10 synthetic pressure cancellation'); updates.append({'step': step, 'task_id': pending, 'kind': 'cancel'}); pending = None
                        elif available:
                            pending = available.pop(0); service.task_start(project, task_id=pending, execution_ref='synthetic-pressure-background')
                            updates.append({'step': step, 'task_id': pending, 'kind': 'start'})
                    metrics = {row['name']: row['value'] for row in cdp.send('Performance.getMetrics')['metrics']}
                    pool = page.evaluate('async () => (await import("/v2/images.js")).imagePool.snapshot()')
                    row = {'elapsed_s': time.monotonic() - start, 'phase': phase, 'heap_used': metrics['JSHeapUsedSize'], 'heap_total': metrics['JSHeapTotalSize'],
                           'nodes': metrics['Nodes'], 'documents': metrics['Documents'], 'pool': pool,
                           'gallery_dom': page.locator('.slide-tile').count(), 'run_dom': page.locator('.run-task').count(), 'candidate_dom': page.locator('.candidate-batch-row').count()}
                    rows.append(row)
                    with (args.out / 'samples.jsonl').open('a') as stream: stream.write(json.dumps(row) + '\n')
                    if step % 6 == 0: print(json.dumps({'elapsed_s': round(row['elapsed_s'], 1), 'heap_mb': round(row['heap_used'] / 1048576, 2), 'updates': len(updates)}), flush=True)
                    step += 1
                    until = min(start + duration, start + step * 10)
                    if until > time.monotonic(): page.wait_for_timeout((until - time.monotonic()) * 1000)
                middle = [r['heap_used'] for r in rows if 300 <= r['elapsed_s'] < 600]
                end = [r['heap_used'] for r in rows if 900 <= r['elapsed_s'] <= 1200]
                ratio = statistics.median(end) / statistics.median(middle) - 1 if middle and end else None
                image_bounds = all(r['pool']['network_peak'] <= 6 and r['pool']['decode_peak'] <= 2 and r['pool']['thumbnails_peak'] <= 60 and r['pool']['large_peak'] <= 4 for r in rows)
                payload = {'image_bounds_pass': image_bounds, 'qualifying': not args.smoke, 'elapsed_s': time.monotonic() - start, 'synthetic': True, 'model_calls': 0,
                    'fixture': {'factory': manifest['factory'], 'project_id': doc['project_id'], 'page_count': 300, 'candidate_count': 1500, 'attempt_count': 4500},
                    'icon_comparison_included': bool(icon_columns), 'grouped_candidate_browsing_included':True, 'sampling': 'Chromium Performance.getMetrics JSHeapUsedSize after each ten-second interaction slot; no forced GC',
                    'middle_window_s': [300, 600], 'last_window_s': [900, 1200], 'middle_samples': len(middle), 'last_samples': len(end),
                    'middle_median': statistics.median(middle) if middle else None, 'last_median': statistics.median(end) if end else None, 'growth': ratio,
                    'memory_pass': ratio is not None and ratio <= .20, 'errors': errors, 'post_paths': sorted(set(posts)), 'get_counts': request_counts, 'updates': updates,
                    'environment': {'browser': browser.version, 'os': platform.platform(), 'python': platform.python_version(), 'viewport': [1440, 900],
                                    'commit': args.source_commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                                    'module': str(__import__('deck_master').__file__)}}
                (args.out / 'checks.json').write_text(json.dumps(payload, indent=2) + '\n'); print(json.dumps(payload), flush=True)
                page.screenshot(path=str(args.out / 'final-window.png'))
                assert not errors and image_bounds
                assert not any(path.startswith(('continue', 'changes/commit', 'calls/', 'candidates/adopt')) for path in posts)
                if not args.smoke: assert len(middle) >= 20 and len(end) >= 20 and ratio <= .20
            except BaseException as error:
                (args.out / 'failure.json').write_text(json.dumps({'error': str(error), 'url': page.url, 'body': page.locator('body').inner_text(), 'errors': errors, 'recent_requests': recent, 'updates': updates}, ensure_ascii=False, indent=2))
                page.screenshot(path=str(args.out / 'failure.png'))
                raise
            finally:
                context.close(); browser.close()

    finally:
        server.stop()


if __name__ == '__main__': main()
