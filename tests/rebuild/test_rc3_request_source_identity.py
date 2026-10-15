"""Historical source identity never mints a new request or refreshes credit."""
from copy import deepcopy
import uuid

from deck_master import collaboration, collaboration_budget, service
from deck_master.store import Store
from rc3_fixtures import authorize_scope, evidence_for


def _input(request):
    value = {key: deepcopy(request[key]) for key in
        ('intent', 'content_intent', 'scope', 'instruction_evidence', 'variant')}
    value['instruction_evidence'].pop('assurance', None)
    return value


def _start(project, store, value):
    return collaboration.start_request(project, input=value,
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))


def test_replaying_a_superseded_source_returns_its_original_identity_and_keeps_current_control(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='L1 original bounded source, one request identity')
    store = Store(project)
    first = deepcopy(store.load_document()['collaboration']['request'])
    evidence = evidence_for(project, text='L1 explicit one-call ceiling, not a call fact', locator='L1:source-identity-grant')
    authorize_scope(project, actions=['dispatch.host_task'], scope=first['scope'],
        max_external_calls=1, max_candidate_count=0, adoption_policy='within_scope', evidence=evidence)
    alternate = _input(first)
    alternate.update(intent='review_only', content_intent=None, replace_request_id=first['request_id'])
    alternate['scope']['layers'] = ['review']
    alternate['instruction_evidence'] = {'kind': 'host_attested_instruction',
        'text': 'L1 stop production and inspect only', 'source_locator': 'L1:alternate-source'}
    _start(project, store, alternate)
    middle = store.load_document()
    prior_keys = collaboration_budget.initial_per_page_plan(store, middle,
        request_id=first['request_id'], page_ids=['p1'])['credits']
    # No source-index/cache is consulted: only the original committed ancestry
    # and its embedded receipts remain when an operations cache is absent.
    cache = store.deck_root / 'operations'
    if cache.exists():
        for path in cache.iterdir():
            if path.is_file():
                path.unlink()
    retry = _input(first)
    retry['replace_request_id'] = middle['collaboration']['request']['request_id']
    response = _start(project, store, retry)
    after = store.load_document()
    assert response['status'] == 'already_started' and response['request_id'] == first['request_id']
    assert response['request_state'] == 'superseded'
    assert response['current_request_id'] == middle['collaboration']['request']['request_id']
    assert response['current_request'] == middle['collaboration']['request']
    assert response['creates_request'] is response['refreshes_credit'] is False
    for key in ('collaboration', 'tasks', 'pages', 'sources', 'outputs', 'content_basis'):
        assert after.get(key) == middle.get(key)
    assert collaboration_budget.initial_per_page_plan(store, after,
        request_id=response['request_id'], page_ids=['p1'])['credits'] == prior_keys
    assert all(not store.read_object_json(ref).get('call_allowances') for ref in after['tasks'])


def test_closed_same_source_stays_closed_but_new_explicit_instruction_at_same_locator_can_start(tmp_path):
    project = tmp_path / 'project'
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'L1 fixed completed manuscript', 'body_blocks': []},
        'visual_spec': {'intent': 'L1 fixed input', 'reference_mode': 'new_design'}}
    service.create(project, brief='L1 return fixed copy only', draft={'pages': [page]},
        request_input={'intent': 'content_only', 'content_intent': 'write_only'})
    store = Store(project)
    original = deepcopy(store.load_document()['collaboration']['request'])
    assert original['closed'] is True
    response = _start(project, store, _input(original))
    assert response['status'] == 'already_started' and response['request_state'] == 'closed'
    assert store.load_document()['collaboration']['request'] == original
    new = _input(original)
    new['instruction_evidence'] = {'kind': 'host_attested_instruction',
        'text': 'L1 a new explicit instruction, now revise this copy',
        'source_locator': original['instruction_evidence']['source_locator']}
    response = _start(project, store, new)
    assert response['status'] == 'accepted' and response['request_id'] != original['request_id']
    assert store.load_document()['collaboration']['request']['closed'] is False


def test_same_source_retry_does_not_resume_a_paused_request(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='L1 original request before pause')
    store = Store(project)
    original = deepcopy(store.load_document()['collaboration']['request'])
    collaboration.pause_request(project, reason='L1 explicit pause',
        instruction_evidence={'kind': 'host_attested_instruction', 'text': 'L1 pause current work'},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    paused = store.load_document()
    response = _start(project, store, _input(original))
    assert response['request_id'] == original['request_id'] and response['request_state'] == 'paused'
    assert store.load_document()['collaboration'] == paused['collaboration']
