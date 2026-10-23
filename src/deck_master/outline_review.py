"""Outline review uses the existing preproduction identity and finding contract.

Explicit subject + valid nonempty Narrative/Plan + exactly argument/progression
is the only empty-page exception. It never grants manuscript or visual approval.
"""
from . import content_review, models
from .store import Store

UNITS = ('argument', 'progression')
CAPABILITY = 'outline_review.v1'


def require_outline(store, document):
    refs = [document.get(key) for key in ('narrative', 'content_plan')]
    if not all(refs):
        raise models.ModelError('review/outline', 'outline requires current Narrative and ContentPlan refs')
    narrative, plan = [store.read_object_json(ref) for ref in refs]
    models.validate_narrative_semantics(narrative)
    models.validate_content_plan_semantics(plan)
    if (not narrative.get('nodes') or not plan.get('input', {}).get('page_order')
            or plan.get('narrative_ref') != refs[0]
            or any(value.get('project_id') != document['project_id'] for value in (narrative, plan))):
        raise models.ModelError('review/outline', 'outline requires nonempty, project-bound Narrative/Plan versions')
    return refs


def records(store, document):
    return [row for row in content_review._preproduction_reviews(store, document)
            if row['review'].get('review_subject') == 'outline']


def review_targets(store, document):
    """The whole frozen outline is a deck subject, never an empty-page grant."""
    require_outline(store, document)
    plan = store.read_object_json(document['content_plan'])
    return {'subject': 'deck', 'page_ids': list(plan['input']['page_order']), 'layers': ['review']}


def status(store, document):
    require_outline(store, document)
    from .editing import _current_artifact_digests
    from .review import finding_closed, open_findings, pending_judgments
    history = records(store, document)
    artifacts = _current_artifact_digests(store, document)
    applicable = content_review._applicable_reviews(store, document, [], records=history, digests=artifacts)
    satisfied = sorted({row['review']['kind'] for row in applicable if row['review']['status'] == 'pass'})
    all_records = [{**row['review'], 'ref': row['review_ref']} for row in history]
    blocking = []
    for row in all_records:
        for finding in open_findings(row) + pending_judgments(row):
            if not finding_closed(all_records, row, finding, artifacts):
                blocking.append({'review_ref': row['ref'], 'review_id': row['review_id'],
                    'kind': row['kind'], 'finding_id': finding.get('finding_id'),
                    'message': finding.get('message'), 'impact': finding.get('impact')})
    missing = sorted(set(UNITS) - set(satisfied))
    return {'review_subject': 'outline', 'stage': content_review.STAGE,
            'status': 'blocked' if blocking else 'missing' if missing else 'pass',
            'units': list(UNITS), 'satisfied_units': satisfied, 'missing_units': missing,
            'blocking_findings': blocking, 'review_refs': [row['review_ref'] for row in applicable],
            'production_qualified': False}


def packet(store, document, units=None):
    refs = require_outline(store, document)
    units = list(UNITS if units is None else units)
    if not units or not set(units) <= set(UNITS) or len(units) != len(set(units)):
        raise models.ModelError('review/outline/units', 'outline permits argument/progression only')
    value = content_review.build_review_packet(store, document, page_ids=[], required=units,
        requirement=content_review.requirement_state(store, document)['effective'])
    history = records(store, document)
    replaced = {row['review']['replaces']['sha256'] for row in history if row['review'].get('replaces')}
    gate = status(store, document)
    open_refs = {row['review_ref']['sha256'] for row in gate['blocking_findings']}
    owners = [{'kind': row['review']['kind'], 'review_ref': row['review_ref'],
               'review_id': row['review']['review_id']} for row in history
              if row['review']['kind'] in units and
              (row['review_ref']['sha256'] not in replaced or row['review_ref']['sha256'] in open_refs)]
    value.update(review_subject='outline', subjects=refs,
        review_scope={'units': units, 'owners': owners},
        instruction='Review the fixed Narrative and ContentPlan argument and progression. '
            'Do not evaluate page copy, speech or visual production. Preserve each finding owner and replaces chain.')
    return value


def dispatch(project, *, adapter_context=None, force_units=None):
    from . import service, eligibility
    store = Store(project)
    document = store.load_document()
    gate = status(store, document)
    forced = force_units or []
    if not set(forced) <= set(UNITS) or len(forced) != len(set(forced)):
        raise models.ModelError('review/outline/units', 'outline permits distinct argument/progression only')
    units = sorted(set(gate['missing_units']) | {row['kind'] for row in gate['blocking_findings']} | set(forced))
    if not units:
        return {'status': 'already_reviewed', 'outline': gate}
    eligibility.guard(store, document, 'dispatch.host_task',
        context={'targets': review_targets(store, document)})
    from .native_review import recovery_task_ids
    recoverable = recovery_task_ids(store, document, subject='outline')
    if recoverable:
        return {'status': 'recovery_available', 'task_ids': recoverable, 'outline': gate,
                'next_action': 'recover the original operation before creating or executing another review'}
    from .tasks import task_inputs_current
    pending = [task for ref in document.get('tasks', [])
               if (task := store.read_object_json(ref)).get('review_subject') == 'outline'
               and task.get('status') in ('running', 'awaiting_host', 'queued')]
    for task in pending:
        if (task_inputs_current(store, document, task)
                and {row['kind'] for row in task.get('review_units', [])} == set(units)):
            return {'status': 'review_dispatched', 'task': task, 'outline': gate, 'reused': True}
    if pending:
        return {'status': 'awaiting_recovery', 'task_ids': [task['task_id'] for task in pending],
                'outline': gate, 'next_action': 'query original execution and operation; retire stale task before reissue'}
    value = packet(store, document, units)
    available = content_review.reviewer_capabilities(adapter_context)
    independent = value['requirement'] == 'independent_model_or_human'
    if independent and not (available['independent_review_receipts'] or available['human_review_receipts']):
        return {'status': 'needs_reviewer', 'review_draft': value, 'outline': gate,
                'reason': 'independent channel unavailable; readable outline retained; no model execution'}
    task = service.open_host_task(store, kind='review', page_ids=[],
        review_stage='preproduction', review_subject='outline',
        instruction=value['instruction'], extra_inputs=[store.put_json_object(value)],
        executor_type='external_reviewer' if independent else 'host',
        review_units=[{'kind': unit, 'page_ids': [], 'reason': 'missing'} for unit in units],
        phase='review', base_revision=document['revision_id'])
    return {'status': 'review_dispatched', 'task': task, 'outline': gate}
