"""Bounded personal overview readings and a CAS barrier across preference clear."""
from __future__ import annotations

from .local_state import LocalStateConflict, LocalStateError, local_lock, read_json, safe_path, write_json
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import load_snapshot
from .ui_journal import context

MAX_READINGS = 12
# The reader refuses records beyond this size; the writer must never produce one,
# or normal large selections permanently wedge the preference file (review F1).
MAX_RECORD_BYTES = 32_000


def _file(store):
    return safe_path(store.deck_root, 'workbench', 'overview.json')


def _fit(current, identity, states):
    """Drop the oldest readings until the record fits the reader's budget.

    A single state that cannot fit on its own is refused loudly instead of
    being written as an unreadable record: the UI keeps its input and shows
    the save as unconfirmed (existing error handling), instead of a
    permanently damaged preference file.
    """
    while True:
        probe = {'schema_version': 'ui_overview_record.v1', 'project_id': current['project_id'],
                 'project_identity': identity, 'states': states, 'sequence': 1}
        if len(canonical_json_bytes(probe)) <= MAX_RECORD_BYTES:
            return states
        if len(states) == 1:
            raise LocalStateError('states', 'overview record exceeds the supported size; clear the page selection before saving')
        states = states[1:]


def _etag(record):
    return sha256_bytes(canonical_json_bytes({key: value for key, value in record.items() if key != 'etag'}))


def _validate(current, identity, state):
    validate_schema('ui_overview', state)
    if state['project_id'] != current['project_id'] or state['project_identity'] != identity:
        raise LocalStateError('project_identity', 'overview preference belongs to another project')


def _read(store, current, identity):
    record = read_json(_file(store), max_bytes=MAX_RECORD_BYTES)
    if record is None:
        return None
    if set(record) != {'schema_version', 'project_id', 'project_identity', 'states', 'sequence', 'etag'} or record['schema_version'] != 'ui_overview_record.v1':
        raise LocalStateError('overview', 'invalid overview preference record; preserve it for recovery')
    if record['project_id'] != current['project_id'] or record['project_identity'] != identity:
        raise LocalStateError('project_identity', 'overview preference record belongs to another project')
    if type(record['sequence']) is not int or record['sequence'] < 1 or record['etag'] != _etag(record):
        raise LocalStateError('overview', 'overview sequence or hash is invalid; preserve it for recovery')
    if not isinstance(record['states'], list) or len(record['states']) > MAX_READINGS:
        raise LocalStateError('overview', 'too many saved overview readings')
    seen = set()
    for state in record['states']:
        _validate(current, identity, state)
        if state['revision_id'] in seen:
            raise LocalStateError('revision_id', 'saved overview readings must be unique')
        seen.add(state['revision_id'])
    return record


def _write(store, current, identity, states, previous):
    record = {'schema_version': 'ui_overview_record.v1', 'project_id': current['project_id'],
              'project_identity': identity, 'states': states,
              'sequence': previous['sequence'] + 1 if previous else 1}
    record['etag'] = _etag(record)
    write_json(_file(store), record)
    return record


def get(project, *, revision):
    if not isinstance(revision, str) or not revision or len(revision) > 128:
        raise LocalStateError('revision', 'provide one fixed overview reading revision')
    store, current, identity = context(project)
    # Explicit reading version: never silently return another revision's state.
    load_snapshot(store, revision)
    record = _read(store, current, identity)
    state = next((state for state in record['states'] if state['revision_id'] == revision), None) if record else None
    return {'project_id': current['project_id'], 'project_identity': identity, 'revision_id': revision,
            'record': {'state': state, 'etag': record['etag']} if state else None,
            'etag': record['etag'] if record else None, 'issues': []}


def save(project, *, state, expected_etag=None):
    store, current, identity = context(project)
    _validate(current, identity, state)
    load_snapshot(store, state['revision_id'])
    if expected_etag is not None and (not isinstance(expected_etag, str) or len(expected_etag) != 64):
        raise LocalStateError('expected_etag', 'provide the saved preference identity or null')
    with local_lock(safe_path(_file(store).parent, 'overview.lock')):
        previous = _read(store, current, identity)
        existing = next((value for value in previous['states'] if value['revision_id'] == state['revision_id']), None) if previous else None
        if existing == state:
            return {'status': 'saved', 'record': {'state': state, 'etag': previous['etag']}, 'replayed': True}
        if expected_etag != (previous['etag'] if previous else None):
            raise LocalStateConflict('expected_etag', 'overview preferences changed or were cleared; current input is retained')
        states = [value for value in (previous['states'] if previous else []) if value['revision_id'] != state['revision_id']]
        states = _fit(current, identity, [*states, state][-MAX_READINGS:])
        record = _write(store, current, identity, states, previous)
    return {'status': 'saved', 'record': {'state': state, 'etag': record['etag']}, 'replayed': False}


def _clear(store, current, identity):
    """Caller holds overview.lock; corrupted/foreign files remain recoverable."""
    try:
        previous = _read(store, current, identity)
    except (LocalStateError, ValueError, KeyError, TypeError):
        return
    _write(store, current, identity, [], previous)
