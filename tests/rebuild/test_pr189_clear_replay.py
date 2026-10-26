"""A clear receipt is bound to the original request and preserves later drafts."""
import copy
import pytest

from deck_master import ui_journal
from deck_master.local_state import LocalStateConflict
from test_ui_state_clear import project, store, save_draft, plan  # noqa: F401


@pytest.mark.parametrize('change', ['plan_id', 'manifest_digest', 'draft_ids', 'reading_preferences', 'project_id'])
def test_clear_replay_refuses_another_request(project, store, change):
    save_draft(store, project)
    planned = plan(project)
    payload = {'operation_id': 'fixed-clear', 'plan_id': planned['plan_id'],
        'manifest_digest': planned['manifest_digest'], 'input': {'project_id': planned['project_id'],
        'scope': 'current_project', 'draft_ids': 'all', 'reading_preferences': True}}
    first = ui_journal.commit_clear(project, **payload)
    save_draft(store, project, 'later-draft', text='created after the completed clear')
    before = store.load_document()
    replay = ui_journal.commit_clear(project, **payload)
    assert replay['replayed'] and replay['cleared'] == first['cleared']
    changed = copy.deepcopy(payload)
    if change in ('plan_id', 'manifest_digest'):
        changed[change] = 'different'
    else:
        changed['input'][change] = {'draft_ids': [], 'reading_preferences': False, 'project_id': 'foreign'}[change]
    with pytest.raises(LocalStateConflict):
        ui_journal.commit_clear(project, **changed)
    assert [r['draft']['draft_id'] for r in ui_journal.list_drafts(project)['records']] == ['later-draft']
    assert store.load_document() == before


def test_legacy_receipt_stays_readable_but_cannot_prove_exact_replay(project, store):
    import json
    from deck_master.models import validate_schema
    save_draft(store, project)
    planned = plan(project)
    payload = {'operation_id': 'legacy-clear', 'plan_id': planned['plan_id'],
        'manifest_digest': planned['manifest_digest'], 'input': {'project_id': planned['project_id'],
        'scope': 'current_project', 'draft_ids': 'all', 'reading_preferences': True}}
    ui_journal.commit_clear(project, **payload)
    path = store.deck_root / 'workbench' / 'clear-log.jsonl'
    receipt = json.loads(path.read_text())
    receipt.pop('input_digest')
    validate_schema('ui_clear_result', receipt)
    path.write_text(json.dumps(receipt) + '\n')
    before = {str(p): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()}
    assert ui_journal._read_clear_log(store) == [receipt]
    with pytest.raises(LocalStateConflict):
        ui_journal.commit_clear(project, **payload)
    assert {str(p): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()} == before
