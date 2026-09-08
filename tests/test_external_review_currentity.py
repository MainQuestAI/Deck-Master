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
