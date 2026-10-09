"""Immutable trial results and all-or-none adoption on the existing Store.

B03 adds the content candidate union beside the original image/SVG artifacts:
a single-page Page candidate (``result_kind: page``) and a whole changeset
candidate (``result_kind: content_update``). Returning a result only records
an immutable candidate; the current Page, page order, ContentPlan and outputs
move exclusively through explicit adoption, which reuses the local content
update and invalidation algorithms instead of a second writer.
"""
from __future__ import annotations

import copy
import uuid

from . import operations, tasks
from .local_state import project_path
from .models import (ModelError, bump_revision, canonical_json_bytes, compute_input_digest,
                     content_identity, require_writer, sha256_bytes, validate_schema,
                     validate_task_semantics)
from .snapshots import load_snapshot
from .store import Store

WRITER = 'candidates.v1'
CONTENT_WRITER = 'content-candidates.v1'
CAPABILITY = 'candidate_result'
CONTENT_CAPABILITY = 'content_candidate'
# A content change invalidates everything downstream of the Page; the current
# blueprint stays readable as history (same rule as a local content update).
CONTENT_DOWNSTREAM = ['svg', 'svg_preview', 'ppt_preview', 'deck_outputs', 'quality_applicability']


def is_trial(task):
    return task.get('stage_request', {}).get('mode') == 'trial'


def result_kind(candidate):
    return candidate.get('result_kind', 'artifact')


def generation_basis(store, document, page_id, stage, *, preserve_blueprint=False):
    from .production import resolve_design
    entry = next((e for e in document['pages'] if e['page_id'] == page_id), None)
    if entry is None:
        return None
    page = store.read_object_json(entry['page'])
    design, _ = resolve_design(page, document['design_context'], document['design_context'].get('assets') or [])
    if stage == 'content':
        # Precise single-page scope: the Page identity decides adoption
        # concurrency; the digests stay recorded dispatch facts, not gates.
        return {'page_ref': entry['page'], 'input_digest': compute_input_digest(document),
                'design_digest': sha256_bytes(canonical_json_bytes(design)), 'blueprint_ref': None}
    return {'page_ref': entry['page'], 'input_digest': compute_input_digest(document),
            'design_digest': sha256_bytes(canonical_json_bytes(design)),
            'blueprint_ref': entry.get('blueprint') if stage == 'svg' or preserve_blueprint else None}


def inputs_current(store, document, task):
    target_reference = task.get('stage_request', {}).get('target_reference_ref')
    if target_reference:
        if len(task['scope_pages']) != 1:
            return False
        current = next((entry for entry in document['pages'] if entry['page_id'] == task['scope_pages'][0]), None)
        if current is None or current.get('blueprint') != target_reference:
            return False
    # Same freshness short-circuit as the generic task path: an identical
    # content identity means pages, sources and task facts are unchanged, so
    # the per-page basis comparison would be a no-op (and inputs_update may
    # call this before the dispatch revision is even committed).
    if content_identity(document) == task.get('produced_against'):
        return True
    stage = 'content' if task.get('stage_request', {}).get('stage') == 'content' else (
        'blueprint' if task['kind'] == 'blueprint' else 'svg')
    dispatched = load_snapshot(store, task['dispatch_revision'])
    return all(generation_basis(store, document, pid, stage) == generation_basis(store, dispatched, pid, stage)
               and any(e['page_id'] == pid for e in document['pages'])
               for pid in task['scope_pages'])


def content_basis(document):
    """The fixed basis a whole changeset was derived against (B03 contract)."""
    return {'input_digest': compute_input_digest(document),
            'page_sequence': [{'page_id': e['page_id'], 'page_sha256': e['page']['sha256']} for e in document['pages']],
            'content_plan_ref': document.get('content_plan')}


def _trial_request_ref(store, task):
    """The frozen content request a content trial was dispatched from."""
    binding = task.get('change_binding') or {}
    if binding.get('change_ref'):
        return store.read_object_json(binding['change_ref']).get('plan_ref')
    return task.get('content_operation_ref')


def _common_linkage(candidate, ref, task):
    if (task.get('status') != 'completed' or not is_trial(task)
            or candidate['base_revision'] != task['dispatch_revision']
            or ref not in task.get('candidate_refs', [])
            or candidate['result_ref'] not in task.get('result_refs', [])):
        raise operations.OperationError('candidate_invalid', 'candidate/task_id', 'candidate is not a committed trial result')


def _artifact_linkage(store, document, candidate, task):
    if (task['scope_pages'] != [candidate['page_id']]
            or candidate['stage'] != ('blueprint' if task['kind'] == 'blueprint' else 'svg')):
        raise operations.OperationError('candidate_invalid', 'candidate/task_id', 'candidate is not a committed trial result')
    if candidate['stage'] == 'blueprint':
        request, attempt = (store.read_object_json(candidate['request_ref']) if candidate['request_ref'] else None,
                            store.read_object_json(candidate['attempt_ref']) if candidate['attempt_ref'] else None)
        validate_schema('generation_request', request); validate_schema('generation_attempt', attempt)
        if (candidate['request_ref'] not in task.get('generation_requests', [])
                or candidate['attempt_ref'] not in task.get('generation_attempts', [])
                or attempt['request_ref'] != candidate['request_ref']
                or request['task_id'] != task['task_id'] or attempt['task_id'] != task['task_id']
                or request['project_id'] != document['project_id'] or attempt['project_id'] != document['project_id']):
            raise operations.OperationError('candidate_invalid', 'request_ref', 'candidate request and attempt do not belong to its task')


def _page_linkage(store, document, candidate, task):
    if (candidate['stage'] != 'content' or task['scope_pages'] != [candidate['page_id']]
            or task.get('kind') not in ('repair', 'compose')):
        raise operations.OperationError('candidate_invalid', 'candidate/task_id', 'candidate is not a committed content trial result')
    if candidate['request_ref'] and candidate['request_ref'] != _trial_request_ref(store, task):
        raise operations.OperationError('candidate_invalid', 'request_ref', 'candidate request differs from the committed content request')
    page = store.read_object_json(candidate['result_ref']); validate_schema('page', page)
    if page.get('page_id') != candidate['page_id']:
        raise operations.OperationError('candidate_invalid', 'result_ref', 'result identity differs from the candidate')


def _changeset_linkage(store, document, candidate, task):
    if candidate['stage'] != 'content' or task.get('kind') != 'compose':
        raise operations.OperationError('candidate_invalid', 'candidate/task_id', 'candidate is not a committed changeset trial result')
    if candidate['request_ref'] and candidate['request_ref'] != _trial_request_ref(store, task):
        raise operations.OperationError('candidate_invalid', 'request_ref', 'candidate request differs from the committed content request')
    changeset = store.read_object_json(candidate['result_ref'])
    if not isinstance(changeset, dict) or not isinstance(changeset.get('page_order'), list):
        raise operations.OperationError('candidate_invalid', 'result_ref', 'result is not a recorded content update')
    if candidate['plan_input_ref']:
        validate_schema('content_plan_input', store.read_object_json(candidate['plan_input_ref']))


def _records(store, document):
    task_map = None; records = {}
    for ref in document.get('candidates', []):
        candidate = store.read_object_json(ref); validate_schema('candidate', candidate)
        if candidate['project_id'] != document['project_id'] or candidate['candidate_id'] in records:
            raise operations.OperationError('candidate_invalid', 'candidate', 'candidate identity differs from the committed project')
        if task_map is None:
            task_map = {t['task_id']: t for r in document['tasks'] if (t := store.read_object_json(r))}
        task = task_map.get(candidate['task_id'])
        if not task:
            raise operations.OperationError('candidate_invalid', 'candidate/task_id', 'candidate is not a committed trial result')
        _common_linkage(candidate, ref, task)
        kind = result_kind(candidate)
        if kind == 'artifact':
            _artifact_linkage(store, document, candidate, task)
        elif kind == 'page':
            _page_linkage(store, document, candidate, task)
        else:
            _changeset_linkage(store, document, candidate, task)
        records[candidate['candidate_id']] = (candidate, ref, task)
    return records


def _lookup(records, candidate_id):
    if candidate_id not in records:
        raise operations.OperationError('candidate_not_found', 'candidate_id', 'candidate is not in this committed project version', http_status=404)
    return records[candidate_id]


def _state(store, document, candidate, task=None):
    adoptions = [r['revision_id'] for r in document.get('candidate_adoptions', []) if r['candidate_id'] == candidate['candidate_id']]
    kind = result_kind(candidate)
    if kind == 'content_update':
        current = content_basis(document)
        changed = [key for key in ('input_digest', 'page_sequence', 'content_plan_ref')
                   if candidate['content_basis'][key] != current[key]]
        return {'content_basis': {'status': 'changed' if changed else 'current', 'changed_fields': changed},
                'adoption_target': {'status': 'changed' if changed else 'unchanged',
                                    'original_ref': None, 'current_ref': None},
                'adopted_revisions': adoptions, **_decision_projection(store, document, candidate, adoptions),
                'status': 'adopted' if adoptions else 'available'}
    entry = next((e for e in document['pages'] if e['page_id'] == candidate['page_id']), None)
    if kind == 'page':
        # Precise scope: only the current Page identity can stale a page candidate.
        changed = ['page_ref'] if entry is None or entry['page'] != candidate['generation_basis']['page_ref'] else []
        target = entry['page'] if entry else None
    else:
        target = entry.get(candidate['stage']) if entry else None
        target_reference = (task or {}).get('stage_request', {}).get('target_reference_ref')
        preserve_blueprint = candidate['stage'] == 'blueprint' and bool(target_reference)
        basis = generation_basis(store, document, candidate['page_id'], candidate['stage'], preserve_blueprint=preserve_blueprint)
        expected = candidate['generation_basis']
        if preserve_blueprint:
            # Earlier v2 candidates stored a null blueprint basis. Their exact
            # immutable task already records the preservation reference; derive
            # it without rewriting historical candidate objects.
            expected = {**expected, 'blueprint_ref':target_reference}
            if basis and adoptions and target == candidate['result_ref']:
                # Its own explicit adoption is an allowed transition, so the
                # adopted sample remains usable for further style expansion.
                basis = {**basis, 'blueprint_ref':target_reference}
        changed = ['page_membership'] if basis is None else [key for key in basis if basis[key] != expected[key]]
    return {'generation_basis': {'status': 'changed' if changed else 'current', 'changed_fields': changed},
            'adoption_target': {'status': 'missing_page' if entry is None else 'unchanged' if target == candidate['target_ref'] else 'changed',
                                'original_ref': candidate['target_ref'], 'current_ref': target},
            'adopted_revisions': adoptions, **_decision_projection(store, document, candidate, adoptions),
            'status': 'adopted' if adoptions else 'available'}


def _decision_projection(store, document, candidate, adoptions):
    """B04 projection: latest decision activity and pending truth.

    pending 不等于未采用：曾采用仍是 adopted；keep_current 把待决变为已决定，
    reopen 恢复待决。决定与采用分别保存，互不顶替。决定记录属辅助审阅元数据：
    任一决定引用损伤（无法确认归属哪条候选）时，全部决定按 unreadable 保守
    投影并按待决处理——文档级保守是有意取舍，不阻断候选采用规划；瞬时
    IO/解析异常按同样的损伤面处理（收窄自 broad except）。
    """
    from .snapshots import READ_FAILURES
    try:
        decision = _decision_state(store, document, candidate['candidate_id'])
    except READ_FAILURES + (ValueError, KeyError, TypeError):
        decision = {'state': 'unreadable', 'decision_ref': None, 'decided_at': None}
    return {'decision': decision,
            'pending': not adoptions and decision['state'] != 'keep_current'}


def _changeset_projection(store, document, candidate, task):
    """Validate the stored changeset and derive its adoption projection."""
    from .content import check_page
    from .tasks import page_limit_violation
    changeset = store.read_object_json(candidate['result_ref'])
    upserts = {}
    for index, page in enumerate(changeset.get('upsert_pages') or []):
        try:
            upserts[page['page_id']] = check_page(page)
        except ModelError as exc:
            raise operations.OperationError('candidate_invalid', f'result_ref/upsert_pages[{index}]', str(exc)) from exc
    current_ids = {e['page_id'] for e in document['pages']}
    removed = set(changeset.get('remove_page_ids') or [])
    if (set(changeset['page_order']) != (current_ids - removed) | set(upserts)
            or removed & set(changeset['page_order'])
            or not removed <= current_ids
            or removed & set(upserts)):
        raise operations.OperationError('candidate_invalid', 'result_ref/page_order',
                                        'changeset page order does not cover the resulting deck exactly once')
    violation = page_limit_violation({'pages': changeset['page_order']})
    if violation:
        raise operations.OperationError('candidate_invalid', 'result_ref/page_order', violation)
    sources = []
    planned = store.read_object_json(task['content_operation_ref']) if task.get('content_operation_ref') else None
    if planned:
        sources = [t['page_id'] for t in planned['input']['targets']]
    mapping = []
    for pid in changeset['page_order']:
        if pid in upserts and pid in current_ids:
            mapping.append({'page_id': pid, 'source_page_ids': [pid], 'relation': 'rewritten'})
        elif pid in upserts:
            mapping.append({'page_id': pid, 'source_page_ids': list(sources), 'relation': 'derived'})
        else:
            mapping.append({'page_id': pid, 'source_page_ids': [pid], 'relation': 'retained'})
    for pid in sorted(set(changeset.get('remove_page_ids') or [])):
        mapping.append({'page_id': pid, 'source_page_ids': [pid], 'relation': 'removed'})
    return {'changeset': changeset, 'upserts': upserts, 'mapping': mapping}


def _require_workbench(document):
    """G54: candidates are a workbench.v3 family; the gate lives at the service
    layer so CLI and HTTP share one truth (web.py keeps a defensive copy)."""
    if document.get('compatibility', {}).get('project_format') != 'workbench.v3':
        raise operations.OperationError('unsupported_project_format', 'project',
                                        'candidate planning, adoption and decisions require a workbench.v3 project',
                                        http_status=409)


def _superseded_tasks(store, document, affected_ids):
    from .content_ops import _superseded
    return [t['task_id'] for t in _superseded(store, document, sorted(affected_ids))]


def record_result(store, *, document, task, updated_task, artifacts, artifact_refs,
                  generation_binding, envelope, produced_against, result_digest,
                  page_refs=None, content_update=None):
    """Caller holds the same task-accept lock and has validated the real result.

    One trial returns exactly one planned result: an image/SVG artifact, a
    single Page package, or a whole content_update changeset. Only the
    immutable candidate is recorded; current state never moves here.
    """
    if content_update is not None:
        return _record_changeset_result(store, document=document, task=task, updated_task=updated_task,
                                        envelope=envelope, content_update=content_update,
                                        produced_against=produced_against, result_digest=result_digest)
    if page_refs:
        return _record_page_result(store, document=document, task=task, updated_task=updated_task,
                                   envelope=envelope, page_refs=page_refs,
                                   produced_against=produced_against, result_digest=result_digest)
    if len(artifacts) != 1 or artifacts[0]['role'] not in ('blueprint', 'svg'):
        raise operations.OperationError('candidate_invalid', 'artifact_specs', 'a trial returns exactly one planned artifact')
    stage = artifacts[0]['role']; page_id = artifacts[0]['page_id']
    dispatched = load_snapshot(store, task['dispatch_revision'])
    entry = next(e for e in dispatched['pages'] if e['page_id'] == page_id)
    candidate = {'schema_version': 'candidate.v1', 'candidate_id': 'candidate-' + uuid.uuid4().hex,
                 'project_id': document['project_id'], 'task_id': task['task_id'],
                 'created_at': tasks._utc_now_iso(), 'page_id': page_id, 'stage': stage,
                 'base_revision': task['dispatch_revision'],
                 'generation_basis': generation_basis(store, dispatched, page_id, stage,
                     preserve_blueprint=bool(task.get('stage_request', {}).get('target_reference_ref'))),
                 'request_ref': generation_binding['request_ref'] if generation_binding else None,
                 'attempt_ref': generation_binding['attempt_ref'] if generation_binding else None,
                 'target_ref': entry.get(stage), 'result_ref': artifact_refs[0], 'status': 'available'}
    validate_schema('candidate', candidate); candidate_ref = store.put_json_object(candidate)
    updated_task['candidate_refs'] = [candidate_ref]
    updated_task['result_refs'] = [*artifact_refs, candidate_ref]
    return _commit_candidate(store, document=document, task=task, updated_task=updated_task,
                             candidate_ref=candidate_ref, writer=WRITER, envelope=envelope,
                             produced_against=produced_against, result_digest=result_digest, response={
                                 'status': 'candidate_ready', 'result_kind': 'artifact',
                                 'revision_id': None, 'candidate_ids': [candidate['candidate_id']],
                                 'candidate_refs': [candidate_ref], 'result_refs': updated_task['result_refs'],
                                 'next_action': 'compare_candidates', 'current_artifacts_changed': False})


def _record_page_result(store, *, document, task, updated_task, envelope, page_refs,
                        produced_against, result_digest):
    if (len(page_refs) != 1 or task['scope_pages'] != list(page_refs)
            or envelope.get('artifact_specs') or envelope.get('page_order')
            or envelope.get('content_plan') or envelope.get('reviews')):
        raise operations.OperationError('candidate_invalid', 'result',
                                        'a content trial returns exactly one Page for its scoped page')
    page_id = task['scope_pages'][0]
    dispatched = load_snapshot(store, task['dispatch_revision'])
    entry = next(e for e in dispatched['pages'] if e['page_id'] == page_id)
    candidate = {'schema_version': 'candidate.v1', 'candidate_id': 'candidate-' + uuid.uuid4().hex,
                 'project_id': document['project_id'], 'task_id': task['task_id'],
                 'created_at': tasks._utc_now_iso(), 'result_kind': 'page', 'page_id': page_id,
                 'stage': 'content', 'base_revision': task['dispatch_revision'],
                 'generation_basis': generation_basis(store, dispatched, page_id, 'content'),
                 'request_ref': _trial_request_ref(store, task), 'attempt_ref': None,
                 'target_ref': entry['page'], 'result_ref': page_refs[page_id], 'status': 'available'}
    validate_schema('candidate', candidate); candidate_ref = store.put_json_object(candidate)
    updated_task['candidate_refs'] = [candidate_ref]
    updated_task['result_refs'] = [page_refs[page_id], candidate_ref]
    return _commit_candidate(store, document=document, task=task, updated_task=updated_task,
                             candidate_ref=candidate_ref, writer=CONTENT_WRITER, envelope=envelope,
                             produced_against=produced_against, result_digest=result_digest, response={
                                 'status': 'candidate_ready', 'result_kind': 'page',
                                 'revision_id': None, 'candidate_ids': [candidate['candidate_id']],
                                 'candidate_refs': [candidate_ref], 'result_refs': updated_task['result_refs'],
                                 'next_action': 'compare_candidates', 'current_content_changed': False})


def _record_changeset_result(store, *, document, task, updated_task, envelope, content_update,
                             produced_against, result_digest):
    from .tasks import EnvelopeError, ModelError, StaleInputContext, _validate_content_update_request, page_limit_violation
    from .content import check_page
    from .content_ops import validate_host_result
    from .content_plan import ContentPlanError, validate_input as validate_plan_input
    from .generation import check_host
    # Same validation head as a direct content_update adoption; nothing is applied.
    check_host(task)
    _validate_content_update_request(envelope, document, task, content_update)
    validate_host_result(store, document, task, content_update, envelope.get('content_plan'))
    if content_basis(document) != content_basis(load_snapshot(store, task['dispatch_revision'])):
        raise StaleInputContext('(content_update)', 'content moved since dispatch; run continue')
    violation = page_limit_violation({'pages': content_update['page_order']})
    if violation:
        raise operations.OperationError('candidate_invalid', 'content_update/page_order', violation)
    plan_value = envelope.get('content_plan')
    # A compose.v1 changeset is only adoptable with its outline, and every
    # stored record must pass the read-side linkage checks: validate the plan
    # here exactly as adoption's bind_result will, against the resulting deck.
    if plan_value is None:
        raise EnvelopeError('(result)/content_plan',
                            'compose.v1 content trials must submit the complete content_plan')
    try:
        resulting_pages = [{'page_id': pid} for pid in content_update['page_order']]
        validate_plan_input(store, document, plan_value, resulting_pages)
    except (ModelError, ContentPlanError) as exc:
        raise EnvelopeError('(result)/content_plan', str(exc)) from exc
    frozen = copy.deepcopy(content_update)
    for index, page in enumerate(frozen.get('upsert_pages') or []):
        frozen['upsert_pages'][index] = check_page(page)
    changeset_ref = store.put_json_object(frozen)
    plan_input_ref = store.put_json_object(plan_value)
    candidate = {'schema_version': 'candidate.v1', 'candidate_id': 'candidate-' + uuid.uuid4().hex,
                 'project_id': document['project_id'], 'task_id': task['task_id'],
                 'created_at': tasks._utc_now_iso(), 'result_kind': 'content_update',
                 'stage': 'content', 'base_revision': task['dispatch_revision'],
                 'content_basis': content_basis(document),
                 'request_ref': _trial_request_ref(store, task), 'target_ref': None,
                 'result_ref': changeset_ref, 'plan_input_ref': plan_input_ref, 'status': 'available'}
    validate_schema('candidate', candidate); candidate_ref = store.put_json_object(candidate)
    updated_task['candidate_refs'] = [candidate_ref]
    updated_task['result_refs'] = [changeset_ref, *([plan_input_ref] if plan_input_ref else []), candidate_ref]
    return _commit_candidate(store, document=document, task=task, updated_task=updated_task,
                             candidate_ref=candidate_ref, writer=CONTENT_WRITER, envelope=envelope,
                             produced_against=produced_against, result_digest=result_digest, response={
                                 'status': 'candidate_ready', 'result_kind': 'content_update',
                                 'revision_id': None, 'candidate_ids': [candidate['candidate_id']],
                                 'candidate_refs': [candidate_ref], 'result_refs': updated_task['result_refs'],
                                 'impact_summary': content_update.get('impact_summary'),
                                 'unchanged_reason': (content_update.get('unchanged_reason') or '').strip() or None,
                                 'next_action': 'compare_candidates', 'current_content_changed': False})


def _commit_candidate(store, *, document, task, updated_task, candidate_ref, writer,
                      envelope, produced_against, result_digest, response):
    validate_task_semantics(updated_task)
    updated = bump_revision(document, {'operation_id': task['operation_id'], 'kind': 'task_update',
                                       'description': 'trial returned an immutable candidate; current state unchanged', 'read_set': []})
    require_writer(updated, writer)
    updated['candidates'] = [*document.get('candidates', []), candidate_ref]
    tasks._replace_task_in_document(updated, task, store.put_json_object(updated_task), store)
    response = {**response, 'revision_id': updated['revision_id']}
    return tasks._commit_adoption(store, document=updated, base_revision=document['revision_id'],
                                  task=task, envelope=envelope, produced_against=produced_against,
                                  result_digest=result_digest, response=response)


@operations.public
def show(project, *, candidate_id, revision=None):
    store = Store(project_path(project)); document = load_snapshot(store, revision)
    candidate, ref, task = _lookup(_records(store, document), candidate_id)
    kind = result_kind(candidate)
    result = {'project_id': document['project_id'], 'revision_id': document['revision_id'],
              'candidate_id': candidate_id, 'candidate_ref': ref, 'candidate': candidate,
              'result_kind': kind, 'task_id': task['task_id'],
              **_state(store, document, candidate, task)}
    if kind == 'artifact':
        artifact = store.read_object_json(candidate['result_ref']); validate_schema('artifact', artifact)
        if artifact['page_id'] != candidate['page_id'] or artifact['role'] != candidate['stage']:
            raise operations.OperationError('candidate_invalid', 'result_ref', 'result identity differs from the candidate')
        request = store.read_object_json(candidate['request_ref']) if candidate['request_ref'] else None
        attempt = store.read_object_json(candidate['attempt_ref']) if candidate['attempt_ref'] else None
        result.update(artifact=artifact, request=request, attempt=attempt,
                      references=task['stage_request']['references'])
        reference_sources = []
        if task.get('change_binding'):
            from .changes import action_for_task, _reference_files
            action_for_task(store, document, task)
            change = store.read_object_json(task['change_binding']['change_ref'])
            change_plan = store.read_object_json(change['plan_ref']); validate_schema('change_plan', change_plan)
            sources = change_plan['input'].get('references', [])
            files = _reference_files(store, document, sources)
            target_ref = task['stage_request'].get('target_reference_ref')
            expected_files = files
            if target_ref:
                dispatched = load_snapshot(store, task['dispatch_revision'])
                target = next(entry for entry in dispatched['pages'] if entry['page_id'] == candidate['page_id'])
                if target['blueprint'] != target_ref:
                    raise operations.OperationError('candidate_invalid', 'references', 'target reference differs from dispatched image')
                expected_files = [{'file':store.read_object_json(target_ref)['file'], 'role':'reference'}, *files]
            if expected_files != task['stage_request']['references']:
                raise operations.OperationError('candidate_invalid', 'references', 'fixed reference sources differ from the committed task')
            reference_sources = [{**source, 'file': file['file']} for source, file in zip(sources, files, strict=True)]
        result['reference_sources'] = reference_sources
        if task.get('stage_request', {}).get('icon_recipe_ref'):
            from .icons import _owned
            result['icon_recipe'] = _owned(store, document, ref=task['stage_request']['icon_recipe_ref'])[0]
    elif kind == 'page':
        result['page'] = store.read_object_json(candidate['result_ref'])
    else:
        projection = _changeset_projection(store, document, candidate, task)
        result.update(content_update=projection['changeset'], mapping=projection['mapping'],
                      content_plan_input=store.read_object_json(candidate['plan_input_ref']) if candidate['plan_input_ref'] else None)
    return result


@operations.public
def listing(project, *, page_id=None, revision=None):
    store = Store(project_path(project)); document = load_snapshot(store, revision)
    return {'project_id': document['project_id'], 'revision_id': document['revision_id'], 'candidates': [
        {'candidate': candidate, 'ref': ref, 'result_kind': result_kind(candidate),
         'style_recipe_ref':task.get('stage_request', {}).get('style_recipe_ref'),
         **_state(store, document, candidate, task)}
        for candidate, ref, task in _records(store, document).values() if page_id is None or candidate.get('page_id') == page_id]}


class AdoptionConflict(operations.OperationError):
    def __init__(self, failures):
        super().__init__('candidate_basis_changed', 'candidate_ids',
                         'no candidates were adopted; inspect conflicts and explicitly preview a new selection', exit_code=5)
        self.failures = failures

    def payload(self):
        value = super().payload(); value['error']['items'] = self.failures
        return value


def _plan(store, document, candidate_ids):
    records = _records(store, document)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise operations.OperationError('candidate_invalid', 'candidate_ids', 'select each candidate once')
    selected = [_lookup(records, cid) for cid in candidate_ids]
    kinds = [result_kind(candidate) for candidate, _, _ in selected]
    if kinds.count('content_update') > 1:
        raise operations.OperationError('candidate_invalid', 'candidate_ids',
                                        'one changeset per adoption; overlapping changesets cannot be mixed')
    if 'content_update' in kinds and len(candidate_ids) > 1:
        raise operations.OperationError('candidate_invalid', 'candidate_ids',
                                        'a whole changeset is adopted atomically; it cannot be mixed with slot candidates')
    selections = []; failures = []; pages = set()
    for (candidate, ref, task), kind in zip(selected, kinds):
        state = _state(store, document, candidate, task)
        if kind == 'content_update':
            if state['content_basis']['status'] != 'current':
                failures.append({'candidate_id': candidate['candidate_id'], 'cause': 'content_basis_changed',
                                 'fields': state['content_basis']['changed_fields']})
                continue
            projection = _changeset_projection(store, document, candidate, task)
            affected = set(projection['upserts']) | set(projection['changeset'].get('remove_page_ids') or [])
            selections.append({'candidate_id': candidate['candidate_id'], 'candidate_ref': ref,
                               'result_kind': 'content_update', 'stage': 'content',
                               'result_ref': candidate['result_ref'], 'plan_input_ref': candidate['plan_input_ref'],
                               'basis_digest': sha256_bytes(canonical_json_bytes(candidate['content_basis'])),
                               'mapping': projection['mapping'],
                               'page_order': list(projection['changeset']['page_order']),
                               'superseded_tasks': _superseded_tasks(store, document, affected),
                               'downstream': list(CONTENT_DOWNSTREAM)})
            continue
        if state['generation_basis']['status'] != 'current':
            failures.append({'candidate_id': candidate['candidate_id'], 'page_id': candidate['page_id'],
                             'cause': 'generation_basis_changed', 'fields': state['generation_basis']['changed_fields']})
            continue
        if candidate['page_id'] in pages:
            failures.append({'candidate_id': candidate['candidate_id'], 'page_id': candidate['page_id'],
                             'cause': 'one_candidate_per_page'})
            continue
        if task.get('stage_request', {}).get('icon_recipe_ref'):
            from .candidate_preview import require_ready
            require_ready(store.project_root, candidate['candidate_id'])
            recipe_ref = task['stage_request']['icon_recipe_ref']
            from .icons import _owned, _sample
            recipe, _ = _owned(store, document, ref=recipe_ref)
            anchor = next(t for t in recipe['input']['targets'] if t['page_id'] == candidate['page_id'])
            for icon in anchor['icons']:
                if icon['method'] == 'reuse': _sample(store, document, icon)
            if state['adoption_target']['current_ref'] != anchor['svg_ref']:
                failures.append({'candidate_id': candidate['candidate_id'], 'cause': 'icon_target_changed'})
                continue
        pages.add(candidate['page_id'])
        downstream = ['svg_preview', 'ppt_preview', 'deck_outputs', 'quality_applicability']
        if candidate['stage'] == 'blueprint':
            downstream.insert(0, 'svg')
        elif candidate['stage'] == 'content':
            downstream = list(CONTENT_DOWNSTREAM)
        selections.append({'candidate_id': candidate['candidate_id'], 'candidate_ref': ref, 'result_kind': kind,
                           'page_id': candidate['page_id'], 'stage': candidate['stage'],
                           'target_ref': state['adoption_target']['current_ref'],
                           'result_ref': candidate['result_ref'],
                           'basis_digest': sha256_bytes(canonical_json_bytes(candidate['generation_basis'])),
                           'downstream': downstream})
    if failures:
        raise AdoptionConflict(failures)
    plan = {'schema_version': 'candidate_adoption.v1', 'project_id': document['project_id'],
            'base_revision': document['revision_id'], 'selections': selections, 'max_calls': 0}
    validate_schema('candidate_adoption', plan)
    return plan


@operations.public
def plan(project, *, input):
    validate_schema('candidate_selection', input)
    store = Store(project_path(project)); document = load_snapshot(store)
    _require_workbench(document)
    if input['project_id'] != document['project_id'] or input['base_revision'] != document['revision_id']:
        raise operations.OperationError('conflict', 'base_revision', 'read current state and preview adoption again', exit_code=5)
    value = _plan(store, document, input['candidate_ids']); ref = store.put_json_object(value)
    return {'status': 'planned', 'plan_id': 'adopt-plan-' + ref['sha256'], 'plan_ref': ref, 'plan': value}


def _apply_page_selection(store, document, updated, selection, operation_id):
    """One Page candidate adoption: the local content-edit invalidation rules.

    A normalized-identical page changes nothing: no slots cleared, no output
    retirement, no plan version bump — only the adoption record is written.
    """
    from .content_ops import refresh_plan_links
    page = store.read_object_json(selection['result_ref']); validate_schema('page', page)
    if page['page_id'] != selection['page_id']:
        raise operations.OperationError('candidate_invalid', 'result_ref', 'result identity differs from the adoption plan')
    entry = next(e for e in updated['pages'] if e['page_id'] == selection['page_id'])
    if entry['page'] == selection['result_ref']:
        return
    entry['page'] = selection['result_ref']
    entry['svg'] = entry['svg_preview'] = entry['ppt_preview'] = None
    updated['outputs'] = {key: None for key in updated['outputs']}
    superseded = set(_superseded_tasks(store, document, {selection['page_id']}))
    for index, ref in enumerate(updated['tasks']):
        task = store.read_object_json(ref)
        if task['task_id'] in superseded:
            updated['tasks'][index] = store.put_json_object(
                {**task, 'status': 'superseded', 'updated_at': tasks._utc_now_iso()})
    refresh_plan_links(store, document, updated, operation_id)


def _apply_changeset_selection(store, document, updated, selection, task):
    """One changeset adoption: the local content_update application algorithm."""
    from .content import check_page
    from .content_plan import attach, bind_result
    from .content_ops import bind_derivation
    from .tasks import _utc_now_iso, page_limit_violation
    changeset = store.read_object_json(selection['result_ref'])
    violation = page_limit_violation({'pages': changeset['page_order']})
    if violation:
        raise operations.OperationError('candidate_invalid', 'result_ref/page_order', violation)
    upserts = {page['page_id']: check_page(page) for page in changeset.get('upsert_pages') or []}
    old_entries = {entry['page_id']: entry for entry in document.get('pages') or []}
    page_refs = {pid: store.put_json_object(page) for pid, page in upserts.items()}
    new_pages = []
    for pid in changeset['page_order']:
        old = old_entries.get(pid)
        if pid in page_refs:
            if old and old['page']['sha256'] == page_refs[pid]['sha256']:
                new_pages.append(dict(old))
                continue
            if old:
                new_pages.append({**old, 'page': page_refs[pid], 'svg': None, 'svg_preview': None, 'ppt_preview': None})
            else:
                new_pages.append({'page_id': pid, 'page': page_refs[pid], 'blueprint': None,
                                  'svg': None, 'svg_preview': None, 'ppt_preview': None})
        else:
            new_pages.append(dict(old))
    if [(e['page_id'], e['page']['sha256']) for e in document['pages']] != \
            [(e['page_id'], e['page']['sha256']) for e in new_pages]:
        updated['outputs'] = {key: None for key in updated['outputs']}
    updated['pages'] = new_pages
    updated['content_basis'] = {'input_digest': changeset['input_digest'],
                                'input_revision_id': task.get('input_revision_id'),
                                'resolved_by_task_id': task['task_id']}
    plan_input = store.read_object_json(selection['plan_input_ref']) if selection['plan_input_ref'] else None
    attach(updated, bind_result(store, document, task, plan_input, new_pages))
    bind_derivation(store, document, updated, task, page_refs)
    superseded = set(selection['superseded_tasks'])
    for index, ref in enumerate(updated['tasks']):
        stored = store.read_object_json(ref)
        if stored['task_id'] in superseded and stored['status'] in ('awaiting_host', 'running', 'blocked'):
            updated['tasks'][index] = store.put_json_object({**stored, 'status': 'superseded', 'updated_at': _utc_now_iso()})


@operations.public
def adopt(project, *, input, base_revision, operation_id):
    operations.validate_id(operation_id, new=True); validate_schema('candidate_adoption', input)
    store = Store(project_path(project))
    with store._locked():
        document = store.load_document()
        _require_workbench(document)
        digest = operations.request_digest(document, 'candidates.adopt', base_revision, input)
        previous = operations.recover(store, operation_id, digest)
        if previous:
            return previous
        if (base_revision != document['revision_id'] or input['base_revision'] != base_revision
                or input['project_id'] != document['project_id']):
            raise operations.OperationError('conflict', 'base_revision', 'adoption plan needs a new current basis; no candidates adopted', exit_code=5)
        ids = [item['candidate_id'] for item in input['selections']]
        current_plan = _plan(store, document, ids)
        if current_plan != input:
            raise operations.OperationError('adoption_target_changed', 'selections', 'planned target or payload changed; no candidates adopted', exit_code=5)
        for item in input['selections']:
            if item.get('result_kind', 'artifact') != 'artifact':
                continue
            artifact = store.read_object_json(item['result_ref']); validate_schema('artifact', artifact)
            if artifact['page_id'] != item['page_id'] or artifact['role'] != item['stage']:
                raise operations.OperationError('candidate_invalid', 'result_ref', 'candidate result identity differs')
            store.read_object_bytes(artifact['file'])
        records = _records(store, document)
        content = any(item.get('result_kind', 'artifact') != 'artifact' for item in input['selections'])
        updated = bump_revision(copy.deepcopy(document), {'operation_id': operation_id,
                                                           'kind': 'content_update' if content else 'artifact_adoption',
                                                           'description': 'explicit all-or-none candidate adoption', 'read_set': []})
        adoptions = list(document.get('candidate_adoptions', []))
        for item in input['selections']:
            candidate, ref, task = records[item['candidate_id']]
            kind = item.get('result_kind', 'artifact')
            if kind == 'page':
                _apply_page_selection(store, document, updated, item, operation_id)
                adoptions.append({key: item[key] for key in ('candidate_id', 'candidate_ref', 'page_id', 'stage')}
                                 | {'result_kind': 'page', 'result_ref': item['result_ref'],
                                    'revision_id': updated['revision_id']})
            elif kind == 'content_update':
                _apply_changeset_selection(store, document, updated, item, task)
                adoptions.append({key: item[key] for key in ('candidate_id', 'candidate_ref')}
                                 | {'result_kind': 'content_update', 'result_ref': item['result_ref'],
                                    'revision_id': updated['revision_id']})
            else:
                entry = next(e for e in updated['pages'] if e['page_id'] == item['page_id'])
                if entry[item['stage']] != item['result_ref']:
                    entry[item['stage']] = item['result_ref']
                    entry['svg_preview'] = entry['ppt_preview'] = None
                    updated['outputs'] = {key: None for key in updated['outputs']}
                    if item['stage'] == 'blueprint':
                        entry['svg'] = None
                adoptions.append({key: item[key] for key in ('candidate_id', 'candidate_ref', 'page_id', 'stage', 'result_ref')}
                                 | {'revision_id': updated['revision_id']})
        if updated['pages'] != document['pages'] or updated['outputs'] != document['outputs']:
            # Compute against the final batch state, not a partially applied
            # page. New refs and retired review tasks publish atomically.
            tasks._supersede_stale_reviews(store, updated)
        # Each selection invalidates outputs only when the deck actually
        # changed; a no-op adoption keeps exports usable
        updated['candidate_adoptions'] = adoptions
        require_writer(updated, CONTENT_WRITER if content else WRITER)
        icon_checks = {}
        for item in input['selections']:
            if records[item['candidate_id']][2].get('stage_request', {}).get('icon_recipe_ref'):
                from .candidate_preview import freeze_check
                icon_checks[item['candidate_id']] = freeze_check(store, item['candidate_id'])
                next(a for a in reversed(adoptions) if a['candidate_id']==item['candidate_id'])['icon_check_ref']=icon_checks[item['candidate_id']]
        result = {'icon_checks': icon_checks, 'status': 'adopted', 'revision_id': updated['revision_id'], 'candidate_ids': ids,
                  'result_refs': [item['result_ref'] for item in input['selections']], 'impact': input['selections'], 'max_calls': 0}
        return operations.commit_locked(store, document=updated, base_revision=base_revision,
                                         operation_id=operation_id, kind='candidates.adopt', digest=digest, result=result)


def _last_decision(store, document, candidate_id):
    """Latest decision record for one candidate; damaged refs fail loudly."""
    last = None
    for ref in document.get('candidate_decisions', []) or []:
        record = store.read_object_json(ref)
        validate_schema('candidate_decision', record)
        if record['candidate_id'] == candidate_id:
            last = (record, ref)
    return last


def _decision_state(store, document, candidate_id):
    last = _last_decision(store, document, candidate_id)
    return {'state': last[0]['decision'] if last else None,
            'decision_ref': last[1] if last else None,
            'decided_at': last[0]['decided_at'] if last else None}


class DecisionConflict(operations.OperationError):
    def __init__(self, candidate_id, current_ref):
        super().__init__('decision_conflict', 'expected_decision_ref',
                         'another decision was recorded for this candidate; re-read it and retry', exit_code=5)
        self.candidate_id = candidate_id
        self.current_ref = current_ref

    def payload(self):
        value = super().payload()
        # 完整 ref 对象与 show/listing 投影对称，客户端可直接回填 expected_decision_ref。
        value['error']['current_decision_ref'] = self.current_ref
        value['error']['candidate_id'] = self.candidate_id
        return value


@operations.public
def decide(project, *, input, base_revision, operation_id):
    """B04: persist one recoverable review decision (keep_current / reopen).

    The decision is a review activity record: it never moves the candidate,
    the current artifacts or the call ledger, and it lives in
    candidate_decisions, separate from candidate_adoptions, so a past
    adoption is never mistaken for the current one. Replaying the exact
    operation returns the original committed result.
    """
    operations.validate_id(operation_id, new=True)
    if not isinstance(input, dict):
        raise operations.OperationError('invalid_input', 'input', 'decision request must be an object')
    if input.get('schema_version') != 'candidate_decision.v1':
        raise operations.OperationError('invalid_input', 'input/schema_version',
                                        'decision requests use candidate_decision.v1')
    unknown = sorted(set(input) - {'schema_version', 'project_id', 'base_revision', 'candidate_id', 'decision', 'expected_decision_ref'})
    if unknown:
        raise operations.OperationError('invalid_input', 'input', 'unknown decision fields: ' + ', '.join(unknown))
    if input.get('decision') not in ('keep_current', 'reopen'):
        raise operations.OperationError('invalid_input', 'input/decision', 'decision is keep_current or reopen')
    expected = input.get('expected_decision_ref')
    if expected is not None and (not isinstance(expected, dict) or set(expected) != {'path', 'sha256'}
                                 or not isinstance(expected.get('sha256'), str)):
        raise operations.OperationError('invalid_input', 'input/expected_decision_ref',
                                        'expected_decision_ref is the current decision ref object, or null when undecided')
    store = Store(project_path(project))
    with store._locked():
        document = store.load_document()
        _require_workbench(document)
        digest = operations.request_digest(document, 'candidates.decide', base_revision, input)
        previous = operations.recover(store, operation_id, digest)
        if previous:
            return previous
        if (base_revision != document['revision_id'] or input.get('base_revision') != base_revision
                or input.get('project_id') != document['project_id']):
            raise operations.OperationError('conflict', 'base_revision',
                                            'decision needs a current basis; re-read the candidate and retry', exit_code=5)
        candidate_id = input.get('candidate_id')
        _candidate, ref, _task = _lookup(_records(store, document), candidate_id)
        if any(a.get('candidate_id') == candidate_id for a in document.get('candidate_adoptions', [])
               if isinstance(a, dict)):
            raise operations.OperationError('candidate_adopted', 'candidate_id',
                                            'this candidate is adopted; decisions apply to pending candidates', exit_code=5)
        last = _last_decision(store, document, candidate_id)
        current_sha = last[1]['sha256'] if last else None
        if (expected.get('sha256') if isinstance(expected, dict) else expected) != current_sha:
            raise DecisionConflict(candidate_id, last[1] if last else None)
        kept = bool(last) and last[0]['decision'] == 'keep_current'
        if (input['decision'] == 'keep_current') == kept:
            # 无变化、不写入：仍是确定终态。携带与请求一致的 operation 身份与
            # request_digest，让前端收据核对（含核实/重放路径）完整校验后清除，
            # 不落入只认提交收据的待核实循环（终审补丁 P1）。
            return {'status': 'unchanged', 'operation_id': operation_id,
                    'request_digest': digest,
                    'committed_revision_id': None, 'current_revision_id': document['revision_id'],
                    'candidate_id': candidate_id,
                    'decision': last[0]['decision'] if last else None,
                    'decision_ref': last[1] if last else None,
                    'revision_id': document['revision_id'], 'max_calls': 0}
        updated = bump_revision(copy.deepcopy(document), {'operation_id': operation_id, 'kind': 'review_update',
                                                          'description': f"candidate {input['decision']} recorded",
                                                          'read_set': []})
        record = {'schema_version': 'candidate_decision.v1', 'candidate_id': candidate_id, 'candidate_ref': ref,
                  'decision': input['decision'], 'decided_at': tasks._utc_now_iso(),
                  'revision_id': updated['revision_id']}
        validate_schema('candidate_decision', record)
        decision_ref = store.put_json_object(record)
        updated['candidate_decisions'] = [*document.get('candidate_decisions', []), decision_ref]
        require_writer(updated, WRITER)
        result = {'status': 'kept_current' if input['decision'] == 'keep_current' else 'reopened',
                  'candidate_id': candidate_id, 'decision': input['decision'],
                  'decision_ref': decision_ref, 'revision_id': updated['revision_id'], 'max_calls': 0}
        return operations.commit_locked(store, document=updated, base_revision=base_revision,
                                        operation_id=operation_id, kind='candidates.decide', digest=digest, result=result)
