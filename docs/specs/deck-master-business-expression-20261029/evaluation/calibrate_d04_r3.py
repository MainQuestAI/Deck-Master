"""Authorized D04 subscription validation, revised total 10-slot budget, one explicit recheck, no automatic retry.

The runtime owns all requests/Tasks/Review receipts. Instrumentation only records
actual prompts/completions, never supplies review judgments or edits content.
"""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import tomllib

from deck_master import business_outline, collaboration, content_production, content_review, method_resources, native_review, outline_review, service
from deck_master.native_review_transport import CodexReviewSession, probe_native_client
from deck_master.store import Store
from generate import schema
from triage import ROOT, digest, save

PLAN=ROOT.parent/'implementation/D04-call-plan-r3.json'


def frozen():
    p=json.loads(PLAN.read_bytes())
    if not p.get('authorized') or p.get('authorized_new_calls')!=10:raise ValueError('D04 separate budget not authorized')
    prior=p['prior_attempt']
    if digest(Path(prior['path']).read_bytes())!=prior['sha256']:raise ValueError('immutable prior budget ledger changed')
    for file,sha in p['frozen_files_sha256'].items():
        if digest(Path(file).read_bytes())!=sha:raise ValueError('frozen D04 source changed: '+file)
    if digest(Path(__file__).read_bytes())!=p['runner_sha256']:raise ValueError('frozen runner changed')
    return p


def specification(p,number):return next(c for c in p['calls'] if c['number']==number)


def tree_digest(path):
    return digest('\n'.join(str(f.relative_to(path))+':'+digest(f.read_bytes()) for f in sorted(path.rglob('*')) if f.is_file()).encode())


def request(path,*,intent,scope,operation,text):
    store=Store(path);doc=store.load_document();old=doc['collaboration']['request']
    return collaboration.start_request(path,input={'intent':intent,'content_intent':'content_full' if intent=='content_only' else None,
        'replace_request_id':old['request_id'],'scope':scope,'instruction_evidence':{'kind':'host_attested_instruction',
        'text':text,'source_locator':'development:d04-approved:'+operation}},base_revision=doc['revision_id'],operation_id=operation)


def prepare_projects(out):
    p=frozen();out.mkdir(parents=True,exist_ok=True)
    for name,source in p['prepared_projects'].items():
        origin=Path(source['path']);path=out/'projects'/name
        if path.exists():raise ValueError('retain prior prepared project; no overwrite')
        if tree_digest(origin)!=source['tree_sha256']:raise ValueError('preflight project changed')
        shutil.copytree(origin,path);store=Store(path);doc=store.load_document()
        assert [doc['narrative'],doc['content_plan']]==source['refs']
        scope=business_outline.scope_for(doc['collaboration']['request'])
        if name=='negative':
            scope.update(layers=['review'],page_manifest_ref=doc['content_plan'])
            intent='review_only';text='D04 独立反例审查：本工程副本故意含三类错误，不代表老板观点或模型生成稿。用户已批总上限10次（原失败已用1次）现有订阅，本次只审固定反例大纲，不修稿、不制作内容。'
        else:
            scope.update(layers=['narrative','plan','page_copy','speech','review'],allow_page_membership_change=True)
            intent='content_only';text='老板认可两份稿可展开并已批D04总上限10次（原失败已用1次）现有Codex订阅。当前正式有界请求沿已采用六页主线写完整正文／案例与明确请求的逐字讲稿（独立讲稿输出）；历史brief中的“仅策划”是已完成旧阶段的产物边界，不是本次范围。保持业务事实、框架、页序、节点与必要限定；不做视觉、SVG、PPT或D08，无API付费或自动重试。'
        receipt=request(path,intent=intent,scope=scope,operation='approved-'+name,text=text)
        save(out/'prepared'/f'{name}.json',{'source_tree_sha256':source['tree_sha256'],'source_unchanged':tree_digest(origin)==source['tree_sha256'],
            'refs':source['refs'],'request_receipt':receipt,'model_called':False})
    print(json.dumps({'event':'projects_prepared','model_calls':0}),flush=True)


def reserve(out,p,number,**evidence):
    with (out/'calls.jsonl').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);f.seek(0);rows=[json.loads(line) for line in f]
        if number!=p['calls_used_at_freeze']+len(rows)+1 or p['calls_used_at_freeze']+len(rows)>=p['authorized_new_calls']:raise ValueError('D04 attempt already reserved, out of order or exhausted')
        row={**specification(p,number),'budget_id':p['budget_id'],'call_plan_sha256':digest(PLAN.read_bytes()),**evidence}
        f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'event':'reserved',**row},ensure_ascii=False),flush=True)


def admitted(out,number):
    path=out/'gates'/f'{number:02}.json'
    if not path.exists():raise ValueError('previous real result has not been inspected/admitted')
    value=json.loads(path.read_bytes())
    if not value.get('accepted_for_next_step') or value.get('call_plan_sha256')!=digest(PLAN.read_bytes()):
        raise ValueError('previous gate is not admitted against this frozen plan')


def review(out,number):
    p=frozen();spec=specification(p,number)
    if number>2:admitted(out,number-1)
    if spec['kind'] not in ('native_outline_review','native_full_content_review'):raise ValueError('not review')
    config=tomllib.loads((Path.home()/'.codex/config.toml').read_text())
    if config.get('model')!=p['review_model'] or config.get('model_reasoning_effort')!='medium':raise ValueError('native model settings changed')
    path=out/'projects'/spec['sample'];store=Store(path);doc=store.load_document()
    subject='outline' if spec['kind']=='native_outline_review' else None
    stage=out/'calls'/f'{number:02}';stage.mkdir(parents=True,exist_ok=False)
    if subject is None:
        scope=business_outline.scope_for(doc['collaboration']['request']);scope.update(subject='pages',page_ids=[e['page_id'] for e in doc['pages']],layers=['review'])
        receipt=request(path,intent='review_only',scope=scope,operation='full-review-'+spec['sample'],
            text='D04 获批独立完整稿前审：审查当前固定六页正文／案例／逐字讲稿四单位，保留旧请求关闭历史。总上限10次（原失败已用1次）预算中的本次审查；不修稿或启动视觉。')
        save(stage/'request.json',receipt);doc=store.load_document()
    packet=outline_review.packet(store,doc) if subject else content_review.build_review_packet(store,doc)
    save(stage/'packet-before.json',packet)
    reserve(out,p,number,requested_model=p['review_model'],source_refs=[doc['narrative'],doc['content_plan']])
    class AuditedSession(CodexReviewSession):
        def __enter__(self):
            super().__enter__()
            if self.model!=p['review_model']:
                self.__exit__(None,None,None);raise ValueError('native session model differs from frozen budget')
            save(stage/'session.json',{'model':self.model,'thread_id':self.thread_id,'execution_ref':self.execution_ref,'model_called':False})
            return self
        def review(self,prompt,contract):
            (stage/'prompt.txt').write_text(prompt);save(stage/'schema.json',contract)
            save(stage/'turn-start.json',{'prompt_sha256':digest(prompt.encode()),'prompt_bytes':len(prompt.encode()),'model':self.model})
            result=super().review(prompt,contract);save(stage/'observation.json',result);return result
    previous=native_review.CodexReviewSession;native_review.CodexReviewSession=AuditedSession;started=time.monotonic()
    try:
        result=native_review.run(path,subject=subject,selected_resource_ids=p['review_selected_resource_ids'])
        save(stage/'result.json',result)
        print(json.dumps({'event':'review_result','number':number,'status':result['status'],'gate':result.get('preproduction',{}).get('status')}),flush=True)
    except Exception as exc:
        save(stage/'failure.json',{'type':type(exc).__name__,'error_code':getattr(exc,'error_code',None),'message':str(exc)});raise
    finally:
        native_review.CodexReviewSession=previous;save(stage/'process.json',{'elapsed_seconds':time.monotonic()-started})


def runtime_contract_bundle():
    """Retain recursive refs with their canonical filename instead of expanding forever."""
    root=Path(native_review.models.__file__).parent/'resources/contracts'
    pending=['page.v2.schema.json','content-plan-input.v2.schema.json'];bundle={}
    while pending:
        name=pending.pop()
        if name in bundle:continue
        body=json.loads((root/name).read_bytes());bundle[name]=body
        def scan(value):
            if isinstance(value,dict):
                if '$ref' in value:
                    filename=value['$ref'].split('#')[0]
                    if filename and filename not in bundle:pending.append(filename)
                for child in value.values():scan(child)
            elif isinstance(value,list):
                for child in value:scan(child)
        scan(body)
    return bundle


def prepare_generation(out,number):
    p=frozen();spec=specification(p,number);admitted(out,number-1);phase=spec['kind']
    if phase not in ('page_copy','speech'):raise ValueError('not generation')
    path=out/'projects'/spec['sample'];store=Store(path)
    selected=p['generation_selected_resource_ids'][phase]
    continued=service.continue_project(path,selected_resource_ids=selected)
    doc=store.load_document();pending=[t for ref in doc['tasks'] if (t:=store.read_object_json(ref))['status']=='awaiting_host' and t['kind']=='compose']
    if len(pending)!=1 or pending[0]['collaboration_binding']['phase']!=phase:raise ValueError('expected one actual pending content phase')
    task=pending[0];methods=method_resources.read_task_methods(path,task['task_id'])
    actual=[{k:m[k] for k in ('id','relative_path','sha256')} for m in methods['methods']]
    if methods['status']!='current' or actual!=p['method_previews'][phase]:raise ValueError('frozen generation methods changed')
    stage=out/'calls'/f'{number:02}';stage.mkdir(parents=True,exist_ok=False)
    save(stage/'continued.json',continued);save(stage/'task.json',task);save(stage/'methods.json',methods)
    plan=store.read_object_json(doc['content_plan']);narrative=store.read_object_json(doc['narrative'])
    materials=[{**source,'extract_body':store.read_object_json(source['extract'])} for source in doc['sources']]
    original=schema('compose-result.v2.schema.json')
    payload_contract=next(row['then']['properties']['payload'] for row in original['allOf'] if row['if']['properties']['variant'].get('const')==phase)
    bundle=runtime_contract_bundle()
    context={'runtime_contract_bundle':bundle,'actual_task':doc['task'],'current_request':doc['collaboration']['request'],'frozen_task':task,
        'adopted_narrative_ref':doc['narrative'],'adopted_narrative':narrative,'adopted_plan_ref':doc['content_plan'],'adopted_plan':plan,
        'materials':materials,'frozen_methods':[{'id':m['id'],'sha256':m['sha256'],'content':m['content']} for m in methods['methods']],
        'payload_contract':payload_contract}
    page_contract=bundle['page.v2.schema.json']
    if phase=='page_copy':
        context['exact_nested_contracts']={'pages_items':{'$ref':'page.v2.schema.json'},'plan_input':{'$ref':'content-plan-input.v2.schema.json'}}
    else:
        context['exact_nested_contracts']={'updates_items':{'type':'object','additionalProperties':False,'required':['page_id','page_ref','speaker_notes','speech_segments'],'properties':{'page_id':{'type':'string'},'page_ref':schema('collaboration.v1.schema.json','/$defs/ref'),'speaker_notes':{'type':'string'},'speech_segments':page_contract['properties']['content_mapping']['anyOf'][1]['properties']['speech_segments']}}}
    if phase=='speech':context['actual_pages']=[{'page_ref':e['page'],'page':store.read_object_json(e['page'])} for e in doc['pages']]
    preface='外层 compose 合同的 object 字段是开放容器，内部必须使用 runtime_contract_bundle 里完整的最新合同及 exact_nested_contracts。Page schema_version=deck_page_package.v2，正文在customer_visible.title/body_blocks，段落用{id,type:paragraph,text}；不要编造page.v2/title/content/visible_atoms字段。映射在content_mapping，必含narrative_ref、plan_role_page_id、visible_links、speech_segments；visible_links用element_ref=atom:<page_id>:title或atom:<page_id>:block:<block_id>:text。visual_spec必须有intent与reference_mode=new_design，只是意图元数据。来源、节点和真实原文均须遵守合同。'+'只返回一个合法JSON对象 {"payload":本阶段真实完整内容,"author_notes":"简明作者说明"}，不加代码围栏、尾注或对象外文字。不调用工具、不联网、不请求API Key，不创建决定或伪造审查通过。材料全部明确合成。当前正式请求授权完整正文和逐字讲稿，历史brief中仅策划的限制属于已结束旧请求，不重做或改写已经认可的框架与业务事实。'
    if phase=='page_copy':
        preface+='本次只产六个完整Page.v2及完整page_order和plan_input；不生产口播、图像、SVG或PPT。正文必须足以直接阅读，不只给大纲或写作建议。按已采用页职责写具体业务动作、机制、案例和必要边界，商业首提与竞标策略保持原稿。优先最小合法正文结构；每个可见atom都有真实节点和来源映射，表格／列表也须合法且对应全部atom。speaker_notes留空，speech_segments=[]。保持原page_order、page_id、所有既有页职责的narrative_node_ids与required_qualifications；plan_input.speech_policy必须是 {"mode":"verbatim","source":"provided","output":"separate_script"}，这是当前明确请求的后续产物，不能沿用旧策划阶段的none。visual_spec只给合法的文字意图等最小元数据，不制作视觉。author_notes简述取舍，并给出具体演示提纲（场景、能力、说明目的和未确认条件），不要复述全文。'
    else:
        preface+='本次仅为六个实际固定Page Ref写完整可讲的逐字口播，不改正文、页序、主线或视觉。每页至少说明具体动作／机制／衔接，沿已采用内容而非重复标题。不要捏造已演示、已连通或已产生收益。每页以一个连续verbatim段覆盖全部实际speaker_notes（如有未口播指令应明确cue且准确分段）；节点映射须解释本页实际内容。估时标为估计，不说实测；Host只对单个整页verbatim段机械校准其Unicode码点终点，文字、节点、kind与估时不变。payload仅updates；每项含page_id、原page_ref、speaker_notes、speech_segments。author_notes只写讲述取舍、演示条件和估时假设。'
    prompt=preface+'\nJSON上下文与真实合同：\n'+json.dumps(context,ensure_ascii=False)
    (stage/'prompt.txt').write_text(prompt)
    print(json.dumps({'event':'prepared','number':number,'phase':phase,'prompt_bytes':len(prompt.encode()),'model_calls':0}),flush=True)


def generate(out,number):
    p=frozen();spec=specification(p,number);phase=spec['kind'];admitted(out,number-1)
    stage=out/'calls'/f'{number:02}';task=json.loads((stage/'task.json').read_bytes());prompt=(stage/'prompt.txt').read_bytes()
    path=out/'projects'/spec['sample']
    if probe_native_client(check_login=True)['status']!='prerequisites_ready':raise ValueError('ChatGPT subscription login required')
    reserve(out,p,number,requested_model=p['generation_model'],prompt_sha256=digest(prompt),prompt_bytes=len(prompt))
    service.task_start(path,task_id=task['task_id'],execution_ref='codex:D04:'+str(number)+':'+phase,
        supported_protocols=['compose.v2'],capabilities=task['required_capabilities'])
    fresh=stage/'fresh-context';fresh.mkdir();started=time.monotonic()
    cmd=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','-C',str(fresh),'-s','read-only',
         '-m',p['generation_model'],'-c','model_reasoning_effort="high"','--json','--color','never','--output-last-message',str(stage/'response.txt'),'-']
    with (stage/'events.jsonl').open('xb') as stdout,(stage/'stderr.txt').open('xb') as stderr:
        result=subprocess.run(cmd,input=prompt,stdout=stdout,stderr=stderr,timeout=900,check=False,
            env={k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY','CODEX_API_KEY')})
    save(stage/'process.json',{'returncode':result.returncode,'elapsed_seconds':time.monotonic()-started})
    if result.returncode:raise RuntimeError('model failed; preserve evidence; no retry')
    events=[json.loads(line) for line in (stage/'events.jsonl').read_text().splitlines()]
    if sum(e['type']=='turn.completed' for e in events)!=1 or any(e.get('item',{}).get('type') in ('command_execution','mcp_tool_call','web_search') for e in events):raise RuntimeError('unexpected model activity')
    response=json.loads((stage/'response.txt').read_bytes())
    if set(response)!={'payload','author_notes'}:raise ValueError('unexpected response shape')
    payload=copy.deepcopy(response['payload']);normalizations=[]
    if phase=='page_copy':
        if payload.get('plan_input',{}).get('speech_policy')!={'mode':'verbatim','source':'provided','output':'separate_script'}:raise ValueError('explicit requested speech policy missing')
    elif phase=='speech':
        for update in payload.get('updates',[]):
            segments=update.get('speech_segments',[])
            if len(segments)==1 and segments[0].get('kind')=='verbatim' and segments[0].get('start_codepoint')==0:
                actual=len(update['speaker_notes']);prior=segments[0]['end_codepoint']
                if actual!=prior:
                    segments[0]['end_codepoint']=actual;normalizations.append({'page_id':update['page_id'],'field':'single_full_page_segment/end_codepoint','before':prior,'after':actual,'text_or_meaning_changed':False})
    save(stage/'serialization.json',{'normalizations':normalizations,'model_retries':0,'content_text_changed':False})
    envelope={'schema_version':'compose_result.v2','kind':'compose','variant':phase,'task_id':task['task_id'],
        'operation_id':task['operation_id'],'produced_against':task['produced_against'],'eligibility_digest':task['collaboration_binding']['eligibility_digest'],
        'payload':payload,'usage_events':[]}
    save(stage/'envelope.json',envelope)
    accepted=service.accept_result(path,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],result_payload=envelope)
    save(stage/'result.json',accepted);save(stage/'usage.json',next(e for e in events if e['type']=='turn.completed'))
    (stage/'author-notes.md').write_text(response['author_notes'])
    print(json.dumps({'event':'accepted','number':number,'phase':phase,'status':accepted['status'],'offset_normalizations':len(normalizations)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare_projects','review','prepare_generation','generate'])
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--number',type=int,choices=range(2,11));args=parser.parse_args()
    if args.action=='prepare_projects':prepare_projects(args.out.resolve())
    elif args.action=='review':review(args.out.resolve(),args.number)
    elif args.action=='prepare_generation':prepare_generation(args.out.resolve(),args.number)
    else:generate(args.out.resolve(),args.number)
