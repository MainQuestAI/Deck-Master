"""RP-24 read-only diagnostic, explicit synthetic calls and snapshots only."""
import json
import pytest

from deck_master import cli, generation, service, tasks
from deck_master.native_image_evidence import NativeImageRegistry
from rc3_fixtures import source_snapshot
from test_generation_protocol import flow, start, freeze, begin


@pytest.mark.parametrize('state', ['in_flight', 'unknown', 'consumed', 'released', 'cancelled'])
def test_public_attempt_diagnostic_preserves_facts_without_inspecting_external_events(flow, monkeypatch, capsys, state):
    project, store, task, _ = flow
    start(flow)
    attempt = begin(flow, freeze(flow))
    if state in ('unknown', 'consumed', 'released'):
        tasks.call_settle(store, task_id=task['task_id'], allowance_id=attempt['allowance_id'],
            attempt_id=attempt['attempt_id'], outcome='not_sent' if state == 'released' else state,
            report_bytes=b'{"synthetic_l1":"explicit call fact, not native proof"}')
    if state == 'cancelled':
        service.task_cancel(project, task_id=task['task_id'])
    normal = generation.show(project, attempt_id=attempt['attempt_id'])
    before = source_snapshot(project)
    def forbidden(*args, **kwargs):
        pytest.fail('A read must never collect or issue external native evidence')
    monkeypatch.setattr(generation, 'collect_codex_image', forbidden)
    monkeypatch.setattr(NativeImageRegistry, 'image_context', forbidden)
    assert cli.main(['attempts', 'show', '--project', str(project), '--attempt-id',
                     attempt['attempt_id'], '--explain-reassociation']) == 0
    read = json.loads(capsys.readouterr().out)
    diagnostic = read.pop('cross_execution_diagnostic')
    assert read == normal
    assert diagnostic['status'] == 'unsupported'
    assert diagnostic['association_ready'] is diagnostic['adoption_ready'] is False
    assert diagnostic['current_authority_checked'] is diagnostic['current_budget_checked'] is False
    assert diagnostic['facts']['call_state'] == normal['call']['state']
    assert diagnostic['facts']['execution_ref'] == normal['attempt']['execution_ref']
    if state == 'cancelled':
        assert diagnostic['facts']['task_status'] == 'cancelled'
        assert diagnostic['facts']['call_state'] == 'in_flight'
    assert {proof['verification'] for proof in diagnostic['proof_obligations']} == {
        'not_established', 'not_evaluated', 'unsupported'}
    assert source_snapshot(project) == before


def test_historical_cli_diagnostic_never_claims_current_authority(flow, capsys):
    project, store, task, _ = flow
    start(flow)
    attempt = begin(flow, freeze(flow))
    old_revision = store.current_revision_id()
    service.task_cancel(project, task_id=task['task_id'])
    before = source_snapshot(project)
    assert cli.main(['attempts', 'show', '--project', str(project), '--attempt-id', attempt['attempt_id'],
        '--revision', old_revision, '--explain-reassociation']) == 0
    read = json.loads(capsys.readouterr().out)
    diag = read['cross_execution_diagnostic']
    assert diag['revision_id'] == read['revision_id'] == old_revision
    assert diag['fact_scope'] == 'historical_snapshot'
    assert diag['facts']['task_status'] == 'running'
    assert tasks._lookup_task(store.load_document(), task['task_id'], store)['status'] == 'cancelled'
    assert not diag['current_authority_checked'] and not diag['current_budget_checked']
    assert not diag['association_ready'] and not diag['adoption_ready']
    assert source_snapshot(project) == before


def test_request_read_cannot_be_used_as_association_preparation(flow):
    project, _, _, _ = flow
    start(flow)
    request = freeze(flow)
    before = source_snapshot(project)
    with pytest.raises(generation.GenerationError, match='existing attempt'):
        generation.show(project, request_id=request['request_id'], explain_reassociation=True)
    assert source_snapshot(project) == before
