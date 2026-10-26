"""Synthetic original-only engineering checks, NOT independent pixel acceptance."""
import copy
import pytest
from deck_master import original_review, models, tasks, review_evidence, service
from test_content_preproduction_review import _deck
from test_rc3_design_recipes import synthetic_artifact
from synthetic_review_provider import synthetic_context, synthetic_runtime_call, accept_with_synthetic_provider
from rc3_fixtures import claim_fixture_task


def fixture(tmp_path):
    project, store = _deck(tmp_path)
    doc = store.load_document()
    changed = models.bump_revision(doc, {'operation_id': 'synthetic-original', 'kind': 'task_update', 'description': 'Synthetic original-only fixture', 'read_set': []})
    page = store.read_object_json(doc['pages'][0]['page'])
    page['visual_spec']['nodes'] = [{'node_id': 'model', 'label_ref': 'atom:p1:title', 'status': 'existing'},
                                    {'node_id': 'human', 'label_ref': 'atom:p1:block:b1:text', 'status': 'existing'},
                                    {'node_id': 'other', 'label_ref': 'atom:p1:title', 'status': 'existing'}]
    page['visual_spec']['edges'] = [{'edge_id': 'confirm', 'from': 'model', 'to': 'human', 'direction': 'forward', 'relationship': 'Synthetic fixed endpoint'}]
    changed['pages'][0]['page'] = store.put_json_object(page)
    plan = store.read_object_json(doc['content_plan'])
    plan['page_links'][0]['page_ref'] = changed['pages'][0]['page']
    changed['content_plan'] = store.put_json_object(plan)
    changed['pages'][0]['blueprint'] = synthetic_artifact(store, role='blueprint', page_id='p1')
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='synthetic-original')
    return project, store


def dispatch(project, store):
    context = synthetic_context()
    result = synthetic_runtime_call(original_review.dispatch, project, page_id='p1', adapter_context=context)
    task = result['task']
    claim_fixture_task(project, task, execution_ref='exec-independent')
    return task, result['packet'], context


def review(fixed, *, wrong=False, state='pass'):
    nodes = fixed['page']['visual_spec']['nodes']
    edges = [{key: edge[key] for key in ('edge_id', 'from', 'to', 'direction')} for edge in fixed['page']['visual_spec']['edges']]
    if wrong:
        edges[0]['to'] = 'other'
    return {'schema_version': 'deck_review.v2', 'review_id': 'original-1', 'kind': 'visual_expression',
        'review_stage': 'original_image', 'status': state, 'subjects': fixed['subjects'], 'dependencies': fixed['dependencies'],
        'reviewer': {'type': 'independent_host', 'id': 'independent', 'execution_ref': 'exec-independent',
                     'independence_confirmed': True, 'evidence_ref': None, 'identity_receipt': None, 'assurance': 'host_attested'},
        'observations': ['Synthetic reported graph; no claim of actual image inspection.'], 'findings': [],
        'expression_checks': {'graph': 'pass', 'hierarchy': 'pass', 'reading_path': 'pass',
                              'observed_nodes': [n['node_id'] for n in nodes], 'observed_edges': edges},
        'created_at': '2026-10-22T00:00:00Z', 'replaces': None}


def submit(project, task, row, context):
    return accept_with_synthetic_provider(project, **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')},
        result_payload={'kind': 'review', 'pages': [], 'page_order': [], 'artifact_specs': [], 'reviews': [row],
                        'usage_events': [], 'notes': 'Synthetic engineering receipt only'}, adapter_context=context)


def test_original_without_svg_accepts_applicable_authenticated_review(tmp_path):
    project, store = fixture(tmp_path)
    assert not store.load_document()['pages'][0]['svg']
    assert original_review.dispatch(project, page_id='p1')['status'] == 'needs_reviewer'
    task, fixed, context = dispatch(project, store)
    assert submit(project, task, review(fixed), context)['status'] == 'accepted'
    assert original_review.reference_status(store, store.load_document(), 'p1')['allowed']
    assert store.load_document()['compatibility']['minimum_writer'] == 'original-review.v1'


@pytest.mark.parametrize('fault', ['endpoint', 'unknown', 'basis', 'untrusted'])
def test_cannot_turn_wrong_unknown_or_unsigned_image_judgment_into_pass(tmp_path, fault):
    project, store = fixture(tmp_path)
    task, fixed, context = dispatch(project, store)
    row = review(fixed, wrong=fault == 'endpoint')
    if fault == 'unknown':
        row['expression_checks']['reading_path'] = 'unknown'
    if fault == 'basis':
        row['dependencies'] = []
    if fault == 'untrusted':
        context = None
    expected = {'endpoint': 'cannot pass', 'unknown': 'cannot pass', 'basis': 'exact frozen', 'untrusted': 'completed receipt'}[fault]
    with pytest.raises((tasks.EnvelopeError, review_evidence.EvidenceRejected), match=expected):
        submit(project, task, row, context)
    assert not original_review.reference_status(store, store.load_document(), 'p1')['allowed']


def test_known_relation_error_requires_fix_and_only_allows_explicit_repair_reference(tmp_path):
    project, store = fixture(tmp_path)
    task, fixed, context = dispatch(project, store)
    row = review(fixed, wrong=True, state='fail')
    row['findings'] = [{'finding_id': 'wrong-endpoint', 'kind': 'design', 'impact': 'must_fix', 'page_id': 'p1',
        'element_refs': ['edge:confirm'], 'message': 'Fixed model→human was drawn model→other',
        'expected': 'model→human', 'actual': 'model→other', 'evidence': [fixed['image_ref']], 'resolution': 'open'}]
    assert submit(project, task, row, context)['status'] == 'accepted'
    state = original_review.reference_status(store, store.load_document(), 'p1')
    assert state['status'] == 'fail' and not state['allowed']
    assert original_review.reference_status(store, store.load_document(), 'p1', use='repair_reference')['allowed']
    # Fresh synthetic pixels and an explicit closing independent result. This is
    # receiver/closure evidence only, not a claim that a model drew the repair.
    from io import BytesIO
    from PIL import Image
    stream = BytesIO(); Image.new('RGB', (2, 2), 'green').save(stream, format='PNG')
    doc = store.load_document()
    previous = doc['reviews'][-1]
    changed = models.bump_revision(doc, {'operation_id': 'synthetic-repair', 'kind': 'task_update', 'description': 'Synthetic repaired image', 'read_set': []})
    artifact = store.read_object_json(doc['pages'][0]['blueprint'])
    artifact['file'] = store.put_blob(stream.getvalue(), ext='png')
    changed['pages'][0]['blueprint'] = store.put_json_object(artifact)
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='synthetic-repair')
    task2, fixed2, context2 = dispatch(project, store)
    assert not original_review.reference_status(store, store.load_document(), 'p1')['allowed']
    repaired = review(fixed2)
    repaired['replaces'] = previous
    repaired['findings'] = [{**row['findings'][0], 'actual': 'model→human', 'resolution': 'fixed',
        'resolution_reason': 'New original checked with fixed directed endpoints', 'evidence': [fixed2['image_ref']]}]
    assert submit(project, task2, repaired, context2)['status'] == 'accepted'
    assert original_review.reference_status(store, store.load_document(), 'p1')['status'] == 'pass'



@pytest.mark.parametrize('change', ['page', 'cancel'])
def test_late_and_old_basis_results_are_rejected(tmp_path, change):
    project, store = fixture(tmp_path)
    task, fixed, context = dispatch(project, store)
    if change == 'cancel':
        service.task_cancel(project, task_id=task['task_id'])
    else:
        doc = store.load_document()
        changed = models.bump_revision(doc, {'operation_id': 'synthetic-edit', 'kind': 'task_update', 'description': 'Synthetic new basis', 'read_set': []})
        page = copy.deepcopy(fixed['page']); page['customer_visible']['title'] = 'Changed current requirement'
        changed['pages'][0]['page'] = store.put_json_object(page)
        store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='synthetic-edit')
    with pytest.raises((tasks.StaleInputContext, tasks.TaskConflict)):
        submit(project, task, review(fixed), context)


def test_cli_reader_and_old_host_capability_do_not_imply_image_inspection(tmp_path, capsys):
    import json
    from deck_master import cli
    project, store = fixture(tmp_path)
    assert cli.main(['review', 'original', '--project', str(project), '--page-id', 'p1']) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'needs_reviewer'
    context = synthetic_context()
    result = synthetic_runtime_call(original_review.dispatch, project, page_id='p1', adapter_context=context)
    task = result['task']
    from deck_master.generation import GenerationError
    assert 'original_expression_review.v1' in task['required_capabilities']
    with pytest.raises(GenerationError, match='declared capabilities'):
        service.task_start(project, task_id=task['task_id'], execution_ref='old-reader',
            supported_protocols=[task['protocol_version']],
            capabilities=[c for c in task['required_capabilities'] if c != 'original_expression_review.v1'])
    summary = service.task_summary(store, store.load_document(), task)
    assert summary['original_expression_packet']['image_ref'] == result['packet']['image_ref']
    assert summary['reference_images'][0]['file'] == result['packet']['image_ref']
    assert not store.load_document()['pages'][0]['svg']


def test_unadopted_original_candidate_can_be_reviewed_then_retains_pass_on_adoption(tmp_path):
    from test_styles import Flow, confirm, dispatch as dispatch_style
    from synthetic_review_provider import accept_original_expression_fixture
    flow = Flow(tmp_path)
    recipe = confirm(flow)
    cid = flow.image(dispatch_style(flow, recipe))['candidate_ids'][0]
    before = flow.store.load_document()['pages'][1]['blueprint']
    assert accept_original_expression_fixture(flow.project, page_id='p02', candidate_id=cid)['status'] == 'accepted'
    assert flow.store.load_document()['pages'][1]['blueprint'] == before
    assert original_review.reference_status(flow.store, flow.store.load_document(), 'p02', candidate_id=cid)['allowed']
    flow.adopt([cid])
    assert original_review.reference_status(flow.store, flow.store.load_document(), 'p02', candidate_id=cid)['allowed']


def test_unknown_provider_cannot_submit_an_original_pass(tmp_path):
    project, store = fixture(tmp_path)
    task, fixed, _ = dispatch(project, store)
    with pytest.raises(review_evidence.ProviderUnavailable, match='no trusted receipt provider'):
        service.accept_result(project, **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')},
            result_payload={'kind': 'review', 'pages': [], 'page_order': [], 'artifact_specs': [],
                            'reviews': [review(fixed)], 'usage_events': [], 'notes': 'untrusted selector'},
            review_receipt_selector={'provider_id': 'unknown', 'event_id': 'unknown'})
    assert not original_review.reference_status(store, store.load_document(), 'p1')['allowed']


def test_unknown_observation_remains_not_evaluated_and_does_not_expand(tmp_path):
    project, store = fixture(tmp_path)
    task, fixed, context = dispatch(project, store)
    row = review(fixed, state='not_evaluated')
    row['expression_checks'].update(graph='unknown', observed_nodes=[], observed_edges=[])
    assert submit(project, task, row, context)['status'] == 'accepted'
    status = original_review.reference_status(store, store.load_document(), 'p1')
    assert status['status'] == 'not_evaluated' and not status['allowed']


def test_old_runtime_writer_floor_refuses_new_original_review_facts(tmp_path, monkeypatch):
    from deck_master import store as storage
    project, store = fixture(tmp_path)
    dispatch(project, store)
    monkeypatch.setattr(storage, 'SUPPORTED_WRITERS', tuple(w for w in storage.SUPPORTED_WRITERS if w != 'original-review.v1'))
    with pytest.raises(storage.StoreError, match='writer'):
        storage.Store(project).load_document()


@pytest.mark.parametrize('format_name,mime,ext', [('PNG', 'image/png', 'png'), ('JPEG', 'image/jpeg', 'jpg'), ('WEBP', 'image/webp', 'webp')])
def test_original_raster_bytes_are_decoded_in_their_actual_format(tmp_path, format_name, mime, ext):
    from io import BytesIO
    from PIL import Image
    project, store = fixture(tmp_path)
    stream = BytesIO(); Image.new('RGB', (3, 2), 'blue').save(stream, format=format_name)
    doc = store.load_document()
    changed = models.bump_revision(doc, {'operation_id': 'synthetic-format', 'kind': 'task_update', 'description': 'Synthetic raster format', 'read_set': []})
    art = store.read_object_json(doc['pages'][0]['blueprint'])
    art.update(file=store.put_blob(stream.getvalue(), ext=ext), media_type=mime)
    changed['pages'][0]['blueprint'] = store.put_json_object(art)
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='synthetic-format')
    outcome = original_review.dispatch(project, page_id='p1')
    assert outcome['status'] == 'needs_reviewer'
    assert store.read_object_bytes(outcome['packet']['image_ref']) == stream.getvalue()


def test_same_original_pixels_cannot_close_a_known_endpoint_error(tmp_path):
    project, store = fixture(tmp_path)
    task, fixed, context = dispatch(project, store)
    row = review(fixed, wrong=True, state='fail')
    finding = {'finding_id': 'wrong-endpoint', 'kind': 'design', 'impact': 'must_fix', 'page_id': 'p1',
        'element_refs': ['edge:confirm'], 'message': 'Wrong fixed endpoint', 'expected': 'model→human',
        'actual': 'model→other', 'evidence': [fixed['image_ref']], 'resolution': 'open'}
    row['findings'] = [finding]
    assert submit(project, task, row, context)['status'] == 'accepted'
    prior = store.load_document()['reviews'][-1]
    task2, fixed2, context2 = dispatch(project, store)
    relabeled = review(fixed2)
    relabeled.update(replaces=prior, findings=[{**finding, 'resolution': 'fixed', 'actual': 'claimed correct',
        'resolution_reason': 'Claim without changed pixels'}])
    with pytest.raises(tasks.EnvelopeError, match='same image retains'):
        submit(project, task2, relabeled, context2)
    assert original_review.reference_status(store, store.load_document(), 'p1')['status'] == 'fail'


@pytest.mark.parametrize('change', ['notes', 'unrelated_edge', 'edge_label', 'required_edge'])
def test_notes_change_cannot_erase_same_image_endpoint_failure(tmp_path, change):
    project, store = fixture(tmp_path)
    task, fixed, context = dispatch(project, store)
    failed = review(fixed, wrong=True, state='fail')
    failed['findings'] = [{'finding_id': 'retained-edge', 'kind': 'design', 'impact': 'must_fix', 'page_id': 'p1',
        'element_refs': ['edge:confirm'], 'message': 'Wrong endpoint', 'expected': 'model→human',
        'actual': 'model→other', 'evidence': [fixed['image_ref']], 'resolution': 'open'}]
    assert submit(project, task, failed, context)['status'] == 'accepted'
    doc = store.load_document()
    changed = models.bump_revision(doc, {'operation_id': 'notes-only', 'kind': 'task_update', 'description': 'Synthetic notes-only change', 'read_set': []})
    page = store.read_object_json(doc['pages'][0]['page']); page['speaker_notes'] += ' Unrelated cue.'
    page['content_mapping']['speech_segments'][-1]['end_codepoint'] = len(page['speaker_notes'])
    if change == 'required_edge':
        page['visual_spec']['edges'][0]['to'] = 'other'
    elif change == 'edge_label':
        page['visual_spec']['edges'][0]['relationship'] = 'New wording, same fixed endpoints'
    elif change == 'unrelated_edge':
        page['visual_spec']['edges'].append({'edge_id': 'new-edge', 'from': 'other', 'to': 'human', 'direction': 'forward', 'relationship': 'New unrelated requirement'})
    changed['pages'][0]['page'] = store.put_json_object(page)
    plan = store.read_object_json(doc['content_plan']); plan['page_links'][0]['page_ref'] = changed['pages'][0]['page']
    changed['content_plan'] = store.put_json_object(plan)
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='notes-only')
    task2, fixed2, context2 = dispatch(project, store)
    assert fixed2['image_ref'] == fixed['image_ref']
    if change == 'required_edge':
        assert submit(project, task2, review(fixed2), context2)['status'] == 'accepted'
        assert original_review.reference_status(store, store.load_document(), 'p1')['allowed'] is True
    else:
        with pytest.raises(tasks.EnvelopeError, match='same image retains'):
            submit(project, task2, review(fixed2), context2)
        state = original_review.reference_status(store, store.load_document(), 'p1')
        assert state['allowed'] is False and state['retained_findings'][0]['finding_id'] == 'retained-edge'
        prior = doc['reviews'][-1]
        relabeled = review(fixed2)
        relabeled.update(replaces=prior, findings=[{**failed['findings'][0], 'resolution': 'fixed',
            'resolution_reason': 'Claim after Page update, without changed pixels'}])
        with pytest.raises(tasks.EnvelopeError, match='same image retains'):
            submit(project, task2, relabeled, context2)
        if change == 'notes':
            from deck_master.editing import _current_artifact_digests
            from deck_master.review import finding_closed
            owner = {**store.read_object_json(prior), 'ref': prior}
            artifacts = _current_artifact_digests(store, store.load_document(), owner['subjects'] + relabeled['subjects'])
            assert not finding_closed([owner, relabeled], owner, owner['findings'][0], artifacts)


def test_original_dispatch_consumes_admission_before_creating_task(tmp_path):
    from deck_master import collaboration, eligibility
    project, store = fixture(tmp_path)
    document = store.load_document()
    collaboration.pause_request(project, reason='Synthetic admission refusal',
        base_revision=document['revision_id'], operation_id='pause-original-dispatch')
    paused = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        synthetic_runtime_call(original_review.dispatch, project, page_id='p1',
            adapter_context=synthetic_context())
    assert store.load_document() == paused
