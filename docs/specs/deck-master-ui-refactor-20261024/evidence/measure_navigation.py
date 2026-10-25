"""Reproducible UI observations, synthetic projects; not a production SLA benchmark.

Prepare once with current src on PYTHONPATH and --prepare. Measure the same saved
inputs with each version's src on PYTHONPATH, --label and a distinct --output.
Only the preparation step imports repository fixture builders. No model calls.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--projects', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--label')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    from deck_master.store import Store
    from deck_master.models import canonical_json_bytes
    if args.prepare:
        from deck_master.samples import create_gallery_sample
        sys.path.insert(0, str(args.repo/'tests/rebuild'))
        from test_candidates import store as candidate_store, candidate
        from test_workbench_actions import commit
        args.projects.mkdir(parents=True, exist_ok=False)
        cases = []
        for pages in [24, 100]:
            root = args.projects/f'gallery-{pages}'
            create_gallery_sample(root, page_count=pages, readonly=False)
            cases.append({'case': root.name, 'path': root.name, 'pages': pages, 'candidates': 0})
        for count in [1, 500]:
            root = args.projects/f'history-{count}';root.mkdir()
            store = candidate_store.__wrapped__(root)
            candidate(store, 'p01')
            doc = store.load_document()
            original = store.read_object_json(doc['candidates'][0])
            index = next(i for i,ref in enumerate(doc['tasks']) if store.read_object_json(ref)['task_id'] == original['task_id'])
            task = store.read_object_json(doc['tasks'][index])
            for i in range(1, count):
                item = {**copy.deepcopy(original), 'candidate_id':f'synthetic-history-{i}'}
                ref = store.put_json_object(item);doc['candidates'].append(ref);task['candidate_refs'].append(ref)
            doc['tasks'][index] = store.put_json_object(task)
            page = store.read_object_json(doc['pages'][0]['page'])
            page['customer_visible']['title'] = 'Synthetic newer manuscript'
            doc['pages'][0]['page'] = store.put_json_object(page)
            commit(store, doc, 'synthetic-history-load')
            cases.append({'case': root.name, 'path': str(store.project_root.relative_to(args.projects)), 'pages': 2, 'candidates': count})
        for case in cases:
            case['document_sha256'] = hashlib.sha256(canonical_json_bytes(Store(args.projects/case['path']).load_document())).hexdigest()
        (args.projects/'manifest.json').write_text(json.dumps(cases, indent=2)+'\n')
        print(json.dumps({'prepared':len(cases),'model_calls':0}));return
    from deck_master.web import WorkbenchServer
    from deck_master.local_runtime import BUILD_ID
    from playwright.sync_api import sync_playwright
    import deck_master
    cases = json.loads((args.projects/'manifest.json').read_text());results=[]
    surfaces=[('content','内容与页序','.content-sources'),('gallery','整稿画廊','.gallery-view'),
              ('style','风格校准','.style-calibration'),('runs','任务与交付','.run-desk'),('overview','制作总览','.matrix')]
    with sync_playwright() as runtime, tempfile.TemporaryDirectory(prefix='navigation-', dir=args.projects.parent) as temporary:
        browser=runtime.chromium.launch()
        try:
            for case in cases:
                target=Path(temporary)/case['case'];shutil.copytree(args.projects/case['path'],target)
                store=Store(target);before=store.load_document();server=WorkbenchServer(target)
                page=browser.new_page(viewport={'width':1440,'height':900});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                try:
                    url=server.start();start=time.perf_counter();page.goto(url+'studio/')
                    page.locator('main .matrix tbody tr').first.wait_for()
                    cold=round((time.perf_counter()-start)*1000,2);switches=[]
                    labels=page.evaluate("async()=> (await import('/v2/routes.js')).surfaces")
                    for cycle in range(3):
                        for surface,label,selector in surfaces:
                            start=time.perf_counter();page.locator('.nav').get_by_role('button',name=labels[surface],exact=True).click()
                            page.locator('main '+selector).first.wait_for()
                            page.locator('main button:visible:not([disabled])').first.wait_for()
                            switches.append({'round':cycle+1,'surface':surface,'visible_action_ms':round((time.perf_counter()-start)*1000,2)})
                    idle=None
                    if case['case'] in ['gallery-100','history-500']:
                        counts={};active={};peaks={};inflight={}
                        def began(request):
                            path=urlsplit(request.url).path
                            if not path.startswith('/api/'):return
                            counts[path]=counts.get(path,0)+1;active[path]=active.get(path,0)+1
                            peaks[path]=max(peaks.get(path,0),active[path]);inflight[request]=path
                        def ended(request):
                            path=inflight.pop(request,None)
                            if path:active[path]-=1
                        page.on('request',began);page.on('requestfinished',ended);page.on('requestfailed',ended)
                        cdp=page.context.new_cdp_session(page);cdp.send('Performance.enable')
                        def task_time():return next(x['value'] for x in cdp.send('Performance.getMetrics')['metrics'] if x['name']=='TaskDuration')
                        cpu=time.process_time();renderer=task_time();wall=time.perf_counter()
                        page.wait_for_timeout(46000)
                        elapsed=time.perf_counter()-wall
                        idle={'seconds':round(elapsed,2),'server_process_cpu_percent':round((time.process_time()-cpu)/elapsed*100,3),
                              'renderer_task_time_percent':round((task_time()-renderer)/elapsed*100,3),'requests':counts,'max_concurrent_by_path':peaks}
                    assert store.load_document()==before
                    results.append({**case,'cold_matrix_ms':cold,'switches':switches,'idle':idle,'page_errors':errors,'business_document_unchanged':True})
                    args.output.write_text(json.dumps({'label':args.label,'build_id':BUILD_ID,'results':results,'module_root_kind':'source checkout','fixture':'synthetic','model_calls':0},ensure_ascii=False,indent=2)+'\n')
                    print(json.dumps({'label':args.label,'case':case['case'],'cold_ms':cold,'completed':len(results)}),flush=True)
                finally:page.close();server.stop()
        finally:browser.close()
    assert Path(deck_master.__file__).is_file()


if __name__=='__main__':main()
