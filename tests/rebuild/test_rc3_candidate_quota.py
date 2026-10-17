"""Formal trial slots use existing Tasks; no calls or professional approval."""
import uuid

import pytest

from deck_master import candidates, changes, collaboration, content_ops, editing, eligibility, service
from rc3_fixtures import evidence_for
from test_candidates import store as candidate_store, dispatch, start, accept, plan, adopt
from test_content_candidates import project as content_project, content_ops_value


def grant(store, limit, *, actions=None, pages=None, parent=None, replace=False):
    doc = store.load_document()
    ref = doc['collaboration']['authorizations'][-1]
    original = store.read_object_json(ref)
    value = {'mode': 'execute', 'actions': actions or original['actions'],
        'scope': {**original['scope'], **({'page_ids': pages, 'page_manifest_ref': None} if pages else {})},
        'max_external_calls': 0, 'max_candidate_count': limit,
        'adoption_policy': 'within_scope', 'budget_parent_ref': parent,
        'instruction_evidence': evidence_for(store.project_root,
            text=f'Explicit L1 quota: at most {limit} candidate slots, no image calls.', locator='L1:candidate-quota')}
    if replace:
        value.update(authorization_id=original['authorization_id'], replaces=ref)
    return collaboration.grant(store.project_root, input=value,
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))['authorization_ref']


def test_two_slots_can_dispatch_together_last_accept_and_adopt_remain_legal(candidate_store):
    store = candidate_store
    authority = grant(store, 2, replace=True)
    first = dispatch(store, 'p01')
    second = dispatch(store, 'p02')
    assert eligibility.candidate_budget(store, store.load_document(), authority)['remaining'] == 0
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        dispatch(store, 'p01')
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document() == before
    start(store, first)
    returned = accept(store, first)
    candidate_id = returned['candidate_ids'][0]
    assert candidates.show(store.project_root, candidate_id=candidate_id)['candidate_id'] == candidate_id
    assert accept(store, first)['status'] == 'already_applied'
    adopt(store, plan(store, [candidate_id]))
    assert eligibility.candidate_budget(store, store.load_document(), authority)['used'] == 2
    service.task_cancel(store.project_root, task_id=second['task_id'], reason='L1 cancel before any candidate result')
    assert eligibility.candidate_budget(store, store.load_document(), authority)['used'] == 1
    dispatch(store, 'p02')
    assert eligibility.candidate_budget(store, store.load_document(), authority)['remaining'] == 0


def test_zero_candidate_budget_refuses_trial_without_writing_but_auto_is_legal(candidate_store):
    store = candidate_store
    grant(store, 0, replace=True)
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        dispatch(store)
    assert store.load_document() == before
    assert dispatch(store, mode='auto')['stage_request']['mode'] == 'auto'


def test_children_share_numeric_candidate_root_and_keep_their_own_smaller_caps(candidate_store):
    store = candidate_store
    root = grant(store, 2, actions=['candidate.adopt'], replace=True)
    first = grant(store, 1, actions=['change.commit'], pages=['p01'], parent=root)
    second = grant(store, 1, actions=['change.commit'], pages=['p02'], parent=root)
    dispatch(store, 'p01')
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        dispatch(store, 'p01')
    assert store.load_document() == before
    assert eligibility.candidate_budget(store, before, first)['remaining'] == 0
    assert eligibility.candidate_budget(store, before, second)['remaining'] == 1
    dispatch(store, 'p02')
    assert eligibility.candidate_budget(store, store.load_document(), root)['used'] == 2


def test_restore_keeps_produced_candidate_consumption(candidate_store):
    store = candidate_store
    authority = grant(store, 1, replace=True)
    basis = store.load_document()['revision_id']
    task = dispatch(store)
    start(store, task)
    candidate_id = accept(store, task)['candidate_ids'][0]
    editing.restore(store.project_root, revision_id=basis, base_revision=store.current_revision_id(),
                    operation_id=str(uuid.uuid4()))
    assert candidates.show(store.project_root, candidate_id=candidate_id)['candidate_id'] == candidate_id
    assert eligibility.candidate_budget(store, store.load_document(), authority)['remaining'] == 0
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        dispatch(store)
    assert store.load_document() == before


def test_batch_reserves_all_planned_trial_slots_atomically(candidate_store):
    store = candidate_store
    grant(store, 1, replace=True)
    before = store.load_document()
    value = {'schema_version': 'change_intent.v1', 'project_id': before['project_id'],
        'base_revision': before['revision_id'], 'intent': 'repair', 'instruction': 'L1 two-page SVG trial',
        'annotation_refs': [], 'max_calls': 0, 'mode': 'trial', 'targets': [
            {'page_id': item['page_id'], 'page_ref': item['page'], 'layer': 'svg', 'artifact_ref': item['svg']}
            for item in before['pages']]}
    planned = changes.plan(store.project_root, input=value)
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        changes.commit(store.project_root, plan_id=planned['plan_id'], base_revision=before['revision_id'],
                       operation_id=str(uuid.uuid4()))
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document() == before


def test_content_changeset_trial_also_needs_one_available_candidate_slot(content_project):
    path, store = content_project
    grant(store, 0, replace=True)
    before = store.load_document()
    planned = content_ops.plan(path, input=content_ops_value(store, 'rewrite', ['p01', 'p02'], mode='trial'))
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        content_ops.commit(path, plan_id=planned['plan_id'], base_revision=before['revision_id'],
                           operation_id=str(uuid.uuid4()))
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document() == before
