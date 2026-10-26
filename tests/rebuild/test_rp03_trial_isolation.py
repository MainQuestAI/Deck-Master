"""RP-03 uses synthetic engineering artifacts; no visual acceptance claim."""
import copy
import uuid

import pytest
from PIL import Image

from deck_master import review, service, tasks
from deck_master.editing import check_summary, export_project
from deck_master.handoff import check_handoff
from deck_master.pipeline import artifact
from deck_master.store import Store
from test_review import _project_with_passing_reviews, make_document, pass_set, current_artifacts, finding, make_review
from test_content_candidates import dispatch_content_trial, start_task, accept, page_envelope, adopt
from test_content_ops import prepare_editorial_project


def test_unadopted_trial_preserves_review_and_handoff_then_adoption_invalidates(tmp_path):
    path = _project_with_passing_reviews(tmp_path)
    store = Store(path)
    doc = store.load_document()
    image = tmp_path / 'synthetic.png'
    Image.new('RGB', (120, 80), 'white').save(image)
    updated = tasks.bump_revision(copy.deepcopy(doc), {'operation_id': 'complete-slots',
        'kind': 'task_update', 'description': 'Synthetic handoff fixture slots', 'read_set': []})
    updated['pages'][0]['blueprint'] = artifact(store, image, 'blueprint', page_id='p1')
    updated['pages'][0]['svg_preview'] = artifact(store, image, 'svg_preview', page_id='p1')
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='complete-slots')
    prepare_editorial_project(path)
    export_project(path, output_dir=tmp_path / 'export', purpose='review')
    output = tmp_path / 'export/deck.pptx'
    assert check_summary(store, store.load_document())['status'] == 'pass'
    assert check_handoff(path, file_path=output)['status'] == 'verified'
    before = copy.deepcopy(store.load_document())
    task = dispatch_content_trial(path, store, 'p1')
    assert check_summary(store, store.load_document())['status'] == 'pass'
    assert check_handoff(path, file_path=output)['status'] == 'verified'
    start_task(path, task)
    assert check_summary(store, store.load_document())['status'] == 'pass'
    assert check_handoff(path, file_path=output)['status'] == 'verified'
    result = accept(path, task, page_envelope(store, task))
    assert store.load_document()['outputs'] == before['outputs']
    assert check_summary(store, store.load_document())['status'] == 'pass'
    assert check_handoff(path, file_path=output)['status'] == 'verified'
    adopt(path, store, result['candidate_ids'])
    assert not store.load_document()['outputs']['pptx']
    assert check_summary(store, store.load_document())['status'] != 'pass'
    assert check_handoff(path, file_path=output)['status'] == 'blocked'


@pytest.mark.parametrize('extra', [
    {'stage_request': {'mode': 'auto', 'stage': 'content'}},
    {'stage_request': {'mode': 'trial', 'stage': 'blueprint'}, 'cost_class': 'external_generation'},
    {'call_allowances': [{'state': 'unknown'}]},
    {'call_allowances': [{'state': 'in_flight'}]},
    {'usage': {'external_calls': 1}},
])
def test_real_or_uncertain_work_still_suspends_current_reviews(extra):
    task = {'kind': 'repair', 'status': 'running', 'scope_pages': ['p1'],
            'stage_request': {'mode': 'trial', 'stage': 'content'},
            'cost_class': 'host_reasoning', 'call_allowances': [], **extra}
    summary = review.evaluate_current(make_document(tasks=[task]), pass_set(), current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert review.task_blocks_current_output(task)


def test_side_branch_does_not_close_existing_findings():
    task = {'kind': 'repair', 'status': 'running', 'scope_pages': ['p1'],
            'stage_request': {'mode': 'trial', 'stage': 'content'},
            'cost_class': 'host_reasoning', 'call_allowances': []}
    reviews = pass_set() + [make_review('content', status='fail', seed='open', findings=[finding('unresolved')])]
    summary = review.evaluate_current(make_document(tasks=[task]), reviews, current_artifacts())
    assert summary['status'] == 'fail'
    assert summary['dimensions']['content:p1']['open_must_fix']
