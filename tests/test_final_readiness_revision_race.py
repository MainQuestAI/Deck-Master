"""Exercise real readiness and revision commits; no user approval is written."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from runtime import final_readiness
from test_revision_transactions import commit
from workflow.actions import read_current_revision


@pytest.mark.parametrize("write", [False, True])
def test_revision_commit_during_readiness_cannot_publish_ready(write):
    from test_final_readiness import FinalReadinessTests

    case = FinalReadinessTests()
    case.setUp()
    try:
        case._write_baseline()
        from runtime.build import run_build
        run_build(case.run_dir)
        # A fixture is sufficient for the transaction race; the separate real
        # native-run probe checks its render and export consumers too.
        first = commit(case.run_dir, "baseline", {"controlled-note.txt": "first"})
        baseline = final_readiness.compute_final_readiness(case.run_dir, write=False)
        assert baseline["ready"], baseline["blockers"]
        actual_validate = final_readiness.validate_delivery

        def concurrent_commit(*args, **kwargs):
            result = actual_validate(*args, **kwargs)
            commit(case.run_dir, "during-readiness", {"controlled-note.txt": "second"})
            return result

        with patch.object(final_readiness, "validate_delivery", concurrent_commit):
            result = final_readiness.compute_final_readiness(case.run_dir, write=write)
        assert read_current_revision(case.run_dir)["revision_id"] != first["revision_id"]
        assert result["ready"] is False
        assert result["status"] == "blocked"
        assert any(item["code"] == "final_revision_changed" for item in result["blockers"])
        saved = case.run_dir / final_readiness.FINAL_READINESS_PATH
        if write:
            assert json.loads(saved.read_text())["ready"] is False
        else:
            assert not saved.exists()
        assert not (case.run_dir / "delivery/final_approval.json").exists()
        assert not (case.run_dir / "final_artifact_approval.json").exists()
    finally:
        case.doCleanups()
