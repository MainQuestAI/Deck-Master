"""Finite independent R5 boundaries; all projects are explicit external L1 fixtures."""
from copy import deepcopy
import uuid

import pytest

from deck_master import collaboration, content_review, eligibility, production, ui_journal
from deck_master.models import ModelError, bump_revision
from deck_master.store import StoreError
from rc3_fixtures import source_snapshot
from test_icon_quality import confirm, dispatch, icon_store  # noqa: F401


@pytest.mark.parametrize('fault',['damaged-bytes','valid-hash-malformed-json'])
def test_actual_bad_task_keeps_owned_error_path_and_read_only_missing_proof(icon_store,fault):
    store=icon_store
    assert eligibility.preproduction_state(store,store.load_document())['satisfied'] is True
    recipe=confirm(store)
    task=dispatch(store,recipe)[0]
    doc=store.load_document()
    ref=next(ref for ref in doc['tasks'] if store.read_object_json(ref)['task_id']==task['task_id'])
    if fault=='damaged-bytes':
        damaged=store.project_root/ref['path']
        damaged.write_bytes(b'{broken task')
    else:
        # Unlike the original immutable-byte fault, this also reaches the
        # actual JSON decoder after a valid Ref digest. Neither is production.
        malformed=store.put_blob(b'{broken task',ext='json')
        changed=bump_revision(deepcopy(doc),{'operation_id':str(uuid.uuid4()),'kind':'task_update',
            'description':'L1 reviewer malformed Task fault only','read_set':[]})
        changed['tasks']=[malformed if item==ref else item for item in changed['tasks']]
        store.commit_change(base_revision=doc['revision_id'],document=changed,
            operation_id=changed['change']['operation_id'])
        doc=store.load_document()
        damaged=store.project_root/malformed['path']
    snap=source_snapshot(store.project_root)
    with pytest.raises(ModelError) as caught:
        production.adopted_blueprint_design(store,doc,doc['pages'][0])
    assert caught.value.path=='blueprint/provenance/generation_request'
    assert isinstance(caught.value.__cause__,StoreError)
    if fault=='damaged-bytes':
        assert 'sha256' in caught.value.__cause__.detail
    else:
        assert 'not valid JSON' in caught.value.__cause__.detail
    state=eligibility.preproduction_state(store,doc)
    assert state['status']=='unreadable' and state['satisfied'] is False
    assert state['missing_units']==state['units'] and state['satisfied_units']==[]
    assert collaboration.describe(store.project_root)['revision_id']==doc['revision_id']
    assert ui_journal.project_info(store.project_root)['revision_id']==doc['revision_id']
    with pytest.raises(ModelError) as strict_again:
        production.resolve_page_rendering_design(store,doc,doc['pages'][0])
    assert strict_again.value.path==caught.value.path
    assert source_snapshot(store.project_root)==snap
    assert damaged.read_bytes()==b'{broken task'


@pytest.mark.parametrize('stage,error',[
    ('status',ModelError('design_context/allowed_asset_ids','unreadable or invalid adopted generation lineage')),
    ('qualify',ModelError('design_context/canvas','unreadable or invalid adopted generation lineage')),
    ('status',ModelError('blueprint/provenance/generation_request/permission','same prefix must not match')),
    ('status',StoreError('asset:logo','unreadable or invalid adopted generation lineage')),
    ('qualify',StoreError('blueprint/provenance/generation_request','same path but wrong exception type')),
    ('status',RuntimeError('blueprint/provenance/generation_request')),
])
def test_other_errors_propagate_the_exact_original_instance(monkeypatch,stage,error):
    # This is a forced negative boundary test, not an actual asset observation.
    def fail(*args,**kwargs):
        raise error
    def status(*args,**kwargs):
        return {'requirement_state':{'effective':'independent_model_or_human','declared':None,
            'origin':None,'reasons':[]},'status':'missing','units':['argument'],
            'satisfied_units':[],'missing_units':['argument'],'blocking_findings':[],'review_refs':[]}
    monkeypatch.setattr(content_review,'preproduction_status',fail if stage=='status' else status)
    monkeypatch.setattr(content_review,'qualify_for_production',fail)
    with pytest.raises(type(error)) as caught:
        eligibility.preproduction_state(None,{'pages':[]})
    assert caught.value is error
