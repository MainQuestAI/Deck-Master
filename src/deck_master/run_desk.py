"""Bounded, snapshot-bound run projections; no writes or execution side effects."""
from __future__ import annotations

import copy
import re
from collections import Counter
from datetime import datetime, timezone
from functools import wraps

from .models import validate_schema
from .snapshots import IDENTIFIER, READ_FAILURES, ReadModelError, load_snapshot
from .store import Store
from .result_reading import key as reading_key
from .workbench import _ReadContext, _candidate_facts
from .action_currentness import Projection

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


def task_instruction_summary(task):
    """Only summarize exact core-authored compose wrappers, never edit the request.

    These literals mirror service/content_ops dispatch templates. An unknown or
    changed template falls back to the complete instruction rather than guessing
    which words belong to the user's request.
    """
    text = task.get('instruction') or ''
    if task.get('kind') != 'compose':
        return text
    initial = ("Read every source in Task.sources plus the method resources; derive the "
               "audience's open question and write complete visible copy as Page v2 with "
               "an explicit page order. Same source supports different framings; do not "
               "call a rule planner or fill pages from templates.")
    if task.get('intent') in ('initial', 'import_draft', None) and text == initial:
        return '阅读全部材料，围绕受众的问题组织完整正文与页面顺序。'
    trial_suffix = (' 当前为显式 trial：除 content_update 外还须提交完整 content_plan_input；'
                    '结果保存为候选，采用前不改动当前正文、页序或产物。')
    input_id = task.get('input_revision_id')
    prefix = f'输入已更新（operation {input_id}）：'
    if task.get('protocol_version') == 'compose.v2' and task.get('intent') == 'input_revision' and input_id and text.startswith(prefix):
        trial = text.endswith(trial_suffix)
        body = text[:-len(trial_suffix)] if trial else text
        modern_suffix = ('。读取新输入与 diff，提交 compose.v2 input_revision：changed_layers、'
                         '每个变化层的 proposal Ref 与 diff。')
        reason, marker, impact = body[len(prefix):].rpartition(modern_suffix)
        # Only the literal core template plus its known impact-summary grammar
        # is a wrapper. Additional user prose must remain complete, never be
        # discarded by a loose prefix/substring sanitizer.
        identity = r'[A-Za-z0-9][A-Za-z0-9_.-]*'
        identities = identity + r'(?:, ' + identity + r')*'
        task_field = r'(?:title|brief|audience|scenario|presentation_mode|presentation_mode_source|page_limit|existing_decisions)'
        fields = task_field + r'(?:, ' + task_field + r')*'
        part = (r'(?:(?:新增来源|移除来源|来源版本变化) [1-9][0-9]*'
                r'|任务事实变化：' + fields + r'|受影响 claim：' + identities +
                r'|受影响页面：' + identities + r'|没有页面直接引用变化的来源)')
        known_impact = re.fullmatch(r' 影响分析：(本次没有材料或任务事实变化|' + part + r'(?:；' + part + r')*)。', impact)
        if marker and (not impact or known_impact):
            return (reason + ' · 核对新材料与全稿正文，只更新受影响内容。' + impact
                    + (' 先返回候选，采用前保持当前稿。' if trial else ''))
    suffixes = {
        'input_revision': ('。读取新输入、变化说明与全稿概览，检查相关正文和跨页结论；提交 content_update，'
                           '只包含真正变化的完整 Page v2、新增/删除页 ID 和最终页序；无影响时给出具体 unchanged_reason。'),
        'initial': '。读取全部来源与任务事实，按方法写完整 Page v2 正文与页序。',
    }
    suffix = suffixes.get(task.get('intent'))
    if input_id and suffix and text.startswith(prefix):
        trial = text.endswith(trial_suffix)
        body = text[:-len(trial_suffix)] if trial else text
        if body.endswith(suffix):
            reason = body[len(prefix):-len(suffix)]
            purpose = '核对新材料与全稿正文，只更新受影响内容。' if task['intent'] == 'input_revision' else '阅读更新后的材料，整理完整正文与页面顺序。'
            return reason + ' · ' + purpose + (' 先返回候选，采用前保持当前稿。' if trial else '')
    operation_suffix = ('\n仅处理所选页。rewrite 保留原 page_id；merge/split 返回全新 page_id，移除所选旧页。'
                        '未选页正文及目标不得改变。提交完整 content_plan 和 content_update，包含具体影响依据；不生成图片。')
    candidate_suffix = '当前为 trial：结果保存为候选，采用前不改动当前正文或页序。'
    if task.get('content_operation_ref'):
        body = text
        if task.get('protocol_version') == 'compose.v2':
            modern_operation = ('\n正式返回 compose_result.v2 variant=input_revision；changed_layers仅page_copy/plan；'
                '每个变化页提交完整含映射的Page Ref，plan提交完整content_plan_input.v2 Ref；'
                'diff列input_digest、真实changed_page_ids、removed_page_ids与完整page_order。未选页不得改变。')
            if not body.endswith(modern_operation):
                return text
            body = body[:-len(modern_operation)]
        trial = body.endswith(candidate_suffix)
        body = body[:-len(candidate_suffix)] if trial else body
        for action, label in (('rewrite', '改写所选正文'), ('merge', '合并所选页'), ('split', '拆分所选页')):
            prefix = f'明确的内容操作 {action}：'
            if body.startswith(prefix) and body.endswith(operation_suffix):
                reason = body[len(prefix):-len(operation_suffix)]
                return reason + ' · ' + label + '，其余页面保持。' + (' 先返回候选，采用前保持当前稿。' if trial else '')
    return text


def task_row(task, ref=None, *, adopted=(), now=None, live=True, projection=None, pending_shas=None):
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
    if pending_shas is not None:
        pending_candidates = [r for r in pending_candidates if r['sha256'] in pending_shas]
    relation = projection.task(task) if projection else {'state': 'unknown', 'reason': 'context_not_loaded'}
    actions = []
    if unknown:
        actions.append('verify_unknown_call')
    if stale or unclaimed_running:
        actions.append('verify_execution')
    if task['status'] == 'awaiting_host':
        actions.append('handoff')
    elif task['status'] == 'failed':
        actions.append('inspect_failure')
    elif task['status'] == 'completed':
        if pending_candidates:
            actions.append('compare_candidates')
        elif not task.get('candidate_refs') and task.get('result_refs'):
            actions.append('review_results')
    if 'handoff' in actions and relation['reason'] in ('dependency_basis_changed', 'dependencies_unverifiable'):
        actions = ['replan' if relation['reason'] == 'dependency_basis_changed' else 'verify_execution']
    if unknown:
        actions = [action for action in actions if action in ('verify_unknown_call', 'verify_execution')]
    if relation['state'] == 'historical':
        actions = []
    return {'current_relation': relation, 'ref': ref, 'task_id': task['task_id'], 'operation_id': task['operation_id'],
            'kind': task['kind'], 'status': task['status'], 'scope_pages': task['scope_pages'],
            'instruction': task['instruction'], 'display_instruction': task_instruction_summary(task), 'dispatch_revision': task['dispatch_revision'],
            'created_at': task['created_at'], 'updated_at': task['updated_at'],
            'execution_ref': task.get('execution_ref'), 'execution_started_at': started,
            'execution_time_source': 'core_recorded' if started else 'not_recorded',
            'verification_clock': 'live' if live else 'not_evaluated_for_fixed_revision',
            'needs_verification': unknown or stale or unclaimed_running,
            'waiting_time_basis': 'execution_started_at' if started else 'last_task_update' if wait_basis else 'unknown', 'call_counts': dict(calls),
            'reading_key':reading_key(task), 'human_actions': actions, 'request_count': len(task.get('generation_requests', [])),
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
def listing(project, *, revision=None, limit=30, offset=0, change_id=None, status=None, attention=False, reading=None, search=None):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0 or type(attention) is not bool:
        raise RunReadError('invalid_run_query', 'pagination', 'limit must be 1..100, offset nonnegative, attention boolean', http_status=400)
    if status is not None and status not in ('queued', 'awaiting_host', 'running', 'completed', 'failed', 'cancelled', 'superseded', 'unreadable'):
        raise RunReadError('invalid_run_query', 'status', 'unknown task status', http_status=400)
    if change_id is not None and (not isinstance(change_id, str) or not IDENTIFIER.fullmatch(change_id)):
        raise RunReadError('invalid_run_query', 'change_id', 'invalid change identifier', http_status=400)
    if search is not None and (not isinstance(search, str) or len(search) > 200):
        raise RunReadError('invalid_run_query', 'search', 'search must be text up to 200 characters', http_status=400)
    needle = (search or '').strip().casefold()
    store = Store(project); doc = load_snapshot(store, revision); ctx = _ReadContext(store, doc)
    page_terms = {}
    if needle:
        for index, entry in enumerate(doc['pages']):
            title = ''
            try:
                title = str((ctx.read(entry['page']).get('customer_visible') or {}).get('title') or '')
            except READ_FAILURES:
                pass  # A damaged page must not hide its task's own searchable identity.
            page_terms[entry['page_id']] = f"{entry['page_id']} 第{index + 1}页 第 {index + 1} 页 {title}"
    kind_names = {'style_analyze': '分析截图规范', 'reconstruct': '制作可编辑稿', 'compile': '编译整稿',
                  'check': '工程检查', 'compose': '整理内容', 'blueprint': '制作原图', 'svg': '制作 SVG',
                  'render': '渲染预览', 'repair': '局部修改', 'review': '检查', 'export': '准备文件'}
    records = _records(ctx); groups = _groups(ctx, records)
    projection, pending_shas = _projection(ctx, records)
    selected_ids = None
    if change_id:
        group = next((g for g in groups if g['change_id'] == change_id), None)
        if group is None:
            raise RunReadError('change_not_found', 'change_id', 'change is not in this committed version')
        selected_ids = set(group['task_ids'])
    adopted = {r['candidate_ref']['sha256'] for r in doc.get('candidate_adoptions', [])}
    now = datetime.now(timezone.utc); projected = []
    for ref, task in reversed(records):
        row = (task_row(task, ref, adopted=adopted, now=now, live=revision is None, projection=projection, pending_shas=pending_shas) if task else
               {'ref': ref, 'task_id': None, 'status': 'unreadable', 'human_actions': ['inspect_failure'], 'error': _error()})
        if task and reading is not None and reading_key(task) in reading['seen']:
            row['human_actions']=[a for a in row['human_actions'] if a!='review_results']
        if selected_ids is not None and row['task_id'] not in selected_ids:
            continue
        if status is not None and row['status'] != status:
            continue
        if attention and not row['human_actions']:
            continue
        if needle:
            text = ' '.join([str(row.get('task_id') or ''), str(row.get('instruction') or ''), str(row.get('display_instruction') or ''),
                             kind_names.get(row.get('kind'), ''),
                             *(page_terms.get(pid, pid) for pid in row.get('scope_pages', []))])
            if needle not in text.casefold():
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
    records = _records(ctx)
    projection, pending_shas = _projection(ctx, records)
    record = next(((ref, t) for ref, t in records if t and t['task_id'] == task_id), None)
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
        'task': task_row(task, ref, adopted=adopted, live=revision is None, projection=projection, pending_shas=pending_shas), 'links': links,
        'call_allowances': task.get('call_allowances', []), 'errors': errors, 'docs_ref': DOCS})


def _projection(ctx, records):
    tasks = {task['task_id']: task for _, task in records if task}
    ctx.action_projection = Projection(ctx, tasks)
    _, facts = _candidate_facts(ctx, tasks)
    pending = {ref['sha256'] for fact in facts for ref in fact['source_refs'][:1]}
    return ctx.action_projection, pending
