"""Isolated W04 core/HTTP proof; not the W04 gallery browser acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
import time
from urllib.parse import urlencode

from PIL import Image
from playwright.sync_api import expect, sync_playwright

from deck_master import gallery_state, samples, thumbnails, ui_journal
from deck_master.models import content_identity
from deck_master.pipeline import artifact
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    root = Path(args.out).absolute(); root.mkdir(parents=True, exist_ok=False)
    project = root / 'project'; samples.create_sample(project, page_count=30, readonly=False)
    store = Store(project); doc = store.load_document()
    before = (store.read_current(), content_identity(doc))
    originals = [store.read_object_json(entry['blueprint'])['file'] for entry in doc['pages']]
    cold_started = time.monotonic()
    queued = [thumbnails.request(project, ref=ref) for ref in originals]
    thumbnails.QUEUE.drain()
    cold_seconds = time.monotonic() - cold_started
    warm_started = time.monotonic()
    warm = [thumbnails.request(project, ref=ref) for ref in originals]
    warm_seconds = time.monotonic() - warm_started
    assert all(result['status'] == 'ready' and result['cache'] == 'hit' for result in warm)
    source = root / 'next-original.png'; Image.new('RGB', (1600, 900), '#415263').save(source)
    new_artifact = artifact(store, source, 'blueprint', page_id='p01')
    thumbnails.QUEUE.drain()
    assert thumbnails.request(project, ref=store.read_object_json(new_artifact)['file'])['status'] == 'ready'
    info = ui_journal.project_info(project)
    value = {'schema_version': 'ui_gallery.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
             'revision_id': info['revision_id'], 'layer': 'original_image', 'mode': 'compare', 'columns': 3,
             'selected_page_ids': ['p01', 'p03'], 'references': [{'page_id': 'p01', 'revision_id': info['revision_id'], 'original_ref': originals[0]}],
             'filter': {'chapter_id': None, 'status': 'all'}, 'anchor': {'page_id': 'p03', 'offset': .4},
             'zoom': {'synchronized': True, 'scale': 1.25}}
    saved = gallery_state.save(project, state=value)['record']
    assert gallery_state.get(project)['record'] == saved
    assert (store.read_current(), content_identity(store.load_document())) == before
    malicious = store.put_blob(b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="32" onload="window.injected=true"><script>window.injected=true;fetch("http://127.0.0.1:9/forbidden")</script><rect width="64" height="32" fill="red"/></svg>', ext='svg')
    server = WorkbenchServer(project); url = server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); browser_version = browser.version
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            requests = []; violations = []
            page.on('request', lambda request: requests.append(request.url))
            page.add_init_script("addEventListener('securitypolicyviolation', e => { (window.cspViolations ||= []).push(e.violatedDirective); });")
            page.goto(url + 'v2/')
            expect(page.get_by_role('heading', name='制作总览', exact=True)).to_be_visible()
            source_url = '/api/file?' + urlencode(malicious)
            page.evaluate('''async (path) => {
                const blob = await (await fetch(path)).blob();
                const url = URL.createObjectURL(blob); const image = new Image();
                image.src = url; document.body.append(image); await image.decode();
                image.remove(); URL.revokeObjectURL(url);
            }''', source_url)
            assert page.evaluate('window.injected === undefined')
            assert not any('/forbidden' in request for request in requests)
            violations = page.evaluate('window.cspViolations || []')
            assert 'img-src' not in violations
            status = page.request.get(url + 'api/health').json()
            assert 'thumbnails.v1' in status['ui_capabilities']
            browser.close()
        report = {'evidence_level': 'core/HTTP and targeted real Chromium CSP proof; synthetic data',
                  'baseline_commit': 'f3c9b617b868748ea09765ff072858f563f65b8f',
                  'environment': {'os': platform.platform(), 'python': sys.version.split()[0], 'chromium': browser_version},
                  'fixture': {'pages': 30, 'candidate_objects': 'deferred to W07', 'real_model_calls': 0, 'source_dimensions': [960, 540]},
                  'thumbnail_derivation': {'cold_30_seconds': round(cold_seconds, 6), 'warm_30_seconds': round(warm_seconds, 6),
                    'note': 'core batch measurements only, not UI first-screen SLO', 'initial_states': [result['status'] for result in queued],
                    'queue_metrics': thumbnails.QUEUE.metrics(), 'all_warm_hits': True,
                    'dimensions': [[record['width'], record['height']] for record in warm],
                    'source_bytes': sum(len(store.read_object_bytes(ref)) for ref in originals), 'thumbnail_bytes': sum(record['bytes'] for record in warm)},
                  'checks': {'new_artifact_background_warming': True, 'gallery_etag_ack': True, 'fixed_reference_and_selection': True,
                    'document_and_content_identity_unchanged': True, 'blob_svg_scripts_inert': True,
                    'blob_image_allowed': True, 'svg_external_script_request_absent': True},
                  'gallery_frontend_verified': False, 'full_300x5x3_fixture_verified': False, 'real_home_changed': False}
        (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': 'verified', 'report': str(root / 'checks.json'), 'checks': len(report['checks'])}))
    finally:
        server.stop(); thumbnails.QUEUE.drain()


if __name__ == '__main__': main()
