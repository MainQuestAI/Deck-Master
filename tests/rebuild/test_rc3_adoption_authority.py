"""Adoption authority is enforced through public SVG SDK flows; L1, no calls."""
import copy
import uuid

import pytest

from deck_master import collaboration, eligibility
from deck_master.operations import OperationError
from rc3_fixtures import evidence_for
from candidate_fixtures import store as candidate_store, dispatch, start, accept, envelope


def grant(store, policy, *, replace=True):
    doc = store.load_document()
    original_ref = doc['collaboration']['authorizations'][-1]
    original = store.read_object_json(original_ref)
    value = {
        'mode': 'execute', 'actions': ['change.commit'], 'scope': original['scope'],
        'max_external_calls': 0, 'max_candidate_count': 2, 'adoption_policy': policy,
        'instruction_evidence': evidence_for(store.project_root,
            text=('L1 explicit restriction: return comparison candidates without changing current artifacts.'
                  if policy == 'candidate_only' else
                  'L1 explicit permission: automatically apply this bounded SVG change within the fixed scope.'),
            locator='L1:adoption-authority:' + policy),
    }
    if replace:
        value.update(authorization_id=original['authorization_id'], replaces=original_ref)
    return collaboration.grant(store.project_root, input=value,
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))['authorization_ref']


def artifacts(document):
    return copy.deepcopy({key: document.get(key) for key in
                          ('narrative', 'content_plan', 'pages', 'outputs')})


def test_candidate_only_authority_cannot_be_upgraded_by_auto_svg_dispatch(candidate_store):
    store = candidate_store
    grant(store, 'candidate_only')
    before = store.load_document()
    pointer = store.read_current()
    with pytest.raises(OperationError, match='automatic adoption needs explicit within_scope authority') as failure:
        dispatch(store, mode='auto', layer='svg')
    assert failure.value.error_code == 'invalid_input'
    assert store.load_document() == before
    assert store.read_current() == pointer


def test_candidate_only_trial_accepts_real_svg_without_changing_current(candidate_store):
    store = candidate_store
    authority = grant(store, 'candidate_only')
    before = artifacts(store.load_document())
    task = dispatch(store, mode='trial', layer='svg')
    assert task['collaboration_binding']['authorization_ref'] == authority
    assert task['collaboration_binding']['adoption_policy'] == 'candidate_only'
    start(store, task)
    result = accept(store, task)
    assert result['status'] == 'candidate_ready'
    assert result['candidate_ids'] and result['current_artifacts_changed'] is False
    assert artifacts(store.load_document()) == before


def test_explicit_within_scope_auto_svg_still_updates_only_selected_page(candidate_store):
    store = candidate_store
    authority = grant(store, 'within_scope')
    before = store.load_document()
    task = dispatch(store, mode='auto', layer='svg')
    assert task['collaboration_binding']['authorization_ref'] == authority
    assert task['collaboration_binding']['adoption_policy'] == 'within_scope'
    start(store, task)
    assert accept(store, task)['status'] == 'accepted'
    after = store.load_document()
    assert after['pages'][0]['svg'] != before['pages'][0]['svg']
    assert after['pages'][0]['blueprint'] == before['pages'][0]['blueprint']
    assert after['pages'][1] == before['pages'][1]
    assert after['outputs'] == before['outputs']


def test_tightened_current_authority_refuses_already_claimed_auto_result(candidate_store):
    store = candidate_store
    original = grant(store, 'within_scope')
    task = dispatch(store, mode='auto', layer='svg')
    assert task['collaboration_binding']['authorization_ref'] == original
    start(store, task)
    payload = envelope(store, task)
    grant(store, 'candidate_only')
    before = store.load_document()
    state = eligibility.task_binding_state(store, before, task)
    assert state['status'] == 'invalid' and state['reasons']
    # The original Task remains immutable. The existing current-region guard
    # may reject its superseded ref before the new policy-specific guard.
    assert task['collaboration_binding']['authorization_ref'] == original
    with pytest.raises(eligibility.EligibilityBlocked):
        accept(store, task, payload)
    assert store.load_document() == before


def test_old_candidate_only_does_not_shadow_equally_funded_explicit_auto_authority(candidate_store):
    store = candidate_store
    restricted = grant(store, 'candidate_only')
    automatic = grant(store, 'within_scope', replace=False)
    task = dispatch(store, mode='auto', layer='svg')
    assert task['collaboration_binding']['authorization_ref'] == automatic
    assert task['collaboration_binding']['authorization_ref'] != restricted
    start(store, task)
    assert accept(store, task)['status'] == 'accepted'
