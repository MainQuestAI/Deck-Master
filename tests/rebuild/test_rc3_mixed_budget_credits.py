"""Ready-review regression: real SDK transactions, synthetic inputs, zero calls."""
import uuid
import pytest
from deck_master import (changes, collaboration, collaboration_budget, content_review,
                         eligibility, review_evidence, service, tasks)
from test_content_preproduction_review import _deck, _instruction
from test_eligibility_enforcement import _declared, _grant
from test_rc3_budget_workflow import change_input, grant, project
from test_rc3_review_policy_workflow import choice, decide

def task_by_id(store, task_id):
    return tasks._lookup_task(store.load_document(), task_id, store)


def mixed_input(store):
    value = change_input(store, ids=('p1',))
    entry = store.load_document()['pages'][1]
    value['targets'].append({'page_id': 'p2', 'page_ref': entry['page'],
                            'layer': 'content', 'artifact_ref': entry['page']})
    return value


@pytest.mark.parametrize('other_grant', [False, True])
def test_fixed_mixed_edit_uses_only_paid_pages_for_credits(tmp_path, other_grant):
    path, store = project(tmp_path, intent='edit')
    plan = changes.plan(path, input=mixed_input(store))
    fixed = grant(path, store, template='edit_rebuild_per_page', change_plan_id=plan['plan_id'])
    other = _grant(path, store, actions=('change.commit', 'dispatch.blueprint'),
        max_external_calls=1, max_candidate_count=0) if other_grant else None
    plan = changes.plan(path, input=mixed_input(store))
    result = changes.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                            operation_id=str(uuid.uuid4()))['operation_result']
    actual = [task_by_id(store, identity) for identity in result['task_ids']]
    assert len(actual) == 2
    assert all(task['collaboration_binding']['authorization_ref'] == fixed['authorization_ref'] for task in actual)
    assert eligibility.authorization_budget(store, store.load_document(), fixed['authorization_ref'])['used'] == 1
    if other:
        assert eligibility.authorization_budget(store, store.load_document(), other['authorization_ref'])['used'] == 0


def test_zero_call_page_stays_in_scope_and_cannot_borrow_an_image_credit(tmp_path):
    path, store = project(tmp_path, intent='edit')
    plan = changes.plan(path, input=mixed_input(store))
    fixed = grant(path, store, template='edit_rebuild_per_page', change_plan_id=plan['plan_id'])
    doc = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        service.open_blueprint_task(store, doc, doc['pages'][1])
    assert 'budget_exhausted' in failure.value.decision['reason_codes']
    assert store.load_document() == doc
    request = doc['collaboration']['request']
    collaboration.start_request(path, input={'intent': 'edit',
        'scope': {**request['scope'], 'page_ids': ['p1']},
        'replace_request_id': request['request_id'], 'instruction_evidence': _declared(store)},
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    # A fresh in-scope image grant cannot authorize the content write on p2.
    _grant(path, store, actions=('change.commit', 'dispatch.blueprint'),
           scope={**request['scope'], 'page_ids': ['p1']}, max_external_calls=1,
           operation_id='narrow-image-grant')
    plan = changes.plan(path, input=mixed_input(store))
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        changes.commit(path, plan_id=plan['plan_id'], base_revision=before['revision_id'],
                       operation_id=str(uuid.uuid4()))
    assert 'scope_exceeded' in failure.value.decision['reason_codes']
    assert store.load_document() == before
    assert eligibility.authorization_budget(store, before, fixed['authorization_ref'])['used'] == 0

