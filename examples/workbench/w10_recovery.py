"""Runnable W10 synthetic recovery checks. Never invokes a model or edits HOME.

PYTHONPATH=src python examples/workbench/w10_recovery.py --out <new-directory>
Uses actual core/CLI/HTTP transitions; simulated clock and late result are labeled.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from unittest.mock import patch

from deck_master import changes, generation, operations, run_desk, service, tasks
from deck_master.web import WorkbenchServer
from w07_synthetic import SyntheticW07, EXECUTION


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    fixture = SyntheticW07(args.out, pages=3); store = fixture.store; checks = {}; responses = {}
    doc = store.load_document()
    intent = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
              'mode': 'trial', 'intent': 'synthetic_recovery', 'instruction': 'Synthetic two-page SVG recovery example',
              'annotation_refs': [], 'max_calls': 0, 'targets': [
                  {'page_id': entry['page_id'], 'page_ref': entry['page'], 'layer': 'svg', 'stage': 'reconstruct', 'artifact_ref': entry.get('svg')}
                  for entry in doc['pages'][:2]]}
    planned = changes.plan(fixture.project, input=intent); operation_id = str(uuid.uuid4())
    committed = changes.commit(fixture.project, plan_id=planned['plan_id'], base_revision=doc['revision_id'], operation_id=operation_id)
    # Simulated response loss: recover committed facts using the ORIGINAL ID.
    recovered = operations.show(fixture.project, operation_id=operation_id)
    assert recovered['operation_result'] == committed['operation_result']
    checks['lost_response_original_operation_recovered'] = True
    change_id = committed['operation_result']['change_id']
    first, second = [fixture.task(tid) for tid in committed['operation_result']['task_ids']]
    fixed = store.current_revision_id(); fixed_rows = run_desk.listing(fixture.project, revision=fixed, change_id=change_id)
    returned = fixture.svg(second)
    partial = run_desk.listing(fixture.project, change_id=change_id)
    assert partial['groups'][-1]['status'] == 'partial'
    assert partial['groups'][-1]['completed_count'] == 1
    assert run_desk.listing(fixture.project, revision=fixed, change_id=change_id) == fixed_rows
    fixture.adopt(returned['candidate_ids'])
    adopted_page = store.load_document()['pages'][1]
    checks['reverse_return_partial_group_fixed_history_and_selected_adoption'] = True
    fixture.start(first); claim = run_desk.detail(fixture.project, task_id=first['task_id'])['task']['execution_started_at']
    fake_now = datetime.fromisoformat(claim.replace('Z', '+00:00')) + timedelta(minutes=31)
    class SimulatedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fake_now if tz else fake_now.replace(tzinfo=None)
    with patch.object(run_desk, 'datetime', SimulatedClock):
        delayed = run_desk.detail(fixture.project, task_id=first['task_id'])
    assert delayed['task']['needs_verification'] and delayed['task']['status'] == 'running'
    service.task_cancel(fixture.project, task_id=first['task_id'], reason='Explicit synthetic cancellation before replacement')
    stopped = store.load_document()
    try:
        with patch.object(fixture, 'start', lambda task: None):
            fixture.svg(first)
    except tasks.TaskConflict:
        checks['cancelled_late_svg_refused'] = True
    else:
        raise AssertionError('cancelled late result must be refused')
    after_late = store.load_document()
    assert all(after_late[key] == stopped[key] for key in ('pages', 'outputs', 'candidates'))
    assert fixture.task(first['task_id'])['status'] == 'cancelled'
    checks['late_result_only_settles_facts_current_artifacts_unchanged'] = True
    replacement = fixture.dispatch(stage='reconstruct'); fixture.svg(replacement)
    assert store.load_document()['pages'][1] == adopted_page
    checks['only_unfinished_page_replaced_adopted_page_preserved'] = True
    unknown_task = fixture.dispatch('p03'); fixture.start(unknown_task)
    frozen = generation.freeze(fixture.project, task_id=unknown_task['task_id'],
        input=generation.prepared_input(store, store.load_document(), unknown_task),
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    attempt = tasks.call_begin(store, task_id=unknown_task['task_id'], allowance_id=unknown_task['call_allowances'][0]['allowance_id'],
                               execution_ref=EXECUTION, request_id=frozen['request_id'])
    tasks.call_settle(store, task_id=unknown_task['task_id'], allowance_id=attempt['allowance_id'], attempt_id=attempt['attempt_id'],
                      outcome='unknown', report_bytes=None)
    original = store.read_current(); server = WorkbenchServer(fixture.project)
    def get(url):
        try:
            with urllib.request.urlopen(url) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
    try:
        url = server.start().rstrip('/')
        for path in ['/api/tasks?limit=2', '/api/tasks?limit=2&attention=1', '/api/tasks/' + unknown_task['task_id'],
                     '/api/requests/' + frozen['request_id'], '/api/attempts/' + attempt['attempt_id']]:
            status, result = get(url + path); assert status == 200; responses[path] = result
        for path, expected in [('/api/tasks?limit=0', 400), ('/api/tasks/missing', 404)]:
            status, result = get(url + path); assert status == expected
            responses[path] = result
        assert store.read_current() == original
        detail = responses['/api/tasks/' + unknown_task['task_id']]
        assert detail['call_allowances'][0]['state'] == 'unknown'
        assert detail['task']['human_actions'] == ['verify_unknown_call']
        assert len(detail['links']['generation_attempts']) == 1
        checks['unknown_read_never_replays_or_allocates'] = True
    finally:
        server.stop()
    service.task_cancel(fixture.project, task_id=unknown_task['task_id'])
    assert fixture.task(unknown_task['task_id'])['call_allowances'][0]['state'] == 'unknown'
    checks['unknown_survives_cancellation'] = True
    cli_project = args.out / 'awaiting-project'; created = service.create(cli_project, brief='Synthetic no-model run-status example')
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-m', 'deck_master', 'continue', '--project', str(cli_project), '--json'], env=env, capture_output=True, text=True)
    pending = json.loads(result.stdout); assert result.returncode == 3 and pending['status'] == 'awaiting_host'
    task_id = pending['pending_tasks'][0]['task_id']
    result = subprocess.run([sys.executable, '-m', 'deck_master', 'task', 'status', '--project', str(cli_project), '--task-id', task_id, '--details', '--json'], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['task']['status'] == 'awaiting_host'
    checks['continue_awaiting_exit3_status_query_exit0'] = True
    # Detailed responses may contain local read commands; keep them local only.
    raw = args.out / 'local-only'; raw.mkdir(exist_ok=True); write(raw / 'responses.json', responses)
    write(args.out / 'checks.json', {'synthetic': True, 'model_calls': 0, 'native_host_evidence': False,
        'faults': ['lost response after real commit', '31-minute projection clock', 'late SVG after confirmed cancellation', 'unknown call without tool receipt'],
        'checks': checks, 'project_id': doc['project_id'], 'awaiting_project_id': created['project_id'], 'operation_id': operation_id,
        'change_id': change_id, 'task_ids': [first['task_id'], second['task_id'], replacement['task_id'], unknown_task['task_id']],
        'request_id': frozen['request_id'], 'attempt_id': attempt['attempt_id'], 'execution_started_at': claim,
        'errors': {path: result for path, result in responses.items() if path in ['/api/tasks?limit=0', '/api/tasks/missing']}})
    print(json.dumps({'checks': len(checks), 'passed': all(checks.values())}), flush=True)


if __name__ == '__main__':
    main()
