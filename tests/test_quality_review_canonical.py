import copy,json,sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import pytest
from jsonschema import Draft202012Validator
from native_pptx.contracts import SCHEMA_DIR
from quality_review_v2_helpers import canonical_report
from quality.external_review import validate_external_review,validate_external_review_v2,prepare_quality_review_v2,import_external_review,ExternalReviewError

def run(tmp_path):
    root=tmp_path/'review-run';(root/'page_packages').mkdir(parents=True)
    (root/'request.json').write_text('{"run_id":"review-run","run_mode":"production"}')
    for page in ['P001','P002']:(root/'page_packages'/f'{page}.json').write_text(json.dumps({'page_id':page}))
    return root

def test_canonical_result_passes_public_validator():
    report=canonical_report()
    Draft202012Validator(json.loads((SCHEMA_DIR/'external-quality-review.v2.schema.json').read_text())).validate(report)
    assert validate_external_review(report)['valid']

def test_prepare_is_separate_task_schema(tmp_path):
    root=run(tmp_path);task=prepare_quality_review_v2(root,scope='semantic',required_page_ids=['P001','P002'])
    assert task['schema_version']=='deck_external_quality_review_task.v2'
    Draft202012Validator(json.loads((SCHEMA_DIR/'external-quality-review-task.v2.schema.json').read_text())).validate(task)
    assert not validate_external_review(task)['valid']

@pytest.mark.parametrize('mutation', ['skip','self','severity','missing_input','wrong_fingerprint'])
def test_invalid_review_cannot_satisfy_contract(mutation):
    report=canonical_report()
    if mutation=='skip':report['coverage']['reviewed_page_ids']=['P001'];report['coverage']['skipped']=[{'ref':'P002','reason':'not read'}]
    if mutation=='self':report['reviewer_session_id']=report['producer_session_id']
    if mutation=='severity':report['findings']=[{'finding_id':'bad','severity':'P9','dimension':'evidence_quality','object_refs':['P001'],'message':'Bad evidence','evidence_refs':[],'repair_action':'read_source','repair_instruction':'Read original source','recheck':'Check quote','allowed_scope_refs':['P001']}]
    if mutation=='missing_input':report['reviewed_inputs']=report['reviewed_inputs'][:1]
    if mutation=='wrong_fingerprint':report['based_on']['input_fingerprint']='b'*64
    assert not validate_external_review_v2(report)['valid']

def test_empty_rework_remains_blocking(tmp_path):
    root=run(tmp_path);report=canonical_report(root)
    report['summary']['reported_status']='rework_required'
    result=import_external_review(root,report)
    gate=json.loads((root/'quality_reports'/result['gate_report']).read_text())
    assert gate['status']=='rework_required' and gate['blocks_delivery']

def test_actual_page_omission_rejected_even_self_declared_complete(tmp_path):
    root=run(tmp_path)
    with pytest.raises(ExternalReviewError):prepare_quality_review_v2(root,scope='semantic',required_page_ids=['P001'])

def test_stale_or_unissued_report_rejected(tmp_path):
    root=run(tmp_path);report=canonical_report(root)
    report['review_action_id']='not-issued'
    with pytest.raises(ExternalReviewError):import_external_review(root,report)
    report=canonical_report(root)
    (root/'page_packages/P002.json').write_text('{"page_id":"P002","text":"changed"}')
    with pytest.raises(ExternalReviewError):import_external_review(root,report)


def test_self_review_kind_is_not_independent_even_with_two_ids():
    report=canonical_report();report['review_kind']='producer_self'
    assert not validate_external_review_v2(report)['valid']


def test_skipped_rework_can_be_retained_but_never_passes_gate(tmp_path):
    root=run(tmp_path);report=canonical_report(root)
    report['summary']['reported_status']='rework_required'
    report['coverage']['reviewed_page_ids']=['P001']
    report['coverage']['skipped']=[{'ref':'P002','reason':'Source unread'}]
    result=import_external_review(root,report)
    gate=json.loads((root/'quality_reports'/result['gate_report']).read_text())
    assert gate['status']=='rework_required' and gate['blocks_delivery']
    assert gate['canonical_review']['coverage']['skipped']


def test_old_or_tampered_gate_cannot_supply_canonical_review(tmp_path):
    from quality.gate_policy import _semantic_review_input_current
    from quality_review_v2_helpers import canonical_gate
    root=run(tmp_path);gate=canonical_gate(root)
    assert _semantic_review_input_current(root,gate)
    old=copy.deepcopy(gate);old.pop('canonical_review')
    assert not _semantic_review_input_current(root,old)
    disguised=copy.deepcopy(gate)
    disguised['canonical_review']['reviewer_session_id']=disguised['canonical_review']['producer_session_id']
    assert not _semantic_review_input_current(root,disguised)
    prepare_quality_review_v2(root,scope='semantic',required_page_ids=['P001','P002'])
    assert not _semantic_review_input_current(root,gate)
