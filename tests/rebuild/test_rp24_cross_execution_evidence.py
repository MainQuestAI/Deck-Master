"""RP-24 evidence-model regressions; all events/projects explicitly synthetic."""
import copy
import pytest
from deck_master import generation, tasks
from deck_master.models import canonical_json_bytes
from deck_master.native_image_evidence import NativeImageRegistry, NativeImageRuntime, NativeObservationRejected
from test_generation_protocol import flow, start, freeze, begin
from test_rc3_native_image_bridge import prepared, issue, settle_native


def test_begin_is_reservation_not_proof_of_send_or_absence(flow):
    start(flow)
    frozen = freeze(flow)
    attempt = begin(flow, frozen)
    shown = generation.show(flow[0], attempt_id=attempt['attempt_id'])
    assert shown['call']['state'] == 'in_flight'
    assert shown['attempt']['observations'] == []
    assert shown['attempt']['output_refs'] == []
    # No transport invoked anywhere in this test, despite identical in_flight state.


def test_execution_b_selector_rejected_before_collecting_b_event(flow, monkeypatch):
    start(flow)
    attempt = begin(flow, freeze(flow))
    monkeypatch.setattr(generation, 'collect_codex_image', lambda *a, **k: pytest.fail('must not relabel B as A'))
    with pytest.raises(generation.GenerationError, match='claimed execution'):
        tasks.call_settle(flow[1], task_id=flow[2]['task_id'], allowance_id=attempt['allowance_id'],
            attempt_id=attempt['attempt_id'], outcome='consumed', report_bytes=canonical_json_bytes({
                'source':'codex_session.v1', 'thread_id':'11111111-1111-7111-8111-111111111111',
                'turn_id':'33333333-3333-7333-8333-333333333333','item_id':'exec-other'}))


def test_registry_seen_digest_is_local_not_persistent(flow):
    _, attempt, provider, registry = prepared(flow)
    with NativeImageRuntime(registry).bound():
        issue(flow, attempt, registry)
        provider.claims['diagnostic_extra'] = 'Synthetic changed authenticated event claims'
        with pytest.raises(NativeObservationRejected, match='rebound'):
            issue(flow, attempt, registry)
    restarted = NativeImageRegistry()
    restarted.register(provider)
    with NativeImageRuntime(restarted).bound():
        assert issue(flow, attempt, restarted) is not None
    # This tests admission cache lifetime, NOT successful second consumption.


def test_persistent_project_invocation_guard_survives_registry_restart(flow):
    _, attempt, provider, registry = prepared(flow)
    with NativeImageRuntime(registry).bound():
        result = settle_native(flow, attempt, issue(flow, attempt, registry))
    assert result['native_observation_status'] == 'accepted'
    shown = generation.show(flow[0], attempt_id=attempt['attempt_id'])
    # A distinct allowance cannot consume an already registered project invocation.
    other = {**copy.deepcopy(shown['call']), 'allowance_id':'another-allowance',
             'state':'in_flight','invocation_ref':None,'evidence':[]}
    with pytest.raises(tasks.TaskConflict, match='already registered in project'):
        tasks._settle_target(flow[1], flow[1].load_document(), flow[2]['task_id'],
            other['allowance_id'], other, 'consumed', b'{"synthetic":true}',
            invocation_ref=shown['call']['invocation_ref'])
