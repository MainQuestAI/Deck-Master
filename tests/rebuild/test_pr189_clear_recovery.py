"""Interrupted personal cleanup is inspectable and fenced after explicit end."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from deck_master import ui_journal as journal
from deck_master.local_state import LocalStateConflict, LocalStateError
from test_ui_state_clear import project, store, save_draft, plan  # noqa: F401


def request(project, store):
    save_draft(store, project)
    p = plan(project)
    return dict(operation_id='original-clear', input=dict(project_id=p['project_id'], scope='current_project',
        draft_ids='all', reading_preferences=True), plan_id=p['plan_id'], manifest_digest=p['manifest_digest'])


def test_not_sent_then_changed_can_end_and_replan(project, store):
    req = request(project, store)
    save_draft(store, project, 'later')
    before = store.load_document()
    with pytest.raises(LocalStateConflict): journal.commit_clear(project, **req)
    observed = journal.inspect_clear(project, **req)
    assert observed['status'] == 'no_execution_evidence'
    ended = journal.end_clear(project, **req, inspection_digest=observed['inspection_digest'])
    assert ended['status'] == 'ended'
    assert journal.inspect_clear(project, **req)['status'] == 'ended'
    assert journal.end_clear(project, **req, inspection_digest=observed['inspection_digest']) == ended
    with pytest.raises(LocalStateConflict, match='ended'): journal.commit_clear(project, **req)
    assert len(plan(project)['items']) == 2
    assert store.load_document() == before


def test_success_lost_response_preserves_later_drafts(project, store):
    req = request(project, store)
    result = journal.commit_clear(project, **req)
    save_draft(store, project, 'later')
    observed = journal.inspect_clear(project, **req)
    assert observed['status'] == 'cleared' and observed['receipt']['cleared'] == result['cleared']
    assert journal.commit_clear(project, **req)['replayed']
    assert [r['draft']['draft_id'] for r in journal.list_drafts(project)['records']] == ['later']


@pytest.mark.parametrize('fault', ['before_delete', 'partial', 'before_receipt'])
def test_interrupted_backup_is_preserved_on_end(project, store, monkeypatch, fault):
    from pathlib import Path
    req = request(project, store)
    save_draft(store, project, 'second')
    p = plan(project); req.update(plan_id=p['plan_id'], manifest_digest=p['manifest_digest'])
    original_unlink = Path.unlink
    count = 0
    def fail_delete(path, *args, **kwargs):
        nonlocal count
        if path.parent == journal._directory(store) and path.suffix == '.json':
            count += 1
            if (fault == 'before_delete' and count == 1) or (fault == 'partial' and count == 2):
                raise OSError('injected deletion interruption')
        return original_unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', fail_delete)
        if fault == 'before_receipt':
            import builtins
            original_open = builtins.open
            def fail_receipt(path, mode='r', *args, **kwargs):
                if Path(path) == journal._clear_log_path(store) and mode == 'a': raise OSError('injected receipt interruption')
                return original_open(path, mode, *args, **kwargs)
            patch.setattr(builtins, 'open', fail_receipt)
        with pytest.raises(OSError): journal.commit_clear(project, **req)
    before = store.load_document()
    observed = journal.inspect_clear(project, **req)
    assert observed['status'] == 'incomplete' and observed['backup']['available']
    ended = journal.end_clear(project, **req, inspection_digest=observed['inspection_digest'])
    raw, _ = journal.clear_recovery_download(project, operation_id=req['operation_id'])
    bundle = json.loads(raw)
    assert bundle['backup']['records'] and bundle['request'] == req
    assert bundle['inspection']['status'] == 'incomplete'
    # A later clear cannot overwrite the operation-owned recovery copy.
    save_draft(store, project, 'new-clear')
    fresh = plan(project)
    journal.commit_clear(project, **{**req, 'operation_id': 'new-op', 'plan_id': fresh['plan_id'], 'manifest_digest': fresh['manifest_digest']})
    assert journal.clear_recovery_download(project, operation_id=req['operation_id'])[0] == raw
    assert journal.inspect_clear(project, **req)['status'] == 'ended'
    assert ended['request'] == req and store.load_document() == before


def test_stale_inspection_and_different_request_are_refused(project, store):
    req = request(project, store)
    observed = journal.inspect_clear(project, **req)
    save_draft(store, project, 'new')
    with pytest.raises(LocalStateConflict): journal.end_clear(project, **req, inspection_digest=observed['inspection_digest'])
    fresh = journal.inspect_clear(project, **req)
    journal.end_clear(project, **req, inspection_digest=fresh['inspection_digest'])
    changed = copy.deepcopy(req); changed['input']['reading_preferences'] = False
    with pytest.raises(LocalStateConflict): journal.inspect_clear(project, **changed)
    with pytest.raises(LocalStateConflict): journal.commit_clear(project, **changed)


def test_damaged_backup_and_end_write_failure_never_report_success(project, store, monkeypatch):
    req = request(project, store)
    journal._clear_backup_path(store, req['manifest_digest']).parent.mkdir(parents=True)
    journal._clear_backup_path(store, req['manifest_digest']).write_text('{bad')
    observed = journal.inspect_clear(project, **req)
    assert observed['status'] == 'unverifiable'
    with pytest.raises(LocalStateError): journal.end_clear(project, **req, inspection_digest=observed['inspection_digest'])
    journal._clear_backup_path(store, req['manifest_digest']).unlink()
    observed = journal.inspect_clear(project, **req)
    from deck_master import ui_clear_recovery
    with monkeypatch.context() as patch:
        patch.setattr(ui_clear_recovery, 'write_json', lambda *a, **kw: (_ for _ in ()).throw(OSError('disk full')))
        with pytest.raises(OSError): journal.end_clear(project, **req, inspection_digest=observed['inspection_digest'])
    assert journal.inspect_clear(project, **req)['status'] == 'no_execution_evidence'
    assert len(journal.list_drafts(project)['records']) == 1


def test_end_and_late_commit_are_serialized(project, store):
    req = request(project, store)
    observed = journal.inspect_clear(project, **req)
    def end():
        try:return journal.end_clear(project, **req, inspection_digest=observed['inspection_digest'])['status']
        except LocalStateConflict:return 'conflict'
    def commit():
        try:return journal.commit_clear(project, **req)['status']
        except LocalStateConflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(end); b=pool.submit(commit); results={a.result(), b.result()}
    assert results in ({'ended', 'conflict'}, {'cleared', 'conflict'})
    result = journal.inspect_clear(project, **req)
    assert result['status'] in ('ended', 'cleared')


def test_cli_inspect_and_end_share_original_request(project, store, tmp_path, capsys):
    from deck_master import cli
    req = request(project, store)
    path = tmp_path / 'clear-input.json'; path.write_text(json.dumps(req['input']))
    flags = ['--project', str(project), '--operation-id', req['operation_id'], '--input', str(path),
        '--plan-id', req['plan_id'], '--manifest-digest', req['manifest_digest']]
    assert cli.main(['ui', 'inspect-clear', *flags]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'no_execution_evidence'
    assert cli.main(['ui', 'end-clear', *flags, '--inspection-digest', result['inspection_digest']]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'ended'
    from deck_master.ui_clear_recovery import listing
    assert listing(project)['recoveries'][0]['operation_id'] == req['operation_id']


def test_corrupt_log_cannot_be_treated_as_not_executed(project, store):
    req = request(project, store)
    journal._clear_log_path(store).write_text('{unfinished receipt')
    state = journal.inspect_clear(project, **req)
    assert state['status'] == 'unverifiable'
    with pytest.raises(LocalStateError): journal.end_clear(project, **req, inspection_digest=state['inspection_digest'])


def test_ended_record_cannot_be_borrowed_by_another_project(project, store, tmp_path):
    from deck_master.samples import create_sample
    from deck_master.store import Store
    from deck_master.ui_clear_recovery import closure_path
    req = request(project, store)
    state = journal.inspect_clear(project, **req)
    journal.end_clear(project, **req, inspection_digest=state['inspection_digest'])
    other = tmp_path / 'other-project'; create_sample(other, page_count=2, readonly=False)
    other_store = Store(other)
    dest = closure_path(other_store, req['operation_id']); dest.parent.mkdir(parents=True)
    dest.write_bytes(closure_path(store, req['operation_id']).read_bytes())
    with pytest.raises(LocalStateConflict): journal.clear_recovery_download(other, operation_id=req['operation_id'])
