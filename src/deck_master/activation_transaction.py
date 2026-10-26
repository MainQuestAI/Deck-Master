"""Durable, finite installation actions (never project state or executable code).

A prepared replacement and a renamed old inode witness both rename windows.
Records and their pending pointer are fsync'd with the store's atomic writer.
Artifact names are unique, adjacent to their managed path, hence same-device.
The caller holds prefix then Host locks throughout preparation and recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import ctypes
import errno
import sys
import uuid
from datetime import datetime, timezone

from .errors import InstallationTransactionError as Failure
from .store import _atomic_write_bytes

VERSION = 'activation_transaction.v1'
RECOVERY_VERSION = 'activation_transaction.v2'
VERSIONS = {VERSION, RECOVERY_VERSION}
TERMINAL = {'completed', 'rolled_back', 'abandoned'}
STATES = {'preparing', 'prepared', 'applying', 'compensating', 'recovery_conflict', *TERMINAL}
KINDS = {'link', 'launcher', 'remove', 'move'}


def _needs_anchor(identity):
    return identity is not None and identity['type'] in (stat.S_IFLNK, stat.S_IFREG)


def _renameat_noreplace(directory, source, destination):
    """One kernel operation; never emulate exclusivity with a path check."""
    libc = ctypes.CDLL(None, use_errno=True)
    name, flags = ('renameatx_np', 4) if sys.platform == 'darwin' else ('renameat2', 1)
    function = getattr(libc, name, None)
    if function is None:
        raise OSError(errno.ENOTSUP, 'atomic no-replace rename is unavailable')
    function.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    function.restype = ctypes.c_int
    if function(directory, os.fsencode(source), directory, os.fsencode(destination), flags):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), os.fsdecode(destination))


def rename_noreplace(source, destination, expected_parent=None):
    """Pin the parent inode and refuse an occupied destination atomically."""
    source, destination = Path(source), Path(destination)
    if source.parent != destination.parent:
        raise ValueError('installation rename must use one adjacent parent')
    directory = os.open(source.parent.resolve(strict=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory)
        if expected_parent is not None and (info.st_dev, info.st_ino) != (
                expected_parent['dev'], expected_parent['ino']):
            raise OSError(errno.ESTALE, 'installation parent changed before rename', str(source.parent))
        _renameat_noreplace(directory, source.name, destination.name)
        os.fsync(directory)
    finally:
        os.close(directory)


def checkpoint(point, record, step=None):
    """Fault-injection seam; production performs no external callbacks."""


def fsync_dir(path):
    handle = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def snapshot(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    row = {'dev': info.st_dev, 'ino': info.st_ino, 'type': stat.S_IFMT(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):
        row['target'] = os.readlink(path)
    elif stat.S_ISREG(info.st_mode):
        raw, actual = read_regular(path)
        if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('installation file changed while reading: ' + str(path))
        row.update(sha256=hashlib.sha256(raw).hexdigest(), mode=stat.S_IMODE(info.st_mode))
    elif stat.S_ISDIR(info.st_mode):
        # Legacy directories have exactly the validated manifest; include bytes.
        manifest = path / 'companion-manifest.json'
        if manifest.is_file() and not manifest.is_symlink():
            row['manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            row['manifest_identity'] = snapshot(manifest)
            row['entries'] = sorted(entry.name for entry in path.iterdir())
    return row


def read_regular(path):
    """Never follow a replaced symlink or block on an installation FIFO."""
    handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(handle, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('installation record must be a regular file: ' + str(path))
        raw = stream.read()
        after = os.fstat(stream.fileno())
        named = Path(path).lstat()
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or (named.st_dev, named.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError('installation record changed while reading: ' + str(path))
        return raw, before


def parent_identity(path):
    rows = []
    for parent in (path.parent, *path.parent.parents):
        info = parent.lstat()
        rows.append({'path': str(parent), 'dev': info.st_dev, 'ino': info.st_ino,
                     'type': stat.S_IFMT(info.st_mode)})
    info = path.parent.stat()
    return {'dev': info.st_dev, 'ino': info.st_ino, 'ancestors': rows}


def transaction_id(value=None):
    if value is None:
        return str(uuid.uuid4())
    try:
        parsed = uuid.UUID(value)
        if str(parsed) != value or parsed.version != 4:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise Failure('invalid_transaction_id', 'transaction ID must be a canonical UUIDv4') from None
    return value


def record_path(root, ident):
    return root / 'transactions/activation' / (ident + '.json')


def save(root, record):
    _check_journal_directory(root)
    _atomic_write_bytes(record_path(root, record['transaction_id']),
                        (json.dumps(record, sort_keys=True, indent=2) + '\n').encode())


def pending(root, record):
    path = root / 'activation-pending.json'
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise _unavailable('pending pointer was replaced externally', record['transaction_id'])
        value = json.loads(read_regular(path)[0])
        if value.get('schema_version') not in VERSIONS or value.get('transaction_id') != record['transaction_id']:
            raise _unavailable('pending pointer is owned by a different or unknown transaction', record['transaction_id'])
        return  # A pointer is immutable; never replace a checked pathname.
    prepared = root / ('.deck-master-pending-' + str(uuid.uuid4()) + '.after')
    with prepared.open('xb') as stream:
        stream.write(json.dumps({'schema_version': VERSION, 'transaction_id': record['transaction_id']}).encode())
        stream.flush()
        os.fsync(stream.fileno())
    fsync_dir(root)
    rename_noreplace(prepared, path, parent_identity(path))


def clear_pending(root, record):
    path = root / 'activation-pending.json'
    identity = snapshot(path)
    if identity is not None:
        if identity['type'] != stat.S_IFREG:
            raise ValueError('pending pointer changed')
        value = json.loads(read_regular(path)[0])
        if value.get('schema_version') not in VERSIONS or value.get('transaction_id') != record['transaction_id']:
            raise ValueError('pending pointer changed')
        # There is no portable compare-and-unlink. Retain the captured inode;
        # if a writer swapped the source, restore it without replacing anything.
        captured = root / ('.deck-master-pending-' + str(uuid.uuid4()) + '.before')
        rename_noreplace(path, captured, parent_identity(path))
        checkpoint('pending_captured', record)
        if snapshot(captured) != identity:
            try:
                rename_noreplace(captured, path, parent_identity(path))
            except OSError as exc:
                raise ValueError('pending pointer changed; preserved at ' + str(captured)) from exc
            raise ValueError('pending pointer changed; restored external replacement')


def _unavailable(message, ident=None):
    return Failure('installation_recovery_unavailable', message,
                   transaction_id=ident, state='unknown')


def _check_journal_directory(root):
    for path in (root, root / 'transactions', root / 'transactions/activation'):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise _unavailable('installation journal directory is not a real managed directory: ' + str(path))


def _validate_record(root, record, ident):
    if (not isinstance(record, dict) or record.get('schema_version') not in VERSIONS
            or record.get('transaction_id') != ident or record.get('prefix') != str(root.parent)
            or record.get('state') not in STATES):
        raise ValueError('unsupported or foreign installation transaction')
    transaction_id(ident)
    if record['state'] == 'abandoned':
        resolution = record.get('abandonment')
        if (record['schema_version'] != RECOVERY_VERSION or not isinstance(resolution, dict)
                or not isinstance(resolution.get('reason'), str) or not resolution['reason'].strip()
                or not isinstance(resolution.get('preserved_paths'), list)
                or not all(isinstance(path, str) for path in resolution['preserved_paths'])
                or resolution.get('previous_state') not in STATES - TERMINAL
                or resolution.get('restoration_verified') is not False):
            raise ValueError('invalid abandonment receipt')
    request = record['request']
    if (request['verb'] not in ('activate', 'rollback') or
            request['prefix'] != str(root.parent) or request['transaction_id'] != ident or
            not isinstance(request['register_host'], bool) or
            not isinstance(request['target_release_id'], str) or
            not isinstance(request['target_release_identity'], str)):
        raise ValueError('invalid frozen request')
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', request['target_release_id']) or
            not re.fullmatch(r'[0-9a-f]{64}', request['target_release_identity']) or
            not isinstance(record.get('steps'), list) or
            not isinstance(record.get('watched'), list) or
            not isinstance(record.get('planned_result'), dict) or
            'old_current' not in record or 'old_previous' not in record or
            'host_identity' not in record or 'host_parent_identity' not in record or
            not isinstance(record.get('apply_cursor', -1), int) or
            not -1 <= record.get('apply_cursor', -1) < max(len(record['steps']), 1)):
        raise ValueError('incomplete or invalid frozen activation plan')
    if record['state'] == 'completed' and not isinstance(record.get('result'), dict):
        raise ValueError('completed transaction lacks its original receipt')
    if record['state'] == 'rolled_back' and not isinstance(record.get('failure'), dict):
        raise ValueError('rolled-back transaction lacks its original failure')
    host = Path(request['host_root']) if request['register_host'] else None
    if host is not None and (not host.is_absolute() or '..' in host.parts):
        raise ValueError('invalid frozen Host root')
    if not request['register_host'] and request['host_root'] is not None:
        raise ValueError('opt-out transaction contains Host root')
    namespace = record.get('preparation_id', ident)
    transaction_id(namespace)
    preparing = (record['state'] == 'preparing' or record['state'] == 'abandoned'
                 and record['abandonment']['previous_state'] == 'preparing')
    migration = record.get('migration', {})
    moved = migration.get('moved')
    removed = migration.get('removed_links', [])
    if (not isinstance(migration.get('migrated'), bool) or not isinstance(removed, list) or
            len(removed) != len(set(removed)) or any(not isinstance(name, str) or
            not re.fullmatch(r'(?:deck|ppt)-[^/]+', name) or Path(name).name != name for name in removed)):
        raise ValueError('invalid frozen legacy migration')
    if moved is not None:
        destination = Path(moved['to'])
        if (not migration['migrated'] or moved['from'] != str(root / 'current') or destination.parent != root or
                not re.fullmatch(r'legacy-companion-[A-Za-z0-9-]+', destination.name)):
            raise ValueError('legacy migration escaped its managed paths')
    if host is None and removed:
        raise ValueError('opt-out migration contains Host actions')
    watched_paths = {root / 'current', root / 'previous', root / 'bin/deck-master'}
    if host:
        watched_paths.update(host / name for name in ('deck-master', 'deck-content', 'deck-design', 'deck-review', *removed))
    for row in record['watched']:
        if Path(row['path']) not in watched_paths or not isinstance(row['parent_identity'], dict):
            raise ValueError('watched path is outside the managed installation')
    if preparing and ({Path(row['path']) for row in record['watched']} != watched_paths or
                      len(record['watched']) != len(watched_paths)):
        raise ValueError('preparing transaction lacks its complete frozen managed state')
    access = record.get('host_access_path')
    if preparing and host is not None and access is None:
        raise ValueError('preparing transaction lacks its frozen Host access chain')
    if access is not None and (host is None or not Path(access).is_absolute() or '..' in Path(access).parts or
                               not isinstance(record.get('host_access_identity'), dict)):
        raise ValueError('invalid frozen Host access chain')
    if preparing and not isinstance(record.get('preparations'), list):
        raise ValueError('preparing transaction lacks durable preparation intents')
    if 'preparations' in record:
        if not isinstance(record['preparations'], list):
            raise ValueError('invalid durable preparation intents')
        allowed = {root, root / 'bin'} | ({host} if host else set())
        for item in record['preparations']:
            path = Path(item['path'])
            if (path.parent not in allowed or
                    not re.fullmatch(r'\.deck-master-' + re.escape(namespace) + r'-[0-9]+\.(?:after|witness)', path.name) or
                    item['kind'] not in ('link', 'launcher', 'witness') or
                    not isinstance(item['expected'], dict) or
                    (item['identity'] is not None and not isinstance(item['identity'], dict))):
                raise ValueError('preparation intent is outside the frozen namespace')
    for index, step in enumerate(record['steps']):
        path = Path(step['path'])
        kind = step['kind']
        if step['step_id'] != str(index) or kind not in KINDS or step['step_state'] not in ('ready', 'applied', 'restored'):
            raise ValueError('unknown installation action')
        core_path = path in (root / 'current', root / 'previous', root / 'bin/deck-master')
        host_path = host is not None and path.parent == host and (
            path.name in ('deck-master', 'deck-content', 'deck-design', 'deck-review') or
            (kind == 'remove' and re.fullmatch(r'(?:deck|ppt)-.*', path.name)
             and (step['before'] or {}).get('target', '').startswith(str(root / 'current/skills') + '/')))
        if not path.is_absolute() or not (core_path or host_path):
            raise ValueError('action is outside managed installation paths')
        if kind == 'launcher' and path != root / 'bin/deck-master':
            raise ValueError('launcher action outside launcher path')
        stem = f'.deck-master-{namespace}-{index}'
        if step['backup'] != str(path.parent / (stem + '.before')) and kind != 'move':
            raise ValueError('invalid backup location')
        if kind == 'move':
            destination = Path(step['backup'])
            if (path != root / 'current' or destination.parent != root or
                    not re.fullmatch(r'legacy-companion-[A-Za-z0-9-]+', destination.name)):
                raise ValueError('invalid companion move')
        if kind in ('link', 'launcher'):
            if step['prepared']['path'] != str(path.parent / (stem + '.after')):
                raise ValueError('invalid preparation location')
            if step['expected_after'] != step['prepared']['identity']:
                raise ValueError('inconsistent prepared identity')
            if kind == 'link':
                expected = ('releases/' + request['target_release_id'] if path == root / 'current' else
                            record['old_current'] if path == root / 'previous' else
                            str(root / 'current/skill' / path.name))
                if step['expected_after']['target'] != expected:
                    raise ValueError('link action disagrees with frozen activation plan')
    for row in record.get('created_directories', []):
        path = Path(row['path'])
        if path != root / 'bin' and not (host is not None and (path == host or path in host.parents)):
            raise ValueError('invalid prepared parent directory')
    anchors = record.get('inode_anchors')
    historical_terminal = anchors is None and record['state'] in TERMINAL
    if historical_terminal:
        anchors = []  # Historical terminal receipts require no new ownership claim.
    if not isinstance(anchors, list):
        raise ValueError('unfinished transaction lacks persistent inode witnesses')
    required = []
    for step in record['steps']:
        required.append((step['path'], step['before']))
        if step['prepared']:
            required.append((step['prepared']['path'], step['prepared']['identity']))
    required.extend((row['path'], row['before']) for row in record['watched'])
    if preparing:
        required.extend((row['path'], row['identity']) for row in record['preparations'] if row['kind'] != 'witness')
    required = {(path, json.dumps(identity, sort_keys=True)) for path, identity in required if _needs_anchor(identity)}
    found = set()
    for index, anchor in enumerate(anchors):
        source = Path(anchor['source'])
        if anchor['path'] != str(source.parent / f'.deck-master-{namespace}-{index}.witness'):
            raise ValueError('invalid inode witness location')
        item = (str(source), json.dumps(anchor['identity'], sort_keys=True))
        if item not in required or item in found:
            raise ValueError('inode witness disagrees with frozen managed plan')
        found.add(item)
    if not preparing and not historical_terminal and found != required:
        raise ValueError('frozen managed path lacks its inode witness')
    artifacts = {item['path']: item['identity'] for item in record.get('preparations', [])
                 if item.get('identity') is not None}
    artifacts.update({item['path']: item['identity'] for item in anchors})
    for index, item in enumerate(record.get('cleanup', [])):
        source = Path(item['path'])
        if (record['state'] not in {'completed', 'rolled_back'} or artifacts.get(item['path']) != item['identity']
                or item['captured'] != str(source.parent / f'.deck-master-{namespace}-cleanup-{index}')
                or item['state'] not in ('pending', 'cleaned', 'preserved')):
            raise ValueError('invalid terminal cleanup ownership')


def read(root, ident):
    path = record_path(root, ident)
    try:
        _check_journal_directory(root)
        if path.is_symlink():
            raise ValueError('transaction record is a symlink')
        record = json.loads(read_regular(path)[0])
        _validate_record(root, record, ident)
        return record
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _unavailable(f'cannot verify preserved transaction {path}: {exc}', ident) from exc


def collect(root):
    """Collect readable receipts and unreadable evidence without changing either.

    Partial discovery never establishes that no request is pending. Consumers
    may display trusted neighbours, but only strict discover authorizes recovery.
    """
    records, diagnostics = [], []
    complete = True

    def problem(path, reason, ident=None, *, incomplete=True):
        nonlocal complete
        complete = complete and not incomplete
        diagnostics.append({'path': str(path), 'transaction_id': ident,
                            'error_code': 'installation_recovery_unavailable', 'reason': reason})

    def entries(path):
        try:
            return sorted(path.iterdir())
        except FileNotFoundError:
            return []
        except OSError as exc:
            problem(path, 'cannot enumerate installation evidence: ' + str(exc))
            return []

    try:
        _check_journal_directory(root)
    except Failure as exc:
        problem(root, str(exc))
        return {'records': [], 'diagnostics': diagnostics, 'discovery_complete': False,
                'recovery_blocked': True, 'unfinished_transaction_ids': [],
                'pending': {'state': 'unknown', 'transaction_id': None, 'pointer_transaction_id': None}}
    for path in entries(root / 'transactions/activation'):
        if not path.name.endswith('.json'):
            continue
        try:
            records.append(read(root, path.stem))
        except Failure as exc:
            problem(path, str(exc), path.stem)
    by_id = {record['transaction_id']: record for record in records}

    def pointer_id(path):
        value = json.loads(read_regular(path)[0])
        if value['schema_version'] not in VERSIONS:
            raise ValueError('unknown pending version')
        ident = transaction_id(value['transaction_id'])
        if ident not in by_id:
            raise ValueError('pending pointer references an unverifiable journal: ' + ident)
        return ident

    # Captures are retained evidence, including after a pending-clear crash.
    for captured in entries(root):
        if not (captured.name.startswith('.deck-master-pending-') and captured.name.endswith('.before')):
            continue
        try:
            ident = pointer_id(captured)
            if by_id[ident]['state'] not in TERMINAL:
                raise ValueError('captured pending pointer lacks a terminal receipt')
        except (OSError, ValueError, KeyError, TypeError, AttributeError, Failure) as exc:
            problem(captured, f'cannot verify preserved pending capture {captured}: {exc}')
    selected = None
    pointer = root / 'activation-pending.json'
    try:
        pointer.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        problem(pointer, 'cannot verify preserved pending pointer: ' + str(exc))
    else:
        try:
            selected = pointer_id(pointer)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, Failure) as exc:
            problem(pointer, 'cannot verify preserved pending pointer: ' + str(exc))
    active = [record['transaction_id'] for record in records if record['state'] not in TERMINAL]
    if len(active) > 1:
        problem(root / 'transactions/activation', 'multiple unfinished installation records; preserve journals and inspect',
                incomplete=False)
    if selected and by_id[selected]['state'] not in TERMINAL and active != [selected]:
        problem(pointer, 'pending pointer disagrees with installation journal', selected, incomplete=False)
    pending = {'state': ('unknown' if diagnostics else 'verified' if active else 'terminal' if selected else 'none'),
               'transaction_id': active[0] if len(active) == 1 else selected,
               'pointer_transaction_id': selected}
    return {'records': records, 'diagnostics': diagnostics, 'discovery_complete': complete,
            'recovery_blocked': bool(diagnostics), 'unfinished_transaction_ids': active, 'pending': pending}


def discover(root, *, repair_pointer=True):
    """Require complete trusted discovery before any installation recovery."""
    result = collect(root)
    if result['recovery_blocked']:
        first = result['diagnostics'][0]
        raise _unavailable(first['reason'], first['transaction_id'])
    by_id = {record['transaction_id']: record for record in result['records']}
    selected = result['pending']['pointer_transaction_id']
    if selected and by_id[selected]['state'] in TERMINAL and repair_pointer:
        # Completed JSON is authoritative even if pointer deletion failed.
        try:
            clear_pending(root, by_id[selected])
        except (OSError, ValueError):
            pass
    active = result['unfinished_transaction_ids']
    return by_id[active[0]] if active else None


def preserved_paths(record):
    """Finite paths from a validated journal; no glob-based cleanup authority."""
    paths = {row['path'] for row in record['watched']}
    for step in record['steps']:
        paths.add(step['path']); paths.add(step['backup'])
        if step['prepared']:
            paths.add(step['prepared']['path'])
    for preparation in [record, *record.get('preparation_history', [])]:
        paths.update(item['path'] for item in preparation.get('preparations', []))
    paths.update(item['path'] for item in record.get('inode_anchors', []))
    return sorted(paths)


def abandon(root, record, reason):
    """Terminate only this verified journal; never repair or delete managed data."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('abandon requires a nonempty reason')
    if record['state'] == 'abandoned':
        if record['abandonment']['reason'] != reason:
            raise Failure('installation_transaction_conflict', 'abandon retry must retain its original reason',
                          transaction_id=record['transaction_id'], state='abandoned')
    elif record['state'] in TERMINAL:
        raise Failure('installation_transaction_conflict', 'a completed or rolled-back transaction cannot be abandoned',
                      transaction_id=record['transaction_id'], state=record['state'])
    else:
        record.update(schema_version=RECOVERY_VERSION, state='abandoned', abandonment={
            'reason': reason, 'occurred_at': datetime.now(timezone.utc).isoformat(),
            'previous_state': record['state'], 'preserved_paths': preserved_paths(record),
            'restoration_verified': False})
        save(root, record)
        checkpoint('abandoned', record)
    try:
        clear_pending(root, record)
    except ValueError as exc:
        # The abandoned receipt is already durable; a pointer that now belongs
        # to another transaction is never this transaction's to clear.
        raise Failure('installation_transaction_conflict',
                      f'the abandoned receipt is durable, but the pending pointer was not cleared: {exc}',
                      transaction_id=record['transaction_id'], state='abandoned',
                      details={'pending_pointer': 'retained'}) from exc
    return record


class Plan:
    """Prepare finite actions, using the installer's existing preflight result."""

    def __init__(self, root, request):
        self.root = root
        self.record = {'schema_version': VERSION, 'transaction_id': request['transaction_id'],
                       'prefix': str(root.parent), 'request': request, 'state': 'preparing',
                       'cleanup_protocol': 'installation_cleanup.v1',
                       'preparation_id': transaction_id(), 'preparations': [],
                       'steps': [], 'created_directories': [], 'inode_anchors': []}
        self.virtual = {}

    def intent(self, path, kind, expected):
        item = {'path': str(path), 'kind': kind, 'expected': expected, 'identity': None}
        self.record['preparations'].append(item)
        save(self.root, self.record)
        return item

    def anchor(self, path, identity):
        """Keep the inode allocated across death and unlink/recreate attacks."""
        if not _needs_anchor(identity):
            return
        if any(row['source'] == str(path) and row['identity'] == identity for row in self.record['inode_anchors']):
            return
        index = len(self.record['inode_anchors'])
        anchor = path.parent / f'.deck-master-{self.record["preparation_id"]}-{index}.witness'
        item = self.intent(anchor, 'witness', identity)
        os.link(path, anchor, follow_symlinks=False)
        fsync_dir(path.parent)
        checkpoint('witness_created', self.record, {'path': str(path), 'kind': 'witness'})
        if snapshot(path) != identity or snapshot(anchor) != identity:
            raise Failure('installation_recovery_conflict', 'path changed while preparing its inode witness',
                          transaction_id=self.record['transaction_id'], state='prepared',
                          details={'path': str(path), 'witness': str(anchor)})
        self.record['inode_anchors'].append({'source': str(path), 'path': str(anchor), 'identity': identity})
        item['identity'] = identity
        save(self.root, self.record)

    def mkdir(self, path):
        if path.is_dir():
            return
        self.mkdir(path.parent)
        path.mkdir()
        fsync_dir(path.parent)
        identity = snapshot(path)
        self.record['created_directories'].append({
            'step_id': 'directory-' + str(len(self.record['created_directories'])),
            'kind': 'mkdir', 'path': str(path), 'parent_identity': parent_identity(path),
            'before': None, 'prepared': {'path': str(path), 'identity': identity},
            'expected_after': identity, 'identity': identity, 'step_state': 'applied',
            'observed': {'state': 'created_parent'}})

    def add(self, kind, path, target=None, destination=None):
        self.mkdir(path.parent)
        index = str(len(self.record['steps']))
        stem = f'.deck-master-{self.record["preparation_id"]}-{index}'
        before = self.virtual.get(str(path), snapshot(path))
        step = {'step_id': index, 'kind': kind, 'path': str(path), 'before': before,
                'parent_identity': parent_identity(path), 'step_state': 'ready', 'observed': None,
                'backup': str(destination or path.parent / (stem + '.before')), 'prepared': None,
                'expected_after': None}
        if snapshot(Path(step['backup'])) is not None:
            raise ValueError('transaction backup path occupied')
        self.anchor(path, before)
        if kind in ('link', 'launcher'):
            prepared = path.parent / (stem + '.after')
            item = self.intent(prepared, kind, {'target': str(target)} if kind == 'link' else
                               {'sha256': hashlib.sha256(target.encode()).hexdigest(), 'mode': 0o755})
            if kind == 'link':
                prepared.symlink_to(target)
            else:
                with prepared.open('xb') as stream:
                    stream.write(target.encode())
                    stream.flush()
                    os.fchmod(stream.fileno(), 0o755)
                    os.fsync(stream.fileno())
            fsync_dir(path.parent)
            checkpoint('preparation_created', self.record, step)
            step['prepared'] = {'path': str(prepared), 'identity': snapshot(prepared)}
            step['expected_after'] = step['prepared']['identity']
            item['identity'] = step['expected_after']
            self.anchor(prepared, step['expected_after'])
        self.record['steps'].append(step)
        self.virtual[str(path)] = step['expected_after']
        save(self.root, self.record)
        return step

    def begin(self):
        # Persist directory entries for the journal itself before its pointer.
        directory = record_path(self.root, self.record['transaction_id']).parent
        missing = []
        parent = directory
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for path in reversed(missing):
            path.mkdir()
            fsync_dir(path.parent)
        save(self.root, self.record)

    def persist(self):
        self.record['state'] = 'prepared'
        save(self.root, self.record)
        checkpoint('prepared', self.record)
        pending(self.root, self.record)
        checkpoint('pending', self.record)
        return self.record


def _ownership_problem(record, step):
    """Read the same parent and inode-witness proof for status and recovery."""
    try:
        if parent_identity(Path(step['path'])) != step['parent_identity']:
            return 'managed parent identity changed externally'
        sources = [step['path']]
        if step['prepared']:
            sources.append(step['prepared']['path'])
        if any(snapshot(Path(anchor['path'])) != anchor['identity']
               for anchor in record.get('inode_anchors', []) if anchor['source'] in sources):
            return 'persistent inode witness changed or disappeared'
    except (OSError, ValueError) as exc:
        return 'parent or inode witness cannot be verified: ' + str(exc)
    return None


def observe_step(record, step, *, direction='apply', projection=None):
    """Pure phase observation; never update a step, journal, pointer or path.

    A repeated path may currently belong to another action. Its projected phase
    still verifies this action's own backup/preparation and ownership witnesses.
    """
    row = {'path': step['path'], 'state': 'conflict'}
    try:
        reason = _ownership_problem(record, step)
        if reason:
            return {**row, 'reason': reason}
        actual = snapshot(Path(step['path']))
        saved = snapshot(Path(step['backup']))
        ready = snapshot(Path(step['prepared']['path'])) if step['prepared'] else None
        row.update(actual=actual, backup=saved, prepared=ready)
        before, after = step['before'], step['expected_after']
        if projection == 'waiting':
            if saved is None and ready == after:
                return {**row, 'state': 'waiting'}
        elif projection in ('superseded', 'deferred'):
            if saved == before and ready is None:
                return {**row, 'state': projection}
        elif projection == 'restored':
            if saved is None and ready in (None, after):
                return {**row, 'state': 'restored'}
        elif direction == 'restore':
            if actual == before and saved is None and ready in (None, after):
                return {**row, 'state': 'restored'}
            if step['kind'] in ('remove', 'move') and actual is None and saved == before:
                return {**row, 'state': 'applied'}
            if step['prepared'] and saved == before and ready in (None, after):
                if actual == after and ready is None:
                    return {**row, 'state': 'applied'}
                if actual is None:
                    return {**row, 'state': 'backed_up'}
        elif step['kind'] in ('remove', 'move'):
            if actual is None and saved == before:
                return {**row, 'state': 'applied'}
            if actual == before and saved is None:
                return {**row, 'state': 'ready'}
        else:
            if actual == after and ready is None and saved == before:
                return {**row, 'state': 'applied'}
            if actual == before and saved is None and ready == after:
                return {**row, 'state': 'ready'}
            if before is not None and actual is None and saved == before and ready == after:
                return {**row, 'state': 'backed_up'}
    except (OSError, ValueError) as exc:
        return {**row, 'reason': 'current ownership cannot be verified: ' + str(exc)}
    return {**row, 'reason': 'path/preparation/backup does not match a provable transaction state'}


def observe_transaction(record):
    """Observe the live action frontier, including reverse and repeated paths."""
    if record['state'] in TERMINAL:
        return [{'path': step['path'], 'state': 'historical'} for step in record['steps']], []
    direction = 'restore' if record['state'] in ('compensating', 'recovery_conflict') else 'apply'
    cursor = record.get('apply_cursor', -1)
    groups = {}
    for index, step in enumerate(record['steps']):
        groups.setdefault(step['path'], []).append(index)
    phases = []
    for index, step in enumerate(record['steps']):
        indices = groups[step['path']]
        reached = [item for item in indices if item <= cursor]
        projection = None
        if direction == 'apply':
            frontier = max(reached) if reached else indices[0]
            if index < frontier:
                projection = 'superseded'
            elif index > frontier:
                projection = 'waiting'
        else:
            remaining = [item for item in reached if record['steps'][item]['step_state'] != 'restored']
            frontier = max(remaining) if remaining else min(reached) if reached else indices[0]
            if index > cursor:
                projection = 'waiting' if index != frontier else None
                phase_direction = 'apply'
            else:
                phase_direction = 'restore'
                if index < frontier:
                    projection = 'deferred'
                elif index > frontier:
                    projection = 'restored'
            phases.append(observe_step(record, step, direction=phase_direction, projection=projection))
            continue
        phases.append(observe_step(record, step, direction=direction, projection=projection))
    conflicts = [phase for phase in phases if phase['state'] == 'conflict']
    for watched in record.get('watched', []):
        if watched['path'] in groups:
            continue
        try:
            reason = _ownership_problem(record, {**watched, 'prepared': None})
            if reason or snapshot(Path(watched['path'])) != watched['before']:
                conflicts.append({'path': watched['path'], 'state': 'conflict',
                                  'reason': reason or 'watched path differs from the frozen transaction'})
        except (OSError, ValueError) as exc:
            conflicts.append({'path': watched['path'], 'state': 'conflict',
                              'reason': 'watched ownership cannot be verified: ' + str(exc)})
    return phases, conflicts


class Transaction:
    def __init__(self, root, record):
        self.root, self.record = root, record

    def save(self):
        save(self.root, self.record)

    def conflict(self, step, reason):
        step['observed'] = {'reason': reason, 'actual': snapshot(Path(step['path'])),
                            'backup': snapshot(Path(step['backup']))}
        raise Failure('installation_recovery_conflict', reason,
                      transaction_id=self.record['transaction_id'], state=self.record['state'],
                      details={'path': step['path'], 'expected_before': step['before'],
                               'expected_after': step['expected_after'], 'observed': step['observed'],
                               'backup': step['backup']})

    def check_parent(self, step):
        reason = _ownership_problem(self.record, step)
        if reason:
            self.conflict(step, reason)

    def anchors_intact(self, *sources):
        return all(snapshot(Path(anchor['path'])) == anchor['identity']
                   for anchor in self.record['inode_anchors'] if anchor['source'] in sources)

    def move(self, step, source, destination):
        try:
            rename_noreplace(source, destination, step['parent_identity'])
        except OSError as exc:
            if exc.errno in (errno.EEXIST, errno.ENOTEMPTY, errno.ESTALE,
                             errno.ENOENT, errno.ELOOP, errno.ENOTDIR):
                self.conflict(step, 'external path/parent change at atomic rename: ' + str(exc))
            raise

    def inspect(self, step):
        phase = observe_step(self.record, step)
        if phase['state'] == 'conflict':
            self.conflict(step, phase['reason'])
        return phase['state']

    def apply(self, step):
        state = self.inspect(step)
        path, backup = Path(step['path']), Path(step['backup'])
        if state != 'applied':
            checkpoint('before_action', self.record, step)
            state = self.inspect(step)
            if state == 'ready' and step['before'] is not None:
                self.move(step, path, backup)
                checkpoint('after_backup', self.record, step)
            if step['prepared']:
                if self.inspect(step) not in ('ready', 'backed_up'):
                    self.conflict(step, 'state changed before publishing prepared item')
                self.move(step, step['prepared']['path'], path)
            checkpoint('after_action', self.record, step)
            if self.inspect(step) != 'applied':
                self.conflict(step, 'action failed verification')
        step['step_state'] = 'applied'
        step['observed'] = {'state': 'applied', 'actual': snapshot(path)}
        self.save()
        checkpoint('applied', self.record, step)

    def restore(self, step):
        phase = observe_step(self.record, step, direction='restore')
        if phase['state'] == 'conflict':
            self.conflict(step, phase['reason'])
        path, backup = Path(step['path']), Path(step['backup'])
        actual, saved = phase['actual'], phase['backup']
        before, after = step['before'], step['expected_after']
        prepared = step['prepared']
        ready = phase['prepared']
        # Restored path is the original inode; never accept equal bytes alone.
        if actual == before and saved is None:
            if prepared and ready not in (None, after):
                self.conflict(step, 'prepared item replaced externally during compensation')
        elif step['kind'] in ('remove', 'move') and actual is None and saved == before:
            checkpoint('before_restore', self.record, step)
            self.check_parent(step)
            if snapshot(path) is not None or snapshot(backup) != before:
                self.conflict(step, 'external change before restoring original backup')
            self.move(step, backup, path)
            checkpoint('after_restore', self.record, step)
        elif prepared and saved == before and actual in (None, after) and ready in (None, after):
            checkpoint('before_restore', self.record, step)
            self.check_parent(step)
            if snapshot(path) != actual or snapshot(backup) != saved or snapshot(Path(prepared['path'])) != ready:
                self.conflict(step, 'external change before compensation rename')
            if actual == after:
                # Move the new inode back to its own witnessed preparation slot.
                if ready is not None:
                    self.conflict(step, 'both prepared and published identities are present')
                self.move(step, path, prepared['path'])
                checkpoint('after_unpublish', self.record, step)
            if before is not None:
                self.check_parent(step)
                if snapshot(path) is not None or snapshot(backup) != before:
                    self.conflict(step, 'external path appeared before restoring original backup')
                self.move(step, backup, path)
            checkpoint('after_restore', self.record, step)
        else:
            self.conflict(step, 'cannot restore without overwriting an external path')
        step['step_state'] = 'restored'
        step['observed'] = {'state': 'restored', 'actual': snapshot(path)}
        self.save()
        checkpoint('restored', self.record, step)

    def compensate(self):
        failures = []
        reached = self.record.get('apply_cursor', -1)
        for step in reversed(self.record['steps'][:reached + 1]):
            if step['step_state'] == 'restored':
                continue
            try:
                self.restore(step)
            except Failure as exc:
                failures.append(exc.payload()['error'])
        if failures:
            self.record.update(state='recovery_conflict', conflicts=failures)
            self.save()
            raise Failure('installation_recovery_conflict', 'compensation is incomplete; preserved external paths and backups',
                          transaction_id=self.record['transaction_id'], state='recovery_conflict',
                          details={'conflicts': failures, 'original_failure': self.record.get('failure'),
                                   'old_state_verified': False})
        # Repeated paths (legacy remove then replace) require the first before.
        originals = {row['path']: row['before'] for row in self.record.get('watched', [])}
        for step in self.record['steps']:
            originals.setdefault(step['path'], step['before'])
        for path, identity in originals.items():
            if snapshot(Path(path)) != identity:
                self.record.update(state='recovery_conflict', conflicts=[{'path': path, 'reason': 'old state verification failed'}])
                self.save()
                raise Failure('installation_recovery_conflict', 'old managed state could not be verified',
                              transaction_id=self.record['transaction_id'], state='recovery_conflict',
                              details={'conflicts': self.record['conflicts']})
        for watched in self.record.get('watched', []):
            try:
                unchanged = (parent_identity(Path(watched['path'])) == watched['parent_identity'] and
                             self.anchors_intact(watched['path']))
            except OSError:
                unchanged = False
            if not unchanged:
                self.record.update(state='recovery_conflict', conflicts=[{'path': watched['path'], 'reason': 'old parent identity changed'}])
                self.save()
                raise Failure('installation_recovery_conflict', 'old parent identity could not be verified',
                              transaction_id=self.record['transaction_id'], state='recovery_conflict',
                              details={'conflicts': self.record['conflicts']})
        # Every original path has been verified before claiming rolled_back.
        conflict = self.record.get('failure', {}).get('code') == 'installation_recovery_conflict'
        self.record['state'] = 'recovery_conflict' if conflict else 'rolled_back'
        self.record['restoration_verified'] = True
        self.save()
        if not conflict:
            checkpoint('rolled_back', self.record)
            self.finish_pointer()
            self.cleanup()

    def finish_pointer(self):
        # A stale pointer does not turn a durable terminal result into a failure.
        try:
            clear_pending(self.root, self.record)
        except (OSError, ValueError):
            pass

    def cleanup(self):
        """Remove only confirmed temporary inodes after a durable terminal result.

        Backups, unacknowledged preparations and earlier namespaces stay intact.
        Capture intents survive a crash between rename and unlink. Unknown or
        externally replaced paths are preserved, never a reason to undo success.
        """
        if (self.record['state'] not in {'completed', 'rolled_back'}
                or self.record.get('cleanup_protocol') != 'installation_cleanup.v1'):
            return
        if 'cleanup' not in self.record:
            artifacts = {item['path']: item['identity'] for item in self.record.get('preparations', [])
                         if item.get('identity') is not None}
            artifacts.update({item['path']: item['identity'] for item in self.record.get('inode_anchors', [])})
            namespace = self.record.get('preparation_id', self.record['transaction_id'])
            self.record['cleanup'] = [
                {'path': path, 'identity': identity, 'state': 'pending',
                 'parent_identity': parent_identity(Path(path)),
                 'captured': str(Path(path).parent / f'.deck-master-{namespace}-cleanup-{index}')}
                for index, (path, identity) in enumerate(artifacts.items())]
            self.save()
        for item in self.record['cleanup']:
            if item['state'] != 'pending':
                continue
            path, captured = Path(item['path']), Path(item['captured'])
            try:
                if parent_identity(path) != item['parent_identity']:
                    raise ValueError('temporary parent changed')
                actual, saved = snapshot(path), snapshot(captured)
                if actual is None and saved is None:
                    item['state'] = 'cleaned'
                else:
                    if saved is None:
                        if actual != item['identity']:
                            raise ValueError('temporary inode changed')
                        rename_noreplace(path, captured, item['parent_identity'])
                        checkpoint('cleanup_captured', self.record, item)
                    elif actual is not None:
                        raise ValueError('cleanup capture or source is externally occupied')
                    if snapshot(captured) != item['identity']:
                        if snapshot(path) is None:
                            rename_noreplace(captured, path, item['parent_identity'])
                        raise ValueError('captured temporary inode changed')
                    directory = os.open(captured.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    try:
                        info = os.fstat(directory)
                        if (info.st_dev, info.st_ino) != (item['parent_identity']['dev'], item['parent_identity']['ino']):
                            raise ValueError('cleanup parent changed')
                        os.unlink(captured.name, dir_fd=directory)
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                    item['state'] = 'cleaned'
            except (OSError, ValueError) as exc:
                item.update(state='preserved', reason=str(exc))
            self.save()
            checkpoint('cleaned', self.record, item)

    def failure(self, recovered):
        original = self.record.get('failure', {})
        return Failure(original.get('code', 'installation_failed'), original.get('message', 'installation failed and was rolled back'),
                       transaction_id=self.record['transaction_id'], state=self.record['state'],
                       details={'recovered': recovered, 'original_error_type': original.get('type'),
                                'old_state_verified': self.record['state'] == 'rolled_back'})
