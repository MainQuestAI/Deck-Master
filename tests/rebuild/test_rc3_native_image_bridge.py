"""Synthetic L1 trusted-controller protocol tests, never actual image-tool evidence."""
import copy
import io
import time

import pytest
from PIL import Image

from deck_master import generation, tasks
from deck_master.models import canonical_json_bytes, sha256_bytes
from deck_master.native_image_evidence import (NativeImageCompletion, NativeImageRegistry,
    NativeImageRuntime, NativeObservationRejected, image_binding)
from test_generation_protocol import flow, start, freeze, begin, accept  # noqa: F401


class SyntheticController:
    provider_id = 'synthetic-l1-controller'
    adapter_version = 'synthetic-l1.v1'
    authentication = 'protected_transport'

    def __init__(self, binding, attempt):
        image = io.BytesIO()
        Image.new('RGB', (16, 12), '#526478').save(image, 'PNG')
        self.png = image.getvalue()
        now = time.time_ns() // 1_000_000
        self.claims = {'provider_id': self.provider_id, 'event_id': 'synthetic-event',
            'binding': binding, 'tool_name': 'image_gen__imagegen', 'status': 'completed',
            'issued_at_ms': now, 'expires_at_ms': now + 60000,
            'started_at_ms': attempt['started_at_ms'], 'completed_at_ms': now,
            'arguments': {'prompt': binding['prompt'], 'transparent_background': False},
            'output_sha256': sha256_bytes(self.png), 'invocation_ref': None}
        self.healthy = True

    def health(self):
        return self.healthy

    def fetch(self, event_id):
        return canonical_json_bytes(self.claims)

    def verify(self, raw):
        assert raw == canonical_json_bytes(self.claims)
        return NativeImageCompletion(copy.deepcopy(self.claims), self.png)


def prepared(flow):
    _, store, task, _ = flow
    start(flow)
    frozen = freeze(flow)
    attempt = begin(flow, frozen)
    binding, _, actual, _ = image_binding(store, store.load_document(), task['task_id'], attempt['attempt_id'])
    provider = SyntheticController(binding, actual)
    registry = NativeImageRegistry(); registry.register(provider)
    return frozen, attempt, provider, registry


def settle_native(flow, attempt, context=None, **report_fields):
    _, store, task, _ = flow
    report = {'source': 'native_host_image.v1', 'provider_id': 'synthetic-l1-controller',
              'event_id': 'synthetic-event', **report_fields}
    return tasks.call_settle(store, task_id=task['task_id'], allowance_id=attempt['allowance_id'],
        attempt_id=attempt['attempt_id'], outcome='consumed',
        report_bytes=canonical_json_bytes(report), adapter_context=context)


def issue(flow, attempt, registry):
    _, store, task, _ = flow
    return registry.image_context(store, store.load_document(), task_id=task['task_id'],
        attempt_id=attempt['attempt_id'], selector={'provider_id': 'synthetic-l1-controller', 'event_id': 'synthetic-event'})


def test_trusted_native_controller_keeps_exact_install_and_original_bytes(flow):
    frozen, attempt, provider, registry = prepared(flow)
    binding = provider.claims['binding']
    assert binding['execution_identity']['python_executable']
    assert set(binding['execution_identity']['runtime_sha256']) == {'generation.py','observations.py','native_image_evidence.py','production.py','tasks.py'}
    with NativeImageRuntime(registry).bound():
        context = issue(flow, attempt, registry)
        result = settle_native(flow, attempt, context)
    assert result['native_observation_status'] == 'accepted'
    shown = generation.show(flow[0], attempt_id=attempt['attempt_id'])
    assert shown['call']['state'] == 'consumed'
    observation = shown['observations'][-1]
    assert observation['source']['fee'] == 'not_reported'
    assert observation['source']['platform_invocation_ref'] is None
    proof = flow[1].read_object_json(observation['source']['receipt_ref'])
    assert proof['claims']['binding'] == binding
    assert flow[1].read_object_bytes(shown['attempt']['output_refs'][0]) == provider.png
    assert accept(flow, frozen, attempt, provider.png)['status'] == 'accepted'


@pytest.mark.parametrize('context_kind', ['missing','json','foreign','expired','unhealthy','health_exception','malformed_report'])
def test_proof_rejection_commits_consumed_unknown_fee_and_blocks_adoption(flow, context_kind):
    frozen, attempt, provider, registry = prepared(flow)
    with NativeImageRuntime(registry).bound():
        context = issue(flow, attempt, registry)
        if context_kind == 'missing': context = None
        if context_kind == 'json': context = {'assurance': 'native', 'binding': provider.claims['binding']}
        if context_kind == 'expired':
            from deck_master.native_image_evidence import _CONTEXTS
            data = _CONTEXTS[context]; _CONTEXTS[context] = (*data[:-1], 0)
        if context_kind == 'unhealthy': provider.healthy = False
        if context_kind == 'health_exception': provider.health = lambda: (_ for _ in ()).throw(RuntimeError('down'))
        if context_kind == 'foreign':
            with NativeImageRuntime(NativeImageRegistry()).bound():
                result = settle_native(flow, attempt, context)
        else:
            result = settle_native(flow, attempt, context, **({'claimed_fee': 0} if context_kind == 'malformed_report' else {}))
    assert result['native_observation_status'] == 'rejected'
    shown = generation.show(flow[0], attempt_id=attempt['attempt_id'])
    assert shown['call']['state'] == 'consumed'
    assert shown['observations'][-1]['observer'] == 'host_reported'
    assert shown['observations'][-1]['reported']['native_observation_rejected']
    assert not shown['attempt']['output_refs']
    with pytest.raises(generation.GenerationError):
        accept(flow, frozen, attempt, provider.png)


@pytest.mark.parametrize('field', ['prompt','parameters','execution_identity','settlement_reader_identity','references','control_sha256'])
def test_authenticated_event_still_requires_exact_frozen_binding(flow, field):
    _, attempt, provider, registry = prepared(flow)
    provider.claims['binding'][field] = 'different'
    with NativeImageRuntime(registry).bound():
        with pytest.raises(NativeObservationRejected, match='exact Task'):
            issue(flow, attempt, registry)
        result = settle_native(flow, attempt)
    assert result['native_observation_status'] == 'rejected'
    assert generation.show(flow[0], attempt_id=attempt['attempt_id'])['call']['state'] == 'consumed'


def test_actual_arguments_must_match_explicit_parameters_and_prompt(flow):
    _, attempt, provider, registry = prepared(flow)
    provider.claims['arguments']['prompt'] += ' unauthorized'
    with NativeImageRuntime(registry).bound():
        with pytest.raises(NativeObservationRejected, match='fully match'):
            issue(flow, attempt, registry)
        assert settle_native(flow, attempt)['native_observation_status'] == 'rejected'


@pytest.mark.parametrize('change', ['pause','revoke','replace_scope','replace_target'])
@pytest.mark.parametrize('outcome', ['consumed','unknown'])
def test_formal_control_change_after_begin_retains_call_facts_and_refuses_late_result(tmp_path, change, outcome):
    from deck_master import collaboration, service, eligibility
    from deck_master.models import bump_revision
    from test_rc3_notes_visual_inputs import enf, _seed_imported_plan
    project, store = enf._project(tmp_path)
    _seed_imported_plan(store)
    enf._start(project, store)
    enf._settle_preproduction(store, seed='g12-controlled-l1')
    grant = enf._grant(project, store, actions=('dispatch.blueprint','allowance.allocate','task.start','call.begin','result.accept'))
    document = store.load_document()
    task = service.open_blueprint_task(store, document, document['pages'][0])
    service.task_start(project, task_id=task['task_id'], execution_ref='synthetic-control-execution',
                       supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    value = generation.prepared_input(store, store.load_document(), task)
    frozen = generation.freeze(project, task_id=task['task_id'], input=value,
                               base_revision=store.current_revision_id(), operation_id='g12-freeze')
    attempt = tasks.call_begin(store, task_id=task['task_id'], allowance_id='call-1',
        execution_ref='synthetic-control-execution', request_id=frozen['request_id'])
    binding, _, actual, _ = image_binding(store, store.load_document(), task['task_id'], attempt['attempt_id'])
    provider = SyntheticController(binding, actual)
    registry = NativeImageRegistry(); registry.register(provider)
    controlled = (project,store,task,None)
    with NativeImageRuntime(registry).bound():
        context = issue(controlled, attempt, registry)
        doc = store.load_document()
        if change == 'pause':
            collaboration.pause_request(project, reason='Synthetic pause after actual begin', base_revision=doc['revision_id'], operation_id='g12-pause')
        elif change == 'revoke':
            collaboration.revoke_authorization(project, authorization_id=grant['authorization_id'], reason='Synthetic revoke after begin', base_revision=doc['revision_id'], operation_id='g12-revoke')
        elif change == 'replace_scope':
            enf._start(project,store,operation_id='g12-replace',replace_request_id=doc['collaboration']['request']['request_id'],scope=enf._scope(page_ids=['p2']))
        else:
            changed = bump_revision(copy.deepcopy(doc), {'operation_id':'g12-target','kind':'content_update','description':'Synthetic actual target replacement','read_set':[]})
            page = store.read_object_json(changed['pages'][0]['page']); page['customer_visible']['title'] += ' changed'
            changed['pages'][0]['page'] = store.put_json_object(page)
            store.commit_change(base_revision=doc['revision_id'],document=changed,operation_id='g12-target')
        report = {'source':'native_host_image.v1','provider_id':provider.provider_id,'event_id':'synthetic-event'}
        settled = tasks.call_settle(store,task_id=task['task_id'],allowance_id='call-1',attempt_id=attempt['attempt_id'],outcome=outcome,report_bytes=canonical_json_bytes(report),adapter_context=context)
    assert settled['native_observation_status'] == 'rejected'
    shown = generation.show(project,attempt_id=attempt['attempt_id'])
    assert shown['call']['state'] == outcome
    assert shown['observations'][-1]['observer'] == 'host_reported'
    assert shown['observations'][-1]['reported']['unusable_receipt_ref']
    with pytest.raises((eligibility.EligibilityBlocked,tasks.TaskConflict,generation.GenerationError)):
        accept(controlled,frozen,attempt,provider.png)
    assert generation.show(project,attempt_id=attempt['attempt_id'])['call']['state'] == outcome


def test_exact_native_settlement_replay_uses_immutable_begun_attempt(flow):
    _,attempt,_,registry=prepared(flow)
    with NativeImageRuntime(registry).bound():
        context=issue(flow,attempt,registry)
        first=settle_native(flow,attempt,context)
        revision=flow[1].current_revision_id()
        second=settle_native(flow,attempt,context)
    assert first['attempt_ref']==second['attempt_ref']
    assert second['status']=='already_settled'
    assert flow[1].current_revision_id()==revision
    assert len(generation.show(flow[0],attempt_id=attempt['attempt_id'])['observations'])==1
