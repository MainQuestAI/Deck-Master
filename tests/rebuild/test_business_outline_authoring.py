"""D06a real transaction mechanisms over explicitly synthetic outline objects."""
import copy
import uuid

import pytest

from deck_master import business_outline, collaboration, content_insight, content_production, models, service, tasks
from deck_master.store import ConflictError
from test_business_framing import SCOPE, adoption_request, pending, project, proposals, submit, v2
from test_workbench_reads import commit


def edit_payload(store, refs):
    return {'project_id': store.load_document()['project_id'], 'base_revision': store.current_revision_id(),
            'operation_id': str(uuid.uuid4()), 'narrative_ref': refs[0], 'plan_ref': refs[1],
            'reason': 'Synthetic author clarification: preserve the handoff, clarify the business meaning.',
            'topic_edits': [{'topic_id': 'handoff', 'name': '确认与接手', 'meaning': '先确认已知条件，再将未决事项交给责任人'}],
            'node_edits': [], 'page_edits': []}


def test_closed_planning_read_has_exact_pair_and_no_write(tmp_path):
    path, store, refs = proposals(tmp_path)
    before = store.load_document()
    group = content_insight.argument(path, refs[0]['sha256'])['data']['business_group']
    assert group['plan_ref'] == refs[1] and group['narrative_ref'] == refs[0]
    assert group['can_start_followup'] and group['can_revise'] and not group['can_adopt']
    assert [s['artifact_ref'] for s in group['subject_refs']] == refs
    assert store.load_document() == before


def test_paired_admission_tracks_two_ordered_adoptions(tmp_path):
    path, store, refs = proposals(tmp_path)
    old, decision = adoption_request(path, store, refs)
    group = content_insight.argument(path, refs[0]['sha256'])['data']['business_group']
    assert group['can_adopt'] and group['next_ref'] == refs[0]
    task_count = len(store.load_document()['tasks'])
    for index, ref in enumerate(refs):
        content_production.adopt_proposal(path, input={'proposal_ref': ref, 'decision_ref': decision, 'write_scope': SCOPE},
            base_revision=store.current_revision_id(), operation_id=f'paired-adopt-{index}')
        group = content_insight.argument(path, refs[0]['sha256'])['data']['business_group']
        if index == 0:
            assert group['can_adopt'] and group['next_ref'] == refs[1] and not group['is_adopted']
    assert group['is_adopted'] and not group['can_adopt']
    assert old['closed'] and old['request_id'] != store.load_document()['collaboration']['request']['request_id']
    assert not store.load_document()['pages'] and len(store.load_document()['tasks']) == task_count


def test_author_revision_uses_local_task_and_atomic_matching_proposal(tmp_path):
    path, store, refs = proposals(tmp_path)
    before = store.load_document();value = edit_payload(store, refs)
    result = business_outline.revise(path, value)
    assert result['model_called'] is False and result['adopted'] is False
    new_refs = result['proposal_refs']
    narrative, plan = [store.read_object_json(ref) for ref in new_refs]
    assert narrative['business_frame']['topics'][0]['name'] == '确认与接手'
    assert narrative['previous_ref'] == refs[0] and plan['previous_ref'] == refs[1]
    assert plan['narrative_ref'] == new_refs[0] and narrative['method_applications'] == []
    current = store.load_document()
    assert current.get('narrative') is None and not current['pages']
    assert before['collaboration']['request']['closed'] and current['collaboration']['request']['closed']
    assert before['collaboration']['request']['request_id'] != current['collaboration']['request']['request_id']
    task = store.read_object_json(current['tasks'][-1])
    assert task['status'] == 'completed' and task['cost_class'] == 'local_compute'
    assert all(ref in task['inputs'] for ref in refs)
    revision = current['revision_id']
    again = business_outline.revise(path, value)
    assert again['operation_result']['proposal_refs'] == new_refs
    assert store.current_revision_id() == revision


def test_changed_base_or_payload_does_not_restart_revision(tmp_path):
    path, store, refs = proposals(tmp_path)
    value = edit_payload(store, refs)
    changed = store.load_document();changed['task']['title'] = 'Synthetic concurrent change'
    commit(store, changed, 'concurrent-business-title')
    before = store.load_document()
    with pytest.raises(ConflictError):
        business_outline.revise(path, value)
    assert store.load_document() == before
    value['base_revision'] = store.current_revision_id()
    business_outline.revise(path, value)
    before = store.load_document()
    different = copy.deepcopy(value);different['reason'] += ' different'
    with pytest.raises(ConflictError):
        business_outline.revise(path, different)
    assert store.load_document() == before


def test_changed_strategy_inputs_block_old_outline_before_new_request(tmp_path):
    path, store, refs = proposals(tmp_path)
    changed = store.load_document();changed['task']['scenario'] = 'competitive_bid'
    commit(store, changed, 'synthetic-changed-commercial-task')
    before = store.load_document()
    group = content_insight.argument(path, refs[0]['sha256'])['data']['business_group']
    assert not group['can_revise'] and group['reason_codes']
    with pytest.raises(models.ModelError):
        business_outline.revise(path, edit_payload(store, refs))
    assert store.load_document() == before


def test_facts_are_not_editable_through_interpretation_editor(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store);submit(path, store, task, v2(store.load_document()['project_id'], task=task, maturity='framing'))
    service.continue_project(path);task = pending(store);narrative = v2(store.load_document()['project_id'], task=task)
    source = store.load_document()['sources'][0]
    narrative['nodes'][0].update(authority='reported_fact', statement='Synthetic contract input: preserve unknown device versions and the expert handoff.',
        source_links=[{'source_id': source['source_id'], 'source_version': {'original_sha256': source['original_sha256'],
            'extract': source['extract']}, 'locator': 'L1'}])
    submit(path, store, task, narrative, attach_plan=True)
    refs = content_production.completion_status(store, store.load_document())['outputs']
    value = edit_payload(store, refs);value['node_edits'] = [{'node_id': 'n1', 'statement': 'invent a different fact'}]
    before = store.load_document()
    with pytest.raises(models.ModelError, match='source facts'):
        business_outline.revise(path, value)
    assert store.load_document() == before


def test_interrupted_dispatch_resumes_same_local_task(tmp_path, monkeypatch):
    path, store, refs = proposals(tmp_path);value = edit_payload(store, refs)
    with monkeypatch.context() as patch:
        patch.setattr(service, 'task_start', lambda *a, **k: (_ for _ in ()).throw(OSError('synthetic interrupt')))
        with pytest.raises(OSError):business_outline.revise(path, value)
    task = store.read_object_json(store.load_document()['tasks'][-1]);count = len(store.load_document()['tasks'])
    result = business_outline.revise(path, value)
    assert result['status'] == 'accepted' and len(store.load_document()['tasks']) == count
    assert store.read_object_json(store.load_document()['tasks'][-1])['task_id'] == task['task_id']


def test_lost_accept_ack_replays_without_second_write(tmp_path, monkeypatch):
    path, store, refs = proposals(tmp_path);value = edit_payload(store, refs);original = service.accept_result
    def lost(*a, **k):
        original(*a, **k)
        raise TimeoutError('synthetic lost ack after commit')
    with monkeypatch.context() as patch:
        patch.setattr(service, 'accept_result', lost)
        with pytest.raises(TimeoutError):business_outline.revise(path, value)
    before = store.load_document()
    assert business_outline.revise(path, value)['status'] == 'already_applied'
    assert store.load_document() == before


def test_cancelled_local_task_cannot_publish_revision(tmp_path, monkeypatch):
    path, store, refs = proposals(tmp_path);value = edit_payload(store, refs);original = service.task_start
    def cancel(*a, **k):
        result = original(*a, **k)
        service.task_cancel(path, task_id=k['task_id'])
        return result
    with monkeypatch.context() as patch:
        patch.setattr(service, 'task_start', cancel)
        with pytest.raises(tasks.TaskConflict):business_outline.revise(path, value)
    assert store.load_document().get('narrative') is None
    assert store.read_object_json(store.load_document()['tasks'][-1])['status'] == 'cancelled'


def test_concurrent_change_between_request_and_dispatch_keeps_draft_unpublished(tmp_path, monkeypatch):
    path, store, refs = proposals(tmp_path);value = edit_payload(store, refs);original = collaboration.start_request
    def changed(*a, **k):
        result = original(*a, **k)
        current = store.load_document();current['task']['title'] = 'Concurrent author title'
        commit(store, current, 'concurrent-after-bounded-request')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(collaboration, 'start_request', changed)
        with pytest.raises(ConflictError):business_outline.revise(path, value)
    assert len(store.load_document()['tasks']) == 2 and store.load_document().get('narrative') is None


def test_lost_request_ack_resumes_runtime_computed_request_identity(tmp_path, monkeypatch):
    path, store, refs = proposals(tmp_path);value = edit_payload(store, refs);original = collaboration.start_request
    def lost(*a, **k):
        original(*a, **k)
        raise TimeoutError('synthetic request response lost')
    with monkeypatch.context() as patch:
        patch.setattr(collaboration, 'start_request', lost)
        with pytest.raises(TimeoutError):business_outline.revise(path, value)
    request_id = store.load_document()['collaboration']['request']['request_id']
    result = business_outline.revise(path, value)
    assert result['status'] == 'accepted' and len(store.load_document()['tasks']) == 3
    assert store.load_document()['collaboration']['request']['request_id'] == request_id


def test_business_projection_is_versioned_and_strict_legacy_is_unchanged(tmp_path):
    path, store, refs = proposals(tmp_path)
    value = content_insight.argument(path, refs[0]['sha256'])
    assert value['schema_version'] == 'ui_argument.v2'
    models.validate_schema('ui_argument', value)
    corrupt = copy.deepcopy(value);corrupt['data']['business_group']['can_adopt'] = 'yes'
    with pytest.raises(models.ModelError):models.validate_schema('ui_argument', corrupt)
    old_contract = copy.deepcopy(value);old_contract['schema_version'] = 'ui_argument.v1'
    with pytest.raises(models.ModelError):models.validate_schema('ui_argument', old_contract)
    del old_contract['data']['business_group']
    models.validate_schema('ui_argument', old_contract)
