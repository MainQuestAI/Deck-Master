"""Preparing recovery needs witnesses for every frozen existing managed path."""
from __future__ import annotations

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
from test_install_preparation_compatibility import rc3_installer, symlink_layout  # noqa: F401
from test_install_transaction_recovery import kill_at, load, managed, root


EARLY_EXIT = r'''
import json, os, sys
from pathlib import Path
from deck_master import install, activation_transaction as journal
p = json.loads(sys.argv[1])
os.environ['CODEX_HOME'] = p['host_parent']
if p['window'] == 'begin':
    original = journal.Plan.begin
    def begin(self):
        original(self)
        os._exit(91)
    journal.Plan.begin = begin
elif p['window'] == 'last_intent':
    original = journal.Plan.intent
    def intent(self, path, kind, expected):
        item = original(self, path, kind, expected)
        host_path = Path(p['host_parent'], 'skills').resolve() / 'deck-master'
        if kind == 'witness' and expected == journal.snapshot(host_path):
            os._exit(91)
        return item
    journal.Plan.intent = intent
else:
    original = journal.Plan.anchor
    def anchor(self, path, identity):
        host_path = Path(p['host_parent'], 'skills').resolve() / 'deck-master'
        if p['window'] == 'last_unregistered' and path == host_path:
            os._exit(91)
        original(self, path, identity)
        if p['window'] == 'partial' and self.record['inode_anchors']:
            os._exit(91)
    journal.Plan.anchor = anchor
install.activate(p['prefix'], 'new', transaction_id=p['ident'])
'''


def exit_during_old_witness_coverage(prefix, host, ident, window):
    params = {'prefix': str(prefix), 'host_parent': str(host.parent), 'ident': ident, 'window': window}
    result = subprocess.run([sys.executable, '-c', EARLY_EXIT, json.dumps(params)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 91, result.stderr
    record = load(prefix, ident)
    assert record['state'] == 'preparing'
    expected_count = {'begin': 0, 'partial': 1, 'last_unregistered': 2, 'last_intent': 2}
    assert len(record['inode_anchors']) == expected_count[window]
    if window == 'begin':
        assert record['preparations'] == record['steps'] == []
    return record


@pytest.mark.parametrize('window', ['begin', 'partial', 'last_unregistered', 'last_intent'])
@pytest.mark.parametrize('external_replacement', [False, True])
def test_incomplete_old_witness_coverage_preserves_entire_scene(symlink_layout, monkeypatch, window, external_replacement):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    record = exit_during_old_witness_coverage(prefix, logical, ident, window)
    # At the partial window the list is nonempty, but this particular existing
    # Host path has no witness at all. At begin, reproduce the reported current.
    path = root(prefix) / 'current' if window == 'begin' else actual / 'deck-master'
    frozen = next(row['before'] for row in record['watched'] if row['path'] == str(path))
    assert not any(row['source'] == str(path) for row in record['inode_anchors'])
    if window in ('last_unregistered', 'last_intent'):
        # All other existing watched objects are covered; report this exact
        # missing path rather than merely requiring any nonempty proof list.
        assert all(row['before'] is None or row['path'] == str(path) or
                   any(anchor['source'] == row['path'] for anchor in record['inode_anchors'])
                   for row in record['watched'])
        assert not any(item['path'].endswith('.after') for item in record['preparations'])
        intents = [item for item in record['preparations'] if item['kind'] == 'witness' and item['expected'] == frozen]
        assert len(intents) == (1 if window == 'last_intent' else 0)
        if intents:
            assert intents[0]['identity'] is None and journal.snapshot(Path(intents[0]['path'])) is None
    raw_snapshot = journal.snapshot
    if external_replacement:
        path.unlink()
        path.symlink_to(frozen['target'])
        external = raw_snapshot(path)
        # Explicit synthetic collision control: the child exit and replacement
        # are real; tmpfs/overlay need not recycle the removed inode in a test.
        def recycled(candidate):
            observed = raw_snapshot(candidate)
            if observed is not None and (observed['dev'], observed['ino']) == (external['dev'], external['ino']):
                return {**observed, 'dev': frozen['dev'], 'ino': frozen['ino']}
            return observed
        monkeypatch.setattr(journal, 'snapshot', recycled)
    journal_path = journal.record_path(root(prefix), ident)
    original_journal = journal_path.read_bytes()
    def scene():
        return {str(item): raw_snapshot(item) for item in (root(prefix), *root(prefix).rglob('*'), actual, *actual.iterdir())}
    before = scene()
    before_managed = {name: raw_snapshot(Path(name)) for name in managed(prefix, logical)}
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.transaction_state == 'preparing'
    assert caught.value.details['path'] in {row['path'] for row in record['watched']}
    if window in ('last_unregistered', 'last_intent'):
        assert caught.value.details['path'] == str(path)
    assert journal_path.read_bytes() == original_journal
    assert scene() == before
    assert {name: raw_snapshot(Path(name)) for name in before_managed} == before_managed
    assert os.readlink(root(prefix) / 'current') == 'releases/old'


def test_first_unconfirmed_old_witness_exit_has_incomplete_coverage(symlink_layout):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    kill_at(prefix, logical, point='witness_created', name='current', ident=ident)
    record = load(prefix, ident)
    assert record['inode_anchors'] == []
    assert len(record['preparations']) == 1
    intent = record['preparations'][0]
    assert intent['kind'] == 'witness' and intent['identity'] is None
    assert journal.snapshot(Path(intent['path'])) == intent['expected']
    before = managed(prefix, logical)
    journal_path = journal.record_path(root(prefix), ident)
    original = journal_path.read_bytes()
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.details['path'] == str(root(prefix) / 'bin/deck-master')
    assert journal_path.read_bytes() == original and managed(prefix, logical) == before
    assert journal.snapshot(Path(intent['path'])) == intent['expected']


@pytest.mark.parametrize('missing', ['current', 'launcher', 'host'])
def test_complete_old_witness_set_requires_every_actual_artifact(symlink_layout, missing):
    prefix, logical, actual = symlink_layout
    ident = str(uuid.uuid4())
    kill_at(prefix, logical, point='preparation_created', ident=ident)
    record = load(prefix, ident)
    assert record['state'] == 'preparing' and record['preparations'][-1]['identity'] is None
    path = {'current': root(prefix) / 'current', 'launcher': root(prefix) / 'bin/deck-master',
            'host': actual / 'deck-master'}[missing]
    before = next(row['before'] for row in record['watched'] if row['path'] == str(path))
    anchor = next(row for row in record['inode_anchors'] if row['source'] == str(path))
    intent = next(item for item in record['preparations'] if item['path'] == anchor['path'])
    assert intent['identity'] == anchor['identity'] == before
    assert all(any(item['kind'] == 'witness' and item['identity'] == watched['before']
                   for item in record['preparations'])
               for watched in record['watched'] if watched['before'] is not None)
    Path(anchor['path']).unlink()
    def scene():
        return {str(item): journal.snapshot(item) for item in (root(prefix), *root(prefix).rglob('*'), actual, *actual.iterdir())}
    preserved = scene()
    journal_path = journal.record_path(root(prefix), ident)
    original = journal_path.read_bytes()
    with pytest.raises(InstallationTransactionError) as caught:
        install.activate(prefix, 'new', transaction_id=ident)
    assert caught.value.error_code == 'installation_recovery_conflict'
    assert caught.value.details['path'] == str(path)
    assert caught.value.transaction_state == 'preparing'
    assert scene() == preserved and journal_path.read_bytes() == original
