"""RP-04: paused recovery is a read of committed facts, not new permission."""
from copy import deepcopy
import uuid

import pytest

from deck_master import candidates, collaboration, eligibility, generation, icons, pipeline, stages, tasks
from deck_master.operations import OperationError
from test_candidate_decisions import store, candidate  # noqa: F401
from test_icon_quality import icon_store, input_for  # noqa: F401
from test_generation_protocol import flow, start, freeze, begin, EXECUTION  # noqa: F401


def pause(store):
    collaboration.pause_request(store.project_root, reason='Synthetic pause before exact recovery',
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))


def test_icon_confirmation_recovers_while_paused_but_new_or_changed_request_does_not(icon_store):
    value = input_for(icon_store)
    proposal = icons.propose(icon_store.project_root, input=value)
    other = icons.propose(icon_store.project_root, input={**value, 'instruction': 'Different bounded correction'})
    args = dict(proposal_id=proposal['proposal_id'], base_revision=value['base_revision'], operation_id=str(uuid.uuid4()))
    first = icons.confirm(icon_store.project_root, **args)
    pause(icon_store)
    before = icon_store.load_document()
    second = icons.confirm(icon_store.project_root, **args)
    assert second['operation_result'] == first['operation_result']
    assert icon_store.load_document() == before
    with pytest.raises(OperationError, match='different payload'):
        icons.confirm(icon_store.project_root, **{**args, 'proposal_id': other['proposal_id']})
    with pytest.raises(eligibility.EligibilityBlocked) as denied:
        icons.confirm(icon_store.project_root, **{**args, 'operation_id': str(uuid.uuid4())})
    assert denied.value.error_code == 'request_paused'


def test_candidate_decision_recovers_while_paused_and_validates_complete_payload(store):
    cid, _ = candidate(store)
    doc = store.load_document()
    value = dict(schema_version='candidate_decision.v1', project_id=doc['project_id'],
        base_revision=doc['revision_id'], candidate_id=cid, decision='keep_current', expected_decision_ref=None)
    args = dict(input=value, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    first = candidates.decide(store.project_root, **args)
    pause(store)
    before = store.load_document()
    assert candidates.decide(store.project_root, **args)['operation_result'] == first['operation_result']
    assert store.load_document() == before
    for changed in ({'decision': 'reopen'}, {'candidate_id': 'another-candidate'}, {'project_id': 'another-project'},
                    {'expected_decision_ref': {'path': 'different', 'sha256': '0' * 64}}):
        with pytest.raises(OperationError, match='different payload'):
            candidates.decide(store.project_root, **{**args, 'input': {**value, **changed}})
    with pytest.raises(eligibility.EligibilityBlocked) as denied:
        candidates.decide(store.project_root, **{**args, 'operation_id': str(uuid.uuid4())})
    assert denied.value.error_code == 'request_paused'
    from deck_master import pipeline
    with pytest.raises(OperationError, match='different payload'):
        pipeline.produce(store.project_root, base_revision=args['base_revision'], operation_id=args['operation_id'])
    assert store.load_document() == before


def test_call_begin_recovery_keeps_identity_request_and_allowance_binding(flow):
    _, store, task, _ = flow
    start(flow)
    frozen = freeze(flow)
    first = begin(flow, frozen)
    pause(store)
    before = deepcopy(store.load_document())
    replay = begin(flow, frozen)
    assert replay['status'] == 'already_started'
    assert replay['attempt_id'] == first['attempt_id'] and replay['attempt_ref'] == first['attempt_ref']
    assert store.load_document() == before
    with pytest.raises(tasks.TaskConflict, match='execution_ref'):
        tasks.call_begin(store, task_id=task['task_id'], allowance_id=first['allowance_id'],
                         execution_ref=EXECUTION + '-other', request_id=frozen['request_id'])
    with pytest.raises(generation.GenerationError):
        begin(flow, {'request_id': 'another-request'})
    with pytest.raises(tasks.EnvelopeError):
        begin(flow, frozen, allowance='not-allocated')
    assert store.load_document() == before


from test_candidates import store as assembly_store  # noqa: E402,F401
from test_pipeline_preview_reuse import prepared  # noqa: E402


@pytest.mark.render
@pytest.mark.parametrize('entrypoint', [stages.assemble, pipeline.produce])
def test_real_assembly_then_pause_replays_without_compiling_or_writing(assembly_store, monkeypatch, entrypoint):
    store = assembly_store
    doc = prepared(store)
    args = dict(base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    first = entrypoint(store.project_root, **args)
    assert first['operation_result']['report']['status'] == 'pass'
    pause(store)
    before = store.load_document()
    objects = sorted(store.objects_dir.rglob('*'))

    def forbidden(*args, **kwargs):
        pytest.fail('exact replay must not compile, render, read back or create output artifacts')

    for name in ('compile_deck', 'render_deck', 'readback', 'artifact'):
        monkeypatch.setattr(pipeline, name, forbidden)
    replay = entrypoint(store.project_root, **args)
    assert replay['operation_result'] == first['operation_result']
    assert replay['committed_revision_id'] == first['committed_revision_id']
    assert replay['current_revision_id'] == before['revision_id']
    assert store.load_document() == before and sorted(store.objects_dir.rglob('*')) == objects
    with pytest.raises(OperationError, match='different payload'):
        entrypoint(store.project_root, **{**args, 'base_revision': before['revision_id']})
    with pytest.raises(eligibility.EligibilityBlocked) as denied:
        entrypoint(store.project_root, base_revision=before['revision_id'], operation_id=str(uuid.uuid4()))
    assert denied.value.error_code == 'request_paused'
    # Receipt integrity remains mandatory even on the read-only recovery path.
    from deck_master.snapshots import load_snapshot
    saved = load_snapshot(store, first['committed_revision_id'])
    receipt = saved['change']['operation_commit']
    (store.project_root / receipt['path']).write_bytes(b'corrupt receipt')
    with pytest.raises(OperationError) as damaged:
        entrypoint(store.project_root, **args)
    assert damaged.value.error_code == 'operation_unavailable'


def test_inflight_recovery_never_invents_a_missing_attempt(flow, monkeypatch):
    _, store, task, _ = flow
    start(flow)
    frozen = freeze(flow)
    begin(flow, frozen)
    pause(store)
    original_lookup = tasks._lookup_task

    def damaged(document, task_id, current_store):
        actual = original_lookup(document, task_id, current_store)
        return {**actual, 'generation_attempts': []}

    monkeypatch.setattr(tasks, '_lookup_task', damaged)
    before = store.load_document()
    objects = sorted(store.objects_dir.rglob('*'))
    with pytest.raises(generation.GenerationError, match='no committed attempt'):
        begin(flow, frozen)
    assert store.load_document() == before and sorted(store.objects_dir.rglob('*')) == objects


def test_reserved_call_is_not_started_while_paused(flow):
    _, store, _, _ = flow
    start(flow)
    frozen = freeze(flow)
    pause(store)
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as denied:
        begin(flow, frozen)
    assert denied.value.error_code == 'request_paused'
    assert store.load_document() == before
