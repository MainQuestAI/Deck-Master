"""HTTP-only protocol admission; request bodies and service recovery stay intact."""
import json
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from deck_master import ui_journal
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401


def test_clear_protocol_requires_upgrade_but_preserves_recovery_and_exact_replay(project, store):
    save_draft(store, project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        base = server.start().rstrip('/')
        with urlopen(base + '/api/session') as response:
            token = json.load(response)['token']
        headers = {'Origin': base, 'X-Deck-Token': token, 'Content-Type': 'application/json'}

        def post(endpoint, body, extra=None):
            request = Request(base + '/api/ui-state/' + endpoint,
                data=json.dumps(body).encode(), headers={**headers, **(extra or {})})
            try:
                with urlopen(request) as response:
                    return response.status, json.load(response)
            except HTTPError as response:
                return response.code, json.load(response)

        input_value = {'project_id': before['project_id'], 'scope': 'current_project',
                       'draft_ids': 'all', 'reading_preferences': True}
        code, plan = post('plan-clear', {'input': input_value})
        assert code == 200 and plan['items']  # Plan is still headerless/read-only.
        request = {'operation_id': str(uuid.uuid4()), 'input': input_value,
                   'plan_id': plan['plan_id'], 'manifest_digest': plan['manifest_digest']}
        for extra in ({}, {'X-Deck-Clear-Recovery': 'localstorage.v1'},
                      {'X-Deck-Clear-Recovery': 'indexeddb.v2'}):
            code, result = post('commit-clear', request, extra)
            assert code == 409
            assert result['error']['code'] == 'clear_recovery_upgrade_required'
            assert result['error']['field'] == 'recovery_protocol'
            assert '原清理请求' in result['error']['message']
            assert len(ui_journal.list_drafts(project)['records']) == 1
            assert store.load_document() == before

        # Original session/origin checks take precedence over the new protocol.
        for extra in ({'X-Deck-Token': 'wrong'}, {'Origin': 'https://untrusted.example'}):
            code, result = post('commit-clear', request, extra)
            assert code == 403
            assert result == {'error': 'same-origin session token required'}

        # An old request can be inspected and explicitly ended without adding
        # fields to its original body or supplying the new commit header.
        code, inspected = post('inspect-clear', request)
        assert code == 200 and inspected['status'] == 'no_execution_evidence'
        code, ended = post('end-clear', {**request, 'inspection_digest': inspected['inspection_digest']})
        assert code == 200 and ended['status'] == 'ended'
        assert len(ui_journal.list_drafts(project)['records']) == 1

        # Same manifest can still start a new, distinct operation after ending.
        request = {**request, 'operation_id': str(uuid.uuid4())}
        protocol = {'X-Deck-Clear-Recovery': 'indexeddb.v1'}
        code, cleared = post('commit-clear', request, protocol)
        assert code == 200 and cleared['status'] == 'cleared'
        assert cleared['operation_id'] == request['operation_id']
        save_draft(store, project, 'after-clear', text='Preserve on exact replay')
        code, replay = post('commit-clear', request, protocol)
        assert code == 200 and replay['replayed'] is True and cleared['replayed'] is False
        assert {key: value for key, value in replay.items() if key != 'replayed'} == {
            key: value for key, value in cleared.items() if key != 'replayed'}
        assert [row['draft']['draft_id'] for row in ui_journal.list_drafts(project)['records']] == ['after-clear']
        assert store.load_document() == before
    finally:
        server.stop()
