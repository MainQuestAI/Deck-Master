"""Four specifically authorized D03 subscription requests, one shared reservation ledger.

Actual generation and native review only; no fallback, retry or holdout. Native
transport instrumentation records its own actual prompt/completion and checks the
frozen model before turn/start; it never supplies or changes judgments/receipts.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib

from deck_master import method_resources, native_review, outline_review, service
from deck_master.native_review_transport import CodexReviewSession, probe_native_client
from deck_master.store import Store
from generate import schema, CONTRACTS
from triage import ROOT, digest, save

PLAN = ROOT.parent / 'implementation/D03-call-plan.json'


def frozen():
    plan = json.loads(PLAN.read_bytes())
    if plan.get('authorized') is not True:
        raise ValueError('D03 allocation is not authorized')
    for filename, expected in plan['frozen_files_sha256'].items():
        if digest(Path(filename).read_bytes()) != expected:
            raise ValueError('frozen D03 input/transport changed: ' + filename)
    if digest(Path(__file__).read_bytes()) != plan['runner_sha256']:
        raise ValueError('D03 runner changed')
    original = json.loads((ROOT.parent / 'implementation/D02b-call-plan.json').read_bytes())
    for filename, expected in original['contract_sha256'].items():
        if digest((CONTRACTS / filename).read_bytes()) != expected:
            raise ValueError('frozen generation contract changed')
    return plan, original


def reserve(out, plan, number, **evidence):
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'calls.jsonl').open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX);handle.seek(0)
        previous = [json.loads(line) for line in handle]
        if len(previous) >= plan['max_new_calls'] or number != 29 + len(previous):
            raise ValueError('retain prior call; no duplicate, skipped or extra reservations')
        row = {**next(c for c in plan['calls'] if c['number'] == number),
               'call_plan_sha256': digest(PLAN.read_bytes()), **evidence}
        handle.write(json.dumps(row, ensure_ascii=False) + '\n');handle.flush();os.fsync(handle.fileno())
    print(json.dumps({'event': 'reserved', **row}, ensure_ascii=False), flush=True)


def prepare(out, reference, phase):
    plan, original = frozen()
    base = plan['fixed_framework_input']['base_task']
    definition = next(t for t in json.loads((ROOT / 'tasks.json').read_bytes())['tasks'] if t['id'] == base)
    if definition['split'] != 'development':raise ValueError('holdout forbidden')
    material = ROOT / 'materials' / (definition['pack_id'] + '.md')
    project = out / 'projects/dev-01-fixed-framework'
    if not project.exists():
        if phase != 'framing':raise ValueError('framing must precede argument')
        service.create(project, brief=definition['brief'], title='dev-01 合成既定框架', audience=definition['audience'],
            scenario=definition['scenario'], presentation_mode=definition['presentation_mode'], page_limit=definition['page_limit'],
            existing_decisions=[*definition['existing_decisions'], plan['fixed_framework_input']['instruction']],
            sources=[material], request_input=definition['request_input'], business_framing=True,
            selected_resource_ids=definition['method_selection']['framing'])
    store = Store(project)
    stage = out / 'calls/dev-01-fixed-framework' / phase
    if stage.exists():raise ValueError('retain previous preparation; do not overwrite/retry')
    if phase == 'argument':service.continue_project(project, selected_resource_ids=definition['method_selection']['argument'])
    document = store.load_document()
    pending = [t for r in document['tasks'] if (t := store.read_object_json(r))['status'] == 'awaiting_host']
    if len(pending) != 1 or pending[0]['collaboration_binding']['phase'] != phase:raise ValueError('unexpected phase')
    task = pending[0];methods = method_resources.read_task_methods(project, task['task_id'])
    if methods['status'] != 'current' or [{k:m[k] for k in ('id','relative_path','sha256')} for m in methods['methods']] != original['manifests'][base][phase]:
        raise ValueError('frozen D02b method bytes changed')
    stage.mkdir(parents=True);save(stage / 'methods.json', methods);save(stage / 'task.json', task)
    source = document['sources'][0]
    fixed = {'project_id':document['project_id'],'task_id':task['task_id'],
        'basis':{'revision_id':task['dispatch_revision'],'input_digest':task['input_digest']},
        'source_link_template':{'source_id':source['source_id'],'source_version':{'original_sha256':source['original_sha256'],'extract':source['extract']},
                               'locator':'replace with an actual single L-number from extract.locators'},
        'narrative_input_basis':task['collaboration_binding']['eligibility_basis']}
    old = (reference / 'calls' / ('baseline--' + base) / phase / 'prompt.txt').read_text()
    if digest(old.encode()) != plan['reference_prompts_sha256'][phase]:raise ValueError('frozen reference prompt changed')
    prefix = old[:old.index('{"actual_task":')].replace('不要虚构Ref，不提交未来v2字段。','不要虚构Ref。本Task要求narrative.v2，使用随附合同；不向v1对象增加字段。')
    contracts = {'narrative':schema('narrative.v2.schema.json')}
    if phase == 'argument':contracts['plan'] = schema('content-plan.v2.schema.json')
    prompt = prefix + json.dumps({'actual_task':document['task'],'phase':phase,'instruction':task['instruction'],'fixed':fixed,
        'source_extract':store.read_object_json(source['extract']),
        'prior_this_sample_only':[store.read_object_json(r) for t_ref in document['tasks'] if (t := store.read_object_json(t_ref))['status']=='completed' for r in t['result_refs']],
        'frozen_methods':[{'id':m['id'],'sha256':m['sha256'],'content':m['content']} for m in methods['methods']],
        'payload_contracts':contracts},ensure_ascii=False)
    (stage / 'prompt.txt').write_text(prompt)
    print(json.dumps({'event':'prepared','phase':phase,'prompt_bytes':len(prompt.encode()),'model_called':False}),flush=True)


def generate(out, phase):
    plan, _ = frozen();project = out / 'projects/dev-01-fixed-framework';store = Store(project)
    stage = out / 'calls/dev-01-fixed-framework' / phase
    task = json.loads((stage / 'task.json').read_bytes());prompt = (stage / 'prompt.txt').read_bytes()
    if probe_native_client(check_login=True)['status'] != 'prerequisites_ready':raise ValueError('subscription login required')
    reserve(out,plan,29 if phase=='framing' else 30,prompt_sha256=digest(prompt),prompt_bytes=len(prompt),requested_model=plan['generation_model'])
    service.task_start(project,task_id=task['task_id'],execution_ref='codex:D03:fixed-framework:'+phase,
        supported_protocols=['compose.v2'],capabilities=task['required_capabilities'])
    fresh = stage / 'fresh-context';fresh.mkdir()
    cmd = ['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','-C',str(fresh),'-s','read-only',
           '-m',plan['generation_model'],'-c','model_reasoning_effort="high"','--json','--color','never',
           '--output-last-message',str(stage / 'response.txt'),'-']
    started = time.monotonic()
    with (stage/'events.jsonl').open('xb') as stdout,(stage/'stderr.txt').open('xb') as stderr:
        process = subprocess.run(cmd,input=prompt,stdout=stdout,stderr=stderr,timeout=900,check=False,
            env={k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY','CODEX_API_KEY')})
    save(stage/'process.json',{'returncode':process.returncode,'elapsed_seconds':time.monotonic()-started})
    if process.returncode:raise RuntimeError('model failed; no automatic retry')
    events = [json.loads(line) for line in (stage/'events.jsonl').read_text().splitlines()]
    if sum(e['type']=='turn.completed' for e in events)!=1 or any(e.get('item',{}).get('type') in ('command_execution','mcp_tool_call','web_search') for e in events):
        raise RuntimeError('unexpected model activity; preserve and reconcile')
    response = json.loads((stage/'response.txt').read_bytes())
    if set(response)!={'payload','author_notes'}:raise ValueError('unexpected response shape')
    envelope = {'schema_version':'compose_result.v2','kind':'compose','variant':'framing' if phase=='framing' else 'narrative',
        'task_id':task['task_id'],'operation_id':task['operation_id'],'produced_against':task['produced_against'],
        'eligibility_digest':task['collaboration_binding']['eligibility_digest'],'payload':response['payload'],'usage_events':[]}
    save(stage/'envelope.json',envelope)
    result = service.accept_result(project,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],result_payload=envelope)
    save(stage/'receipt.json',result);save(stage/'usage.json',next(e for e in events if e['type']=='turn.completed'))
    (stage/'author-notes.md').write_text(response['author_notes'])
    print(json.dumps({'event':'accepted','phase':phase,'status':result['status']}),flush=True)


def review(out, project, number):
    plan, _ = frozen()
    config = tomllib.loads((Path.home()/'.codex/config.toml').read_text())
    if config.get('model')!=plan['review_model'] or config.get('model_reasoning_effort')!='medium':
        raise ValueError('native model/reasoning settings changed; stop before turn')
    store = Store(project);packet = outline_review.packet(store,store.load_document())
    stage = out / 'calls' / ('native-'+str(number));stage.mkdir(parents=True,exist_ok=False)
    save(stage/'packet-before.json',packet)
    reserve(out,plan,number,subjects=packet['subjects'],requested_model=plan['review_model'])
    class AuditedSession(CodexReviewSession):
        def __enter__(self):
            super().__enter__()
            if self.model!=plan['review_model']:
                self.__exit__(None,None,None)
                raise ValueError('native session model differs from frozen allocation')
            save(stage/'session.json',{'model':self.model,'thread_id':self.thread_id,'execution_ref':self.execution_ref,
                'native_openai_subscription_login_checked':True,'model_called':False})
            return self
        def review(self,prompt,contract):
            (stage/'prompt.txt').write_text(prompt);save(stage/'output-schema.json',contract)
            save(stage/'turn-start.json',{'prompt_sha256':digest(prompt.encode()),'prompt_bytes':len(prompt.encode()),'model':self.model})
            observation = super().review(prompt,contract)
            save(stage/'observation.json',observation)
            return observation
    original = native_review.CodexReviewSession;native_review.CodexReviewSession = AuditedSession
    started = time.monotonic()
    try:
        result = native_review.run(project,subject='outline',selected_resource_ids=plan['review_selected_resource_ids'])
        save(stage/'result.json',result)
        print(json.dumps({'event':'review_result','number':number,'status':result['status'],'gate':result.get('preproduction',{}).get('status')},ensure_ascii=False),flush=True)
    except Exception as exc:
        save(stage/'failure.json',{'type':type(exc).__name__,'error_code':getattr(exc,'error_code',None),'message':str(exc)})
        raise
    finally:
        native_review.CodexReviewSession = original
        save(stage/'process.json',{'elapsed_seconds':time.monotonic()-started})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','generate','review']);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--reference-run',type=Path);parser.add_argument('--phase',choices=['framing','argument'])
    parser.add_argument('--project',type=Path);parser.add_argument('--number',type=int,choices=[31,32])
    args = parser.parse_args()
    if args.action=='prepare':prepare(args.out.resolve(),args.reference_run.resolve(),args.phase)
    elif args.action=='generate':generate(args.out.resolve(),args.phase)
    else:review(args.out.resolve(),args.project.resolve(),args.number)
