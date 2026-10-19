"""RC4 N2: actual subprocess exits; synthetic releases and Host only.

The seam fires *after* rename and *before* step_state persistence. Assertions
inspect actual inode/target/hash/mode and durable state, not callback counts.
"""
from __future__ import annotations

import json
import errno
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from deck_master import activation_transaction as journal
from deck_master import install
from deck_master.errors import InstallationTransactionError


def release(prefix, name, skills=install.PUBLIC_SKILLS):
    root = prefix / '.deck-master/releases' / name
    root.mkdir(parents=True)
    (root / 'release.json').write_text(json.dumps({'status': 'candidate_ready', 'release_id': name}))
    for skill in skills:
        path = root / 'skill' / skill / 'SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text(f'{skill} {name}\n')
    return root


@pytest.fixture
def layout(tmp_path, monkeypatch):
    prefix = tmp_path / 'isolated prefix'
    host = tmp_path / 'synthetic-host/skills'
    monkeypatch.setenv('CODEX_HOME', str(host.parent))
    release(prefix, 'old', ('deck-master',))
    release(prefix, 'new')
    release(prefix, 'bare', ())
    release(prefix, 'later')
    install.activate(prefix, 'old')
    return prefix, host


def root(prefix):
    return prefix / '.deck-master'


def managed(prefix, host=None):
    paths = [root(prefix) / name for name in ('current', 'previous', 'bin/deck-master')]
    if host is not None:
        paths.extend(host / name for name in install.PUBLIC_SKILLS)
    return {str(path): journal.snapshot(path) for path in paths}


def load(prefix, ident):
    return json.loads(journal.record_path(root(prefix), ident).read_text())


def current(prefix):
    return os.readlink(root(prefix) / 'current')


def assert_active(prefix, host, name, skills=install.PUBLIC_SKILLS):
    assert current(prefix) == 'releases/' + name
    launcher = root(prefix) / 'bin/deck-master'
    assert launcher.read_text() == install._LAUNCHER_TEXT
    assert launcher.stat().st_mode & 0o111
    for skill in install.PUBLIC_SKILLS:
        path = host / skill
        if skill in skills:
            assert os.readlink(path) == str(root(prefix) / 'current/skill' / skill)
            assert (path / 'SKILL.md').read_text() == f'{skill} {name}\n'
        else:
            assert journal.snapshot(path) is None


CHILD = r'''
import json, os, sys
from pathlib import Path
from deck_master import install
from deck_master import activation_transaction as journal
p=json.loads(sys.argv[1])
os.environ['CODEX_HOME']=p['host_parent']
def checkpoint(point, record, step=None):
    name=Path(step['path']).name if step else None
    if p.get('interrupt_first') and point=='after_action' and name=='deck-review' and record['state']=='applying':
        raise KeyboardInterrupt('first interruption requests compensation')
    if point==p['point'] and (p.get('name') is None or name==p['name']):
        os._exit(91)
journal.checkpoint=checkpoint
kwargs={'register_host':p.get('register_host',True)}
if p.get('ident') is not None: kwargs['transaction_id']=p['ident']
if p.get('verb','activate')=='rollback': install.rollback(p['prefix'],**kwargs)
else: install.activate(p['prefix'],p.get('target','new'),**kwargs)
'''


def kill_at(prefix, host, *, point, name=None, ident=None, **extra):
    params = {'prefix': str(prefix), 'host_parent': str(host.parent), 'point': point,
              'name': name, 'ident': ident, **extra}
    result = subprocess.run([sys.executable, '-c', CHILD, json.dumps(params)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 91, result.stderr


def test_normal_contract_and_no_duplicate_same_target_actions(layout):
    prefix, host = layout
    report = install.activate(prefix, 'new')
    assert report['status'] == 'activated' and report['previous'] == 'releases/old'
    assert report['transaction_state'] == 'completed' and report['cli_active']
    assert len(report['skill_links']) == 4
    assert_active(prefix, host, 'new')
    before = managed(prefix, host)
    again = install.activate(prefix, 'new')
    assert again['status'] == 'already_active'
    assert managed(prefix, host) == before
    assert load(prefix, again['transaction_id'])['steps'] == []


@pytest.mark.parametrize('point', ['before_action', 'after_action'])
@pytest.mark.parametrize('name', ['previous', 'current', *install.PUBLIC_SKILLS])
def test_keyboard_interrupt_each_addition_and_pointer_restores_original_inodes(layout, monkeypatch, point, name):
    prefix, host = layout
    # Include an actual deck-master creation rather than only current rotation.
    if name == 'deck-master':
        (host / name).unlink()
    before = managed(prefix, host)
    ident = str(uuid.uuid4())
    def interrupt(where, record, step=None):
        if record['state'] == 'applying' and where == point and step and Path(step['path']).name == name:
            raise KeyboardInterrupt('synthetic Ctrl-C')
    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_interrupted'
    assert caught.value.exit_code == 130 and caught.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before
    assert load(prefix, ident)['state'] == 'rolled_back'
    with pytest.raises(InstallationTransactionError) as replay:
        install.activate(prefix, 'new', transaction_id=ident)
    assert replay.value.transaction_state == 'rolled_back'
    assert replay.value.details['recovered'] is True
    assert managed(prefix, host) == before


@pytest.mark.parametrize('point', ['prepared', 'pending', 'before_completed', 'completed'])
def test_process_death_prepared_pointer_and_final_result_windows(layout, point):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, ident=ident)
    before = load(prefix, ident)
    assert before['schema_version'] == 'activation_transaction.v1'
    if point == 'prepared':
        assert not (root(prefix) / 'activation-pending.json').exists()
    report = install.activate(prefix, 'new', transaction_id=ident)
    assert report['transaction_id'] == ident and report['recovered'] is True
    assert load(prefix, ident)['state'] == 'completed'
    assert_active(prefix, host, 'new')
    assert not (root(prefix) / 'activation-pending.json').exists()


@pytest.mark.parametrize('point', ['before_action', 'after_action', 'applied'])
@pytest.mark.parametrize('name', ['previous', 'current', *install.PUBLIC_SKILLS])
def test_process_death_each_addition_no_recreation_of_published_inode(layout, point, name):
    prefix, host = layout
    if name == 'deck-master':
        (host / name).unlink()
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, name=name, ident=ident)
    record = load(prefix, ident)
    step = next(row for row in record['steps'] if Path(row['path']).name == name)
    published = journal.snapshot(Path(step['path']))
    report = install.activate(prefix, 'new', transaction_id=ident)
    assert report['recovered'] and report['transaction_state'] == 'completed'
    assert_active(prefix, host, 'new')
    if point in ('after_action', 'applied'):
        assert journal.snapshot(Path(step['path'])) == published


def test_death_between_backup_and_replacement_recovers_original_plan(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_backup', name='current', ident=ident)
    record = load(prefix, ident)
    step = next(row for row in record['steps'] if row['path'] == str(root(prefix) / 'current'))
    assert journal.snapshot(root(prefix) / 'current') is None
    assert journal.snapshot(Path(step['backup'])) == step['before']
    install.activate(prefix, 'new', transaction_id=ident)
    assert_active(prefix, host, 'new')


@pytest.mark.parametrize('point', ['before_action', 'after_action', 'after_backup', 'applied'])
@pytest.mark.parametrize('target,name', [(target, name) for target, names in
                                        [('old', install.PUBLIC_SKILLS[1:]), ('bare', install.PUBLIC_SKILLS)]
                                        for name in names])
def test_rollback_death_each_removal_preserves_backup_and_converges(layout, point, name, target):
    prefix, host = layout
    if target == 'bare':
        install.activate(prefix, 'bare')
    install.activate(prefix, 'new')
    ident = str(uuid.uuid4())
    before = journal.snapshot(host / name)
    kill_at(prefix, host, point=point, name=name, ident=ident, verb='rollback')
    record = load(prefix, ident)
    step = next(row for row in record['steps'] if Path(row['path']).name == name)
    assert step['before'] == before
    if point != 'before_action':
        assert journal.snapshot(Path(step['backup'])) == before
    report = install.rollback(prefix, transaction_id=ident)
    assert report['release_id'] == target
    assert_active(prefix, host, target, ('deck-master',) if target == 'old' else ())
    assert journal.snapshot(Path(step['backup'])) == before


@pytest.mark.parametrize('point', ['before_action', 'after_action'])
@pytest.mark.parametrize('target,removed', [('old', install.PUBLIC_SKILLS[1:]), ('bare', install.PUBLIC_SKILLS)])
def test_keyboard_interrupt_each_actual_removal_restores_original(layout, monkeypatch, point, target, removed):
    prefix, host = layout
    install.activate(prefix, target)
    install.activate(prefix, 'new')
    # Each name gets an independent restoration with a fresh request identity.
    before = managed(prefix, host)
    for name in removed:
        ident = str(uuid.uuid4())
        def interrupt(where, record, step=None):
            if record['state'] == 'applying' and where == point and step and Path(step['path']).name == name:
                raise KeyboardInterrupt('retirement interruption')
        monkeypatch.setattr(journal, 'checkpoint', interrupt)
        with pytest.raises(InstallationTransactionError) as caught:
            install.rollback(prefix, transaction_id=ident)
        assert caught.value.transaction_state == 'rolled_back'
        assert managed(prefix, host) == before


@pytest.mark.parametrize('point', ['compensating', 'before_restore', 'after_unpublish', 'after_restore', 'restored'])
def test_compensation_process_dies_again_and_resumes_reverse_direction(layout, point):
    prefix, host = layout
    before = managed(prefix, host)
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, ident=ident, interrupt_first=True)
    assert load(prefix, ident)['state'] == 'compensating'
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_interrupted'
    assert caught.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before


def test_exact_activate_and_rollback_replay_after_later_switch_changes_nothing(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    first = install.activate(prefix, 'new', transaction_id=ident)
    rollback_id = str(uuid.uuid4())
    rollback = install.rollback(prefix, transaction_id=rollback_id)
    install.activate(prefix, 'later')
    before = managed(prefix, host)
    replay = install.activate(prefix, 'new', transaction_id=ident)
    assert replay['transaction_id'] == ident and replay['recovered']
    assert replay['release_id'] == first['release_id'] == 'new'
    assert replay['observed_current_release_id'] == 'later'
    assert replay['current_install_state'] == 'verified'
    again = install.rollback(prefix, transaction_id=rollback_id)
    assert again['release_id'] == rollback['release_id'] == 'old'
    assert again['observed_current_release_id'] == 'later'
    assert managed(prefix, host) == before


def test_replay_reports_current_unknown_without_reapplying_history(layout):
    prefix, host = layout
    first = install.activate(prefix, 'new')
    (root(prefix) / 'current').unlink()
    before = managed(prefix, host)
    replay = install.activate(prefix, 'new', transaction_id=first['transaction_id'])
    assert replay['cli_active'] is True  # Historical result only.
    assert replay['current_install_state'] == 'unknown'
    assert replay['observed_current_release_id'] is None
    assert managed(prefix, host) == before


def test_no_id_completed_rollback_toggles_but_unfinished_rollback_freezes_target(layout):
    prefix, host = layout
    install.activate(prefix, 'new')
    kill_at(prefix, host, point='after_action', name='current', verb='rollback')
    pending = json.loads((root(prefix) / 'activation-pending.json').read_text())['transaction_id']
    assert current(prefix) == 'releases/old'
    resumed = install.rollback(prefix)
    assert resumed['transaction_id'] == pending and resumed['release_id'] == 'old'
    assert resumed['recovered']
    toggled = install.rollback(prefix)
    assert toggled['transaction_id'] != pending and toggled['release_id'] == 'new'
    assert not toggled['recovered']
    assert_active(prefix, host, 'new')


@pytest.mark.parametrize('mutation', ['link', 'launcher', 'parent', 'unchanged-link'])
def test_external_replacement_is_preserved_and_compensates_only_owned_paths(layout, mutation):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_action', name='deck-content', ident=ident)
    pending = load(prefix, ident)
    published = next(step for step in pending['steps'] if Path(step['path']).name == 'deck-content')
    assert published['step_state'] == 'ready'  # Filesystem action preceded its state write.
    assert journal.snapshot(host / 'deck-content') == published['expected_after']
    if mutation == 'parent':
        original = host.with_name('preserved-original-parent')
        host.rename(original)
        host.mkdir()
        foreign = host / 'deck-content'
        foreign.write_text('external parent content')
    else:
        foreign = (root(prefix) / 'bin/deck-master' if mutation == 'launcher' else
                   host / ('deck-master' if mutation == 'unchanged-link' else 'deck-content'))
        previous = foreign.read_bytes() if mutation == 'launcher' else os.readlink(foreign)
        original_identity = journal.snapshot(foreign)
        witnesses = [Path(row['path']) for row in pending['inode_anchors'] if row['identity'] == original_identity]
        assert witnesses and all(journal.snapshot(path) == original_identity for path in witnesses)
        foreign.unlink()
        assert all(journal.snapshot(path) == original_identity for path in witnesses)
        if mutation == 'launcher':
            foreign.write_bytes(previous)  # Witness keeps the original inode allocated.
            foreign.chmod(0o755)
        else:
            foreign.symlink_to(previous)  # Same target is insufficient ownership.
        assert foreign.lstat().st_ino != original_identity['ino']
    preserved = journal.snapshot(foreign)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'recovery_conflict'
    assert journal.snapshot(foreign) == preserved
    record = load(prefix, ident)
    assert record['state'] == 'recovery_conflict'
    assert record['conflicts']
    if mutation == 'parent':
        assert journal.snapshot(original / 'deck-content') is not None
    # Addition had no old link to back up; retained remaining preparations and
    # the conflict record are the recovery evidence for this case.
    assert any(row['observed'] for row in record['steps'])
    assert current(prefix) == 'releases/old'  # Still-owned pointer compensation.


@pytest.mark.parametrize('mutation', ['link', 'launcher', 'unchanged-link'])
@pytest.mark.parametrize('damage', ['missing', 'replaced'])
def test_lost_inode_witness_refuses_even_simulated_recycled_inode(layout, monkeypatch, mutation, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='after_action', name='deck-content', ident=ident)
    record = load(prefix, ident)
    foreign = (root(prefix) / 'bin/deck-master' if mutation == 'launcher' else
               host / ('deck-master' if mutation == 'unchanged-link' else 'deck-content'))
    original = journal.snapshot(foreign)
    anchor = Path(next(row for row in record['inode_anchors'] if row['identity'] == original)['path'])
    previous = foreign.read_bytes() if mutation == 'launcher' else os.readlink(foreign)
    foreign.unlink()
    if mutation == 'launcher':
        foreign.write_bytes(previous)
        foreign.chmod(0o755)
    else:
        foreign.symlink_to(previous)
    if damage == 'replaced':
        anchor.rename(anchor.with_suffix('.preserved-witness'))
        if mutation == 'launcher':
            anchor.write_bytes(previous)
            anchor.chmod(0o755)
        else:
            anchor.symlink_to(previous)
        assert journal.snapshot(anchor) != original
    else:
        anchor.unlink()
    real_snapshot = journal.snapshot
    foreign_identity = real_snapshot(foreign)
    anchor_identity = real_snapshot(anchor)

    def recycled_snapshot(path):
        actual = real_snapshot(path)
        if path == foreign:
            # Deterministically reproduce the indistinguishable dev/ino/bytes
            # observation that occurred on the CI filesystem after recreation.
            return {**actual, 'dev': original['dev'], 'ino': original['ino']}
        return actual

    monkeypatch.setattr(journal, 'snapshot', recycled_snapshot)
    assert journal.snapshot(foreign) == original
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'recovery_conflict'
    assert real_snapshot(foreign) == foreign_identity
    assert real_snapshot(anchor) == anchor_identity
    assert load(prefix, ident)['state'] == 'recovery_conflict'
    assert current(prefix) == 'releases/old'


def test_unfinished_record_without_inode_witnesses_is_preserved_and_refused(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident)
    record = load(prefix, ident)
    del record['inode_anchors']
    path = journal.record_path(root(prefix), ident)
    path.write_text(json.dumps(record))
    preserved = path.read_bytes()
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert path.read_bytes() == preserved and managed(prefix, host) == before


def test_historical_terminal_record_without_inode_witnesses_still_replays(layout):
    prefix, host = layout
    result = install.activate(prefix, 'new')
    record = load(prefix, result['transaction_id'])
    del record['inode_anchors']
    path = journal.record_path(root(prefix), result['transaction_id'])
    path.write_text(json.dumps(record))
    before = managed(prefix, host)
    replay = install.activate(prefix, 'new', transaction_id=result['transaction_id'])
    assert replay['recovered'] and replay['transaction_state'] == 'completed'
    assert managed(prefix, host) == before


@pytest.mark.parametrize('changed', ['target', 'verb', 'host', 'registration'])
def test_same_id_different_request_is_rejected_without_mutation(layout, monkeypatch, changed):
    prefix, host = layout
    ident = str(uuid.uuid4())
    install.activate(prefix, 'new', transaction_id=ident)
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        if changed == 'target':
            install.activate(prefix, 'later', transaction_id=ident)
        elif changed == 'verb':
            install.rollback(prefix, transaction_id=ident)
        elif changed == 'host':
            monkeypatch.setenv('CODEX_HOME', str(host.parent.with_name('different-host')))
            install.activate(prefix, 'new', transaction_id=ident)
        else:
            install.activate(prefix, 'new', transaction_id=ident, register_host=False)
    assert caught.value.error_code == 'installation_transaction_conflict'
    assert managed(prefix, host) == before


def test_different_request_cannot_supersede_pending_and_prepared_without_pointer_is_found(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident)
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'later')
    assert caught.value.error_code == 'installation_transaction_pending'
    assert caught.value.transaction_id == ident
    assert managed(prefix, host) == before
    resumed = install.activate(prefix, 'new')
    assert resumed['transaction_id'] == ident and resumed['recovered']


@pytest.mark.parametrize('point', ['normal', 'after_action', 'interrupt'])
def test_opt_out_never_resolves_or_writes_host_including_recovery(layout, monkeypatch, point):
    prefix, host = layout
    before = {str(path): journal.snapshot(path) for path in (host.parent, host, *host.iterdir())}
    def forbidden():
        raise AssertionError('opt-out must not resolve Host root')
    monkeypatch.setattr(install, '_codex_skill_root', forbidden)
    ident = str(uuid.uuid4())
    if point == 'after_action':
        kill_at(prefix, host, point=point, name='current', ident=ident, register_host=False)
    if point == 'interrupt':
        def interrupt(where, record, step=None):
            if where == 'after_action' and record['state'] == 'applying':
                raise KeyboardInterrupt()
        monkeypatch.setattr(journal, 'checkpoint', interrupt)
        with pytest.raises(InstallationTransactionError) as caught:
            install.activate(prefix, 'new', transaction_id=ident, register_host=False)
        assert caught.value.transaction_state == 'rolled_back'
    else:
        install.activate(prefix, 'new', transaction_id=ident, register_host=False)
    assert {path: journal.snapshot(Path(path)) for path in before} == before
    assert set(map(str, (host.parent, host, *host.iterdir()))) == set(before)
    record = load(prefix, ident)
    assert record['request']['host_root'] is None
    assert all(not Path(row['path']).is_relative_to(host.parent) for row in record['steps'])


@pytest.mark.parametrize('damage', ['json', 'version', 'prefix', 'id', 'action', 'resource'])
def test_damaged_or_foreign_records_and_changed_resources_are_never_reinterpreted(layout, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident)
    path = journal.record_path(root(prefix), ident)
    record = load(prefix, ident)
    if damage == 'json':
        path.write_text('{broken')
    elif damage == 'version':
        record['schema_version'] = 'activation_transaction.v99'
    elif damage == 'prefix':
        record['prefix'] = str(prefix.parent / 'unrelated')
    elif damage == 'id':
        record['transaction_id'] = str(uuid.uuid4())
    elif damage == 'action':
        record['steps'][0]['kind'] = 'execute_python'
    else:
        (root(prefix) / 'releases/new/skill/deck-master/SKILL.md').write_text('externally changed resource')
    if damage not in ('json', 'resource'):
        path.write_text(json.dumps(record))
    original_bytes = path.read_bytes()
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == ('installation_recovery_conflict' if damage == 'resource' else 'installation_recovery_unavailable')
    assert managed(prefix, host) == before
    if damage != 'resource':
        assert path.read_bytes() == original_bytes


def test_completed_record_with_stale_pending_does_not_apply_again(layout, monkeypatch):
    prefix, host = layout
    original = journal.clear_pending
    def fail(*args):
        raise OSError('synthetic pending unlink failure')
    monkeypatch.setattr(journal, 'clear_pending', fail)
    first = install.activate(prefix, 'new')
    assert first['transaction_state'] == 'completed'
    assert (root(prefix) / 'activation-pending.json').exists()
    before = managed(prefix, host)
    monkeypatch.setattr(journal, 'clear_pending', original)
    replay = install.activate(prefix, 'new', transaction_id=first['transaction_id'])
    assert replay['recovered'] and managed(prefix, host) == before
    assert not (root(prefix) / 'activation-pending.json').exists()


def test_pending_write_failure_preserves_prepared_plan_and_recovers(layout, monkeypatch):
    prefix, host = layout
    ident = str(uuid.uuid4())
    original = journal.pending
    monkeypatch.setattr(journal, 'pending', lambda *args: (_ for _ in ()).throw(OSError('pending write failed')))
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert load(prefix, ident)['state'] == 'prepared'
    assert managed(prefix, host) == before
    monkeypatch.setattr(journal, 'pending', original)
    assert install.activate(prefix, 'new', transaction_id=ident)['recovered']
    assert_active(prefix, host, 'new')


def test_cli_structured_interrupt_and_invalid_transaction_id(layout, monkeypatch, capsys):
    from deck_master.cli import main
    prefix, host = layout
    before = managed(prefix, host)
    assert main(['install', 'activate', '--prefix', str(prefix), '--release-id', 'new', '--transaction-id', 'not-a-uuid']) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out or captured.err)['error']['code'] == 'invalid_transaction_id'
    ident = str(uuid.uuid4())
    def interrupt(where, record, step=None):
        if where == 'after_action' and record['state'] == 'applying':
            raise KeyboardInterrupt()
    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    assert main(['install', 'activate', '--prefix', str(prefix), '--release-id', 'new', '--transaction-id', ident]) == 130
    captured = capsys.readouterr()
    error = json.loads(captured.out or captured.err)['error']
    assert error['code'] == 'installation_interrupted'
    assert error['transaction_id'] == ident and error['transaction_state'] == 'rolled_back'
    assert managed(prefix, host) == before


@pytest.mark.parametrize('point,name', [('after_action', 'current'), ('after_action', 'deck-legacy-1'), ('after_action', 'deck-master')])
def test_legacy_companion_move_and_exact_retirement_survive_process_death(tmp_path, monkeypatch, point, name):
    from test_install_host_skill import _build_legacy_layout
    prefix, host = tmp_path / 'prefix', tmp_path / 'host/skills'
    monkeypatch.setenv('CODEX_HOME', str(host.parent))
    _build_legacy_layout(prefix, host.parent)
    release(prefix, 'new')
    extra = host / 'ppt-retired'
    extra.symlink_to(str(root(prefix) / 'current/skills/ppt-retired'))
    original_manifest = journal.snapshot(root(prefix) / 'current')
    original_foreign = {str(path): journal.snapshot(path) for path in host.iterdir()
                        if not path.name.startswith('deck-legacy') and path.name not in ('deck-master', 'ppt-retired')}
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point=point, name=name, ident=ident)
    report = install.activate(prefix, 'new', transaction_id=ident)
    assert report['migration']['migrated']
    assert len(report['migration']['removed_links']) == 16
    assert journal.snapshot(Path(report['migration']['moved']['to'])) == original_manifest
    assert {path: journal.snapshot(Path(path)) for path in original_foreign} == original_foreign
    assert_active(prefix, host, 'new')


@pytest.mark.parametrize('mode', ['normal', 'interrupt', 'process_death'])
def test_legacy_optout_preserves_host_configuration_and_inodes_whole_lifecycle(tmp_path, monkeypatch, mode):
    from test_install_host_skill import _build_legacy_layout
    prefix, host = tmp_path / 'prefix', tmp_path / 'host/skills'
    monkeypatch.setenv('CODEX_HOME', str(host.parent))
    _build_legacy_layout(prefix, host.parent)
    release(prefix, 'new')
    config = host.parent / 'config.toml'
    config.write_bytes(b'# external host configuration\n')
    before = {str(path): journal.snapshot(path) for path in (host.parent, *host.parent.rglob('*'))}
    ident = str(uuid.uuid4())
    if mode == 'process_death':
        kill_at(prefix, host, point='after_action', name='current', ident=ident, register_host=False)
    if mode == 'interrupt':
        def interrupt(point, record, step=None):
            if point == 'after_action' and record['state'] == 'applying':
                raise KeyboardInterrupt()
        monkeypatch.setattr(journal, 'checkpoint', interrupt)
        with pytest.raises(InstallationTransactionError) as caught:
            install.activate(prefix, 'new', transaction_id=ident, register_host=False)
        assert caught.value.transaction_state == 'rolled_back'
        assert (root(prefix) / 'current/companion-manifest.json').is_file()
    else:
        result = install.activate(prefix, 'new', transaction_id=ident, register_host=False)
        assert result['migration']['removed_links'] == []
        assert current(prefix) == 'releases/new'
    assert {str(path): journal.snapshot(path) for path in (host.parent, *host.parent.rglob('*'))} == before
    assert not (host / '.deck-master-registration.lock').exists()


@pytest.mark.parametrize('point', ['before_restore', 'after_restore', 'restored'])
def test_link_retirement_compensation_dies_and_restores_original_link_inode(layout, point):
    prefix, host = layout
    install.activate(prefix, 'new')
    before = managed(prefix, host)
    ident = str(uuid.uuid4())
    # Raise after deleting review during rollback, then kill while restoring it.
    script = CHILD.replace("and record['state']=='applying':", "and record['state']=='applying':")
    params = {'prefix': str(prefix), 'host_parent': str(host.parent), 'point': point,
              'name': 'deck-review', 'ident': ident, 'verb': 'rollback', 'interrupt_first': True}
    child = subprocess.run([sys.executable, '-c', script, json.dumps(params)], capture_output=True, text=True, timeout=20)
    assert child.returncode == 91, child.stderr
    assert load(prefix, ident)['state'] == 'compensating'
    with pytest.raises(InstallationTransactionError) as caught:
        install.rollback(prefix, transaction_id=ident)
    assert caught.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before


def test_occupied_retired_link_preserves_external_path_and_original_backup(layout):
    prefix, host = layout
    install.activate(prefix, 'new')
    ident = str(uuid.uuid4())
    before = journal.snapshot(host / 'deck-content')
    kill_at(prefix, host, point='after_action', name='deck-content', ident=ident, verb='rollback')
    external = host / 'deck-content'
    external.write_text('external occupant after retirement')
    occupied = journal.snapshot(external)
    with pytest.raises(InstallationTransactionError) as caught:
        install.rollback(prefix, transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert journal.snapshot(external) == occupied
    record = load(prefix, ident)
    step = next(row for row in record['steps'] if row['path'] == str(external))
    assert journal.snapshot(Path(step['backup'])) == before
    assert record['state'] == 'recovery_conflict'
    assert current(prefix) == 'releases/new'


def test_record_write_failure_after_action_reports_unknown_then_recovers_original_transaction(layout, monkeypatch):
    prefix, host = layout
    ident = str(uuid.uuid4())
    original = journal.save
    failed = False
    def fail(root_path, record):
        nonlocal failed
        if any(step['step_state'] == 'applied' for step in record['steps']):
            failed = True
            raise OSError('persistent journal device failure')
        return original(root_path, record)
    monkeypatch.setattr(journal, 'save', fail)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert failed and caught.value.error_code == 'installation_recovery_unavailable'
    assert caught.value.transaction_state == 'unknown'
    assert load(prefix, ident)['state'] == 'applying'
    monkeypatch.setattr(journal, 'save', original)
    result = install.activate(prefix, 'new', transaction_id=ident)
    assert result['recovered'] and result['transaction_id'] == ident
    assert_active(prefix, host, 'new')


def test_prepared_interrupt_compensates_before_pending_and_two_unfinished_records_refuse(layout, monkeypatch):
    prefix, host = layout
    ident = str(uuid.uuid4())
    before = managed(prefix, host)
    def interrupt(point, record, step=None):
        if point == 'prepared':
            raise KeyboardInterrupt()
    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before
    monkeypatch.setattr(journal, 'checkpoint', lambda *args: None)
    first = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=first)
    duplicate = load(prefix, first)
    second = str(uuid.uuid4())
    duplicate['transaction_id'] = second
    duplicate['request']['transaction_id'] = second
    # A separately copied record cannot be interpreted as a second executable
    # plan: its preparation paths still belong to the first transaction.
    journal.record_path(root(prefix), second).write_text(json.dumps(duplicate))
    with pytest.raises(InstallationTransactionError) as rejected:
        install.activate(prefix, 'new')
    assert rejected.value.error_code == 'installation_recovery_unavailable'
    assert managed(prefix, host) == before


CONCURRENT = r'''
import json, os, sys, time
from pathlib import Path
from deck_master import install
from deck_master import activation_transaction as journal
from deck_master.errors import HostSkillConflict
p=json.loads(sys.argv[1]); os.environ['CODEX_HOME']=p['host_parent']
if p['role']=='first':
    def checkpoint(point, record, step=None):
        if point=='prepared':
            Path(p['prepared']).write_text('Host lock held; public links absent')
            until=time.monotonic()+10
            while not Path(p['go']).exists():
                if time.monotonic()>until: raise RuntimeError('test gate timed out')
                time.sleep(.01)
    journal.checkpoint=checkpoint
else:
    original=install._preflight_host_skill
    def preflight(*args,**kwargs):
        result=original(*args,**kwargs)
        Path(p['waiting']).write_text('initial preflight passed')
        return result
    install._preflight_host_skill=preflight
try:
    install.activate(p['prefix'],'new')
except HostSkillConflict:
    sys.exit(5)
'''


def test_two_prefixes_share_host_lock_and_recheck_after_waiting(tmp_path, monkeypatch):
    import time
    host = tmp_path / 'shared-host/skills'
    prefixes = [tmp_path / 'first-prefix', tmp_path / 'second-prefix']
    for prefix in prefixes:
        release(prefix, 'new')
    common = {'host_parent': str(host.parent), 'prepared': str(tmp_path / 'prepared'),
              'go': str(tmp_path / 'go'), 'waiting': str(tmp_path / 'waiting')}
    first = subprocess.Popen([sys.executable, '-c', CONCURRENT, json.dumps({**common, 'role': 'first', 'prefix': str(prefixes[0])})],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = None
    try:
        until = time.monotonic() + 10
        while not Path(common['prepared']).exists():
            assert first.poll() is None
            assert time.monotonic() < until
            time.sleep(.01)
        lock_identity = journal.snapshot(host / '.deck-master-registration.lock')
        second = subprocess.Popen([sys.executable, '-c', CONCURRENT, json.dumps({**common, 'role': 'second', 'prefix': str(prefixes[1])})],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while not Path(common['waiting']).exists():
            assert second.poll() is None
            assert time.monotonic() < until
            time.sleep(.01)
        # Both preflights saw absence. The second waits for the same shared lock
        # and must recheck foreign registration before touching its current.
        assert second.poll() is None
        Path(common['go']).write_text('finish the first transaction')
        _, first_error = first.communicate(timeout=10)
        _, second_error = second.communicate(timeout=10)
        assert first.returncode == 0, first_error
        assert second.returncode == 5, second_error
        assert journal.snapshot(host / '.deck-master-registration.lock') == lock_identity
        assert_active(prefixes[0], host, 'new')
        assert journal.snapshot(root(prefixes[1]) / 'current') is None
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill()  # Only these dedicated fixture children.
                process.communicate(timeout=5)


def test_historical_replay_does_not_clear_another_transactions_pending_pointer(layout):
    prefix, host = layout
    original = install.activate(prefix, 'new')
    later_id = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=later_id, target='later')
    pointer_bytes = (root(prefix) / 'activation-pending.json').read_bytes() if (root(prefix) / 'activation-pending.json').exists() else None
    before = managed(prefix, host)
    replay = install.activate(prefix, 'new', transaction_id=original['transaction_id'])
    assert replay['recovered'] and replay['release_id'] == 'new'
    assert managed(prefix, host) == before
    actual_pointer = (root(prefix) / 'activation-pending.json').read_bytes() if (root(prefix) / 'activation-pending.json').exists() else None
    assert actual_pointer == pointer_bytes
    assert load(prefix, later_id)['state'] == 'prepared'
    install.activate(prefix, 'later', transaction_id=later_id)
    assert_active(prefix, host, 'later')


def test_copied_record_in_different_prefix_refuses_original_paths(layout, tmp_path, monkeypatch):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident)
    copied_prefix = tmp_path / 'unrelated-prefix'
    copied_path = journal.record_path(root(copied_prefix), ident)
    copied_path.parent.mkdir(parents=True)
    copied_bytes = journal.record_path(root(prefix), ident).read_bytes()
    copied_path.write_bytes(copied_bytes)
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(copied_prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert copied_path.read_bytes() == copied_bytes
    assert managed(prefix, host) == before


@pytest.mark.parametrize('target', ['old', 'bare'])
def test_rollback_never_changes_any_project_writer_floor(layout, target):
    prefix, host = layout
    project = prefix / 'unrelated-project'
    project.mkdir()
    document = project / 'document.json'
    document.write_bytes(b'{"writer_floor":"rc4-content.v1","opaque_user_state":[1,2,3]}\n')
    before = journal.snapshot(document)
    install.activate(prefix, target)
    install.activate(prefix, 'new')
    install.rollback(prefix)
    assert journal.snapshot(document) == before


def test_journal_symlink_is_refused_without_writing_its_external_target(layout, tmp_path):
    prefix, host = layout
    directory = root(prefix) / 'transactions/activation'
    preserved = directory.with_name('original-journal')
    directory.rename(preserved)
    foreign = tmp_path / 'foreign-journal'
    foreign.mkdir()
    directory.symlink_to(foreign, target_is_directory=True)
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new')
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert list(foreign.iterdir()) == []
    assert managed(prefix, host) == before


def test_same_bytes_launcher_mode_repair_is_published_atomically_and_compensated(layout, monkeypatch):
    prefix, host = layout
    launcher = root(prefix) / 'bin/deck-master'
    launcher.chmod(0o644)
    before = managed(prefix, host)
    def interrupt(point, record, step=None):
        if point == 'after_action' and step and step['kind'] == 'launcher' and record['state'] == 'applying':
            raise KeyboardInterrupt()
    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new')
    assert caught.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before
    monkeypatch.setattr(journal, 'checkpoint', lambda *args: None)
    install.activate(prefix, 'new')
    assert launcher.stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize('window', ['before_action', 'after_backup', 'before_restore', 'after_unpublish'])
def test_external_occupant_arriving_at_rename_boundary_is_never_overwritten(layout, monkeypatch, window):
    prefix, host = layout
    ident = str(uuid.uuid4())
    target = root(prefix) / 'current'
    injected = False
    external_identity = None
    def collide(point, record, step=None):
        nonlocal injected, external_identity
        if step is None or step['path'] != str(target):
            return
        if window in ('before_restore', 'after_unpublish') and point == 'after_action' and record['state'] == 'applying':
            raise KeyboardInterrupt('request reverse recovery')
        if point == window and not injected:
            injected = True
            if target.is_symlink():
                target.rename(target.with_name('external-preserved-original'))
            target.write_text('external occupant at rename boundary')
            external_identity = journal.snapshot(target)
    monkeypatch.setattr(journal, 'checkpoint', collide)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert injected
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'recovery_conflict'
    assert journal.snapshot(target) == external_identity
    assert load(prefix, ident)['state'] == 'recovery_conflict'


def test_external_preparation_replacement_is_preserved_and_refused(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident)
    record = load(prefix, ident)
    step = next(row for row in record['steps'] if Path(row['path']).name == 'current')
    prepared = Path(step['prepared']['path'])
    target = os.readlink(prepared)
    prepared.rename(prepared.with_suffix('.external-original'))
    prepared.symlink_to(target)
    external_identity = journal.snapshot(prepared)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert journal.snapshot(prepared) == external_identity
    assert current(prefix) == 'releases/old'


def test_second_keyboard_interrupt_leaves_compensating_until_original_retry(layout, monkeypatch):
    prefix, host = layout
    before = managed(prefix, host)
    ident = str(uuid.uuid4())
    def interrupt(point, record, step=None):
        if point == 'after_action' and record['state'] == 'applying':
            raise KeyboardInterrupt('first')
        if point == 'before_restore' and record['state'] == 'compensating':
            raise KeyboardInterrupt('second')
    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_interrupted'
    assert caught.value.transaction_state == 'compensating'
    assert load(prefix, ident)['state'] == 'compensating'
    monkeypatch.setattr(journal, 'checkpoint', lambda *args: None)
    with pytest.raises(InstallationTransactionError) as resumed:
        install.activate(prefix, 'new', transaction_id=ident)
    assert resumed.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before


@pytest.mark.parametrize('damage', ['json', 'version', 'identity'])
def test_corrupt_pending_pointer_preserves_record_and_does_not_guess_new_transaction(layout, damage):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending', ident=ident)
    pointer = root(prefix) / 'activation-pending.json'
    payload = ('{broken' if damage == 'json' else
               json.dumps({'schema_version': 'activation_transaction.v99' if damage == 'version' else journal.VERSION,
                           'transaction_id': str(uuid.uuid4()) if damage == 'identity' else ident}))
    pointer.write_text(payload)
    record_bytes = journal.record_path(root(prefix), ident).read_bytes()
    before = managed(prefix, host)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert pointer.read_text() == payload
    assert journal.record_path(root(prefix), ident).read_bytes() == record_bytes
    assert managed(prefix, host) == before


def test_replay_still_returns_completed_result_when_stale_pointer_unlink_repeatedly_fails(layout, monkeypatch):
    prefix, host = layout
    monkeypatch.setattr(journal, 'clear_pending', lambda *args: (_ for _ in ()).throw(OSError('persistent unlink failure')))
    completed = install.activate(prefix, 'new')
    before = managed(prefix, host)
    replay = install.activate(prefix, 'new', transaction_id=completed['transaction_id'])
    assert replay['transaction_state'] == 'completed' and replay['recovered']
    assert managed(prefix, host) == before
    assert (root(prefix) / 'activation-pending.json').exists()


def _strict_release(prefix, name):
    import hashlib
    released = release(prefix, name)
    files, rows = {}, []
    for skill in install.PUBLIC_SKILLS:
        host_path = released / 'skill' / skill / 'SKILL.md'
        package_path = released / 'venv/synthetic-site-packages' / skill / 'SKILL.md'
        package_path.parent.mkdir(parents=True)
        package_path.write_bytes(host_path.read_bytes())
        digest = hashlib.sha256(host_path.read_bytes()).hexdigest()
        wheel_path = f'deck_master/resources/skills/{skill}/SKILL.md'
        files[wheel_path] = {'sha256': digest}
        rows.append({'wheel_path': wheel_path, 'host_path': str(host_path),
                     'installed_package_path': str(package_path), 'sha256': digest})
    (released / 'release.json').write_text(json.dumps({'status': 'candidate_ready',
        'public_skills': list(install.PUBLIC_SKILLS), 'method_resource_inventory': {'files': files},
        'installed_resource_paths': rows}))
    return released, rows


@pytest.mark.parametrize('mutation', ['host-bytes', 'package-bytes', 'missing-host', 'unknown-host'])
def test_strict_installed_release_validation_stays_in_force_before_activation(layout, mutation):
    prefix, host = layout
    released, rows = _strict_release(prefix, 'strict')
    if mutation == 'host-bytes':
        Path(rows[0]['host_path']).write_text('corrupt Host method')
    elif mutation == 'package-bytes':
        Path(rows[0]['installed_package_path']).write_text('corrupt installed method')
    elif mutation == 'missing-host':
        Path(rows[0]['host_path']).unlink()
    else:
        (released / 'skill/unknown.txt').write_text('unknown resource')
    before = managed(prefix, host)
    with pytest.raises(ValueError):
        install.activate(prefix, 'strict')
    assert managed(prefix, host) == before


def test_strict_resource_change_after_prepared_is_recovery_conflict_with_safe_compensation(layout):
    prefix, host = layout
    _, rows = _strict_release(prefix, 'strict')
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='prepared', ident=ident, target='strict')
    before = managed(prefix, host)
    Path(rows[0]['installed_package_path']).write_text('externally modified installed resource')
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'strict', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'recovery_conflict'
    assert caught.value.details['old_state_verified'] is True
    assert managed(prefix, host) == before
    assert load(prefix, ident)['state'] == 'recovery_conflict'


@pytest.mark.parametrize('window', ['backup', 'publish', 'unpublish', 'restore', 'retire', 'restore_retired'])
@pytest.mark.parametrize('occupant', ['file', 'symlink', 'directory'])
def test_atomic_rename_refuses_occupant_after_final_path_check(layout, monkeypatch, window, occupant):
    prefix, host = layout
    retirement = window in ('retire', 'restore_retired')
    if retirement:
        install.activate(prefix, 'bare')
        install.activate(prefix, 'new')
    target = host / 'deck-content' if retirement else root(prefix) / 'current'
    ident = str(uuid.uuid4())
    original = journal._renameat_noreplace
    external = None
    external_identity = None

    def interrupt(point, record, step=None):
        if (window in ('unpublish', 'restore', 'restore_retired') and point == 'after_action'
                and record['state'] == 'applying' and step['path'] == str(target)):
            raise KeyboardInterrupt('exercise reverse rename')

    def collide(directory, source, destination):
        nonlocal external, external_identity
        matches = ((window in ('backup', 'retire') and source == target.name and destination.endswith('.before')) or
                   (window == 'publish' and source.endswith('.after') and destination == target.name) or
                   (window == 'unpublish' and source == target.name and destination.endswith('.after')) or
                   (window in ('restore', 'restore_retired') and source.endswith('.before') and destination == target.name))
        if matches and external is None:
            external = target.parent / destination
            if occupant == 'file':
                external.write_bytes(b'external content arriving at the actual syscall boundary')
            elif occupant == 'symlink':
                external.symlink_to('foreign-target')
            else:
                external.mkdir()
            external_identity = journal.snapshot(external)
        return original(directory, source, destination)

    monkeypatch.setattr(journal, 'checkpoint', interrupt)
    monkeypatch.setattr(journal, '_renameat_noreplace', collide)
    with pytest.raises(InstallationTransactionError) as caught:
        if retirement:
            install.rollback(prefix, transaction_id=ident)
        else:
            install.activate(prefix, 'new', transaction_id=ident)
    assert external is not None
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'recovery_conflict'
    assert journal.snapshot(external) == external_identity
    assert load(prefix, ident)['state'] == 'recovery_conflict'


def test_atomic_rename_pins_host_parent_when_ancestor_is_replaced(layout, monkeypatch):
    prefix, host = layout
    original = journal._renameat_noreplace
    preserved = host.with_name('preserved-owned-skills')
    replaced = False
    foreign = None

    def collide(directory, source, destination):
        nonlocal replaced, foreign
        if destination == 'deck-content' and not replaced:
            replaced = True
            host.rename(preserved)
            host.mkdir()
            (host / 'deck-content').write_bytes(b'foreign parent and occupant')
            foreign = {path.name: journal.snapshot(path) for path in host.iterdir()}
        return original(directory, source, destination)

    monkeypatch.setattr(journal, '_renameat_noreplace', collide)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new')
    assert replaced and caught.value.error_code == 'installation_recovery_conflict'
    assert {path.name: journal.snapshot(path) for path in host.iterdir()} == foreign
    assert (preserved / 'deck-content').is_symlink()


@pytest.mark.parametrize('occupant', ['file', 'symlink', 'directory'])
def test_atomic_rename_primitive_preserves_both_source_and_existing_destination(tmp_path, occupant):
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    source.symlink_to('owned-target')
    if occupant == 'file':
        destination.write_bytes(b'foreign')
    elif occupant == 'symlink':
        destination.symlink_to('foreign-target')
    else:
        destination.mkdir()
    before = journal.snapshot(source), journal.snapshot(destination)
    with pytest.raises(FileExistsError):
        journal.rename_noreplace(source, destination, journal.parent_identity(source))
    assert (journal.snapshot(source), journal.snapshot(destination)) == before


def test_atomic_rename_success_retains_inode_and_rejects_changed_parent(tmp_path):
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    source.write_bytes(b'owned bytes')
    before = journal.snapshot(source)
    parent = journal.parent_identity(source)
    changed = {**parent, 'ino': parent['ino'] + 1}
    with pytest.raises(OSError, match='parent changed'):
        journal.rename_noreplace(source, destination, changed)
    assert journal.snapshot(source) == before and not destination.exists()
    journal.rename_noreplace(source, destination, parent)
    assert journal.snapshot(source) is None and journal.snapshot(destination) == before


def test_unsupported_atomic_rename_never_uses_overwriting_fallback(layout, monkeypatch):
    prefix, host = layout
    before = managed(prefix, host)
    original = journal._renameat_noreplace

    def unsupported(directory, source, destination):
        if destination == 'deck-content':
            raise OSError(errno.ENOTSUP, 'unsupported fixture filesystem')
        return original(directory, source, destination)

    monkeypatch.setattr(journal, '_renameat_noreplace', unsupported)
    with pytest.raises(OSError) as caught:
        install.activate(prefix, 'new')
    assert caught.value.errno == errno.ENOTSUP
    assert caught.value.transaction_state == 'rolled_back'
    assert managed(prefix, host) == before


@pytest.mark.parametrize('replacement', ['file', 'symlink'])
@pytest.mark.parametrize('second_occupant', [False, True])
def test_pending_cleanup_captures_and_preserves_racing_replacement(layout, monkeypatch, replacement, second_occupant):
    prefix, host = layout
    completed = install.activate(prefix, 'new')
    record = load(prefix, completed['transaction_id'])
    pointer = root(prefix) / 'activation-pending.json'
    pointer.write_text(json.dumps({'schema_version': journal.VERSION, 'transaction_id': record['transaction_id']}))
    original = journal._renameat_noreplace
    replaced = False
    external = None
    captured = None
    second = None

    def collide(directory, source, destination):
        nonlocal replaced, external, captured, second
        if source == pointer.name and not replaced:
            replaced = True
            pointer.rename(pointer.with_name('original-pointer-preserved'))
            if replacement == 'file':
                pointer.write_bytes(b'foreign replacement must survive cleanup')
            else:
                pointer.symlink_to('foreign-pointer-target')
            external = journal.snapshot(pointer)
            captured = root(prefix) / destination
            result = original(directory, source, destination)
            if second_occupant:
                pointer.write_bytes(b'second external occupant must also survive')
                second = journal.snapshot(pointer)
            return result
        return original(directory, source, destination)

    before = managed(prefix, host)
    monkeypatch.setattr(journal, '_renameat_noreplace', collide)
    with pytest.raises(ValueError, match='pending pointer changed'):
        journal.clear_pending(root(prefix), record)
    assert replaced
    if second_occupant:
        assert journal.snapshot(pointer) == second
        assert journal.snapshot(captured) == external
    else:
        assert journal.snapshot(pointer) == external
        assert not captured.exists() and not captured.is_symlink()
    assert managed(prefix, host) == before
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'later')
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert managed(prefix, host) == before


def test_pending_publish_never_replaces_external_occupant_at_syscall_boundary(layout, monkeypatch):
    prefix, host = layout
    before = managed(prefix, host)
    pointer = root(prefix) / 'activation-pending.json'
    original = journal._renameat_noreplace
    external = None

    def collide(directory, source, destination):
        nonlocal external
        if destination == pointer.name and external is None:
            pointer.write_bytes(b'foreign pending occupant')
            external = journal.snapshot(pointer)
        return original(directory, source, destination)

    monkeypatch.setattr(journal, '_renameat_noreplace', collide)
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new')
    assert caught.value.error_code == 'installation_recovery_unavailable'
    assert journal.snapshot(pointer) == external
    assert managed(prefix, host) == before


def test_process_death_after_pending_capture_replays_completed_receipt(layout):
    prefix, host = layout
    ident = str(uuid.uuid4())
    kill_at(prefix, host, point='pending_captured', ident=ident)
    assert load(prefix, ident)['state'] == 'completed'
    before = managed(prefix, host)
    replay = install.activate(prefix, 'new', transaction_id=ident)
    assert replay['transaction_state'] == 'completed' and replay['recovered']
    assert managed(prefix, host) == before
