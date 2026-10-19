"""Derive an offline iteration ledger's summary without adjudicating any AC."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

STATUSES = ('PASS', 'FAIL', 'BLOCKED', 'NOT_RUN', 'NOT_APPLICABLE')


def summarize(ledger, *, ci_status=None):
    result = copy.deepcopy(ledger)
    rows = result['acceptance']
    ids = [row['ac_id'] for row in rows]
    if len(ids) != len(set(ids)) or any(row['status'] not in STATUSES for row in rows):
        raise ValueError('acceptance IDs must be unique and statuses explicit')
    counts = {status: sum(row['status'] == status for row in rows) for status in STATUSES}
    unresolved = [row['ac_id'] for row in rows if row['status'] not in ('PASS', 'NOT_APPLICABLE')]
    ci_observation = next((check for check in result.get('integration_checks', [])
                           if check.get('kind') == 'current_candidate_ci'), {})
    if ci_status is None:
        ci_status = ci_observation.get('state_at_assembly', 'NOT_RUN')
    candidate = result.get('candidate', {})
    build_ok = (candidate.get('build_runtime_and_skill_bytes_match_candidate') is True
                and not candidate.get('fresh_build_required', False))
    installed_ok = any(item.get('status') == 'PASS' for item in candidate.get('installed_instances', []))
    gates = []
    if unresolved:
        gates.append('unresolved_acceptance')
    if ci_status != 'PASS':
        gates.append('final_exact_head_ci')
    if not build_ok:
        gates.append('current_build_identity')
    if not installed_ok:
        gates.append('installed_resource_identity')
    overall = 'FAIL' if counts['FAIL'] or ci_status == 'FAIL' else 'BLOCKED' if gates else 'PASS'
    deferred_local = any(item.get('status') == 'DEFERRED_TO_USER_LOCAL_VALIDATION'
                         for item in result.get('deferred_observations', []))
    per_task = {}
    for owner in dict.fromkeys(row['owner'] for row in rows):
        owned = [row for row in rows if row['owner'] == owner]
        pending = [row['ac_id'] for row in owned if row['status'] not in ('PASS', 'NOT_APPLICABLE')]
        per_task[owner] = {
            'status': 'FAIL' if any(row['status'] == 'FAIL' for row in owned) else 'BLOCKED' if pending else 'PASS',
            'counts': {status: sum(row['status'] == status for row in owned) for status in STATUSES},
            'unresolved_ac_ids': pending,
        }
    result['status_counts'] = counts
    result['status'] = 'PASS' if overall == 'PASS' else 'PARTIAL'
    result['completion'] = {
        'engineering_candidate': overall,
        'all_six_tasks': overall,
        'unresolved_ac_ids': unresolved,
        'per_task_component_findings': per_task,
        'final_ci_state_at_assembly': ci_status,
        'state_observed_at_utc': ci_observation.get('observed_at_utc'),
        'observation_scope': 'Assembly snapshot; the exact-head live checks and final PR handoff provide subsequent terminal CI evidence.',
        'live_terminal_ci': 'https://github.com/MainQuestAI/Deck-Master/pull/124/checks',
        'remaining_engineering_gates': gates,
        'real_acceptance': 'DEFERRED_TO_USER_LOCAL_VALIDATION' if deferred_local else 'NOT_CLAIMED',
        'summary': (f"{len(rows)} AC: {counts['PASS']} PASS, {counts['FAIL']} FAIL, "
                    f"{counts['BLOCKED']} BLOCKED, {counts['NOT_RUN']} NOT_RUN, "
                    f"{counts['NOT_APPLICABLE']} NOT_APPLICABLE; {len(unresolved)} unresolved. "
                    f"Engineering candidate {overall}; exact-head CI {ci_status}. "
                    'User local effects/usability and trusted Host acceptance are separate observations, not inferred PASS.'),
    }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--ci-status')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    derived = summarize(json.loads(args.ledger.read_text()), ci_status=args.ci_status)
    if args.write:
        args.ledger.write_text(json.dumps(derived, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(derived['completion'], ensure_ascii=False, indent=2))
