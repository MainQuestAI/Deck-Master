"""RP-23 diagnosis: public Runtime calls, synthetic transport only, no image calls."""
import copy
import json
import uuid

import pytest

from deck_master import cli, collaboration, eligibility, generation, service, tasks
from rc3_fixtures import authorize_scope, evidence_for, settle_fidelity_review
from test_generation_protocol import EXECUTION, THREAD, accept, begin, flow, freeze, settle, start  # noqa: F401

NEW_TURN = '33333333-3333-7333-8333-333333333333'
NEW_EXECUTION = f'codex:{THREAD}:{NEW_TURN}'


def claim(project, task, execution):
    return service.task_start(project, task_id=task['task_id'], execution_ref=execution,
        supported_protocols=[task['protocol_version']], capabilities=task['required_capabilities'])


def test_confirmed_not_sent_cli_then_scope_replacement_can_claim_new_task(flow, capsys):
    project, store, task, _ = flow
    start(flow)
    frozen = freeze(flow)
    begun = begin(flow, frozen)
    before = store.load_document()
    with pytest.raises(tasks.TaskConflict, match='another execution'):
        claim(project, task, NEW_EXECUTION)
    assert store.load_document() == before
    # This test has invoked no transport at all: not_sent is known, not guessed.
    assert cli.main(['task', 'call', 'settle', '--project', str(project), '--task-id', task['task_id'],
        '--allowance-id', begun['allowance_id'], '--attempt-id', begun['attempt_id'], '--outcome', 'not_sent']) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['status'] == 'settled'
    released = generation.show(project, attempt_id=begun['attempt_id'])
    assert released['call']['state'] == 'released'
    assert released['attempt']['execution_ref'] == EXECUTION
    # Releasing a call does not transfer the Task's execution identity.
    with pytest.raises(tasks.TaskConflict, match='another execution'):
        claim(project, task, NEW_EXECUTION)
    request = store.load_document()['collaboration']['request']
    changed_scope = copy.deepcopy(request['scope'])
    changed_scope['layers'].remove('output')
    replacement = collaboration.start_request(project, input={'intent': 'full_deck', 'content_intent': None,
        'scope': changed_scope, 'replace_request_id': request['request_id'],
        'instruction_evidence': evidence_for(project, text='L1 next turn: exclude output delivery from this request.', locator='L1:RP23:next-turn')},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert task['task_id'] in replacement['affected_tasks']
    assert tasks._lookup_task(store.load_document(), task['task_id'], store)['status'] == 'superseded'
    # The changed request does not inherit authority from a superseded request.
    authorize_scope(project, actions=['dispatch.blueprint', 'change.commit', 'candidate.adopt', 'allowance.allocate', 'call.begin'],
        scope=changed_scope, max_external_calls=1, max_candidate_count=1, adoption_policy='within_scope',
        evidence=evidence_for(project, text='L1 explicit bounded authority for the changed request.', locator='L1:RP23:grant'))
    settle_fidelity_review(project, page_ids=['p1'], execution_ref='L1-RP23-fidelity', scenario='L1 current changed request')
    current = service.continue_project(project)['pending_tasks'][0]
    assert current['task_id'] != task['task_id']
    claim(project, current, NEW_EXECUTION)
    new_frozen = generation.freeze(project, task_id=current['task_id'], input=current['generation_input'],
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    new_attempt = tasks.call_begin(store, task_id=current['task_id'], allowance_id=current['call_allowances'][0]['allowance_id'],
        execution_ref=NEW_EXECUTION, request_id=new_frozen['request_id'])
    assert new_attempt['attempt_id'] != begun['attempt_id']
    assert generation.show(project, attempt_id=new_attempt['attempt_id'])['attempt']['execution_ref'] == NEW_EXECUTION
    retained = generation.show(project, attempt_id=begun['attempt_id'])
    assert {k: v for k, v in retained.items() if k != 'revision_id'} == {k: v for k, v in released.items() if k != 'revision_id'}
    # No transport was sent by this diagnostic; settle its reservation honestly.
    tasks.call_settle(store, task_id=current['task_id'], allowance_id=new_attempt['allowance_id'],
        attempt_id=new_attempt['attempt_id'], outcome='not_sent', report_bytes=None)


def test_unknown_is_not_not_sent_or_reclaim_permission(flow):
    project, store, task, _ = flow
    start(flow)
    frozen = freeze(flow)
    begun = begin(flow, frozen)
    settle(flow, begun, outcome='unknown')
    before = store.load_document()
    with pytest.raises(tasks.EnvelopeError, match='actual report'):
        settle(flow, begun, outcome='not_sent')
    assert store.load_document() == before
    with pytest.raises((tasks.TaskConflict, eligibility.EligibilityBlocked)):
        claim(project, task, NEW_EXECUTION)
    assert generation.show(project, attempt_id=begun['attempt_id'])['call']['state'] == 'unknown'


def test_new_turn_selector_cannot_be_assigned_to_old_attempt(flow):
    project, store, _, native = flow
    start(flow)
    frozen = freeze(flow)
    begun = begin(flow, frozen)
    report, raw = native()  # Explicit synthetic event, never a real tool output.
    different_turn = {**report, 'turn_id': NEW_TURN}
    before = store.load_document()
    with pytest.raises(generation.GenerationError, match='claimed execution'):
        settle(flow, begun, different_turn)
    assert store.load_document() == before
    # Honest Host reporting can preserve a consumed fact; it cannot upgrade the
    # mismatched event or make its bytes adoptable.
    settle(flow, begun, {'synthetic_l1': 'Tool completed in a different execution; native binding is unavailable.'})
    with pytest.raises(generation.GenerationError, match='native observation'):
        accept(flow, frozen, begun, raw)
    observation = generation.show(project, attempt_id=begun['attempt_id'])
    assert observation['call']['state'] == 'consumed'
    assert observation['observations'][-1]['observer'] == 'host_reported'
    assert store.load_document()['pages'][0]['blueprint'] is None


def test_existing_correctly_bound_completion_can_be_accepted_later_without_new_call(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    begun = begin(flow, frozen)
    report, raw = native()
    settle(flow, begun, report)
    observed = generation.show(project, attempt_id=begun['attempt_id'])
    # Resume by reading the original identities, not by claiming another turn.
    assert observed['attempt']['execution_ref'] == EXECUTION
    accepted = accept(flow, frozen, begun, raw)
    assert accepted['status'] == 'accepted'
    assert accept(flow, frozen, begun, raw)['revision_id'] == accepted['revision_id']
    saved = tasks._lookup_task(store.load_document(), task['task_id'], store)
    assert len(saved['generation_attempts']) == len(saved['call_allowances']) == 1
    assert saved['call_allowances'][0]['state'] == 'consumed'


def test_cancelled_task_retains_completed_call_but_cannot_adopt_its_late_output(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    begun = begin(flow, frozen)
    report, raw = native()
    service.task_cancel(project, task_id=task['task_id'], reason='L1 new turn has withdrawn the old work')
    settle(flow, begun, report)
    with pytest.raises(tasks.TaskConflict, match='after cancellation'):
        accept(flow, frozen, begun, raw)
    assert generation.show(project, attempt_id=begun['attempt_id'])['call']['state'] == 'consumed'
    assert store.load_document()['pages'][0]['blueprint'] is None


def test_sdk_controller_new_execution_claim_cannot_rebind_old_attempt(flow):
    from deck_master.native_image_evidence import NativeImageRuntime, NativeObservationRejected
    from test_rc3_native_image_bridge import issue, prepared, settle_native
    frozen, begun, provider, registry = prepared(flow)
    provider.claims['binding']['execution_ref'] = NEW_EXECUTION
    with NativeImageRuntime(registry).bound():
        with pytest.raises(NativeObservationRejected, match='exact Task'):
            issue(flow, begun, registry)
        settlement = settle_native(flow, begun)
    assert settlement['native_observation_status'] == 'rejected'
    assert generation.show(flow[0], attempt_id=begun['attempt_id'])['call']['state'] == 'consumed'
    with pytest.raises(generation.GenerationError, match='native observation'):
        accept(flow, frozen, begun, provider.png)
