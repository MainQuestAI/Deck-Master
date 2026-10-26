"""Explicit recovery of this project's registered clear backups; no business writes."""
from __future__ import annotations

import copy
import re
from . import ui_journal as journal, gallery_state, overview_state, result_reading
from .local_state import LocalStateConflict, LocalStateError, local_lock, read_json, safe_path, write_json
from .models import canonical_json_bytes, validate_schema
from .snapshots import FixedSnapshotReader, load_snapshot

LABELS = {'draft': '个人草稿', 'gallery_state': '画廊选择', 'reading_position': '阅读位置',
          'overview_preferences': '总览阅读设置', 'result_reading': '结果已读记录'}
IDS = {'gallery_state': 'gallery.json', 'reading_position': 'position.json',
       'overview_preferences': 'overview.json', 'result_reading': 'result-reading.json'}


def _backup(project, backup_id, *, context=None):
    if not isinstance(backup_id, str) or not re.fullmatch('[a-f0-9]{16}', backup_id):
        raise LocalStateError('backup_id', 'select a registered backup of this project')
    if context is None:
        store, doc, identity = journal.context(project)
        entries_by_id = {e['manifest_digest'][:16]: e for e in journal._read_clear_log(store)}
        reader = FixedSnapshotReader(store, head_revision=doc["revision_id"])
    else:
        store, doc, identity, entries_by_id, reader = context
    entry = entries_by_id.get(backup_id)
    if entry is None:
        raise LocalStateError('backup_id', 'backup is not registered in this project')
    value = read_json(journal._clear_backup_path(store, entry['manifest_digest']))
    validate_schema('ui_clear_backup', value)
    items = [{k: row[k] for k in ('kind', 'id', 'etag')} for row in value['records']]
    manifest = {'project_id': doc['project_id'], 'project_identity': identity,
                'scope': 'current_project', 'items': items}
    if (value['operation_id'] != entry['operation_id'] or items != entry['cleared']
            or value['manifest_digest'] != entry['manifest_digest']
            or journal.digest(manifest) != value['manifest_digest']):
        raise LocalStateError('backup', 'backup identity or manifest does not match this project')
    if len({(v['kind'], v['id']) for v in items}) != len(items):
        raise LocalStateError('backup', 'duplicate personal records')
    for row in value['records']:
        _validate_record(store, doc, identity, row, snapshot_reader=reader)
    return store, doc, identity, value


def _validate_record(store, doc, identity, row, *, snapshot_reader=None):
    read = snapshot_reader.load if snapshot_reader else lambda revision: load_snapshot(store, revision)
    kind, record = row['kind'], row['record']
    if kind != 'draft' and row['id'] != IDS[kind]:
        raise LocalStateError('backup', 'invalid personal record identity')
    if kind == 'draft':
        validate_schema('ui_draft_record', record)
        journal._validate(store, doc, identity, record['draft'], snapshot_reader=snapshot_reader)
        valid = (record['draft']['draft_id'] == row['id']
                 and record['digest'] == journal.digest(record['draft'])
                 and record['etag'] == journal.digest({'sequence': record['updated_sequence'], 'digest': record['digest']}))
    elif kind == 'gallery_state':
        gallery_state._validate(store, doc, identity, record['state'], snapshot_reader=snapshot_reader)
        valid = record['etag'] == journal.digest({'state': record['state'], 'sequence': record['sequence']})
    elif kind == 'overview_preferences':
        valid = (record['project_id'] == doc['project_id'] and record['project_identity'] == identity
                 and record['etag'] == overview_state._etag(record) and len(record['states']) <= overview_state.MAX_READINGS)
        for state in record['states']:
            overview_state._validate(doc, identity, state)
            read(state['revision_id'])
    elif kind == 'result_reading':
        validate_schema('result_reading', record)
        valid = (record['project_id'] == doc['project_id'] and record['project_identity'] == identity
                 and record['etag'] == result_reading._etag(record))
    else:
        position = record['position']; validate_schema('ui_position', position)
        read(position['revision'])
        valid = (position['project_id'] == doc['project_id'] and position['project_identity'] == identity
                 and record['digest'] == journal.digest(position))
    if not valid or row['etag'] != record.get('etag', record.get('digest')):
        raise LocalStateError('backup', 'personal record hash or project identity is invalid')


def listing(project):
    store, doc, identity = journal.context(project)
    log = journal._read_clear_log(store)
    reader = FixedSnapshotReader(store, head_revision=doc["revision_id"])
    context = (store, doc, identity, {e['manifest_digest'][:16]: e for e in log}, reader)
    entries, seen = [], set()
    for entry in reversed(log):
        key = entry['manifest_digest'][:16]
        if key in seen: continue
        seen.add(key)
        try:
            _, _, _, backup = _backup(project, key, context=context)
            entries.append({'backup_id': key, 'cleared_at': backup['cleared_at'],
                            'count': len(backup['records']), 'available': True})
        except (ValueError, RuntimeError, OSError, KeyError, TypeError):
            entries.append({'backup_id': key, 'cleared_at': entry['cleared_at'],
                            'available': False, 'reason': '备份无法核实，原文件保留。'})
    return {'backups': entries}


def download(project, *, backup_id):
    *_, value = _backup(project, backup_id)
    return canonical_json_bytes(value), 'deck-master-personal-backup-' + backup_id + '.json'


def _current(project, store, doc, identity, row):
    kind = row['kind']
    if kind == 'draft': return journal._read(store, row['id'])
    if kind == 'gallery_state': return gallery_state._read(store, doc, identity)
    if kind == 'overview_preferences': return overview_state._read(store, doc, identity)
    if kind == 'result_reading': return result_reading._read(store, doc, identity)
    return journal.read_position(project)


def plan(project, *, backup_id):
    store, doc, identity, backup = _backup(project, backup_id)
    rows = []
    for row in backup['records']:
        try:
            current = _current(project, store, doc, identity, row)
            kind = row['kind']
            empty = current is None or (kind == 'overview_preferences' and not current['states']) or (kind == 'result_reading' and not current['seen'])
            action = 'restore' if empty else ('copy' if kind == 'draft' and current['digest'] != row['record']['digest'] else 'keep')
            item = {'kind': kind, 'id': row['id'], 'label': LABELS[kind], 'action': action,
                    'current': current, 'backup': row['record']}
            if kind == 'draft':
                item['copy_id'] = 'recovered-clear-' + journal.digest([backup_id, row['id']])[:32]
                item['existing_copy'] = journal._read(store, item['copy_id'])
                # A lost response or repeated preview never duplicates the backup;
                # later edits to that recovered copy are also left untouched.
                if item['existing_copy'] is not None: item['action'] = 'keep'
            rows.append(item)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError):
            rows.append({'kind': row['kind'], 'id': row['id'], 'label': LABELS[row['kind']],
                         'action': 'keep', 'current': {'unreadable': True}, 'backup': row['record']})
    value = {'backup_id': backup_id, 'project_identity': identity, 'records': rows}
    return {**value, 'plan_digest': journal.digest(value)}


def _restore(project, store, doc, identity, item):
    kind, record, expected = item['kind'], item['backup'], item['current']
    if kind == 'draft':
        draft = copy.deepcopy(record['draft'])
        if item['action'] == 'copy': draft['draft_id'] = item['copy_id']
        # This is a registered same-project private backup, not a portable
        # customer artifact. Valid user text may itself contain a local path.
        journal._validate(store, doc, identity, draft)
        return journal.save(project, draft=draft)
    if kind == 'gallery_state':
        return gallery_state.save(project, state=record['state'], expected_etag=expected['etag'] if expected else None)
    lock_name = {'reading_position': 'position.lock', 'overview_preferences': 'overview.lock', 'result_reading': 'result-reading.lock'}[kind]
    with local_lock(safe_path(store.deck_root, 'workbench', lock_name)):
        current = _current(project, store, doc, identity, item)
        if current != expected:
            raise LocalStateConflict('current', 'personal state changed; retain current records and preview again')
        if kind == 'overview_preferences':
            states = overview_state._fit(doc, identity, copy.deepcopy(record['states']), current)
            overview_state._write(store, doc, identity, states, current)
        elif kind == 'result_reading':
            updated = {**record, 'sequence': current['sequence'] + 1}
            updated['etag'] = result_reading._etag(updated)
            write_json(result_reading._file(store), updated)
        else:
            write_json(journal._position_path(store), record)
    return {'status': 'saved'}


def restore(project, *, backup_id, plan_digest):
    store, doc, identity, _ = _backup(project, backup_id)
    with local_lock(safe_path(store.deck_root, 'workbench', 'personal-recovery.lock')):
        planned = plan(project, backup_id=backup_id)
        if planned['plan_digest'] != plan_digest:
            raise LocalStateConflict('plan_digest', 'personal state changed after preview; nothing restored, preview again')
        outcomes = []
        for item in planned['records']:
            outcome = {'kind': item['kind'], 'id': item['id'], 'status': 'kept'}
            if item['action'] != 'keep':
                try:
                    result = _restore(project, store, doc, identity, item)
                    outcome.update(status='restored', draft_id=result.get('record', {}).get('draft', {}).get('draft_id'))
                except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                    outcome.update(status='failed', reason=str(exc))
            outcomes.append(outcome)
        return {'status': 'partial' if any(v['status'] == 'failed' for v in outcomes) else 'restored', 'records': outcomes}
