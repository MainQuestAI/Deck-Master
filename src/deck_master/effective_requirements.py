"""Read current editorial requirements from the existing collaboration ledger.

This is a scoped read projection, not a second instruction store or authority
source. Decision effectiveness and immutable evidence stay owned by Runtime.
"""
from __future__ import annotations

import json

from . import dependency_slices
from .store import StoreError

UNIT_LAYERS = {
    'argument': {'narrative', 'plan', 'page_copy', 'review'},
    'page_copy': {'narrative', 'plan', 'page_copy', 'review'},
    'progression': {'narrative', 'plan', 'page_copy', 'review'},
    'speech': {'narrative', 'plan', 'page_copy', 'speech', 'review'},
}
CONTENT_TOPICS = {'direction', 'manuscript', 'tradeoff'}


def _evidence(store, evidence):
    """Expand the real fixed instruction source, without asserting its truth."""
    result = dict(evidence or {})
    for key in ('source_ref', 'presentation_ref'):
        ref = result.get(key)
        if not ref:
            continue
        raw = store.read_object_bytes(ref)
        try:
            text = raw.decode('utf-8')
        except UnicodeError:
            # Binary source remains inspectable through its exact Ref; never
            # invent prose from bytes the text reader cannot interpret.
            result[key.removesuffix('_ref') + '_content'] = {'status': 'binary_read_required', 'ref': ref}
            continue
        try:
            body = json.loads(text)
        except ValueError:
            body = text
        result[key.removesuffix('_ref') + '_content'] = body
    return result


def project_requirements(store, document, *, page_ids, unit):
    """Only requirements applicable to this editorial unit and selected pages.

    A deck planning decision may describe manuscript-wide constraints before
    pages exist; reading it is never interpreted as wildcard page authority.
    A pages scope with no members remains empty, and visual/delivery-only
    decisions do not become content review requirements.
    """
    from .eligibility import scope_page_ids
    if unit not in UNIT_LAYERS:
        raise ValueError('unknown content review unit')
    region = document.get('collaboration') or {}
    request = region.get('request') or {}
    ids = set(page_ids)
    request_view = {key: request.get(key) for key in ('request_id', 'intent', 'content_intent', 'scope', 'closed')}
    request_view['instruction_evidence'] = _evidence(store, request.get('instruction_evidence'))
    decisions = []
    for ref in region.get('decisions') or []:
        record = store.read_object_json(ref)
        if record.get('status') != 'active' or record.get('disposition') != 'accepted':
            continue
        topic = record.get('topic')
        if topic not in CONTENT_TOPICS | ({'speech'} if unit == 'speech' else set()) | {'policy'}:
            continue
        # Only the existing explicit content-review policy is an editorial
        # policy; e.g. call budget policies belong to execution, not copy.
        if topic == 'policy' and not (isinstance(record.get('value'), dict)
                and 'content_review_requirement' in record['value']):
            continue
        scope = record.get('scope') or {}
        if not set(scope.get('layers') or []) & UNIT_LAYERS[unit]:
            continue
        selected = scope_page_ids(store, scope)
        if selected is not None and not ids.intersection(selected):
            continue
        if record.get('request_id') != request.get('request_id'):
            continue
        if not dependency_slices.accepted_decision(store, document, ref):
            continue
        decisions.append({'ref': ref, 'decision': record,
                          'instruction_evidence': _evidence(store, record.get('evidence'))})
    decisions.sort(key=lambda item: (item['decision']['decision_id'], item['ref']['sha256']))
    return {'request': request_view,
            'task_facts': {key: document.get('task', {}).get(key) for key in
                           ('audience', 'brief', 'scenario', 'presentation_mode')},
            'review_scope': {'page_ids': sorted(ids), 'unit': unit},
            'decisions': decisions,
            'interpretation': 'Effective requirements only; reading does not grant production or assert user acceptance.'}


def outline_page_ids(store, document):
    """Requirement coverage of a validated Plan, never Page review subjects."""
    from .outline_review import require_outline
    require_outline(store, document)
    return list(store.read_object_json(document['content_plan'])['input']['page_order'])


def packet_requirements(store, document, *, page_ids, units):
    return {unit: project_requirements(store, document, page_ids=page_ids, unit=unit) for unit in units}


def _semantic_requirements(value):
    """Ignore audit identity only for the same effective review-policy choice.

    Packets/readers retain complete refs, replacement chains and instruction
    evidence. Applicability still resolves the current accepted record first;
    scope, value, authority, evidence, expiry and dependency basis stay compared.
    """
    rows = []
    for row in value['decisions']:
        decision = row['decision']
        if decision.get('topic') == 'policy' and 'content_review_requirement' in (decision.get('value') or {}):
            row = {key: item for key, item in row.items() if key != 'ref'}
            row['decision'] = {key: item for key, item in decision.items() if key not in ('replaces', 'created_at')}
        rows.append(row)
    return {**value, 'decisions': rows}


def task_requirements_current(store, document, task, *, unit=None, page_ids=None):
    """Compare scoped semantic requirements, never the whole Document revision.

    Historical Tasks without the new packet field derive the same projection
    from their actual immutable dispatch snapshot; no old object is rewritten.
    """
    from .snapshots import load_snapshot
    if task.get('review_subject') == 'outline':
        before = load_snapshot(store, task['dispatch_revision'])
        prior_ids = outline_page_ids(store, before)
        current_ids = outline_page_ids(store, document)
        kinds = [unit] if unit else [row['kind'] for row in task.get('review_units') or []]
        prior = packet_requirements(store, before, page_ids=prior_ids, units=kinds)
        for ref in task.get('inputs') or []:
            if not ref.get('path', '').endswith('.json'):
                continue
            packet = store.read_object_json(ref)
            if not isinstance(packet, dict) or packet.get('schema_version') != 'content_review_packet.v1':
                continue
            frozen = packet.get('effective_requirements')
            if frozen:
                for kind in kinds:
                    supplied = frozen.get(kind)
                    # Old empty-page packets may have omitted accepted Plan
                    # requirements. Do not retroactively pretend they were read.
                    if supplied is None:
                        return False
                    supplied = {**supplied, 'review_scope': prior[kind]['review_scope']}
                    if _semantic_requirements(supplied) != _semantic_requirements(prior[kind]):
                        return False
        return all(_semantic_requirements(prior[kind]) ==
                   _semantic_requirements(project_requirements(store, document, page_ids=current_ids, unit=kind))
                   for kind in kinds)
    ids = list(task.get('scope_pages') or []) if page_ids is None else list(page_ids)
    units = [unit] if unit else sorted({row['kind'] for row in task.get('review_units') or []} or UNIT_LAYERS)
    from .eligibility import scope_page_ids
    frozen = None
    for ref in task.get('inputs') or []:
        if not ref.get('path', '').endswith('.json'):
            continue
        candidate = store.read_object_json(ref)
        if isinstance(candidate, dict) and candidate.get('schema_version') == 'content_review_packet.v1':
            frozen = candidate.get('effective_requirements')
            if frozen:
                break
    before = None if frozen else load_snapshot(store, task['dispatch_revision'])
    for kind in units:
        if frozen and kind in frozen:
            prior = dict(frozen[kind])
            prior['review_scope'] = {'page_ids': sorted(ids), 'unit': kind}
            prior['decisions'] = [row for row in prior['decisions']
                                  if (selected := scope_page_ids(store, row['decision']['scope'])) is None
                                  or set(ids).intersection(selected)]
        else:
            if before is None:
                before = load_snapshot(store, task['dispatch_revision'])
            prior = project_requirements(store, before, page_ids=ids, unit=kind)
        if _semantic_requirements(prior) != _semantic_requirements(
                project_requirements(store, document, page_ids=ids, unit=kind)):
            return False
    return True


def review_task_owners(store, document):
    owners = {}
    for ref in document.get('tasks') or []:
        task = store.read_object_json(ref)
        if task.get('kind') == 'review' and task.get('review_stage') == 'preproduction' and task.get('status') == 'completed':
            for result in task.get('result_refs') or []:
                owners.setdefault(result['sha256'], []).append(task)
    return owners


def accepted_requirements_current(store, document, review, ref, owners):
    """Use actual acceptance provenance to recheck this unit's requirements."""
    tasks = owners.get(ref['sha256']) or []
    ids = [dep['identity'].split(':', 1)[1] for dep in review.get('dependencies') or []
           if dep.get('kind') == 'content' and dep.get('identity', '').startswith('page:')]
    try:
        if not tasks:
            # External/human imports have no Task. Compare against their first
            # committed introduction, without inventing execution provenance.
            from .snapshots import committed_snapshots
            introduced = None
            for snapshot in committed_snapshots(store):
                if any(row['sha256'] == ref['sha256'] for row in snapshot.get('reviews') or []):
                    introduced = snapshot
                elif introduced is not None:
                    break
            if introduced is not None and review.get('review_subject') == 'outline':
                return _semantic_requirements(project_requirements(store, introduced,
                    page_ids=outline_page_ids(store, introduced), unit=review['kind'])) == _semantic_requirements(
                    project_requirements(store, document, page_ids=outline_page_ids(store, document), unit=review['kind']))
            return introduced is not None and _semantic_requirements(project_requirements(
                store, introduced, page_ids=ids, unit=review['kind'])) == _semantic_requirements(project_requirements(
                store, document, page_ids=ids, unit=review['kind']))
        return any(task_requirements_current(store, document, task, unit=review['kind'], page_ids=ids) for task in tasks)
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        return False


def reader_requirements(store, document, *, task=None):
    """Shared read-only author/reader view, bounded to an actual Task if supplied."""
    ids = task.get('scope_pages', []) if task else [row['page_id'] for row in document.get('pages') or []]
    units = [row['kind'] for row in task.get('review_units') or [] if row['kind'] in UNIT_LAYERS] if task else []
    if (task and task.get('review_subject') == 'outline') or (not task and not ids and document.get('content_plan')):
        ids = outline_page_ids(store, document)
        units = units or ['argument', 'progression']
    return packet_requirements(store, document, page_ids=ids, units=units or list(UNIT_LAYERS))
