"""Actual Chromium gallery proof. Synthetic data, no HOME or model calls.

Use a new --out directory. Share checks.json / screenshots only: raw traces
contain local session headers. The 80-page cache walk is NOT 300x5x3 pressure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

from deck_master import gallery_state, samples, thumbnails, ui_journal, workbench
from deck_master.models import bump_revision, content_identity
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    root = Path(args.out).absolute(); root.mkdir(parents=True, exist_ok=False)
    shots = root / 'screenshots'; shots.mkdir()
    project = root / 'gallery'; manifest = samples.create_gallery_sample(project, readonly=False)
    large_project = root / 'cache-walk'; large_manifest = samples.create_gallery_sample(large_project, page_count=80)
    store = Store(project); doc = store.load_document(); info = ui_journal.project_info(project)
    before = (store.read_current(), content_identity(doc))
    # Persisted personal opinion on the same fixed content basis, no review pass.
    ui_journal.save(project, draft={'schema_version': 'ui_draft.v1', 'project_id': info['project_id'],
        'project_identity': info['project_identity'], 'draft_id': 'gallery-note',
        'target': {'scope': 'page', 'page_id': 'p05', 'layer': 'content'}, 'base_revision': doc['revision_id'],
        'base_ref': doc['pages'][4]['page'], 'content': {'text': 'Synthetic personal opinion for gallery filtering.'}, 'pending': None})
    checks = {}; metrics = []; browser_errors = []; timings = []; server = WorkbenchServer(project); url = server.start()
    large_server = WorkbenchServer(large_project); large_url = large_server.start()
    large_info = ui_journal.project_info(large_project)
    initial = {'schema_version': 'ui_gallery.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
        'revision_id': doc['revision_id'], 'layer': 'original_image', 'mode': 'grid', 'columns': 3,
        'selected_page_ids': [], 'references': [], 'filter': {'chapter_id': None, 'status': 'all'},
        'anchor': {'page_id': None, 'offset': 0}, 'zoom': {'synchronized': True, 'scale': 1}}

    def reset():
        saved = gallery_state.get(project)['record']
        gallery_state.save(project, state=initial, expected_etag=saved['etag'] if saved else None)

    def gallery_url(base=url, details=info, revision=doc['revision_id']):
        return base + 'v2/#' + urlencode({'project': details['project_identity'], 'surface': 'gallery',
            'layer': 'original_image', 'revision': revision, 'zoom': 1})

    def card(page, page_id): return page.locator(f'.gallery-card[data-page-id="{page_id}"]')

    def ready(page):
        page.wait_for_function('''() => {
          const port = document.querySelector('.gallery-viewport'); if (!port) return false;
          const rect = port.getBoundingClientRect();
          const inView = node => {
            const r = node.getBoundingClientRect(); return r.bottom > rect.top && r.top < Math.min(innerHeight, rect.bottom);
          };
          const visible = [...port.querySelectorAll('.pooled-image')].filter(inView);
          return [...port.querySelectorAll('.gallery-card')].some(inView) && visible.every(node => node.dataset.imageState === 'ready');
        }''')

    def settled(page):
        page.wait_for_function('''async () => {
          const value = (await import('/v2/images.js')).imagePool.snapshot();
          return value.network === 0 && value.decode === 0 && !document.querySelector('.pooled-image[data-image-state="loading"]');
        }''')

    def snapshot(page, name):
        value = page.evaluate('async () => (await import("/v2/images.js")).imagePool.snapshot()')
        assert value['network_peak'] <= 6 and value['decode_peak'] <= 2
        assert value['thumbnails_peak'] <= 60 and value['large_peak'] <= 4
        metrics.append({'scene': name, **value}); return value

    def saved(page): expect(page.get_by_text('画廊选择已保存', exact=True)).to_be_visible()

    def change_layer(page, label):
        page.get_by_role('navigation', name='画廊图层').get_by_role('button', name=label, exact=True).click()
        expect(page.get_by_role('navigation', name='画廊图层').get_by_role('button', name=label, exact=True)).to_have_attribute('aria-pressed', 'true')

    def shot(page, name): page.screenshot(path=str(shots / (name + '.png')), full_page=True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); browser_version = browser.version
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='zh-CN')
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page(); page.on('pageerror', lambda error: browser_errors.append(str(error)))
            image_requests = []; network_active = set(); network_peak = [0]
            def requested(request):
                if any(path in request.url for path in ['/api/thumbnail', '/api/file?']):
                    image_requests.append(request.url.split(url)[-1]); network_active.add(request)
                    network_peak[0] = max(network_peak[0], len(network_active))
            page.on('request', requested); page.on('requestfinished', lambda request: network_active.discard(request)); page.on('requestfailed', lambda request: network_active.discard(request))
            reset(); started = time.perf_counter(); page.goto(gallery_url()); ready(page)
            timings.append({'cache': 'cold derivatives', 'viewport': [1440, 900], 'seconds': time.perf_counter() - started})
            assert page.locator('.gallery-card').count() < 30
            assert not any('/api/file?' in item for item in image_requests)
            checks['cold_progressive_thumbnails_no_original_batch'] = True
            card(page, 'p01').get_by_role('checkbox').check(); card(page, 'p02').get_by_role('checkbox').check()
            card(page, 'p01').get_by_role('button', name='☆ 标记原图参考', exact=True).click(); saved(page)
            reference = gallery_state.get(project)['record']['state']['references'][0]
            assert reference['revision_id'] == doc['revision_id']
            assert reference['original_ref'] == store.read_object_json(doc['pages'][0]['blueprint'])['file']
            page.get_by_label('筛选章节', exact=True).select_option('chapter-2')
            expect(page.locator('.gallery-selection')).to_contain_text('筛选外选中 2 页')
            page.get_by_role('button', name='并排比较', exact=True).click(); ready(page)
            assert page.locator('.gallery-card').evaluate_all('(nodes)=>nodes.map(node=>node.dataset.pageId)') == ['p01', 'p02']
            checks['selection_across_chapter_filter_and_fixed_original_reference'] = True
            zooms = page.locator('.is-comparison select'); zooms.nth(0).select_option('1.5')
            expect(zooms.nth(1)).to_have_value('1.5')
            page.get_by_label('同步缩放', exact=True).uncheck(); zooms.nth(0).select_option('2')
            expect(zooms.nth(1)).to_have_value('1')
            page.get_by_label('同步缩放', exact=True).check(); zooms.nth(0).select_option('1'); ready(page)
            assert page.locator('.compare-image canvas').evaluate_all('(nodes)=>nodes.every(n=>getComputedStyle(n).objectFit==="contain")')
            shot(page, 'compare-original-1440'); checks['comparison_contain_sync_and_independent_zoom'] = True
            change_layer(page, 'SVG'); ready(page)
            expect(card(page, 'p01').get_by_text('SVG · 未生成', exact=True)).to_be_visible()
            assert card(page, 'p01').locator('canvas').count() == 0 and card(page, 'p02').locator('canvas').count() == 1
            change_layer(page, 'PPT'); expect(card(page, 'p02').get_by_text('PPT · 未生成', exact=True)).to_be_visible()
            assert page.locator('.gallery-card canvas').count() == 0
            assert page.locator('.gallery-card').evaluate_all('(nodes)=>new Set(nodes.map(n=>n.dataset.revision)).size') == 1
            checks['missing_svg_and_ppt_never_fill_from_other_layer'] = True
            page.get_by_role('button', name='回到联系表', exact=True).click()
            page.get_by_label('筛选章节', exact=True).select_option('')
            page.get_by_label('筛选页面状态', exact=True).select_option('stale'); ready(page)
            assert page.locator('.gallery-card').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.pageId)') == ['p11', 'p21']
            shot(page, 'stale-ppt-1440'); checks['stale_ppt_is_visible_without_fake_quality_pass'] = True
            change_layer(page, '原图'); page.get_by_label('筛选页面状态', exact=True).select_option('attention')
            assert page.locator('.gallery-card').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.pageId)') == ['p05']
            page.get_by_label('筛选页面状态', exact=True).select_option('references')
            assert page.locator('.gallery-card').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.pageId)') == ['p01']
            page.get_by_label('筛选页面状态', exact=True).select_option('missing')
            assert page.locator('.gallery-card').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.pageId)') == ['p03', 'p14']
            checks['fixed_revision_personal_opinion_reference_missing_filters'] = True
            page.get_by_label('筛选页面状态', exact=True).select_option('all')
            for columns in ['2', '4', '3']:
                page.get_by_label('联系表列数', exact=True).select_option(columns); ready(page)
                assert len(page.locator('.gallery-grid').evaluate('(n)=>getComputedStyle(n).gridTemplateColumns.split(" ")')) == int(columns)
            checks['two_three_four_columns'] = True
            page.get_by_role('button', name='连续阅读', exact=True).click(); ready(page)
            page.locator('.gallery-viewport').evaluate('(node)=>node.scrollTop=8100'); ready(page)
            scroll = page.locator('.gallery-viewport').evaluate('(node)=>node.scrollTop')
            first = page.locator('.gallery-open').first; page_id = first.locator('..').get_attribute('data-page-id')
            first.evaluate('(node)=>node.focus({preventScroll:true})'); page.keyboard.press('Enter')
            expect(page.get_by_role('button', name='回到整稿画廊', exact=True)).to_be_visible()
            page.locator('#view-title').focus(); page.keyboard.press('Escape'); expect(page.locator('.gallery-viewport')).to_have_attribute('data-mode', 'continuous'); ready(page)
            restored_scroll = page.locator('.gallery-viewport').evaluate('(node)=>node.scrollTop')
            assert abs(restored_scroll - scroll) < 30, {'before': scroll, 'after': restored_scroll, 'state': gallery_state.get(project)['record']['state']['anchor']}
            expect(card(page, page_id).locator('.gallery-open')).to_be_focused()
            page.keyboard.press('ArrowDown')
            # Cross multiple animation frames: browser scroll anchoring must not
            # repeatedly advance virtual spacers and remove the focused page.
            page.evaluate('async()=>{for(let i=0;i<6;i++) await new Promise(requestAnimationFrame);}');
            focused = page.evaluate('document.activeElement.closest("[data-page-id]")?.dataset.pageId')
            assert focused is not None
            assert focused != page_id
            page.keyboard.press('Enter'); expect(page.get_by_role('button', name='回到整稿画廊', exact=True)).to_be_visible()
            assert 'page=' + focused in page.url
            page.locator('#view-title').focus(); page.keyboard.press('Escape'); ready(page)
            checks['continuous_anchor_arrow_enter_escape_and_focus_restore'] = True
            snapshot(page, 'continuous-return')
            page.get_by_role('button', name='联系表', exact=True).click()
            page.locator('.gallery-viewport').evaluate('(node)=>node.scrollTop=0'); ready(page); saved(page)
            shot(page, 'grid-original-1440')

            # Real receipt written, network ACK intentionally lost; later selection
            # must wait behind the frozen retry and then receive a second ACK.
            once = [True]
            def drop_ack(route):
                if route.request.method == 'POST' and once[0]:
                    once[0] = False; route.fetch(); route.abort('failed')
                else: route.continue_()
            page.route('**/api/gallery', drop_ack)
            card(page, 'p04').get_by_role('checkbox').check()
            expect(page.get_by_role('button', name='核实画廊保存', exact=True)).to_be_visible()
            card(page, 'p05').get_by_role('checkbox').check()
            page.get_by_role('button', name='核实画廊保存', exact=True).click(); saved(page)
            assert gallery_state.get(project)['record']['state']['selected_page_ids'] == ['p01', 'p02', 'p04', 'p05']
            card(page, 'p06').get_by_role('checkbox').click()
            expect(card(page, 'p06').get_by_role('checkbox')).not_to_be_checked()
            expect(page.locator('.gallery-selection')).to_contain_text('已选 4 页')
            page.unroute('**/api/gallery', drop_ack); checks['lost_ack_frozen_retry_then_later_selection'] = True
            page.set_viewport_size({'width': 1280, 'height': 800})
            page.get_by_role('button', name='并排比较', exact=True).click(); ready(page)
            assert page.locator('.is-comparison .gallery-card canvas').count() == 4
            assert page.locator('.is-comparison select').count() == 4
            shot(page, 'compare-four-1280'); snapshot(page, 'four-image-comparison-1280')
            page.get_by_role('button', name='回到联系表', exact=True).click()
            page.set_viewport_size({'width': 1440, 'height': 900}); ready(page); saved(page)

            before_read = gallery_state.get(project)['record']
            other = context.new_page(); other.goto(gallery_url()); ready(other)
            other.wait_for_timeout(450)  # exceeds save debounce: restoration itself must not write
            assert gallery_state.get(project)['record'] == before_read
            checks['opening_another_window_does_not_save_restored_anchor'] = True
            page.get_by_label('联系表列数', exact=True).select_option('4'); saved(page)
            other.get_by_label('联系表列数', exact=True).select_option('2')
            other.get_by_role('button', name='比较窗口选择', exact=True).click()
            other.get_by_role('button', name='保存此窗口选择', exact=True).click(); saved(other)
            assert gallery_state.get(project)['record']['state']['columns'] == 2
            other.close(); checks['two_window_cas_explicit_selection_resolution'] = True

            context.set_offline(True)
            assert page.locator('canvas').count() > 0
            page.get_by_role('button', name='任务与交付', exact=True).click()
            expect(page.locator('.notice')).to_contain_text('已显示的工作面仍属于顶栏标明的版本')
            assert page.locator('canvas').count() > 0
            context.set_offline(False); page.get_by_role('button', name='整稿画廊', exact=True).click(); ready(page)
            checks['offline_retains_readable_fixed_gallery'] = True
            assert (store.read_current(), content_identity(store.load_document())) == before
            checks['all_personal_interactions_leave_document_unchanged'] = True
            snapshot(page, 'personal-state-recovery'); settled(page)
            context.tracing.stop(path=str(root / 'browser-trace.zip')); context.close()

            # Existing images warmed through the real backend cache, not base64 or
            # an in-memory fake. Navigation includes all project JSON reads.
            for entry in doc['pages']:
                if entry['blueprint']: thumbnails.request(project, ref=store.read_object_json(entry['blueprint'])['file'])
            thumbnails.QUEUE.drain()
            for width, height in [(1280, 800), (1440, 900)]:
                for sample in range(3):
                    reset(); warm = browser.new_context(viewport={'width': width, 'height': height}, locale='zh-CN')
                    p = warm.new_page(); p.on('pageerror', lambda error: browser_errors.append(str(error)))
                    started = time.perf_counter(); p.goto(gallery_url()); ready(p)
                    seconds = time.perf_counter() - started
                    card(p, 'p01').get_by_role('checkbox').check()
                    expect(p.locator('.gallery-selection')).to_contain_text('已选 1 页')
                    # Button action is part of actionable timing, not just paint.
                    seconds = time.perf_counter() - started
                    timings.append({'cache': 'warm service and derivatives', 'viewport': [width, height], 'sample': sample, 'seconds': seconds})
                    assert seconds <= 2, timings[-1]
                    assert p.locator('.gallery-card strong').first.is_visible()
                    if sample == 0: shot(p, f'grid-warm-{width}')
                    snapshot(p, f'warm-{width}-{sample}'); saved(p); settled(p); warm.close()
            checks['warm_30_page_first_actionable_le_2s_both_viewports'] = True

            reset(); fault = browser.new_context(viewport={'width': 1280, 'height': 800}); p = fault.new_page()
            fail_once = [True]
            def fail_image(route):
                if fail_once[0]: fail_once[0] = False; route.abort('failed')
                else: route.continue_()
            p.route('**/api/thumbnail-file?*', fail_image); p.goto(gallery_url())
            retry = p.get_by_role('button', name='重试图片', exact=True); expect(retry).to_be_visible()
            failed_card = retry.locator('..').locator('..'); failed_id = failed_card.get_attribute('data-page-id')
            expect(failed_card).to_have_attribute('data-layer', 'original_image')
            retry.click(); ready(p)
            card(p, failed_id).get_by_role('checkbox').check(); ready(p)
            expect(card(p, failed_id).get_by_role('checkbox')).to_be_checked()
            assert card(p, failed_id).locator('canvas').count() == 1
            checks['image_failure_keeps_identity_selection_and_recovers'] = True
            saved(p); settled(p); fault.close()

            # UI keeps old comparison after a genuine new revision is committed.
            reset(); history = browser.new_context(viewport={'width': 1440, 'height': 900}); p = history.new_page(); p.goto(gallery_url()); ready(p)
            card(p, 'p01').get_by_role('checkbox').check(); card(p, 'p02').get_by_role('checkbox').check(); saved(p)
            changed = bump_revision(doc, {'kind': 'task_update', 'operation_id': 'gallery-order-fixture', 'description': 'Synthetic reorder for page identity proof', 'read_set': []})
            changed['pages'].reverse(); store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='gallery-order-fixture')
            change_layer(p, 'SVG'); expect(p.get_by_text('历史版本 · 只读', exact=True)).to_be_visible()
            assert p.locator('.gallery-card').first.get_attribute('data-revision') == doc['revision_id']
            p.get_by_role('button', name='查看当前版本', exact=True).click(); ready(p); saved(p)
            assert gallery_state.get(project)['record']['state']['selected_page_ids'] == ['p01', 'p02']
            checks['new_revision_only_notifies_and_reorder_keeps_page_ids'] = True
            settled(p); history.close()

            walk = browser.new_context(viewport={'width': 1440, 'height': 900}); p = walk.new_page()
            p.on('pageerror', lambda error: browser_errors.append(str(error)))
            p.goto(gallery_url(large_url, large_info, large_info['revision_id'])); ready(p)
            viewport = p.locator('.gallery-viewport'); max_nodes = 0
            distance = 0
            while True:
                viewport.evaluate('(node, top)=>node.scrollTop=top', distance); ready(p); settled(p)
                max_nodes = max(max_nodes, p.locator('.gallery-card').count())
                geometry = viewport.evaluate('(n)=>({top:n.scrollTop,end:n.scrollHeight-n.clientHeight})')
                if geometry['top'] >= geometry['end'] - 1: break
                distance += 300
            stats = snapshot(p, '80-page-thumbnail-cache-walk')
            assert stats['thumbnails'] == 60 and stats['closed_bitmaps'] > 0 and max_nodes < 25
            viewport.evaluate('(n)=>n.scrollTop=0'); ready(p)
            card(p, 'p01').locator('.gallery-open').click()
            for page_id in ['p01', 'p02', 'p04', 'p05', 'p06', 'p07']:
                p.get_by_label('转到页面', exact=True).select_option(page_id)
                expect(p.locator('#view-title')).to_contain_text(f'第 {int(page_id[1:])} 页 ·')
                expect(p.locator('.page-image')).to_be_visible()
                p.wait_for_function('()=>document.querySelector(".pooled-image")?.dataset.imageState==="ready"')
            stats = snapshot(p, 'six-large-images-through-page-reader')
            assert stats['large'] == 4 and stats['large_peak'] == 4 and stats['active_object_urls'] == 0
            checks['shared_six_network_two_decode_sixty_thumbnail_four_large_lru'] = True
            checks['offscreen_dom_removed_and_bitmaps_closed'] = {'max_gallery_nodes': max_nodes, 'closed_bitmaps': stats['closed_bitmaps']}
            walk.close(); browser.close()
            assert not browser_errors, browser_errors
            assert network_peak[0] <= 6, network_peak
            def machine(key):
                return subprocess.check_output(['sysctl', '-n', key], text=True).strip() if sys.platform == 'darwin' else 'unavailable'
            checkout = Path(__file__).resolve().parents[2]
            source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
            assets = checkout / 'src/deck_master/resources/static/v2'
            report = {'evidence_level': 'real Chromium / real local service / explicitly synthetic objects',
                'core_baseline': 'e5e7892561400a06003971c8ad9239fb5e3b62af',
                'source_commit': source_commit,
                'ui_asset_sha256': {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(assets.iterdir()) if file.is_file()},
                'environment': {'os': platform.platform(), 'hardware': machine('hw.model'), 'memory_bytes': machine('hw.memsize'),
                    'cpu': machine('machdep.cpu.brand_string'), 'python': sys.version.split()[0], 'chromium': browser_version},
                'fixture': manifest, 'image_cache_walk_fixture': large_manifest, 'timings': timings, 'image_metrics': metrics,
                'network_event_peak': network_peak[0], 'initial_session_image_request_count': len(image_requests), 'checks': checks,
                'browser_errors': browser_errors, 'source_bytes': sum(path.stat().st_size for path in store.objects_dir.rglob('*.png')),
                'total_object_count': sum(1 for path in store.objects_dir.rglob('*') if path.is_file()),
                'background_load': 'bounded derivative queue and personal-state saves; no model calls',
                'full_300x5x3_pressure': 'pending W07 Candidate contract; the 80-page walk only verifies cache bounds',
                'human_30_second_observation': 'not measured', 'twenty_minute_heap': 'W10 owner; not measured', 'real_home_changed': False}
            (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}))
    except Exception:
        (root / 'partial-checks.json').write_text(json.dumps({'checks': checks, 'timings': timings, 'browser_errors': browser_errors}, ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        server.stop(); large_server.stop(); thumbnails.QUEUE.drain()


if __name__ == '__main__': main()
