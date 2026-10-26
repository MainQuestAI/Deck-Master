"""Synthetic protocol flows: review results belong to the queried original."""
import copy
import pytest
from deck_master import original_review, changes, models
from deck_master.operations import OperationError
from synthetic_review_provider import accept_original_expression_fixture, synthetic_context, synthetic_runtime_call
from rc3_fixtures import claim_fixture_task
from test_styles import Flow, confirm, dispatch
from test_rp20_original_review import review, submit


def test_other_page_pass_cannot_dispatch_expansion(tmp_path):
    flow = Flow(tmp_path)
    recipe = confirm(flow)
    cid = flow.image(dispatch(flow, recipe))['candidate_ids'][0]
    flow.adopt([cid])
    accept_original_expression_fixture(flow.project, page_id='p01')
    before = copy.deepcopy(flow.store.load_document())
    state = original_review.reference_status(flow.store, before, 'p02', candidate_id=cid)
    assert state['status'] == 'not_evaluated' and not state['allowed']
    with pytest.raises(OperationError, match='original expression review'):
        dispatch(flow, recipe, ['p03'], cid)
    assert flow.store.load_document() == before


def test_other_page_fail_does_not_poison_reviewed_target(tmp_path):
    flow = Flow(tmp_path)
    recipe = confirm(flow)
    cid = flow.image(dispatch(flow, recipe))['candidate_ids'][0]
    flow.adopt([cid])
    accept_original_expression_fixture(flow.project, page_id='p02', candidate_id=cid)
    ctx = synthetic_context()
    outcome = synthetic_runtime_call(original_review.dispatch, flow.project, page_id='p01', adapter_context=ctx)
    task, fixed = outcome['task'], outcome['packet']
    claim_fixture_task(flow.project, task, execution_ref='exec-independent')
    review_input = copy.deepcopy(fixed)
    review_input['page']['visual_spec'].setdefault('nodes', [])
    review_input['page']['visual_spec'].setdefault('edges', [])
    row = review(review_input, state='fail')
    row['expression_checks']['hierarchy'] = 'fail'
    row['findings'] = [{'finding_id': 'bad-hierarchy', 'kind': 'design', 'impact': 'must_fix', 'page_id': 'p01',
        'element_refs': [], 'message': 'Synthetic hierarchy defect', 'expected': 'clear', 'actual': 'unclear',
        'evidence': [fixed['image_ref']], 'resolution': 'open'}]
    submit(flow.project, task, row, ctx)
    assert original_review.reference_status(flow.store, flow.store.load_document(), 'p02', candidate_id=cid)['status'] == 'pass'
    assert dispatch(flow, recipe, ['p03'], cid)['status'] == 'awaiting_host'


def test_new_candidate_cannot_inherit_old_candidate_review(tmp_path):
    flow = Flow(tmp_path)
    recipe = confirm(flow)
    cid = flow.image(dispatch(flow, recipe))['candidate_ids'][0]
    accept_original_expression_fixture(flow.project, page_id='p02', candidate_id=cid)
    newer = flow.image(dispatch(flow, recipe), 2)['candidate_ids'][0]
    assert newer != cid
    state = original_review.reference_status(flow.store, flow.store.load_document(), 'p02', candidate_id=newer)
    assert state['status'] == 'not_evaluated' and not state['allowed']


def test_legacy_review_still_matches_its_target_after_upgrade(tmp_path, monkeypatch):
    from deck_master import design_requirements
    from test_rp20_original_review import fixture, dispatch as review_dispatch
    current = design_requirements.resolve_content_requirements
    def legacy(*args, **kwargs):
        value = current(*args, **kwargs)
        value['content_requirements'].pop('text_visibility', None)
        return value
    with monkeypatch.context() as old:
        old.setattr(design_requirements, 'resolve_content_requirements', legacy)
        project, store = fixture(tmp_path)
        task, fixed, ctx = review_dispatch(project, store)
        submit(project, task, review(fixed), ctx)
    before = store.load_document()
    assert original_review.reference_status(store, before, 'p1')['status'] == 'pass'
    assert store.load_document() == before
