"""Proposed four-call D02b live check of the new contract and smaller package.

No holdout, automatic retry, adoption, tool use or API-key billing. The common
prompt is retained from I0; only current frozen methods and actual Task data
change. This is a new calibration record, never a rewrite of the I0 cohort.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from deck_master import method_resources, service
from deck_master.store import Store
from generate import schema
from triage import ROOT, digest, save


def run(out, reference, sample, phase):
    plan_path = ROOT.parent / 'implementation/D02b-call-plan.json'
    plan = json.loads(plan_path.read_bytes())
    if plan.get('authorized') is not True:
        raise ValueError('D02b model calls are not authorized; stop before creating a project or spending a request')
    if digest((ROOT / 'tasks.json').read_bytes()) != plan['tasks_sha256']:
        raise ValueError('fixed tasks changed')
    for name, value in plan['contract_sha256'].items():
        from generate import CONTRACTS
        if digest((CONTRACTS / name).read_bytes()) != value: raise ValueError('contract bytes changed')
    if sample not in plan['samples']:
        raise ValueError('only the two authorized development tasks can run')
    definition = next(x for x in json.loads((ROOT / 'tasks.json').read_bytes())['tasks'] if x['id'] == sample)
    if definition['split'] != 'development':
        raise ValueError('holdout input is forbidden')
    material = ROOT / 'materials' / (definition['pack_id'] + '.md')
    expected = next(x for x in json.loads((ROOT / 'manifest.json').read_bytes())['packs'] if x['id'] == definition['pack_id'])
    if digest(material.read_bytes()) != expected['sha256']:
        raise ValueError('fixed input changed')
    project = out / 'projects' / sample
    if not project.exists():
        if phase != 'framing': raise ValueError('framing must run first')
        service.create(project, brief=definition['brief'], title=definition['title'], audience=definition['audience'],
            scenario=definition['scenario'], presentation_mode=definition['presentation_mode'],
            page_limit=definition['page_limit'], existing_decisions=definition['existing_decisions'], sources=[material],
            request_input=definition['request_input'], selected_resource_ids=definition['method_selection']['framing'], business_framing=True)
    store = Store(project)
    if phase == 'argument':
        service.continue_project(project, selected_resource_ids=definition['method_selection']['argument'])
    doc = store.load_document()
    task = next(t for ref in doc['tasks'] if (t := store.read_object_json(ref))['status'] == 'awaiting_host')
    if task['collaboration_binding']['phase'] != phase: raise ValueError('unexpected phase')
    methods = method_resources.read_task_methods(project, task['task_id'])
    actual = [{k: x[k] for k in ('id', 'relative_path', 'sha256')} for x in methods['methods']]
    if actual != plan['manifests'][sample][phase]: raise ValueError('calibration method bytes changed')
    stage = out / 'calls' / sample / phase
    stage.mkdir(parents=True, exist_ok=False)
    save(stage / 'methods.json', methods)
    source = doc['sources'][0]
    prior = [store.read_object_json(ref) for t_ref in doc['tasks']
             if (old := store.read_object_json(t_ref))['status'] == 'completed' for ref in old.get('result_refs', [])]
    fixed = {'project_id': doc['project_id'], 'task_id': task['task_id'],
        'basis': {'revision_id': task['dispatch_revision'], 'input_digest': task['input_digest']},
        'source_link_template': {'source_id': source['source_id'], 'source_version': {
            'original_sha256': source['original_sha256'], 'extract': source['extract']},
            'locator': 'replace with an actual single L-number from extract.locators'},
        'narrative_input_basis': task['collaboration_binding']['eligibility_basis']}
    old_prompt = (reference / 'calls' / ('baseline--' + sample) / phase / 'prompt.txt').read_text()
    prefix = old_prompt[:old_prompt.index('{"actual_task":')]
    prefix = prefix.replace('不要虚构Ref，不提交未来v2字段。', '不要虚构Ref。本Task要求narrative.v2，使用随附合同；不向v1对象增加字段。')
    contracts = {'narrative': schema('narrative.v2.schema.json')}
    if phase == 'argument': contracts['plan'] = schema('content-plan.v2.schema.json')
    prompt = prefix + json.dumps({'actual_task': doc['task'], 'phase': phase, 'instruction': task['instruction'],
        'fixed': fixed, 'source_extract': store.read_object_json(source['extract']), 'prior_this_sample_only': prior,
        'frozen_methods': [{'id': x['id'], 'sha256': x['sha256'], 'content': x['content']} for x in methods['methods']],
        'payload_contracts': contracts}, ensure_ascii=False)
    (stage / 'prompt.txt').write_text(prompt)
    import fcntl
    ledger = out / 'calls.jsonl'
    with ledger.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX);handle.seek(0)
        count = len(handle.readlines())
        if count >= plan['max_new_calls']: raise ValueError('four-call authorization exhausted')
        reservation = {'number': plan['prior_local_calls'] + count + 1, 'sample': sample, 'phase': phase,
            'prompt_sha256': digest(prompt.encode()), 'prompt_bytes': len(prompt.encode()),
            'call_plan_sha256': digest(plan_path.read_bytes()), 'requested_model_id': plan['model']}
        handle.write(json.dumps(reservation) + '\n');handle.flush();os.fsync(handle.fileno())
    execution = 'codex:D02b:' + sample + ':' + phase
    service.task_start(project, task_id=task['task_id'], execution_ref=execution,
        supported_protocols=['compose.v2'], capabilities=task['required_capabilities'])
    fresh = stage / 'fresh-context';fresh.mkdir()
    cmd = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check', '-C', str(fresh),
        '-s', 'read-only', '-m', plan['model'], '-c', 'model_reasoning_effort="high"', '--json', '--color', 'never',
        '--output-last-message', str(stage / 'response.txt'), '-']
    print(json.dumps({'event': 'start', **reservation}), flush=True)
    started = time.monotonic()
    with (stage / 'events.jsonl').open('xb') as stdout, (stage / 'stderr.txt').open('xb') as stderr:
        process = subprocess.run(cmd, input=prompt.encode(), stdout=stdout, stderr=stderr, timeout=900,
            env={k: v for k, v in os.environ.items() if k not in ('OPENAI_API_KEY', 'CODEX_API_KEY')}, check=False)
    save(stage / 'process.json', {'returncode': process.returncode, 'elapsed_seconds': time.monotonic()-started})
    if process.returncode: raise RuntimeError('model process failed; preserve record; no automatic retry')
    events = [json.loads(x) for x in (stage / 'events.jsonl').read_text().splitlines()]
    if (sum(e['type'] == 'turn.completed' for e in events) != 1 or
        any(e.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'web_search') for e in events)):
        raise RuntimeError('unexpected model activity; investigate request count')
    response = json.loads((stage / 'response.txt').read_bytes())
    if set(response) != {'payload', 'author_notes'}: raise ValueError('unexpected response shape')
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose',
        'variant': 'framing' if phase == 'framing' else 'narrative', 'task_id': task['task_id'],
        'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
        'payload': response['payload'], 'usage_events': []}
    save(stage / 'envelope.json', envelope)
    result = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
        produced_against=task['produced_against'], result_payload=envelope)
    save(stage / 'receipt.json', result)
    save(stage / 'usage.json', next(e for e in events if e['type'] == 'turn.completed'))
    (stage / 'author-notes.md').write_text(response['author_notes'])
    print(json.dumps({'event': 'accepted', 'sample': sample, 'phase': phase, 'status': result['status']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reference-run', type=Path, required=True)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--phase', choices=['framing', 'argument'], required=True)
    args = parser.parse_args()
    run(args.out.resolve(), args.reference_run.resolve(), args.sample, args.phase)
