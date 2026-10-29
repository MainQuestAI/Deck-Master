"""One frozen D00 generation stage per invocation, through real Runtime tasks.

No review, adoption, model fallback or automatic retry. Run outputs stay outside
the repository. Each initiated CLI request is reserved before transmission;
timeouts/unknown outcomes stay reserved and require investigation.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from deck_master import method_resources, models, service
from deck_master.store import Store

from triage import ROOT, digest, save


CONTRACTS = Path(models.__file__).parent / 'resources' / 'contracts'


def schema(filename: str, pointer: str = ''):
    value = json.loads((CONTRACTS / filename).read_bytes())
    for part in pointer.lstrip('/').split('/') if pointer else []:
        value = value[part.replace('~1', '/').replace('~0', '~')]

    def expand(node):
        if isinstance(node, list):
            return [expand(item) for item in node]
        if not isinstance(node, dict):
            return node
        if '$ref' in node:
            target, _, fragment = node['$ref'].partition('#')
            return schema(target or filename, fragment)
        return {key: expand(item) for key, item in node.items()
                if key not in ('$schema', '$defs')}
    return expand(value)


def generate(out: Path, sample: str, phase: str):
    freeze = json.loads((ROOT / 'freeze.json').read_bytes())
    if freeze['status'] != 'frozen_for_I0' or not freeze['budget']['authorization']:
        raise ValueError('I0 must be frozen and explicitly authorized')
    for name, field in [('manifest.json', 'materials_manifest_sha256'), ('tasks.json', 'tasks_sha256'),
                        ('protocol.md', 'protocol_sha256'), ('experiment.md', 'experiment_sha256'),
                        ('report-template.md', 'report_template_sha256')]:
        if digest((ROOT / name).read_bytes()) != freeze[field]:
            raise ValueError(f'frozen file changed: {name}')
    definitions = json.loads((ROOT / 'tasks.json').read_bytes())['tasks']
    arm, task_id = sample.split('--', 1)
    if arm not in ('baseline', 'experiment'):
        raise ValueError('sample arm must be baseline or experiment')
    definition = next(item for item in definitions if item['id'] == task_id)
    if definition['split'] != 'development':
        raise ValueError('D00 generator cannot access holdout tasks')
    material = next(pack for pack in json.loads((ROOT / 'manifest.json').read_bytes())['packs']
                    if pack['id'] == definition['pack_id'])
    source = ROOT / material['path']
    if digest(source.read_bytes()) != material['sha256']:
        raise ValueError('fixed source changed')
    out.mkdir(parents=True, exist_ok=True)
    project = out / 'projects' / sample
    if not project.exists():
        if phase != 'framing':
            raise ValueError('framing must run first')
        created = service.create(project, brief=definition['brief'], title=definition['title'],
            sources=[source], audience=definition['audience'], scenario=definition['scenario'],
            presentation_mode=definition['presentation_mode'], page_limit=definition['page_limit'],
            existing_decisions=definition['existing_decisions'], request_input=definition['request_input'],
            selected_resource_ids=definition['method_selection']['framing'])
        save(out / 'created' / f'{sample}.json', created)
    store = Store(project)
    document = store.load_document()
    pending = [store.read_object_json(ref) for ref in document['tasks']
               if store.read_object_json(ref)['status'] in ('awaiting_host', 'running')]
    if not pending and phase == 'argument':
        continued = service.continue_project(project, selected_resource_ids=definition['method_selection']['argument'])
        save(out / 'continued' / f'{sample}.json', continued)
        document = store.load_document()
        pending = [store.read_object_json(ref) for ref in document['tasks']
                   if store.read_object_json(ref)['status'] in ('awaiting_host', 'running')]
    if len(pending) != 1 or pending[0]['collaboration_binding']['phase'] != phase:
        raise ValueError('expected one pending Task in the requested phase')
    task = pending[0]
    stage = out / 'calls' / sample / phase
    stage.mkdir(parents=True, exist_ok=False)
    consumed = method_resources.read_task_methods(project, task['task_id'])
    if consumed['status'] != 'current':
        raise ValueError('method basis is not current')
    save(stage / 'methods.json', consumed)
    source_entry = document['sources'][0]
    extract = store.read_object_json(source_entry['extract'])
    prior = []
    for ref in document['tasks']:
        old = store.read_object_json(ref)
        if old['status'] == 'completed':
            prior.extend(store.read_object_json(item) for item in old.get('result_refs', []))
    fixed = {'project_id': document['project_id'], 'task_id': task['task_id'],
             'basis': {'revision_id': task['dispatch_revision'], 'input_digest': task['input_digest']},
             'source_link_template': {'source_id': source_entry['source_id'], 'source_version': {
                 'original_sha256': source_entry['original_sha256'], 'extract': source_entry['extract']},
                 'locator': 'replace with an actual single L-number from extract.locators'},
             'narrative_input_basis': task['collaboration_binding']['eligibility_basis']}
    payload_schemas = {'narrative': schema('narrative.v1.schema.json')}
    if phase == 'argument':
        payload_schemas['plan'] = schema('content-plan.v2.schema.json')
    prompt = (
        '你在独立新会话中执行一个真实 Deck Master 内容 Task。只使用本提示提供的资料和方法。'
        '禁止使用任何工具、读取文件、运行命令、调用模型或请求子Agent。不要评审另一份稿。'
        '只输出一个合法 JSON 对象，结构为 {"payload":{...},"author_notes":"完整可读策划说明（Markdown字符串）"}。'
        '不要代码围栏或额外前后文字。payload仅含本阶段允许的字段，author_notes在Runtime信封之外。'
        '严格使用所附最新合同。不要虚构Ref，不提交未来v2字段。'
        'framing只含maturity=framing的narrative；argument必须含maturity=argument的narrative和mode=planned的plan。'
        'plan.narrative_ref=null，由Runtime绑定同次提交的Narrative；page_links=[]；previous_ref=null；'
        'origin=host_composed；version=1。Narrative.input_basis使用给出的依据。'
        'plan.basis和task_id使用fixed原值。所有reported_fact须用正确source_id/version与实际单个L号定位。'
        'argument全部节点须通过有实际意义的edges/qualification_node_ids与中心连通；Plan的节点ID必须存在。'
        '最多6页只规划职责与具体展开，不写Page、口播、视觉，不作采用或批准。'
        'author_notes须自包含地说明主张、可展开主题及关系、逐页内容安排、场景、关键限制与具体取舍；'
        '论证和取舍依据需足以供作者判断，不以方法打卡代替实际内容。\n'
        + json.dumps({'actual_task': document['task'], 'phase': phase, 'instruction': task['instruction'],
                      'fixed': fixed, 'source_extract': extract, 'prior_this_sample_only': prior,
                      'frozen_methods': [{'id': row['id'], 'sha256': row['sha256'], 'content': row['content']}
                                         for row in consumed['methods']], 'payload_contracts': payload_schemas}, ensure_ascii=False)
    )
    if arm == 'experiment':
        prompt += '\n实验补充指令（不改运行合同）：\n' + (ROOT / 'experiment.md').read_text()
    (stage / 'prompt.txt').write_text(prompt, encoding='utf-8')
    # Reserve under a filesystem lock; an unknown transmission is never free.
    import fcntl
    ledger = out / 'budget.jsonl'
    execution = 'd00-' + uuid.uuid4().hex
    with ledger.open('a+', encoding='utf-8') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        initiated = sum(1 for line in handle if line.strip())
        if initiated >= freeze['budget']['generation_planned'] + freeze['budget']['failure_retry_reserve']:
            raise ValueError('generation/retry request bound exhausted')
        reservation = {'number': initiated + 1, 'sample': sample, 'phase': phase,
                       'execution_ref': execution, 'requested_model': freeze['generation']['requested_model_id'],
                       'prompt_sha256': digest(prompt.encode()), 'prompt_bytes': len(prompt.encode()),
                       'freeze_sha256': digest((ROOT / 'freeze.json').read_bytes())}
        handle.write(json.dumps(reservation) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    service.task_start(project, task_id=task['task_id'], execution_ref=execution,
                       supported_protocols=['compose.v2'], capabilities=task['required_capabilities'])
    # No HOME/config mutation. Auth uses the observed existing ChatGPT login.
    fresh = stage / 'fresh-context'
    fresh.mkdir()
    cmd = ['codex', 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
           '-C', str(fresh), '-s', 'read-only', '-m', freeze['generation']['requested_model_id'],
           '-c', 'model_reasoning_effort="high"', '--json', '--color', 'never',
           '--output-last-message', str(stage / 'response.txt'), '-']
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('OPENAI_API_KEY', 'CODEX_API_KEY')}
    started = time.monotonic()
    print(json.dumps({'event': 'generation_start', **reservation}), flush=True)
    with (stage / 'events.jsonl').open('xb') as stdout, (stage / 'stderr.txt').open('xb') as stderr:
        result = subprocess.run(cmd, input=prompt.encode(), stdout=stdout, stderr=stderr,
                                env=environment, timeout=900, check=False)
    save(stage / 'process.json', {'returncode': result.returncode, 'elapsed_seconds': time.monotonic() - started})
    if result.returncode:
        raise RuntimeError(f'model process failed ({result.returncode}); inspect local stderr; no automatic retry')
    events = [json.loads(line) for line in (stage / 'events.jsonl').read_text().splitlines() if line.strip()]
    if any(event.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'web_search') for event in events):
        raise RuntimeError('unexpected tool activity; preserve trace and stop the budget audit')
    turns = [event for event in events if event.get('type') == 'turn.completed']
    if len(turns) != 1:
        raise RuntimeError('model request count not bounded by a single observed turn; investigate before continuing')
    response = json.loads((stage / 'response.txt').read_text())
    if set(response) != {'payload', 'author_notes'} or not isinstance(response['author_notes'], str):
        raise ValueError('model output must contain only payload and author_notes')
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose',
                'variant': 'framing' if phase == 'framing' else 'narrative',
                'task_id': task['task_id'], 'operation_id': task['operation_id'],
                'produced_against': task['produced_against'],
                'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
                'payload': response['payload'], 'usage_events': []}
    save(stage / 'envelope.json', envelope)
    accepted = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                                    produced_against=task['produced_against'], result_payload=envelope)
    save(stage / 'acceptance.json', accepted)
    (stage / 'author-notes.md').write_text(response['author_notes'], encoding='utf-8')
    save(stage / 'usage.json', turns[0])
    print(json.dumps({'event': 'generation_accepted', 'sample': sample, 'phase': phase,
                      'status': accepted['status'], 'usage': turns[0].get('usage')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sample', required=True)
    parser.add_argument('--phase', choices=['framing', 'argument'], required=True)
    args = parser.parse_args()
    generate(args.out.expanduser().resolve(), args.sample, args.phase)
