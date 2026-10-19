"""Recoverable operations on the existing Store pointer and committed ancestry.

The operations directory is a disposable index. Neither its presence nor an
orphan result object is proof that a business transaction was committed.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
import uuid

from .errors import TypedServiceError
from .local_state import safe_path
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import committed_snapshots, READ_FAILURES, reuse_current_snapshot
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
                         'next_action': ('inspect the original operation; preserve its payload, base and ID until verification succeeds'
                                         if self.operation_state == 'unknown' else
                                         'replay the exact saved payload with the same operation ID'
                                         if self.error_code == 'operation_not_found' else
                                         'read current state; changed input requires a new plan and operation ID'),
                         'docs_ref': 'docs/agent-recovery-playbook.md#workbench-operations'}}


def validate_id(value, *, new=False):
    valid = isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value))
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


@dataclass
class OperationLookup:
    state: str
    head_revision: str | None = None
    receipt_format: str | None = None
    stored_kind: str | None = None
    committed_revision_id: str | None = None
    record: dict | None = None
    result: dict | None = None
    reason: str | None = None


def _decode_committed_operation(store, document, operation_id):
    """Canonical receipt decoder. Called only for a verified ancestor."""
    change = document.get('change') or {}
    if change.get('operation_commit'):
        obj = store.read_object_json(change['operation_commit'])
        validate_schema('operation_commit', obj)
        if (obj['operation_id'] != operation_id or obj['project_id'] != document['project_id']
                or obj['committed_revision_id'] != document['revision_id']
                or obj['base_revision'] != document['parent_revision_id']):
            raise StoreError('operation_commit', 'operation binding mismatch')
        result = store.read_object_json(obj['result_ref'])
        if not isinstance(result, dict) or result.get('revision_id') != document['revision_id']:
            raise StoreError('operation_commit', 'result revision mismatch')
        return 'operation_commit.v1', obj['kind'], obj, result
    receipt = change.get('operation_receipt')
    if receipt is not None:
        validate_schema('document', document)
        if receipt['response']['revision_id'] != document['revision_id']:
            raise StoreError('operation_receipt', 'result revision mismatch')
        return 'operation_receipt.v1', change['kind'], {
            'operation_id': operation_id, 'project_id': document['project_id'],
            'kind': change['kind'], 'request_digest': receipt['request_digest'],
            'base_revision': document['parent_revision_id'],
            'committed_revision_id': document['revision_id']}, copy.deepcopy(receipt['response'])
    return None


def resolve_operation(store, operation_id, *, head_revision=None, use_cache=None):
    """Pure I01 query; only this process's canonical coverage proves absence.

    Set use_cache=False (or DECK_MASTER_OPERATION_CACHE=0) for a cold canonical
    control. Signature checks remain O(H); only JSON parsing is incremental.
    """
    import os
    from . import operation_coverage as coverage_cache
    validate_id(operation_id)
    enabled = os.environ.get('DECK_MASTER_OPERATION_CACHE', '1') != '0' if use_cache is None else use_cache
    head = None
    root = None
    try:
        for attempt in range(2):
            root = coverage_cache.root_identity(store)
            control = coverage_cache.current_head(store)
            head = head_revision if head_revision is not None else control
            cached = coverage_cache.get(root) if enabled else None
            if cached is not None:
                try:
                    valid_coverage = coverage_cache.valid(store, cached)
                except READ_FAILURES:
                    # Old coverage may describe a no-longer-selected branch.
                    # Unreadable cached paths invalidate this disposable hint;
                    # only the selected canonical scan may establish unknown.
                    valid_coverage = False
                if not valid_coverage:
                    coverage_cache.discard(root)
                    cached = None
            coverage, head, document = coverage_cache.scan(
                store, root=root, control=control, operation_id=operation_id,
                head_revision=head_revision, cached=cached)
            result = OperationLookup('not_found', head)
            if document is not None:
                change = document.get('change') or {}
                decoded = _decode_committed_operation(store, document, operation_id)
                if decoded is None:
                    result = OperationLookup('unknown', head, stored_kind=change.get('kind'),
                        committed_revision_id=document['revision_id'], reason='legacy_receipt_only')
                else:
                    fmt, kind, record, response = decoded
                    result = OperationLookup('committed', head, fmt, kind, document['revision_id'], record, response)
            if (coverage_cache.current_head(store) != control
                    or coverage_cache.root_identity(store) != root):
                coverage_cache.discard(root)
                continue
            if enabled and result.state != 'unknown':
                coverage_cache.publish(coverage)
            elif result.state == 'unknown':
                coverage_cache.discard(root)
            return result
        return OperationLookup('unknown', head, reason='current_changed')
    except READ_FAILURES:
        if root is not None:
            coverage_cache.discard(root)
        return OperationLookup('unknown', head, reason='history_unreadable')


def lookup_error(lookup, operation_id):
    unavailable = lookup.reason in ('history_unreadable', 'current_changed')
    return OperationError('operation_unavailable' if unavailable else 'operation_unverified', 'operation_id',
        'operation history could not be verified; preserve the original request and inspect the original operation',
        exit_code=4, http_status=503 if unavailable else 409, operation_id=operation_id, operation_state='unknown')


def committed_record(store, operation_id):
    found = resolve_operation(store, operation_id)
    if found.state == 'unknown':
        raise lookup_error(found, operation_id)
    return (found.record, found.result) if found.state == 'committed' else None


def read_legacy_record(store, operation_id, *, head_revision=None):
    """Read one old input journal without treating it as atomic receipt truth."""
    validate_id(operation_id)
    try:
        from .local_state import LocalStateError
        try:
            path = safe_path(store.deck_root, 'operations', operation_id + '.json')
        except LocalStateError as exc:
            raise ValueError('unsafe journal') from exc
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink():
            raise ValueError('symlink journal')
        record = json.loads(path.read_bytes())
        if record.get('format') == 'operation_index.v1':
            return None
        if (record.get('operation_id') != operation_id or record.get('kind') != 'input_update'
                or not isinstance(record.get('request_sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', record['request_sha256'])
                or not isinstance(record.get('result'), dict)
                or record['result'].get('status') not in ('updated', 'unchanged')):
            raise ValueError('invalid journal')
        revision = record['result'].get('revision_id')
        for doc in committed_snapshots(store, head_revision=head_revision):
            if doc['revision_id'] == revision:
                if (record['result']['status'] != 'unchanged'
                        and (doc.get('change') or {}).get('operation_id') != operation_id):
                    raise ValueError('legacy result does not match its commit')
                return record
        raise ValueError('unreachable journal')
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise lookup_error(OperationLookup('unknown', reason='legacy_receipt_only'), operation_id) from exc
    except READ_FAILURES as exc:
        raise lookup_error(OperationLookup('unknown', reason='history_unreadable'), operation_id) from exc


def publish_index(store, record):
    """Best effort: failure cannot make an already committed operation repeat."""
    try:
        path = safe_path(store.deck_root, 'operations', record['operation_id'] + '.json')
        if path.exists():
            try:
                previous = json.loads(path.read_bytes())
            except (ValueError, OSError):
                previous = None
            if isinstance(previous, dict) and previous.get('kind') == 'input_update' and 'request_sha256' in previous:
                return None
        _atomic_write_bytes(path, canonical_json_bytes({'format': 'operation_index.v1', **record}))
    except (OSError, TypedServiceError):
        return {'code': 'receipt_cache_unavailable', 'message': 'committed result is recoverable from project history'}
    return None


def recover(store, operation_id, digest=None):
    return _recover_lookup(store, operation_id, resolve_operation(store, operation_id), digest)


def _recover_lookup(store, operation_id, lookup, digest=None):
    """Project one already verified lookup without selecting another head."""
    if lookup.state == "unknown":
        raise lookup_error(lookup, operation_id)
    if lookup.state == "not_found":
        return None
    record, result = lookup.record, lookup.result
    if digest is not None and record['request_digest'] != digest:
        raise OperationError('operation_payload_conflict', 'operation_id',
                             'this operation was committed with a different payload', exit_code=5,
                             operation_id=operation_id, operation_state='committed')
    # The old task replay checks its committed receipt first and may rebuild
    # its legacy projection afterward; both are disposable index formats.
    warning = publish_index(store, record)
    response = {'status': 'committed', 'operation_id': operation_id,
                'committed_revision_id': record['committed_revision_id'],
                'current_revision_id': lookup.head_revision,
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


@reuse_current_snapshot()
def show(project, *, operation_id):
    from .local_state import project_path
    from .store import Store
    store = Store(project_path(project))
    lookup = resolve_operation(store, operation_id)
    if lookup.state == 'unknown' and lookup.reason != 'legacy_receipt_only':
        raise lookup_error(lookup, operation_id)
    result = _recover_lookup(store, operation_id, lookup) if lookup.state == 'committed' else None
    if result is None:
        legacy = read_legacy_record(store, operation_id, head_revision=lookup.head_revision)
        if legacy is not None:
            return {'status': 'legacy_recorded', 'receipt_source': 'legacy_log',
                    'request_binding_verification': 'legacy_only', 'operation_id': operation_id,
                    'result_revision_id': legacy['result']['revision_id'],
                    'current_revision_id': lookup.head_revision,
                    'request_sha256': legacy['request_sha256'], 'operation_result': legacy['result']}
        if lookup.state == 'unknown':
            raise lookup_error(lookup, operation_id)
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
    # Marker for the T04 entry-inventory coverage test: it enumerates the public
    # operation surface by introspection so a new public operation cannot be
    # added without being classified against an eligibility action.
    wrapped.__public_operation__ = function.__qualname__
    return wrapped


show = public(show)
