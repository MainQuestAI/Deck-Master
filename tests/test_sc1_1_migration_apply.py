"""Migration source safety tests: no compiler success is fabricated."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import migrate


def old_run(tmp_path):
    root = tmp_path / 'old-run'
    (root / 'build').mkdir(parents=True)
    (root / 'build/render_request.json').write_text('{}')
    (root / 'request.json').write_text(json.dumps({'run_id': 'old-run', 'run_mode': 'production'}))
    (root / 'approved.pptx').write_bytes(b'old approved bytes')
    return root


def test_plan_binds_source_and_preserves_artifact(tmp_path):
    root = old_run(tmp_path)
    before = list(root.rglob('*'))
    plan = migrate.build_migration_plan(root)
    assert plan['source_fingerprint']
    assert plan['preserved_files']['approved.pptx']
    assert plan['read_only'] is True
    assert before == list(root.rglob('*'))


def test_apply_rejects_stale_plan_before_writing(tmp_path):
    root = old_run(tmp_path)
    plan = migrate.build_migration_plan(root)
    (root / 'request.json').write_text('{}')
    with pytest.raises(ValueError, match='source_changed'):
        migrate.apply_migration(root, plan)
    assert not (root / 'build/migrations').exists()


def test_missing_sources_never_build_or_switch(tmp_path):
    root = old_run(tmp_path)
    result = migrate.apply_migration(root, migrate.build_migration_plan(root))
    assert result['status'] == 'blocked'
    assert not (root / 'build/route.json').exists()
    assert (root / 'approved.pptx').read_bytes() == b'old approved bytes'


def test_unknown_and_symlink_are_not_guessed(tmp_path):
    root = tmp_path / 'unknown'
    root.mkdir()
    assert migrate.build_migration_plan(root)['read_only']
    (root / 'escape').symlink_to(tmp_path)
    with pytest.raises(ValueError, match='symlink'):
        migrate.build_migration_plan(root)


def test_plan_tampering_rejected(tmp_path):
    root = old_run(tmp_path)
    plan = migrate.build_migration_plan(root)
    plan['target_profile'] = 'legacy-ppt-master'
    with pytest.raises(ValueError, match='plan_changed'):
        migrate.apply_migration(root, plan)


def test_candidate_build_failure_keeps_old_version(tmp_path, monkeypatch):
    import test_sc1_1_migration_and_chain as helpers
    root = helpers._hd_run(tmp_path)
    plan = migrate.build_migration_plan(root)
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    import runtime.build
    def fail(candidate):
        assert candidate != root
        assert candidate.name == root.name
        raise RuntimeError('renderer unavailable')
    monkeypatch.setattr(runtime.build, 'run_build', fail)
    with pytest.raises(RuntimeError, match='renderer unavailable'):
        migrate.apply_migration(root, plan)
    for name, data in before.items():
        assert (root / name).read_bytes() == data
    assert migrate.verify_migration(root, plan['plan_id'])['status'] == 'blocked'


def test_forged_plan_hash_cannot_add_arbitrary_source_paths(tmp_path):
    root = old_run(tmp_path)
    plan = migrate.build_migration_plan(root)
    plan['source_files']['../outside'] = 'bad'
    plan['plan_id'] = migrate._digest({k: v for k, v in plan.items() if k != 'plan_id'})
    with pytest.raises(ValueError, match='plan_changed'):
        migrate.apply_migration(root, plan)


def test_transaction_roundtrip_and_later_revision_guard(tmp_path, monkeypatch):
    """Stub compiler only: tests migration transaction, not production rendering."""
    import build.native_engine
    import runtime.build
    import workflow.actions as actions
    root = old_run(tmp_path)
    original = (root / 'request.json').read_bytes()
    monkeypatch.setattr(build.native_engine, '_approved_packages', lambda root: [{'page_id': 'P001'}])
    def compile_stub(candidate):
        (candidate / 'new.pptx').write_bytes(b'new test artifact')
        return {'status': 'completed', 'artifact_path': 'new.pptx'}
    monkeypatch.setattr(runtime.build, 'run_build', compile_stub)
    plan = migrate.build_migration_plan(root)
    result = migrate.apply_migration(root, plan)
    assert result['status'] == 'applied'
    assert migrate.verify_migration(root, plan['plan_id'])['status'] == 'verified'
    assert (root / 'approved.pptx').read_bytes() == b'old approved bytes'
    rolled_back = migrate.rollback_migration(root, plan['plan_id'])
    assert rolled_back['status'] == 'rolled_back'
    assert (root / 'request.json').read_bytes() == original
    assert not (root / 'build/route.json').exists()
    assert (root / result['artifact']).exists()
    assert (root / 'approved.pptx').read_bytes() == b'old approved bytes'


def test_result_receipt_recovers_after_report_write_loss(tmp_path, monkeypatch):
    import build.native_engine
    import runtime.build
    root = old_run(tmp_path)
    monkeypatch.setattr(build.native_engine, '_approved_packages', lambda root: [{'page_id': 'P001'}])
    def compile_stub(candidate):
        (candidate / 'new.pptx').write_bytes(b'transaction fixture')
        return {'status': 'completed', 'artifact_path': 'new.pptx'}
    monkeypatch.setattr(runtime.build, 'run_build', compile_stub)
    plan = migrate.build_migration_plan(root)
    migrate.apply_migration(root, plan)
    (root / 'build/migrations' / plan['plan_id'] / 'result.json').unlink()
    assert migrate.verify_migration(root, plan['plan_id'])['status'] == 'verified'
    assert migrate.rollback_migration(root, plan['plan_id'])['status'] == 'rolled_back'


def test_rollback_refuses_to_overwrite_later_action(tmp_path, monkeypatch):
    import build.native_engine
    import runtime.build
    import workflow.actions as actions
    root = old_run(tmp_path)
    monkeypatch.setattr(build.native_engine, '_approved_packages', lambda root: [{'page_id': 'P001'}])
    def compile_stub(candidate):
        (candidate / 'new.pptx').write_bytes(b'transaction fixture')
        return {'status': 'completed', 'artifact_path': 'new.pptx'}
    monkeypatch.setattr(runtime.build, 'run_build', compile_stub)
    plan = migrate.build_migration_plan(root)
    result = migrate.apply_migration(root, plan)
    envelope = actions.create_action_envelope(action_id='later', task_id='later', scope_pages=['P001'], input_fingerprint='later', permission='runtime')
    actions.stage_action_result(root, envelope, {'request.json': b'{"later": true}'})
    actions.commit_action_result(root, envelope, current_input_fingerprint=lambda: 'later', targets={'request.json': root / 'request.json'}, expected_revision=result['revision_id'])
    with pytest.raises(actions.ActionStaleError):
        migrate.rollback_migration(root, plan['plan_id'])
    assert (root / 'request.json').read_bytes() == b'{"later": true}'
