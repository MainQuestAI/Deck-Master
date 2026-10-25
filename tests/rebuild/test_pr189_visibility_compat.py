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
