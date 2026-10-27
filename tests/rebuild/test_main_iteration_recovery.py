"""Unknown draft-save requests are portable evidence, never replay commands."""
import copy
from http.client import HTTPConnection
from urllib.parse import urlsplit

import pytest

from deck_master import ui_journal
from deck_master.local_state import LocalStateError
from deck_master.models import canonical_json_bytes
from deck_master.web import WorkbenchServer
from test_workbench_services import auth
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


@pytest.mark.parametrize('text', ['a' * 1_100_000, '中😀' * 180_000], ids=['ascii', 'utf8'])
def test_two_large_drafts_roundtrip_without_replaying_original(project, store, text):
    current = save_draft(store, project)['record']['draft']
    previous = copy.deepcopy(current)
    previous['content']['text'] = text
    current['content']['text'] = text[:-1] + 'b'
    pending = {'draft': previous, 'expected_etag': None}
    recovery = ui_journal.recovery_file(project, draft=current, pending_save=pending)
    assert 2_000_000 < len(canonical_json_bytes(recovery)) <= 4_000_000
    result = ui_journal.import_recovery(project, recovery=recovery)
    assert result['preserved_pending_save']
    assert result['record']['draft']['content'] == current['content']
    assert recovery['pending_save'] == pending
    assert recovery['digest'] == ui_journal.digest(current)
    assert recovery['pending_save_digest'] == ui_journal.digest(pending)


def test_single_draft_capacity_is_unchanged_for_both_recovery_versions(project, store):
    current = save_draft(store, project)['record']['draft']
    current['draft_id'] = 'near-limit'
    current['content']['text'] = ''
    current['content']['text'] = 'a' * (1_998_976 - len(canonical_json_bytes(current)))
    pending = {'draft': copy.deepcopy(current), 'expected_etag': None}
    assert ui_journal.import_recovery(project, recovery=ui_journal.recovery_file(
        project, draft=current, pending_save=pending))['preserved_pending_save']
    for which in ('current', 'pending'):
        one, two = copy.deepcopy(current), copy.deepcopy(pending)
        (one if which == 'current' else two['draft'])['content']['text'] += 'a'
        with pytest.raises(LocalStateError):
            ui_journal.recovery_file(project, draft=one, pending_save=two)


@pytest.mark.parametrize('endpoint,limit', [('/api/drafts/import', 4_001_024),
    ('/api/drafts/recovery', 4_001_024), ('/api/drafts/save', 2_000_000)])
def test_only_recovery_http_channels_have_extra_transport_capacity(project, store, endpoint, limit):
    current = save_draft(store, project)['record']['draft']
    payload = {'draft': current} if endpoint != '/api/drafts/import' else {
        'recovery': ui_journal.recovery_file(project, draft=current)}
    server = WorkbenchServer(project)
    url = server.start()
    try:
        parsed = urlsplit(url)
        for size in (limit - 1, limit, limit + 1):
            raw = canonical_json_bytes(payload)
            raw += b' ' * (size - len(raw))
            connection = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
            try:
                if size > limit:
                    connection.putrequest('POST', endpoint)
                    for key, value in {**auth(url), 'Content-Length': str(size)}.items():
                        connection.putheader(key, value)
                    connection.endheaders()
                else:
                    connection.request('POST', endpoint, body=raw, headers=auth(url))
                response = connection.getresponse()
                body = response.read()
                assert response.status == (422 if size > limit else 200), body[:500]
            finally:
                connection.close()
    finally:
        server.stop()
