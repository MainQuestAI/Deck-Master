"""Fault injection uses a compiler stub only to isolate rollback durability."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from build import migrate
from test_sc1_1_migration_apply import old_run
import workflow.actions as actions

@pytest.mark.parametrize("interruption", ["projection", "receipt", "response_lost", "process_exit", "projection_then_later_commit"])
def test_cli_rollback_resumes_after_pointer_switch(tmp_path, monkeypatch, interruption):
    import build.native_engine
    import runtime.build
    root = old_run(tmp_path)
    original = (root / "request.json").read_bytes()
    approved = (root / "approved.pptx").read_bytes()
    monkeypatch.setattr(build.native_engine, "_approved_packages", lambda root: [{"page_id": "P001"}])

    def compile_stub(candidate):
        (candidate / "new.pptx").write_bytes(b"transaction-only compiler stub")
        return {"status": "completed", "artifact_path": "new.pptx"}

    monkeypatch.setattr(runtime.build, "run_build", compile_stub)
    plan = migrate.build_migration_plan(root)
    applied = migrate.apply_migration(root, plan)
    write = migrate._write

    def interrupted_write(path, value):
        if path.name == "result.json" and value.get("status") == "rolled_back":
            if interruption == "response_lost":
                write(path, value)
            raise OSError("injected rollback receipt failure")
        return write(path, value)

    def interrupted_projection(root):
        raise OSError("injected rollback projection failure")

    if interruption == "process_exit":
        code = """import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from build import migrate
import workflow.actions as actions
assert Path(migrate.__file__).resolve() == Path(sys.argv[1]).resolve() / "build/migrate.py"
actions.recover_projections = lambda root: os._exit(73)
migrate.rollback_migration(sys.argv[2], sys.argv[3])
"""
        stopped = subprocess.run(
            [sys.executable, "-I", "-c", code, str(ROOT / "scripts"), str(root), plan["plan_id"]],
            cwd=tmp_path,
        )
        assert stopped.returncode == 73
    else:
        with monkeypatch.context() as fault:
            if interruption.startswith("projection"):
                fault.setattr(actions, "recover_projections", interrupted_projection)
            else:
                fault.setattr(migrate, "_write", interrupted_write)
            with pytest.raises(OSError, match="injected rollback"):
                migrate.rollback_migration(root, plan["plan_id"])
    assert actions.read_current_revision(root)["revision_id"] == applied["rollback_revision"]
    if interruption == "projection_then_later_commit":
        later = actions.create_action_envelope(action_id="later", task_id="later", scope_pages=["P001"], permission="runtime", input_fingerprint="later")
        actions.stage_action_result(root, later, {"request.json": '{"later": true}'})
        actions.commit_action_result(root, later, current_input_fingerprint="later", expected_revision=applied["rollback_revision"], targets={"request.json": root / "request.json"})
    retried = subprocess.run(
        [sys.executable, str(ROOT / "scripts/deck_master.py"), "build", "migrate",
         "--run-dir", str(root), "--rollback", "--migration-id", plan["plan_id"]],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "DECK_MASTER_DEV_SKIP_SETUP": "1"},
    )
    if interruption == "projection_then_later_commit":
        assert retried.returncode == 2, retried.stdout + retried.stderr
        assert json.loads(retried.stdout)["code"] == "ACTION_STALE"
        assert (root / "request.json").read_text() == '{"later": true}'
        assert (root / "approved.pptx").read_bytes() == approved
        return
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert json.loads(retried.stdout)["status"] == "rolled_back"
    assert migrate.verify_migration(root, plan["plan_id"])["status"] == "verified"
    assert (root / "request.json").read_bytes() == original
    assert not (root / "build/route.json").exists()
    assert (root / "approved.pptx").read_bytes() == approved
    assert (root / applied["artifact"]).is_file()
    assert migrate.rollback_migration(root, plan["plan_id"])["status"] == "rolled_back"
