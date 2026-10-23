"""Local diagnostic history, never Task, checkpoint, receipt or authority evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import stat
import uuid

from .store import _atomic_write_bytes

PHASES = {'client_lookup', 'login_status', 'app_server_start', 'initialize',
          'config_read', 'thread_start', 'session_validation', 'session_enter'}
CATEGORIES = {'tool_missing', 'tool_failed', 'login_required', 'session_rejected', 'startup_failed'}
NEXT_ACTION = ('Inspect the existing native client and its local diagnostics; resolve the named startup phase, '
               'then explicitly retry an authorized review. Discovery and prerequisites_ready do not prove '
               'session startup or review completion. No automatic retry or credential change is performed.')
_FILENAME = 'native-review-startup-history.json'


def read(store):
    """Read diagnostics without executing a client or changing project facts."""
    try:
        fd = os.open(store.deck_root / _FILENAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return []
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('startup history is not a regular file')
        records = json.load(stream)
    if not isinstance(records, list):
        raise ValueError('invalid startup history')
    for row in records:
        if (not isinstance(row, dict) or set(row) != {'attempt_id', 'occurred_at', 'revision_id',
                'category', 'phase', 'exit_code', 'process_exit_code'}
                or not all(isinstance(row[key], str) for key in ('attempt_id', 'occurred_at', 'revision_id', 'category', 'phase'))
                or row['category'] not in CATEGORIES or row['phase'] not in PHASES
                or type(row['exit_code']) is not int
                or (row['process_exit_code'] is not None and type(row['process_exit_code']) is not int)):
            raise ValueError('invalid startup history')
        uuid.UUID(row['attempt_id'])
        datetime.fromisoformat(row['occurred_at'])
        # Revisions are generated identifiers; never echo arbitrary file content.
        if not isinstance(row['revision_id'], str) or len(row['revision_id']) != 32 or not all(c in '0123456789abcdef' for c in row['revision_id']):
            raise ValueError('invalid startup history revision')
    return records


def normalize(failure):
    """Use the same fixed whitelist for disk and public error details."""
    failure = failure if isinstance(failure, dict) else {}
    category, phase = failure.get('category'), failure.get('phase')
    return {
        'category': category if isinstance(category, str) and category in CATEGORIES else 'startup_failed',
        'phase': phase if isinstance(phase, str) and phase in PHASES else 'session_enter',
        'exit_code': failure.get('exit_code') if type(failure.get('exit_code')) is int else 3,
        'process_exit_code': failure.get('process_exit_code') if type(failure.get('process_exit_code')) is int else None,
    }


def record(store, revision_id, failure):
    """Caller holds native-review.lock. Atomic sidecar only; no business commit."""
    row = {'attempt_id': str(uuid.uuid4()), 'occurred_at': datetime.now(timezone.utc).isoformat(),
           'revision_id': revision_id, **normalize(failure)}
    records = read(store)
    _atomic_write_bytes(store.deck_root / _FILENAME, json.dumps([*records, row]).encode())


def describe(store):
    try:
        return {'status': 'read', 'failures': [{**row, 'status': 'startup_failed',
            'evidence_scope': 'historical_local_startup_diagnostic', 'next_action': NEXT_ACTION} for row in read(store)]}
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'unavailable', 'failures': [],
                'next_action': 'Preserve and inspect local startup history; unreadable history is not absence of a failure.'}
