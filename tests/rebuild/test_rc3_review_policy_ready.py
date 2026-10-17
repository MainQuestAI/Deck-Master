"""Ready-review regression: real SDK transactions, synthetic inputs, zero calls."""
import uuid
import pytest
from deck_master import (changes, collaboration, collaboration_budget, content_review,
                         eligibility, review_evidence, service, tasks)
from test_content_preproduction_review import _deck, _instruction
from test_eligibility_enforcement import _declared, _grant
from test_rc3_budget_workflow import change_input, grant, project
from test_rc3_review_policy_workflow import choice, decide

class CapabilityOnly:
    provider_id = 'synthetic-capability-only'
    adapter_version = 'synthetic-no-completion.v1'
    authentication = 'protected_transport'
    channels = ('independent_review_receipts',)

    def health(self):
        return True

    def fetch(self, event_id):
        raise AssertionError('No model completion in this test')

    def verify(self, raw):
        raise AssertionError('No model completion in this test')


def task_by_id(store, task_id):
    return tasks._lookup_task(store.load_document(), task_id, store)


@pytest.mark.parametrize('running', [False, True])
def test_effective_review_change_retires_old_executor_and_preserves_claims(tmp_path, running):
    path, store = _deck(tmp_path)
    decide(store, choice(store))
    old = store.load_document()['collaboration']['request']
    collaboration.start_request(path, input={
        'intent': old['intent'], 'content_intent': old['content_intent'], 'scope': old['scope'],
        'replace_request_id': old['request_id'],
        'instruction_evidence': _instruction(store, 'replace-policy-request')},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert content_review.requirement_state(store, store.load_document())['effective'] == 'independent_model_or_human'
    registry = review_evidence.ProviderRegistry()
    registry.register(CapabilityOnly())
    with review_evidence.ProviderRuntime(registry).bound():
        old_task = content_review.dispatch_preproduction_review(path)['task']
    if running:
        service.task_start(path, task_id=old_task['task_id'], execution_ref='synthetic-independent',
            supported_protocols=[old_task['protocol_version']], capabilities=old_task['required_capabilities'])
    original = task_by_id(store, old_task['task_id'])
    pages = store.load_document()['pages']
    decide(store, choice(store))
    retired = task_by_id(store, old_task['task_id'])
    assert retired['status'] == 'superseded'
    assert {k: v for k, v in retired.items() if k not in ('status', 'updated_at')} == {
        k: v for k, v in original.items() if k not in ('status', 'updated_at')}
    new = content_review.dispatch_preproduction_review(path)['task']
    assert new['task_id'] != old_task['task_id']
    assert new['collaboration_binding']['executor_type'] == 'host'
    service.task_start(path, task_id=new['task_id'], execution_ref='synthetic-self-host',
        supported_protocols=[new['protocol_version']], capabilities=new['required_capabilities'])
    # Replacing the same effective choice must not retire the legitimate claim.
    selected = store.load_document()['collaboration']['quality_profile']['override_decision_ref']
    record = store.read_object_json(selected)
    decide(store, choice(store, decision_id=record['decision_id'], replaces=selected))
    assert task_by_id(store, new['task_id'])['status'] == 'running'
    assert content_review.dispatch_preproduction_review(path)['task']['task_id'] == new['task_id']
    assert store.load_document()['pages'] == pages

