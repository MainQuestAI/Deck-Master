"""Legacy frozen visibility contract stays absent; new work stays explicit."""
import copy
import pytest
from deck_master import production, tasks, models
from test_rc3_adopted_design_handoff import _adopted, _open, _commit


@pytest.mark.parametrize('change', [None, 'page', 'design'])
def test_legacy_adopted_image_uses_frozen_visibility(tmp_path, monkeypatch, change):
    from deck_master import design_requirements
    current = design_requirements.resolve_content_requirements
    def legacy(*args, **kwargs):
        result = current(*args, **kwargs)
        result['content_requirements'].pop('text_visibility')
        return result
    with monkeypatch.context() as old:
        old.setattr(design_requirements, 'resolve_content_requirements', legacy)
        project, store, _, _, author = _adopted(tmp_path)
    doc = store.load_document()
    original = copy.deepcopy(doc)
    if change == 'page':
        page = store.read_object_json(doc['pages'][0]['page'])
        page['customer_visible']['title'] += ' changed'
        doc['pages'][0]['page'] = store.put_json_object(page)
        doc = _commit(store, doc, 'changed content')
    elif change == 'design':
        doc['design_context']['assets'] = []
        page = store.read_object_json(doc['pages'][0]['page'])
        page['visual_spec']['intent'] += ' changed'
        doc['pages'][0]['page'] = store.put_json_object(page)
        doc = _commit(store, doc, 'changed design')
    if change:
        with pytest.raises(models.ModelError):
            production.resolve_page_design(store, doc, doc['pages'][0], require_current=True)
    else:
        resolved = production.resolve_page_design(store, doc, doc['pages'][0], require_current=True)
        assert 'text_visibility' not in resolved['content_requirements']
        assert tasks.task_inputs_current(store, doc, author)
        assert store.load_document() == original
        assert _open(store)['kind'] == 'reconstruct'


def test_unknown_visibility_is_not_legacy():
    with pytest.raises(models.ModelError):
        production.frozen_design_options({'content_requirements': {'text_visibility': 'unknown.v9'}})


def test_legacy_original_review_task_stays_current(tmp_path, monkeypatch):
    from deck_master import design_requirements, original_review
    from test_rp20_original_review import dispatch as rp20_dispatch, fixture as rp20_fixture
    from test_rp20_original_review import review as rp20_review, submit as rp20_submit
    current = design_requirements.resolve_content_requirements
    def legacy(*args, **kwargs):
        result = current(*args, **kwargs)
        result['content_requirements'].pop('text_visibility')
        return result
    with monkeypatch.context() as old:
        old.setattr(design_requirements, 'resolve_content_requirements', legacy)
        project, store = rp20_fixture(tmp_path)
        task, fixed, context = rp20_dispatch(project, store)
        assert rp20_submit(project, task, rp20_review(fixed), context)['status'] == 'accepted'
    assert 'text_visibility' not in fixed['resolved_design']['content_requirements']
    doc = store.load_document()
    original = copy.deepcopy(doc)
    assert original_review.inputs_current(store, doc, task)
    state = original_review.reference_status(store, doc, 'p1')
    assert state['status'] == 'pass' and state['allowed']
    assert store.load_document() == original


def test_legacy_original_reference_real_change_stays_conservative(tmp_path, monkeypatch):
    from deck_master import design_requirements, models, original_review
    from test_rp20_original_review import dispatch as rp20_dispatch, fixture as rp20_fixture
    from test_rp20_original_review import review as rp20_review, submit as rp20_submit
    current = design_requirements.resolve_content_requirements
    def legacy(*args, **kwargs):
        result = current(*args, **kwargs)
        result['content_requirements'].pop('text_visibility')
        return result
    with monkeypatch.context() as old:
        old.setattr(design_requirements, 'resolve_content_requirements', legacy)
        project, store = rp20_fixture(tmp_path)
        task, fixed, context = rp20_dispatch(project, store)
        assert rp20_submit(project, task, rp20_review(fixed), context)['status'] == 'accepted'
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] += ' changed'
    doc['pages'][0]['page'] = store.put_json_object(page)
    plan = store.read_object_json(doc['content_plan'])
    plan['page_links'][0]['page_ref'] = doc['pages'][0]['page']
    doc['content_plan'] = store.put_json_object(plan)
    changed = models.bump_revision(doc, {'operation_id': 'legacy-original-change', 'kind': 'task_update',
        'description': 'Changed legacy original page', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='legacy-original-change')
    doc = store.load_document()
    assert not original_review.inputs_current(store, doc, task)
    assert not original_review.reference_status(store, doc, 'p1')['allowed']
