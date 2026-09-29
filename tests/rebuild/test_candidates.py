"""Synthetic mechanism proof; no model or professional review claim."""
import copy
import uuid

import pytest

from deck_master import candidates, changes, generation, service, tasks
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from deck_master.samples import create_sample
from deck_master.store import Store


@pytest.fixture
def store(tmp_path):
    project = tmp_path / 'candidate-project'
    create_sample(project, page_count=2, readonly=False)
    return Store(project)


def dispatch(store, page='p01', *, mode='trial', layer='svg', references=None):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == page)
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'Improve the spacing.',
             'annotation_refs': [], 'max_calls': int(layer == 'original_image'), 'mode': mode,
             'targets': [{'page_id': page, 'page_ref': entry['page'], 'layer': layer,
                          'artifact_ref': entry['blueprint'] if layer == 'original_image' else entry.get('svg')}]}
    if references is not None:
        value['references'] = references
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    return tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)


def start(store, task, candidate_support=True):
    capabilities = ['change_plan', 'generation_request_freeze', 'attempt_binding', 'native_tool_observation']
    if candidate_support:
        capabilities.append('candidate_result')
    return service.task_start(store.project_root, task_id=task['task_id'], execution_ref='synthetic-test-host',
                              supported_protocols=['changes.v1', 'generation.v1'], capabilities=capabilities)


def envelope(store, task, width=20):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == task['scope_pages'][0])
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    staging = store.staging_dir / task['operation_id']; staging.mkdir(parents=True, exist_ok=True)
    (staging / 'page.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}"><rect width="{width}" height="20" fill="#000000"/></svg>')
    return {'kind': task['kind'], 'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
            'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': entry['page_id'],
                                'provenance': {'source_type': 'unknown', 'tool': 'synthetic-test', 'invocation_ref': None}}]}


def accept(store, task, payload=None):
    return service.accept_result(store.project_root, **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
                                  result_payload=payload or envelope(store, task))


def candidate(store, page='p01', width=20):
    task = dispatch(store, page); start(store, task)
    result = accept(store, task, envelope(store, task, width))
    return result['candidate_ids'][0]


def plan(store, ids):
    doc = store.load_document()
    return candidates.plan(store.project_root, input={'schema_version': 'candidate_selection.v1', 'project_id': doc['project_id'],
                                                      'base_revision': doc['revision_id'], 'candidate_ids': ids})['plan']


def adopt(store, value, op=None):
    return candidates.adopt(store.project_root, input=value, base_revision=value['base_revision'], operation_id=op or str(uuid.uuid4()))


def test_trial_no_current_writes_and_atomic_idempotent_adoption(store):
    before = store.load_document(); task = dispatch(store); start(store, task)
    result = accept(store, task); cid = result['candidate_ids'][0]
    after = store.load_document()
    assert result['status'] == 'candidate_ready' and result['current_artifacts_changed'] is False
    assert before['pages'] == after['pages'] and before['outputs'] == after['outputs']
    assert after['compatibility']['minimum_writer'] == 'candidates.v1'
    replay = accept(store, task)
    assert replay['status'] == 'already_applied' and replay['operation_result']['candidate_ids'] == [cid]
    assert len(candidates.listing(store.project_root)['candidates']) == 1
    value = plan(store, [cid]); op = str(uuid.uuid4()); applied = adopt(store, value, op)
    adopted = store.load_document()
    assert adopted['pages'][0]['svg'] == value['selections'][0]['result_ref']
    assert adopted['pages'][0]['blueprint'] == before['pages'][0]['blueprint']
    assert adopted['pages'][1] == before['pages'][1]
    assert adopt(store, value, op)['operation_result'] == applied['operation_result']


def test_auto_and_trial_coexist_return_in_reverse_order(store):
    trial = dispatch(store); auto = dispatch(store, mode='auto')
    assert service._pending_host_tasks(store.load_document(), store, include_trials=False)[0]['task_id'] == auto['task_id']
    start(store, trial); start(store, auto)
    accept(store, auto, envelope(store, auto, 40)); current = copy.deepcopy(store.load_document()['pages'])
    cid = accept(store, trial)['candidate_ids'][0]
    assert store.load_document()['pages'] == current
    detail = candidates.show(store.project_root, candidate_id=cid)
    assert detail['generation_basis']['status'] == 'current'
    assert detail['adoption_target']['status'] == 'changed'
    assert not service._pending_host_tasks(store.load_document(), store, include_trials=False)


def test_project_cas_differs_from_content_basis_and_batch_conflict_is_all_or_none(store):
    first = candidate(store); second = candidate(store, 'p02'); old_plan = plan(store, [first, second])
    # Unrelated management revision requires a new plan, no new generation.
    unused_trial = dispatch(store, 'p02'); now = copy.deepcopy(store.load_document()['pages'])
    with pytest.raises(OperationError): adopt(store, old_plan)
    assert store.load_document()['pages'] == now
    new_plan = plan(store, [first, second]); assert new_plan['max_calls'] == 0
    doc = store.load_document(); updated = copy.deepcopy(doc)
    page = store.read_object_json(updated['pages'][1]['page']); page['customer_visible']['title'] += ' changed'
    updated['pages'][1]['page'] = store.put_json_object(page)
    updated = bump_revision(updated, {'operation_id': 'test-change', 'kind': 'task_update', 'description': 'synthetic concurrent content change', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='test-change')
    before = store.read_current()
    with pytest.raises(candidates.AdoptionConflict) as error: plan(store, [first, second])
    assert error.value.payload()['error']['items'][0]['candidate_id'] == second
    assert store.read_current() == before
    adopt(store, plan(store, [first]))
    assert store.load_document()['pages'][1] == updated['pages'][1]


def test_cancelled_trial_repeat_never_claims_adopted(store):
    task = dispatch(store); start(store, task); payload = envelope(store, task)
    service.task_cancel(store.project_root, task_id=task['task_id'], reason='synthetic cancellation')
    before = copy.deepcopy(store.load_document()['pages'])
    for _ in range(2):
        with pytest.raises(tasks.TaskConflict): accept(store, task, payload)
    assert store.load_document()['pages'] == before
    assert candidates.listing(store.project_root)['candidates'] == []


def test_old_host_cannot_claim_trial(store):
    task = dispatch(store)
    with pytest.raises(generation.GenerationError, match='capabilities'): start(store, task, candidate_support=False)
    assert tasks._lookup_task(store.load_document(), task['task_id'], store)['status'] == 'awaiting_host'


def test_fixed_historical_reference_and_short_instruction_cannot_drift(store):
    doc = store.load_document(); entry = doc['pages'][1]
    refs = [{'page_id': entry['page_id'], 'revision_id': doc['revision_id'], 'artifact_ref': entry['blueprint'], 'role': 'reference'}]
    # A later reference-page result must not replace the selected historical file.
    from PIL import Image
    from io import BytesIO
    output = BytesIO(); Image.new('RGB', (40, 30), '#224466').save(output, 'PNG')
    artifact = store.read_object_json(entry['blueprint']); artifact['file'] = store.put_blob(output.getvalue(), ext='png')
    updated = copy.deepcopy(doc); updated['pages'][1]['blueprint'] = store.put_json_object(artifact)
    updated = bump_revision(updated, {'operation_id': 'test-reference-replaced', 'kind': 'task_update',
                                      'description': 'synthetic concurrent reference replacement', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='test-reference-replaced')
    task = dispatch(store, layer='original_image', references=refs); start(store, task)
    current = store.load_document(); prepared = generation.prepared_input(store, current, task)
    assert prepared['references'][0]['file'] == store.read_object_json(entry['blueprint'])['file']
    assert prepared['prompt'].startswith('Improve the spacing.')
    for key, value in [('references', []), ('prompt', 'different')]:
        changed = copy.deepcopy(prepared); changed[key] = value
        with pytest.raises(generation.GenerationError): generation._validate_input(store, current, task, changed)
    generation._validate_input(store, current, task, prepared)


def test_continue_dispatches_normal_work_while_trial_waits(store):
    trial = dispatch(store)
    result = service.continue_project(store.project_root)
    assert result['next_action'] == 'codex_reconstruct_svg'
    assert result['pending_tasks'][0]['task_id'] != trial['task_id']
    assert len(service._pending_host_tasks(store.load_document(), store)) == 2


def test_assembly_refuses_missing_dependencies_and_unreviewed_svg(store, monkeypatch):
    from deck_master import pipeline, stages
    calls = []
    monkeypatch.setattr(pipeline, 'executable', lambda tool: calls.append(tool))
    before = store.read_current()
    with pytest.raises(OperationError) as error:
        stages.assemble(store.project_root, base_revision=before['revision_id'], operation_id=str(uuid.uuid4()))
    assert error.value.error_code == 'stage_prerequisite_missing'
    assert store.read_current() == before and calls == []
    cid = candidate(store); adopt(store, plan(store, [cid]))
    with pytest.raises(OperationError): pipeline.produce(store.project_root)
    assert calls == []


def test_http_cli_read_plan_adopt_share_transaction(store, tmp_path, capsys):
    import json
    from deck_master import cli
    from deck_master.web import WorkbenchServer
    from test_web import _get_json, _post_json, _session_token
    cid = candidate(store)
    server = WorkbenchServer(store.project_root); url = server.start().rstrip('/')
    try:
        token = _session_token(url)
        assert _get_json(url + '/api/candidates')[2] == candidates.listing(store.project_root)
        assert _get_json(url + '/api/candidates/' + cid)[2] == candidates.show(store.project_root, candidate_id=cid)
        assert _get_json(url + '/api/candidates?revision=x&revision=y')[0] == 422
        value = plan(store, [cid]); op = str(uuid.uuid4())
        data = {'input': value, 'base_revision': value['base_revision'], 'operation_id': op}
        assert _post_json(url + '/api/candidates/adopt', data, token=token, origin='https://invalid.example')[0] == 403
        status, applied = _post_json(url + '/api/candidates/adopt', data, token=token, origin=url)
        assert status == 200
        input_file = tmp_path / 'adoption.json'; input_file.write_text(json.dumps(value))
        assert cli.main(['candidates', 'adopt', '--project', str(store.project_root), '--input', str(input_file),
                         '--base-revision', value['base_revision'], '--operation-id', op]) == 0
        replay = json.loads(capsys.readouterr().out)
        assert replay['operation_result'] == applied['operation_result']
        assert cli.main(['candidates', 'show', '--project', str(store.project_root), '--candidate-id', cid]) == 0
        assert json.loads(capsys.readouterr().out)['candidate_id'] == cid
    finally:
        server.stop()


@pytest.mark.parametrize('phase', ['before_pointer', 'after_pointer', 'before_index'])
def test_batch_interruption_recovers_whole_transaction(store, monkeypatch, phase):
    from deck_master import operations, store as store_module
    ids = [candidate(store), candidate(store, 'p02')]; value = plan(store, ids); op = str(uuid.uuid4())
    before = copy.deepcopy(store.load_document()['pages']); atomic = store_module._atomic_write_bytes; index = operations.publish_index
    def write(path, data):
        if path.name == 'current.json' and phase == 'before_pointer': raise SystemExit('synthetic crash')
        atomic(path, data)
        if path.name == 'current.json' and phase == 'after_pointer': raise SystemExit('synthetic crash')
    def publish(*args):
        if phase == 'before_index': raise SystemExit('synthetic crash')
        return index(*args)
    monkeypatch.setattr(store_module, '_atomic_write_bytes', write); monkeypatch.setattr(operations, 'publish_index', publish)
    with pytest.raises(SystemExit): adopt(store, value, op)
    monkeypatch.setattr(store_module, '_atomic_write_bytes', atomic); monkeypatch.setattr(operations, 'publish_index', index)
    current = store.load_document()
    if phase == 'before_pointer': assert current['pages'] == before
    else: assert [e['svg'] for e in current['pages']] == [x['result_ref'] for x in value['selections']]
    result = adopt(store, value, op)
    assert result['operation_result']['candidate_ids'] == ids
    assert len(store.load_document()['candidate_adoptions']) == 2


def test_restore_does_not_revive_cancelled_trial_or_drop_completed_candidates(store):
    from deck_master import editing
    cid = candidate(store); original = store.current_revision_id()
    old = dispatch(store); start(store, old); payload = envelope(store, old)
    service.task_cancel(store.project_root, task_id=old['task_id'], reason='synthetic removal preparation')
    editing.restore(store.project_root, revision_id=original, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    with pytest.raises(tasks.TaskConflict): accept(store, old, payload)
    assert candidates.show(store.project_root, candidate_id=cid)['candidate_id'] == cid
    fresh = dispatch(store)
    assert fresh['task_id'] != old['task_id']
    assert tasks._lookup_task(store.load_document(), old['task_id'], store)['status'] == 'cancelled'


# This fixture emits synthetic Codex events to test existing evidence binding.
# It is deliberately not a real Host/image-generation acceptance result.
from test_generation_protocol import flow, EXECUTION


def test_blueprint_candidate_keeps_request_attempt_and_only_adoption_changes_original(flow):
    from deck_master.models import canonical_json_bytes
    from test_generation_protocol import accept as accept_image
    project, store, automatic, native = flow
    task = dispatch(store, 'p1', layer='original_image')
    service.task_start(project, task_id=task['task_id'], execution_ref=EXECUTION,
                       supported_protocols=['generation.v1'], capabilities=[*generation.CAPABILITIES, 'change_plan', 'candidate_result'])
    prepared = generation.prepared_input(store, store.load_document(), task)
    prepared['parameters'] = {'transparent_background': False}
    frozen = generation.freeze(project, task_id=task['task_id'], input=prepared,
                                base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    attempt = tasks.call_begin(store, task_id=task['task_id'], allowance_id=task['call_allowances'][0]['allowance_id'],
                               execution_ref=EXECUTION, request_id=frozen['request_id'])
    report, raw = native(prompt=prepared['prompt'])
    tasks.call_settle(store, task_id=task['task_id'], allowance_id=attempt['allowance_id'], attempt_id=attempt['attempt_id'],
                       outcome='consumed', report_bytes=canonical_json_bytes(report))
    before = copy.deepcopy(store.load_document()['pages'])
    result = accept_image((project, store, task, native), frozen, attempt, raw)
    assert store.load_document()['pages'] == before
    cid = result['candidate_ids'][0]; shown = candidates.show(project, candidate_id=cid)
    assert shown['request']['request_id'] == frozen['request_id'] and shown['attempt']['attempt_id'] == attempt['attempt_id']
    adopt(store, plan(store, [cid]))
    assert store.load_document()['pages'][0]['blueprint'] == shown['candidate']['result_ref']
    assert store.load_document()['pages'][0]['svg'] is None
    assert tasks._lookup_task(store.load_document(), task['task_id'], store)['call_allowances'][0]['state'] == 'consumed'


@pytest.mark.render
@pytest.mark.parametrize("use_candidates", [True, False])
def test_explicit_assembly_uses_real_pipeline_after_page_gate_and_replays(store, monkeypatch, use_candidates):
    import shutil
    from deck_master import pipeline, stages
    from page_visual_helpers import pass_page_review
    if any(not shutil.which(tool) for tool in ('rsvg-convert', 'soffice', 'pdftoppm')):
        pytest.skip('real renderer toolchain unavailable')
    if use_candidates:
        ids = [candidate(store), candidate(store, 'p02')]; adopt(store, plan(store, ids))
    else:
        for pid in ('p01', 'p02'):
            task = service.open_host_task(store, kind='reconstruct', page_ids=[pid], instruction='Synthetic normal automatic SVG return')
            accept(store, task)
        assert store.load_document()['compatibility']['minimum_writer'] == 'content-plan.v1'
    for _ in range(2):
        pending = service.continue_project(store.project_root)['pending_tasks'][0]
        assert pending['kind'] == 'review' and pending['review_stage'] == 'page_visual'
        with pytest.raises(OperationError) as error:
            stages.assemble(store.project_root, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
        assert error.value.error_code == 'stage_quality_blocked'
        pass_page_review(store.project_root, pending)
    base = store.current_revision_id(); op = str(uuid.uuid4())
    response = stages.assemble(store.project_root, base_revision=base, operation_id=op)
    assert response['operation_result']['status'] == 'assembled'
    after = store.load_document()
    assert all(e['ppt_preview'] for e in after['pages']) and after['outputs']['pptx']
    assert after['compatibility']['minimum_writer'] == 'candidates.v1'
    assert response['operation_result']['final_review'] == 'required'
    def unexpected(*args, **kwargs): raise AssertionError('replay must not compile again')
    monkeypatch.setattr(pipeline, 'compile_deck', unexpected)
    assert stages.assemble(store.project_root, base_revision=base, operation_id=op)['operation_result'] == response['operation_result']


def test_explicit_svg_stage_requires_original_hash(store):
    task = dispatch(store); start(store, task); payload = envelope(store, task)
    path = store.staging_dir / task['operation_id'] / 'page.svg'
    import re
    path.write_text(re.sub(r' data-blueprint-sha256="[a-f0-9]+"', '', path.read_text()))
    before = store.read_current()
    with pytest.raises(tasks.EnvelopeError, match='original image hash'): accept(store, task, payload)
    assert store.read_current() == before


def test_explicit_assembly_does_not_migrate_legacy_project(tmp_path):
    from deck_master import stages
    project = tmp_path / 'legacy-core'; service.create(project, brief='legacy core stays legacy')
    store = Store(project); before = store.read_current()
    with pytest.raises(OperationError) as error:
        stages.assemble(project, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert error.value.error_code == 'stage_format_required'
    assert store.read_current() == before
