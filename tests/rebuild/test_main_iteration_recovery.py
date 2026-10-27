"""Unknown draft-save requests are portable evidence, never replay commands."""
import copy

import pytest

from deck_master import ui_journal
from deck_master.local_state import LocalStateError
from test_ui_state_clear import project, store, save_draft  # noqa: F401


def test_recovery_keeps_exact_original_request_and_imports_only_current_draft(project, store):
    current = save_draft(store, project)['record']['draft']
    previous = copy.deepcopy(current); previous['content']['text'] = 'sent-v1'
    current['content']['text'] = 'current-v2'
    request = {'draft': previous, 'expected_etag': None}
    recovery = ui_journal.recovery_file(project, draft=current, pending_save=request)
    assert recovery['pending_save'] == request
    assert recovery['digest'] == ui_journal.digest(current)
    assert recovery['pending_save_digest'] == ui_journal.digest(request)
    result = ui_journal.import_recovery(project, recovery=recovery)
    assert result['preserved_pending_save']
    assert result['record']['draft']['content']['text'] == 'current-v2'
    assert all(row['draft']['content']['text'] != 'sent-v1' for row in ui_journal.list_drafts(project)['records'])


@pytest.mark.parametrize('mutation', ['hash', 'basis', 'identity', 'absolute_path'])
def test_recovery_original_request_is_validated_before_any_import(project, store, mutation):
    current = save_draft(store, project)['record']['draft']
    recovery = ui_journal.recovery_file(project, draft=current, pending_save={'draft': copy.deepcopy(current), 'expected_etag': None})
    if mutation == 'hash':
        recovery['pending_save']['expected_etag'] = 'a' * 64
    else:
        old = recovery['pending_save']['draft']
        if mutation == 'basis':
            old['draft_id'] = 'another-draft'
        elif mutation == 'identity':
            old['project_identity'] = 'foreign'
        else:
            old['content']['text'] = '/absolute/local/path'
        recovery['pending_save_digest'] = ui_journal.digest(recovery['pending_save'])
    before = ui_journal.list_drafts(project)
    with pytest.raises((LocalStateError, ValueError)):
        ui_journal.import_recovery(project, recovery=recovery)
    assert ui_journal.list_drafts(project) == before


def test_legacy_recovery_file_still_imports_without_new_metadata(project, store):
    current = save_draft(store, project)['record']['draft']
    recovery = ui_journal.recovery_file(project, draft=current)
    assert set(recovery) == {'schema_version', 'draft', 'digest'}
    assert ui_journal.import_recovery(project, recovery=recovery)['record']['draft'] == current
