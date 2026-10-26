"""Inspect and explicitly end uncertain personal clears without business writes.

An absent receipt is not proof of no execution. End records fence late commits,
not rollback them; their operation-owned backup never shares a future clear slot.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import stat
import tempfile
from . import ui_journal as journal
from .local_state import LocalStateConflict, LocalStateError, read_json, safe_path, write_json, MAX_BODY
from .models import validate_schema, canonical_json_bytes


def request(doc, *, operation_id, input, plan_id, manifest_digest):
    value = dict(operation_id=operation_id, input=input, plan_id=plan_id, manifest_digest=manifest_digest)
    validate_schema('ui_clear_request', value)
    if input['project_id'] != doc['project_id']:
        raise LocalStateConflict('project_id', 'clear request belongs to another project')
    if plan_id != 'clear-plan-' + manifest_digest[:16]:
        raise LocalStateConflict('plan_id', 'clear plan does not match its original manifest')
    return value


def closure_path(store, operation_id):
    if not isinstance(operation_id, str) or not journal.IDENTIFIER.fullmatch(operation_id):
        raise LocalStateError('operation_id', 'invalid clear operation identity')
    return safe_path(store.deck_root, 'workbench', 'clear-closures', operation_id + '.json')


def evidence_path(store, digest):
    if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise LocalStateError('clear_evidence', 'invalid recovery evidence digest')
    return safe_path(store.deck_root, 'workbench', 'clear-evidence', digest + '.json')


def _read_evidence(store, reference):
    """Verify the exact regular file before parsing, without the draft size cap.

    A spooled stream keeps hashing bounded in memory and avoids reopening a
    potentially replaced path between verification and JSON decoding.
    """
    path = evidence_path(store, reference['sha256'])
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source, tempfile.SpooledTemporaryFile(max_size=MAX_BODY) as verified:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != reference['bytes']:
                raise LocalStateError('clear_evidence', 'recovery evidence has a different type or length; retain it')
            digest = hashlib.sha256()
            remaining = reference['bytes']
            while remaining:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    raise LocalStateError('clear_evidence', 'recovery evidence is truncated; retain it')
                remaining -= len(chunk)
                digest.update(chunk)
                verified.write(chunk)
            if source.read(1) or digest.hexdigest() != reference['sha256']:
                raise LocalStateError('clear_evidence', 'recovery evidence digest differs; retain it')
            verified.seek(0)
            return json.load(verified)
    except (OSError, ValueError, UnicodeError) as exc:
        raise LocalStateError('clear_evidence', 'recovery evidence cannot be verified; retain original request') from exc


def _load_closure(store, identity, operation_id):
    value = read_json(closure_path(store, operation_id))
    if value is None:
        return None
    if value.get('schema_version') == 'ui_clear_closure.v2':
        validate_schema('ui_clear_closure_v2', value)
        if value['project_identity'] != identity or value['operation_id'] != operation_id:
            raise LocalStateConflict('operation_id', 'ended clear belongs to another project or operation')
        if value['record_digest'] != journal.digest({k: v for k, v in value.items() if k != 'record_digest'}):
            raise LocalStateError('clear_closure', 'ended clear marker cannot be verified; retain it')
        marker = value
        value = _read_evidence(store, marker['evidence'])
        validate_schema('ui_clear_closure', value)
        if (value['project_identity'] != identity or value['request']['operation_id'] != operation_id
                or value['request_digest'] != marker['request_digest']
                or value['inspection']['inspection_digest'] != marker['inspection_digest']
                or value['ended_at'] != marker['ended_at']):
            raise LocalStateError('clear_evidence', 'recovery evidence does not match its terminal record')
    validate_schema('ui_clear_closure', value)
    if value['project_identity'] != identity or value['request']['operation_id'] != operation_id:
        raise LocalStateConflict('operation_id', 'ended clear belongs to another project or operation')
    if (value['record_digest'] != journal.digest({k: v for k, v in value.items() if k != 'record_digest'})
            or value['request_digest'] != journal.digest(value['request'])):
        raise LocalStateError('clear_closure', 'ended clear recovery record cannot be verified; retain it')
    return value


def closure(store, identity, req):
    value = _load_closure(store, identity, req['operation_id'])
    if value is not None and value['request'] != req:
        raise LocalStateConflict('operation_id', 'ended clear belongs to a different preserved request')
    return value


def _save_closure(store, value):
    from .store import _atomic_write_bytes
    raw = canonical_json_bytes(value)
    reference = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    path = evidence_path(store, reference['sha256'])
    # Never overwrite an existing content-addressed file, even if damaged.
    if not path.exists():
        _atomic_write_bytes(path, raw)
    if _read_evidence(store, reference) != value:
        raise LocalStateError('clear_evidence', 'saved recovery evidence differs')
    marker = dict(schema_version='ui_clear_closure.v2', project_identity=value['project_identity'],
        operation_id=value['request']['operation_id'], request_digest=value['request_digest'],
        inspection_digest=value['inspection']['inspection_digest'], evidence=reference,
        ended_at=value['ended_at'])
    marker['record_digest'] = journal.digest(marker)
    validate_schema('ui_clear_closure_v2', marker)
    # Only this atomic final write is the commit fence. Orphan evidence is not
    # an ended operation; failures leave the original request recoverable.
    write_json(closure_path(store, marker['operation_id']), marker)


def refuse_ended(store, identity, req):
    if closure(store, identity, req) is not None:
        raise LocalStateConflict('operation_id', 'this clear operation has ended; inspect it and create a new plan')


def _receipt(store, req):
    # Unlike the legacy convenience reader, inspection cannot interpret a
    # damaged or truncated log as evidence that an operation never completed.
    path = journal._clear_log_path(store)
    if not path.exists():
        return None
    raw = path.read_bytes()
    if len(raw) > MAX_BODY:
        raise LocalStateError('clear_log', 'clear log exceeds inspection limit; retain original evidence')
    entries = []
    for line in raw.decode('utf-8').splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        validate_schema('ui_clear_result', entry)
        if entry['operation_id'] == req['operation_id']:
            if (entry['plan_id'] != req['plan_id'] or entry['manifest_digest'] != req['manifest_digest']
                    or entry['scope'] != req['input']['scope'] or entry.get('input_digest') != journal.digest(req['input'])):
                raise LocalStateConflict('operation_id', 'receipt cannot verify this exact preserved request')
            entries.append(entry)
    if any(entry != entries[0] for entry in entries[1:]):
        raise LocalStateConflict('operation_id', 'conflicting clear receipts; retain the original evidence')
    return entries[0] if entries else None


def _backup(store, doc, identity, req):
    from .personal_recovery import _validate_record
    from .snapshots import FixedSnapshotReader
    value = read_json(journal._clear_backup_path(store, req['manifest_digest']))
    if value is None:
        return None
    validate_schema('ui_clear_backup', value)
    items = [{k: r[k] for k in ('kind', 'id', 'etag')} for r in value['records']]
    manifest = dict(project_id=doc['project_id'], project_identity=identity, scope='current_project', items=items)
    if (value['manifest_digest'] != req['manifest_digest']
            or journal.digest(manifest) != req['manifest_digest'] or len({(r['kind'], r['id']) for r in items}) != len(items)):
        raise LocalStateError('backup', 'backup does not match this project and manifest')
    reader = FixedSnapshotReader(store, head_revision=doc['revision_id'])
    for row in value['records']:
        _validate_record(store, doc, identity, row, snapshot_reader=reader)
    return value


def _backup_evidence(store, doc, identity, req):
    """Validate bytes first; a shared manifest slot does not imply operation ownership."""
    backup = _backup(store, doc, identity, req)
    summary = dict(available=False, count=0, digest=None)
    if backup is None:
        return None, summary
    if backup['operation_id'] != req['operation_id']:
        summary['related_operation'] = dict(operation_id=backup['operation_id'],
            manifest_digest=backup['manifest_digest'], digest=journal.digest(backup), count=len(backup['records']))
        return None, summary
    return backup, dict(available=True, count=len(backup['records']), digest=journal.digest(backup))


def _inspection(store, doc, identity, req):
    value = dict(schema_version='ui_clear_inspection.v1', project_identity=identity, request=req,
        request_digest=journal.digest(req), status='no_execution_evidence', receipt=None,
        backup=None, items=[], current_state=None, reason=None, recovery_url=None)
    backup = None
    ended = closure(store, identity, req)
    if ended:
        value.update(status='ended', backup=ended['inspection']['backup'],
            recovery_url='/api/ui-state/clear-recovery/' + req['operation_id'] + '/download')
    else:
        try:
            receipt = _receipt(store, req)
            if receipt:
                # A valid committed receipt proves success independently of a
                # missing/changed backup. Backup availability is a separate fact.
                value.update(status='cleared', receipt=receipt)
                try:
                    backup, value['backup'] = _backup_evidence(store, doc, identity, req)
                except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                    value['backup'] = {'available': False, 'count': 0, 'digest': None}
            else:
                backup, summary = _backup_evidence(store, doc, identity, req)
                value['backup'] = summary if backup is not None or summary.get('related_operation') else None
                _, _, live, blockers, kept_out, live_digest = journal._clear_manifest(store, doc, identity,
                    dict(project_id=doc['project_id'], scope='current_project', draft_ids='all', reading_preferences=True))
                value['current_state'] = dict(manifest_digest=live_digest, items=live, blockers=blockers, kept_out=kept_out)
                if backup is not None:
                    from .personal_recovery import _current
                    value.update(status='incomplete', backup={'available': True, 'count': len(backup['records']),
                        'digest': journal.digest(backup)})
                    for row in backup['records']:
                        current = _current(store.project_root, store, doc, identity, row)
                        etag = current.get('etag', current.get('digest')) if current else None
                        value['items'].append({k: row[k] for k in ('kind', 'id', 'etag')} | {
                            'current_etag': etag, 'state': 'absent' if current is None else
                            ('unchanged' if etag == row['etag'] else 'changed')})
        except LocalStateConflict:
            raise
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            value.update(status='unverifiable', reason=str(exc), backup=None)
            backup = None
    value['inspection_digest'] = journal.digest(value)
    validate_schema('ui_clear_inspection', value)
    return value, backup


def inspect_clear(project, **kwargs):
    store, doc, identity = journal.context(project)
    req = request(doc, **kwargs)
    with journal.clear_lock(store):
        return _inspection(store, doc, identity, req)[0]


def _ended_result(value):
    return dict(status='ended', project_identity=value['project_identity'], request=value['request'],
        request_digest=value['request_digest'], inspection_digest=value['inspection']['inspection_digest'],
        recovery_url='/api/ui-state/clear-recovery/' + value['request']['operation_id'] + '/download')


def end_clear(project, *, inspection_digest, **kwargs):
    store, doc, identity = journal.context(project)
    req = request(doc, **kwargs)
    with journal.clear_lock(store):
        ended = closure(store, identity, req)
        if ended:
            if ended['inspection']['inspection_digest'] != inspection_digest:
                raise LocalStateConflict('inspection_digest', 'end replay must use its original inspection')
            return _ended_result(ended)
        observed, backup = _inspection(store, doc, identity, req)
        if observed['inspection_digest'] != inspection_digest:
            raise LocalStateConflict('inspection_digest', 'clear evidence changed; inspect the original request again')
        if observed['status'] not in ('no_execution_evidence', 'incomplete'):
            raise LocalStateError('inspection', 'only a verified unresolved clear can be explicitly ended')
        value = dict(schema_version='ui_clear_closure.v1', project_identity=identity, request=req,
            request_digest=journal.digest(req), inspection=observed, backup=backup, ended_at=journal._utc_now_iso())
        value['record_digest'] = journal.digest(value)
        validate_schema('ui_clear_closure', value)
        _save_closure(store, value)
        return _ended_result(value)


def download(project, *, operation_id):
    store, doc, identity = journal.context(project)
    with journal.clear_lock(store):
        value = _load_closure(store, identity, operation_id)
        if value is None:
            raise LocalStateError('operation_id', 'no ended clear recovery record exists')
        validate_schema('ui_clear_closure', value)
        if value['request']['operation_id'] != operation_id:
            raise LocalStateError('operation_id', 'recovery record has a different operation identity')
        request(doc, **value['request'])
        value = closure(store, identity, value['request'])
        return canonical_json_bytes(value), 'deck-master-clear-recovery-' + operation_id + '.json'


def listing(project):
    store, doc, identity = journal.context(project)
    rows = []
    with journal.clear_lock(store):
        directory = safe_path(store.deck_root, 'workbench', 'clear-closures')
        for path in sorted(directory.glob('*.json')):
            operation_id = path.stem
            try:
                value = _load_closure(store, identity, operation_id)
                validate_schema('ui_clear_closure', value)
                if value['request']['operation_id'] != operation_id:
                    raise LocalStateError('operation_id', 'mismatched recovery record')
                request(doc, **value['request'])
                value = closure(store, identity, value['request'])
                rows.append(dict(operation_id=operation_id, available=True, ended_at=value['ended_at'],
                    count=len(value['backup']['records']) if value['backup'] else 0))
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                rows.append(dict(operation_id=operation_id, available=False, reason='旧清理恢复记录无法核实，原文件保留。'))
    return {'recoveries': rows}
