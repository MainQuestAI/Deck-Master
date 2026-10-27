"""Synthetic engineering regression: immutable SVG trials are not current writes."""
import copy
import uuid

import pytest
from PIL import Image

from deck_master import candidates, changes, review, tasks
from deck_master.editing import check_summary, export_project
from deck_master.handoff import check_handoff
from deck_master.pipeline import artifact
from deck_master.store import Store
from test_review import _project_with_passing_reviews
from test_content_ops import prepare_editorial_project
from candidate_fixtures import start, accept, plan, adopt


@pytest.fixture
def current_deck(tmp_path):
    path = _project_with_passing_reviews(tmp_path)
    store = Store(path); doc = store.load_document()
    image = tmp_path / 'synthetic.png'
    Image.new('RGB', (120, 80), 'white').save(image)
    updated = tasks.bump_revision(copy.deepcopy(doc), {'operation_id': 'complete-slots',
        'kind': 'task_update', 'description': 'Synthetic complete handoff fixture', 'read_set': []})
    updated['pages'][0]['blueprint'] = artifact(store, image, 'blueprint', page_id='p1')
    updated['pages'][0]['svg_preview'] = artifact(store, image, 'svg_preview', page_id='p1')
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='complete-slots')
    prepare_editorial_project(path)
    export_project(path, output_dir=tmp_path / 'export', purpose='review')
    output = tmp_path / 'export/deck.pptx'
    assert check_summary(store, store.load_document())['status'] == 'pass'
    assert check_handoff(path, file_path=output)['status'] == 'verified'
    return store, output


def dispatch(store, *, stage='reconstruct', mode='trial'):
    doc = store.load_document(); entry = doc['pages'][0]
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
        'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'Synthetic spacing alternative.',
        'annotation_refs': [], 'max_calls': 0, 'mode': mode,
        'targets': [{'page_id': 'p1', 'page_ref': entry['page'], 'layer': 'svg',
                     'artifact_ref': entry['svg'], 'stage': stage}]}
    preview = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=preview['plan_id'], base_revision=doc['revision_id'],
                            operation_id=str(uuid.uuid4()))
    return tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)


@pytest.mark.parametrize('stage', ['reconstruct', 'repair'])
def test_svg_trial_preserves_current_through_dispatch_start_completion_until_adopt(current_deck, stage):
    store, output = current_deck; before = store.load_document()
    task = dispatch(store, stage=stage)
    assert task['stage_request'] == {'mode': 'trial', 'stage': stage, 'references': []}
    for phase in ('dispatch', 'start', 'completion'):
        if phase == 'start': start(store, task)
        if phase == 'completion': result = accept(store, task)
        current = store.load_document()
        assert current['pages'] == before['pages'] and current['outputs'] == before['outputs']
        summary = check_summary(store, current)
        handoff = check_handoff(store.project_root, file_path=output)
        assert (summary['status'], handoff['status']) == ('pass', 'verified'), (phase, handoff['gaps'])
    assert candidates.show(store.project_root, candidate_id=result['candidate_ids'][0])
    adopt(store, plan(store, result['candidate_ids']))
    current = store.load_document()
    assert current['pages'][0]['svg'] != before['pages'][0]['svg']
    assert current['outputs']['pptx'] is None
    assert check_summary(store, current)['status'] != 'pass'
    assert check_handoff(store.project_root, file_path=output)['status'] == 'blocked'


def replace_task(store, task, mutate):
    """Explicit fault fixture: preserve immutable objects and replace one Ref."""
    doc = store.load_document(); updated = copy.deepcopy(doc); value = copy.deepcopy(task)
    mutate(value)
    for index, ref in enumerate(updated['tasks']):
        if store.read_object_json(ref)['task_id'] == task['task_id']:
            updated['tasks'][index] = store.put_json_object(value)
    op = 'fault-' + uuid.uuid4().hex
    updated = tasks.bump_revision(updated, {'operation_id': op, 'kind': 'task_update',
        'description': 'Synthetic invalid isolation evidence', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id=op)


@pytest.mark.parametrize('mode', ['auto', 'forged_trial_label'])
def test_current_write_plan_still_blocks_even_with_trial_label(current_deck, mode):
    store, output = current_deck
    task = dispatch(store, mode='auto')
    if mode == 'forged_trial_label':
        def disguise(value):
            value['stage_request']['mode'] = 'trial'
            value['required_capabilities'].append('candidate_result')
            value['collaboration_binding']['adoption_policy'] = 'candidate_only'
        replace_task(store, task, disguise)
    summary = check_summary(store, store.load_document())
    assert summary['status'] == 'not_evaluated' and 'host tasks still open' in summary['reason']
    assert 'pending_host_tasks' in check_handoff(store.project_root, file_path=output)['gaps']


@pytest.mark.parametrize('fault', ['reserved', 'in_flight', 'unknown', 'consumed', 'released',
    'reported_spend', 'missing_plan', 'missing_capability', 'within_scope', 'uncommitted_change', 'existing_result'])
def test_unproven_or_nonzero_call_trial_remains_blocking(current_deck, fault):
    store, output = current_deck; task = dispatch(store)
    def invalidate(value):
        if fault in ('reserved', 'in_flight', 'unknown', 'consumed', 'released'):
            value['call_allowances'] = [{'allowance_id': 'fault-call', 'state': fault,
                'execution_ref': 'synthetic-execution' if fault != 'reserved' else None,
                'invocation_ref': None, 'evidence': []}]
        elif fault == 'reported_spend': value['usage']['external_calls'] = 1
        elif fault == 'missing_plan': value.pop('change_binding')
        elif fault == 'missing_capability': value['required_capabilities'].remove('candidate_result')
        elif fault == 'within_scope': value['collaboration_binding']['adoption_policy'] = 'within_scope'
        elif fault == 'uncommitted_change':
            change = store.read_object_json(value['change_binding']['change_ref']); change['project_id'] = 'foreign-project'
            value['change_binding']['change_ref'] = store.put_json_object(change)
        else: value['result_refs'] = [store.load_document()['pages'][0]['svg']]
    replace_task(store, task, invalidate)
    current = store.load_document()
    summary = check_summary(store, current)
    assert summary['status'] == 'not_evaluated' and 'host tasks still open' in summary['reason']
    result = check_handoff(store.project_root, file_path=output)
    assert result['status'] == 'blocked' and 'pending_host_tasks' in result['gaps']


def test_isolated_trial_does_not_hide_a_current_open_finding(current_deck):
    from deck_master import service
    from rc3_fixtures import claim_fixture_task
    from test_review import finding, make_review
    store, output = current_deck
    review_task = service.open_host_task(store, kind='review', page_ids=['p1'],
        instruction='Synthetic actual open finding', review_stage='final',
        extra_inputs=[store.load_document()['outputs']['pptx']])
    claim_fixture_task(store.project_root, review_task, execution_ref='synthetic-open-finding')
    doc = store.load_document()
    record = make_review('content', status='fail', seed='svg-side-branch-open',
        subjects=[doc['outputs']['pptx'], doc['pages'][0]['page']], findings=[finding('still-open')],
        dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': doc['pages'][0]['page']['sha256']}])
    service.accept_result(store.project_root, result_payload={'kind': 'review', 'files': [], 'reviews': [record]},
        **{key: review_task[key] for key in ('task_id', 'operation_id', 'produced_against')})
    dispatch(store)
    summary = check_summary(store, store.load_document())
    assert summary['status'] == 'fail'
    assert summary['dimensions']['content:p1']['open_must_fix']
    # Review copies remain explicitly non-delivery; the finding is still shown.
    assert check_handoff(store.project_root, file_path=output)['review_status'] == 'fail'
    delivery = check_handoff(store.project_root, file_path=output, purpose='delivery')
    assert delivery['status'] == 'blocked' and 'required_review_not_pass' in delivery['gaps']
