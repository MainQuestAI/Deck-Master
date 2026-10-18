"""AUDIT-F05: real preflight/export parity on explicit L1 engineering fixtures."""
import copy
import uuid

import pytest

from deck_master import collaboration, delivery_eligibility, exports, service
from deck_master.models import bump_revision, sha256_bytes
from deck_master.operations import OperationError
from test_export import (_passing_deck, _set_policy, _review, _must_fix,
                         _authorize_delivery, REQUIRED)


def _commit(store, change):
    before=store.load_document()
    document=copy.deepcopy(before)
    change(document)
    operation='audit-parity-'+uuid.uuid4().hex
    document=bump_revision(document, {'operation_id':operation,'kind':'task_update',
        'description':'Explicit synthetic delivery predicate counterexample','read_set':[]})
    store.commit_change(base_revision=before['revision_id'],document=document,operation_id=operation)


@pytest.mark.parametrize('notes_policy', [None, 'pptx_notes', 'separate_script', 'both', 'pure_reading'])
@pytest.mark.parametrize('scenario', ['ready', 'historical', 'missing_ppt', 'missing_report',
    'failed_check', 'strict_policy', 'paused', 'revoked', 'pending_inputs', 'stale_output'])
def test_preflight_matches_actual_delivery_on_same_basis(tmp_path, scenario, notes_policy):
    project,store=_passing_deck(tmp_path,notes='Explicit synthetic complete speaker notes.')
    selected=store.current_revision_id()
    evidence={'kind':'host_attested_instruction','text':'L1 synthetic stop/control test; no human approval.'}
    if scenario=='historical':
        _set_policy(store,professional_review_required_for_delivery=False)
    elif scenario=='strict_policy':
        _set_policy(store,professional_review_required_for_delivery=True)
    elif scenario=='paused':
        collaboration.pause_request(project,reason='L1 stop delivery',instruction_evidence=evidence,
            base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    elif scenario=='revoked':
        current=store.load_document()
        record=next(store.read_object_json(ref) for ref in current['collaboration']['authorizations']
            if store.read_object_json(ref)['status']=='active')
        collaboration.revoke_authorization(project,authorization_id=record['authorization_id'],reason='L1 withdraw',
            instruction_evidence=evidence,base_revision=current['revision_id'],operation_id=str(uuid.uuid4()))
    elif scenario=='pending_inputs':
        service.inputs_update(project,patch={'reason':'L1 new audience pending reconciliation',
            'task_patch':{'audience':'Changed synthetic audience'}},base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
        selected=store.current_revision_id()
    elif scenario=='missing_ppt':
        _commit(store,lambda document:document['outputs'].__setitem__('pptx',None))
        selected=store.current_revision_id()
    elif scenario=='missing_report':
        _commit(store,lambda document:document['outputs'].__setitem__('render_report',None))
        selected=store.current_revision_id()
    elif scenario=='failed_check':
        _review(store,store.load_document(),'conversion','fail',seed='audit-failed',findings=_must_fix())
        selected=store.current_revision_id()
    elif scenario=='stale_output':
        def stale(document):
            artifact=store.read_object_json(document['outputs']['pptx'])
            artifact['dependencies']=[{'kind':'svg','identity':'p1','sha256':'f'*64}]
            document['outputs']['pptx']=store.put_json_object(artifact)
        _commit(store,stale)
        for kind in REQUIRED:
            _review(store,store.load_document(),kind,'pass',seed='audit-current-'+kind)
        _authorize_delivery(store)
        selected=store.current_revision_id()
        assert any(gap['reason']=='basis_changed' for gap in exports.describe(project,revision=selected)['gaps'])
    before=store.read_current()
    report=delivery_eligibility.describe(project,revision=selected,notes_policy=notes_policy)
    assert store.read_current()==before
    assert report['artifact_revision_id']==selected
    assert report['control_revision_id']==store.current_revision_id()
    try:
        packet=exports.create(project,purpose='delivery',revision=selected,notes_policy=notes_policy)
        actual=True
    except OperationError:
        actual=False
    assert (report['status']=='ready') is actual, (scenario,notes_policy,report)
    assert actual is (scenario in ('ready','historical'))
    if actual:
        data,_=exports.download(project,export_id=packet['export_id'],filename='deck.pptx')
        assert sha256_bytes(data)==report['selected_output']['file_sha256']
        assert packet['manifest']['notes_policy']==report['selected_output']['notes_policy']
    assert store.read_current()==before
