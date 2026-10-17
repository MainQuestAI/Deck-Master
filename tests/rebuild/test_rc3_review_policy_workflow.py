"""Explicit user choices via the public API; synthetic prose/reviews, no provider."""
import copy
import uuid

import pytest

from deck_master import collaboration, collaboration_api, content_review, service
from deck_master.models import ModelError, bump_revision
from test_content_preproduction_review import _deck, _instruction, _review


def choice(store, requirement='host_self', **updates):
    doc = store.load_document()
    value = {
        'topic': 'policy', 'disposition': 'accepted', 'authority_mode': 'direct_user',
        'scope': {**doc['collaboration']['request']['scope'],
                  'page_ids': [entry['page_id'] for entry in doc['pages']],
                  'page_manifest_ref': None, 'layers': ['review']},
        'value': {'content_review_requirement': requirement,
                  'reason': 'Explicit synthetic user choice: self-review this fixed manuscript, retaining human delivery policy.'},
        'instruction_evidence': _instruction(store, 'explicit-review-policy'),
    }
    value.update(updates)
    return value


def decide(store, value):
    return collaboration.record_decision(store.project_root, input=value,
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))


@pytest.mark.parametrize('reviewer_type', ['host_self', 'independent_host'])
def test_normal_api_choice_unblocks_review_but_strict_requires_proven_independence(tmp_path, reviewer_type):
    project, store = _deck(tmp_path)
    before = store.load_document()
    missing = content_review.dispatch_preproduction_review(project)
    assert missing['status'] == 'needs_reviewer'
    payload = {'decision': choice(store), 'base_revision': store.current_revision_id(),
               'operation_id': str(uuid.uuid4())}
    response, http, code = collaboration_api.invoke(project, 'decision', payload)
    assert http == 200 and code == 0, response
    current = store.load_document()
    assert current['collaboration']['quality_profile']['override_decision_ref'] == response['result']['decision_ref']
    assert current['policy'] == before['policy']
    assert current['collaboration']['authorizations'] == before['collaboration']['authorizations']
    replay, http, code = collaboration_api.invoke(project, 'decision', payload)
    assert replay['result']['status'] == 'already_applied' and http == 200 and code == 0
    assert store.load_document() == current
    dispatched = content_review.dispatch_preproduction_review(project)
    assert dispatched['status'] == 'review_dispatched' and dispatched['requirement'] == 'host_self'
    task = dispatched['task']
    assert task['collaboration_binding']['executor_type'] == 'host'
    service.task_start(project, task_id=task['task_id'], execution_ref='synthetic-ordinary-host',
        supported_protocols=[task['protocol_version']], capabilities=task['required_capabilities'])
    document = store.load_document()
    reviews = [_review(store, document, kind, reviewer={
        'type': reviewer_type, 'id': 'synthetic-ordinary-host',
        'execution_ref': 'unverified-independent-name' if reviewer_type == 'independent_host' else None,
        'independence_confirmed': reviewer_type == 'independent_host',
        'identity_receipt': None, 'assurance': 'host_attested'})
        for kind in content_review.required_units(store, document)]
    accepted = service.accept_result(project,
        **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
        result_payload={'kind': 'review', 'files': [], 'reviews': reviews})
    assert accepted['status'] == 'accepted'
    assert content_review.qualify_for_production(store, store.load_document())['allowed']
    strict = decide(store, choice(store, 'independent_model_or_human'))
    assert strict['status'] == 'accepted'
    assert content_review.requirement_state(store, store.load_document())['effective'] == 'independent_model_or_human'
    assert content_review.dispatch_preproduction_review(project)['status'] == 'needs_reviewer'
    qualification = content_review.qualify_for_production(store, store.load_document())
    assert qualification['allowed'] is False
    assert qualification['requirement'] == 'independent_model_or_human'
    assert qualification['missing_units']


@pytest.mark.parametrize('bad', ['empty_reason', 'empty_pages', 'one_page', 'future_page', 'wrong_layer',
                                 'host_proposal', 'imported_unknown', 'unverified', 'fidelity_only'])
def test_policy_refusals_leave_current_profile_grants_and_manuscript_unchanged(tmp_path, bad):
    _, store = _deck(tmp_path)
    value = choice(store)
    if bad == 'empty_reason':
        value['value']['reason'] = '   '
    elif bad == 'empty_pages':
        value['scope']['page_ids'] = []
    elif bad == 'one_page':
        value['scope']['page_ids'] = ['p1']
    elif bad == 'future_page':
        value['scope']['page_ids'].append('not-yet-written')
    elif bad == 'wrong_layer':
        value['scope']['layers'] = ['page_copy']
    elif bad in ('host_proposal', 'imported_unknown'):
        value['authority_mode'] = bad
    elif bad == 'unverified':
        value['instruction_evidence']['kind'] = 'approved_document'
    else:
        value['value']['content_review_requirement'] = 'fidelity_only'
    before = store.load_document()
    with pytest.raises(ModelError):
        decide(store, value)
    assert store.load_document() == before


@pytest.mark.parametrize('disposition', ['rejected', 'deferred'])
def test_nonaccepted_policy_is_recorded_without_choosing_self_review(tmp_path, disposition):
    _, store = _deck(tmp_path)
    before = store.load_document()['collaboration']['quality_profile']
    decide(store, choice(store, disposition=disposition))
    assert store.load_document()['collaboration']['quality_profile'] == before


@pytest.mark.parametrize('replacement', ['unrelated', 'rejected', 'strict'])
def test_replacement_does_not_keep_an_old_self_review_override_alive(tmp_path, replacement):
    _, store = _deck(tmp_path)
    first = decide(store, choice(store))
    prior = store.load_document()
    record = store.read_object_json(first['decision_ref'])
    value = choice(store, decision_id=record['decision_id'], replaces=first['decision_ref'])
    if replacement == 'unrelated':
        value['value'] = {'reason': 'An unrelated working policy is not a self-review choice.'}
    elif replacement == 'rejected':
        value['disposition'] = 'rejected'
    else:
        value['value']['content_review_requirement'] = 'independent_model_or_human'
    decide(store, value)
    current = store.load_document()
    # Even an old persisted/restore profile pointer cannot revive the replaced decision.
    current['collaboration']['quality_profile'] = prior['collaboration']['quality_profile']
    assert content_review.requirement_state(store, current)['effective'] == 'independent_model_or_human'


@pytest.mark.parametrize('mutation', ['new_page', 'verified_policy', 'unrelated_value', 'unverified_source'])
def test_consumer_rechecks_scope_meaning_and_authority_of_stored_overrides(tmp_path, mutation):
    _, store = _deck(tmp_path)
    chosen = decide(store, choice(store))
    current = store.load_document()
    assert content_review.requirement_state(store, current)['effective'] == 'host_self'
    if mutation == 'new_page':
        current['pages'].append({**copy.deepcopy(current['pages'][0]), 'page_id': 'new-page'})
    elif mutation == 'verified_policy':
        current['collaboration']['authority_policy'] = 'verified_user'
    else:
        record = store.read_object_json(chosen['decision_ref'])
        if mutation == 'unrelated_value':
            record['value'] = {'reason': 'Unrelated policy, no explicit review choice.'}
        else:
            record['evidence']['assurance'] = 'unverified'
        ref = store.put_json_object(record)
        current['collaboration']['decisions'] = [ref if item == chosen['decision_ref'] else item
                                                  for item in current['collaboration']['decisions']]
        current['collaboration']['quality_profile']['override_decision_ref'] = ref
    assert content_review.requirement_state(store, current)['effective'] == 'independent_model_or_human'


def test_new_request_cannot_borrow_self_review_from_a_background_request(tmp_path):
    _, store = _deck(tmp_path)
    decide(store, choice(store))
    prior = store.load_document()['collaboration']['request']
    collaboration.start_request(store.project_root, input={
        'intent': prior['intent'], 'content_intent': prior['content_intent'], 'scope': prior['scope'],
        'instruction_evidence': _instruction(store, 'new-explicit-request'),
        'replace_request_id': prior['request_id'], 'background_request_ids': [prior['request_id']]},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert content_review.requirement_state(store, store.load_document())['effective'] == 'independent_model_or_human'


def test_explicit_policy_delegation_can_choose_review_but_execute_grant_cannot(tmp_path):
    _, store = _deck(tmp_path)
    scope = choice(store)['scope']
    grant = collaboration.grant(store.project_root, input={
        'mode': 'delegate', 'actions': ['review.record'], 'scope': scope, 'delegated_topics': ['policy'],
        'max_external_calls': 0, 'max_candidate_count': 0, 'adoption_policy': 'candidate_only',
        'instruction_evidence': _instruction(store, 'delegate-this-review-policy')},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    decide(store, choice(store, authority_mode='delegated', delegation_ref=grant['authorization_ref']))
    assert content_review.requirement_state(store, store.load_document())['effective'] == 'host_self'
    execution = collaboration.grant(store.project_root, input={
        'mode': 'execute', 'actions': ['review.record'], 'scope': scope,
        'max_external_calls': 0, 'max_candidate_count': 0, 'adoption_policy': 'candidate_only',
        'instruction_evidence': _instruction(store, 'execute-review-only')},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    before = store.load_document()
    with pytest.raises(ModelError):
        decide(store, choice(store, authority_mode='delegated', delegation_ref=execution['authorization_ref']))
    assert store.load_document() == before


def test_verified_user_policy_refuses_unverified_normal_transport_choice(tmp_path):
    _, store = _deck(tmp_path)
    doc = store.load_document()
    updated = bump_revision(doc, {'operation_id': 'strict-user-fixture', 'kind': 'collaboration_update',
                                 'description': 'Explicit verified-user policy fixture', 'read_set': []})
    updated['collaboration']['authority_policy'] = 'verified_user'
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='strict-user-fixture')
    before = store.load_document()
    response, http, _ = collaboration_api.invoke(store.project_root, 'decision', {
        'decision': choice(store), 'base_revision': store.current_revision_id(),
        'operation_id': str(uuid.uuid4())})
    assert http >= 400, response
    assert store.load_document() == before


def test_requirement_change_supersedes_pending_review_and_retains_call_facts(tmp_path):
    project, store = _deck(tmp_path)
    decide(store, choice(store))
    dispatched = content_review.dispatch_preproduction_review(project)
    task = dispatched['task']
    before = store.load_document()
    original = next(store.read_object_json(ref) for ref in before['tasks']
                    if store.read_object_json(ref)['task_id'] == task['task_id'])
    decide(store, choice(store, 'independent_model_or_human'))
    current = store.load_document()
    retired = next(store.read_object_json(ref) for ref in current['tasks']
                   if store.read_object_json(ref)['task_id'] == task['task_id'])
    assert retired['status'] == 'superseded'
    assert retired['call_allowances'] == original['call_allowances']
    assert current['pages'] == before['pages'] and current['policy'] == before['policy']


def test_strict_consumes_authenticated_external_import_after_provider_goes_offline(tmp_path):
    from deck_master import models, review_evidence, review_import
    from deck_master.store import Store
    from synthetic_review_provider import SyntheticProvider
    from test_rc3_collaboration_adapters import imported_project, external_packet_for_page

    project = imported_project(tmp_path)
    store = Store(project)
    decide(store, choice(store, 'independent_model_or_human'))
    external = external_packet_for_page(tmp_path, project)
    template = external['report']['reviews'][0]
    external['report']['reviews'] = []
    for kind in content_review.required_units(store, store.load_document()):
        review = copy.deepcopy(template)
        review.update(kind=kind, status='pass', review_id='L1-imported-' + kind)
        review['reviewer'].update(type='independent_host', execution_ref='L1-external-reviewer',
                                  independence_confirmed=True)
        external['report']['reviews'].append(review)
    external['report_sha256'] = models.sha256_bytes(models.canonical_json_bytes(external['report']))
    bindings = review_import.describe_bindings(project, external_report=external)['source_bindings']
    registry = review_evidence.ProviderRegistry()
    provider = SyntheticProvider()
    registry.register(provider)
    document = store.load_document()
    binding = review_evidence.external_review_binding(store, document, document, external, bindings)
    selector = provider.issue('L1-external-review', {**binding, 'executor_ref': 'L1-external-reviewer'},
                              'independent_review_receipts')
    with review_evidence.ProviderRuntime(registry).bound():
        context = registry.external_review_context(store, external_report=external,
            source_bindings=bindings, selector=selector)
        review_import.import_report(project, external_report=external, source_bindings=bindings,
            evidence=_instruction(store), base_revision=document['revision_id'],
            operation_id=str(uuid.uuid4()), adapter_context=context)
    provider.ready = False
    assert review_evidence.DEFAULT_REGISTRY.describe()['providers'] == []
    assert content_review.qualify_for_production(store, store.load_document())['allowed']
