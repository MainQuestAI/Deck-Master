"""W03 real local processes and HTTP. Synthetic projects, isolated registries."""
import copy
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from urllib.parse import urlsplit

import pytest

from deck_master import cli, launcher, local_runtime as runtime, registry, service, ui_journal
from deck_master.local_state import LocalStateError, write_json
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def http(url, route, data=None, *, headers=None):
    parsed = urlsplit(url)
    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.request('GET' if data is None else 'POST', route,
                           body=json.dumps(data).encode() if data is not None else None, headers=headers or {})
        response = connection.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if 'json' in response.getheader('Content-Type', '') else raw
    finally:
        connection.close()


def auth(url):
    return {'Origin': url.rstrip('/'), 'X-Deck-Token': http(url, '/api/session')[1]['token']}


def project(path):
    service.create(path, brief='合成材料流程', title='合成项目', audience='验证者', project_format='workbench.v3')
    return path


@pytest.fixture
def launcher_service(tmp_path):
    reg = tmp_path / 'config' / 'projects.json'
    desc = runtime.descriptor(registry=reg)
    state = runtime.ensure(desc)
    try:
        yield reg, desc, state
    finally:
        runtime.stop(desc)


def test_empty_launcher_is_not_a_fake_project_and_does_not_scan(launcher_service, tmp_path):
    reg, desc, state = launcher_service
    project(tmp_path / 'unregistered')
    code, data = http(state['url'], '/api/projects')
    assert code == 200 and data['projects'] == []
    assert not reg.exists()
    assert not (reg.parent / '.deckmaster').exists()
    health = http(state['url'], '/api/health')[1]
    assert health['role'] == 'launcher' and health['identity'] == desc['identity']
    assert state['pid'] != os.getpid() and state['port'] != 0
    assert all(health[key] == state[key] for key in runtime.HEALTH_KEYS)
    assert http(state['url'], '/v2/')[0] == (200 if health['ui_available'] else 404)


def test_registry_canonical_registration_remove_and_no_activity_rewrites(tmp_path):
    reg = tmp_path / 'registry.json'
    p = project(tmp_path / 'project')
    alias = tmp_path / 'alias'
    alias.symlink_to(p, target_is_directory=True)
    entry = registry.register(reg, alias)['project']
    registry.register(reg, p)
    before = reg.read_bytes(), reg.stat().st_mtime_ns
    assert len(registry.listing(reg)['projects']) == 1
    assert entry['path'] == str(p.resolve())
    info = ui_journal.project_info(p)
    ui_journal.save_position(p, position={'schema_version': 'ui_position.v1',
        'project_id': info['project_id'], 'project_identity': info['project_identity'],
        'page_id': None, 'surface': 'content', 'layer': 'content', 'revision': None})
    assert registry.listing(reg)['projects'][0]['position']['position']['surface'] == 'content'
    assert (reg.read_bytes(), reg.stat().st_mtime_ns) == before
    registry.remove(reg, entry['entry_id'])
    assert registry.listing(reg)['projects'] == [] and Store(p).load_document()


def test_registry_concurrent_registrations_and_invalid_file_are_not_lost(tmp_path):
    reg = tmp_path / 'registry.json'
    projects = [project(tmp_path / f'p{i}') for i in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda p: registry.register(reg, p), projects))
    assert len(registry.listing(reg)['projects']) == 4
    reg.write_text('{broken')
    with pytest.raises(LocalStateError):
        registry.register(reg, projects[0])
    assert reg.read_text() == '{broken'


def test_registry_refuses_old_or_invalid_project_without_initialization(tmp_path):
    reg = tmp_path / 'registry.json'
    missing = tmp_path / 'missing'
    with pytest.raises(LocalStateError):
        registry.register(reg, missing)
    assert not missing.exists() and not reg.exists()
    p = project(tmp_path / 'project')
    state = p / '.deckmaster'
    state.rename(tmp_path / 'elsewhere')
    state.symlink_to(tmp_path / 'elsewhere', target_is_directory=True)
    with pytest.raises(RuntimeError):
        registry.register(reg, p)
    assert not reg.exists()
    reg.symlink_to(tmp_path / 'target.json')
    with pytest.raises(LocalStateError):
        registry.listing(reg)
    assert not (tmp_path / 'target.json').exists()


def test_create_material_update_handoff_preserves_one_eligible_compose(tmp_path):
    reg = tmp_path / 'registry.json'
    p = tmp_path / '中文项目'
    result = registry.create_project(reg, path=str(p), title='中文名称', brief='整理材料', audience='内部读者', page_limit=12)
    assert result['registered'] and result['model_started'] is False
    original = result['pending_tasks'][0]['task_id']
    assert result['pending_tasks'][0]['staging_dir'].startswith(str(p / '.deckmaster' / 'staging'))
    assert '.deck-master-create-' not in json.dumps(result)
    handoff = launcher.compose_handoff(p)
    assert handoff['task_id'] == original and handoff['model_started'] is False
    assert Store(p).load_document()['sources'] == []
    assert Store(p).load_document()['task']['page_limit'] == 12
    source = tmp_path / 'facts.md'
    source.write_text('# 合成材料\n三个步骤，未验证成效。')
    store = Store(p)
    service.inputs_update(p, patch={'reason': '补充合成材料', 'source_changes': {'add': [{'path': str(source)}]}},
                          base_revision=store.current_revision_id(), operation_id='add-material')
    before = store.current_revision_id()
    first = launcher.compose_handoff(p)
    second = launcher.compose_handoff(p)
    assert first == second and first['task_id'] != original
    assert store.current_revision_id() == before
    tasks = [store.read_object_json(ref) for ref in store.load_document()['tasks']]
    assert len(tasks) == 2
    assert [t['status'] for t in tasks if t['task_id'] == original] == ['superseded']
    assert sum(t['status'] == 'awaiting_host' for t in tasks) == 1
    assert all(not t['call_allowances'] for t in tasks)
    assert not list(tmp_path.glob('.deck-master-create-*'))


def test_create_validation_and_registry_preflight_never_replace_files(tmp_path, monkeypatch):
    reg = tmp_path / 'registry.json'
    p = tmp_path / 'new'
    for field in ('title', 'brief', 'audience'):
        args = dict(path=str(p), title='Example', brief='Facts', audience='Readers')
        args[field] = '  '
        with pytest.raises(LocalStateError):
            registry.create_project(reg, **args)
    assert not p.exists()
    reg.write_text('not JSON')
    with pytest.raises(LocalStateError):
        registry.create_project(reg, path=str(p), title='Example', brief='Facts', audience='Readers')
    assert not p.exists()
    reg.unlink()
    def fail_register(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(registry, 'register', fail_register)
    result = registry.create_project(reg, path=str(p), title='Example', brief='Facts', audience='Readers')
    assert result['registered'] is False and Store(p).load_document()['tasks']
    assert not reg.exists()
    with pytest.raises(LocalStateError):
        registry.create_project(reg, path=str(p), title='Another', brief='Facts', audience='Readers')
    assert Store(p).load_document()['task']['title'] == 'Example'


def test_failed_project_creation_keeps_sources_and_no_partial_project(tmp_path, monkeypatch):
    source = tmp_path / 'facts.md'
    source.write_text('keep original')
    def fail(*args, **kwargs):
        Path(args[0]).mkdir(parents=True)
        (Path(args[0]) / 'partial').write_text('staging only')
        raise OSError('interrupted')
    monkeypatch.setattr(service, 'create', fail)
    with pytest.raises(OSError):
        registry.create_project(tmp_path / 'registry.json', path=str(tmp_path / 'new'),
                                title='Example', brief='Facts', audience='Readers', sources=[source])
    assert not (tmp_path / 'new').exists() and source.read_text() == 'keep original'
    assert not list(tmp_path.glob('.deck-master-create-*'))


def test_concurrent_starts_share_one_detached_instance(tmp_path):
    desc = runtime.descriptor(registry=tmp_path / 'registry.json')
    with ThreadPoolExecutor(max_workers=3) as pool:
        states = list(pool.map(lambda _: runtime.ensure(desc), range(3)))
    try:
        assert len({s['instance_id'] for s in states}) == 1
        assert sum(not s['reused'] for s in states) == 1
    finally:
        runtime.stop(desc)


def test_launcher_and_project_shutdown_are_independent(launcher_service, tmp_path):
    reg, launch_desc, launch = launcher_service
    p = project(tmp_path / 'project')
    desc = runtime.descriptor(project=p)
    state = runtime.ensure(desc)
    try:
        registry.register(reg, p)
        before = reg.read_bytes()
        runtime.stop(launch_desc)
        assert runtime.healthy(state, desc) and reg.read_bytes() == before
        restarted = runtime.ensure(launch_desc)
        assert restarted['instance_id'] != launch['instance_id']
        runtime.stop(desc)
        assert runtime.healthy(restarted, launch_desc)
        assert Store(p).load_document() and reg.read_bytes() == before
    finally:
        runtime.stop(desc)


def test_wrong_identity_pid_and_build_are_never_reused(launcher_service, tmp_path):
    reg, desc, state = launcher_service
    for key, value in [('pid', state['pid'] + 1000), ('role', 'project'), ('identity', '0' * 64),
                       ('instance_id', 'f' * 32), ('build_id', 'old'), ('service_version', 'old'),
                       ('url', 'http://example.test/'), ('protocol_version', 'old')]:
        assert not runtime.healthy({**state, key: value}, desc), key
    other = runtime.descriptor(registry=tmp_path / 'other.json')
    write_json(other['state_path'], state)
    second = runtime.ensure(other)
    try:
        assert second['instance_id'] != state['instance_id'] and runtime.healthy(state, desc)
    finally:
        runtime.stop(other)


def test_stale_crashed_service_restarts_and_cleans_only_its_instance(tmp_path):
    desc = runtime.descriptor(registry=tmp_path / 'registry.json')
    first = runtime.ensure(desc)
    os.kill(first['pid'], signal.SIGKILL)
    # Reap the child before restart so a listening-but-dying process cannot win.
    os.waitpid(first['pid'], 0)
    second = runtime.ensure(desc)
    try:
        assert first['instance_id'] != second['instance_id']
        runtime.clear_own_state(desc, first['instance_id'])
        assert runtime.read_state(desc)['instance_id'] == second['instance_id']
    finally:
        runtime.stop(desc)
    assert not desc['state_path'].exists()


def test_explicit_port_conflict_and_stale_pid_are_not_signalled(tmp_path, monkeypatch):
    desc = runtime.descriptor(registry=tmp_path / 'registry.json')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        with pytest.raises(runtime.PortConflict):
            runtime.ensure(desc, port=listener.getsockname()[1])
    assert not desc['state_path'].exists()
    write_json(desc['state_path'], {'pid': os.getpid(), 'port': 1, 'url': 'http://127.0.0.1:1/'})
    monkeypatch.setattr(os, 'kill', lambda *_: pytest.fail('must not signal an unverified PID'))
    assert runtime.stop(desc)['status'] == 'not_running'


def test_launcher_get_host_and_post_origin_instance_and_size_guards(launcher_service, tmp_path):
    reg, desc, state = launcher_service
    url = state['url']
    headers = auth(url)
    p = project(tmp_path / 'project')
    body = {'path': str(p)}
    assert http(url, '/api/projects', headers={'Host': 'evil.example'})[0] == 403
    for bad in ({}, {**headers, 'Origin': 'https://evil.example'}, {**headers, 'X-Deck-Token': 'old-instance'},
                {**headers, 'Host': 'wrong.example'}):
        assert http(url, '/api/projects/register', body, headers=bad)[0] == 403
    conn = HTTPConnection('127.0.0.1', state['port'], timeout=5)
    conn.putrequest('POST', '/api/projects/register')
    for key, value in {**headers, 'Content-Length': '2000001'}.items():
        conn.putheader(key, value)
    conn.endheaders()
    assert conn.getresponse().status == 422
    conn.close()
    assert not reg.exists()
    assert http(url, '/api/projects/register', body, headers=headers)[0] == 200
    assert http(url, '/api/projects/open', {'entry_id': 'not-registered'}, headers=headers)[0] == 422
    instance = WorkbenchServer(p)
    project_url = instance.start()
    try:
        assert http(url, '/api/projects/remove', {'entry_id': 'anything'}, headers={**headers, 'X-Deck-Token': auth(project_url)['X-Deck-Token']})[0] == 403
        assert http(project_url, '/api/ui-state', {}, headers={**headers, 'Origin': project_url.rstrip('/')})[0] == 403
        assert http(project_url, '/api/drafts', headers={'Host': 'evil.example'})[0] == 403
    finally:
        instance.stop()


def test_folder_picker_cancel_and_unsupported_do_not_register(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.sys, 'platform', 'linux')
    assert launcher.pick_directory() == {'status': 'manual_path_required', 'path': None}
    monkeypatch.setattr(launcher.sys, 'platform', 'darwin')
    monkeypatch.setattr(launcher.subprocess, 'run', lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '\n', ''))
    assert launcher.pick_directory() == {'status': 'cancelled', 'path': None}
    assert not list(tmp_path.iterdir())


def test_cli_no_open_legacy_port_and_help(tmp_path, monkeypatch, capsys):
    reg = tmp_path / 'registry.json'
    monkeypatch.setattr(launcher.webbrowser, 'open', lambda *_args, **_kw: pytest.fail('no browser requested'))
    result_code = cli.main(['workbench', '--registry', str(reg), '--no-open', '--json'])
    payload = json.loads(capsys.readouterr().out)
    assert result_code == (0 if payload['ui_available'] else 3)
    assert payload['url'].endswith('/v2/') and payload['project_id'] is None
    assert payload['mode'] == 'v2' and payload['service_version']
    assert cli.main(['workbench', '--registry', str(reg), '--stop']) == 0
    capsys.readouterr()
    p = project(tmp_path / 'project')
    try:
        assert cli.main(['workbench', '--project', str(p), '--registry', str(reg), '--ui', 'legacy', '--no-open']) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload['url'].endswith('/') and not payload['url'].endswith('/v2/')
        assert http(payload['url'], '/')[0] == 200
        assert cli.main(['workbench', '--project', str(p), '--registry', str(reg), '--port', '-1', '--no-open']) == 2
        error = json.loads(capsys.readouterr().err)
        assert error['error']['code'] == 'local_state_invalid'
    finally:
        runtime.stop(runtime.descriptor(project=p))
    with pytest.raises(SystemExit) as code:
        cli.main(['workbench', '--help'])
    assert code.value.code == 0 and '--registry' in capsys.readouterr().out
