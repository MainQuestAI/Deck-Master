"""Shared untrusted JSON adapter for the collaboration CLI and HTTP API."""
from __future__ import annotations

from . import collaboration, collaboration_migration, content_production, eligibility
from .capabilities import describe as capabilities
from .models import ModelError
from .store import Store, StoreError, ConflictError
from .operations import OperationError

WRITE_ACTIONS = {name: name for name in (
    'request.start', 'request.replace', 'decision', 'grant', 'adopt-proposal',
    'pause', 'resume', 'revoke', 'migration.apply', 'review.import', 'draft.import')}
READ_ACTIONS = ('show', 'migration.describe', 'eligibility', 'review.bindings', 'review.evaluate', 'delivery.describe')
MUTATING_ROUTES = ('continue',)
_FORBIDDEN = {'adapter_context', 'verified_user_events', 'independent_review_receipts', 'human_review_receipts'}
_REQUEST = {'intent', 'content_intent', 'scope', 'instruction_evidence', 'variant',
            'variant_transition', 'replace_request_id', 'background_request_ids', 'request_source_key'}
_DECISION = {'topic', 'delegation_ref', 'authority_mode', 'instruction_evidence', 'basis', 'subject_refs',
             'decision_id', 'replaces', 'scope', 'value', 'disposition'}
_GRANT = {'instruction_evidence', 'basis', 'authorization_id', 'replaces', 'mode', 'actions', 'scope',
          'decision_refs', 'delegated_topics', 'constraints', 'max_external_calls', 'max_candidate_count',
          'budget_template', 'budget_parent_ref', 'budget_key', 'adoption_policy', 'delivery_binding',
          'parent_authorization_ref', 'expires_at', 'stop_conditions'}
_FIELDS = {
    'show': set(), 'migration.describe': set(),
    'continue': set(),
    'request.start': _REQUEST | {'request'}, 'request.replace': _REQUEST | {'request'},
    'decision': _DECISION | {'decision'}, 'grant': _GRANT | {'authorization'},
    'adopt-proposal': {'proposal_ref', 'decision_ref', 'write_scope'},
    'pause': {'request_id', 'reason', 'evidence', 'instruction_evidence'},
    'resume': {'request_id', 'evidence', 'instruction_evidence'},
    'revoke': {'authorization_id', 'reason', 'evidence', 'instruction_evidence'},
    'migration.apply': {'plan_digest', 'instruction_evidence', 'request_input'},
    'eligibility': {'action', 'targets', 'artifact_revision', 'persistence'},
    'delivery.describe': {'revision', 'file_path', 'notes_policy'},
    'review.import': {'external_report', 'source_bindings', 'evidence', 'artifact_revision'},
    'review.bindings': {'external_report', 'artifact_revision'},
    'review.evaluate': {'source', 'source_sha256', 'scope', 'persistence', 'report_output'},
    'draft.import': {'draft_payload', 'instruction_evidence', 'preserve_mainline'},
}


def _reject_context(data):
    if isinstance(data, dict):
        if set(data) & _FORBIDDEN:
            raise OperationError('untrusted_adapter_context', 'request', 'transport evidence cannot be supplied by JSON',
                                 exit_code=4, http_status=403)
        for value in data.values():
            _reject_context(value)
    elif isinstance(data, list):
        for value in data:
            _reject_context(value)


def _known(data, fields, path='request'):
    unknown = sorted(set(data) - fields)
    if unknown:
        raise ModelError(path, f'unknown fields: {unknown}')


def _body(body, wrapper, fields):
    if wrapper not in body:
        return body
    value = body[wrapper]
    if not isinstance(value, dict):
        raise ModelError(wrapper, 'must be an object')
    _known(value, fields, wrapper)
    duplicates = set(value) & (set(body) - {wrapper})
    if duplicates:
        raise ModelError(wrapper, f'duplicate fields inside and outside wrapper: {sorted(duplicates)}')
    return {**value, **{k: v for k, v in body.items() if k != wrapper}}


def validate_declarations(data):
    """Reject ignored adapter arguments without inspecting opaque user values."""
    _reject_context(data)
    if not isinstance(data, dict):
        raise ModelError('request', 'must be an object')
    for key in ('request', 'request_input', 'decision', 'authorization'):
        if key in data and data[key] is not None:
            if not isinstance(data[key], dict):
                raise ModelError(key, 'must be an object')
            _known(data[key], {'request': _REQUEST, 'request_input': _REQUEST,
                               'decision': _DECISION, 'authorization': _GRANT}[key], key)
            validate_declarations(data[key])
    for key in ('instruction_evidence', 'evidence'):
        if key in data and data[key] is not None:
            value = data[key]
            if not isinstance(value, dict):
                raise ModelError(key, 'must be an object')
            if 'assurance' in value:
                raise OperationError('untrusted_evidence_assurance', key + '/assurance',
                                     'evidence assurance is derived by the runtime', exit_code=4, http_status=403)
            fields = {'kind', 'text', 'source_locator'} if 'text' in value else {
                'kind', 'source_ref', 'source_locator', 'actor_id', 'transport_receipt_ref', 'presentation_ref'}
            _known(value, fields, key)
    for key in ('scope', 'write_scope', 'targets'):
        if key in data and data[key] is not None:
            if not isinstance(data[key], dict):
                raise ModelError(key, 'must be an object')
            _known(data[key], {'subject', 'page_ids', 'page_manifest_ref', 'external_artifact_ref', 'layers',
                               'allow_page_membership_change', 'allow_page_order_change', 'purpose'}, key)
    if isinstance(data.get('variant'), dict):
        _known(data['variant'], {'group_id', 'variant_id', 'label', 'requested_variant_ids'}, 'variant')
    if isinstance(data.get('variant_transition'), dict):
        value = data['variant_transition']
        _known(value, {'kind', 'source'}, 'variant_transition')
        if isinstance(value.get('source'), dict):
            _known(value['source'], {'revision_id', 'export_id'}, 'variant_transition/source')


def _response(document, *, status, result=None, error=None, operation_id=None):
    return {'schema_version': 'collaboration_response.v1', 'status': status,
            'project_id': document.get('project_id') if document else None,
            'artifact_revision_id': (result or {}).get('artifact_revision_id') or (result or {}).get('revision_id') or (document or {}).get('revision_id'),
            'control_revision_id': (result or {}).get('control_revision_id') or (document or {}).get('revision_id'),
            'operation_id': operation_id, 'result': result, 'error': error,
            'next_action': (result or {}).get('next_action') or ('resolve_the_named_gap' if error else 'inspect_current_state')}


def error_response(exc, *, document=None, operation_id=None):
    """Fixed §12 mapping, independent of the legacy command error mapping."""
    from .service import ServiceError
    field, details = getattr(exc, 'path', 'request'), {}
    if isinstance(exc, eligibility.EligibilityBlocked):
        code, http, exit_code = exc.decision['reason_codes'][0], 409, 4
        details = exc.decision
    elif isinstance(exc, OperationError):
        code, http, exit_code = exc.error_code, exc.http_status, exc.exit_code
        if http == 422:
            http = 400
        if http == 409 and exit_code != 5:
            exit_code = 4
        details = getattr(exc, 'details', {}) or {}
    elif isinstance(exc, ConflictError) or (isinstance(exc, StoreError) and field == 'base_revision'):
        code, http, exit_code = 'conflict', 409, 5
    elif getattr(exc, 'error_code', None):
        code = exc.error_code
        http, exit_code = getattr(exc, 'http_status', 403), getattr(exc, 'exit_code', 4)
    elif isinstance(exc, (ModelError, ServiceError)):
        message = str(exc)
        gap = next((s for s in ('migration_required', 'decision_needed', 'needs_reviewer', 'authority_channel_unavailable',
                               'paused', 'scope_exceeded', 'budget_exhausted', 'authority_insufficient') if s in message), None)
        code, http, exit_code = (gap, 409, 4) if gap else ('invalid_input', 400, 2)
    elif isinstance(exc, (StoreError, FileNotFoundError)):
        code, http, exit_code = 'object_not_found', 404, 2
    elif isinstance(exc, (KeyError, TypeError, ValueError)):
        code, http, exit_code = 'invalid_input', 400, 2
    else:
        raise exc
    details = {'artifact_revision_id': (document or {}).get('revision_id'),
               'control_revision_id': (document or {}).get('revision_id'),
               'affected_scope': details.get('scope'), 'decision': details.get('decision_card'), **details}
    error = {'code': code, 'path': field, 'message': str(exc), 'recoverable': http != 403, 'details': details}
    return _response(document, status='blocked' if http == 409 else 'error', error=error,
                     operation_id=operation_id), http, exit_code


def invoke(project, action, payload=None, *, adapter_context=None, expected_project_id=None):
    """Return shared response, HTTP status and CLI exit. Context is transport-only."""
    document, data = None, {}
    try:
        if payload is not None and not isinstance(payload, dict):
            raise ModelError('request', 'body must be an object')
        data = dict(payload or {})
        validate_declarations(data)
        if action not in _FIELDS:
            raise ModelError('action', 'unsupported collaboration action')
        common_keys = {'project_id'} | ({'base_revision', 'operation_id'} if action in WRITE_ACTIONS else set())
        _known(data, _FIELDS[action] | common_keys)
        if action == 'review.evaluate':
            from .external_review import evaluate
            _known(data, _FIELDS[action])
            result = evaluate(**data, adapter_context=adapter_context)
            return _response(None, status=result['status'], result=result), 200, 0
        store = Store(project)
        document = store.load_document()
        if expected_project_id is not None and expected_project_id != document['project_id']:
            raise StoreError('project_id', 'URL project is not served by this service')
        if data.get('project_id') not in (None, document['project_id']):
            raise ModelError('project_id', 'request belongs to another project')
        body = {k: v for k, v in data.items() if k not in common_keys}
        if action == 'show':
            result = {**collaboration.describe(project), 'capabilities': capabilities(adapter_context),
                      'completion': content_production.completion_status(store, document)}
        elif action == 'continue':
            from .service import continue_project
            result = continue_project(project)
            document = store.load_document()
            if result.get('status') != 'completed' and (result.get('eligibility') or {}).get('allowed') is False:
                response, http, code = error_response(eligibility.EligibilityBlocked(result['eligibility']), document=document)
                response['result'] = result
                response['next_action'] = result.get('next_action') or response['next_action']
                return response, http, code
        elif action == 'migration.describe':
            result = collaboration_migration.describe(project)
        elif action == 'eligibility':
            from .snapshots import load_snapshot
            artifact = load_snapshot(store, body.get('artifact_revision'))
            context = {k: body[k] for k in ('targets', 'persistence') if k in body}
            result = eligibility.evaluate(store, artifact, document, body['action'], context)
        elif action == 'delivery.describe':
            from .delivery_eligibility import describe
            result = describe(project, **body)
        elif action == 'review.bindings':
            from . import review_import
            result = review_import.describe_bindings(project, **body)
        else:
            common = {key: data.get(key) for key in ('base_revision', 'operation_id')}
            for key, value in common.items():
                if not isinstance(value, str) or not value.strip():
                    raise ModelError(key, 'must be a nonempty string')
            if action.startswith('request.'):
                value = _body(body, 'request', _REQUEST)
                if action == 'request.replace' and not value.get('replace_request_id'):
                    raise ModelError('replace_request_id', 'replace names the current request')
                result = collaboration.start_request(project, input=value, adapter_context=adapter_context, **common)
            elif action in ('decision', 'grant'):
                wrapper, fields, call = ('decision', _DECISION, collaboration.record_decision) if action == 'decision' else ('authorization', _GRANT, collaboration.grant)
                result = call(project, input=_body(body, wrapper, fields), adapter_context=adapter_context, **common)
            elif action == 'adopt-proposal':
                result = content_production.adopt_proposal(project, input=body, adapter_context=adapter_context, **common)
            elif action in ('pause', 'resume', 'revoke'):
                if 'evidence' in body and 'instruction_evidence' in body:
                    raise ModelError('evidence', 'provide evidence once')
                values = {k: v for k, v in body.items() if k != 'evidence'}
                if 'evidence' in body:
                    values['instruction_evidence'] = body['evidence']
                if action in ('pause', 'resume') and not values.get('request_id'):
                    raise ModelError('request_id', 'the current request must be named')
                call = {'pause': collaboration.pause_request, 'resume': collaboration.resume_request,
                        'revoke': collaboration.revoke_authorization}[action]
                result = call(project, adapter_context=adapter_context, **values, **common)
            elif action == 'migration.apply':
                result = collaboration_migration.apply(project, adapter_context=adapter_context, **body, **common)
            elif action == 'draft.import':
                from .service import import_draft
                result = import_draft(project, adapter_context=adapter_context, **body, **common)
            else:
                from . import review_import
                result = review_import.import_report(project, adapter_context=adapter_context, **body, **common)
            document = store.load_document()
        return _response(document, status=result.get('status', 'ok'), result=result, operation_id=data.get('operation_id')), 200, 0
    except Exception as exc:
        return error_response(exc, document=document, operation_id=data.get('operation_id'))


HTTP_ROUTES = {
    ('POST', '/api/reviews/evaluate'): 'review.evaluate',
    ('GET', '/api/projects/{project_id}/collaboration'): 'show',
    ('GET', '/api/projects/{project_id}/collaboration/migration'): 'migration.describe',
    ('POST', '/api/projects/{project_id}/collaboration/requests'): 'request.start',
    ('POST', '/api/projects/{project_id}/eligibility'): 'eligibility',
    ('POST', '/api/projects/{project_id}/collaboration/decisions'): 'decision',
    ('POST', '/api/projects/{project_id}/collaboration/authorizations'): 'grant',
    ('POST', '/api/projects/{project_id}/collaboration/proposal-adoptions'): 'adopt-proposal',
    ('POST', '/api/projects/{project_id}/collaboration/request/pause'): 'pause',
    ('POST', '/api/projects/{project_id}/collaboration/request/resume'): 'resume',
    ('POST', '/api/projects/{project_id}/collaboration/authorizations/{authorization_id}/revoke'): 'revoke',
    ('POST', '/api/projects/{project_id}/collaboration/migration'): 'migration.apply',
    ('POST', '/api/projects/{project_id}/reviews/import'): 'review.import',
    ('POST', '/api/projects/{project_id}/reviews/bindings'): 'review.bindings',
    ('POST', '/api/projects/{project_id}/draft/import'): 'draft.import',
    ('POST', '/api/projects/{project_id}/continue'): 'continue',
    ('GET', '/api/projects/{project_id}/delivery-eligibility'): 'delivery.describe',
}


def http_action(method, path):
    """Resolve only exact catalog routes; placeholders match one path segment."""
    from urllib.parse import unquote
    pieces = path.strip('/').split('/')
    for (verb, template), action in HTTP_ROUTES.items():
        expected = template.strip('/').split('/')
        if verb != method or len(pieces) != len(expected):
            continue
        bound = {}
        for actual, part in zip(pieces, expected, strict=True):
            if part.startswith('{') and part.endswith('}'):
                value = unquote(actual)
                if not value or '/' in value:
                    break
                bound[part[1:-1]] = value
            elif actual != part:
                break
        else:
            return bound.pop('project_id', None), action, bound
    return None
