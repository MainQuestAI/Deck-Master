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

def test_archive_target_symlink_cannot_overwrite_external_file(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from uuid import UUID
    import quality.external_review as external_review
    root=run(tmp_path);report=canonical_report(root);result=import_external_review(root,report)
    gate = root / 'quality_reports' / result['gate_report']
    original_gate = gate.read_bytes()
    outside=tmp_path/'protected';outside.write_text('keep');archive=root/'quality_reports/archive';archive.mkdir()
    fixed = datetime(2026, 9, 9, 12, 0, 0, 123456, tzinfo=timezone.utc)
    identity = UUID('01234567-89ab-cdef-0123-456789abcdef')
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed
    monkeypatch.setattr(external_review, 'datetime', FixedDatetime)
    monkeypatch.setattr(external_review.uuid, 'uuid4', lambda: identity)
    target = archive / (fixed.strftime('%Y%m%d%H%M%S%f') + '_' + identity.hex + '_' + result['gate_report'])
    target.symlink_to(outside)
    with pytest.raises(ExternalReviewError, match='archive target escapes'):
        import_external_review(root,report,replace=True)
    assert outside.read_bytes() == b'keep'
    assert target.is_symlink()
    assert gate.read_bytes() == original_gate

def test_task_file_symlink_cannot_write_outside(tmp_path):
    from quality.external_review import prepare_quality_review_v2,TASK_DIR
    root=run(tmp_path);outside=tmp_path/'protected';outside.write_text('keep');task_dir=root/TASK_DIR;task_dir.mkdir(parents=True)
    (task_dir/'semantic_review_task.json').symlink_to(outside)
    with pytest.raises(ExternalReviewError):prepare_quality_review_v2(root,scope='semantic',required_page_ids=['P001','P002'])
    assert outside.read_text()=='keep'
