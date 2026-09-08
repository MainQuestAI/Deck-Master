import json
import pytest
from test_quality_review_canonical import run
from quality_review_v2_helpers import canonical_report
from quality.external_review import import_external_review, ExternalReviewError

@pytest.mark.parametrize('name',['x/../../outside','x\\..\\outside','..','/absolute'])
def test_reviewer_cannot_choose_output_path(tmp_path,name):
    root=run(tmp_path);report=canonical_report(root);report['reviewer_session_id']=name
    with pytest.raises(ExternalReviewError):import_external_review(root,report)
    assert not list(tmp_path.glob('*_gate.json'))

def test_review_directory_symlink_cannot_write_outside(tmp_path):
    root=run(tmp_path);report=canonical_report(root)
    outside=tmp_path/'outside';outside.mkdir()
    (root/'quality_reports').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ExternalReviewError):import_external_review(root,report)
    assert not list(outside.iterdir())
