"""Third review: whole-deck revision dependencies and activation compensation."""
import os

import pytest

from deck_master import install, service, tasks
from deck_master.errors import HostSkillConflict
from test_install_host_skill import _make_release
from test_flow_quality import _setup_project_with_pages, _raw_commit


@pytest.mark.parametrize('change', ['reverse', 'remove', 'add', 'edit'])
def test_revision_tracks_ordered_document(tmp_path, change):
    project, store, _ = _setup_project_with_pages(tmp_path)
    pending = service.inputs_update(project, patch={'reason': 'new audience', 'task_patch': {'audience': 'other'}},
                                    base_revision=store.load_document()['revision_id'], operation_id='new-input')['pending_tasks'][0]
    task = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                if store.read_object_json(ref)['task_id'] == pending['task_id'])
    def mutate(doc):
        if change == 'reverse':
            doc['pages'] = list(reversed(doc['pages']))
        elif change == 'remove':
            doc['pages'] = doc['pages'][:-1]
        else:
            page = store.read_object_json(doc['pages'][0]['page'])
            page['customer_visible']['title'] = 'Changed body'
            if change == 'add':
                page['page_id'] = 'p04'
                doc['pages'].append({**doc['pages'][0], 'page_id': 'p04', 'page': store.put_json_object(page)})
            else:
                doc['pages'][0]['page'] = store.put_json_object(page)
    _raw_commit(store, mutate)
    assert not tasks.task_inputs_current(store, store.load_document(), task)
    resumed = service.continue_project(project)['pending_tasks']
    assert len(resumed) == 1 and resumed[0]['intent'] == 'input_revision'
    assert resumed[0]['task_id'] != task['task_id']
    assert service.task_status(project, task_id=task['task_id'])['status'] == 'superseded'


@pytest.mark.parametrize('kind', ['dangling', 'cycle', 'file'])
@pytest.mark.parametrize('level', ['skills', 'home', 'ancestor'])
def test_host_parent_conflicts_are_preflighted(tmp_path, monkeypatch, kind, level):
    prefix = tmp_path / 'prefix'
    home = tmp_path / 'host' / 'home'
    monkeypatch.setenv('CODEX_HOME', str(home))
    _make_release(prefix, 'new')
    path = {'skills': home / 'skills', 'home': home, 'ancestor': home.parent}[level]
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == 'file':
        path.write_text('user')
    else:
        path.symlink_to(path.name if kind == 'cycle' else 'missing')
    with pytest.raises(HostSkillConflict):
        install.activate(prefix, 'new')
    assert not (prefix / '.deck-master/current').is_symlink()


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('after_write', [False, True])
def test_registration_failure_restores_activation(tmp_path, monkeypatch, existing, after_write):
    prefix, home = tmp_path / 'prefix', tmp_path / 'host'
    monkeypatch.setenv('CODEX_HOME', str(home))
    _make_release(prefix, 'new')
    if existing:
        _make_release(prefix, 'old')
        install.activate(prefix, 'old', register_host=False)
    original = install._replace_link
    def fail(path, target):
        if path == home / 'skills/deck-master':
            if after_write:
                original(path, target)
            raise OSError('injected registration failure')
        return original(path, target)
    monkeypatch.setattr(install, '_replace_link', fail)
    with pytest.raises(OSError, match='injected'):
        install.activate(prefix, 'new')
    root = prefix / '.deck-master'
    assert (os.readlink(root / 'current') if (root / 'current').is_symlink() else None) == ('releases/old' if existing else None)
    assert not (root / 'previous').is_symlink()
    assert not (home / 'skills/deck-master').is_symlink()
    if not existing:
        assert not (root / 'bin').exists()
    assert not home.exists()


def test_import_reorder_refuses_old_result_and_continue_retires_it(tmp_path):
    project, store, _ = _setup_project_with_pages(tmp_path)
    pending = service.inputs_update(project, patch={'reason': 'new audience', 'task_patch': {'audience': 'other'}},
                                    base_revision=store.load_document()['revision_id'], operation_id='new-input')['pending_tasks'][0]
    task = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                if store.read_object_json(ref)['task_id'] == pending['task_id'])
    old = store.load_document()
    pages = [store.read_object_json(entry['page']) for entry in old['pages']]
    service.import_draft(project, draft_payload={'pages': pages, 'page_order': ['p03', 'p02', 'p01']})
    before = store.load_document()
    with pytest.raises(tasks.StaleInputContext):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                              produced_against=task['produced_against'], result_payload={'kind': 'compose', 'content_update': {
                                  'input_digest': task['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
                                  'page_order': ['p01', 'p02', 'p03'], 'unchanged_reason': 'unchanged'}})
    assert store.load_document() == before
    pending = service.continue_project(project)['pending_tasks']
    assert all(t['task_id'] != task['task_id'] for t in pending)
    assert service.task_status(project, task_id=task['task_id'])['status'] == 'superseded'
    assert service.inputs_show(project)['input_alignment'] == 'current'


@pytest.mark.parametrize('scenario', ['legacy', 'deferred', 'rollback'])
@pytest.mark.parametrize('point', ['migration', 'registration'])
def test_failure_compensates_migration_and_rollback(tmp_path, monkeypatch, scenario, point):
    from test_install_host_skill import _build_legacy_layout
    prefix, home = tmp_path / 'prefix', tmp_path / 'host'
    monkeypatch.setenv('CODEX_HOME', str(home))
    _make_release(prefix, 'new')
    _make_release(prefix, 'old', with_skill=False)
    if scenario in ('legacy', 'deferred'):
        _build_legacy_layout(prefix, home)
        if scenario == 'deferred':
            install.activate(prefix, 'old', register_host=False)
    else:
        install.activate(prefix, 'old')
        install.activate(prefix, 'new')
    def snapshot():
        paths = list((prefix / '.deck-master').rglob('*')) + list(home.rglob('*'))
        return {str(p): ('link', os.readlink(p)) if p.is_symlink() else
                ('file', p.read_bytes()) if p.is_file() else ('dir',) for p in paths if p.name != 'install.lock'}
    before = snapshot()
    if point == 'migration' and scenario != 'rollback':
        original = install._unlink
        def fail(path):
            original(path)
            raise OSError('injected migration')
        monkeypatch.setattr(install, '_unlink', fail)
    else:
        original = install._sync_host_skill
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError('injected registration')
        monkeypatch.setattr(install, '_sync_host_skill', fail)
    with pytest.raises(OSError, match='injected'):
        if scenario == 'rollback':
            install.rollback(prefix)
        else:
            install.activate(prefix, 'new')
    assert snapshot() == before


def test_compensation_preserves_external_occupant_and_reports(tmp_path, monkeypatch):
    prefix, home = tmp_path / 'prefix', tmp_path / 'host'
    monkeypatch.setenv('CODEX_HOME', str(home))
    _make_release(prefix, 'new')
    def fail(*args, **kwargs):
        current = prefix / '.deck-master/current'
        current.unlink()
        current.write_text('external writer')
        raise OSError('original failure')
    monkeypatch.setattr(install, '_sync_host_skill', fail)
    with pytest.raises(RuntimeError, match='original failure.*compensation incomplete.*current.*backups:'):
        install.activate(prefix, 'new')
    assert (prefix / '.deck-master/current').read_text() == 'external writer'


def test_valid_directory_symlink_and_optout_broken_host(tmp_path, monkeypatch):
    prefix, home = tmp_path / 'prefix', tmp_path / 'host'
    monkeypatch.setenv('CODEX_HOME', str(home))
    _make_release(prefix, 'new')
    real = tmp_path / 'real'
    real.mkdir()
    home.symlink_to(real, target_is_directory=True)
    install.activate(prefix, 'new')
    assert (real / 'skills/deck-master/SKILL.md').is_file()
    home.unlink()
    home.symlink_to('missing')
    install.activate(prefix, 'new', register_host=False)
    assert os.readlink(home) == 'missing'


@pytest.mark.parametrize('timing', ['settlement', 'commit'])
def test_accept_rechecks_after_settlement_and_commit_race(tmp_path, monkeypatch, timing):
    from deck_master.store import StoreError
    project, store, _ = _setup_project_with_pages(tmp_path)
    task = service.inputs_update(project, patch={'reason': 'new audience', 'task_patch': {'audience': 'other'}},
                                 base_revision=store.load_document()['revision_id'], operation_id='new-input')['pending_tasks'][0]
    tasks.allocate_call_allowances(store, task_id=task['task_id'], count=1)
    service.task_start(project, task_id=task['task_id'], execution_ref='race')
    tasks.call_begin(store, task_id=task['task_id'], allowance_id='call-1', execution_ref='race')
    stored = tasks._lookup_task(store.load_document(), task['task_id'], store)
    original = type(store).commit_change
    fired = False
    def racing(self, **kwargs):
        nonlocal fired
        is_settlement = kwargs['operation_id'].startswith('settle-')
        if not fired and is_settlement == (timing == 'settlement'):
            fired = True
            if timing == 'settlement':
                result = original(self, **kwargs)
            _raw_commit(store, lambda doc: doc['pages'].reverse())
            if timing == 'settlement':
                return result
        return original(self, **kwargs)
    monkeypatch.setattr(type(store), 'commit_change', racing)
    with pytest.raises((tasks.StaleInputContext, StoreError)):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                              produced_against=task['produced_against'], result_payload={
                                  'kind': 'compose', 'usage_events': [{'allowance_id': 'call-1', 'outcome': 'unknown'}],
                                  'content_update': {'input_digest': stored['input_digest'], 'upsert_pages': [],
                                                     'remove_page_ids': [], 'page_order': ['p01', 'p02', 'p03'],
                                                     'unchanged_reason': 'unchanged'}})
    assert fired, tasks._lookup_task(store.load_document(), task['task_id'], store)
    current = store.load_document()
    assert [p['page_id'] for p in current['pages']] == ['p03', 'p02', 'p01']
    assert tasks._lookup_task(current, task['task_id'], store)['call_allowances'][0]['state'] == 'unknown'


def test_cli_reorder_then_late_accept_is_exit_five(tmp_path, monkeypatch, capsys):
    import json
    from deck_master.cli import main
    from test_flow_quality import _load_fixture
    from deck_master.store import Store
    monkeypatch.setenv('DECK_MASTER_NO_AUTO_VIEW', '1')
    project = tmp_path / 'cli-project'
    draft = tmp_path / 'draft.json'
    draft.write_text(json.dumps(_load_fixture('initial-pages.json')))
    assert main(['create', '--brief', 'test', '--draft', str(draft), '--out', str(project)]) == 0
    store = Store(project)
    patch = tmp_path / 'patch.json'
    patch.write_text(json.dumps({'reason': 'audience', 'task_patch': {'audience': 'changed'}}))
    assert main(['inputs', 'update', '--project', str(project), '--patch', str(patch),
                 '--base-revision', store.load_document()['revision_id'], '--operation-id', 'input-cli']) == 0
    task = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                if store.read_object_json(ref).get('intent') == 'input_revision')
    reordered = json.loads(draft.read_text())
    reordered['page_order'].reverse()
    draft.write_text(json.dumps(reordered))
    assert main(['import-draft', '--project', str(project), '--input', str(draft)]) == 0
    before = store.load_document()
    result = tmp_path / 'result.json'
    result.write_text(json.dumps({'kind': 'compose', 'content_update': {
        'input_digest': task['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
        'page_order': ['p01', 'p02', 'p03'], 'unchanged_reason': 'unchanged'}}))
    assert main(['task', 'accept', '--project', str(project), '--task-id', task['task_id'],
                 '--operation-id', task['operation_id'], '--produced-against', task['produced_against'],
                 '--result', str(result)]) == 5
    assert 'stale_input_context' in capsys.readouterr().err
    assert store.load_document() == before


def test_cli_install_conflict_and_compensation_failure_codes(tmp_path, monkeypatch, capsys):
    from deck_master.cli import main
    prefix, home = tmp_path / 'prefix', tmp_path / 'host'
    monkeypatch.setenv('CODEX_HOME', str(home))
    _make_release(prefix, 'new')
    home.symlink_to('missing')
    command = ['install', 'activate', '--prefix', str(prefix), '--release-id', 'new']
    assert main(command) == 5
    assert 'host_skill_conflict' in capsys.readouterr().err
    home.unlink()
    def fail(*args, **kwargs):
        current = prefix / '.deck-master/current'
        current.unlink()
        current.mkdir()
        raise OSError('registration failed')
    monkeypatch.setattr(install, '_sync_host_skill', fail)
    assert main(command) == 4
    error = capsys.readouterr().err
    assert 'compensation incomplete' in error and 'registration failed' in error
    assert (prefix / '.deck-master/current').is_dir()


@pytest.mark.parametrize('missing', ['source-reading', 'content-examples', 'input-update'])
def test_compose_doctor_refuses_incomplete_method_set(tmp_path, monkeypatch, missing):
    from deck_master import doctor
    from deck_master.method_resources import RELATIVE_PATHS, method_ids_for
    root = tmp_path / 'skill'
    (root / 'references').mkdir(parents=True)
    (root / 'SKILL.md').write_text('skill')
    for method in method_ids_for('compose', intent='input_revision'):
        if method != missing:
            (root / RELATIVE_PATHS[method]).write_text('method')
    monkeypatch.setattr(doctor, 'resolve_root', lambda: root)
    result = doctor.diagnose('compose')
    assert result['status'] == 'needs_tool'
    assert next(c for c in result['checks'] if c['name'] == 'method:' + RELATIVE_PATHS[missing])['status'] == 'unavailable'
