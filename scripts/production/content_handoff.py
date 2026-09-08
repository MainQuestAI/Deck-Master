"""Agent-authored page content handoff before native image/SVG production.

Content approval permits building a draft. It is never final delivery approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shlex
import tempfile

from workflow.actions import (create_action_envelope, stage_action_result, commit_action_result,
    read_current_revision, revision_read, revision_input_path, fingerprint_payload)
from production.page_builder import write_page_packages

TASK_REF = 'production/page_content_task.json'
INPUTS = ('request.json', 'deck_brief.json', 'context_manifest.json', 'claim_map.json',
          'narrative_plan.json', 'sourcing_plan.json', 'solution_model.json')


def _read(root, name, default=None):
    path = revision_input_path(root, root / name)
    return json.loads(path.read_text()) if path.is_file() else default


def _inputs(root):
    refs = []
    for name in INPUTS:
        path = revision_input_path(root, root / name)
        if path.is_file():
            refs.append({'ref': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'input_refs': refs, 'input_fingerprint': fingerprint_payload(refs)}


def _commit(root, parent, files, task_id):
    fp = fingerprint_payload(parent)
    action_id = 'content_' + fingerprint_payload({'parent':parent,'files':files})[:32]
    envelope = create_action_envelope(action_id=action_id, task_id=task_id, scope_pages=['content'], permission='runtime', input_fingerprint=fp)
    stage_action_result(root,envelope,files)
    return commit_action_result(root,envelope,current_input_fingerprint=lambda:fingerprint_payload(read_current_revision(root).get('revision_id','')),expected_revision=parent,targets={name:root/name for name in files})


def prepare_content(run_dir):
    root = Path(run_dir).resolve()
    from build.run_policy import enforce_origin_mode
    enforce_origin_mode(root, json.loads((root / 'request.json').read_text()))
    with revision_read(root, fresh=True) as parent:
        narrative = _read(root,'narrative_plan.json',{})
        beats = narrative.get('beats',[])
        ids = [str(beat.get('page_id') or beat.get('beat_id') or '') for beat in beats]
        if not ids or not all(ids) or len(ids)!=len(set(ids)):
            raise ValueError('content handoff requires a nonempty narrative with unique page identities')
        based_on = _inputs(root)
        prior = _read(root,TASK_REF,{})
        if prior.get('status') == 'content_ready' and prior.get('completed_based_on') == based_on:
            return prior
        if prior.get('based_on') == based_on and prior.get('status') == 'awaiting_agent_content':
            return prior
        task = {'schema_version':'deck_page_content_task.v1','run_id':_read(root,'request.json',{}).get('run_id',root.name),
                'task_id':'content_'+based_on['input_fingerprint'][:24],'status':'awaiting_agent_content',
                'based_on':based_on,'page_ids':ids,'pages':beats,
                'output_contract':{'schema_version':'deck_page_content_result.v1','required':['run_id','task_id','source_fingerprint','pages','content_review'],
                    'page_fields':['page_id','page_title','conclusion','business_implication','source_refs','evidence_bindings','fact_kind'],
                    'content_review':{'status':'approved_for_build','reviewer':'actual host reviewer identity','basis':'actual content review rationale'},
                    'boundary':'Write finished customer-visible copy and source bindings. Do not submit layout instructions or claim final delivery approval.'},
                'submit_command':f'deck-master page-content submit --run-dir {shlex.quote(str(root))} --input <host-content.json>'}
        _commit(root,parent,{TASK_REF:json.dumps(task,ensure_ascii=False,indent=2)},task['task_id'])
        return task


def content_status(run_dir):
    root=Path(run_dir).resolve()
    with revision_read(root, fresh=True):
        task=_read(root,TASK_REF)
        if not task:
            raise ValueError('page content task missing; run page-content prepare')
        return task


def content_continuation(run_dir):
    root=Path(run_dir).resolve()
    with revision_read(root, fresh=True):
        task=_read(root,TASK_REF,{})
        if task.get('status')!='awaiting_agent_content':
            return None
        stale = task.get('based_on') != _inputs(root)
        command=(f'deck-master page-content prepare --run-dir {shlex.quote(str(root))}' if stale else task['submit_command'])
        return {'stage':'awaiting_agent_execution','reason':'page content inputs changed; refresh task' if stale else 'host must author and review finished page content before native rendering',
                'next_command':command,'host_task':{'kind':'page_content','task':task},'build_status':{}}


def submit_content(run_dir, result):
    root=Path(run_dir).resolve()
    if not isinstance(result,dict) or result.get('schema_version')!='deck_page_content_result.v1':
        raise ValueError('expected deck_page_content_result.v1')
    from build.run_policy import enforce_origin_mode
    enforce_origin_mode(root, json.loads((root / 'request.json').read_text()))
    with revision_read(root,fresh=True) as parent:
        task=_read(root,TASK_REF,{})
        digest=fingerprint_payload(result)
        if task.get('status')=='content_ready' and task.get('result_sha256')==digest:
            return {'status':'already_applied','page_count':len(task['page_ids'])}
        if task.get('status')!='awaiting_agent_content' or result.get('task_id')!=task.get('task_id') or result.get('run_id')!=task.get('run_id'):
            raise ValueError('content result does not match the issued task')
        if result.get('source_fingerprint')!=task['based_on']['input_fingerprint'] or _inputs(root)!=task['based_on']:
            raise ValueError('content result inputs are stale; prepare a fresh task')
        pages=result.get('pages')
        if not isinstance(pages,list) or any(not isinstance(p,dict) for p in pages) or [p.get('page_id') for p in pages]!=task['page_ids']:
            raise ValueError('content result must preserve the exact complete page order')
        review=result.get('content_review') or {}
        if not isinstance(review,dict) or review.get('status')!='approved_for_build' or not str(review.get('reviewer') or '').strip() or not str(review.get('basis') or '').strip():
            raise ValueError('content result requires explicit host content review for building, not delivery approval')
        context=_read(root,'context_manifest.json',{})
        from quality.source_binding import source_quote_matches, evidence_index
        source_map={str(s.get('source_id')):s for s in context.get('sources',[]) if isinstance(s,dict)}
        quotes=result.get('evidence_quotes',[])
        if not isinstance(quotes,list):
            raise ValueError('evidence_quotes must be a list')
        for quote in quotes:
            if not isinstance(quote,dict) or str(quote.get('source_id')) not in source_map:
                raise ValueError('quote must identify an existing Context source')
            source=source_map[str(quote['source_id'])]
            if not source_quote_matches(source,quote,run_dir=root):
                raise ValueError('quote must exactly match original source bytes and position')
            if not str(quote.get('evidence_id') or '').strip() or '::' in quote['evidence_id']:
                raise ValueError('quote evidence_id must be a nonempty local identity')
            evidence={key:copy.deepcopy(value) for key,value in quote.items() if key!='source_id'}
            existing=source.setdefault('evidence_candidates',[])
            same=[item for item in existing if item.get('evidence_id')==evidence['evidence_id']]
            if same and same != [evidence]:
                raise ValueError('quote identity conflicts with an existing Context evidence')
            if not same:
                existing.append(evidence)
        sources={str(s.get('source_id')) for s in context.get('sources',[]) if isinstance(s,dict)}
        narrative=copy.deepcopy(_read(root,'narrative_plan.json'))
        for beat,page in zip(narrative['beats'],pages):
            if any(not isinstance(page.get(key),str) or not page[key].strip() for key in ('page_title','conclusion','business_implication')):
                raise ValueError('each page requires finished title, conclusion and business implication')
            if page.get('fact_kind') not in {'customer_fact','design_suggestion','analysis_judgment','working_assumption'}:
                raise ValueError('page fact_kind must distinguish supplied facts from proposals')
            from production.page_builder import assert_no_production_instructions
            for key in ('page_title', 'conclusion', 'business_implication'):
                assert_no_production_instructions(page[key], page_id=page['page_id'])
            refs=page.get('source_refs',page.get('evidence_refs'))
            if not isinstance(refs,list) or not refs or any(not isinstance(ref,str) or ref not in sources for ref in refs):
                raise ValueError('each page must bind actual Context source ids')
            # Only authored visible content crosses this boundary; identities,
            # order, role and model references remain owned by the narrative.
            beat.update({key:copy.deepcopy(page[key]) for key in ('page_title','conclusion','business_implication','fact_kind')})
            beat['source_refs']=refs
            beat['evidence_bindings']=copy.deepcopy(page.get('evidence_bindings') or [])
            for binding in beat['evidence_bindings']:
                matches=evidence_index(context).get(str(binding),[])
                if '::' not in str(binding) or len(matches)!=1 or not source_quote_matches(*matches[0],run_dir=root):
                    raise ValueError('every evidence binding requires a source-qualified, verified original quote')
            if page['fact_kind']=='customer_fact' and not beat['evidence_bindings']:
                raise ValueError('customer facts require verified quote evidence bindings, not source ids')
            beat['page_id']=page['page_id']
        with tempfile.TemporaryDirectory(prefix='deck-page-content-') as temp:
            candidate=Path(temp)
            report=write_page_packages(candidate,narrative_plan=narrative,context_manifest=context,solution_model=_read(root,'solution_model.json',{}),sourcing_plan=_read(root,'sourcing_plan.json',{}),source_run_dir=root)
            if report['page_count']!=len(pages) or report['insufficient_pages']:
                raise ValueError('content handoff did not produce a complete source-bound page set')
            packages=[json.loads(p.read_text()) for p in (candidate/'page_packages').glob('*.json') if p.name!='index.json']
            from quality.semantic_checks import find_unsupported_numbers, find_internal_label_leak
            findings=find_unsupported_numbers(packages,context_manifest=context)+find_internal_label_leak(packages)
            if findings:
                raise ValueError('content review blocked: '+findings[0]['message'])
            narrative_json = json.dumps(narrative,ensure_ascii=False,indent=2)
            context_json = json.dumps(context,ensure_ascii=False,indent=2)
            completed_refs = copy.deepcopy(task['based_on']['input_refs'])
            for ref in completed_refs:
                if ref['ref'] == 'context_manifest.json':
                    ref['sha256'] = hashlib.sha256(context_json.encode()).hexdigest()
                if ref['ref'] == 'narrative_plan.json':
                    ref['sha256'] = hashlib.sha256(narrative_json.encode()).hexdigest()
            task.update(status='content_ready',result_sha256=digest,content_review=review,
                        completed_based_on={'input_refs':completed_refs,'input_fingerprint':fingerprint_payload(completed_refs)})
            files={str(path.relative_to(candidate)):path.read_text() for path in (candidate/'page_packages').glob('*.json')}
            files['context_manifest.json']=context_json
            files.update({'narrative_plan.json':json.dumps(narrative,ensure_ascii=False,indent=2),TASK_REF:json.dumps(task,ensure_ascii=False,indent=2)})
            receipt=_commit(root,parent,files,task['task_id'])
        return {'status':'content_ready','page_count':len(pages),'revision_id':receipt['revision_id'],'content_review':review,'delivery_approved':False}
