"""All-four Host links: preflight and compensated upgrade/rollback.

Synthetic activation fixtures only; candidate installation has a separate real
wheel/venv diagnostic. All roots are temporary, never the actual user's HOME.
"""
import json
import os
from pathlib import Path

import pytest

from deck_master import install
from deck_master.errors import HostSkillConflict


def _release(prefix, name, skills=install.PUBLIC_SKILLS):
    root = prefix / '.deck-master/releases' / name
    root.mkdir(parents=True)
    (root / 'release.json').write_text(json.dumps({'status': 'candidate_ready'}))
    for skill in skills:
        target = root / 'skill' / skill / 'SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text(f'{skill} {name}')
    return root


@pytest.fixture
def layout(tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'host'))
    prefix = tmp_path / 'prefix with spaces'
    _release(prefix, 'old', ('deck-master',))
    _release(prefix, 'new')
    return prefix, tmp_path / 'host/skills'


def _snapshot(prefix, host):
    rows = {}
    for root in (prefix, host):
        if root.exists():
            for path in root.rglob('*'):
                if path.is_symlink():
                    rows[str(path)] = ('link', os.readlink(path))
                elif path.is_file() and path.name != 'install.lock':
                    rows[str(path)] = ('file', path.read_bytes())
                elif path.is_dir():
                    rows[str(path)] = ('directory',)
    return rows


@pytest.mark.parametrize('name', install.PUBLIC_SKILLS)
@pytest.mark.parametrize('occupant', ['directory', 'file', 'foreign-link', 'dangling-link'])
def test_every_link_conflict_aborts_before_any_activation(layout, name, occupant):
    prefix, host = layout
    install.activate(prefix, 'old', register_host=False)
    path = host / name
    path.parent.mkdir(parents=True)
    if occupant == 'directory':
        path.mkdir()
        (path / 'user-data').write_text('preserve')
    elif occupant == 'file':
        path.write_text('preserve')
    else:
        target = prefix / ('foreign' if occupant == 'foreign-link' else 'absent')
        if occupant == 'foreign-link':
            target.mkdir()
        path.symlink_to(target)
    before = _snapshot(prefix, host)
    with pytest.raises(HostSkillConflict):
        install.activate(prefix, 'new')
    assert _snapshot(prefix, host) == before


def test_upgrade_four_links_rollback_single_and_return(layout):
    prefix, host = layout
    install.activate(prefix, 'old')
    report = install.activate(prefix, 'new')
    assert len(report['skill_links']) == 4
    for name in install.PUBLIC_SKILLS:
        assert os.readlink(host / name) == str(prefix / '.deck-master/current/skill' / name)
        assert (host / name / 'SKILL.md').read_text() == f'{name} new'
    install.rollback(prefix)
    assert (host / 'deck-master/SKILL.md').read_text() == 'deck-master old'
    assert all(not (host / name).is_symlink() for name in install.PUBLIC_SKILLS[1:])
    install.rollback(prefix)
    assert all((host / name / 'SKILL.md').is_file() for name in install.PUBLIC_SKILLS)


@pytest.mark.parametrize('failure', install.PUBLIC_SKILLS)
def test_failure_during_each_link_creation_compensates_every_pointer_and_link(layout, monkeypatch, failure):
    prefix, host = layout
    install.activate(prefix, 'old', register_host=False)
    before = _snapshot(prefix, host)
    original = install._replace_link

    def fail(path, target):
        if path.parent == host and path.name == failure:
            raise OSError('injected individual link creation failure')
        return original(path, target)

    monkeypatch.setattr(install, '_replace_link', fail)
    with pytest.raises(OSError, match='injected'):
        install.activate(prefix, 'new')
    assert _snapshot(prefix, host) == before


def test_failure_retiring_old_links_compensates_rollback(layout, monkeypatch):
    prefix, host = layout
    install.activate(prefix, 'old')
    install.activate(prefix, 'new')
    before = _snapshot(prefix, host)
    original = install._unlink

    def fail(path):
        if path.name == 'deck-review':
            raise OSError('injected retirement failure')
        return original(path)

    monkeypatch.setattr(install, '_unlink', fail)
    with pytest.raises(OSError, match='retirement'):
        install.rollback(prefix)
    assert _snapshot(prefix, host) == before


def test_opt_out_preserves_all_four_host_paths(layout):
    prefix, host = layout
    install.activate(prefix, 'new')
    before = {name: os.readlink(host / name) for name in install.PUBLIC_SKILLS}
    install.activate(prefix, 'old', register_host=False)
    assert {name: os.readlink(host / name) for name in install.PUBLIC_SKILLS} == before
