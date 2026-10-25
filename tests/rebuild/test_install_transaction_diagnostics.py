"""Read-only recovery diagnostics retain incomplete discovery and rename phases."""
from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

import pytest

from deck_master import activation_transaction as journal, install
from deck_master.errors import InstallationTransactionError
from test_install_transaction_recovery import assert_active, kill_at, layout, load, release, root  # noqa: F401


def scene(directory):
    return {str(path): journal.snapshot(path) for path in (directory, *directory.rglob('*'))}


def damage_record(prefix, ident, damage):
    path = journal.record_path(root(prefix), ident)
    if damage == 'json':
        path.write_text('{damaged')
    elif damage == 'version':
        record = load(prefix, ident)
        record['schema_version'] = 'activation_transaction.v99'
        path.write_text(json.dumps(record))
    else:
        original = path.with_suffix('.preserved')
        path.rename(original)
        if damage == 'symlink':
            path.symlink_to(original)
        else:
            os.mkfifo(path)


@pytest.mark.parametrize('damage', ['json', 'version', 'symlink', 'fifo'])
def test_bad_neighbor_is_collectable_but_all_recovery_is_globally_blocked(layout, tmp_path, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    neighbor = next(path.stem for path in (root(prefix) / 'transactions/activation').glob('*.json') if path.stem != ident)
    damage_record(prefix, neighbor, damage)
    before = scene(tmp_path)
    listed = install.transaction_status(prefix)
    selected = install.transaction_status(prefix, transaction_id=ident)
    broken = install.transaction_status(prefix, transaction_id=neighbor)
    assert listed['discovery_complete'] is False and listed['recovery_blocked']
    assert listed['pending']['state'] == 'unknown'
    healthy = next(row for row in listed['transactions'] if row['transaction_id'] == ident)
    assert healthy['verification'] == 'verified' and healthy['available_actions'] == []
    assert selected['transactions'][0]['transaction_id'] == ident
    assert selected['transactions'][0]['available_actions'] == []
    bad, = broken['transactions']
    assert bad['verification'] == 'unverifiable' and bad['transaction_state'] == 'unknown'
    assert bad['available_actions'] == [] and bad['reason']
    assert any(item.get('transaction_id') == neighbor for item in listed['diagnostics'])
    assert scene(tmp_path) == before
    for action in ('resume', 'rollback', 'abandon'):
        with pytest.raises(InstallationTransactionError) as caught:
            install.recover_transaction(prefix, transaction_id=ident, action=action,
                reason='No global trust bypass' if action == 'abandon' else None)
        assert caught.value.error_code == 'installation_recovery_unavailable'
    assert scene(tmp_path) == before


@pytest.mark.parametrize('damage', ['json', 'version', 'symlink', 'foreign_id'])
def test_unknown_pending_is_not_reported_as_no_pending(layout, tmp_path, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    pointer = root(prefix) / 'activation-pending.json'
    if damage == 'json':
        pointer.write_text('{damaged')
    elif damage == 'symlink':
        original = pointer.with_suffix('.preserved')
        pointer.rename(original); pointer.symlink_to(original)
    else:
        pointer.write_text(json.dumps({'schema_version': 'activation_transaction.v99' if damage == 'version' else journal.VERSION,
            'transaction_id': str(uuid.uuid4()) if damage == 'foreign_id' else ident}))
    before = scene(tmp_path)
    result = install.transaction_status(prefix, transaction_id=ident)
    assert result['pending']['state'] == 'unknown'
    assert result['recovery_blocked'] and result['diagnostics']
    assert result['transactions'][0]['verification'] == 'verified'
    assert result['transactions'][0]['available_actions'] == []
    assert scene(tmp_path) == before


def test_multiple_unfinished_records_remain_visible_without_recovery_permission(layout, tmp_path):
    prefix, host = layout
    ident, other = str(uuid.uuid4()), str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    extra = load(prefix, ident)
    extra['transaction_id'] = extra['request']['transaction_id'] = other
    journal.save(root(prefix), extra)
    before = scene(tmp_path)
    result = install.transaction_status(prefix)
    assert result['discovery_complete'] and result['recovery_blocked']
    assert result['pending']['state'] == 'unknown'
    assert {row['transaction_id'] for row in result['transactions']} >= {ident, other}
    assert all(row['available_actions'] == [] for row in result['transactions'])
    assert scene(tmp_path) == before
    with pytest.raises(InstallationTransactionError):
        install.recover_transaction(prefix, transaction_id=ident, action='resume')
    assert scene(tmp_path) == before


def test_backup_rename_window_is_readable_and_recovery_uses_the_same_phase(layout, tmp_path):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_backup', name='current', ident=ident)
    before = scene(tmp_path)
    result = install.transaction_status(prefix, transaction_id=ident)
    row, = result['transactions']
    assert row['conflicts'] == []
    action = next(item for item in row['actions'] if Path(item['path']).name == 'current')
    assert action['phase']['state'] == 'backed_up'
    assert 'resume' in row['available_actions']
    assert result['pending']['state'] == 'verified' and not result['recovery_blocked']
    assert scene(tmp_path) == before
    assert install.recover_transaction(prefix, transaction_id=ident, action='resume')['transaction_state'] == 'completed'
    assert_active(prefix, host, 'new')


@pytest.mark.parametrize('damage', ['backup', 'prepared', 'witness', 'replacement'])
def test_incomplete_rename_proof_is_a_readonly_conflict(layout, tmp_path, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_backup', name='current', ident=ident)
    record = load(prefix, ident)
    step = next(item for item in record['steps'] if Path(item['path']).name == 'current')
    if damage == 'backup':
        Path(step['backup']).unlink()
    elif damage == 'prepared':
        Path(step['prepared']['path']).unlink()
    elif damage == 'witness':
        Path(next(item['path'] for item in record['inode_anchors'] if item['source'] == step['path'])).unlink()
    else:
        Path(step['path']).write_text('external current owner')
    before = scene(tmp_path)
    row, = install.transaction_status(prefix, transaction_id=ident)['transactions']
    assert any(item['path'] == step['path'] for item in row['conflicts'])
    assert next(item for item in row['actions'] if item['path'] == step['path'])['phase']['state'] == 'conflict'
    assert row['available_actions'] == ['rollback', 'abandon']
    assert scene(tmp_path) == before


def test_changed_host_parent_is_a_readonly_conflict(layout, tmp_path):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    host.rename(host.with_name('preserved-skills'))
    host.mkdir()
    before = scene(tmp_path)
    row, = install.transaction_status(prefix, transaction_id=ident)['transactions']
    assert any('parent' in item['reason'] for item in row['conflicts'])
    assert row['available_actions'] == ['rollback', 'abandon']
    assert scene(tmp_path) == before


@pytest.mark.parametrize('point', ['before_restore', 'after_unpublish', 'after_restore', 'restored'])
def test_compensation_rename_windows_are_observed_without_false_conflict(layout, tmp_path, point):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, name='current', ident=ident, interrupt_first=True)
    before = scene(tmp_path)
    row, = install.transaction_status(prefix, transaction_id=ident)['transactions']
    assert row['transaction_state'] == 'compensating' and row['conflicts'] == []
    assert scene(tmp_path) == before
    result = install.recover_transaction(prefix, transaction_id=ident, action='rollback')
    assert result['transaction_state'] == 'rolled_back' and result['restoration_verified']


def test_historical_terminal_receipt_does_not_claim_its_old_paths_are_current(layout, tmp_path):
    prefix, host = layout
    old = install.activate(prefix, 'new')['transaction_id']
    install.activate(prefix, 'later')
    before = scene(tmp_path)
    result = install.transaction_status(prefix, transaction_id=old)
    row, = result['transactions']
    assert row['conflicts'] == [] and row['observed_current_release_id'] == 'later'
    assert result['pending']['state'] == 'none'
    assert scene(tmp_path) == before


def test_absent_pointer_with_bad_neighbor_stays_unknown_and_selected_absence_is_readable(layout, tmp_path):
    prefix, host = layout
    healthy = next(path.stem for path in (root(prefix) / 'transactions/activation').glob('*.json'))
    damaged, absent = str(uuid.uuid4()), str(uuid.uuid4())
    journal.record_path(root(prefix), damaged).write_text('{incomplete')
    before = scene(tmp_path)
    status = install.transaction_status(prefix, transaction_id=healthy)
    assert status['pending_transaction_id'] is None and status['pending']['state'] == 'unknown'
    assert status['transactions'][0]['verification'] == 'verified'
    missing = install.transaction_status(prefix, transaction_id=absent)
    assert missing['transactions'][0]['verification'] == 'unverifiable'
    assert missing['transactions'][0]['available_actions'] == []
    assert scene(tmp_path) == before


@pytest.mark.parametrize('point,name', [('pending', None), ('after_action', 'current'), ('after_action', 'deck-master')])
def test_legacy_repeated_paths_wait_for_their_own_frontier(tmp_path, monkeypatch, point, name):
    from test_install_host_skill import _build_legacy_layout
    prefix, host = tmp_path / 'prefix', tmp_path / 'host/skills'
    monkeypatch.setenv('CODEX_HOME', str(host.parent))
    _build_legacy_layout(prefix, host.parent)
    release(prefix, 'new')
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, name=name, ident=ident)
    before = scene(tmp_path)
    row, = install.transaction_status(prefix, transaction_id=ident)['transactions']
    assert row['conflicts'] == []
    assert any(item['phase']['state'] == 'waiting' for item in row['actions'])
    assert scene(tmp_path) == before
    assert install.recover_transaction(prefix, transaction_id=ident, action='resume')['transaction_state'] == 'completed'
    assert_active(prefix, host, 'new')


def test_unverifiable_pending_capture_does_not_hide_a_healthy_receipt(layout, tmp_path):
    prefix, host = layout
    healthy = next(path.stem for path in (root(prefix) / 'transactions/activation').glob('*.json'))
    captured = root(prefix) / ('.deck-master-pending-' + str(uuid.uuid4()) + '.before')
    captured.write_text('{external captured content')
    before = scene(tmp_path)
    result = install.transaction_status(prefix, transaction_id=healthy)
    assert result['recovery_blocked'] and result['pending']['state'] == 'unknown'
    assert result['transactions'][0]['verification'] == 'verified'
    assert any(item['path'] == str(captured) for item in result['diagnostics'])
    assert scene(tmp_path) == before
