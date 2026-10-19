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

from .errors import InstallationTransactionError as Failure
from .store import _atomic_write_bytes

VERSION = 'activation_transaction.v1'
TERMINAL = {'completed', 'rolled_back'}
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
        row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), mode=stat.S_IMODE(info.st_mode))
    elif stat.S_ISDIR(info.st_mode):
        # Legacy directories have exactly the validated manifest; include bytes.
        manifest = path / 'companion-manifest.json'
        if manifest.is_file() and not manifest.is_symlink():
            row['manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            row['manifest_identity'] = snapshot(manifest)
            row['entries'] = sorted(entry.name for entry in path.iterdir())
    return row


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
        value = json.loads(path.read_text())
        if value.get('schema_version') != VERSION or value.get('transaction_id') != record['transaction_id']:
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
        value = json.loads(path.read_text())
        if value.get('schema_version') != VERSION or value.get('transaction_id') != record['transaction_id']:
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
    if (not isinstance(record, dict) or record.get('schema_version') != VERSION
            or record.get('transaction_id') != ident or record.get('prefix') != str(root.parent)
            or record.get('state') not in STATES):
        raise ValueError('unsupported or foreign installation transaction')
    transaction_id(ident)
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
    preparing = record['state'] == 'preparing'
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
    if record['state'] == 'preparing':
        if not isinstance(record.get('preparations'), list):
            raise ValueError('preparing transaction lacks durable preparation intents')
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
    if anchors is None and record['state'] in TERMINAL:
        return  # Historical terminal receipts require no new ownership claim.
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
    if not preparing and found != required:
        raise ValueError('frozen managed path lacks its inode witness')


def read(root, ident):
    path = record_path(root, ident)
    try:
        _check_journal_directory(root)
        if path.is_symlink():
            raise ValueError('transaction record is a symlink')
        record = json.loads(path.read_text())
        _validate_record(root, record, ident)
        return record
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _unavailable(f'cannot verify preserved transaction {path}: {exc}', ident) from exc


def discover(root):
    """Inspect the bounded activation journal, including prepared-before-pointer."""
    pointer = root / 'activation-pending.json'
    _check_journal_directory(root)
    # Captures survive cleanup crashes. An unrecognized captured replacement
    # remains evidence and must not be silently treated as an absent pointer.
    for captured in root.glob('.deck-master-pending-*.before'):
        try:
            if not stat.S_ISREG(captured.lstat().st_mode):
                raise ValueError('captured pending pointer is not regular')
            value = json.loads(captured.read_text())
            if value['schema_version'] != VERSION:
                raise ValueError('unknown captured pending version')
            historical = read(root, transaction_id(value['transaction_id']))
            if historical['state'] not in TERMINAL:
                raise ValueError('captured pending pointer lacks a terminal receipt')
        except (OSError, ValueError, KeyError, TypeError, Failure) as exc:
            raise _unavailable(f'cannot verify preserved pending capture {captured}: {exc}') from exc
    selected = None
    if pointer.exists() or pointer.is_symlink():
        try:
            if pointer.is_symlink():
                raise ValueError('pending pointer is a symlink')
            value = json.loads(pointer.read_text())
            if value['schema_version'] != VERSION:
                raise ValueError('unknown pending version')
            selected = transaction_id(value['transaction_id'])
        except (OSError, ValueError, KeyError, TypeError, Failure) as exc:
            raise _unavailable(f'cannot verify preserved pending pointer: {exc}') from exc
    active = []
    for path in sorted((root / 'transactions/activation').glob('*.json')):
        record = read(root, path.stem)
        if record['state'] not in TERMINAL:
            active.append(record)
    if len(active) > 1:
        raise _unavailable('multiple unfinished installation records; preserve journals and inspect')
    if selected:
        original = read(root, selected)
        if original['state'] in TERMINAL:
            # Completed JSON is authoritative even if pointer deletion failed.
            try:
                clear_pending(root, original)
            except (OSError, ValueError):
                pass
        elif not active or active[0]['transaction_id'] != selected:
            raise _unavailable('pending pointer disagrees with installation journal', selected)
    return active[0] if active else None


class Plan:
    """Prepare finite actions, using the installer's existing preflight result."""

    def __init__(self, root, request):
        self.root = root
        self.record = {'schema_version': VERSION, 'transaction_id': request['transaction_id'],
                       'prefix': str(root.parent), 'request': request, 'state': 'preparing',
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
        try:
            actual = parent_identity(Path(step['path']))
        except OSError:
            actual = None
        if actual != step['parent_identity']:
            self.conflict(step, 'managed parent identity changed externally')
        sources = [step['path']]
        if step['prepared']:
            sources.append(step['prepared']['path'])
        if not self.anchors_intact(*sources):
            self.conflict(step, 'persistent inode witness changed or disappeared')

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
        self.check_parent(step)
        path, backup = Path(step['path']), Path(step['backup'])
        actual, saved = snapshot(path), snapshot(backup)
        before, after = step['before'], step['expected_after']
        prepared = step['prepared']
        ready = snapshot(Path(prepared['path'])) if prepared else None
        # Ordering handles absent-before remove/move and completed rename windows.
        if step['kind'] in ('remove', 'move'):
            if actual is None and saved == before:
                return 'applied'
            if actual == before and saved is None:
                return 'ready'
        else:
            if actual == after and ready is None and saved == before:
                return 'applied'
            if actual == before and saved is None and ready == after:
                return 'ready'
            if before is not None and actual is None and saved == before and ready == after:
                return 'backed_up'
        self.conflict(step, 'path/preparation/backup does not match a provable transaction state')

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
        self.check_parent(step)
        path, backup = Path(step['path']), Path(step['backup'])
        actual, saved = snapshot(path), snapshot(backup)
        before, after = step['before'], step['expected_after']
        prepared = step['prepared']
        ready = snapshot(Path(prepared['path'])) if prepared else None
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

    def finish_pointer(self):
        # A stale pointer does not turn a durable terminal result into a failure.
        try:
            clear_pending(self.root, self.record)
        except (OSError, ValueError):
            pass

    def failure(self, recovered):
        original = self.record.get('failure', {})
        return Failure(original.get('code', 'installation_failed'), original.get('message', 'installation failed and was rolled back'),
                       transaction_id=self.record['transaction_id'], state=self.record['state'],
                       details={'recovered': recovered, 'original_error_type': original.get('type'),
                                'old_state_verified': self.record['state'] == 'rolled_back'})
