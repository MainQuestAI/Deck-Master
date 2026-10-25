"""Fresh source identities remain observed across the Q2 performance path."""
import subprocess
from types import SimpleNamespace

import pytest

from deck_master import capabilities


def checkout(tmp_path, monkeypatch):
    import deck_master
    module = tmp_path / 'src/deck_master/__init__.py'
    module.parent.mkdir(parents=True)
    module.write_text('# synthetic identity source\n')
    monkeypatch.setattr(deck_master, '__file__', str(module))
    monkeypatch.setattr(capabilities, 'resolve_root', lambda: tmp_path)
    return module


def test_installation_identity_observes_new_commit_dirty_state_and_bytes(tmp_path, monkeypatch):
    module = checkout(tmp_path, monkeypatch)
    run = subprocess.run
    def git(*args):
        return run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True, text=True).stdout.strip()
    git('init', '-q')
    git('add', '.')
    git('-c', 'user.name=Synthetic Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'first')
    commands = []
    def observed(argv, **kwargs):
        commands.append(argv[3:])
        return run(argv, **kwargs)
    monkeypatch.setattr(capabilities.subprocess, 'run', observed)
    first = capabilities.installation_identity()
    assert first['source'] == {'sha': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'), 'dirty': False}
    assert commands == [['rev-parse', 'HEAD', 'HEAD^{tree}'], ['status', '--porcelain']]
    module.write_text('# changed source bytes\n')
    dirty = capabilities.installation_identity()
    assert dirty['source'] == {**first['source'], 'dirty': True}
    assert dirty['module_sha256'] != first['module_sha256']
    git('add', '.')
    git('-c', 'user.name=Synthetic Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'second')
    after = capabilities.installation_identity()
    assert after['source']['sha'] != first['source']['sha']
    assert after['source']['tree'] != first['source']['tree']
    assert after['source']['dirty'] is False
    assert commands == [['rev-parse', 'HEAD', 'HEAD^{tree}'], ['status', '--porcelain']] * 3


@pytest.mark.parametrize('output', ['', 'a' * 40, 'a' * 40 + '\n' + 'b' * 40 + '\nextra', 'HEAD\nHEAD^{tree}', 'a' * 39 + '\n' + 'b' * 40])
def test_incomplete_or_malformed_git_batch_never_becomes_an_identity(tmp_path, monkeypatch, output):
    checkout(tmp_path, monkeypatch)
    calls = []
    def malformed(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr(capabilities.subprocess, 'run', malformed)
    assert capabilities.installation_identity()['source'] is None
    assert len(calls) == 1
