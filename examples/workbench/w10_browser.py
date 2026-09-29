"""W10 browser recovery against actual services; SVG-only synthetic Host.

--out must be a new directory. No model, HOME modification or delivery approval.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master.web import WorkbenchServer
from deck_master import run_desk
from w07_synthetic import SyntheticW07


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    expect.set_options(timeout=15000)
    flow = SyntheticW07(args.out); checks = []; errors = []; writes = []
    # Real protocol transitions, explicit synthetic SVG content and Host identity.
    for n in range(31):
        flow.svg(flow.dispatch(stage='reconstruct', instruction=f'Synthetic pagination candidate {n}'), n + 1)
    running = flow.dispatch('p02', stage='reconstruct'); flow.start(running)
    claimed = flow.task(running['task_id'])['execution_started_at']
    remaining = run_desk.listing(flow.project)['pagination']['total'] - 30
    server = WorkbenchServer(flow.project)
    def check(name, condition=True):
        assert condition, name
        checks.append(name); print(name, flush=True)
    try:
        url = server.start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
            ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = ctx.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' and '/api/' in request.url else None)
            page.goto(url + 'v2/'); page.get_by_role('button', name='任务与交付', exact=True).click()
            expect(page.locator('.run-task')).to_have_count(30)
            expect(page.locator('.candidate-batch-row')).to_have_count(30)
            check('task_and_candidate_dom_bounded_to_30')
            first = page.locator('.run-task').first.get_attribute('data-task-id')
            page.get_by_role('button', name='下一页任务', exact=True).click()
            expect(page.locator('.run-task')).to_have_count(remaining)
            fixed_ids = page.locator('.run-task').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.taskId)')
            # No business transition should move this fixed second page.
            flow.dispatch('p03', stage='reconstruct')
            page.wait_for_timeout(3400)
            check('paged_task_snapshot_does_not_reorder_on_background_update', page.locator('.run-task').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.taskId)') == fixed_ids)
            page.reload(); expect(page.locator('.run-task')).to_have_count(remaining)
            check('same_origin_reload_restores_task_page_and_revision', page.locator('.run-task').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.taskId)') == fixed_ids)
            # Current version lets the synthetic project persist personal selection.
            page.get_by_role('button', name='读取项目最新状态', exact=True).click()
            page.locator('.candidate-batch-row').first.wait_for()
            page.locator('.candidate-batch-row input').first.check()
            selected_id = page.locator('.candidate-batch-row').first.get_attribute('data-candidate-id')
            page.get_by_role('button', name='下一页候选', exact=True).click()
            expect(page.locator('.candidate-batch-row')).to_have_count(1)
            expect(page.locator('.candidate-batch')).to_contain_text('已选 1 个')
            page.get_by_role('button', name='上一页候选', exact=True).click()
            expect(page.locator(f'[data-candidate-id="{selected_id}"] input')).to_be_checked()
            check('candidate_selection_survives_pagination')
            page.get_by_role('button', name='核实最新执行状态', exact=True).click()
            expect(page.locator('.run-task')).to_have_count(30)
            page.get_by_role('checkbox', name='只看需我处理', exact=True).check()
            expect(page.locator('.run-task')).to_have_count(30)
            expect(page.locator(f'.run-task[data-task-id="{running["task_id"]}"]')).to_have_count(0)
            check('normal_running_excluded_from_human_todo', page.locator(f'.run-task[data-task-id="{running["task_id"]}"]').count() == 0)
            page.get_by_role('checkbox', name='只看需我处理', exact=True).uncheck()
            row = page.locator(f'.run-task[data-task-id="{running["task_id"]}"]')
            row.get_by_role('button', name='查看这项任务', exact=True).click()
            expect(page.locator('.run-detail')).to_contain_text(running['task_id'])
            check('real_claim_time_and_execution_identity_visible', page.locator('.run-detail').inner_text().find('执行标识：codex:') >= 0 and bool(claimed))
            page.route('**/api/cancel', lambda route: route.abort(), times=1)
            page.locator('.run-detail').get_by_role('button', name='取消原任务', exact=True).click()
            expect(page.locator('.run-detail')).to_contain_text('取消结果待核实')
            page.reload(); expect(page.locator('.run-detail')).to_contain_text('取消结果待核实')
            before = sum(url.endswith('/api/cancel') for url in writes)
            page.wait_for_timeout(3300)
            check('unknown_cancel_survives_reload_without_automatic_resend', sum(url.endswith('/api/cancel') for url in writes) == before and flow.task(running['task_id'])['status'] == 'running')
            page.locator('.run-detail').get_by_role('button', name='核实原任务', exact=True).click()
            page.locator('.run-detail').get_by_role('button', name='再次请求取消原任务', exact=True).click()
            expect(page.locator('.run-detail h3')).to_contain_text('已取消')
            check('explicit_cancel_retry_confirms_same_task', flow.task(running['task_id'])['status'] == 'cancelled')
            check('poll_never_dispatches_or_allocates', not any('/api/continue' in url or '/api/changes/commit' in url or '/api/calls/' in url for url in writes))
            for width, height in [(1280, 800), (1440, 900)]:
                page.set_viewport_size({'width': width, 'height': height})
                check(f'no_horizontal_overflow_{width}', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.screenshot(path=str(args.out / f'runs-{width}.png'), full_page=True)
            check('no_boolean_placeholders_in_task_detail', not any(word in page.locator('.run-detail').inner_text() for word in ['false', '[object']))
            page.evaluate('scrollTo(0,0)'); page.screenshot(path=str(args.out / 'runs-first-window.png'))
            check('no_browser_javascript_errors', not errors)
            ctx.tracing.stop(path=str(args.out / 'local-only' / 'trace.zip'))
            (args.out / 'checks.json').write_text(json.dumps({'checks': checks, 'errors': errors, 'synthetic': True, 'model_calls': 0, 'native_host_evidence': False,
                'execution_started_at': claimed, 'task_id': running['task_id'], 'browser': browser.version}, indent=2) + '\n')
            ctx.close(); browser.close()
    finally:
        server.stop()


if __name__ == '__main__': main()
