"""Immutable trial results and all-or-none adoption on the existing Store."""
from __future__ import annotations

import copy
import uuid

from . import operations
from .local_state import project_path
from .models import (bump_revision, canonical_json_bytes, compute_input_digest,
                     sha256_bytes, validate_schema, validate_task_semantics)
from .snapshots import load_snapshot
from .store import Store

WRITER = 'candidates.v1'
CAPABILITY = 'candidate_result'


def is_trial(task):
    return task.get('stage_request', {}).get('mode') == 'trial'


def generation_basis(store, document, page_id, stage):
    from .production import resolve_design
    entry = next((e for e in document['pages'] if e['page_id'] == page_id), None)
    if entry is None:
        return None
    page = store.read_object_json(entry['page'])
    design, _ = resolve_design(page, document['design_context'], document['design_context'].get('assets') or [])
    return {'page_ref': entry['page'], 'input_digest': compute_input_digest(document),
            'design_digest': sha256_bytes(canonical_json_bytes(design)),
            'blueprint_ref': entry.get('blueprint') if stage == 'svg' else None}


def inputs_current(store, document, task):
    stage = 'blueprint' if task['kind'] == 'blueprint' else 'svg'
    dispatched = load_snapshot(store, task['dispatch_revision'])
    return all(generation_basis(store, document, pid, stage) == generation_basis(store, dispatched, pid, stage)
               and any(e['page_id'] == pid for e in document['pages']) for pid in task['scope_pages'])


def record_result(store, *, document, task, updated_task, artifacts, artifact_refs,
                  generation_binding, envelope, produced_against, result_digest):
    """Caller holds the same task-accept lock and has validated the real result."""
    from . import tasks
    if len(artifacts) != 1 or artifacts[0]['role'] not in ('blueprint', 'svg'):
        raise operations.OperationError('candidate_invalid', 'artifact_specs', 'a trial returns exactly one planned artifact')
    stage = artifacts[0]['role']; page_id = artifacts[0]['page_id']
    dispatched = load_snapshot(store, task['dispatch_revision'])
    entry = next(e for e in dispatched['pages'] if e['page_id'] == page_id)
    candidate = {'schema_version': 'candidate.v1', 'candidate_id': 'candidate-' + uuid.uuid4().hex,
                 'project_id': document['project_id'], 'task_id': task['task_id'],
                 'created_at': tasks._utc_now_iso(), 'page_id': page_id, 'stage': stage,
                 'base_revision': task['dispatch_revision'],
                 'generation_basis': generation_basis(store, dispatched, page_id, stage),
                 'request_ref': generation_binding['request_ref'] if generation_binding else None,
                 'attempt_ref': generation_binding['attempt_ref'] if generation_binding else None,
                 'target_ref': entry.get(stage), 'result_ref': artifact_refs[0], 'status': 'available'}
    validate_schema('candidate', candidate); candidate_ref = store.put_json_object(candidate)
    updated_task['candidate_refs'] = [candidate_ref]
    updated_task['result_refs'] = [*artifact_refs, candidate_ref]
    validate_task_semantics(updated_task)
    updated = bump_revision(document, {'operation_id': task['operation_id'], 'kind': 'task_update',
                                      'description': 'trial returned an immutable candidate; current artifacts unchanged', 'read_set': []})
    updated['compatibility'] = {'project_format': 'workbench.v3', 'minimum_writer': WRITER}
    updated['candidates'] = [*document.get('candidates', []), candidate_ref]
    tasks._replace_task_in_document(updated, task, store.put_json_object(updated_task), store)
    response = {'status': 'candidate_ready', 'revision_id': updated['revision_id'],
                'candidate_ids': [candidate['candidate_id']], 'candidate_refs': [candidate_ref],
                'result_refs': updated_task['result_refs'], 'next_action': 'compare_candidates',
                'current_artifacts_changed': False}
    return tasks._commit_adoption(store, document=updated, base_revision=document['revision_id'],
                                  task=task, envelope=envelope, produced_against=produced_against,
                                  result_digest=result_digest, response=response)


def _records(store, document):
    task_map = None; records = {}
    for ref in document.get('candidates', []):
        candidate = store.read_object_json(ref); validate_schema('candidate', candidate)
        if candidate['project_id'] != document['project_id'] or candidate['candidate_id'] in records:
            raise operations.OperationError('candidate_invalid', 'candidate', 'candidate identity differs from the committed project')
        if task_map is None:
            task_map = {t['task_id']: t for r in document['tasks'] if (t := store.read_object_json(r))}
        task = task_map.get(candidate['task_id'])
        if (not task or task['status'] != 'completed' or not is_trial(task)
                or candidate['base_revision'] != task['dispatch_revision']
                or task['scope_pages'] != [candidate['page_id']]
                or candidate['stage'] != ('blueprint' if task['kind'] == 'blueprint' else 'svg')
                or ref not in task.get('candidate_refs', [])
                or candidate['result_ref'] not in task.get('result_refs', [])):
            raise operations.OperationError('candidate_invalid', 'candidate/task_id', 'candidate is not a committed trial result')
        records[candidate['candidate_id']] = (candidate, ref, task)
    return records


def _lookup(records, candidate_id):
    if candidate_id not in records:
        raise operations.OperationError('candidate_not_found', 'candidate_id', 'candidate is not in this committed project version', http_status=404)
    return records[candidate_id]


def _state(store, document, candidate):
    basis = generation_basis(store, document, candidate['page_id'], candidate['stage'])
    changed = ['page_membership'] if basis is None else [key for key in basis if basis[key] != candidate['generation_basis'][key]]
    entry = next((e for e in document['pages'] if e['page_id'] == candidate['page_id']), None)
    target = entry.get(candidate['stage']) if entry else None
    adoptions = [r['revision_id'] for r in document.get('candidate_adoptions', []) if r['candidate_id'] == candidate['candidate_id']]
    return {'generation_basis': {'status': 'changed' if changed else 'current', 'changed_fields': changed},
            'adoption_target': {'status': 'missing_page' if entry is None else 'unchanged' if target == candidate['target_ref'] else 'changed',
                                'original_ref': candidate['target_ref'], 'current_ref': target},
            'adopted_revisions': adoptions, 'status': 'adopted' if adoptions else 'available'}


@operations.public
def show(project, *, candidate_id, revision=None):
    store = Store(project_path(project)); document = load_snapshot(store, revision)
    candidate, ref, task = _lookup(_records(store, document), candidate_id)
    artifact = store.read_object_json(candidate['result_ref']); validate_schema('artifact', artifact)
    if artifact['page_id'] != candidate['page_id'] or artifact['role'] != candidate['stage']:
        raise operations.OperationError('candidate_invalid', 'result_ref', 'result identity differs from the candidate')
    request = store.read_object_json(candidate['request_ref']) if candidate['request_ref'] else None
    attempt = store.read_object_json(candidate['attempt_ref']) if candidate['attempt_ref'] else None
    if candidate['stage'] == 'blueprint':
        validate_schema('generation_request', request); validate_schema('generation_attempt', attempt)
        if (candidate['request_ref'] not in task.get('generation_requests', [])
                or candidate['attempt_ref'] not in task.get('generation_attempts', [])
                or attempt['request_ref'] != candidate['request_ref']
                or request['task_id'] != task['task_id'] or attempt['task_id'] != task['task_id']
                or request['project_id'] != document['project_id'] or attempt['project_id'] != document['project_id']):
            raise operations.OperationError('candidate_invalid', 'request_ref', 'candidate request and attempt do not belong to its task')
    return {'project_id': document['project_id'], 'revision_id': document['revision_id'],
            'candidate_id': candidate_id, 'candidate_ref': ref, 'candidate': candidate, 'artifact': artifact,
            'request': request, 'attempt': attempt, 'references': task['stage_request']['references'],
            **_state(store, document, candidate)}


@operations.public
def listing(project, *, page_id=None, revision=None):
    store = Store(project_path(project)); document = load_snapshot(store, revision)
    return {'project_id': document['project_id'], 'revision_id': document['revision_id'], 'candidates': [
        {'candidate': candidate, 'ref': ref, **_state(store, document, candidate)}
        for candidate, ref, task in _records(store, document).values() if page_id is None or candidate['page_id'] == page_id]}


class AdoptionConflict(operations.OperationError):
    def __init__(self, failures):
        super().__init__('candidate_basis_changed', 'candidate_ids',
                         'no candidates were adopted; inspect conflicts and explicitly preview a new selection', exit_code=5)
        self.failures = failures

    def payload(self):
        value = super().payload(); value['error']['items'] = self.failures
        return value


def _plan(store, document, candidate_ids):
    records = _records(store, document); selections = []; failures = []; pages = set()
    for cid in candidate_ids:
        candidate, ref, _ = _lookup(records, cid)
        state = _state(store, document, candidate)
        if state['generation_basis']['status'] != 'current':
            failures.append({'candidate_id': cid, 'page_id': candidate['page_id'],
                             'cause': 'generation_basis_changed', 'fields': state['generation_basis']['changed_fields']})
            continue
        if candidate['page_id'] in pages:
            failures.append({'candidate_id': cid, 'page_id': candidate['page_id'], 'cause': 'one_candidate_per_page'})
            continue
        pages.add(candidate['page_id'])
        downstream = ['svg_preview', 'ppt_preview', 'deck_outputs', 'quality_applicability']
        if candidate['stage'] == 'blueprint':
            downstream.insert(0, 'svg')
        selections.append({'candidate_id': cid, 'candidate_ref': ref, 'page_id': candidate['page_id'],
                           'stage': candidate['stage'], 'target_ref': state['adoption_target']['current_ref'],
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
    if input['project_id'] != document['project_id'] or input['base_revision'] != document['revision_id']:
        raise operations.OperationError('conflict', 'base_revision', 'read current state and preview adoption again', exit_code=5)
    value = _plan(store, document, input['candidate_ids']); ref = store.put_json_object(value)
    return {'status': 'planned', 'plan_id': 'adopt-plan-' + ref['sha256'], 'plan_ref': ref, 'plan': value}


@operations.public
def adopt(project, *, input, base_revision, operation_id):
    operations.validate_id(operation_id, new=True); validate_schema('candidate_adoption', input)
    store = Store(project_path(project))
    with store._locked():
        document = store.load_document()
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
            artifact = store.read_object_json(item['result_ref']); validate_schema('artifact', artifact)
            if artifact['page_id'] != item['page_id'] or artifact['role'] != item['stage']:
                raise operations.OperationError('candidate_invalid', 'result_ref', 'candidate result identity differs')
            store.read_object_bytes(artifact['file'])
        updated = bump_revision(copy.deepcopy(document), {'operation_id': operation_id, 'kind': 'artifact_adoption',
                                                           'description': 'explicit all-or-none candidate adoption', 'read_set': []})
        adoptions = list(document.get('candidate_adoptions', []))
        entries = {e['page_id']: e for e in updated['pages']}
        for item in input['selections']:
            entry = entries[item['page_id']]; entry[item['stage']] = item['result_ref']
            entry['svg_preview'] = entry['ppt_preview'] = None
            if item['stage'] == 'blueprint':
                entry['svg'] = None
            adoptions.append({key: item[key] for key in ('candidate_id', 'candidate_ref', 'page_id', 'stage', 'result_ref')} | {'revision_id': updated['revision_id']})
        updated['outputs'] = {key: None for key in updated['outputs']}
        updated['candidate_adoptions'] = adoptions
        updated['compatibility'] = {'project_format': 'workbench.v3', 'minimum_writer': WRITER}
        result = {'status': 'adopted', 'revision_id': updated['revision_id'], 'candidate_ids': ids,
                  'result_refs': [item['result_ref'] for item in input['selections']], 'impact': input['selections'], 'max_calls': 0}
        return operations.commit_locked(store, document=updated, base_revision=base_revision,
                                         operation_id=operation_id, kind='candidates.adopt', digest=digest, result=result)
