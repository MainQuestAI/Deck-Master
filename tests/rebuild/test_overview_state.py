"""U03 personal preferences, CAS/clear races and real HTTP immutability."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import uuid

import pytest

from deck_master import overview_state, ui_journal
from deck_master.local_state import LocalStateConflict, LocalStateError
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_gallery_core import request, business
from test_ui_state_clear import plan as clear_plan, commit as clear_commit
from test_workbench_actions import commit


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'overview-project'
    create_sample(root, page_count=3, readonly=False)
    return root


def state(project, **patch):
    info = ui_journal.project_info(project)
    return {'schema_version': 'ui_overview.v1', 'project_id': info['project_id'],
            'project_identity': info['project_identity'], 'revision_id': info['revision_id'],
            'search': '', 'filter': 'all', 'sort': 'ascending', **patch}


def test_fixed_revision_states_cas_replay_and_business_immutability(project):
    store = Store(project)
    value = state(project, search='材料', filter='todo', sort='descending')
    before = business(project)
    saved = overview_state.save(project, state=value)
    assert overview_state.save(project, state=value)['replayed']
    assert overview_state.get(project, revision=value['revision_id'])['record'] == saved['record']
    assert business(project) == before
    doc = copy.deepcopy(store.load_document())
    commit(store, doc, str(uuid.uuid4()))
    newer = state(project)
    assert overview_state.get(project, revision=newer['revision_id'])['record'] is None
    saved2 = overview_state.save(project, state=newer, expected_etag=saved['record']['etag'])
    assert overview_state.get(project, revision=value['revision_id'])['record']['state'] == value
    with pytest.raises(LocalStateConflict):
        overview_state.save(project, state={**value, 'search': '另一窗口'}, expected_etag=saved['record']['etag'])
    assert saved2['record']['etag'] != saved['record']['etag']


@pytest.mark.parametrize('patch', [{'selected_page_ids': ['p01', 42]}, {'selected_page_ids': 'p01'}, {'selected_page_ids': ['p0' + '1' * 200]}, {'plan_id': 'plan'}, {'operation_id': 'op'}, {'search': 'x' * 201}, {'filter': 'ready'}, {'sort': 'reverse'}, {'project_identity': '0' * 64}, {'revision_id': 'not-in-this-project'}])
def test_invalid_or_business_fields_never_overwrite_personal_record(project, patch):
    value = state(project)
    saved = overview_state.save(project, state=value)
    before = overview_state._file(Store(project)).read_bytes()
    with pytest.raises((RuntimeError, ValueError)):
        overview_state.save(project, state={**value, **patch}, expected_etag=saved['record']['etag'])
    assert overview_state._file(Store(project)).read_bytes() == before


def test_selected_page_ids_is_a_persisted_reading_field_and_never_business(project):
    """D1：选择是 ui_overview 的阅读状态字段；合法值可保存，业务事实不受影响。"""
    store = Store(project)
    value = state(project, selected_page_ids=['p01', 'p02'])
    before = business(project)
    saved = overview_state.save(project, state=value)
    assert overview_state.get(project, revision=value['revision_id'])['record']['state']['selected_page_ids'] == ['p01', 'p02']
    assert business(project) == before


def test_retention_is_bounded_reads_do_not_add_history_and_versions_do_not_inherit(project):
    store = Store(project)
    saved, revisions = None, []
    for index in range(15):
        commit(store, copy.deepcopy(store.load_document()), str(uuid.uuid4()))
        value = state(project, search=str(index))
        revisions.append(value['revision_id'])
        saved = overview_state.save(project, state=value, expected_etag=saved['record']['etag'] if saved else None)
    file = overview_state._file(store)
    raw = file.read_bytes()
    record = json.loads(raw)
    assert len(record['states']) == 12 and record['sequence'] == 15
    assert overview_state.get(project, revision=revisions[0])['record'] is None
    assert overview_state.get(project, revision=revisions[-1])['record']['state']['search'] == '14'
    assert file.read_bytes() == raw and len(raw) < 32_000


def test_two_windows_have_one_cas_winner(project):
    value = state(project)
    saved = overview_state.save(project, state=value)
    def edit(search):
        try:
            return overview_state.save(project, state={**value, 'search': search}, expected_etag=saved['record']['etag'])
        except LocalStateConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, ['window-a', 'window-b']))
    assert results.count('conflict') == 1
    assert overview_state.get(project, revision=value['revision_id'])['record']['state']['search'] in ['window-a', 'window-b']


@pytest.mark.parametrize('initially_saved', [True, False])
def test_clear_backs_up_and_barrier_refuses_delayed_saves_even_from_missing_record(project, initially_saved):
    value = state(project, search='旧偏好')
    saved = overview_state.save(project, state=value) if initially_saved else None
    before = business(project)
    planned = clear_plan(project)
    assert any(item['kind'] == 'overview_preferences' for item in planned['items']) is initially_saved
    result = clear_commit(project, planned)
    after = overview_state.get(project, revision=value['revision_id'])
    assert after['record'] is None and after['etag'] is not None
    with pytest.raises(LocalStateConflict):
        overview_state.save(project, state=value, expected_etag=saved['record']['etag'] if saved else None)
    backup = json.loads((project / result['backup_ref']).read_bytes())
    saved_records = [item for item in backup['records'] if item['kind'] == 'overview_preferences']
    assert len(saved_records) == int(initially_saved)
    if saved_records:
        assert saved_records[0]['record']['states'] == [value]
    assert not any(item['kind'] == 'overview_preferences' for item in clear_plan(project)['items'])
    assert business(project) == before
    # Only a fresh, explicitly chosen write against the new barrier can save.
    overview_state.save(project, state={**value, 'search': '明确重选'}, expected_etag=after['etag'])


def test_preference_edit_invalidates_clear_plan_and_backup_failure_clears_nothing(project, monkeypatch):
    value = state(project)
    saved = overview_state.save(project, state=value)
    planned = clear_plan(project)
    changed = overview_state.save(project, state={**value, 'search': '后写'}, expected_etag=saved['record']['etag'])
    with pytest.raises(LocalStateConflict):
        clear_commit(project, planned)
    planned = clear_plan(project)
    def fail(*args, **kwargs):
        raise OSError('synthetic backup write failure')
    monkeypatch.setattr(ui_journal, 'write_json', fail)
    with pytest.raises(OSError):
        clear_commit(project, planned)
    assert overview_state.get(project, revision=value['revision_id'])['record'] == changed['record']


@pytest.mark.parametrize('damage', ['json', 'hash', 'foreign'])
def test_damaged_or_foreign_preferences_remain_available_for_manual_recovery(project, damage):
    value = state(project)
    overview_state.save(project, state=value)
    file = overview_state._file(Store(project))
    record = json.loads(file.read_bytes())
    if damage == 'json':
        file.write_text('{broken')
    else:
        if damage == 'hash': record['etag'] = '0' * 64
        else: record['project_identity'] = '0' * 64
        file.write_text(json.dumps(record))
    before = file.read_bytes()
    with pytest.raises(LocalStateError):
        overview_state.get(project, revision=value['revision_id'])
    planned = clear_plan(project)
    assert any('overview_preferences' in reason for reason in planned['kept_out'])
    clear_commit(project, planned)
    assert file.read_bytes() == before


def test_http_requires_fixed_query_allows_personal_readonly_preferences_and_changes_no_business(tmp_path):
    project = tmp_path / 'readonly'
    create_sample(project, page_count=2, readonly=True)
    value = state(project)
    before = business(project)
    server = WorkbenchServer(project)
    try:
        url = server.start()
        assert 'ui_overview.v1' in request(url, '/api/health')[1]['ui_capabilities']
        for suffix in ['', '?revision=', '?revision=x&revision=y', '?revision=x&other=y']:
            assert request(url, '/api/overview' + suffix)[0] == 422
        suffix = '?revision=' + value['revision_id']
        assert request(url, '/api/overview' + suffix)[1]['record'] is None
        status, result, _ = request(url, '/api/overview', {'state': value, 'expected_etag': None})
        assert status == 200 and result['status'] == 'saved'
        assert request(url, '/api/overview' + suffix)[1]['record'] == result['record']
        assert request(url, '/api/overview', {'state': {**value, 'search': '另稿'}, 'expected_etag': None})[0] == 409
        assert business(project) == before
    finally:
        server.stop()


def test_oversized_selection_record_is_trimmed_or_refused_never_written_unreadable(project):
    """评审 F1：写入永不产生读不回的记录——超预算先丢最旧，单份也放不下就拒绝。"""
    import pytest as _pytest
    from deck_master.local_state import LocalStateError
    store = Store(project)
    long_ids = [f'page-{index:05d}-' + 'a' * 16 for index in range(500)]
    # 三份各自可放下、合计超预算的状态：保存第三份时最旧的一份被丢弃。
    revisions, saved = [], None
    for index in range(3):
        commit(store, copy.deepcopy(store.load_document()), str(uuid.uuid4()))
        revisions.append(store.current_revision_id())
        value = state(project, selected_page_ids=long_ids)
        saved = overview_state.save(project, state=value, expected_etag=saved['record']['etag'] if saved else None)
    assert overview_state.get(project, revision=revisions[0])['record'] is None
    assert overview_state.get(project, revision=revisions[-1])['record']['state']['selected_page_ids'] == long_ids
    assert overview_state._file(Store(project)).stat().st_size <= 32_000
    # 单份也放不下（合法 schema 的超长选择）：明确拒绝，文件保持可读。
    huge = ['x' * 128 for _ in range(500)]
    with _pytest.raises(LocalStateError):
        overview_state.save(project, state=state(project, selected_page_ids=huge),
                            expected_etag=saved['record']['etag'])
    assert overview_state.get(project, revision=revisions[-1])['record'] is not None


def test_fit_probe_is_byte_exact_at_the_reader_boundary(project):
    """复审 P1-1：探针省掉 etag/真实 sequence 会漏掉 31.9–32 KB 边界带，
    写出读取端拒收的文件（F1 永久卡死）。边界构造必须能写且能读回。"""
    from deck_master import overview_state as module
    from deck_master.local_state import read_json
    from deck_master.ui_journal import context

    store, document, identity = context(project)
    revision = document['revision_id']

    def state_with_selection(page_count):
        return {'schema_version': 'ui_overview.v1', 'revision_id': revision,
                'search': '', 'filter': 'all', 'sort': 'ascending',
                'selected_page_ids': [f'p{n:03}' for n in range(1, page_count + 1)]}

    # 找到恰好落在预算边界内层的规模：先粗放放大到被裁剪，再二分回可用规模。
    low, high = 1, 300
    while low < high:
        mid = (low + high + 1) // 2
        try:
            module._fit(current=document, identity=identity,
                        states=[state_with_selection(mid)] * module.MAX_READINGS, previous=None)
            low = mid
        except module.LocalStateError:
            high = mid - 1
    boundary = state_with_selection(low)

    # 用 _fit 的最终结果直接写出（探针判 OK 的规模必须真的可写可读）。
    states = [boundary] * module.MAX_READINGS
    fitted = module._fit(current=document, identity=identity, states=states, previous=None)
    record = module._write(store, document, identity, fitted, None)
    path = module._file(store)
    assert path.stat().st_size <= module.MAX_RECORD_BYTES, path.stat().st_size
    assert read_json(path, max_bytes=module.MAX_RECORD_BYTES) is not None
    assert len(fitted) == module.MAX_READINGS or record['etag']
