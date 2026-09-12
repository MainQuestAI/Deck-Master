"""The public evidence command must preserve read-only pending/failure semantics."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from test_evidence_bundle_validation import SHA, bundle, digest


@pytest.mark.parametrize("changed", [False, True])
def test_public_cli_reports_pending_or_stale_without_writing(tmp_path, changed):
    evidence, run = bundle(tmp_path)
    if changed:
        (run / "deck.pptx").write_bytes(b"different artifact")
    before = {str(path): (digest(path), path.stat().st_mtime_ns)
              for path in tmp_path.rglob("*") if path.is_file()}
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/deck_master.py"), "verify-evidence",
         "--evidence-root", str(evidence), "--candidate-sha", SHA,
         "--run", "main=" + str(run)], cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert result.returncode == (2 if changed else 0), result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == ("stale" if changed else "human_pending")
    assert payload["read_only"] is True
    assert before == {str(path): (digest(path), path.stat().st_mtime_ns)
                      for path in tmp_path.rglob("*") if path.is_file()}


def test_public_cli_rejects_duplicate_run_labels(tmp_path):
    evidence, run = bundle(tmp_path)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/deck_master.py"), "verify-evidence",
         "--evidence-root", str(evidence), "--candidate-sha", SHA,
         "--run", "main=" + str(run), "--run", "main=" + str(tmp_path / "other")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "unique LABEL=RUN_DIR" in result.stderr
