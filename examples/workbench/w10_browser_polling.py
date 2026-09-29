"""Actual browser route integration with an injected visibility flag.

The DOM visibility fault is explicit; real desktop tab minimization is not claimed.
No model calls or business writes. Current-summary responses can be delayed to
exercise the single in-flight guard independently of loopback response speed.
"""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from deck_master.web import WorkbenchServer
from w07_synthetic import SyntheticW07


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    flow = SyntheticW07(args.out); flow.dispatch(stage='reconstruct')
    server = WorkbenchServer(flow.project); requests = []; active = set(); peaks = []; errors = []; checks = []
    def check(name, value):
        assert value, name
        checks.append(name); print(name, flush=True)
    try:
        url = server.start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); context = browser.new_context()
            context.add_init_script("Object.defineProperty(document, 'hidden', {get:()=>window.__testHidden===true});")
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            def started(request):
                if request.url.endswith('/api/view/summary'):
                    requests.append({'time': time.monotonic(), 'url': request.url}); active.add(request); peaks.append(len(active))
            page.on('request', started); page.on('requestfinished', lambda request: active.discard(request)); page.on('requestfailed', lambda request: active.discard(request))
            page.goto(url + 'v2/'); page.get_by_role('button', name='整稿画廊', exact=True).click()
            page.wait_for_function('()=>Boolean(document.querySelector(".gallery-card"))').dispose()
            page.locator('.gallery-open').first.click(); page.wait_for_function('()=>Boolean(document.querySelector(".page-workbench"))').dispose()
            for surface in ['page', 'runs']:
                if surface == 'runs':
                    page.get_by_role('button', name='任务与交付', exact=True).click()
                    page.wait_for_function('()=>Boolean(document.querySelector(".run-desk"))').dispose()
                page.wait_for_timeout(1000)
                page.evaluate("window.__testHidden=true;document.dispatchEvent(new Event('visibilitychange'))")
                page.wait_for_timeout(300); before = len(requests); page.wait_for_timeout(6500)
                check(f'{surface}_hidden_pauses_current_summary_requests', len(requests) == before)
                page.evaluate("window.__testHidden=false;document.dispatchEvent(new Event('visibilitychange'))")
                page.wait_for_timeout(500); check(f'{surface}_visible_refreshes_immediately', len(requests) > before)
            page.wait_for_timeout(800); peaks.clear()
            # Delay the response to keep one poll in flight across many focus events.
            def delay(route):
                response = route.fetch(); time.sleep(.8); route.fulfill(response=response)
            page.route('**/api/view/summary', delay)
            page.evaluate("for(let i=0;i<8;i++)window.dispatchEvent(new Event('focus'))")
            page.wait_for_timeout(2500)
            check('focus_burst_keeps_one_summary_inflight', max(peaks or [0]) <= 1)
            page.unroute('**/api/view/summary', delay)
            check('no_browser_errors', not errors)
            (args.out / 'checks.json').write_text(json.dumps({'checks': checks, 'visibility': 'injected document.hidden flag with real DOM events', 'model_calls': 0, 'errors': errors, 'peak': max(peaks or [0])}, indent=2) + '\n')
            context.close(); browser.close()
    finally: server.stop()


if __name__ == '__main__': main()
