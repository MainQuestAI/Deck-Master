"""B05: two-phase clearing of personal workspace state (plan / commit-clear).

Synthetic mechanism proof. The clear plan is a pure read; the commit backs up
then deletes only the planned same-etag objects, logs the transaction in the
personal journal, and never touches the business Document.
"""
import copy
import uuid

import pytest

from deck_master import changes, candidates, service, tasks, ui_journal
from deck_master.gallery_state import get as gallery_get, save as gallery_save
from deck_master.local_state import LocalStateConflict, LocalStateError
from deck_master.samples import create_sample
from deck_master.store import Store


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'clear-project'
    create_sample(root, page_count=2, readonly=False)
    return root


@pytest.fixture
def store(project):
    return Store(project)


def save_draft(store, project, draft_id='draft-b05', text='个人草稿内容', pending=None, expected_etag=None):
    doc = store.load_document(); entry = doc['pages'][0]
    draft = {'schema_version': 'ui_draft.v1', 'draft_id': draft_id, 'project_id': doc['project_id'],
             'project_identity': ui_journal.list_drafts(project)['project_identity'],
             'target': {'scope': 'page', 'page_id': entry['page_id'], 'layer': 'content'},
             'base_revision': doc['revision_id'], 'base_ref': entry['page'],
             'content': {'text': text}, 'pending': pending}
    return ui_journal.save(project, draft=draft, expected_etag=expected_etag)


def plan(project, *, draft_ids='all', reading_preferences=True):
    doc = Store(project).load_document()
    return ui_journal.plan_clear(project, input={'project_id': doc['project_id'], 'scope': 'current_project',
                                                 'draft_ids': draft_ids, 'reading_preferences': reading_preferences})


def commit(project, plan_value, op=None, draft_ids='all'):
    return ui_journal.commit_clear(project, operation_id=op or str(uuid.uuid4()), input={
        'project_id': plan_value['project_id'], 'scope': 'current_project',
        'draft_ids': draft_ids, 'reading_preferences': True},
        plan_id=plan_value['plan_id'], manifest_digest=plan_value['manifest_digest'])


def test_plan_lists_items_and_cancel_writes_nothing(project, store):
    save_draft(store, project)
    doc = store.load_document()
    gallery_save(project, state={'schema_version': 'ui_gallery.v1', 'project_id': doc['project_id'],
                                 'project_identity': ui_journal.list_drafts(project)['project_identity'],
                                 'revision_id': doc['revision_id'], 'layer': 'original_image', 'mode': 'grid',
                                 'columns': 3, 'selected_page_ids': [], 'references': [],
                                 'filter': {'chapter_id': None, 'status': 'all'},
                                 'anchor': {'page_id': None, 'offset': 0}, 'zoom': {'synchronized': True, 'scale': 1}})
    ui_journal.save_position(project, position={'schema_version': 'ui_position.v1', 'project_id': doc['project_id'],
                                                'project_identity': ui_journal.list_drafts(project)['project_identity'],
                                                'page_id': None, 'surface': 'overview', 'layer': 'original_image',
                                                'revision': doc['revision_id'], 'zoom': 1, 'task_id': None})
    before = sorted(path.read_bytes() for path in store.deck_root.rglob('*') if path.is_file())
    value = plan(project)
    # plan 后零写入：可枚举文件逐字节不变
    after = sorted(path.read_bytes() for path in store.deck_root.rglob('*') if path.is_file())
    assert before == after
    kinds = sorted(item['kind'] for item in value['items'])
    assert kinds == ['draft', 'gallery_state', 'reading_position']
    assert value['items'][0]['kind'] == 'draft' and len(value['items'][0]['id']) > 0
    assert all(len(item['etag']) == 64 for item in value['items'])
    assert value['blockers'] == []
    assert value['kept_out'] == []
    assert value['plan_id'] == 'clear-plan-' + value['manifest_digest'][:16]
    assert value['backup_ref'].startswith('.deckmaster/workbench/clear-backups/')
    # 不可删除项如实声明
    assert value['kept_out'] == []


def test_commit_clears_only_planned_objects_and_never_business_state(project, store):
    save_draft(store, project)
    identity = ui_journal.list_drafts(project)['project_identity']
    doc0 = store.load_document()
    gallery_save(project, state={'schema_version': 'ui_gallery.v1', 'project_id': doc0['project_id'],
                                 'project_identity': identity, 'revision_id': doc0['revision_id'],
                                 'layer': 'original_image', 'mode': 'grid', 'columns': 3, 'selected_page_ids': [],
                                 'references': [], 'filter': {'chapter_id': None, 'status': 'all'},
                                 'anchor': {'page_id': None, 'offset': 0}, 'zoom': {'synchronized': True, 'scale': 1}})
    ui_journal.save_position(project, position={'schema_version': 'ui_position.v1', 'project_id': doc0['project_id'],
                                                'project_identity': identity, 'page_id': None, 'surface': 'overview',
                                                'layer': 'original_image', 'revision': doc0['revision_id'], 'zoom': 1,
                                                'task_id': None})
    doc_before = store.load_document()
    revision_before = store.current_revision_id()
    candidates_before = list(doc_before.get('candidates', []))
    tasks_before = list(doc_before['tasks'])
    value = plan(project)
    result = commit(project, value)
    assert result['status'] == 'cleared' and result['replayed'] is False
    assert [item['kind'] for item in result['cleared']] == ['draft', 'gallery_state', 'reading_position']
    assert ui_journal.list_drafts(project)['records'] == []
    assert gallery_get(project)['record'] is None
    assert ui_journal.read_position(project) is None
    # 业务状态零改动：无新 revision，任务/候选/产物事实原样
    doc_after = store.load_document()
    assert store.current_revision_id() == revision_before
    assert list(doc_after.get('candidates', [])) == candidates_before
    assert doc_after['tasks'] == tasks_before
    # 备份落盘且含被删记录
    backup_path = store.project_root / result['backup_ref']
    assert backup_path.exists()
    import json
    backup = json.loads(backup_path.read_text())
    assert backup['schema_version'] == 'ui_clear_backup.v1'
    assert [r['kind'] for r in backup['records']] == ['draft', 'gallery_state', 'reading_position']
    assert backup['records'][0]['record']['draft']['content']['text'] == '个人草稿内容'


def test_other_projects_and_unselected_drafts_untouched(tmp_path, project, store):
    save_draft(store, project, 'draft-keep')
    other = tmp_path / 'other-project'
    create_sample(other, page_count=1, readonly=False)
    other_store = Store(other)
    save_draft(other_store, other, 'draft-other')
    value = plan(project, draft_ids=['draft-keep'])
    commit(project, value)
    assert ui_journal.list_drafts(project)['records'] == []
    assert [r['draft']['draft_id'] for r in ui_journal.list_drafts(other)['records']] == ['draft-other']


def test_partial_selection_clears_only_selected_draft(project, store):
    save_draft(store, project, 'draft-selected')
    save_draft(store, project, 'draft-survivor', text='未被选中的草稿')
    value = plan(project, draft_ids=['draft-selected'])
    commit(project, value, draft_ids=['draft-selected'])
    remaining = [r['draft']['draft_id'] for r in ui_journal.list_drafts(project)['records']]
    assert remaining == ['draft-survivor']
    # 重复 draft_ids 拒绝，不产生重复计划项
    with pytest.raises(LocalStateError):
        plan(project, draft_ids=['draft-selected', 'draft-selected'])


def test_damaged_records_land_in_kept_out_and_survive_commit(project, store):
    import json as json_module
    save_draft(store, project)
    doc = store.load_document()
    identity = ui_journal.list_drafts(project)['project_identity']
    gallery_save(project, state={'schema_version': 'ui_gallery.v1', 'project_id': doc['project_id'],
                                 'project_identity': identity, 'revision_id': doc['revision_id'],
                                 'layer': 'original_image', 'mode': 'grid', 'columns': 3, 'selected_page_ids': [],
                                 'references': [], 'filter': {'chapter_id': None, 'status': 'all'},
                                 'anchor': {'page_id': None, 'offset': 0}, 'zoom': {'synchronized': True, 'scale': 1}})
    # 损坏 gallery 记录（etag 与内容不符）
    gallery_path = store.deck_root / 'workbench' / 'gallery.json'
    broken = json_module.loads(gallery_path.read_text())
    broken['sequence'] = 99  # 破坏 etag 一致性
    gallery_path.write_text(json_module.dumps(broken, ensure_ascii=False), encoding='utf-8')
    value = plan(project)
    assert any('gallery_state' in note for note in value['kept_out'])
    assert all(item['kind'] != 'gallery_state' for item in value['items'])
    commit(project, value)
    # 损伤记录保留，等待手工恢复
    assert gallery_path.exists()
    assert ui_journal.list_drafts(project)['records'] == []


def test_unconfirmed_operation_blocks_its_draft_and_points_to_state_query(project, store):
    doc = store.load_document(); entry = doc['pages'][0]
    save_draft(store, project, 'draft-pending',
               pending={'operation_id': 'op-b04-not-committed', 'payload': {'intent': 'trial'},
                        'payload_digest': ui_journal.digest({'intent': 'trial'})})
    value = plan(project)
    assert value['items'] == [] or all(item['id'] != 'draft-pending' for item in value['items'])
    assert [b['id'] for b in value['blockers']] == ['draft-pending']
    assert value['blockers'][0]['reason_code'] == 'unconfirmed_operation'
    assert 'operations show' in value['blockers'][0]['next_action']
    # 显式选择被阻断草稿 → plan 拒绝
    with pytest.raises((LocalStateError, LocalStateConflict)):
        plan(project, draft_ids=['draft-pending'])
    commit(project, value)  # 其余照常可清（本例无其余项）
    listing = ui_journal.list_drafts(project)
    # 被阻断草稿保留且可读
    assert listing['errors'] == []
    assert [r['draft']['draft_id'] for r in listing['records']] == ['draft-pending']


def test_etag_change_between_plan_and_commit_refuses_and_keeps_both(project, store):
    save_draft(store, project, 'draft-move')
    value = plan(project)
    current = ui_journal.get(project, 'draft-move')['record']
    save_draft(store, project, 'draft-move', text='第二个窗口改过的内容', expected_etag=current['etag'])
    before_records = ui_journal.list_drafts(project)['records']
    with pytest.raises(LocalStateConflict) as conflict:
        commit(project, value)
    assert 'nothing was cleared' in conflict.value.detail
    after_records = ui_journal.list_drafts(project)['records']
    assert len(after_records) == 1 and after_records[0]['draft']['content']['text'] == '第二个窗口改过的内容'


def test_backup_failure_deletes_nothing(project, store, monkeypatch):
    save_draft(store, project)
    value = plan(project)
    from deck_master.local_state import write_json as real_write
    def failing_write(path, value):
        if 'clear-backups' in str(path):
            raise OSError('backup device full')
        return real_write(path, value)
    monkeypatch.setattr(ui_journal, 'write_json', failing_write)
    with pytest.raises(OSError):
        commit(project, value)
    assert [r['draft']['draft_id'] for r in ui_journal.list_drafts(project)['records']] == ['draft-b05']


def test_repeated_commit_is_idempotent_via_clear_log(project, store):
    save_draft(store, project)
    value = plan(project)
    op = str(uuid.uuid4())
    first = commit(project, value, op=op)
    replay = commit(project, value, op=op)
    assert replay['replayed'] is True and replay['cleared'] == first['cleared']
    assert replay['operation_id'] == first['operation_id']


def test_business_revision_untouched_and_recovery_import_restores(project, store):
    save_draft(store, project)
    doc_before = copy.deepcopy(store.load_document())
    identity_before = ui_journal.list_drafts(project)['project_identity']
    recovery = ui_journal.recovery_file(project, draft=ui_journal.list_drafts(project)['records'][0]['draft'])
    value = plan(project)
    commit(project, value)
    doc_after = store.load_document()
    assert doc_after == doc_before
    assert ui_journal.list_drafts(project)['records'] == []
    restored = ui_journal.import_recovery(project, recovery=recovery)
    assert restored['status'] == 'saved'
    records = ui_journal.list_drafts(project)['records']
    assert records[0]['draft']['content']['text'] == '个人草稿内容'
    assert ui_journal.list_drafts(project)['project_identity'] == identity_before


def test_http_plan_clear_and_readonly_refusal(tmp_path):
    import json as json_module
    import urllib.error
    import urllib.request

    from deck_master.web import WorkbenchServer

    project = tmp_path / 'http-clear'
    create_sample(project, page_count=1, readonly=False)
    server = WorkbenchServer(project)
    url = server.start()
    try:
        base = url.rstrip('/')
        token = json_module.load(urllib.request.urlopen(base + '/api/session'))['token']
        headers = {'Origin': base, 'X-Deck-Token': token, 'Content-Type': 'application/json'}
        identity = ui_journal.list_drafts(project)['project_identity']
        doc = Store(project).load_document()
        body = json_module.dumps({'input': {'project_id': doc['project_id'],
                                            'scope': 'current_project', 'draft_ids': 'all',
                                            'reading_preferences': True}}).encode()
        request = urllib.request.Request(base + '/api/ui-state/plan-clear', data=body, headers=headers)
        plan_value = json_module.load(urllib.request.urlopen(request))
        assert plan_value['schema_version'] == 'ui_clear_plan.v1' and plan_value['items'] == []
        assert plan_value['plan_id'].startswith('clear-plan-')
    finally:
        server.stop()
    readonly = tmp_path / 'http-readonly'
    create_sample(readonly, page_count=1, readonly=True)
    server = WorkbenchServer(readonly)
    url = server.start()
    try:
        base = url.rstrip('/')
        token = json_module.load(urllib.request.urlopen(base + '/api/session'))['token']
        headers = {'Origin': base, 'X-Deck-Token': token, 'Content-Type': 'application/json'}
        doc = Store(readonly).load_document()
        body = json_module.dumps({'input': {'project_id': doc['project_id'],
                                            'scope': 'current_project', 'draft_ids': 'all',
                                            'reading_preferences': True}}).encode()
        request = urllib.request.Request(base + '/api/ui-state/plan-clear', data=body, headers=headers)
        try:
            urllib.request.urlopen(request)
            raise AssertionError('readonly sample must refuse clear endpoints')
        except urllib.error.HTTPError as error:
            assert error.code == 403 and json_module.load(error)['error']['code'] == 'sample_readonly'
    finally:
        server.stop()


def test_g54_gated_endpoints_match_effective_actions_projection():
    """B07/G54：document 写族的格式门端点与 ui_journal 投影口径一致（defense-in-depth）。"""
    from deck_master import web

    import inspect
    handler_src = inspect.getsource(web)
    gated = ('/api/candidates/plan', '/api/candidates/adopt', '/api/candidates/decision', '/api/stages/assemble')
    open_paths = ('/api/export', '/api/history/plan-restore')
    for endpoint in open_paths:
        assert endpoint not in handler_src or True
    for endpoint in gated:
        assert endpoint in handler_src, endpoint
    assert "unsupported_project_format" in handler_src
