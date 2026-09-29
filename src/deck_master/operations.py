"""Recoverable operations on the existing Store pointer and committed ancestry.

The operations directory is a disposable index. Neither its presence nor an
orphan result object is proof that a business transaction was committed.
"""
from __future__ import annotations

import copy
import uuid

from .errors import TypedServiceError
from .local_state import safe_path
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import IDENTIFIER, committed_snapshots
from .store import StoreError, _atomic_write_bytes


class OperationError(TypedServiceError):
    def __init__(self, code, field, message, *, exit_code=2, http_status=None,
                 operation_id=None, operation_state='not_committed'):
        super().__init__(field, message)
        self.error_code = code
        self.exit_code = exit_code
        self.http_status = http_status or (409 if exit_code == 5 else 422)
        self.operation_id = operation_id
        self.operation_state = operation_state

    def payload(self):
        return {'error': {'code': self.error_code, 'message': self.detail, 'field': self.path,
                         'cause': self.error_code, 'operation_id': self.operation_id,
                         'retryable': self.error_code == 'operation_not_found',
                         'operation_state': self.operation_state,
                         'next_action': ('replay the exact saved payload with the same operation ID'
                                         if self.error_code == 'operation_not_found' else
                                         'read current state; changed input requires a new plan and operation ID'),
                         'docs_ref': 'docs/agent-recovery-playbook.md#workbench-operations'}}


def validate_id(value, *, new=False):
    valid = isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))
    if valid and new:
        try:
            parsed = uuid.UUID(value)
            valid = parsed.version == 4 and str(parsed) == value
        except ValueError:
            valid = False
    if not valid:
        raise OperationError('invalid_operation_id', 'operation_id',
                             'new operations require a canonical UUIDv4' if new else 'invalid operation identifier')


def request_digest(document, kind, base_revision, payload):
    return sha256_bytes(canonical_json_bytes({'protocol': 'changes.v1', 'kind': kind,
                       'project_id': document['project_id'], 'base_revision': base_revision,
                       'payload': payload}))


def committed_record(store, operation_id):
    """Resolve only a same-project, reachable operation; never trust the index."""
    validate_id(operation_id)
    for document in committed_snapshots(store):
        change = document.get('change') or {}
        if change.get('operation_id') != operation_id:
            continue
        if change.get('operation_commit'):
            obj = store.read_object_json(change['operation_commit'])
            validate_schema('operation_commit', obj)
            if (obj['operation_id'] != operation_id or obj['project_id'] != document['project_id']
                    or obj['committed_revision_id'] != document['revision_id']
                    or obj['base_revision'] != document['parent_revision_id']):
                raise StoreError('operation_commit', 'operation binding does not match its committed Document')
            result = store.read_object_json(obj['result_ref'])
            if not isinstance(result, dict) or result.get('revision_id') != document['revision_id']:
                raise StoreError('operation_commit', 'result does not name its committed revision')
            return obj, result
        # Compatibility with W02's atomic task/freeze receipts. No invented
        # digest for older journal-only operations.
        receipt = change.get('operation_receipt')
        if receipt is not None:
            validate_schema('document', document)
            if receipt['response']['revision_id'] != document['revision_id']:
                raise StoreError('operation_receipt', 'result revision mismatch')
            return {'operation_id': operation_id, 'project_id': document['project_id'],
                    'kind': change['kind'], 'request_digest': receipt['request_digest'],
                    'base_revision': document['parent_revision_id'],
                    'committed_revision_id': document['revision_id']}, copy.deepcopy(receipt['response'])
        raise OperationError('operation_unverified', 'operation_id',
                             'historical operation has no verifiable request receipt; do not guess or replay it',
                             exit_code=4, http_status=409, operation_id=operation_id, operation_state='unknown')
    return None


def publish_index(store, record):
    """Best effort: failure cannot make an already committed operation repeat."""
    try:
        path = safe_path(store.deck_root, 'operations', record['operation_id'] + '.json')
        _atomic_write_bytes(path, canonical_json_bytes({'format': 'operation_index.v1', **record}))
    except (OSError, TypedServiceError):
        return {'code': 'receipt_cache_unavailable', 'message': 'committed result is recoverable from project history'}
    return None


def recover(store, operation_id, digest=None):
    found = committed_record(store, operation_id)
    if found is None:
        return None
    record, result = found
    if digest is not None and record['request_digest'] != digest:
        raise OperationError('operation_payload_conflict', 'operation_id',
                             'this operation was committed with a different payload', exit_code=5,
                             operation_id=operation_id, operation_state='committed')
    # The old task replay checks its committed receipt first and may rebuild
    # its legacy projection afterward; both are disposable index formats.
    warning = publish_index(store, record)
    response = {'status': 'committed', 'operation_id': operation_id,
                'committed_revision_id': record['committed_revision_id'],
                'current_revision_id': store.current_revision_id(),
                'request_digest': record['request_digest'], 'operation_result': result}
    if record.get('result_ref'):
        response['result_ref'] = record['result_ref']
    if warning:
        response['journal_warning'] = warning
    return response


def commit_locked(store, *, document, base_revision, operation_id, kind, digest, result):
    """Caller owns Store._locked and has deduped before CAS/business effects."""
    if result.get('revision_id') != document['revision_id']:
        raise StoreError('operation_result', 'result must name the preallocated commit revision')
    record = {'schema_version': 'operation_commit.v1', 'operation_id': operation_id,
              'kind': kind, 'project_id': document['project_id'], 'request_digest': digest,
              'base_revision': base_revision, 'committed_revision_id': document['revision_id'],
              'result_ref': store.put_json_object(result)}
    validate_schema('operation_commit', record)
    document['change']['operation_commit'] = store.put_json_object(record)
    from .models import require_writer
    require_writer(document, 'changes.v1')
    store._commit_locked(base_revision=base_revision, document=document, operation_id=operation_id, blobs=[])
    warning = publish_index(store, record)
    response = {'status': 'committed', 'operation_id': operation_id,
                'committed_revision_id': document['revision_id'], 'current_revision_id': document['revision_id'],
                'request_digest': digest, 'result_ref': record['result_ref'], 'operation_result': copy.deepcopy(result)}
    if warning:
        response['journal_warning'] = warning
    return response


def show(project, *, operation_id):
    from .local_state import project_path
    from .store import Store
    store = Store(project_path(project))
    result = recover(store, operation_id)
    if result is None:
        raise OperationError('operation_not_found', 'operation_id', 'no committed fact for this operation',
                             http_status=404, operation_id=operation_id, operation_state='not_found')
    return result


def public(function):
    """Same typed, path-sanitized failures for CLI and same-origin HTTP."""
    from functools import wraps
    from .models import ModelError
    from .store import ConflictError
    @wraps(function)
    def wrapped(*args, **kwargs):
        import inspect
        try:
            inspect.signature(function).bind(*args, **kwargs)
        except TypeError as exc:
            raise OperationError('invalid_input', 'request', 'request fields do not match this command') from exc
        try:
            return function(*args, **kwargs)
        except OperationError:
            raise
        except ModelError as exc:
            raise OperationError('invalid_input', exc.path, exc.detail,
                                 operation_id=kwargs.get('operation_id')) from exc
        except ConflictError as exc:
            raise OperationError('conflict', 'base_revision', 'project changed; read current state and replan',
                                 exit_code=5, operation_id=kwargs.get('operation_id')) from exc
        except TypedServiceError as exc:
            raise OperationError(exc.error_code, exc.path, exc.detail, exit_code=exc.exit_code,
                                 operation_id=kwargs.get('operation_id')) from exc
        except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
            raise OperationError('operation_unavailable', 'project', 'operation could not be verified; keep its original payload and ID',
                                 exit_code=4, http_status=503, operation_id=kwargs.get('operation_id'),
                                 operation_state='unknown') from exc
    return wrapped


show = public(show)
