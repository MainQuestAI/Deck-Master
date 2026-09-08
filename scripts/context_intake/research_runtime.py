"""Durable, bounded host research with explicit public projection authorization.

Tool execution belongs to the host. Runtime issues one action at a time and
records actual host observations; a receipt is not an independent truth check.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from native_pptx.contracts import SCHEMA_DIR
from workflow.actions import (
    create_action_envelope, stage_action_result, commit_action_result,
    fingerprint_payload, read_current_revision, revision_read, revision_input_path,
    validate_identifier,
)
from .research_task import ingest_research_result, redaction_problems, _utc_now

TERMINAL = {'executed', 'inconclusive', 'capability_unavailable'}


def _path(root: Path, relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute() or '..' in raw.parts or not relative:
        raise ValueError('research reference must be relative to the run')
    path = root / raw
    if not path.resolve().is_relative_to(root):
        raise ValueError('research reference escapes run')
    return revision_input_path(root, path)


def _read(root: Path, relative: str, default=None):
    path = _path(root, relative)
    return json.loads(path.read_text()) if path.exists() else default


def _state_ref(task_id: str) -> str:
    return f'research/tasks/{validate_identifier(task_id,"task_id")}.json'


def _persist(root: Path, parent: str, state: dict, *, context: dict | None = None) -> dict:
    files = {_state_ref(state['task']['task_id']): json.dumps(state, ensure_ascii=False, indent=2)}
    if context is not None:
        files['context_manifest.json'] = json.dumps(context, ensure_ascii=False, indent=2)
    action = 'research_' + fingerprint_payload({'parent':parent,'files':files})[:32]
    fp = fingerprint_payload(parent)
    envelope = create_action_envelope(action_id=action, task_id='research_state_'+state['task']['task_id'], scope_pages=['research'], permission='runtime', input_fingerprint=fp)
    stage_action_result(root, envelope, files)
    commit_action_result(root, envelope, current_input_fingerprint=lambda: fingerprint_payload(read_current_revision(root).get('revision_id','')), expected_revision=parent, targets={ref:root/ref for ref in files})
    return _status(state)


def _status(state: dict) -> dict:
    task = state['task']
    return {'task_id':task['task_id'],'status':state['status'],'actions_used':len(state['actions']), 'max_tool_actions':task['limits']['max_tool_actions'], 'pending_action':state.get('pending_action'), 'affected_refs':[ref for q in task['questions'] for ref in q['affected_refs']], 'open_questions':state.get('result',{}).get('open_questions',[])}


def _authorize(root: Path, task: dict) -> None:
    auth = _read(root, task['authorization_ref'])
    if not isinstance(auth,dict) or auth.get('scope') != 'public_research' or not str(auth.get('authorization_basis') or '').strip():
        raise ValueError('public research requires an explicit authorization record and basis')
    if auth.get('public_query_context') != task['public_query_context'] or auth.get('allowed_sources') != task['allowed_sources']:
        raise ValueError('research query or sources differ from the authorized public projection')
    limits = task['limits']
    defaults = {'max_rounds_per_question': 2, 'max_tool_actions': 2, 'max_candidate_sources_per_round': 6}
    authorized_limits = auth.get('limits') or {}
    for name, default in defaults.items():
        ceiling = authorized_limits.get(name, default)
        if not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling < 1 or limits[name] > ceiling:
            raise ValueError('research budget exceeds explicit matching authorization or default limits: '+name)
    problems = redaction_problems([task['public_query_context']])
    if problems:
        raise ValueError('unredacted public query: ' + '; '.join(problems))
    for source in task['allowed_sources']:
        if not source or '/' in source or ':' in source or source.startswith('.'):
            raise ValueError('allowed_sources must contain exact public hostnames')


def _check_inputs(root: Path, task: dict) -> None:
    refs = task['based_on']['input_refs']
    if task['based_on']['input_fingerprint'] != fingerprint_payload(refs):
        raise ValueError('research task input fingerprint does not match its refs')
    for ref in refs:
        path = _path(root, ref['ref'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('research task input is stale: '+ref['ref'])
    _authorize(root,task)


def prepare_research(run_dir: str | Path, task: dict) -> dict:
    root = Path(run_dir).resolve()
    schema = json.loads((SCHEMA_DIR/'research-task.v1.schema.json').read_text())
    errors = list(Draft202012Validator(schema).iter_errors(task))
    if errors:
        raise ValueError('invalid research task: '+errors[0].message)
    if len(task['questions']) != 1:
        raise ValueError('dispatch one concrete research question per task; use separate task ids for independent questions')
    with revision_read(root) as parent:
        request = _read(root,'request.json',{})
        if task['run_id'] != request.get('run_id',root.name) or task['run_mode'] != request.get('run_mode','production'):
            raise ValueError('research task run identity mismatch')
        _check_inputs(root,task)
        existing = _read(root,_state_ref(task['task_id']))
        if existing:
            if existing['task'] != task:
                raise ValueError('research task id already belongs to different inputs')
            return _status(existing)
        return _persist(root,parent,dict(task=copy.deepcopy(task),status='pending',actions=[],pending_action=None,created_at=_utc_now()))


def research_status(run_dir: str | Path, task_id: str) -> dict:
    root = Path(run_dir).resolve()
    with revision_read(root):
        state = _read(root,_state_ref(task_id))
        if not state:
            raise ValueError('research task does not exist')
        return _status(state)


def research_continuation(run_dir: str | Path) -> dict | None:
    """Expose durable pending research to the common continuation router."""
    import shlex
    root = Path(run_dir).resolve()
    with revision_read(root):
        directory = revision_input_path(root, root / 'research/tasks')
        for path in sorted(directory.glob('*.json')):
            state = json.loads(path.read_text())
            if state['status'] != 'pending':
                continue
            status = _status(state)
            command = f'deck-master research dispatch --run-dir {shlex.quote(str(root))} --task-id {shlex.quote(status["task_id"])}'
            return {'stage':'awaiting_agent_execution', 'reason':'pending public research; affected refs: '+', '.join(status['affected_refs']),
                    'next_command':command, 'host_task':{'kind':'research','research_status':status}, 'build_status':{}}
    return None


def dispatch_research(run_dir: str | Path, task_id: str) -> dict:
    root = Path(run_dir).resolve()
    with revision_read(root) as parent:
        state = _read(root,_state_ref(task_id))
        if not state:
            raise ValueError('research task does not exist')
        if state['status'] in TERMINAL:
            return _status(state)
        task=state['task']; _check_inputs(root,task)
        if state.get('pending_action'):
            return {**state['pending_action'],'resumed':True}
        question = next((q for q in task['questions'] if sum(a['question_id']==q['question_id'] for a in state['actions']) < task['limits']['max_rounds_per_question']),None)
        if len(state['actions']) >= task['limits']['max_tool_actions'] or question is None:
            raise ValueError('research budget exhausted; no additional action can be issued')
        action=dict(action_id='query_'+fingerprint_payload({'task':task,'attempt':len(state['actions'])})[:32],task_id=task_id,question_id=question['question_id'],status='awaiting_host',query=task['public_query_context'],allowed_sources=task['allowed_sources'],max_sources=task['limits']['max_candidate_sources_per_round'],issued_at=_utc_now())
        state['pending_action']=action; state['actions'].append(copy.deepcopy(action))
        _persist(root,parent,state)
        return action


def submit_research(run_dir: str | Path, result: dict) -> dict:
    if not isinstance(result, dict):
        raise ValueError('research result must be an object')
    root = Path(run_dir).resolve()
    with revision_read(root) as parent:
        state = _read(root,_state_ref(result.get('task_id','')))
        if not state:
            raise ValueError('research task does not exist')
        result_hash = fingerprint_payload(result)
        previous = next((a for a in state['actions'] if a['action_id']==result.get('action_id')),None)
        if previous and previous.get('result_sha256'):
            if previous['result_sha256'] != result_hash:
                raise ValueError('conflicting research result replay')
            return _status(state)
        action = state.get('pending_action')
        if state['status'] != 'pending' or not action or action['action_id'] != result.get('action_id'):
            raise ValueError('research result does not match current issued action')
        task=state['task']; _check_inputs(root,task)
        status = result.get('status')
        if status not in TERMINAL | {'retryable_error'}:
            raise ValueError('invalid research outcome')
        logs=result.get('query_log')
        if not isinstance(logs,list) or len(logs) != 1:
            raise ValueError('research outcome requires an actual tool or capability observation')
        for log in logs:
            if not isinstance(log,dict) or log.get('query') != action['query'] or not str(log.get('tool') or '').strip() or not str(log.get('observation') or '').strip():
                raise ValueError('research log must bind the authorized query and actual tool observation')
        sources=result.get('sources') or []
        if not isinstance(sources,list) or any(not isinstance(source,dict) for source in sources):
            raise ValueError('research sources must be an array of objects')
        if len(sources)>action['max_sources']:
            raise ValueError('research candidate source budget exceeded')
        if status=='executed' and (not sources or not result.get('counter_evidence')):
            raise ValueError('executed research requires sources and a counter-evidence check')
        if status in {'capability_unavailable','retryable_error'} and sources:
            raise ValueError('failed or unavailable research cannot claim consulted sources')
        for source in sources:
            parsed=urlparse(str(source.get('url') or ''))
            if parsed.scheme!='https' or parsed.hostname not in task['allowed_sources'] or parsed.username or parsed.password:
                raise ValueError('research source is outside authorized public sources')
            if not str(source.get('excerpt') or '').strip() or not source.get('applicability_bounds'):
                raise ValueError('research source requires captured content and applicability bounds')
        previous.update(status=status,result_sha256=result_hash,result=copy.deepcopy(result))
        state['pending_action']=None
        limit=task['limits']
        exhausted=len(state['actions'])>=limit['max_tool_actions'] or all(sum(a['question_id']==q['question_id'] for a in state['actions'])>=limit['max_rounds_per_question'] for q in task['questions'])
        if status=='retryable_error' and not exhausted:
            return _persist(root,parent,state)
        terminal=copy.deepcopy(result)
        for source in terminal.get('sources') or []:
            source['source_id'] = hashlib.sha256(f"{task['task_id']}:{source['url']}".encode()).hexdigest()[:16]
        if status=='retryable_error':
            terminal['status']='inconclusive';terminal['result_summary']='Research budget exhausted after tool errors; no supported conclusion.'
        terminal['question']='; '.join(q['question'] for q in task['questions'])
        terminal['affects']=[ref for q in task['questions'] for ref in q['affected_refs']]
        state['status']=terminal['status'];state['result']=terminal
        context=_read(root,'context_manifest.json',{'schema_version':'deck_context_manifest.v1','sources':[]})
        context=ingest_research_result(context,terminal)
        context['research_meta'][-1].update(affects=terminal['affects'],query_log=logs,result_sha256=result_hash,authorization_ref=task['authorization_ref'],actions_used=len(state['actions']))
        return _persist(root,parent,state,context=context)
