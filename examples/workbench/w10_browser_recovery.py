"""W10 project-ACK recovery across origins and explicit 31-minute clock fault.

Synthetic tasks, real service/Chromium; no model or native Host claim.
"""
import argparse
from datetime import datetime, timedelta
import json
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, expect
from deck_master import run_desk, ui_journal
from deck_master.web import WorkbenchServer
from w07_synthetic import SyntheticW07


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    flow = SyntheticW07(args.out); checks = []; errors = []; posts = []
    for n in range(32): flow.dispatch(stage='reconstruct', instruction=f'Synthetic recovery task {n}')
    running = flow.dispatch('p02', stage='reconstruct'); flow.start(running)
    doc = flow.store.load_document(); identity = ui_journal.project_info(flow.project)['project_identity']
    query = urlencode({'project': identity, 'surface': 'runs', 'layer': 'original_image', 'revision': doc['revision_id'], 'zoom': 1})
    def check(name, condition=True):
        assert condition, name
        checks.append(name); print(name, flush=True)
    def project_ack(page, expression):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            saved = page.evaluate("""async expression => {
                const result=await(await fetch('/api/drafts')).json();
                return result.records.some(row=>expression==='offset' ? row.draft.content.run_desk?.offset===30 : row.draft.content.cancel_pending?.length>0);
            }""", expression)
            if saved: return
            page.wait_for_timeout(100)
        raise AssertionError('Project journal did not ACK ' + expression)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(); server = WorkbenchServer(flow.project)
        try:
            url = server.start(); ctx = browser.new_context(); page = ctx.new_page(); page.goto(url + 'v2/#' + query)
            expect(page.locator('.run-task')).to_have_count(30)
            page.get_by_role('button', name='下一页任务', exact=True).click(); expect(page.locator('.run-task')).to_have_count(4)
            ids = page.locator('.run-task').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.taskId)'); project_ack(page, 'offset')
            ctx.close(); server.stop(); server = WorkbenchServer(flow.project); next_url = server.start(); assert next_url != url
            ctx = browser.new_context(); page = ctx.new_page(); page.on('pageerror', lambda error: errors.append(str(error))); page.goto(next_url + 'v2/#' + query)
            expect(page.locator('.run-task')).to_have_count(4)
            check('new_origin_restores_only_project_ack_task_page', page.locator('.run-task').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.taskId)') == ids)
            page.get_by_role('button', name='核实最新执行状态', exact=True).click()
            row = page.locator(f'.run-task[data-task-id="{running["task_id"]}"]'); row.get_by_role('button', name='查看这项任务', exact=True).click()
            expect(page.locator('.run-detail')).to_contain_text(running['task_id'])
            page.route('**/api/cancel', lambda route: route.abort(), times=1)
            page.locator('.run-detail').get_by_role('button', name='取消原任务', exact=True).click()
            expect(page.locator('.run-detail')).to_contain_text('取消结果待核实'); project_ack(page, 'cancel')
            task_hash = page.url.split('#')[1]; ctx.close(); server.stop(); server = WorkbenchServer(flow.project); final_url = server.start(); assert final_url != next_url
            ctx = browser.new_context(); page = ctx.new_page(); page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
            page.goto(final_url + 'v2/#' + task_hash); expect(page.locator('.run-detail')).to_contain_text('取消结果待核实')
            check('unknown_cancel_project_ack_survives_second_origin_change', flow.task(running['task_id'])['status'] == 'running')
            claim = run_desk.detail(flow.project, task_id=running['task_id'])['task']['execution_started_at']
            fake_now = datetime.fromisoformat(claim.replace('Z', '+00:00')) + timedelta(minutes=31)
            class SimulatedClock(datetime):
                @classmethod
                def now(cls, tz=None): return fake_now if tz else fake_now.replace(tzinfo=None)
            with patch.object(run_desk, 'datetime', SimulatedClock):
                page.get_by_role('button', name='核实最新执行状态', exact=True).click()
                page.get_by_role('button', name='查看全部任务', exact=True).click()
                expect(page.locator('.run-detail')).to_be_empty()
                page.get_by_role('checkbox', name='只看需我处理', exact=True).check()
                expect(page.locator(f'.run-task[data-task-id="{running["task_id"]}"]')).to_contain_text('核实原执行')
                check('31_minute_projection_clock_only_requests_verification', flow.task(running['task_id'])['status'] == 'running')
            check('no_automatic_cancel_or_dispatch_across_origins', not any(url.endswith('/api/cancel') or url.endswith('/api/changes/commit') for url in posts))
            check('no_browser_javascript_errors', not errors)
            (args.out / 'checks.json').write_text(json.dumps({'checks': checks, 'synthetic': True, 'clock_fault_minutes': 31, 'model_calls': 0, 'native_host_evidence': False, 'errors': errors}, indent=2) + '\n')
            ctx.close(); browser.close()
        finally: server.stop()


if __name__ == '__main__': main()
