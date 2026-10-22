"""Read-only completion of a bounded, zero-call design planning request.

An unconfirmed proposal is an output of propose(), not committed project state.
Only a recipe reachable in this request's history can complete later readback.
Neither observation is an adoption or permission to produce images.
"""
from . import dependency_slices
from .snapshots import load_snapshot
from .store import StoreError


def planning_only(store, document):
    region = document.get('collaboration') or {}
    request = region.get('request') or {}
    if request.get('intent') != 'design_trial' or set(request.get('scope', {}).get('layers') or []) != {'design'}:
        return False
    grants = [store.read_object_json(ref) for ref in region.get('authorizations') or []]
    grants = [grant for grant in grants if grant.get('request_id') == request.get('request_id')]
    # Read the request's declared bounds, not today's remaining budget. A spent
    # or revoked production allowance must never turn a sample request into a plan.
    return bool(grants) and all(
        set(grant.get('actions') or []) <= {'design.feasibility', 'design.propose'}
        and grant.get('max_external_calls') == 0 and grant.get('max_candidate_count') == 0
        for grant in grants)


def completion_status(store, document, *, proposal=None, proposal_ref=None):
    request = (document.get('collaboration') or {}).get('request') or {}
    outputs, missing = [], []
    try:
        if not planning_only(store, document):
            return None
        records = [(store.read_object_json(ref), ref) for ref in document.get('style_recipes') or []]
        if proposal is not None:
            records.append((proposal, proposal_ref))
        for record, ref in records:
            if record.get('schema_version') not in ('style_recipe.v3', 'style_proposal.v3'):
                continue
            from .models import validate_schema
            validate_schema('style_recipe' if record['schema_version'] == 'style_recipe.v3' else 'style_proposal', record)
            source = load_snapshot(store, record['base_revision'])
            source_request = (source.get('collaboration') or {}).get('request') or {}
            if source_request.get('request_id') != request.get('request_id'):
                continue
            if record.get('project_id') != document['project_id']:
                raise ValueError('design output belongs to another project')
            ids = set(record.get('input', {}).get('target_page_ids') or [])
            requested = set(request.get('scope', {}).get('page_ids') or [])
            if requested != ids:
                continue
            if (not record.get('basis') or not dependency_slices.assess_basis(store, document, record['basis'])['current']
                    or source.get('design_context') != document.get('design_context')):
                missing.append({'code': 'design_basis_changed', 'ref': ref})
                continue
            outputs.append(ref)
        pending = any(task.get('status') in ('running', 'awaiting_host', 'queued')
                      and (task.get('collaboration_binding') or {}).get('request_id') == request.get('request_id')
                      for task in (store.read_object_json(ref) for ref in document.get('tasks') or []))
        state = 'completed' if outputs and not pending else 'in_progress'
    except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
        state = 'needs_recovery'
        missing.append({'code': 'design_facts_unreadable', 'detail': type(exc).__name__})
    from .models import input_alignment
    if input_alignment(document) == 'needs_reconciliation':
        state = 'awaiting_decision'
        missing.append({'code': 'input_reconciliation_pending'})
    if not outputs and not missing:
        missing.append({'code': 'design_proposal_required'})
    return {'state': state, 'request_id': request.get('request_id'), 'intent': request.get('intent'),
            'content_intent': None, 'artifact_revision_id': document['revision_id'],
            'effective_scope': request.get('scope'), 'outputs': outputs,
            'checks': [{'kind': 'requested_design_plan', 'status': 'pass' if state == 'completed' else 'not_evaluated',
                        'basis': 'current request, exact scope and unchanged design inputs'}],
            'missing': missing, 'responsible_role': 'caller' if state == 'completed' else 'design',
            'next_action': 'return_requested_design' if state == 'completed' else 'prepare_requested_design',
            'adoption': 'not_implied', 'production_authority': 'not_implied'}
