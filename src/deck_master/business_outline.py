"""Bounded author edits and paired outline admission over existing transactions.

No model executor or alternate adoption state. Edits produce an ordinary local
compose Task and an immutable Narrative/Plan proposal; adoption still uses the
existing request, direction decision and ordered proposal operations.
"""
from __future__ import annotations

import copy
import re

from . import business_framing, collaboration, content_production, dependency_slices, eligibility, models, service, tasks
from .store import Store, ConflictError
from .snapshots import READ_FAILURES


def scope_for(request):
    return {**copy.deepcopy(request.get('scope') or {}), 'subject': 'deck', 'page_ids': [],
            'page_manifest_ref': None, 'external_artifact_ref': None, 'layers': ['narrative', 'plan'],
            'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'working'}


def admission(store, document, ref, narrative, plans):
    if narrative.get('schema_version') != business_framing.VERSION:
        return None
    current = store.load_document()
    request = (current.get('collaboration') or {}).get('request') or {}
    scope = scope_for(request)
    result = {'narrative_ref': ref, 'plan_ref': None, 'subject_refs': [], 'write_scope': scope,
              'assessed_control_revision': current['revision_id'], 'basis': [], 'reason_codes': [],
              'can_start_followup': False, 'can_record_direction_decision': False, 'can_adopt': False,
              'author_revision': False, 'can_revise': False, 'is_adopted': False, 'next_ref': None, 'existing_decision_ref': None}
    choices = [p for p in plans if p.get('readable') and p['data']['mode'] == 'planned']
    produced = set()
    for task_ref in document['tasks']:
        task = store.read_object_json(task_ref)
        if ref in task.get('result_refs', []):
            produced.update(r['sha256'] for r in task['result_refs'][1:])
            result['author_revision'] = task.get('cost_class') == 'local_compute' and task.get('instruction', '').startswith('作者修正固定策划；不调用模型。')
    preferred = [p for p in choices if p['ref'] == current.get('content_plan')] if ref == current.get('narrative') else []
    preferred = preferred or [p for p in choices if p['ref']['sha256'] in produced] or choices
    if len(preferred) != 1:
        result['reason_codes'] = ['matching_planned_outline_required']
        return result
    plan_ref = preferred[0]['ref']
    result.update(plan_ref=plan_ref, subject_refs=[
        {'artifact_kind': 'narrative', 'artifact_ref': ref, 'projection': 'direction'},
        {'artifact_kind': 'content_plan', 'artifact_ref': plan_ref, 'projection': 'page_roles'}])
    if document['revision_id'] != current['revision_id']:
        result['reason_codes'] = ['historical_revision']
        return result
    if current['pages'] or narrative.get('maturity') != 'argument':
        result['reason_codes'] = ['zero_page_argument_required']
        return result
    if request.get('intent') not in ('full_deck', 'content_only') or request.get('content_intent') in ('write_only', 'speech_only'):
        result['reason_codes'] = ['fixed_request_scope']
        return result
    if (current.get('collaboration') or {}).get('authority_policy') == 'verified_user':
        result['reason_codes'] = ['authority_channel_unavailable']
        return result
    try:
        result['basis'] = dependency_slices.merge_required_basis(store, current, family='decision', key='direction', provided=[])
        business_framing.validate_adoption_basis(store, current, narrative, {'basis': result['basis']})
    except READ_FAILURES as exc:
        result['reason_codes'] = [getattr(exc, 'error_code', 'outline_basis_changed')]
        return result
    result['can_revise'] = True
    result['is_adopted'] = current.get('narrative') == ref and current.get('content_plan') == plan_ref
    if request.get('closed'):
        result['can_start_followup'] = not result['is_adopted']
        return result
    result['can_revise'] = eligibility.evaluate(store, current, current, 'dispatch.compose', context={'targets':
        content_production.phase_dispatch_targets(current, phase='argument')})['allowed']
    source = request.get('instruction_evidence') or {}
    declared = {'kind': 'host_attested_instruction', 'source_ref': source.get('source_ref'),
                'source_locator': source.get('source_locator')}
    payload = {'topic': 'direction', 'authority_mode': 'direct_user', 'subject_refs': result['subject_refs'],
               'scope': scope, 'basis': result['basis'], 'value': {'selected': ref['sha256']},
               'disposition': 'accepted', 'instruction_evidence': declared}
    try:
        evidence = collaboration.resolve_evidence(declared)
        collaboration.prepare_decision(store, current, input=payload, operation_id='outline-pair-preflight', evidence=evidence)
        result['can_record_direction_decision'] = not result['is_adopted']
    except READ_FAILURES as exc:
        result['reason_codes'] = [getattr(exc, 'error_code', 'direction_not_allowed')]
    target = plan_ref if current.get('narrative') == ref else ref
    for decision_ref in (current.get('collaboration') or {}).get('decisions', []):
        decision = store.read_object_json(decision_ref)
        if not all(subject in decision.get('subject_refs', []) for subject in result['subject_refs']):
            continue
        try:
            content_production.check_proposal_adoption(store, current, input={
                'proposal_ref': target, 'decision_ref': decision_ref, 'write_scope': scope})
        except READ_FAILURES:
            continue
        result.update(can_adopt=not result['is_adopted'], next_ref=target,
                      existing_decision_ref=decision_ref, reason_codes=[])
        break
    return result


def _source_pair(store, document, value):
    from .content_insight import objects
    known = {r['sha256'] for r, _, _ in objects(store, document)[0]}
    for key in ('narrative_ref', 'plan_ref'):
        models.validate_ref(value[key], where=key)
        if value[key]['sha256'] not in known:
            raise models.ModelError(key, 'choose a reachable fixed outline')
    narrative = store.read_object_json(value['narrative_ref'])
    plan = store.read_object_json(value['plan_ref'])
    models.validate_narrative_semantics(narrative)
    models.validate_content_plan_semantics(plan)
    if (narrative.get('schema_version') != business_framing.VERSION or narrative.get('maturity') != 'argument'
            or plan.get('narrative_ref') != value['narrative_ref'] or plan.get('mode') != 'planned'
            or any(obj.get('project_id') != document['project_id'] for obj in (narrative, plan))):
        raise models.ModelError('outline', 'choose one matching v2 Narrative and planned Plan')
    return copy.deepcopy(narrative), copy.deepcopy(plan)


def _edit(rows, edits, identity, allowed, *, node_authority=False):
    if not isinstance(edits, list) or len(edits) > 100:
        raise models.ModelError('edits', 'provide a bounded list of edits')
    known = {r[identity]: r for r in rows}
    seen = set()
    for edit in edits:
        if (not isinstance(edit, dict) or identity not in edit or not set(edit) <= {identity, *allowed}
                or len(edit) == 1 or not isinstance(edit[identity], str) or edit[identity] in seen
                or edit[identity] not in known):
            raise models.ModelError('edits', 'edit each existing identity once using supported fields')
        row = known[edit[identity]]
        if node_authority and row['authority'] not in ('inference', 'hypothesis', 'recommendation'):
            raise models.ModelError('edits', 'source facts and instructions must be changed through task inputs')
        seen.add(edit[identity])
        for key, text in edit.items():
            if key == identity:
                continue
            if not isinstance(text, str) or not text.strip():
                raise models.ModelError('edits', 'edited text must be nonempty')
            row[key] = text


def revise(project, value):
    fields = {'project_id', 'base_revision', 'operation_id', 'narrative_ref', 'plan_ref',
              'reason', 'topic_edits', 'node_edits', 'page_edits'}
    if not isinstance(value, dict) or set(value) != fields:
        raise models.ModelError('outline_revision', 'provide exact fixed refs, base, reason and bounded edits')
    if any(not isinstance(value[k], str) or not value[k].strip() for k in ('project_id', 'base_revision', 'operation_id', 'reason')):
        raise models.ModelError('outline_revision', 'identity, revision and reason must be nonempty')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', value['operation_id']):
        raise models.ModelError('operation_id', 'invalid operation identity')
    store = Store(project)
    document = store.load_document()
    if document['project_id'] != value['project_id']:
        raise models.ModelError('project_id', 'request belongs to another project')
    fingerprint = models.sha256_bytes(models.canonical_json_bytes(value))
    instruction = '作者修正固定策划；不调用模型。输入指纹：' + fingerprint
    def owns(task):
        return (task['instruction'].startswith(instruction) and task['cost_class'] == 'local_compute'
                and all(ref in task['inputs'] for ref in (value['narrative_ref'], value['plan_ref'])))
    existing = next((task for ref in document['tasks']
                     if (task := store.read_object_json(ref))['operation_id'] == value['operation_id']), None)
    if existing and not owns(existing):
        raise ConflictError('operation_id', 'retain the original operation payload; changed edits need a new operation')
    request = (document.get('collaboration') or {}).get('request') or {}
    own_key = 'studio:outline-revision:' + value['operation_id']
    own_request = (request.get('instruction_evidence') or {}).get('source_locator') == own_key
    if not existing and not own_request and document['revision_id'] != value['base_revision']:
        raise ConflictError('base_revision', 'outline changed; draft retained, reload before a new operation')
    narrative, plan = _source_pair(store, document, value)
    if (not existing or existing['status'] != 'completed') and (
            document['pages'] or request.get('intent') not in ('full_deck', 'content_only')
            or request.get('content_intent') in ('write_only', 'speech_only')):
        raise models.ModelError('outline_revision', 'this editor is for zero-page planning; preserve the current bounded work')
    before = models.canonical_json_bytes([narrative, plan])
    _edit(narrative['business_frame']['topics'], value['topic_edits'], 'topic_id', {'name', 'meaning'})
    _edit(narrative['nodes'], value['node_edits'], 'node_id', {'statement'}, node_authority=True)
    _edit(plan['input']['page_roles'], value['page_edits'], 'page_id', {'role', 'audience_question', 'intended_takeaway'})
    if models.canonical_json_bytes([narrative, plan]) == before:
        raise models.ModelError('edits', 'no content changed')
    models.validate_narrative_semantics(narrative)
    models.validate_content_plan_semantics(plan)
    if not existing:
        basis = dependency_slices.merge_required_basis(store, document, family='decision', key='direction', provided=[])
        business_framing.validate_adoption_basis(store, document, narrative, {'basis': basis})
        reason_ref = store.put_blob((value['reason'] + '\n修订输入指纹：' + fingerprint).encode('utf-8'), ext='txt')
        dispatch_revision = document['revision_id']
        if request.get('closed') or own_request:
            evidence = {'kind': 'host_attested_instruction',
                        'source_ref': reason_ref,
                        'source_locator': own_key}
            started = collaboration.start_request(project, input={'intent': 'content_only', 'content_intent': 'plan_only',
                'scope': scope_for(request), 'instruction_evidence': evidence},
                base_revision=document['revision_id'], operation_id=value['operation_id'] + '-request')
            dispatch_revision = started['revision_id']

        @tasks._project_transaction
        def dispatch(store):
            current = store.load_document()
            # A duplicate POST can arrive after request.start but before dispatch.
            duplicate = next((task for ref in current['tasks']
                if (task := store.read_object_json(ref))['operation_id'] == value['operation_id']), None)
            if duplicate:
                if not owns(duplicate):
                    raise ConflictError('operation_id', 'operation payload changed')
                return duplicate
            if current['revision_id'] != dispatch_revision:
                raise ConflictError('base_revision', 'request changed; preserve the original revision operation')
            eligibility.guard(store, current, 'dispatch.compose', context={'targets':
                content_production.phase_dispatch_targets(current, phase='argument')})
            task = content_production.build_phase_task(store, current, operation_id=value['operation_id'],
                phase='argument', instruction=instruction, business_framing=True)
            task['cost_class'] = 'local_compute'
            task['inputs'] = list(dict((r['sha256'], r) for r in [*task['inputs'], value['narrative_ref'], value['plan_ref'], reason_ref]).values())
            models.validate_task_semantics(task)
            updated = models.bump_revision(current, {'operation_id': value['operation_id'] + '-dispatch',
                'kind': 'task_update', 'description': 'author outline revision; local compute', 'read_set': []})
            updated['tasks'].append(store.put_json_object(task))
            store._commit_locked(base_revision=current['revision_id'], document=updated,
                                 operation_id=updated['change']['operation_id'], blobs=[])
            return task
        existing = dispatch(store)
    if existing['status'] in ('cancelled', 'failed', 'superseded'):
        raise tasks.TaskConflict('outline_revision', 'original local task is settled; preserve it before a new edit')
    execution = 'studio:author-outline:' + value['operation_id']
    if existing['status'] == 'awaiting_host':
        service.task_start(project, task_id=existing['task_id'], execution_ref=execution,
            supported_protocols=['compose.v2'], capabilities=existing['required_capabilities'])
    elif existing['status'] == 'running' and existing.get('execution_ref') != execution:
        raise tasks.TaskConflict('outline_revision', 'original execution belongs to another actor')
    narrative.update(version=narrative['version'] + 1, previous_ref=value['narrative_ref'],
                     input_basis=existing['collaboration_binding']['eligibility_basis'], method_applications=[])
    plan.update(version=plan['version'] + 1, previous_ref=value['plan_ref'], narrative_ref=None,
                task_id=existing['task_id'], basis={'revision_id': existing['dispatch_revision'], 'input_digest': existing['input_digest']})
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'narrative',
                'task_id': existing['task_id'], 'operation_id': existing['operation_id'],
                'produced_against': existing['produced_against'],
                'eligibility_digest': existing['collaboration_binding']['eligibility_digest'],
                'payload': {'narrative': narrative, 'plan': plan}, 'usage_events': []}
    result = service.accept_result(project, task_id=existing['task_id'], operation_id=existing['operation_id'],
        produced_against=existing['produced_against'], result_payload=envelope)
    return {**result, 'model_called': False, 'author_revision': True, 'source_refs': [value['narrative_ref'], value['plan_ref']]}
