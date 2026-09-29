"""W10 local corruption and empty-state browser checks; explicit synthetic fixture."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from deck_master.models import bump_revision
from deck_master.web import WorkbenchServer
from w07_synthetic import SyntheticW07


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    flow = SyntheticW07(args.out); target = flow.dispatch(stage='reconstruct'); flow.dispatch('p02', stage='reconstruct')
    doc = flow.store.load_document(); target_ref = next(ref for ref in doc['tasks'] if flow.store.read_object_json(ref)['task_id'] == target['task_id'])
    target_path = flow.store.project_root / target_ref['path']; original = target_path.read_bytes()
    checks = []; server = WorkbenchServer(flow.project)
    try:
        url = server.start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); ctx = browser.new_context(); page = ctx.new_page(); page.goto(url + 'v2/')
            page.get_by_role('button', name='任务与交付', exact=True).click(); expect(page.locator('.run-task')).to_have_count(3)
            # Only this explicit disposable fixture is corrupted; original bytes
            # are restored below. Nothing is forged into a production run.
            target_path.write_bytes(b'Injected unreadable task for W10 browser recovery')
            page.get_by_role('button', name='核实最新执行状态', exact=True).click()
            expect(page.locator('.run-rows')).to_contain_text('记录无法读取')
            expect(page.locator('.run-rows')).to_contain_text('docs/agent-recovery-playbook.md#run-desk-recovery')
            expect(page.locator('.run-task')).to_have_count(3)
            checks.append('one_corrupt_task_local_error_preserves_other_rows_and_offline_docs')
            target_path.write_bytes(original); page.get_by_role('button', name='核实最新执行状态', exact=True).click()
            expect(page.locator('.run-rows')).not_to_contain_text('记录无法读取'); checks.append('explicit_reread_recovers_original_task')
            # An explicitly committed synthetic empty Task list exercises actions
            # for an existing content project; no production migration is implied.
            current = flow.store.load_document(); empty = bump_revision(current, {'operation_id': 'synthetic-empty-task-list', 'kind': 'task_update', 'description': 'Explicit empty-state browser fixture', 'read_set': []})
            empty['tasks'] = []; empty.pop('changes', None)
            flow.store.commit_change(base_revision=current['revision_id'], document=empty, operation_id='synthetic-empty-task-list')
            page.get_by_role('button', name='核实最新执行状态', exact=True).click()
            expect(page.locator('.run-desk').get_by_role('button', name='阅读内容', exact=True)).to_be_visible()
            expect(page.locator('.run-desk').get_by_role('button', name='查看整稿', exact=True)).to_be_visible()
            checks.append('no_tasks_has_content_and_gallery_actions')
            (args.out / 'checks.json').write_text(json.dumps({'checks': checks, 'synthetic': True, 'model_calls': 0, 'fault': 'temporary corrupt immutable task in disposable fixture; restored byte-for-byte'}, indent=2) + '\n')
            ctx.close(); browser.close(); print(json.dumps({'checks': len(checks), 'passed': True}))
    finally:
        target_path.write_bytes(original); server.stop()


if __name__ == '__main__': main()
