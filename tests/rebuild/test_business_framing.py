"""D01: real version/Host/transaction boundaries; synthetic mechanism inputs."""
import copy

import pytest

from deck_master import collaboration, content_insight, content_production, dependency_slices, models, service
from deck_master.business_framing import CAPABILITY
from deck_master.store import Store
from test_content_contracts import _narrative, _plan, _plan_input


SCOPE = {'subject': 'deck', 'page_ids': [], 'page_manifest_ref': None, 'external_artifact_ref': None,
         'layers': ['narrative', 'plan'], 'allow_page_membership_change': False,
         'allow_page_order_change': False, 'purpose': 'working'}


def v2(project_id='proj', *, task=None, maturity='argument'):
    data = _narrative(project_id=project_id, schema_version='narrative.v2', maturity=maturity,
                      input_basis=(task or {}).get('collaboration_binding', {}).get('eligibility_basis', []))
    data['business_strategy'] = {'scenario': 'custom-business-job', 'author_goal': 'Explain the actual operating change',
        'established_node_ids': [], 'focus_node_ids': ['n1'], 'support_node_ids': [], 'omitted_node_ids': [],
        'rationale': 'Keep the operating responsibility and decision explicit'}
    data['business_frame'] = {'frame_id': 'f1', 'organizing_basis': 'business responsibility',
        'rationale': 'Work moves from the operator to the next responsible person',
        'topics': [{'topic_id': 'handoff', 'name': '交接', 'meaning': '说明交出什么以及谁接手',
                    'links': [{'node_id': 'n1', 'role': 'support'}], 'placement': 'main', 'gap_issue_ids': []}],
        'relations': []}
    data['method_applications'] = []
    if maturity == 'framing':
        data.update(nodes=[], edges=[], central_node_id=None, business_frame=None)
        data['business_strategy']['focus_node_ids'] = []
    return data


def project(tmp_path, **over):
    source = tmp_path / 'source.md'
    source.write_text('Synthetic contract input: preserve unknown device versions and the expert handoff.\n')
    path = tmp_path / 'project'
    service.create(path, brief='Explain how people use the proposed service', sources=[source],
        scenario='first_proposal', audience='Business owners', existing_decisions=['Keep the current ticketing system'],
        request_input={'intent': 'content_only', 'content_intent': 'plan_only', 'scope': SCOPE}, **over)
    return path, Store(path)


def pending(store):
    return next(t for ref in store.load_document()['tasks']
                if (t := store.read_object_json(ref))['status'] == 'awaiting_host')


def submit(path, store, task, narrative, *, attach_plan=False):
    service.task_start(path, task_id=task['task_id'], execution_ref='synthetic-business-writer',
                       supported_protocols=['compose.v2'], capabilities=task['required_capabilities'])
    payload = {'narrative': narrative}
    if attach_plan:
        data = _plan_input()
        data['page_order'] = ['p1']
        data['chapters'][0]['page_ids'] = ['p1']
        data['page_roles'][0].update(source_links=[], required_qualifications=[])
        payload['plan'] = _plan(project_id=store.load_document()['project_id'], task_id=task['task_id'],
            narrative_ref=None, basis={'revision_id': task['dispatch_revision'], 'input_digest': task['input_digest']},
            input=data)
    result = {'schema_version': 'compose_result.v2', 'kind': 'compose',
        'variant': 'framing' if narrative['maturity'] == 'framing' else 'narrative',
        'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'], 'payload': payload, 'usage_events': []}
    return service.accept_result(path, task_id=task['task_id'], operation_id=task['operation_id'],
                                 produced_against=task['produced_against'], result_payload=result)


def proposals(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    submit(path, store, task, v2(store.load_document()['project_id'], task=task, maturity='framing'))
    service.continue_project(path)
    task = pending(store)
    submit(path, store, task, v2(store.load_document()['project_id'], task=task), attach_plan=True)
    doc = store.load_document()
    return path, store, content_production.completion_status(store, doc)['outputs']


def evidence(store):
    return {'kind': 'host_attested_instruction', 'source_ref': store.put_json_object({'synthetic_instruction': True}),
            'source_locator': 'unit-test:explicit-author-instruction'}


def adoption_request(path, store, refs):
    old_request = copy.deepcopy(store.load_document()['collaboration']['request'])
    collaboration.start_request(path, input={'intent': 'content_only', 'content_intent': 'plan_only',
        'scope': {**SCOPE, 'layers': ['narrative', 'plan', 'review']}, 'instruction_evidence': evidence(store)},
        base_revision=store.current_revision_id(), operation_id='adopt-existing-plan')
    result = collaboration.record_decision(path, input={'topic': 'direction', 'disposition': 'accepted',
        'value': 'Use these exact planning objects', 'authority_mode': 'direct_user', 'scope': SCOPE,
        'subject_refs': [{'artifact_kind': 'narrative' if index == 0 else 'content_plan',
                          'artifact_ref': ref, 'projection': 'direction' if index == 0 else 'page_roles'}
                         for index, ref in enumerate(refs)], 'instruction_evidence': evidence(store)},
        base_revision=store.current_revision_id(), operation_id='author-direction')
    return old_request, result['decision_ref']


def test_v1_is_strict_and_reads_without_manufacturing_strategy():
    old = _narrative()
    models.validate_narrative_semantics(old)
    assert 'business_strategy' not in old
    with pytest.raises(models.ModelError):
        models.validate_narrative_semantics({**old, 'business_strategy': v2()['business_strategy']})
    models.validate_narrative_semantics(v2())


@pytest.mark.parametrize('mutation', ['unknown-node', 'unknown-topic', 'missing-frame', 'fake-result-pointer', 'conflicting-placement'])
def test_v2_rejects_unexpandable_references_and_conflicting_placements(mutation):
    value = v2()
    if mutation == 'unknown-node': value['business_frame']['topics'][0]['links'][0]['node_id'] = 'missing'
    if mutation == 'unknown-topic': value['business_frame']['relations'] = [{'from_topic_id': 'missing', 'to_topic_id': 'handoff', 'relation': 'next'}]
    if mutation == 'missing-frame': value['business_frame'] = None
    if mutation == 'fake-result-pointer': value['method_applications'] = [{'task_id': 't', 'method_id': 'm', 'sha256': 'a'*64, 'result_pointer': '/nodes/9'}]
    if mutation == 'conflicting-placement': value['business_strategy']['omitted_node_ids'] = ['n1']
    with pytest.raises(models.ModelError): models.validate_narrative_semantics(value)


def test_opt_in_freezes_host_contract_and_raises_floor_only_on_write(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    assert CAPABILITY in task['required_capabilities']
    assert store.load_document()['compatibility']['minimum_writer'] == CAPABILITY
    before = store.current_revision_id()
    from deck_master.generation import GenerationError
    with pytest.raises(GenerationError, match='requires compose.v2'):
        service.task_start(path, task_id=task['task_id'], execution_ref='old-host',
            supported_protocols=['compose.v2'], capabilities=['compose.v2', 'collaboration.v1', 'rc3-entry.v1'])
    assert store.current_revision_id() == before
    old = _narrative(project_id=store.load_document()['project_id'], maturity='framing')
    with pytest.raises(models.ModelError, match='frozen business-framing'):
        submit(path, store, task, old)
    assert not store.read_object_json(store.load_document()['tasks'][-1]).get('result_refs')


def test_legacy_reads_do_not_raise_floor_and_old_tasks_cannot_take_v2(tmp_path):
    path, store = project(tmp_path)
    before = store.read_current()
    assert not content_insight.arguments(path)['data']['items']
    assert store.read_current() == before and before['minimum_writer'] != CAPABILITY
    task = pending(store)
    with pytest.raises(models.ModelError, match='frozen business-framing'):
        submit(path, store, task, v2(store.load_document()['project_id'], task=task, maturity='framing'))
    assert store.read_current()['minimum_writer'] != CAPABILITY


def test_zero_page_v2_proposals_are_readable_then_adopt_in_existing_bounded_request(tmp_path):
    path, store, refs = proposals(tmp_path)
    doc = store.load_document()
    assert doc['collaboration']['request']['closed'] and not doc['pages'] and doc.get('narrative') is None
    value = content_insight.argument(path, refs[0]['sha256'])
    assert value['data']['narrative']['business_frame']['topics'][0]['name'] == '交接'
    assert value['data']['plans'][0]['data']['plan']['narrative_ref'] == refs[0]
    old_request, decision = adoption_request(path, store, refs)
    for index, ref in enumerate(refs):
        content_production.adopt_proposal(path, input={'proposal_ref': ref, 'decision_ref': decision, 'write_scope': SCOPE},
            base_revision=store.current_revision_id(), operation_id=f'adopt-{index}')
    now = store.load_document()
    assert now['narrative'] == refs[0] and now['content_plan'] == refs[1] and now['pages'] == []
    assert store.read_object_json(now['content_plan'])['narrative_ref'] == now['narrative']
    from deck_master.outline_review import packet
    assert packet(store, now)['narrative']['schema_version'] == 'narrative.v2'
    assert old_request['closed'] and old_request['request_id'] != now['collaboration']['request']['request_id']


@pytest.mark.parametrize('field,value', [('scenario', 'competitive_bid'), ('existing_decisions', ['New author agreement'])])
def test_changed_business_fact_stales_tasks_decisions_and_second_adoption(tmp_path, field, value):
    path, store, refs = proposals(tmp_path)
    _, decision = adoption_request(path, store, refs)
    content_production.adopt_proposal(path, input={'proposal_ref': refs[0], 'decision_ref': decision, 'write_scope': SCOPE},
        base_revision=store.current_revision_id(), operation_id='adopt-narrative')
    old = store.load_document()
    binding = dependency_slices.required_basis('task', 'argument')
    assert ('task_fact', field, 'value') in binding
    service.inputs_update(path, patch={'task_patch': {field: value}, 'reason': 'Actual author strategy changed'},
        base_revision=store.current_revision_id(), operation_id='strategy-change')
    changed = store.load_document()
    revision_task = pending(store)
    assert CAPABILITY in revision_task['required_capabilities']
    assert {dep['identity'] for dep in revision_task['collaboration_binding']['eligibility_basis']
            if dep['kind'] == 'task_fact'} >= {'brief', 'audience', 'scenario', 'existing_decisions'}
    assert not dependency_slices.decision_effectiveness(store, changed, decision)['effective']
    with pytest.raises(models.ModelError):
        content_production.adopt_proposal(path, input={'proposal_ref': refs[1], 'decision_ref': decision, 'write_scope': SCOPE},
            base_revision=store.current_revision_id(), operation_id='stale-plan')
    assert store.load_document()['narrative'] == old['narrative'] and store.load_document().get('content_plan') is None


def test_application_must_name_actual_frozen_method_and_result(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store);data = v2(store.load_document()['project_id'], task=task, maturity='framing')
    data['method_applications'] = [{'task_id': task['task_id'], 'method_id': 'fabricated-method',
        'sha256': 'a'*64, 'result_pointer': '/business_strategy/author_goal'}]
    with pytest.raises(models.ModelError, match='frozen Task method/hash'):submit(path, store, task, data)


@pytest.mark.parametrize('intent,content_intent', [('content_only', 'write_only'), ('content_only', 'speech_only'),
                                                ('design_trial', None), ('review_only', None), ('edit', None)])
def test_bounded_work_cannot_opt_into_replanning(tmp_path, intent, content_intent):
    target = tmp_path / 'bounded'
    with pytest.raises(service.ServiceError, match='not a confirmed or bounded manuscript'):
        service.create(target, brief='Keep the author scope', business_framing=True,
            request_input={'intent': intent, 'content_intent': content_intent, 'scope': SCOPE})
    assert not target.exists()


def test_cancelled_v2_keeps_content_while_recording_late_result(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    service.task_start(path, task_id=task['task_id'], execution_ref='cancelled-v2-host',
        supported_protocols=['compose.v2'], capabilities=task['required_capabilities'])
    service.task_cancel(path, task_id=task['task_id'], reason='synthetic author cancelled before result')
    before = store.load_document()
    from deck_master.tasks import TaskConflict
    with pytest.raises(TaskConflict):
        service.accept_result(path, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], result_payload={'schema_version': 'compose_result.v2',
                'kind': 'compose', 'variant': 'framing', 'task_id': task['task_id'], 'operation_id': task['operation_id'],
                'produced_against': task['produced_against'],
                'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
                'payload': {'narrative': v2(store.load_document()['project_id'], task=task, maturity='framing')},
                'usage_events': []})
    after = store.load_document()
    assert after.get('narrative') == before.get('narrative') and after.get('content_plan') == before.get('content_plan')
    assert after['pages'] == before['pages']
    assert store.read_object_json(after['tasks'][-1])['status'] == 'cancelled'
    assert not content_insight.arguments(path)['data']['items']


def test_older_core_refuses_new_pointer_before_any_write(tmp_path, monkeypatch):
    from deck_master import store as store_module
    path, store = project(tmp_path, business_framing=True)
    before = (path / '.deckmaster/current.json').read_bytes()
    monkeypatch.setattr(store_module, 'SUPPORTED_WRITERS', tuple(x for x in store_module.SUPPORTED_WRITERS if x != CAPABILITY))
    with pytest.raises(store_module.StoreError, match='writer'):
        store.load_document()
    assert (path / '.deckmaster/current.json').read_bytes() == before
