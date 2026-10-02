"""Runnable W06 CLI and same-origin browser example, using synthetic material.

No Host is impersonated: created tasks remain awaiting_host. Real Codex claim
and product UI clipboard acceptance are separate evidence. Raw requests and
responses are local-only; checks.json is safe to include in the engineering report.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import uuid

from playwright.sync_api import sync_playwright

from deck_master.samples import create_sample
from deck_master.web import WorkbenchServer


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); parser.add_argument('--chromium-executable', type=Path); args = parser.parse_args()
    root = Path(args.out).expanduser().resolve(); root.mkdir(parents=True, exist_ok=False)
    project = root / 'synthetic-project'; create_sample(project, page_count=2, readonly=False)
    raw = root / 'local-only-requests'; raw.mkdir(); checks = []
    def check(name, condition):
        assert condition, name
        checks.append({'name': name, 'status': 'pass'})
    def write(name, value):
        path = raw / (name + '.json'); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); return path
    def cli(name, *args, expected=0):
        result = subprocess.run([sys.executable, '-m', 'deck_master', *args], capture_output=True, text=True)
        assert result.returncode == expected, (name, result.returncode, result.stderr)
        value = json.loads(result.stdout if expected == 0 else result.stderr)
        write(name, value); return value
    def summary(name): return cli(name, 'view', '--project', str(project), '--summary', '--json')
    first = summary('initial-summary'); page = first['pages'][0]; ref = page['stages']['content']['ref']
    note = {'schema_version': 'annotation.v1', 'project_id': first['project_id'], 'base_revision': first['revision_id'],
            'scope': 'page', 'page_id': page['page_id'], 'page_ref': ref, 'intent': 'clarify',
            'body': '合成意见：明确这一页的判断依据。', 'status': 'open', 'location': {'kind': 'whole'}}
    batch = {'schema_version': 'annotation_batch.v1', 'project_id': first['project_id'], 'annotations': [note]}
    payload_file = write('notes', batch); op = str(uuid.uuid4())
    write('pending-save', {'operation_id': op, 'base_revision': first['revision_id'], 'input': batch})
    saved = cli('saved', 'annotations', 'save', '--project', str(project), '--input', str(payload_file),
                '--base-revision', first['revision_id'], '--operation-id', op)
    # Deliberately ignore the successful save response as the recovery decision
    # source. Query committed facts, as a client with a lost response must do.
    recovered = cli('recovered', 'operations', 'show', '--project', str(project), '--operation-id', op)
    check('lost-response-query-preserves-original-result', recovered['operation_result'] == saved['operation_result'])
    altered = copy.deepcopy(batch); altered['annotations'][0]['body'] += ' changed'
    changed_file = write('changed-notes', altered)
    conflict = cli('operation-payload-conflict', 'annotations', 'save', '--project', str(project), '--input', str(changed_file),
                   '--base-revision', first['revision_id'], '--operation-id', op, expected=5)
    check('same-id-changed-payload-conflicts', conflict['error']['code'] == 'operation_payload_conflict')
    stale = cli('base-conflict', 'annotations', 'save', '--project', str(project), '--input', str(payload_file),
                '--base-revision', first['revision_id'], '--operation-id', str(uuid.uuid4()), expected=5)
    check('new-operation-stale-base-conflicts', stale['error']['code'] == 'conflict')
    next_op = str(uuid.uuid4()); current = summary('after-save')
    pending = {'operation_id': next_op, 'base_revision': current['revision_id'], 'input': batch}; write('pending-not-found', pending)
    missing = cli('operation-not-found', 'operations', 'show', '--project', str(project), '--operation-id', next_op, expected=2)
    check('not-found-does-not-claim-failure-or-change-id', missing['error']['operation_state'] == 'not_found')
    cli('same-id-replay', 'annotations', 'save', '--project', str(project), '--input', str(payload_file),
        '--base-revision', pending['base_revision'], '--operation-id', next_op)
    current = summary('before-plan')
    value = {'schema_version': 'change_intent.v1', 'project_id': first['project_id'], 'base_revision': current['revision_id'],
             'targets': [{'page_id': page['page_id'], 'page_ref': ref, 'layer': 'content', 'artifact_ref': ref}],
             'intent': 'clarify', 'instruction': '明确本页的判断依据；只修改本页正文，保留原图。', 'max_calls': 0,
             'annotation_refs': [saved['operation_result']['annotations'][0]['ref']]}
    change_file = write('changes', value)
    planned = cli('plan', 'changes', 'plan', '--project', str(project), '--input', str(change_file))
    after_plan = summary('after-plan')
    check('plan-does-not-change-business-version', after_plan['revision_id'] == current['revision_id'])
    commit_op = str(uuid.uuid4()); request = {'plan_id': planned['plan_id'], 'base_revision': current['revision_id'], 'operation_id': commit_op}
    write('pending-commit', request)
    committed = cli('commit', 'changes', 'commit', '--project', str(project), '--plan-id', planned['plan_id'],
                    '--base-revision', request['base_revision'], '--operation-id', commit_op)
    cli('commit-recovered', 'operations', 'show', '--project', str(project), '--operation-id', commit_op)
    change_id = committed['operation_result']['change_id']
    handoff = cli('handoff', 'changes', 'handoff', '--project', str(project), '--change-id', change_id)
    check('handoff-remains-unclaimed', handoff['status'] == 'awaiting_host' and all(t['execution_ref'] is None for t in handoff['handoff']['tasks']))
    check('core-command-quotes-exact-project', shlex.split(handoff['handoff']['read_command']) ==
          ['deck-master', 'changes', 'handoff', '--project', str(project), '--change-id', change_id])
    server = WorkbenchServer(project); url = server.start().rstrip('/')
    try:
        with sync_playwright() as browser_api:
            browser = browser_api.chromium.launch(executable_path=str(args.chromium_executable) if args.chromium_executable else None); tab = browser.new_page(); tab.goto(url + '/v2/')
            # This is an explicit same-origin HTTP example in a real browser,
            # not a script token endpoint and not product annotation UI proof.
            browser_result = tab.evaluate('''async () => {
                const summary = await (await fetch('/api/view/summary')).json();
                const page = summary.pages[1];
                const input = {schema_version:'annotation_batch.v1', project_id:summary.project_id, annotations:[{
                    schema_version:'annotation.v1', project_id:summary.project_id, base_revision:summary.revision_id,
                    scope:'page', page_id:page.page_id, page_ref:page.stages.content.ref,
                    intent:'clarify', body:'Browser HTTP synthetic opinion', status:'open', location:{kind:'whole'}}]};
                const request = {input, base_revision:summary.revision_id, operation_id:crypto.randomUUID()};
                localStorage.setItem('w06-example-pending', JSON.stringify(request));
                const token = (await (await fetch('/api/session')).json()).token;
                const response = await fetch('/api/annotations/batch', {method:'POST', headers:{'Content-Type':'application/json','X-Deck-Token':token},body:JSON.stringify(request)});
                return {status:response.status, request, response:await response.json()};
            }''')
            write('same-origin-browser', browser_result)
            check('same-origin-browser-persists-opinion', browser_result['status'] == 200)
            check('browser-ack-is-business-commit', browser_result['response']['status'] == 'committed')
            browser_version = browser.version; browser.close()
    finally:
        server.stop()
    report = {'status': 'verified', 'evidence': 'synthetic CLI and real Chromium same-origin HTTP; no real Host claim or product annotation UI',
              'python': platform.python_version(), 'platform': platform.platform(), 'browser': browser_version, 'checks': checks,
              'residuals': ['Real Host claim and product clipboard flow are separate W06 UI acceptance evidence.']}
    (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}))


if __name__ == '__main__':
    main()
