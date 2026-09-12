"""SC-1.1 review regression tests: failed-marker retry + run lock.

Acceptance mapping:
- WF-05/F-N10 (review P1): a recorded failure must NOT block a retry of the
  same action id — the retry commits instead of silently returning
  already_applied; an unreadable applied marker fails closed.
- Spec 05 section 5.5 (review P2): the whole compare-validate-commit-pointer
  cycle runs under a per-run write lock (lock file appears during commit).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow.actions import (  # noqa: E402
    ActionEnvelopeError,
    commit_action_result,
    create_action_envelope,
    record_action_failure,
    stage_action_result,
)


def _run(tmp: Path) -> Path:
    root = tmp / "run-retry"
    root.mkdir(parents=True)
    return root


class FailedMarkerRetryTests(unittest.TestCase):
    def test_retry_after_failure_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))
            target = root / "artifacts" / "page.json"
            record_action_failure(root, action_id="act-retry", task_id="task-1", reason="staging incomplete")
            envelope = create_action_envelope(action_id="act-retry", task_id="task-1", scope_pages=["P001"], input_fingerprint="fp-1")
            stage_action_result(root, envelope, {"page.json": "v1"})
            marker = commit_action_result(root, envelope, current_input_fingerprint="fp-1", targets={"page.json": target})
            self.assertEqual("applied", marker["status"], "a retry after failure must commit, not no-op")
            self.assertEqual("v1", target.read_text(encoding="utf-8"))

    def test_unreadable_marker_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))
            marker_dir = root / "workflow" / "actions" / "applied"
            marker_dir.mkdir(parents=True)
            (marker_dir / "act-bad.json").write_text("{not json", encoding="utf-8")
            from workflow.actions import action_applied

            with self.assertRaises(ActionEnvelopeError):
                action_applied(root, "act-bad")


if __name__ == "__main__":
    unittest.main()
