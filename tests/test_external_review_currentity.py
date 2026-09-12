"""Synthetic policy reports, not customer approvals."""
import copy
import json
import pytest
from quality_review_v2_helpers import canonical_gate
from quality.gate_freshness import report_currentity, artifact_identity
from quality.gate_policy import resolve_required_gates
from quality.external_review import validate_external_review_v2


def blocked(report, scope, severity='P1'):
    report=copy.deepcopy(report)
    report['gate']='external_'+scope
    report['scope']=scope
    report['status']='rework_required'
    report['blocks_delivery']=True
    canonical=report['canonical_review']
    canonical['scope']=scope.replace('_','-')
    canonical['summary']['reported_status']='rework_required'
    finding=dict(finding_id='retained-finding',severity=severity,dimension='solution_validity',object_refs=['P001'],message='Synthetic actual-input finding',evidence_refs=['page_packages/P001.json'],repair_action='rewrite_page',repair_instruction='Correct the controlled input',recheck='Check corrected input',allowed_scope_refs=['P001'])
    canonical['findings']=[finding]
    report['findings']=[copy.deepcopy(finding)]
    assert validate_external_review_v2(canonical)['valid']
    return report


def policy(root, reports):
    artifact=root/'deck.pptx'
    artifact.write_bytes(b'controlled artifact')
    base=[dict(gate=g,status='pass',blocks_delivery=False,findings=[],**artifact_identity(root,artifact)) for g in ['render','delivery','customer_visible_safety']]
    return resolve_required_gates(root,artifact,reports=base+reports,run_mode='production',output_profile='production_pptx',include_non_required_blockers=True)


@pytest.mark.parametrize('scope',['semantic','client_readiness','evidence','visual'])
def test_old_input_p1_does_not_block_current_pass(tmp_path,scope):
    old=blocked(canonical_gate(tmp_path),scope)
    (tmp_path/'page_packages/P001.json').write_text('{"page_id":"P001","title":"corrected"}')
    current=canonical_gate(tmp_path)
    result=policy(tmp_path,[old,current])
    assert result['satisfied']
    assert not result['current_blockers']
    assert report_currentity(tmp_path,old,tmp_path/'deck.pptx')['status']=='stale'


@pytest.mark.parametrize('scope',['semantic','client_readiness'])
@pytest.mark.parametrize('severity',['P0','P1'])
def test_current_input_blocker_survives_new_task_and_pass(tmp_path,scope,severity):
    old=blocked(canonical_gate(tmp_path),scope,severity)
    # Reissuing the task with identical bytes must not wash away the finding.
    current=canonical_gate(tmp_path)
    assert old['canonical_review']['review_action_id']!=current['canonical_review']['review_action_id']
    result=policy(tmp_path,[old,current])
    assert not result['satisfied']
    assert any(f['finding_id']=='retained-finding' for f in result['current_blockers'])
    assert report_currentity(tmp_path,old,tmp_path/'deck.pptx')['current']


def test_native_unbound_external_pass_cannot_be_current(tmp_path):
    canonical_gate(tmp_path)
    unbound={'gate':'external_semantic','status':'pass','blocks_delivery':False,'findings':[],'legacy_v1':True}
    assert report_currentity(tmp_path,unbound)['status']=='unbound'
    assert not policy(tmp_path,[unbound])['satisfied']

@pytest.mark.parametrize('scope',['semantic','client-readiness'])
def test_real_replace_cannot_remove_current_p1(tmp_path,scope):
    from quality_review_v2_helpers import canonical_report
    from quality.external_review import import_external_review, prepare_quality_review_v2, ExternalReviewError
    seed=canonical_gate(tmp_path)
    a=blocked(seed,scope.replace('-','_'))['canonical_review']
    task=prepare_quality_review_v2(tmp_path,scope=scope,required_page_ids=['P001'])
    a['review_action_id']=task['review_action_id']
    imported=import_external_review(tmp_path,a,replace=True)
    original=(tmp_path/'quality_reports'/imported['gate_report']).read_bytes()
    b=copy.deepcopy(a);b['findings']=[];b['summary']['reported_status']='pass'
    b['review_action_id']=prepare_quality_review_v2(tmp_path,scope=scope,required_page_ids=['P001'])['review_action_id']
    with pytest.raises(ExternalReviewError,match='current blocking findings'):
        import_external_review(tmp_path,b,replace=True)
    assert (tmp_path/'quality_reports'/imported['gate_report']).read_bytes()==original
    from quality.gate_policy import load_gate_reports
    assert not policy(tmp_path,load_gate_reports(tmp_path))['satisfied']


def test_real_replace_after_input_change_keeps_stale_history(tmp_path):
    from quality_review_v2_helpers import canonical_report
    from quality.external_review import import_external_review
    from quality.gate_policy import load_gate_reports
    a=blocked(canonical_gate(tmp_path),'semantic')['canonical_review']
    import_external_review(tmp_path,a,replace=True)
    (tmp_path/'page_packages/P001.json').write_text('{"page_id":"P001","title":"corrected"}')
    b=canonical_report(tmp_path,['P001'])
    import_external_review(tmp_path,b,replace=True)
    assert list((tmp_path/'quality_reports/archive').glob('*.json'))
    assert policy(tmp_path,load_gate_reports(tmp_path))['satisfied']


def test_existing_archived_current_blocker_is_consumed_even_with_explicit_reports(tmp_path):
    from quality.external_review import import_external_review
    from quality.gate_policy import load_gate_reports
    seed=canonical_gate(tmp_path)
    imported=import_external_review(tmp_path,blocked(seed,'semantic')['canonical_review'],replace=True)
    gate=tmp_path/'quality_reports'/imported['gate_report']
    # Reproduce a run archived by the previous implementation; keep exact bytes.
    archive=tmp_path/'quality_reports/archive/previous_external_semantic_gate.json'
    archive.write_bytes(gate.read_bytes())
    gate.unlink()
    current=canonical_gate(tmp_path)
    assert not policy(tmp_path,[current])['satisfied']
    assert not policy(tmp_path,load_gate_reports(tmp_path))['satisfied']

@pytest.mark.parametrize('bad_kind',['invalid_json','symlink'])
def test_archive_cannot_silently_ignore_unreadable_evidence(tmp_path,bad_kind):
    from quality.gate_policy import load_gate_reports
    canonical_gate(tmp_path)
    archive=tmp_path/'quality_reports/archive';archive.mkdir(exist_ok=True)
    path=archive/'bad_gate.json'
    if bad_kind=='invalid_json':
        path.write_text('{')
    else:
        target=tmp_path/'outside.json';target.write_text('{}');path.symlink_to(target)
    with pytest.raises(ValueError):
        load_gate_reports(tmp_path)


def test_archived_unbound_report_cannot_satisfy_native_gate(tmp_path):
    from quality.gate_policy import load_gate_reports
    canonical_gate(tmp_path)
    for p in (tmp_path/'quality_reports').glob('*_gate.json'):p.unlink()
    archive=tmp_path/'quality_reports/archive';archive.mkdir(exist_ok=True)
    (archive/'legacy_gate.json').write_text(json.dumps({'gate':'external_semantic','status':'pass','findings':[]}))
    assert not policy(tmp_path,load_gate_reports(tmp_path))['satisfied']


def test_rapid_replace_preserves_every_archive(tmp_path):
    from quality.external_review import import_external_review
    a=blocked(canonical_gate(tmp_path),'semantic')['canonical_review']
    archive=tmp_path/'quality_reports/archive'
    for _ in range(3):import_external_review(tmp_path,a,replace=True)
    files=list(archive.glob('*_gate.json'))
    assert len(files)==3
    assert sum(bool(json.loads(p.read_text())['findings']) for p in files)==2
