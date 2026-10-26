"""R1: every accepted clear backup remains endable after interruption.

Value: protects=durable end and downloadable complete evidence at the backup limit;
fails_when=closure reuses the ordinary 2 MB state-file limit;
why_new=previous recovery fixtures contained only small drafts; seam=none;
no_claim=real storage faults are injected at existing filesystem boundaries.
"""
import json
from pathlib import Path
import pytest
from deck_master import ui_journal as j
from deck_master import ui_clear_recovery as recovery
from deck_master.local_state import MAX_BODY, LocalStateError, LocalStateConflict, read_json
from deck_master.models import canonical_json_bytes
from test_ui_state_clear import project, store, save_draft, plan  # noqa: F401


def large_request(project, store, *, size=MAX_BODY, count=2, chinese=False):
    for n in range(count):
        save_draft(store, project, f'draft-{n:03}', '')
    p = plan(project, reading_preferences=False)
    req = dict(operation_id='capacity-op', input=dict(project_id=p['project_id'], scope='current_project',
        draft_ids='all', reading_preferences=False), plan_id=p['plan_id'], manifest_digest=p['manifest_digest'])
    # Timestamp width is stable; fill the remaining canonical UTF-8 byte budget.
    backup = dict(schema_version='ui_clear_backup.v1', operation_id=req['operation_id'],
        manifest_digest=p['manifest_digest'], records=j._clear_backup_records(store, p['items']),
        cleared_at=j._utc_now_iso())
    budget = size - len(canonical_json_bytes(backup))
    for n in range(count):
        amount = budget // count + (n < budget % count)
        text = ('中' * (amount // 3) + 'x' * (amount % 3)) if chinese else 'x' * amount
        record = j._read(store, f'draft-{n:03}')
        save_draft(store, project, f'draft-{n:03}', text, expected_etag=record['etag'])
    p = plan(project, reading_preferences=False)
    return {**req, 'plan_id': p['plan_id'], 'manifest_digest': p['manifest_digest']}


def interrupt(project, store, req, monkeypatch):
    unlink = Path.unlink
    def fail(path, *args, **kwargs):
        if path == j._draft_path(store, 'draft-001'):
            raise OSError('interrupted after first draft')
        return unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', fail)
        with pytest.raises(OSError, match='interrupted'):
            j.commit_clear(project, **req)


@pytest.mark.parametrize('size,count,chinese', [(MAX_BODY-400,2,False), (MAX_BODY,2,True), (MAX_BODY,20,True)])
def test_accepted_capacity_backup_can_end_and_download(project, store, monkeypatch, size, count, chinese):
    req = large_request(project, store, size=size, count=count, chinese=chinese)
    before = store.load_document()
    interrupt(project, store, req, monkeypatch)
    backup_path = j._clear_backup_path(store, req['manifest_digest'])
    assert backup_path.stat().st_size == size
    original_backup = read_json(backup_path)
    state = j.inspect_clear(project, **req)
    assert state['status'] == 'incomplete'
    with pytest.raises(LocalStateConflict): j.commit_clear(project, **req)
    result = j.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    assert result['status'] == 'ended'
    assert j.end_clear(project, **req, inspection_digest=state['inspection_digest']) == result
    assert j.inspect_clear(project, **req)['status'] == 'ended'
    raw, _ = j.clear_recovery_download(project, operation_id=req['operation_id'])
    assert len(raw) > MAX_BODY
    assert json.loads(raw)['backup'] == original_backup
    assert json.loads(raw)['inspection'] == state
    assert store.load_document() == before
    assert len(plan(project)['items']) == count - 1
    with pytest.raises(LocalStateConflict): j.commit_clear(project, **req)
    assert recovery.listing(project)['recoveries'][0]['available']


def test_oversize_backup_refused_before_deleting(project, store):
    req = large_request(project, store, size=MAX_BODY+1)
    before = j.list_drafts(project)
    with pytest.raises(LocalStateError, match='exceeds'): j.commit_clear(project, **req)
    assert j.list_drafts(project) == before
    assert not j._clear_log_path(store).exists()


def small_request(project, store):
    save_draft(store, project)
    p = plan(project)
    return dict(operation_id='small-op', input=dict(project_id=p['project_id'], scope='current_project',
        draft_ids='all', reading_preferences=True), plan_id=p['plan_id'], manifest_digest=p['manifest_digest'])


@pytest.mark.parametrize('phase', ['evidence', 'marker'])
def test_two_phase_write_failure_retains_request_and_allows_retry(project, store, monkeypatch, phase):
    from deck_master import store as storage
    req = small_request(project, store)
    state = j.inspect_clear(project, **req)
    before = store.load_document()
    with monkeypatch.context() as patch:
        if phase == 'evidence':
            patch.setattr(storage, '_atomic_write_bytes', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
        else:
            patch.setattr(recovery, 'write_json', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
        with pytest.raises(OSError, match='disk full'):
            j.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    assert not recovery.closure_path(store, req['operation_id']).exists()
    assert j.inspect_clear(project, **req) == state
    assert len(plan(project)['items']) == 1
    if phase == 'marker':
        assert list((store.deck_root/'workbench/clear-evidence').glob('*.json'))
    assert j.end_clear(project, **req, inspection_digest=state['inspection_digest'])['status'] == 'ended'
    assert store.load_document() == before


@pytest.mark.parametrize('damage', ['missing', 'truncated', 'modified', 'symlink', 'directory', 'wrong-binding', 'marker'])
def test_bad_evidence_never_releases_fence_or_reports_success(project, store, damage):
    req = small_request(project, store)
    state = j.inspect_clear(project, **req)
    j.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    marker_path = recovery.closure_path(store, req['operation_id'])
    marker = read_json(marker_path)
    assert marker['schema_version'] == 'ui_clear_closure.v2'
    path = recovery.evidence_path(store, marker['evidence']['sha256'])
    raw = path.read_bytes()
    if damage == 'missing': path.unlink()
    elif damage == 'truncated': path.write_bytes(raw[:-1])
    elif damage == 'modified': path.write_bytes(b' ' + raw[1:])
    elif damage == 'symlink':
        other = path.with_suffix('.saved'); path.rename(other); path.symlink_to(other)
    elif damage == 'directory': path.unlink(); path.mkdir()
    elif damage == 'wrong-binding':
        marker['inspection_digest'] = '0'*64
        marker['record_digest'] = j.digest({k:v for k,v in marker.items() if k!='record_digest'})
        marker_path.write_bytes(canonical_json_bytes(marker))
    else: marker_path.write_text('{')
    for call in (lambda: j.inspect_clear(project, **req),
                 lambda: j.end_clear(project, **req, inspection_digest=state['inspection_digest']),
                 lambda: j.commit_clear(project, **req),
                 lambda: j.clear_recovery_download(project, operation_id=req['operation_id'])):
        with pytest.raises(LocalStateError): call()
    assert len(plan(project)['items']) == 1
    assert not recovery.listing(project)['recoveries'][0]['available']


def test_legacy_inline_record_still_reads_replays_and_downloads(project, store):
    req = small_request(project, store)
    state = j.inspect_clear(project, **req)
    result = j.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    raw, filename = j.clear_recovery_download(project, operation_id=req['operation_id'])
    assert json.loads(raw)['schema_version'] == 'ui_clear_closure.v1'
    recovery.closure_path(store, req['operation_id']).write_bytes(raw)
    assert j.end_clear(project, **req, inspection_digest=state['inspection_digest']) == result
    assert j.clear_recovery_download(project, operation_id=req['operation_id']) == (raw, filename)
    assert recovery.listing(project)['recoveries'][0]['available']
    with pytest.raises(LocalStateConflict): j.commit_clear(project, **req)


def test_large_live_inspection_survives_complete_evidence_roundtrip(project, store, monkeypatch):
    # Isolated manifest fixture: the storage contract must retain the complete
    # inspection even when many subsequent entries outweigh the original backup.
    req = small_request(project, store)
    original = j._clear_manifest
    def growing(*args, **kwargs):
        doc, identity, items, blockers, kept_out, digest = original(*args, **kwargs)
        kept_out = [f'new-unreadable-{i}: ' + '中'*80 for i in range(10000)]
        return doc, identity, items, blockers, kept_out, digest
    monkeypatch.setattr(j, '_clear_manifest', growing)
    state = j.inspect_clear(project, **req)
    assert len(canonical_json_bytes(state)) > MAX_BODY
    j.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    raw, _ = j.clear_recovery_download(project, operation_id=req['operation_id'])
    assert json.loads(raw)['inspection'] == state
    assert j.inspect_clear(project, **req)['status'] == 'ended'


def test_single_large_draft_receipt_interruption_remains_downloadable(project, store, monkeypatch):
    import builtins
    save_draft(store, project, 'single-large', '中' * 664000)
    p = plan(project, reading_preferences=False)
    req = dict(operation_id='single-op', input=dict(project_id=p['project_id'], scope='current_project',
        draft_ids='all', reading_preferences=False), plan_id=p['plan_id'], manifest_digest=p['manifest_digest'])
    original_open = builtins.open
    def fail(path, mode='r', *args, **kwargs):
        if Path(path) == j._clear_log_path(store) and mode == 'a': raise OSError('receipt interruption')
        return original_open(path, mode, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, 'open', fail)
        with pytest.raises(OSError): j.commit_clear(project, **req)
    assert not j.list_drafts(project)['records']
    state = j.inspect_clear(project, **req)
    assert state['status'] == 'incomplete'
    j.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    raw, _ = j.clear_recovery_download(project, operation_id=req['operation_id'])
    assert json.loads(raw)['backup']['records'][0]['record']['draft']['content']['text'] == '中' * 664000
