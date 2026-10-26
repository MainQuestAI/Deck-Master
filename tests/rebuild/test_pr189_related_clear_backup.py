"""A valid other-operation backup is related evidence, never A's execution proof."""
import json
from pathlib import Path
import pytest
from deck_master import ui_journal as journal
from deck_master.local_state import LocalStateConflict, LocalStateError
from deck_master import personal_recovery
from test_ui_state_clear import project, store, save_draft, plan  # noqa: F401


def request(project, store):
    save_draft(store, project)
    p = plan(project)
    return dict(operation_id='operation-a', input=dict(project_id=p['project_id'], scope='current_project',
        draft_ids='all', reading_preferences=True), plan_id=p['plan_id'], manifest_digest=p['manifest_digest'])


@pytest.mark.parametrize('interrupted', [False, True])
def test_related_backup_allows_end_without_borrowing_receipt(project, store, monkeypatch, interrupted):
    a = request(project, store); b = {**a, 'operation_id': 'operation-b'}
    if interrupted:
        original = Path.unlink
        def fail(path, *args, **kwargs):
            if path.parent == journal._directory(store) and path.suffix == '.json': raise OSError('before delete')
            return original(path, *args, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(Path, 'unlink', fail)
            with pytest.raises(OSError): journal.commit_clear(project, **b)
    else:
        receipt = journal.commit_clear(project, **b)
    save_draft(store, project, 'later')
    before = store.load_document()
    backup_path = journal._clear_backup_path(store, a['manifest_digest']); backup = backup_path.read_bytes()
    log_path = journal._clear_log_path(store); log = log_path.read_bytes() if log_path.exists() else None
    observed = journal.inspect_clear(project, **a)
    assert observed['status'] == 'no_execution_evidence'
    assert observed['receipt'] is None and not observed['backup']['available']
    assert observed['backup']['related_operation']['operation_id'] == b['operation_id']
    ended = journal.end_clear(project, **a, inspection_digest=observed['inspection_digest'])
    assert ended['status'] == 'ended'
    assert journal.end_clear(project, **a, inspection_digest=observed['inspection_digest']) == ended
    with pytest.raises(LocalStateConflict): journal.commit_clear(project, **a)
    raw, _ = journal.clear_recovery_download(project, operation_id=a['operation_id'])
    bundle = json.loads(raw)
    assert bundle['backup'] is None and bundle['inspection'] == observed
    assert backup_path.read_bytes() == backup
    assert (log_path.read_bytes() if log_path.exists() else None) == log
    assert 'later' in [r['draft']['draft_id'] for r in journal.list_drafts(project)['records']]
    if not interrupted:
        assert journal.commit_clear(project, **b) == {**receipt, 'replayed': True}
        downloaded, _ = personal_recovery.download(project, backup_id=a['manifest_digest'][:16])
        assert json.loads(downloaded) == json.loads(backup)
    assert store.load_document() == before


@pytest.mark.parametrize('damage', ['json', 'manifest', 'duplicate', 'content', 'foreign', 'symlink'])
def test_related_backup_is_validated_before_owner_is_ignored(project, store, tmp_path, damage):
    a = request(project, store); journal.commit_clear(project, **{**a, 'operation_id':'operation-b'})
    path = journal._clear_backup_path(store, a['manifest_digest']); value = json.loads(path.read_bytes())
    if damage == 'json': path.write_text('{bad')
    elif damage == 'symlink':
        target = tmp_path/'evidence.json'; target.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(target)
    else:
        if damage == 'manifest': value['manifest_digest'] = '0'*64
        if damage == 'duplicate': value['records'].append(value['records'][0])
        if damage == 'content': value['records'][0]['record']['draft']['content']['text'] = 'tampered'
        if damage == 'foreign': value['records'][0]['record']['draft']['project_identity'] = 'other-project'
        path.write_text(json.dumps(value))
    state = journal.inspect_clear(project, **a)
    assert state['status'] == 'unverifiable'
    with pytest.raises(LocalStateError): journal.end_clear(project, **a, inspection_digest=state['inspection_digest'])


@pytest.mark.parametrize('change', ['owner', 'content', 'current_state'])
def test_related_evidence_change_invalidates_confirmation(project, store, change):
    a = request(project, store); journal.commit_clear(project, **{**a, 'operation_id':'operation-b'})
    observed = journal.inspect_clear(project, **a)
    assert observed['status'] == 'no_execution_evidence'
    if change == 'current_state': save_draft(store, project, 'later')
    else:
        path = journal._clear_backup_path(store, a['manifest_digest']); value = json.loads(path.read_bytes())
        value['operation_id' if change=='owner' else 'cleared_at'] = 'operation-c' if change=='owner' else '2026-10-25T00:00:00Z'
        path.write_text(json.dumps(value))
    with pytest.raises(LocalStateConflict): journal.end_clear(project, **a, inspection_digest=observed['inspection_digest'])


def test_own_success_is_replayed_but_other_backup_not_claimed(project, store):
    a = request(project, store); original = journal.commit_clear(project, **a)
    save_draft(store, project)
    b = {**a, 'operation_id':'operation-b'}; journal.commit_clear(project, **b)
    observed = journal.inspect_clear(project, **a)
    assert observed['status'] == 'cleared'
    assert observed['receipt']['operation_id'] == a['operation_id']
    assert not observed['backup']['available']
    assert observed['backup']['related_operation']['operation_id'] == b['operation_id']
    assert journal.commit_clear(project, **a) == {**original, 'replayed':True}
