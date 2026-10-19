"""N2 review P2: durable preparation exits and existing symlink Host roots."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
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


@pytest.mark.parametrize('damage', ['missing', 'same_target_replacement'])
def test_unconfirmed_current_witness_must_survive_inode_reuse(symlink_layout, monkeypatch, damage):
    prefix, logical, _ = symlink_layout
    ident = str(uuid.uuid4())
    kill_at(prefix, logical, point='witness_created', name='current', ident=ident)
    record = load(prefix, ident)
    witness = record['preparations'][-1]
    assert witness['kind'] == 'witness' and witness['identity'] is None
    assert journal.snapshot(Path(witness['path'])) == witness['expected']
    path = root(prefix) / 'current'
    frozen = journal.snapshot(path)
    Path(witness['path']).unlink()
    path.unlink()
    path.symlink_to(frozen['target'])
    if damage == 'same_target_replacement':
        Path(witness['path']).symlink_to(frozen['target'])
    # Deterministically model legitimate dev/inode reuse after both hard links
    # disappeared. Every real external inode is still checked independently.
    snapshot = journal.snapshot
    external_inode = snapshot(path)
    def reused_inode(candidate):
        actual = snapshot(candidate)
        if actual is not None and (actual['dev'], actual['ino']) == (external_inode['dev'], external_inode['ino']):
            return {**actual, 'dev': frozen['dev'], 'ino': frozen['ino']}
        return actual
    monkeypatch.setattr(journal, 'snapshot', reused_inode)
    before = {str(item): snapshot(item) for item in (path, Path(witness['path']))}
    before_managed = {key: snapshot(Path(key)) for key in managed(prefix, logical)}
    journal_path = journal.record_path(root(prefix), ident)
    preserved = journal_path.read_bytes()
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert {str(item): snapshot(item) for item in (path, Path(witness['path']))} == before
    assert {key: snapshot(Path(key)) for key in managed(prefix, logical)} == before_managed
    assert journal_path.read_bytes() == preserved
    assert current(prefix) == 'releases/old'


def test_unconfirmed_after_external_file_is_preserved_without_claiming_ownership(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='preparation_created', ident=ident)
    original = load(prefix, ident)
    item = original['preparations'][-1]
    assert item['kind'] == 'link' and item['identity'] is None
    path = Path(item['path'])
    path.unlink()
    path.write_bytes(b'external preparation occupant; preserve inode, mode and bytes\n')
    external = journal.snapshot(path)
    result = install.activate(prefix, 'new', transaction_id=ident)
    assert result['transaction_state'] == 'completed' and result['recovered']
    assert journal.snapshot(path) == external
    assert load(prefix, ident)['preparation_history'][-1]['preparations'] == original['preparations']
    assert_active(prefix, host, 'new')


@pytest.fixture(scope='session')
def historical_installers(tmp_path_factory):
    """Execute actual historical packages, never manufacture their journals."""
    repository = Path(__file__).resolve().parents[2]
    exports = {}
    for commit in ('bc6bd55a07b249660e6af8ab4b19a147bb2caf14', '001c8f101e07cab1b230e0745a6f0b17fb54882e'):
        destination = tmp_path_factory.mktemp('installer-' + commit)
        archive = subprocess.check_output(['git', 'archive', commit, 'src/deck_master'], cwd=repository)
        subprocess.run(['tar', '-x', '-C', str(destination)], input=archive, check=True)
        exports[commit[:8]] = destination / 'src'
    return exports


HISTORICAL_ACTIVATE = r'''
import json, os, sys
from deck_master import install, activation_transaction as journal
params=json.loads(sys.argv[1])
if params.get('point'):
    def checkpoint(point, record, step=None):
        if point==params['point']: os._exit(91)
    journal.checkpoint=checkpoint
result=install.activate(params['prefix'], params['target'], transaction_id=params['ident'])
print(json.dumps(result))
'''


def historical_activate(source, prefix, target, ident, *, point=None):
    env = {**os.environ, 'PYTHONPATH': str(source)}
    params = {'prefix': str(prefix), 'target': target, 'ident': ident, 'point': point}
    child = subprocess.run([sys.executable, '-c', HISTORICAL_ACTIVATE, json.dumps(params)],
                           env=env, capture_output=True, text=True, timeout=20)
    assert child.returncode == (91 if point else 0), child.stderr
    return None if point else json.loads(child.stdout)


def test_real_legacy_completed_logical_host_request_replays_without_mutation(symlink_layout, historical_installers, monkeypatch, tmp_path):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    original = historical_activate(historical_installers['bc6bd55a'], prefix, 'old', ident)
    assert original['status'] == 'already_active'
    assert historical_activate(historical_installers['bc6bd55a'], prefix, 'old', ident)['recovered']
    record = load(prefix, ident)
    assert record['request']['host_root'] == str(logical) and 'host_access_path' not in record
    assert record['state'] == 'completed'
    before = managed(prefix, logical)
    path = journal.record_path(root(prefix), ident)
    preserved = path.read_bytes()
    replay = install.activate(prefix, 'old', transaction_id=ident)
    assert replay['recovered'] and replay['transaction_state'] == 'completed'
    assert replay['skill_links'] == original['skill_links']
    assert replay['current_install_state'] == 'verified'
    assert path.read_bytes() == preserved and managed(prefix, logical) == before
    # Even a second alias to the very same actual directory is a different
    # legacy request binding. Never resolve arbitrary old paths into ownership.
    other = tmp_path / 'other-host/skills'
    other.parent.mkdir()
    other.symlink_to(actual, target_is_directory=True)
    monkeypatch.setenv('CODEX_HOME', str(other.parent))
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'old', transaction_id=ident)
    assert caught.value.error_code == 'installation_transaction_conflict'
    assert path.read_bytes() == preserved and managed(prefix, logical) == before


@pytest.mark.parametrize('explicit', [True, False])
def test_real_legacy_prepared_logical_host_request_keeps_ownership_checks(symlink_layout, historical_installers, monkeypatch, tmp_path, explicit):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    historical_activate(historical_installers['001c8f10'], prefix, 'new', ident, point='prepared')
    original = load(prefix, ident)
    assert original['request']['host_root'] == str(logical) and 'host_access_path' not in original
    assert original['state'] == 'prepared' and original['inode_anchors']
    path = journal.record_path(root(prefix), ident)
    preserved = path.read_bytes()
    before = managed(prefix, logical)
    other = tmp_path / 'other-host/skills'
    other.parent.mkdir()
    other.symlink_to(actual, target_is_directory=True)
    monkeypatch.setenv('CODEX_HOME', str(other.parent))
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident if explicit else None)
    assert caught.value.error_code == ('installation_transaction_conflict' if explicit else 'installation_transaction_pending')
    assert path.read_bytes() == preserved and managed(prefix, logical) == before
    monkeypatch.setenv('CODEX_HOME', str(logical.parent))
    result = install.activate(prefix, 'new', transaction_id=ident if explicit else None)
    assert result['recovered'] and result['transaction_id'] == ident
    assert result['transaction_state'] == 'completed'
    completed = load(prefix, ident)
    assert completed['request'] == original['request']
    assert [step['path'] for step in completed['steps'] if Path(step['path']).parent == logical] == [
        str(logical / name) for name in install.PUBLIC_SKILLS[1:]]
    for old, applied in zip(original['steps'], completed['steps'], strict=True):
        assert {key: value for key, value in applied.items() if key not in ('step_state', 'observed')} == {
            key: value for key, value in old.items() if key not in ('step_state', 'observed')}
        assert applied['step_state'] == applied['observed']['state'] == 'applied'
        assert journal.snapshot(Path(applied['path'])) == old['expected_after']
    assert_active(prefix, logical, 'new')


def test_real_legacy_prepared_replaced_host_alias_keeps_external_inode(symlink_layout, historical_installers):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    historical_activate(historical_installers['001c8f10'], prefix, 'new', ident, point='prepared')
    logical.rename(logical.with_name('preserved-original-alias'))
    logical.symlink_to(actual, target_is_directory=True)
    external = journal.snapshot(logical)
    before = managed(prefix, logical)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert journal.snapshot(logical) == external and managed(prefix, logical) == before
