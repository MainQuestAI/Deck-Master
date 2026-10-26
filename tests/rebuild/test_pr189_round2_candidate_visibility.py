"""Historical preparation omits visibility; readers negotiate that frozen shape."""
import copy
import uuid

import pytest

from deck_master import candidates, design_requirements
from deck_master.operations import OperationError
from test_rc3_design_workflows import confirmed, dispatch
from test_rc3_restyle_workflows import candidate, project


@pytest.mark.parametrize('changed', [False, True])
def test_pending_legacy_candidate_uses_its_frozen_design_options(tmp_path, monkeypatch, changed):
    current = design_requirements.resolve_content_requirements

    def legacy(*args, **kwargs):
        result = current(*args, **kwargs)
        result['content_requirements'].pop('text_visibility')
        return result

    with monkeypatch.context() as old:
        old.setattr(design_requirements, 'resolve_content_requirements', legacy)
        path, store, _ = project(tmp_path)
        recipe = confirmed(path, store)
        task = dispatch(path, store, recipe, ['p1'])[0]
        cid, sent = candidate(path, store, task)
    frozen = store.read_object_bytes(sent[0]['request_ref'])
    old_candidate = candidates.show(path, candidate_id=cid)['candidate']
    if changed:
        from test_rc3_restyle_workflows import edit
        edit(path, store, 'p1', lambda page: page['customer_visible'].update(title='Meaningful later visible change'))
    before = copy.deepcopy(store.load_document())
    selection = {'schema_version': 'candidate_selection.v1', 'project_id': before['project_id'],
                 'base_revision': before['revision_id'], 'candidate_ids': [cid]}
    if changed:
        with pytest.raises(OperationError):
            candidates.plan(path, input=selection)
        assert store.load_document() == before
    else:
        proposal = candidates.plan(path, input=selection)['plan']
        result = candidates.adopt(path, input=proposal, base_revision=proposal['base_revision'], operation_id=str(uuid.uuid4()))
        assert result['status'] == 'committed' and result['operation_result']['status'] == 'adopted'
        assert store.load_document()['pages'][0]['blueprint'] == old_candidate['result_ref']
    assert store.read_object_bytes(sent[0]['request_ref']) == frozen
    assert candidates.show(path, candidate_id=cid)['candidate'] == old_candidate
