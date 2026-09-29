"""CLI-only trial/adoption client; does not impersonate a Host or make image calls.

Use --commit only for an explicitly selected trial/adoption. Every request and
UUID is written to a new local output directory before submission. On an
uncertain result, use operations show and the saved payload; never rerun this
script to invent another operation ID. Host execution happens separately.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['trial', 'adopt'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--out', required=True, help='new local request/evidence directory; never commit raw requests')
    parser.add_argument('--commit', action='store_true')
    parser.add_argument('--page-id', action='append', default=[])
    parser.add_argument('--stage', choices=['blueprint', 'reconstruct', 'repair'], default='blueprint')
    parser.add_argument('--instruction')
    parser.add_argument('--reference-page-id')
    parser.add_argument('--reference-revision')
    parser.add_argument('--candidate-id', action='append', default=[])
    args = parser.parse_args()
    if args.action == 'trial' and (not args.page_id or not args.instruction):
        parser.error('trial requires --page-id and --instruction')
    if args.action == 'adopt' and not args.candidate_id:
        parser.error('adopt requires selected --candidate-id values from candidates list/show')
    root = Path(args.out).expanduser().resolve(); root.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        path = root / (name + '.json'); path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); return path
    def cli(name, *command):
        response = subprocess.run([sys.executable, '-m', 'deck_master', *command, '--project', args.project],
                                  text=True, capture_output=True)
        raw = response.stdout if response.returncode == 0 else response.stderr
        value = json.loads(raw); save(name, value)
        if response.returncode:
            print(json.dumps(value, ensure_ascii=False), file=sys.stderr)
            raise SystemExit(response.returncode)
        return value
    current = cli('before', 'view', '--summary', '--json')
    if args.action == 'trial':
        pages = {p['page_id']: p for p in current['pages']}; layer = 'original_image' if args.stage == 'blueprint' else 'svg'
        slot = 'blueprint' if args.stage == 'blueprint' else 'svg'
        value = {'schema_version': 'change_intent.v1', 'project_id': current['project_id'], 'base_revision': current['revision_id'],
                 'mode': 'trial', 'intent': 'explicit_trial', 'instruction': args.instruction, 'annotation_refs': [],
                 'max_calls': len(args.page_id) if args.stage == 'blueprint' else 0,
                 'targets': [{'page_id': pid, 'page_ref': pages[pid]['stages']['content']['ref'], 'layer': layer,
                              'stage': args.stage, 'artifact_ref': pages[pid]['stages'][slot]['ref']} for pid in args.page_id]}
        if args.reference_page_id:
            command = ['view', '--summary', '--json']
            if args.reference_revision: command += ['--revision', args.reference_revision]
            fixed = cli('reference', *command); reference = next(p for p in fixed['pages'] if p['page_id'] == args.reference_page_id)
            value['references'] = [{'page_id': reference['page_id'], 'revision_id': fixed['revision_id'],
                                    'artifact_ref': reference['stages']['blueprint']['ref'], 'role': 'reference'}]
        plan = cli('plan', 'changes', 'plan', '--input', str(save('trial-input', value)))
        command = ['changes', 'commit', '--plan-id', plan['plan_id']]
    else:
        cli('available-candidates', 'candidates', 'list')
        value = {'schema_version': 'candidate_selection.v1', 'project_id': current['project_id'],
                 'base_revision': current['revision_id'], 'candidate_ids': args.candidate_id}
        plan = cli('plan', 'candidates', 'plan', '--input', str(save('selection', value)))
        command = ['candidates', 'adopt', '--input', str(save('adoption-input', plan['plan']))]
    if args.commit:
        operation = str(uuid.uuid4()); command += ['--base-revision', current['revision_id'], '--operation-id', operation]
        save('pending-operation', {'operation_id': operation, 'base_revision': current['revision_id'], 'plan': plan, 'command': command})
        result = cli('committed', *command)
        if args.action == 'trial':
            cli('handoff', 'changes', 'handoff', '--change-id', result['operation_result']['change_id'])
        cli('after', 'view', '--summary', '--json')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
