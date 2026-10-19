"""N2 review P2: durable preparation exits and existing symlink Host roots."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

from deck_master import activation_transaction as journal
from deck_master import install
from deck_master.errors import InstallationTransactionError
from test_install_transaction_recovery import assert_active, current, kill_at, load, managed, release, root


@pytest.fixture
def layout(tmp_path, monkeypatch):
    prefix, host = tmp_path / 'prefix', tmp_path / 'host/skills'
    monkeypatch.setenv('CODEX_HOME', str(host.parent))
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    release(prefix, 'old', ('deck-master',))
    release(prefix, 'new')
    release(prefix, 'later')
    install.activate(prefix, 'old')
    return prefix, host


@pytest.mark.parametrize('explicit_retry', [True, False])
@pytest.mark.parametrize('point,target', [('preparation_created', 'new'), ('witness_created', 'old')])
def test_real_death_before_prepared_record_resumes_original_request(layout, point, target, explicit_retry):
    prefix, host = layout
    ident = str(uuid.uuid4())
    before = managed(prefix, host)
    kill_at(prefix, host, point=point, ident=ident, target=target)
    interrupted = load(prefix, ident)
    assert interrupted['state'] == 'preparing'
    assert interrupted['request']['transaction_id'] == ident
    assert interrupted['request']['target_release_id'] == target
    assert interrupted['preparations'][-1]['identity'] is None
    assert managed(prefix, host) == before
    residuals = {row['path']: journal.snapshot(Path(row['path'])) for row in interrupted['preparations']}
    assert any(identity is not None for identity in residuals.values())
    report = install.activate(prefix, target, transaction_id=ident if explicit_retry else None)
    assert report['transaction_id'] == ident and report['recovered']
    assert report['transaction_state'] == 'completed'
    completed = load(prefix, ident)
    assert completed['preparation_id'] != interrupted['preparation_id']
    assert completed['preparation_history'][-1]['preparations'] == interrupted['preparations']
    assert {path: journal.snapshot(Path(path)) for path in residuals} == residuals
    assert_active(prefix, host, target, install.PUBLIC_SKILLS if target == 'new' else ('deck-master',))
    after = managed(prefix, host)
    replay = install.activate(prefix, target, transaction_id=ident)
    assert replay['recovered'] and managed(prefix, host) == after


@pytest.mark.parametrize('exception', [KeyboardInterrupt, OSError])
@pytest.mark.parametrize('point,target', [('preparation_created', 'new'), ('witness_created', 'old')])
def test_preparation_exception_preserves_intent_and_same_id_can_complete(layout, monkeypatch, point, target, exception):
    prefix, host = layout
    ident = str(uuid.uuid4())
    before = managed(prefix, host)
    def interrupt(where, record, step=None):
        if where == point:
            raise exception('failure after actual preparation creation')
    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, target, transaction_id=ident)
    assert caught.value.error_code == ('installation_interrupted' if exception is KeyboardInterrupt else 'installation_recovery_unavailable')
    assert load(prefix, ident)['state'] == 'preparing'
    assert managed(prefix, host) == before
    monkeypatch.setattr(journal, 'checkpoint', lambda *args: None)
    result = install.activate(prefix, target, transaction_id=ident)
    assert result['recovered'] and result['transaction_state'] == 'completed'


def test_preparing_request_binding_and_known_external_artifact_are_protected(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    before = managed(prefix, host)
    kill_at(prefix, host, point='witness_created', ident=ident)
    record = load(prefix, ident)
    record_bytes = journal.record_path(root(prefix), ident).read_bytes()
    with pytest.raises(InstallationTransactionError) as changed:
        install.activate(prefix, 'later', transaction_id=ident)
    assert changed.value.error_code == 'installation_transaction_conflict'
    assert journal.record_path(root(prefix), ident).read_bytes() == record_bytes
    prepared = next(row for row in record['preparations'] if row['identity'] is not None)
    path = Path(prepared['path'])
    path.rename(path.with_suffix('.preserved-original'))
    path.write_bytes(b'external occupant must not be adopted or deleted')
    external = journal.snapshot(path)
    with pytest.raises(InstallationTransactionError) as collision:
        install.activate(prefix, 'new', transaction_id=ident)
    assert collision.value.error_code == 'installation_recovery_conflict'
    assert journal.snapshot(path) == external and managed(prefix, host) == before


def test_preparing_optout_recovery_never_resolves_or_writes_host(layout, monkeypatch):
    prefix, host = layout
    before = {str(path): journal.snapshot(path) for path in (host.parent, *host.parent.rglob('*'))}
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='preparation_created', ident=ident, register_host=False)
    monkeypatch.setattr(install, '_codex_skill_root', lambda: (_ for _ in ()).throw(AssertionError('opt-out resolved Host')))
    result = install.activate(prefix, 'new', transaction_id=ident, register_host=False)
    assert result['recovered'] and result['transaction_state'] == 'completed'
    assert {str(path): journal.snapshot(path) for path in (host.parent, *host.parent.rglob('*'))} == before


@pytest.fixture
def rc3_installer(tmp_path):
    baseline = tmp_path / 'rc3_install.py'
    baseline.write_bytes(subprocess.check_output([
        'git', 'show', 'a08bc68c1cbbbc806205104c2bb01f3f096305f0:src/deck_master/install.py'],
        cwd=Path(__file__).resolve().parents[2]))
    spec = importlib.util.spec_from_file_location('deck_master._n2_rc3_install', baseline)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def symlink_layout(tmp_path, monkeypatch, rc3_installer):
    prefix, logical, actual = tmp_path / 'prefix', tmp_path / 'host/skills', tmp_path / 'real-skills'
    logical.parent.mkdir()
    actual.mkdir()
    logical.symlink_to(actual, target_is_directory=True)
    monkeypatch.setenv('CODEX_HOME', str(logical.parent))
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    release(prefix, 'old', ('deck-master',))
    release(prefix, 'new')
    rc3_installer.activate(prefix, 'old')
    assert not list((root(prefix) / 'transactions/activation').glob('*.json'))
    return prefix, logical, actual


@pytest.mark.parametrize('engine', ['baseline', 'rc4'])
def test_real_rc3_to_four_skills_supports_symlink_directory(symlink_layout, rc3_installer, engine):
    prefix, logical, actual = symlink_layout
    alias_before = journal.snapshot(logical)
    module = rc3_installer if engine == 'baseline' else install
    result = module.activate(prefix, 'new')
    assert result['skill_link'] == str(logical / 'deck-master')
    assert [item['skill_link'] for item in result['skill_links']] == [str(logical / name) for name in install.PUBLIC_SKILLS]
    assert_active(prefix, logical, 'new')
    assert current(prefix) == 'releases/new' and os.readlink(root(prefix) / 'previous') == 'releases/old'
    assert journal.snapshot(logical) == alias_before
    if engine == 'rc4':
        assert result['transaction_state'] == 'completed'
        record = load(prefix, result['transaction_id'])
        assert record['request']['host_root'] == str(actual.resolve())
        assert record['host_access_path'] == str(logical)
        before = managed(prefix, logical)
        assert install.activate(prefix, 'new', transaction_id=result['transaction_id'])['recovered']
        assert managed(prefix, logical) == before


def test_symlink_host_directory_recovers_real_action_before_log_death(symlink_layout):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    alias_before = journal.snapshot(logical)
    kill_at(prefix, logical, point='after_action', name='deck-content', ident=ident)
    result = install.activate(prefix, 'new', transaction_id=ident)
    assert result['recovered'] and result['transaction_state'] == 'completed'
    assert_active(prefix, logical, 'new')
    assert journal.snapshot(logical) == alias_before


def test_symlink_access_chain_replacement_during_activation_is_preserved(symlink_layout, monkeypatch):
    prefix, logical, actual = symlink_layout
    replacement = None
    def replace(point, record, step=None):
        nonlocal replacement
        if point == 'after_action' and step['path'] == str(actual / 'deck-content'):
            logical.rename(logical.with_name('retained-original-alias'))
            logical.symlink_to(actual, target_is_directory=True)
            replacement = journal.snapshot(logical)
    monkeypatch.setattr(journal, 'checkpoint', replace)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new')
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'recovery_conflict'
    assert replacement is not None and journal.snapshot(logical) == replacement
    assert current(prefix) == 'releases/old'


def test_completed_receipt_replays_after_alias_inode_replacement(symlink_layout):
    prefix, logical, actual = symlink_layout
    result = install.activate(prefix, 'new')
    logical.rename(logical.with_name('retained-original-alias'))
    logical.symlink_to(actual, target_is_directory=True)
    before = managed(prefix, logical)
    alias = journal.snapshot(logical)
    replay = install.activate(prefix, 'new', transaction_id=result['transaction_id'])
    assert replay['recovered'] and replay['transaction_state'] == 'completed'
    assert replay['skill_link'] == result['skill_link'] == str(logical / 'deck-master')
    assert managed(prefix, logical) == before and journal.snapshot(logical) == alias


def test_previous_prepared_format_without_preparation_namespace_still_recovers(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident)
    record = load(prefix, ident)
    namespace = record['preparation_id']
    for item in record['preparations']:
        path = Path(item['path'])
        path.rename(path.with_name(path.name.replace(namespace, ident)))
    record = json.loads(json.dumps(record).replace('.deck-master-' + namespace + '-', '.deck-master-' + ident + '-'))
    for key in ('preparation_id', 'preparations', 'host_access_path', 'host_access_identity'):
        del record[key]
    journal.record_path(root(prefix), ident).write_text(json.dumps(record))
    result = install.activate(prefix, 'new', transaction_id=ident)
    assert result['recovered'] and result['transaction_state'] == 'completed'
    assert_active(prefix, host, 'new')


@pytest.mark.parametrize('damage', ['move_from', 'move_to', 'removed_path', 'invented_legacy_link'])
def test_damaged_preparing_migration_never_writes_external_paths(layout, tmp_path, damage):
    prefix, host = layout
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep.txt').write_bytes(b'external bytes must remain exactly intact')
    external = {str(path): journal.snapshot(path) for path in (outside, *outside.rglob('*'))}
    before = managed(prefix, host)
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='preparation_created', ident=ident)
    record = load(prefix, ident)
    if damage in ('move_from', 'move_to'):
        record['migration'].update(migrated=True, moved={
            'from': str(outside / 'keep.txt') if damage == 'move_from' else str(root(prefix) / 'current'),
            'to': str(outside / 'stolen') if damage == 'move_to' else str(root(prefix) / 'legacy-companion-P2')})
    else:
        record['migration']['removed_links'] = ['../../outside/keep.txt' if damage == 'removed_path' else 'deck-master']
    path = journal.record_path(root(prefix), ident)
    path.write_text(json.dumps(record))
    preserved = path.read_bytes()
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == ('installation_recovery_conflict' if damage == 'invented_legacy_link' else 'installation_recovery_unavailable')
    assert {str(item): journal.snapshot(item) for item in (outside, *outside.rglob('*'))} == external
    assert managed(prefix, host) == before and path.read_bytes() == preserved
