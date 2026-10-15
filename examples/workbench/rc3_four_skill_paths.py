"""Prepare/verify 16 real installed Host responsibility workorders.

This external stdlib driver never imports source deck_master. It runs the chosen
candidate interpreter with -I. Preparation reads real project/task state and
writes a packet outside the sources; it does not fabricate model outputs. The
Host must actually apply each workorder, submit through normal Runtime paths
where needed, then supply application records for verification. Verification
validates records and current state; it does not certify independent identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

SKILLS = ('deck-master', 'deck-content', 'deck-design', 'deck-review')
MODES = ('named', 'natural', 'master', 'recovery')
EXPECTED = {(skill, mode) for skill in SKILLS for mode in MODES}
OUTPUTS = {
    'deck-master': ['task_understanding', 'effective_scope', 'next_responsibility', 'gaps'],
    'deck-content': ['requested_content_artifacts', 'content_checks', 'completion'],
    'deck-design': ['design_scheme_or_recipe', 'coverage', 'layout_reasons', 'content_basis'],
    'deck-review': ['findings', 'source_unchanged', 'coverage', 'limitations', 'evidence_level'],
}
WORKER = r'''
import hashlib,json,sys
from pathlib import Path
import deck_master
from deck_master import method_resources
from deck_master.store import Store

def snapshot(root):
    root=Path(root)
    if root.is_file():
        return {root.name:hashlib.sha256(root.read_bytes()).hexdigest()}
    return {p.relative_to(root).as_posix():({'symlink':str(p.readlink())} if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(root.rglob('*')) if p.is_file() or p.is_symlink()}

case=json.loads(sys.stdin.read())
project=case.get('project')
source=case.get('source')
result=method_resources.read_skill_methods(case['skill'],entry_mode=case['entry_mode'],project=project,
    task_id=case.get('task_id'),text=case['instruction'] if case['entry_mode']=='natural' else None)
if not Path(deck_master.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
    raise RuntimeError('candidate interpreter borrowed a source module')
if case.get('skill_entry'):
    entry=Path(case['skill_entry']).resolve(strict=True)
    release=Path(sys.prefix).resolve().parent
    if entry != release/'skill'/case['skill']/'SKILL.md':
        raise RuntimeError('Host Skill and Python belong to different releases')
else:
    entry=None
facts=[]
if project:
    store=Store(project);document=store.load_document()
    for ref in document['tasks']:
        task=store.read_object_json(ref)
        facts.append({'task_id':task['task_id'],'kind':task['kind'],'status':task['status'],
                      'call_allowances':task.get('call_allowances',[]),'generation_attempts':task.get('generation_attempts',[])})
print(json.dumps({'module_path':str(Path(deck_master.__file__).resolve()),'package_version':deck_master.__version__,
    'python':sys.executable,'prefix':sys.prefix,'skill_entry':str(entry) if entry else None,
    'skill_entry_sha256':hashlib.sha256(entry.read_bytes()).hexdigest() if entry else None,
    'consumption':result,'source_snapshot':snapshot(source) if source else None,'call_facts':facts},ensure_ascii=False))
'''


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_cases(path):
    payload = json.loads(Path(path).read_text())
    cases = payload['cases']
    pairs = [(item['skill'], item['entry_mode']) for item in cases]
    if len(pairs) != 16 or set(pairs) != EXPECTED:
        raise ValueError('cases must contain each of the 16 Skill/entry combinations exactly once')
    for item in cases:
        if not item.get('instruction') or not item.get('skill_entry'):
            raise ValueError('each case requires original instruction and actual loaded Host Skill entry')
        if item['skill'] == 'deck-content' and not item.get('task_id'):
            raise ValueError('Content application must consume a real scoped Task workorder')
        if item['skill'] == 'deck-review' and not item.get('source'):
            raise ValueError('Review requires an explicit immutable source outside its report output')
    return cases


def _run(python, case):
    result = subprocess.run([str(Path(python).absolute()), '-I', '-c', WORKER], input=json.dumps(case),
                            text=True, capture_output=True, timeout=120, check=True)
    return json.loads(result.stdout)


def _outside_sources(out, cases):
    for case in cases:
        for key in ('project', 'source'):
            if case.get(key):
                source = Path(case[key]).resolve()
                if out.is_relative_to(source) or source.is_relative_to(out):
                    raise ValueError('packet output must not overlap any project or review source')


def prepare(python, cases_path, out):
    cases = _read_cases(cases_path)
    out = Path(out).resolve()
    _outside_sources(out, cases)
    out.mkdir(parents=True, exist_ok=False)
    packet = {'schema_version': 'four_skill_host_packet.v1', 'status': 'host_application_not_run',
              'cases_sha256': _sha(cases_path), 'python': str(Path(python).absolute()), 'cases': []}
    for case in cases:
        identity = case['skill'] + '--' + case['entry_mode']
        actual = _run(python, case)
        workorder = {**case, 'case_id': identity, 'required_output_fields': OUTPUTS[case['skill']],
                     'actual': actual,
                     'constraints': ['Preserve current Runtime scope and instruction evidence',
                                     'No image calls for these responsibility-only cases',
                                     'No production or source writes during strict Review',
                                     'Apply the returned method bytes; reading them alone is not application',
                                     'Record actual output files, Runtime completion and exact execution provenance']}
        path = out / (identity + '.workorder.json')
        path.write_text(json.dumps(workorder, ensure_ascii=False, indent=2) + '\n')
        template = {'case_id': identity, 'workorder_sha256': _sha(path), 'executed': False,
                    'execution': {'source': None, 'locator': None, 'evidence_level': 'host_attested'},
                    'method_applications': [], 'output': {}, 'output_files': [],
                    'runtime_status_expected': None, 'limitations': ['NOT_RUN']}
        (out / (identity + '.application.json')).write_text(json.dumps(template, indent=2) + '\n')
        packet['cases'].append({'case_id': identity, 'workorder': path.name, 'sha256': _sha(path)})
    (out / 'packet.json').write_text(json.dumps(packet, indent=2) + '\n')
    return {'status': 'host_application_not_run', 'packet': str(out / 'packet.json'), 'cases': 16}


def verify(out):
    out = Path(out).resolve()
    packet = json.loads((out / 'packet.json').read_text())
    if (packet.get('schema_version') != 'four_skill_host_packet.v1' or len(packet['cases']) != 16
            or {row['case_id'] for row in packet['cases']} != {skill + '--' + mode for skill, mode in EXPECTED}):
        raise ValueError('verification requires the complete frozen 16-path packet')
    results = []
    for row in packet['cases']:
        path = out / row['workorder']
        if _sha(path) != row['sha256']:
            raise ValueError('frozen workorder changed: ' + row['case_id'])
        order = json.loads(path.read_text())
        record = json.loads((out / (row['case_id'] + '.application.json')).read_text())
        if record['case_id'] != row['case_id'] or record['workorder_sha256'] != row['sha256']:
            raise ValueError('application record is not bound to its exact workorder')
        if not record['executed'] or not record['execution'].get('locator') or not record['execution'].get('source'):
            raise ValueError('actual Host execution has not been recorded: ' + row['case_id'])
        methods = order['actual']['consumption']['methods']
        expected = {(item['id'], item['sha256']) for item in methods}
        supplied = {(item['id'], item['sha256']) for item in record['method_applications'] if item.get('application')}
        if supplied != expected:
            raise ValueError('each actual method requires a concrete application note: ' + row['case_id'])
        if set(OUTPUTS[order['skill']]) - set(record['output']):
            raise ValueError('responsibility output is incomplete: ' + row['case_id'])
        if not record['output_files']:
            raise ValueError('application requires actual inspectable output bytes')
        for item in record['output_files']:
            artifact = Path(item['path']).resolve()
            if not artifact.is_relative_to(out) or not artifact.is_file() or _sha(artifact) != item['sha256']:
                raise ValueError('application output missing, outside packet or hash differs')
        actual = _run(packet['python'], order)
        before = order['actual']
        if (actual['module_path'] != before['module_path'] or actual['package_version'] != before['package_version']
                or actual['skill_entry_sha256'] != before['skill_entry_sha256']):
            raise ValueError('installed Host identity changed during application')
        if ([task for task in actual['call_facts'] if task['kind'] == 'blueprint']
                != [task for task in before['call_facts'] if task['kind'] == 'blueprint']):
            raise ValueError('responsibility-only case performed unexpected production work')
        context = actual['consumption']['context']
        if record.get('runtime_status_expected') is not None:
            if context is None or context['completion']['state'] != record['runtime_status_expected']:
                raise ValueError('recorded completion does not match actual Runtime projection')
        if order['skill'] == 'deck-content':
            completion = context['completion']
            if (record.get('runtime_status_expected') != 'completed'
                    or completion['state'] != 'completed' or not completion['outputs']
                    or completion['content_intent'] != order.get('content_intent')):
                raise ValueError('Content must normally complete its exact sub-intent with actual Runtime outputs')
        if order['skill'] == 'deck-review' and actual['source_snapshot'] != before['source_snapshot']:
            raise ValueError('strict Review changed its source')
        results.append({'case_id': row['case_id'], 'status': 'record_and_outputs_verified',
                        'actual_completion': context['completion'] if context else None,
                        'host_application_evidence': 'recorded_host_attestation_not_independently_verified',
                        'independent_human_native_desktop': 'not_claimed'})
    report = {'status': 'application_records_verified', 'cases': results,
              'limitations': ['Owner/Root must link the real Host execution provenance; JSON alone cannot prove model use or independent identity']}
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--python', required=True)
    prep.add_argument('--cases', required=True)
    prep.add_argument('--out', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--out', required=True)
    args = parser.parse_args()
    result = prepare(args.python, args.cases, args.out) if args.action == 'prepare' else verify(args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
