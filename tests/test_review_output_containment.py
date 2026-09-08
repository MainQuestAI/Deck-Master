import json
import pytest
from tests.test_quality_review_canonical import run
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

def test_task_directory_symlink_cannot_write_outside(tmp_path):
    from quality.external_review import prepare_quality_review_v2,TASK_DIR
    root=run(tmp_path);outside=tmp_path/'outside';outside.mkdir();task_dir=root/TASK_DIR
    task_dir.parent.mkdir(parents=True,exist_ok=True);task_dir.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ExternalReviewError):prepare_quality_review_v2(root,scope='semantic',required_page_ids=['P001','P002'])
    assert not list(outside.iterdir())

def test_archive_target_symlink_cannot_overwrite_external_file(tmp_path):
    from datetime import datetime,timezone,timedelta
    root=run(tmp_path);report=canonical_report(root);result=import_external_review(root,report)
    outside=tmp_path/'protected';outside.write_text('keep');archive=root/'quality_reports/archive';archive.mkdir()
    for delta in range(120):
        stamp=(datetime.now(timezone.utc)+timedelta(seconds=delta)).strftime('%Y%m%d%H%M%S')
        target=archive/(stamp+'_'+result['gate_report'])
        if not target.exists():target.symlink_to(outside)
    with pytest.raises(ExternalReviewError):import_external_review(root,report,replace=True)
    assert outside.read_text()=='keep'

def test_task_file_symlink_cannot_write_outside(tmp_path):
    from quality.external_review import prepare_quality_review_v2,TASK_DIR
    root=run(tmp_path);outside=tmp_path/'protected';outside.write_text('keep');task_dir=root/TASK_DIR;task_dir.mkdir(parents=True)
    (task_dir/'semantic_review_task.json').symlink_to(outside)
    with pytest.raises(ExternalReviewError):prepare_quality_review_v2(root,scope='semantic',required_page_ids=['P001','P002'])
    assert outside.read_text()=='keep'
