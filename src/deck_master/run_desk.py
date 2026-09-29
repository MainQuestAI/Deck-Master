"""Bounded, snapshot-bound run projections; no writes or execution side effects."""
from __future__ import annotations

import copy
from collections import Counter
from datetime import datetime, timezone
from functools import wraps

from .models import validate_schema
from .snapshots import IDENTIFIER, READ_FAILURES, ReadModelError, load_snapshot
from .store import Store
from .workbench import _ReadContext

DOCS = 'docs/agent-recovery-playbook.md#run-desk-recovery'


class RunReadError(ReadModelError):
    def payload(self):
        value = super().payload()
        value['error'].update(docs_ref=DOCS, cause=self.error_code,
            next_action='read the original task at a committed revision; verify unknown calls before any replacement')
        return value


def _public(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ReadModelError:
            raise
        except READ_FAILURES as exc:
            raise RunReadError('run_unavailable', 'project', 'run records cannot be read in this project', http_status=503) from exc
    return wrapped


def _error(field='task'):
    return RunReadError('run_object_unreadable', field, 'stored run object is missing, invalid or damaged').payload()['error']


def _records(ctx):
    rows = []
    for ref in ctx.document['tasks']:
        try:
            task = ctx.read(ref)
            if task.get('schema_version') != 'deck_task.v1':
                raise ValueError('not a task')
            rows.append((ref, task))
        except READ_FAILURES:
            rows.append((ref, None))
    return rows


def task_row(task, ref=None, *, adopted=(), now=None, live=True):
    now = now or datetime.now(timezone.utc)
    def timestamp(value):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return parsed if parsed.tzinfo is not None else None
        except (TypeError, ValueError, AttributeError):
            return None
    started_time = timestamp(task.get('execution_started_at'))
    started = task.get('execution_started_at') if started_time else None
    # A legacy last update is a lower bound for waiting, never a claim time.
    wait_basis = started_time or timestamp(task.get('updated_at'))
    stale = bool(live and task['status'] == 'running' and wait_basis and (now - wait_basis).total_seconds() >= 1800)
    unclaimed_running = task['status'] == 'running' and not task.get('execution_ref')
    calls = Counter(call['state'] for call in task.get('call_allowances', []))
    unknown = bool(calls['unknown'])
    pending_candidates = [r for r in task.get('candidate_refs', []) if r['sha256'] not in adopted]
    actions = []
    if unknown:
        actions.append('verify_unknown_call')
    if stale or unclaimed_running:
        actions.append('verify_execution')
    if task['status'] == 'awaiting_host':
        actions.append('handoff')
    elif task['status'] == 'failed':
        actions.append('inspect_failure')
    elif task['status'] == 'superseded':
        actions.append('replan')
    elif task['status'] == 'completed':
        if pending_candidates:
            actions.append('compare_candidates')
        elif not task.get('candidate_refs') and task.get('result_refs'):
            actions.append('review_results')
    return {'ref': ref, 'task_id': task['task_id'], 'operation_id': task['operation_id'],
            'kind': task['kind'], 'status': task['status'], 'scope_pages': task['scope_pages'],
            'instruction': task['instruction'], 'dispatch_revision': task['dispatch_revision'],
            'created_at': task['created_at'], 'updated_at': task['updated_at'],
            'execution_ref': task.get('execution_ref'), 'execution_started_at': started,
            'execution_time_source': 'core_recorded' if started else 'not_recorded',
            'verification_clock': 'live' if live else 'not_evaluated_for_fixed_revision',
            'needs_verification': unknown or stale or unclaimed_running,
            'waiting_time_basis': 'execution_started_at' if started else 'last_task_update' if wait_basis else 'unknown', 'call_counts': dict(calls),
            'human_actions': actions, 'request_count': len(task.get('generation_requests', [])),
            'attempt_count': len(task.get('generation_attempts', [])),
            'result_refs': task.get('result_refs', []), 'candidate_refs': task.get('candidate_refs', []),
            'pending_candidate_refs': pending_candidates, 'change_binding': task.get('change_binding'),
            'error': task.get('error'), 'docs_ref': DOCS}


def _groups(ctx, rows):
    tasks = {t['task_id']: t for _, t in rows if t is not None}
    groups = []
    for ref in ctx.document.get('changes', []):
        try:
            change = ctx.read(ref); validate_schema('change_set', change)
            if change['project_id'] != ctx.document['project_id']:
                raise ValueError('foreign change')
            selected = []
            for tid in change['task_ids']:
                task = tasks[tid]
                if (task.get('change_binding') or {}).get('change_ref') != ref:
                    raise ValueError('task/change binding differs')
                selected.append(task)
            counts = Counter(t['status'] for t in selected)
            unknown = any(c['state'] == 'unknown' for t in selected for c in t.get('call_allowances', []))
            status = ('unknown' if unknown else 'completed' if counts['completed'] == len(selected)
                      else 'partial' if counts['completed'] else 'running' if counts['running']
                      else 'cancelled' if counts['cancelled'] == len(selected)
                      else 'failed' if counts['failed'] or counts['superseded'] else 'awaiting_host')
            groups.append({'change_id': change['change_id'], 'ref': ref, 'base_revision': change['base_revision'],
                'plan_ref': change['plan_ref'], 'task_ids': change['task_ids'], 'status': status,
                'completed_count': counts['completed'], 'total_count': len(selected),
                'task_counts': dict(counts), 'page_ids': list(dict.fromkeys(pid for t in selected for pid in t['scope_pages']))})
        except READ_FAILURES:
            groups.append({'change_id': None, 'ref': ref, 'status': 'unreadable', 'error': _error('change')})
    return groups


@_public
def listing(project, *, revision=None, limit=30, offset=0, change_id=None, status=None, attention=False):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0 or type(attention) is not bool:
        raise RunReadError('invalid_run_query', 'pagination', 'limit must be 1..100, offset nonnegative, attention boolean', http_status=400)
    if status is not None and status not in ('queued', 'awaiting_host', 'running', 'completed', 'failed', 'cancelled', 'superseded', 'unreadable'):
        raise RunReadError('invalid_run_query', 'status', 'unknown task status', http_status=400)
    if change_id is not None and (not isinstance(change_id, str) or not IDENTIFIER.fullmatch(change_id)):
        raise RunReadError('invalid_run_query', 'change_id', 'invalid change identifier', http_status=400)
    store = Store(project); doc = load_snapshot(store, revision); ctx = _ReadContext(store, doc)
    records = _records(ctx); groups = _groups(ctx, records)
    selected_ids = None
    if change_id:
        group = next((g for g in groups if g['change_id'] == change_id), None)
        if group is None:
            raise RunReadError('change_not_found', 'change_id', 'change is not in this committed version')
        selected_ids = set(group['task_ids'])
    adopted = {r['candidate_ref']['sha256'] for r in doc.get('candidate_adoptions', [])}
    now = datetime.now(timezone.utc); projected = []
    for ref, task in reversed(records):
        row = (task_row(task, ref, adopted=adopted, now=now, live=revision is None) if task else
               {'ref': ref, 'task_id': None, 'status': 'unreadable', 'human_actions': ['inspect_failure'], 'error': _error()})
        if selected_ids is not None and row['task_id'] not in selected_ids:
            continue
        if status is not None and row['status'] != status:
            continue
        if attention and not row['human_actions']:
            continue
        projected.append(row)
    return copy.deepcopy({'project_id': doc['project_id'], 'revision_id': doc['revision_id'],
        'tasks': projected[offset:offset + limit], 'groups': groups,
        'pagination': {'offset': offset, 'limit': limit, 'total': len(projected),
                       'next_offset': offset + limit if offset + limit < len(projected) else None},
        'counts': dict(Counter(row['status'] for row in projected)),
        'active': any(task and task['status'] in ('queued', 'awaiting_host', 'running') for _, task in records),
        'read_only': True, 'empty_actions': ['read_content', 'read_current_stages'] if not records else [], 'docs_ref': DOCS})


@_public
def detail(project, *, task_id, revision=None):
    if not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id):
        raise RunReadError('invalid_run_query', 'task_id', 'invalid task identifier', http_status=400)
    store = Store(project); doc = load_snapshot(store, revision); ctx = _ReadContext(store, doc)
    record = next(((ref, t) for ref, t in _records(ctx) if t and t['task_id'] == task_id), None)
    if record is None:
        raise RunReadError('task_not_found', 'task_id', 'task is not readable in this committed project version')
    ref, task = record; links = {}; errors = []
    for field, key in [('generation_requests', 'request_id'), ('generation_attempts', 'attempt_id')]:
        links[field] = []
        for obj_ref in task.get(field, []):
            try:
                obj = ctx.read(obj_ref)
                if obj['task_id'] != task_id or obj['project_id'] != doc['project_id']:
                    raise ValueError('foreign generation record')
                links[field].append({'ref': obj_ref, key: obj[key]})
            except READ_FAILURES:
                errors.append(_error(field))
    adopted = {r['candidate_ref']['sha256'] for r in doc.get('candidate_adoptions', [])}
    return copy.deepcopy({'project_id': doc['project_id'], 'revision_id': doc['revision_id'],
        'task': task_row(task, ref, adopted=adopted, live=revision is None), 'links': links,
        'call_allowances': task.get('call_allowances', []), 'errors': errors, 'docs_ref': DOCS})
