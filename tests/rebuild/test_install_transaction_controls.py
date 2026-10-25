"""Public recovery controls on real subprocess-death fixtures; isolated Host/prefix."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from deck_master import activation_transaction as journal, install
from deck_master.errors import InstallationTransactionError
from test_install_transaction_recovery import (assert_active, kill_at, layout, load, managed, root)  # noqa: F401


def scene(prefix, host):
    return {str(path): journal.snapshot(path) for directory in (root(prefix), host)
            for path in (directory, *directory.rglob('*'))}


def test_status_is_read_only_and_lists_phase_conflicts_and_actions(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    before = scene(prefix, host)
    result = install.transaction_status(prefix, transaction_id=ident)
    assert result['pending_transaction_id'] == ident
    row, = result['transactions']
    assert row['transaction_state'] == 'prepared' and row['conflicts'] == []
    assert row['available_actions'] == ['resume', 'rollback', 'abandon']
    assert scene(prefix, host) == before


def test_resume_uses_frozen_request_and_host_instead_of_environment(layout, monkeypatch):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_backup', name='current', ident=ident)
    monkeypatch.setenv('CODEX_HOME', str(prefix / 'unrelated-host'))
    monkeypatch.setattr(install, '_codex_skill_root', lambda: (_ for _ in ()).throw(AssertionError('used current Host config')))
    result = install.recover_transaction(prefix, transaction_id=ident, action='resume')
    assert result['recovered'] and result['transaction_state'] == 'completed'
    assert_active(prefix, host, 'new')


@pytest.mark.parametrize('point', ['prepared', 'after_backup', 'after_action', 'applied'])
def test_explicit_rollback_restores_old_inodes_and_replays(layout, point):
    prefix, host = layout
    ident = str(uuid.uuid4())
    before = managed(prefix, host)
    kill_at(prefix, host, point=point, name='current' if point != 'prepared' else None, ident=ident)
    result = install.recover_transaction(prefix, transaction_id=ident, action='rollback')
    assert result['status'] == 'rolled_back' and result['restoration_verified']
    assert managed(prefix, host) == before
    assert not (root(prefix) / 'activation-pending.json').exists()
    assert install.recover_transaction(prefix, transaction_id=ident, action='rollback')['status'] == 'rolled_back'
    assert managed(prefix, host) == before


@pytest.mark.parametrize('point', ['witness_created', 'pending', 'after_action'])
def test_abandon_preserves_every_managed_object_and_backup_but_clears_own_pending(layout, point):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, name='current' if point != 'pending' else None, ident=ident)
    before_record = load(prefix, ident)
    paths = journal.preserved_paths(before_record)
    before = {path: journal.snapshot(Path(path)) for path in paths}
    result = install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='Preserve external recovery evidence')
    assert result['status'] == result['transaction_state'] == 'abandoned'
    assert result['current_install_state'] == 'conflict' and result['installation_requires_attention']
    assert result['restoration_verified'] is False
    assert {path: journal.snapshot(Path(path)) for path in paths} == before
    assert not (root(prefix) / 'activation-pending.json').exists()
    saved = journal.read(root(prefix), ident)
    assert saved['schema_version'] == 'activation_transaction.v2'
    assert saved['abandonment']['preserved_paths'] == paths
    assert saved['abandonment']['previous_state'] == before_record['state']
    assert install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='Preserve external recovery evidence')['status'] == 'abandoned'
    with pytest.raises(InstallationTransactionError):
        install.recover_transaction(prefix, transaction_id=ident, action='resume')


def test_abandon_external_replacement_retains_conflict_then_new_request_still_checks_ownership(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_action', name='current', ident=ident)
    current = root(prefix) / 'current'
    current.unlink(); current.write_text('external owner')
    before = journal.snapshot(current)
    scene_before = scene(prefix, host)
    current_status = install.transaction_status(prefix, transaction_id=ident)['transactions'][0]
    assert any(row['path'] == str(current) for row in current_status['conflicts'])
    assert scene(prefix, host) == scene_before
    install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='External owner takes over current')
    assert journal.snapshot(current) == before
    status = install.transaction_status(prefix, transaction_id=ident)['transactions'][0]
    assert status['current_install_state'] == 'conflict'
    with pytest.raises(ValueError):
        install.activate(prefix, 'later')
    assert journal.snapshot(current) == before


@pytest.mark.parametrize('action', ['resume', 'rollback', 'abandon'])
def test_optout_public_recovery_never_resolves_or_touches_host(layout, monkeypatch, action):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident, register_host=False)
    before = {str(path): journal.snapshot(path) for path in (host.parent, *host.parent.rglob('*'))}
    monkeypatch.setattr(install, '_codex_skill_root', lambda: (_ for _ in ()).throw(AssertionError('opt-out resolved Host')))
    result = install.recover_transaction(prefix, transaction_id=ident, action=action,
        reason='Preserve opt-out recovery' if action == 'abandon' else None)
    assert result['transaction_state'] == {'resume': 'completed', 'rollback': 'rolled_back', 'abandon': 'abandoned'}[action]
    assert {str(path): journal.snapshot(path) for path in (host.parent, *host.parent.rglob('*'))} == before


def test_explicit_rollback_conflict_keeps_pending_and_external_inode(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_action', name='current', ident=ident)
    current = root(prefix) / 'current'
    current.unlink(); current.write_text('external current owner')
    external = journal.snapshot(current)
    with pytest.raises(InstallationTransactionError) as caught:
        install.recover_transaction(prefix, transaction_id=ident, action='rollback')
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert load(prefix, ident)['state'] == 'recovery_conflict'
    assert (root(prefix) / 'activation-pending.json').exists()
    assert journal.snapshot(current) == external


def test_abandon_cannot_clear_a_corrupt_or_different_pending_pointer(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    pointer = root(prefix) / 'activation-pending.json'
    pointer.write_text(json.dumps({'schema_version': journal.VERSION, 'transaction_id': str(uuid.uuid4())}))
    before = scene(prefix, host)
    with pytest.raises(InstallationTransactionError):
        install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='No force unlock')
    assert scene(prefix, host) == before


@pytest.mark.parametrize('damage', ['json', 'version', 'symlink', 'fifo'])
def test_untrusted_journal_has_no_abandon_force_unlock(layout, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    path = journal.record_path(root(prefix), ident)
    if damage == 'json':
        path.write_text('{broken')
    elif damage == 'version':
        value = load(prefix, ident); value['schema_version'] = 'activation_transaction.v99'
        path.write_text(json.dumps(value))
    else:
        preserved = path.with_suffix('.preserved')
        path.rename(preserved)
        if damage == 'symlink': path.symlink_to(preserved)
        else: os.mkfifo(path)
    before = managed(prefix, host)
    pointer = (root(prefix) / 'activation-pending.json').read_bytes()
    with pytest.raises(InstallationTransactionError) as caught:
        install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='Cannot bypass validation')
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert (root(prefix) / 'activation-pending.json').read_bytes() == pointer
    assert managed(prefix, host) == before


RECOVERY_CHILD = r'''
import json, os, sys
from deck_master import install, activation_transaction as journal
p=json.loads(sys.argv[1])
def checkpoint(point, record, step=None):
    if point==p['point']: os._exit(92)
journal.checkpoint=checkpoint
install.recover_transaction(p['prefix'], transaction_id=p['ident'], action=p['action'], reason=p.get('reason'))
'''


@pytest.mark.parametrize('action,point', [('abandon', 'abandoned'), ('abandon', 'pending_captured'), ('rollback', 'after_unpublish'),
                                          ('resume', 'cleanup_captured')])
def test_recovery_process_death_retries_exact_action(layout, action, point):
    prefix, host = layout
    ident = str(uuid.uuid4())
    before = managed(prefix, host)
    kill_at(prefix, host, point='after_action', name='current', ident=ident)
    reason = 'Preserve interrupted recovery' if action == 'abandon' else None
    params = {'prefix': str(prefix), 'ident': ident, 'action': action, 'point': point, 'reason': reason}
    child = subprocess.run([sys.executable, '-c', RECOVERY_CHILD, json.dumps(params)], capture_output=True, text=True, timeout=20)
    assert child.returncode == 92, child.stderr
    result = install.recover_transaction(prefix, transaction_id=ident, action=action, reason=reason)
    expected = {'abandon': 'abandoned', 'rollback': 'rolled_back', 'resume': 'completed'}[action]
    assert result['transaction_state'] == expected
    if action == 'rollback': assert managed(prefix, host) == before
    if action == 'resume': assert_active(prefix, host, 'new')


def test_terminal_cleanup_removes_only_confirmed_namespace_and_preserves_backups(layout):
    prefix, host = layout
    result = install.activate(prefix, 'new')
    record = load(prefix, result['transaction_id'])
    assert record['cleanup'] and all(row['state'] == 'cleaned' for row in record['cleanup'])
    assert all(journal.snapshot(Path(row['path'])) is None and journal.snapshot(Path(row['captured'])) is None for row in record['cleanup'])
    old_backup = next(step for step in record['steps'] if Path(step['path']).name == 'current')
    assert journal.snapshot(Path(old_backup['backup'])) == old_backup['before']


def test_terminal_cleanup_preserves_replacement_and_historical_receipt(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='completed', ident=ident)
    record = load(prefix, ident)
    path = Path(record['inode_anchors'][0]['path'])
    original = path.with_suffix('.preserved-original')
    path.rename(original)
    path.write_text('external temporary-path owner')
    replaced = journal.snapshot(path)
    replay = install.recover_transaction(prefix, transaction_id=ident, action='resume')
    assert replay['transaction_state'] == 'completed'
    assert journal.snapshot(path) == replaced and original.exists()
    cleanup = load(prefix, ident)['cleanup']
    assert next(row for row in cleanup if row['path'] == str(path))['state'] == 'preserved'
    assert_active(prefix, host, 'new')


def test_abandoned_record_requires_the_new_explicit_version(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='Version boundary')
    path = journal.record_path(root(prefix), ident)
    record = load(prefix, ident)
    record['schema_version'] = 'activation_transaction.v1'
    path.write_text(json.dumps(record))
    with pytest.raises(InstallationTransactionError, match='invalid abandonment'):
        install.transaction_status(prefix, transaction_id=ident)


def test_new_install_after_abandon_still_exposes_unresolved_health(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    install.recover_transaction(prefix, transaction_id=ident, action='abandon', reason='Leave the old plan intact')
    result = install.activate(prefix, 'later')
    assert result['transaction_state'] == 'completed'
    assert result['current_install_state'] == 'conflict' and ident in result['abandoned_transactions']
    assert_active(prefix, host, 'later')


def test_lock_replacement_after_wait_is_rejected_before_activation(layout, monkeypatch):
    prefix, host = layout
    before = managed(prefix, host)
    real_flock = install.fcntl.flock
    lock = root(prefix) / 'install.lock'
    def replaced(handle, operation):
        real_flock(handle, operation)
        lock.rename(lock.with_suffix('.preserved'))
        lock.write_text('another lock inode')
    monkeypatch.setattr(install.fcntl, 'flock', replaced)
    with pytest.raises(InstallationTransactionError, match='lock or its parent changed'):
        install.activate(prefix, 'new')
    assert managed(prefix, host) == before and lock.read_text() == 'another lock inode'


def test_install_transaction_cli_status_and_abandon(layout, capsys):
    from deck_master.cli import main
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    assert main(['install', 'transaction', 'status', '--prefix', str(prefix), '--transaction-id', ident]) == 0
    assert json.loads(capsys.readouterr().out)['transactions'][0]['transaction_state'] == 'prepared'
    assert main(['install', 'transaction', 'recover', '--prefix', str(prefix), '--transaction-id', ident,
                 '--action', 'abandon', '--reason', 'CLI preserves the scene']) == 0
    assert json.loads(capsys.readouterr().out)['transaction_state'] == 'abandoned'
