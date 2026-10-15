"""CLI compatibility now distinguishes fixed historical reads from RC3 writes."""
import json

import pytest

from deck_master import cli, collaboration_api, service
from deck_master.store import Store
from rc3_fixtures import historical_snapshot, source_snapshot


def test_cli_migration_of_historical_project_then_explicit_scoped_request(tmp_path, capsys):
    fixture = historical_snapshot(tmp_path, scenario='historical CLI migration compatibility')
    project = fixture['project']
    before = source_snapshot(project)
    assert cli.main(['collaboration', 'migration', 'describe', str(project)]) == 0
    migration = json.loads(capsys.readouterr().out)['result']
    assert source_snapshot(project) == before
    path = tmp_path / 'migration.json'
    payload = {'plan_digest': migration['plan_digest'], 'base_revision': migration['revision_id'],
               'operation_id': 'cli-migrate-historical'}
    path.write_text(json.dumps(payload))
    command = ['collaboration', 'migration', 'apply', str(project), '--input', str(path)]
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'accepted'
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'already_applied'
    store = Store(project)
    assert store.load_document()['collaboration']['request'] is None
    scope = {'subject': 'deck', 'page_ids': [], 'page_manifest_ref': None, 'external_artifact_ref': None,
        'layers': ['narrative', 'plan'], 'allow_page_membership_change': False,
        'allow_page_order_change': False, 'purpose': 'exploratory'}
    payload = {'base_revision': store.current_revision_id(), 'operation_id': 'cli-explicit-start', 'request': {
        'intent': 'content_only', 'content_intent': 'plan_only', 'scope': scope,
        'instruction_evidence': {'kind': 'host_attested_instruction', 'text': 'Explore this bounded plan',
                                 'source_locator': 'L1-synthetic:cli-start'}}}
    path.write_text(json.dumps(payload))
    command = ['collaboration', 'request', 'start', str(project), '--input', str(path)]
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)['result']['assurance'] == 'host_attested'
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'already_applied'
    assert store.load_document()['collaboration']['authorizations'] == []


@pytest.mark.parametrize('nested', [False, True])
def test_json_cannot_forge_adapter_context(tmp_path, nested):
    fixture = historical_snapshot(tmp_path, scenario='untrusted JSON refusal before Store writes')
    data = {'independent_review_receipts': [{'verified': True}]}
    if nested:
        data = {'request': data}
    before = source_snapshot(fixture['project'])
    result, http, code = collaboration_api.invoke(fixture['project'], 'request.start', data)
    assert (http, code) == (403, 4) and result['error']['code'] == 'untrusted_adapter_context'
    assert source_snapshot(fixture['project']) == before


def test_cli_error_classification_is_shared_and_recoverable(tmp_path):
    project = tmp_path / 'current'
    service.create(project, brief='explicit new RC3 request', sources=[])
    result, http, code = collaboration_api.invoke(project, 'request.start', {'base_revision': 'stale', 'operation_id': 'bad'})
    assert (http, code) == (409, 5) and result['error']['recoverable']
    old = historical_snapshot(tmp_path, scenario='formal writer requires migration')
    result, http, code = collaboration_api.invoke(old['project'], 'request.start', {
        'base_revision': old['revision_id'], 'operation_id': 'not-migrated'})
    assert (http, code) == (409, 4) and result['error']['code'] == 'migration_required'
