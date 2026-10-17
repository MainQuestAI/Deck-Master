#!/usr/bin/env python3
"""Finite supplied-P5 fidelity review, using the original protected native bridge.

Root attests actual control and observations. Digests bind bytes, not identities
or professional approval. No Writer, image, caller provider or SDK override.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SCOPED_SHA = 'ce1b5a9f8deba92f7f2d468b2ddd977c9e2de1438d4bc32e2036eeb12da20cc0'
COMMON_SHA = 'd0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261'
FORMAT = 'rc3-supplied-p5-fidelity-admission.v1'
ACTION = 'review_selected_provided_p5_only'
STAGE = 'S08-supplied-P5-fidelity'
RUN = Path('/tmp/rc3-pv2/scoped/08--flow-08--Q4A-primary-p5')
REG_SHA = 'cfa6d6dc896913ed332c2c4c0d422c54f10df16ea46bece05e3797ca270a948d'
RUN_SHA = 'ac7de052dc78a20a594f704c089cf6592f3fd9c9208128c080ae1b348c94535c'
SOURCE_SHA = '3015c68adb049c673dbe3802ac995fb6ffb444fa4fd4d567922de13ff86389f4'
WHEEL_SHA = '5f466b43c11fb34bfe10c093990f54d320921f6cb3eb309d8dbb91bd1ccbe10d'
SOURCE_COMMIT = '3ec9917adcef7ede927338bd6f1ffb8fedf06f92'
REQUEST = 'req-462abb882341'
PROTECTED = ('narrative', 'content_plan', 'pages', 'sources', 'files', 'design_context', 'outputs', 'collaboration', 'content_basis', 'policy')
DISCLOSURE = ('P5/source fidelity only, including sequence within P5; no full Narrative/Plan, '
              'other Page, argument or speech review. N/Plan Refs are opaque binding identities. '
              'Provided manuscript is not a native Writer execution or original_complete. '
              'No image/sample/adoption, cap renewal, whole-deck gate or formal/human credit.')
INSTRUCTION = ('Review only the selected supplied P5 and its complete source, with own full methods. '
               'Return original fidelity page_copy/progression records; progression means sequence within P5 '
               'against its supplied source. Read the bounded view and every listed file. Do not read raw '
               'quarantined SDK workorders, full Narrative/Plan or other Pages. Their Refs bind identity only. '
               'Do not claim argument, speech or whole-deck review. '+DISCLOSURE)


class Error(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Error(reason)


def canonical(value):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts
            and not any('oracle' in p.lower() or p.lower() in {'private', 'authkey'} for p in path.parts),
            'canonical ordinary public path required')
    require(path.resolve(strict=True) == path, 'no path aliases or symlinks')
    return path


def reference(path):
    path = canonical(path); raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_ref(ref):
    raw = canonical(ref['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref['sha256'] and len(raw) == ref['bytes'], 'Ref/parser bytes differ')
    def unique(pairs):
        value = {}
        for k, v in pairs:
            require(k not in value, 'duplicate JSON key'); value[k] = v
        return value
    def nonfinite(value):
        raise Error('nonfinite JSON: '+value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def helpers():
    base = Path(__file__).resolve().parent
    require(reference(base/'supplementary_recorder.py')['sha256'] == SCOPED_SHA
            and reference(base/'controller.py')['sha256'] == COMMON_SHA, 'frozen helper bytes differ')
    spec = importlib.util.spec_from_file_location('rc3_s08_frozen_scoped', base/'supplementary_recorder.py')
    scoped = importlib.util.module_from_spec(spec); spec.loader.exec_module(scoped)
    return scoped, scoped.c


def load(root, engineering):
    require(sys.flags.isolated and sys.dont_write_bytecode and Path(sys.executable).is_absolute(), 'use own absolute Python -I -B')
    require(not Path(root).is_relative_to(Path('/tmp/rc3-pv2')) if engineering else Path(root) == RUN,
            'wrong run/profile')
    root = canonical(root); s, c = helpers()
    run_ref = reference(root/'run.json'); state = read_ref(run_ref)
    campaign = canonical(state['campaign'])
    require(not campaign.is_relative_to(Path('/tmp/rc3-pv2')) if engineering else
            campaign == Path('/workspace/work/rc3/r05/postfix-v2-scoped-ledger'), 'wrong campaign')
    reg = reference(campaign/'registration.json'); config = read_ref(reg)
    require(config.get('format') == s.FORMAT and config.get('status') == (s.ENGINEERING if engineering else 'ADMITTED')
            and config.get('recorder_sha256') == SCOPED_SHA and config['common']['sha256'] == COMMON_SHA,
            'original scoped registration/helper required')
    require(state['root'] == str(root) and state['registration_sha256'] == reg['sha256']
            == c.digest(c.encoded(config)) and config['ledger_root'] == str(campaign), 'run/registration drift')
    require(all(state.get(k) == v for k, v in config['scopes'][state['slot']].items()), 'scope row differs')
    require(state['arm'] == 'B' and state['profile'] == 'q3q4' and state['case'] == 'Q4'
            and state['checkpoint'] == 'Q4A' and state['checkpoint_ref'] is None and state['page_ids'] == ['p5']
            and state['repetition'] == 1 and state['native_limits']['feedback'] == state['budget']['feedback'] == 1,
            'only original B supplied P5/null feedback scope')
    require(c.read(campaign/'runs'/(state['slot']+'.json')) == {'root':str(root),'project':state['project']}
            and c.read(campaign/'ledger-origin.json') == {'root':str(campaign),'registration_sha256':reg['sha256']},
            'original slot/resource ledger required')
    if not engineering:
        require(reg['sha256'] == REG_SHA and run_ref['sha256'] == RUN_SHA, 'captured formal run changed')
        require(config['installations']['B']['source_sha'] == SOURCE_COMMIT
                and config['installations']['B']['wheel_sha256'] == WHEEL_SHA, 'only original own B3ec installation')
    else:
        require(not canonical(state['project']).is_relative_to(Path('/tmp/rc3-pv2')), 'engineering cannot open formal project')
    # This is only the explicitly public Host role-exclusion policy. Nested
    # refs, private input indexes and all other registration refs stay opaque.
    exposure = config['exposure_registry']; policy = read_ref(exposure)
    require(policy.get('status') == 'FROZEN' and policy.get('excluded_identities'), 'original public exclusion policy')
    c.installation(config, 'B')
    journal = c.Journal(root)
    require(journal.events()[0]['kind'] == 'scoped_initialized' and journal.events()[0]['data'] == state, 'initialized run differs')
    return s, c, journal, state, config, reg, run_ref


def manuscript(c, state):
    store = c.store_for(state); doc = store.load_document()
    region = doc.get('collaboration') or {}; req = region.get('request') or {}; scope = req.get('scope') or {}
    require(req.get('intent') == 'design_trial' and req.get('content_intent') is None
            and req.get('closed') is False and not req.get('paused') and scope.get('subject') == 'pages'
            and req.get('variant') is None and scope.get('page_ids') == ['p5'] and scope.get('page_manifest_ref') is None
            and scope.get('external_artifact_ref') is None
            and not scope.get('allow_page_membership_change') and not scope.get('allow_page_order_change')
            and 'review' in scope.get('layers', []), 'current P5/null design_trial Request required')
    require((region.get('quality_profile') or {}).get('content_review_requirement') == 'fidelity_only'
            and (region.get('quality_profile') or {}).get('requirement_origin') == 'confirmed_manuscript',
            'provided confirmed-manuscript fidelity posture required')
    require(len(state['materials']) == 1, 'exact one supplied P5/source')
    material = reference(state['materials'][0]['path']); require(material == state['materials'][0], 'supplied bytes changed')
    supplied = read_ref(material)
    entry = next(p for p in doc['pages'] if p['page_id'] == 'p5'); page = store.read_object_json(entry['page'])
    require(supplied.get('schema_version') == 'deck_page_package.v2' and supplied.get('page_id') == 'p5'
            and all(page.get(k) == v for k, v in supplied.items()), 'current selected Page is not exact supplied manuscript')
    require(len(doc.get('sources', [])) == 1 and doc['sources'][0]['original_sha256'] == material['sha256'],
            'unselected/whole-deck source cannot enter bounded review')
    from deck_master import content_review
    require(content_review.requirement_state(store, doc)['effective'] == 'fidelity_only', 'real SDK mapping must support fidelity')
    subjects = [entry['page']] + [doc[k] for k in ('narrative','content_plan') if doc.get(k)]
    authors = sorted(content_review.author_execution_refs(store, doc, subjects))
    return store, doc, entry, material, authors


def context(root, engineering):
    s,c,journal,state,config,reg,run_ref = load(root, engineering)
    store,doc,entry,material,authors = manuscript(c,state)
    events = journal.events()
    require(not journal.unfinished(), 'prior SDK intent unresolved; no retry')
    require(any(e['kind'] == 'instruction_occurrence' for e in events), 'original instruction occurrence required')
    if not engineering:
        require((doc['collaboration']['request']['request_id'], material['sha256']) == (REQUEST,SOURCE_SHA), 'captured Request/source differs')
    install=config['installations']['B']
    scope={'tool':reference(Path(__file__).resolve()),'scoped':reference(Path(__file__).with_name('supplementary_recorder.py')),
           'common':reference(Path(__file__).with_name('controller.py')),'run':run_ref,'registration':reg,
           'installation':{k:install[k] for k in ('python','module_file','source_sha','source_tree','wheel_sha256','manifest')},
           'package_inventory_sha256':c.digest(c.encoded(install['package_files'])),
           'exposure_policy':config['exposure_registry'],'project':state['project'],'project_id':doc['project_id'],
           'revision':doc['revision_id'],'request':doc['collaboration']['request'],
           'selected_page':entry['page'],'source':material,'source_provenance':doc['sources'],
           'imported_author_execution_refs':authors,'checkpoint':None,'page_ids':['p5'],
           'prior_errors':[reference(journal.root/f"journal/{e['sequence']:06d}.json") for e in events if e['kind']=='sdk_error'],
           'frontier':reference(journal.root/f"journal/{events[-1]['sequence']:06d}.json"),
           'original_limits':state['limits'],'original_role_caps':state['native_limits'],
           'resource_frontier':None,'disclosure':DISCLOSURE}
    resources=s.Resources(state); charges=resources.journal.events()
    if charges:scope['resource_frontier']=reference(resources.journal.root/f"journal/{charges[-1]['sequence']:06d}.json")
    return s,c,journal,state,config,store,doc,scope


@contextmanager
def session(root, admission, sha, engineering):
    s,c,journal,state,config,*_ = load(root,engineering)
    a_ref=reference(admission);require(a_ref['sha256']==sha,'exact admission hash required');a=read_ref(a_ref)
    require(set(a)=={'format','action','status','observer_id','assurance','evidence_kind','observed_at_utc',
                    'scope','independent_implementation_review_passed','actual_supplied_checkpoint_observed'}, 'finite admission fields only')
    require(a['format']==FORMAT and a['action']==ACTION and a['status']==config['status']
            and a['observer_id']==('/engineering/rc3-s08' if engineering else '/root')
            and a['assurance']==('synthetic_engineering' if engineering else 'host_attested')
            and a['evidence_kind']==('SYNTHETIC_ENGINEERING_ONLY' if engineering else 'ROOT_ACTUAL_PROSPECTIVE_SUPPLIED_P5_CONTROL')
            and a['independent_implementation_review_passed'] is True and a['actual_supplied_checkpoint_observed'] is True,
            'prospective reviewed Root supplied-input admission required')
    c.fresh(a['observed_at_utc'])
    installation=config['installations']['B']
    unchanged={'tool':reference(Path(__file__).resolve()),
        'scoped':reference(Path(__file__).with_name('supplementary_recorder.py')),
        'common':reference(Path(__file__).with_name('controller.py')),
        'run':reference(journal.root/'run.json'),
        'registration':reference(Path(state['campaign'])/'registration.json'),
        'installation':{k:installation[k] for k in ('python','module_file','source_sha','source_tree','wheel_sha256','manifest')},
        'package_inventory_sha256':c.digest(c.encoded(installation['package_files'])),
        'exposure_policy':config['exposure_registry']}
    require(all(a['scope'].get(k)==v for k,v in unchanged.items()),'reviewed tool/dependency/installation bytes changed')
    with journal.locked(),s.Resources(state).locked() as resources:
        _,_,_,current,current_config,*_=load(root,engineering)
        require(current==state and current_config==config and reference(admission)==a_ref, 'admission scope drift')
        require(not journal.unfinished() and not resources.totals()[2], 'prior SDK/render outcome unknown; never retry')
        s.budget_clean(journal,state)
        yield s,c,s.MeteredJournal(journal,state,resources),state,config,a,a_ref


def protected(doc):return {k:deepcopy(doc.get(k)) for k in PROTECTED}


def checkpoint(journal,c,state,a,a_ref):
    path=journal.root/'supplied-manuscript-input.json'
    checkpoints=[e['data']['checkpoint'] for e in journal.events() if e['kind']=='provided_manuscript_input']
    require(len(checkpoints)==1 and reference(path)==checkpoints[0],'immutable provided checkpoint changed')
    record=read_ref(checkpoints[0])
    require(record['admission']==a_ref and record['scope']==a['scope'], 'checkpoint/admission mismatch')
    store,doc,*_=manuscript(c,state)
    require(protected(doc)==record['protected_document'], 'content/Request/source changed after provided checkpoint')
    return store,doc,record


def packet(s,c,journal,state,task,methods,directory,record):
    """New finite review protocol; never relabel a preproduction Task page_visual."""
    directory=Path(directory);store=c.store_for(state);doc=store.load_document();work=methods['work_order']
    raw=c.save(directory/'quarantine/sdk-method-response.json',methods)
    c.save(directory/'quarantine/actual-task.json',task)
    require(task['kind']=='review' and task['review_stage']=='preproduction' and task['scope_pages']==['p5']
            and work['scope_pages']==['p5'] and set(work)<=s.BOUND_CLASSIFIED,
            'exact P5 preproduction workorder; unclassified/wider fields refuse')
    require(methods['status']=='current' and methods['current_method_release']==task['method_release'], 'own full current methods required')
    entry=next(p for p in doc['pages'] if p['page_id']=='p5');page=store.read_object_json(entry['page'])
    closure=s.Closure(state['project'],page,directory/'author-packet',bounded=True)
    method_rows=[]
    module=Path(sys.modules['deck_master'].__file__).resolve().parent
    method_root=module/'resources/skill' if module.parent.name!='src' else module.parent.parent/'skills/deck-master'
    for item in methods['methods']:
        path=canonical(item['path']);body=item['content'].encode()
        require(path.is_relative_to(method_root) and path.read_bytes()==body and c.digest(body)==item['sha256'], 'method must be complete own installed bytes')
        copied=c.write_once(directory/'author-packet/methods'/(c.safe_name(item['id'])+'.md'),body)
        method_rows.append({'id':item['id'],'own_installed_path':str(path),'sha256':item['sha256'],'bytes':len(body),'read_file':copied})
    view={k:deepcopy(v) for k,v in work.items() if k in s.VIEW_FIELDS}
    view.update(format='rc3-supplied-p5-review-view.v1',raw_response_ref=raw,raw_response_read_permission=False,
                scope_disclosure=DISCLOSURE,methods=method_rows,imported_author_execution_refs=record['scope']['imported_author_execution_refs'])
    # Review packet's full N/Plan and raw instructions stay quarantined. Their
    # identity is retained for protected receipt binding, never as a read grant.
    full=[]
    for r in work['inputs']:
        obj=store.read_object_json(r)
        if obj.get('schema_version')=='content_review_packet.v1':full.append(r)
        elif r in (doc.get('narrative'),doc.get('content_plan')):closure.identity(r,'/opaque/semantic_identity')
        elif r==entry['page']:closure.visit(r,'/selected_page')
        else:raise Error('unclassified review input; no full-deck expansion')
    require(len(full)==1, 'one original protected review packet identity required')
    original=store.read_object_json(full[0])
    require(original['manuscript']['page_order']==['p5'] and original['required_units']==['page_copy','progression']
            and original['requirement']=='fidelity_only', 'SDK review must be local fidelity, never argument/speech')
    view['opaque_review_packet_identity']=full[0]
    view['opaque_semantic_identities']={k:doc.get(k) for k in ('narrative','content_plan')}
    view['selected_page']=entry['page'];closure.visit(entry['page'],'/selected_page')
    require(len(work['source_reading'])==1, 'only selected complete P5 source')
    reading=work['source_reading'][0]
    require(reading['status']=='read' and reading['format_kind']=='json'
            and json.loads(reading['text'])==read_ref(record['scope']['source'])
            and reading['original_sha256']==record['scope']['source']['sha256']
            and reading['original_file']['sha256']==record['scope']['source']['sha256']
            and not reading.get('image_pages'), 'full supplied P5 source required')
    for key in ('original_file',):
        r=reading[key];body=closure.add(r['path'],r['sha256'],'/source_reading/'+key)
        require(json.loads(body)==read_ref(record['scope']['source']), 'source original differs from full P5')
        require(closure.path(reading['original_path'])==closure.path(r['path']), 'source original path differs')
    extract=closure.path(reading['extract_path']);extract_raw=extract.read_bytes();extract_value=json.loads(extract_raw)
    require(all(extract_value.get(k)==reading.get(k) for k in ('text','locators','tables')), 'source extract/expanded fields differ')
    closure.add(str(extract),c.digest(extract_raw),'/source_reading/extract_path')
    view['source_reading']=work['source_reading']
    require(reference(state['instruction']['path'])==state['instruction'],'original Host instruction changed')
    instruction=c.write_once(directory/'author-packet/actual-instruction.txt',Path(state['instruction']['path']).read_bytes())
    technical=[c.write_once(directory/'author-packet/fidelity-scope.txt',INSTRUCTION.encode())]
    for r in [state['grammar']]+state.get('technical_supplements',[]):
        require(reference(r['path'])==r,'technical bytes changed')
        technical.append(c.write_once(directory/'author-packet/technical'/(r['sha256']+Path(r['path']).suffix),Path(r['path']).read_bytes()))
    for path in sorted((module/'resources/contracts').glob('*.schema.json')):
        technical.append(c.write_once(directory/'author-packet/schemas'/path.name,path.read_bytes()))
    manifest=c.save(directory/'read-closure-manifest.json',{'format':'rc3-required-read-closure.v1','bounded':True,
        'target_page_ids':['p5'],'required_read':closure.items,'methods':method_rows,'opaque_binding_only':closure.opaque,
        'instruction_read_file':instruction,'technical_read_files':technical,'original_raw_ref':raw,
        'raw_preserved':True,'full_narrative_plan_or_other_pages_read_permission':False,'scope_disclosure':DISCLOSURE})
    view.update(instruction_read_file=instruction,technical_read_files=technical,
                read_closure_manifest_ref=manifest,required_read_files=[r['author_copy'] for r in closure.items])
    view_ref=c.save(directory/'author-packet/workorder-view.json',view)
    return {'original_raw_ref':raw,'author_view_ref':view_ref,'read_closure_manifest_ref':manifest,
            'method_release':methods['current_method_release'],'raw_workorder_preserved':True}


def prepare(root,admission,sha,bootstrap,engineering=False):
    with session(root,admission,sha,engineering) as (s,c,j,state,config,a,a_ref):
        *_,doc,scope=context(root,engineering)
        require(scope==a['scope'],'initial revision/frontier/source/cost/admission differs')
        require(not any(e['kind'] in {'native_begun','feedback_delivered','repair_begun','review_dispatch'} for e in j.events()), 'earlier author/review/feedback work exists')
        require(not any(e['kind']=='content_feedback' and e['data']['case']==s.case_key(state)
                        for e in j.resources.journal.events()),'original case feedback already consumed in shared ledger')
        record={'format':'provided_manuscript_input.v1','admission':a_ref,'scope':scope,'protected_document':protected(doc),
                'native_writer_execution':False,'human_approval_asserted':False,'scope_disclosure':DISCLOSURE}
        c.save(j.root/'supplied-manuscript-input.json',record)
        j.append('provided_manuscript_input',{'checkpoint':reference(j.root/'supplied-manuscript-input.json'),'native_original_complete':False})
        from deck_master import content_review
        bootstrap_ref=reference(bootstrap)
        with c.native_runtime(bootstrap) as registry:
            outcome=s.perform(j,'content_review.dispatch_preproduction_review',{'project':state['project'],'page_ids':['p5'],'bootstrap':bootstrap_ref,'instruction':INSTRUCTION},
                lambda:content_review.dispatch_preproduction_review(state['project'],page_ids=['p5'],adapter_context=registry.channel_context(),instruction=INSTRUCTION))
        j.append('review_dispatch',{'role':'feedback','actual_result':outcome,'scope_disclosure':DISCLOSURE})
        if outcome['status']!='review_dispatched':return outcome
        task=outcome['task'];require(task['dispatch_revision']==scope['revision'],'SDK dispatch raced initial revision; actual outcome retained')
        methods=s.read_methods(j,state,task)
        result=packet(s,c,j,state,task,methods,j.root/'stages'/STAGE/'preflight',record)
        dispatch={'stage':STAGE,'role':'feedback','task_id':task['task_id'],'project_id':scope['project_id'],
                  'method_release':methods['current_method_release'],'packet_profile':'q4-p5-supplied-fidelity',
                  'prepared_at':c.now(),'status':'quarantined_not_released',**result}
        c.save(j.root/'stages'/STAGE/'dispatch.json',dispatch);j.append('stage_prepared',dispatch)
        return dispatch


def audit(s,c,j,state,config,observation,ordinal=None):
    target,dispatch=c.stage_info(j,STAGE)
    result=dispatch if ordinal is None else c.read(c.execution(j,STAGE,ordinal)[1]/'post-claim-packet.json')
    obs_ref=reference(observation);obs=read_ref(obs_ref);c.fresh(obs['observed_at_utc'])
    excluded=set(read_ref(config['exposure_registry'])['excluded_identities'])
    executors={e['data']['executor'] for e in j.events() if e['kind']=='native_begun'}
    require(obs.get('assurance')=='host_attested' and obs.get('observer_id','').startswith('/root/')
            and obs['observer_id'] not in excluded|executors and obs.get('status')=='PASS'
            and obs.get('project')==state['project'] and obs.get('task_id')==dispatch['task_id']
            and obs.get('required_read_closure_checked') is True and obs.get('raw_workorder_preserved') is True,
            'actual independent Host mechanical audit required, not a model invocation')
    for k in ('original_raw_ref','author_view_ref','read_closure_manifest_ref'):
        require(reference(result[k]['path'])==result[k] and obs.get(k)==result[k], 'audit packet bytes differ')
    manifest=read_ref(result['read_closure_manifest_ref'])
    for row in manifest['required_read']:
        require(reference(row['source_path'])['sha256']==row['sha256'] and reference(row['author_copy']['path'])==row['author_copy'], 'read closure drift')
    for row in manifest['methods']:
        require(reference(row['read_file']['path'])==row['read_file'] and reference(row['own_installed_path'])['sha256']==row['sha256'], 'own method drift')
    for r in [manifest['instruction_read_file']]+manifest['technical_read_files']:require(reference(r['path'])==r,'instruction/technical drift')
    directory=target/'preflight' if ordinal is None else c.execution(j,STAGE,ordinal)[1]
    saved=c.save(directory/'independent-packet-audit.json',{'independent_observation':obs_ref,**result})
    j.append('packet_audited',{'stage':STAGE,'ordinal':ordinal,'audit':saved})
    return saved


def advance(action,root,admission,sha,*,engineering=False,observation=None,result=None,result_sha256=None,observation_sha256=None,bootstrap=None):
    require(action in {'audit','begin','claim','release','observe','accept','feedback'}, 'finite review lifecycle action only')
    with session(root,admission,sha,engineering) as (s,c,j,state,config,a,a_ref):
        for value in (observation,result,bootstrap):
            if value is not None:reference(value)
        store,doc,record=checkpoint(j,c,state,a,a_ref);target,dispatch=c.stage_info(j,STAGE)
        prepared=[e['data'] for e in j.events() if e['kind']=='stage_prepared' and e['data']['stage']==STAGE]
        require(prepared==[dispatch],'immutable prepared Task/packet binding changed')
        task=c.task_for(store,dispatch['task_id'])
        if action=='feedback':
            require(task['kind']=='review' and task['review_stage']=='preproduction' and task['scope_pages']==['p5']
                    and task['status']=='completed','only actual accepted local review can be delivered')
        else:s.role_task(j,state,task,'feedback')
        existing=[e['data'] for e in j.events() if e['kind']=='native_begun' and e['data']['stage']==STAGE]
        if action=='audit':
            require(not existing,'preflight only before invocation');return audit(s,c,j,state,config,observation)
        if action=='begin':
            audits=[e['data']['audit'] for e in j.events() if e['kind']=='packet_audited' and e['data']['ordinal'] is None]
            require(not existing and len(audits)==1,'one audited invocation only');read_ref(audits[0])
            observed_ref=reference(observation);actual=read_ref(observed_ref)
            begun=c.begin_native(j,state,config,STAGE,observation)
            frozen=reference(target/'executions'/f"{begun['ordinal']:04d}"/'root-invocation.json')
            require(begun['observation']==observed_ref and begun['executor']==actual['spawn']['canonical_task_name']
                    and (frozen['bytes'],frozen['sha256'])==(observed_ref['bytes'],observed_ref['sha256']),
                    'native invocation parser/copy consumed different Root bytes; cost retained unknown')
            return begun
        require(len(existing)==1,'one actual native reviewer invocation required');inv=existing[0];ordinal=inv['ordinal']
        _,execution=c.execution(j,STAGE,ordinal)
        if action=='claim':
            require(not (execution/'claim.json').exists(),'claim is write-once, no SDK replay')
            from deck_master import service
            args={'task_id':task['task_id'],'execution_ref':inv['executor'],
                  'supported_protocols':[task['protocol_version']] if task.get('protocol_version') else None,
                  'capabilities':task.get('required_capabilities')}
            claim=s.perform(j,'service.task_start',args,lambda:service.task_start(state['project'],**args));c.save(execution/'claim.json',claim)
            task=c.task_for(store,task['task_id']);methods=s.read_methods(j,state,task)
            require(methods['current_method_release']==dispatch['method_release'],'claim method drift')
            bound=packet(s,c,j,state,task,methods,execution/'post-claim',record);c.save(execution/'post-claim-packet.json',bound)
            saved=c.save(execution/'method-read-record.json',{'format':'rc3-scoped-author-read.v1',**bound,
                'methods':[{k:v for k,v in item.items() if k!='content'} for item in methods['methods']],
                'consumption':'quarantined_until_independent_post_claim_audit','raw_workorder_read_by_author':False})
            j.append('method_bytes_returned',{'ordinal':ordinal,'executor':inv['executor'],'record':saved});return bound
        if action=='release':
            audited=audit(s,c,j,state,config,observation,ordinal)
            bound=c.read(execution/'post-claim-packet.json');data={'ordinal':ordinal,'stage':STAGE,'packet_audit_ref':audited,**bound}
            c.save(execution/'released-packet.json',data);j.append('safe_packet_released',data);return data
        if action=='observe':
            outcome=c.observe(j,state,STAGE,ordinal,result,result_sha256,observation,observation_sha256)
            release=c.read(execution/'released-packet.json')
            frozen=reference(execution/'raw-native-output');observed_ref=reference(execution/'raw-root-completion.json')
            obs=read_ref(observed_ref);completed=obs['completion'];c.fresh(obs['observed_at_utc'])
            require(frozen['sha256']==result_sha256 and observed_ref['sha256']==observation_sha256
                    and obs.get('observation_kind')==c.OBSERVER_KIND and obs.get('assurance')=='host_attested'
                    and obs.get('task_id')==dispatch['task_id'] and obs.get('project_id')==dispatch['project_id']
                    and obs.get('model_output_bytes_sha256')==frozen['sha256'] and obs.get('all_method_bytes_read') is True
                    and obs.get('method_release')==dispatch['method_release']
                    and obs.get('method_read_record_sha256')==reference(execution/'method-read-record.json')['sha256']
                    and completed.get('sender')==inv['executor'] and completed.get('message_type')=='FINAL_ANSWER'
                    and completed.get('status_observation_tool')=='collaboration.list_agents'
                    and completed.get('observed_status')=='completed'
                    and inv['executor'] in completed.get('observed_completed_agents',[])
                    and not obs.get('native_object_files'), 'same actual frozen Root native completion bytes required')
            require(obs.get('author_view_sha256')==release['author_view_ref']['sha256']
                    and obs.get('read_closure_manifest_sha256')==release['read_closure_manifest_ref']['sha256']
                    and obs.get('all_required_view_files_read') is True and obs.get('raw_workorder_read_by_author') is False
                    and obs.get('full_narrative_plan_or_other_pages_read') is False
                    and obs.get('review_scope_page_ids')==['p5']
                    and completed['raw_final_message'].encode()==Path(frozen['path']).read_bytes(), 'actual bounded P5/source consumption required; no whole-deck read claim')
            j.append('scoped_native_observed',{'stage':STAGE,'ordinal':ordinal,'author_view':release['author_view_ref']});return outcome
        if action=='feedback':
            c.observed_result_for_feedback(j,STAGE,ordinal);j.resources.once('content_feedback','one',{'stage':STAGE,'ordinal':ordinal})
            return c.deliver_feedback(j,STAGE,ordinal)
        require(any(e['kind']=='scoped_native_observed' and e['data']['ordinal']==ordinal for e in j.events()), 'bounded native observation required')
        _,_,envelope,_=c.observed_result(j,STAGE,ordinal)
        s.forbid_context(envelope)
        require(envelope.get('kind')=='review' and not any(envelope.get(k) for k in ('pages','page_order','artifact_specs','usage_events'))
                and {r['kind'] for r in envelope['reviews']}=={'page_copy','progression'},
                'fidelity review records only, no Page/order/artifact/image/argument/speech output')
        allowed=[doc[k] for k in ('narrative','content_plan') if doc.get(k)]+[record['scope']['selected_page']]
        dependencies={('content','page:p5'):record['scope']['selected_page']['sha256']}
        dependencies.update({('content',k):doc[k]['sha256'] for k in ('narrative','content_plan') if doc.get(k)})
        dependencies.update({('source',r['source_id']):r['extract']['sha256'] for r in doc['sources'] if r.get('extract')})
        for review in envelope['reviews']:
            require(review.get('review_stage')=='preproduction' and review.get('reviewer',{}).get('type')=='independent_host'
                    and review['reviewer'].get('execution_ref')==inv['executor']
                    and review['reviewer'].get('independence_confirmed') is True
                    and all(r in allowed for r in review['subjects'])
                    and all(dependencies.get((d['kind'],d['identity']))==d.get('sha256') for d in review['dependencies'])
                    and all(f.get('page_id')=='p5' for f in review.get('findings',[])), 'unread whole/other Page evidence cannot be claimed')
        before=protected(doc);outcome=c.review_accept(j,state,STAGE,ordinal,bootstrap)
        require(protected(store.load_document())==before,'read-only review changed protected content/Request')
        return outcome


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','audit','begin','claim','release','observe','accept','feedback'])
    for name in ('run','admission','admission-sha256'):parser.add_argument('--'+name,required=True)
    for name in ('bootstrap','observation','result','result-sha256','observation-sha256'):parser.add_argument('--'+name)
    parser.add_argument('--engineering-only',action='store_true');a=parser.parse_args()
    try:
        if a.action=='prepare':out=prepare(a.run,a.admission,a.admission_sha256,a.bootstrap,a.engineering_only)
        else:out=advance(a.action,a.run,a.admission,a.admission_sha256,engineering=a.engineering_only,
            bootstrap=a.bootstrap,observation=a.observation,result=a.result,result_sha256=a.result_sha256,observation_sha256=a.observation_sha256)
    except Exception as exc:
        print(json.dumps({'status':'refused_or_unknown','error_type':type(exc).__name__,'error':str(exc),'automatic_retry':False}));return 2
    print(json.dumps(out,ensure_ascii=False,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
