"""Personal draft ACK/recovery boundaries, independent of business revisions."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import shutil

import pytest

from deck_master import editing, local_runtime as runtime, samples, service, ui_journal as journal
from deck_master.local_state import LocalStateConflict, LocalStateError
from deck_master.models import ModelError, content_identity
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_services import http, auth


@pytest.fixture
def project(tmp_path):
    path = tmp_path / 'project'
    samples.create_sample(path, page_count=2, readonly=False)
    return path


def draft(project, draft_id='d1', page='p01', text='本地草稿'):
    store = Store(project)
    doc = store.load_document()
    info = journal.project_info(project)
    return {'schema_version': 'ui_draft.v1', 'project_id': info['project_id'],
            'project_identity': info['project_identity'], 'draft_id': draft_id,
            'target': {'scope': 'page', 'page_id': page, 'layer': 'content'},
            'base_revision': doc['revision_id'],
            'base_ref': next(p['page'] for p in doc['pages'] if p['page_id'] == page),
            'content': {'text': text}, 'pending': None}


def business_state(project):
    store = Store(project)
    return ((store.deck_root / 'current.json').read_bytes(), content_identity(store.load_document()),
            sorted(p.name for p in store.revisions_dir.glob('*.json')))


def test_ack_idempotency_cas_pending_payload_and_business_state(project):
    before = business_state(project)
    value = draft(project)
    pending = {'project_id': value['project_id'], 'annotations': [{'page_id': 'p01', 'text': 'old submission'}]}
    value['pending'] = {'operation_id': 'awaiting-response', 'payload': pending, 'payload_digest': journal.digest(pending)}
    first = journal.save(project, draft=value)['record']
    retry = journal.save(project, draft=value)
    assert retry['replayed'] and retry['record'] == first
    changed = copy.deepcopy(value)
    changed['content']['text'] = 'edited after request was sent'
    second = journal.save(project, draft=changed, expected_etag=first['etag'])['record']
    assert second['updated_sequence'] == 2 and second['etag'] != first['etag']
    assert second['draft']['pending'] == first['draft']['pending']
    with pytest.raises(LocalStateConflict):
        journal.save(project, draft=value, expected_etag=first['etag'])
    assert journal.get(project, 'd1')['record'] == second
    assert business_state(project) == before


def test_two_windows_get_conflict_without_overwrite(project):
    value = draft(project)
    first = journal.save(project, draft=value)['record']
    variants = [copy.deepcopy(value), copy.deepcopy(value)]
    variants[0]['content']['text'], variants[1]['content']['text'] = 'window A', 'window B'
    def attempt(v):
        try:
            return journal.save(project, draft=v, expected_etag=first['etag'])['record']
        except LocalStateConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, variants))
    assert sum(v is not None for v in outcomes) == 1
    assert journal.get(project, 'd1')['record'] in outcomes


def test_same_page_and_draft_ids_cannot_cross_projects(project, tmp_path):
    other = tmp_path / 'other' / 'project'
    samples.create_sample(other, page_count=2, readonly=False)
    one, two = draft(project), draft(other)
    assert one['project_id'] == two['project_id'] and one['target'] == two['target']
    assert one['project_identity'] != two['project_identity']
    journal.save(project, draft=one)
    with pytest.raises(LocalStateError, match='another project'):
        journal.save(other, draft=one)
    with pytest.raises(LocalStateError, match='another project'):
        journal.import_recovery(other, recovery=journal.recovery_file(project, draft=one))
    assert journal.list_drafts(other)['records'] == []
    journal.save(other, draft=two)
    assert journal.get(project, 'd1')['record']['draft'] == one
    assert journal.get(other, 'd1')['record']['draft'] == two


def test_moving_same_project_preserves_logical_identity_and_recovery(project, tmp_path):
    value = draft(project)
    recovery = journal.recovery_file(project, draft=value)
    target = tmp_path / 'moved'
    project.rename(target)
    assert journal.project_info(target)['project_identity'] == value['project_identity']
    assert journal.import_recovery(target, recovery=recovery)['status'] == 'saved'


def test_restore_keeps_personal_drafts_and_old_base(project):
    value = draft(project)
    first = journal.save(project, draft=value)['record']
    store = Store(project)
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] = 'revised body'
    editing.edit_page(project, page=page, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='edit-body')
    edited = store.current_revision_id()
    editing.restore(project, revision_id=value['base_revision'], base_revision=edited, operation_id='restore-body')
    assert store.current_revision_id() != value['base_revision']
    assert journal.get(project, 'd1')['record'] == first
    assert journal.list_drafts(project)['records'] == [first]


@pytest.mark.parametrize('case', ['wrong_page', 'wrong_hash', 'foreign_ref', 'orphan_revision', 'invalid_id', 'wrong_layer', 'pending_digest', 'extra_key'])
def test_draft_basis_schema_and_path_rejections_do_not_write(project, case):
    store = Store(project)
    value = draft(project)
    before = business_state(project)
    if case == 'wrong_page':
        value['target']['page_id'] = 'p99'
    elif case == 'wrong_hash':
        value['base_ref']['sha256'] = 'a' * 64
    elif case == 'foreign_ref':
        value['base_ref'] = store.load_document()['pages'][1]['page']
    elif case == 'orphan_revision':
        doc = copy.deepcopy(store.load_document())
        doc['revision_id'] = 'orphan'
        (store.revisions_dir / 'orphan.json').write_text(json.dumps(doc))
        value['base_revision'] = 'orphan'
        before = business_state(project)
    elif case == 'invalid_id':
        value['draft_id'] = '../../outside'
    elif case == 'wrong_layer':
        value['target']['layer'] = 'original_image'
    elif case == 'pending_digest':
        value['pending'] = {'operation_id': 'pending', 'payload': {'text': 'payload'}, 'payload_digest': 'a' * 64}
    else:
        value['token'] = 'never store session'
    with pytest.raises((LocalStateError, ModelError, RuntimeError)):
        journal.save(project, draft=value)
    assert business_state(project) == before
    assert not (store.deck_root / 'workbench' / 'drafts').exists()


def test_base_or_target_change_uses_new_draft_identity(project):
    value = draft(project)
    first = journal.save(project, draft=value)['record']
    with pytest.raises(LocalStateConflict, match='different target or base'):
        journal.save(project, draft=draft(project, page='p02'), expected_etag=first['etag'])
    assert journal.get(project, 'd1')['record'] == first


def test_symlinked_journal_and_files_fail_closed(project, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    directory = Store(project).deck_root / 'workbench' / 'drafts'
    directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(LocalStateError):
        journal.save(project, draft=draft(project))
    assert not list(outside.iterdir())
    directory.unlink()
    directory.mkdir()
    (directory / 'd1.json').symlink_to(outside / 'do-not-write')
    with pytest.raises(LocalStateError):
        journal.save(project, draft=draft(project))
    assert not list(outside.iterdir())


def test_io_failure_and_lost_response_keep_atomic_records(project, monkeypatch):
    value = draft(project)
    first = journal.save(project, draft=value)['record']
    new = copy.deepcopy(value)
    new['content']['text'] = 'latest'
    before = business_state(project)
    original = journal.write_json
    def fail_before(*_args):
        raise OSError('no space')
    monkeypatch.setattr(journal, 'write_json', fail_before)
    with pytest.raises(OSError):
        journal.save(project, draft=new, expected_etag=first['etag'])
    assert journal.get(project, 'd1')['record'] == first
    def lose_ack(*args):
        original(*args)
        raise OSError('response connection lost')
    monkeypatch.setattr(journal, 'write_json', lose_ack)
    with pytest.raises(OSError):
        journal.save(project, draft=new, expected_etag=first['etag'])
    retry = journal.save(project, draft=new, expected_etag=first['etag'])
    assert retry['replayed'] and retry['record']['updated_sequence'] == 2
    assert business_state(project) == before


def test_recovery_conflict_tamper_and_metadata_are_not_silent(project):
    value = draft(project)
    old = journal.save(project, draft=value)['record']
    new = copy.deepcopy(value)
    new['content']['text'] = 'offline newer copy'
    imported = journal.import_recovery(project, recovery=journal.recovery_file(project, draft=new))
    assert imported['imported_from'] == 'd1' and imported['record']['draft']['draft_id'] != 'd1'
    assert journal.get(project, 'd1')['record'] == old
    assert len(journal.list_drafts(project)['records']) == 2
    recovery = journal.recovery_file(project, draft=new)
    recovery['draft']['content']['text'] = 'tampered'
    with pytest.raises(LocalStateError, match='hash'):
        journal.import_recovery(project, recovery=recovery)
    for content in ({'token': 'secret'}, {'path': '/Users/private'}, {'command': 'execute something'}):
        with pytest.raises(LocalStateError):
            journal.recovery_file(project, draft={**new, 'content': content})


def test_bad_journal_is_local_and_safe_text_is_plain_json(project):
    first = journal.save(project, draft=draft(project, text='<img src=x onerror=alert(1)>'))['record']
    folder = Store(project).deck_root / 'workbench' / 'drafts'
    (folder / 'broken.json').write_text('broken')
    result = journal.list_drafts(project)
    assert result['records'] == [first] and result['errors'] == [{'draft_id': 'broken', 'status': 'unreadable'}]
    server = WorkbenchServer(project)
    url = server.start()
    try:
        code, saved = http(url, '/api/drafts/d1')
        assert code == 200 and saved['record'] == first
        assert http(url, '/api/drafts/../../outside')[0] == 422
    finally:
        server.stop()


def test_actual_port_restart_restores_ack_but_not_unsent_and_can_import(project):
    value = draft(project)
    desc = runtime.descriptor(project=project)
    first = runtime.ensure(desc)
    try:
        status, saved = http(first['url'], '/api/drafts/save', {'draft': value}, headers=auth(first['url']))
        assert status == 200 and saved['status'] == 'saved'
        offline = copy.deepcopy(value)
        offline['draft_id'] = 'not-sent'
        offline['content']['text'] = 'only in old origin'
        recovery = journal.recovery_file(project, draft=offline)
    finally:
        runtime.stop(desc)
    # Keep the old port occupied to prove cross-origin recovery.
    import socket
    with socket.socket() as occupied:
        occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupied.bind(('127.0.0.1', first['port']))
        occupied.listen()
        second = runtime.ensure(desc)
        try:
            assert first['port'] != second['port']
            code, records = http(second['url'], '/api/drafts')
            assert code == 200 and [r['draft']['draft_id'] for r in records['records']] == ['d1']
            imported = http(second['url'], '/api/drafts/import', {'recovery': recovery}, headers=auth(second['url']))
            assert imported[0] == 200
            assert len(http(second['url'], '/api/drafts')[1]['records']) == 2
        finally:
            runtime.stop(desc)


def test_position_cross_project_and_historical_reads(project, tmp_path):
    info = journal.project_info(project)
    value = {'schema_version': 'ui_position.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
             'page_id': 'p02', 'surface': 'page', 'layer': 'original_image', 'revision': info['revision_id'], 'zoom': 1.5, 'task_id': None}
    before = business_state(project)
    journal.save_position(project, position=value)
    assert journal.read_position(project)['position'] == value
    other = tmp_path / 'other' / 'project'
    samples.create_sample(other, page_count=2)
    with pytest.raises(LocalStateError):
        journal.save_position(other, position=value)
    shutil.copyfile(Store(project).deck_root / 'workbench' / 'position.json', Store(other).deck_root / 'workbench' / 'position.json')
    with pytest.raises(LocalStateError):
        journal.read_position(other)
    assert business_state(project) == before


def test_synthetic_factory_images_deterministic_and_browser_readonly(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    samples.create_sample(a, page_count=2)
    samples.create_sample(b, page_count=2)
    def images(p):
        store = Store(p)
        return [store.read_object_json(e['blueprint'])['file']['sha256'] for e in store.load_document()['pages']]
    assert images(a) == images(b)
    assert journal.project_info(a)['sample']['readonly']
    server = WorkbenchServer(a)
    url = server.start()
    before = business_state(a)
    try:
        for path in ('/api/edit', '/api/cancel', '/api/inputs/update', '/api/drafts/save'):
            assert http(url, path, {}, headers=auth(url))[0] == 403
    finally:
        server.stop()
    assert business_state(a) == before


@pytest.mark.parametrize('surface', ['overview', 'content', 'gallery', 'style', 'runs', 'page'])
def test_every_work_surface_and_task_location_can_be_restored(project, surface):
    store = Store(project)
    info = journal.project_info(project)
    task_id = store.read_object_json(store.load_document()['tasks'][0])['task_id']
    value = {'schema_version': 'ui_position.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
             'page_id': 'p01', 'surface': surface, 'layer': 'original_image', 'revision': None, 'zoom': 1.25, 'task_id': task_id}
    journal.save_position(project, position=value)
    assert journal.read_position(project)['position'] == value
    with pytest.raises(LocalStateError, match='task'):
        journal.save_position(project, position={**value, 'task_id': 'foreign-task'})
    with pytest.raises(ModelError):
        journal.save_position(project, position={**value, 'zoom': 100})
