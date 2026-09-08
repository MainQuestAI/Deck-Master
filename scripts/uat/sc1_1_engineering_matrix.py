"""Evidence ledger for current SC1.1 and inherited SC1 product acceptance.

This records supplied execution evidence; it never runs a shell command and
never equates a spec self-check, mapping, or unit test with a product pass.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_matrix(repo: Path, candidate_sha: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{40}', candidate_sha):
        raise ValueError('candidate SHA must be a full 40-character git SHA')
    spec = repo / 'docs/specs/sc1.1-native-deck-core'
    old = repo / 'docs/specs/sc1-solution-core-independence/acceptance/cases.json'
    sources = [spec / 'acceptance/cases.json', spec / 'acceptance/SC1_SUPERSESSION_MAP.json', old]
    current, mapping, inherited = (_read(p) for p in sources)
    entries = {entry['sc1_id']: entry for entry in mapping['entries']}
    rows = []
    for suite, cases in [('SC1.1', current['cases']), ('SC1', inherited['cases'])]:
        for case in cases:
            entry = entries.get(case['id'], {}) if suite == 'SC1' else {}
            rows.append({
                'key': f"{suite}:{case['id']}", 'suite': suite, 'id': case['id'],
                'title': case['title'], 'evidence_tier': case['evidence_tier'],
                'mandatory': case.get('mandatory', True), 'given': case['given'],
                'when': case['when'], 'then': case['then'],
                'disposition': entry.get('disposition'), 'ndc_anchor': entry.get('ndc_anchor'),
                'supersession_reason': entry.get('reason'),
                'status': 'not_run', 'records': [],
            })
    return {'schema_version': 'sc1_1_engineering_evidence.v1', 'candidate_sha': candidate_sha,
            'source_hashes': {str(p.relative_to(repo)): _sha(p) for p in sources},
            'unmapped_inherited_ids': sorted(c['id'] for c in inherited['cases'] if c['id'] not in entries),
            'cases': rows}


def record_result(matrix: dict, case_key: str, status: str, commit: str, command: str,
                  actual_result: str, evidence: list[Path], tier: str, environment: dict,
                  *, actor: str = 'agent') -> dict:
    if status not in {'passed', 'blocked', 'failed'}:
        raise ValueError('status must be passed, blocked or failed; untouched cases remain not_run')
    if commit != matrix['candidate_sha']:
        raise ValueError('record must target the matrix candidate SHA')
    row = next((c for c in matrix['cases'] if c['key'] == case_key), None)
    if row is None:
        raise ValueError(f'unknown case: {case_key}')
    if not command.strip() or not actual_result.strip() or not environment:
        raise ValueError('actual command/tool, result and environment are required')
    if status == 'passed' and any(token in command.lower() for token in
            ('validate_spec', 'spec_self_check', 'validate-spec', 'schema_negative_cases')):
        raise ValueError('spec self-check cannot pass a product acceptance case')
    if tier not in {'L1', 'L2', 'L3'} or (status == 'passed' and int(tier[1]) < int(row['evidence_tier'][1])):
        raise ValueError('execution evidence tier is below the required tier')
    if not evidence or any(not p.is_file() for p in evidence):
        raise ValueError('real evidence files are required for every executed result')
    record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'actual_commit': commit,
              'actual_command_or_tool': command, 'actual_result': actual_result,
              'evidence_tier': tier, 'environment': environment, 'actor': actor, 'status': status,
              'evidence_refs': [{'path': str(p.resolve()), 'sha256': _sha(p)} for p in evidence]}
    row['records'].append(record)
    row['status'] = status
    return record


def summarize(matrix: dict) -> dict:
    missing, invalid, outcomes = [], [], []
    counts = Counter()
    for row in matrix['cases']:
        status = row['status']
        if status == 'passed':
            records = row.get('records', [])
            latest = records[-1] if records else {}
            refs = latest.get('evidence_refs', [])
            valid = bool(refs) and latest.get('actual_commit') == matrix['candidate_sha']
            valid = valid and all(Path(ref['path']).is_file() and _sha(Path(ref['path'])) == ref['sha256'] for ref in refs)
            if not valid:
                invalid.append(row['key'])
                status = 'invalid_evidence'
        counts[status] += 1
        if row['mandatory'] and status != 'passed':
            (outcomes if row['evidence_tier'] == 'L3' else missing).append(row['key'])
    human_pending = [row['key'] for row in matrix['cases']
                     if row['key'] in {'SC1.1:UAT-02', 'SC1.1:UAT-03', 'SC1.1:UAT-04'}
                     and not (row.get('records') and row['records'][-1].get('actor') == 'user'
                              and row['status'] == 'passed' and row['key'] not in invalid)]
    return {'candidate_sha': matrix['candidate_sha'], 'counts': dict(counts),
            'engineering_status': 'in_progress' if missing or human_pending else 'engineering_complete',
            'pending_user_reviews': human_pending,
            'outcome_status': 'outcome_pending' if outcomes else 'outcome_evidence_complete',
            'missing_engineering_cases': missing, 'missing_outcome_cases': outcomes,
            'invalid_evidence_cases': invalid,
            'unmapped_inherited_ids': matrix['unmapped_inherited_ids'],
            'note': 'A mapping never inherits a pass. Final human approval is separate; this tool cannot mark accepted.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    init = sub.add_parser('init')
    init.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    init.add_argument('--candidate-sha', required=True)
    init.add_argument('--output', type=Path, required=True)
    record = sub.add_parser('record')
    record.add_argument('--matrix', type=Path, required=True)
    record.add_argument('--case', required=True)
    record.add_argument('--status', required=True, choices=['passed', 'blocked', 'failed'])
    record.add_argument('--commit', required=True)
    record.add_argument('--command', required=True)
    record.add_argument('--result', required=True)
    record.add_argument('--tier', required=True, choices=['L1', 'L2', 'L3'])
    record.add_argument('--environment-json', type=Path, required=True)
    record.add_argument('--evidence', type=Path, action='append', required=True)
    record.add_argument('--actor', default='agent')
    report = sub.add_parser('summary')
    report.add_argument('--matrix', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == 'init':
        if args.output.exists():
            raise ValueError('output exists; retain prior candidate evidence and choose a new output')
        matrix = build_matrix(args.repo.resolve(), args.candidate_sha)
        output = args.output
    else:
        matrix = _read(args.matrix)
        output = args.matrix
        if args.operation == 'record':
            record_result(matrix, args.case, args.status, args.commit, args.command, args.result,
                          args.evidence, args.tier, _read(args.environment_json), actor=args.actor)
    if args.operation != 'summary':
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp = output.with_suffix('.tmp')
        tmp.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(output)
    print(json.dumps(summarize(matrix), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
