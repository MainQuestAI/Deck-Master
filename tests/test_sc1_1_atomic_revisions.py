"""SC-1.1 batch-2.1 tests (failing-first): true batch-atomic revision commit.

Acceptance mapping (review P1-03 / spec 05 section 5.5):
- Commit order: build+validate the COMPLETE immutable revision FIRST, then
  activate with ONE pointer switch. A failure at ANY point (second live
  file, revision creation, pointer write, process death) must leave readers
  on the complete OLD revision — never a mixed old/new projection.
- revision_id incorporates the TARGET run-relative paths (same content
  written to different pages must NOT share a revision identity).
- Failure accounting: repeated failures of the same action append to an
  attempt ledger (each attempt counted); the commit path ENFORCES the task
  budget (exhausted budget blocks the commit, not just reports).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workflow.actions import (  # noqa: E402
    ActionBudgetExhaustedError,
    ActionEnvelopeError,
    check_action_budget,
    commit_action_result,
    create_action_envelope,
    read_current_revision,
    record_action_failure,
    stage_action_result,
)


def _run(tmp: Path) -> Path:
    root = tmp / "run-atomic"
    root.mkdir(parents=True)
    return root


def _envelope(action_id: str, fp: str = "fp-1") -> dict:
    return create_action_envelope(action_id=action_id, task_id="task-1", scope_pages=["P001"], input_fingerprint=fp)


class AtomicCommitOrderTests(unittest.TestCase):
    def test_second_live_file_failure_leaves_old_revision_complete(self) -> None:
        import shutil as _shutil

        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))
            target_a = root / "artifacts" / "a.json"
            target_b = root / "artifacts" / "b.json"
            # v1 committed
            env1 = _envelope("act-1")
            stage_action_result(root, env1, {"a.json": "v1-a", "b.json": "v1-b"})
            commit_action_result(root, env1, current_input_fingerprint="fp-1", targets={"a.json": target_a, "b.json": target_b})
            old_revision = read_current_revision(root)["revision_id"]

            # v2 attempt fails while writing the SECOND live projection
            env2 = _envelope("act-2")
            stage_action_result(root, env2, {"a.json": "v2-a", "b.json": "v2-b"})
            real_replace = Path.replace

            def failing_second_replace(self, target):  # noqa: ANN001
                if "b.json" in str(target):
                    raise OSError("injected second-file failure")
                return real_replace(self, target)

            with mock.patch.object(Path, "replace", failing_second_replace):
                try:
                    commit_action_result(root, env2, current_input_fingerprint="fp-1", targets={"a.json": target_a, "b.json": target_b})
                except OSError:
                    pass
            # readers resolve via the pointer: complete OLD revision
            self.assertEqual(old_revision, read_current_revision(root)["revision_id"])
            # SC-1.1 review round 2: the LIVE files themselves must be
            # complete old content — a production reader on fixed paths
            # must never see a mixed new/old set after the injected failure
            self.assertEqual("v1-a", target_a.read_text(encoding="utf-8"), "live a.json must be rolled back")
            self.assertEqual("v1-b", target_b.read_text(encoding="utf-8"), "live b.json must be restored")
            revisions_dir = root / "build" / "revisions" / old_revision
            self.assertEqual("v1-a", (revisions_dir / "a.json").read_text(encoding="utf-8"))
            self.assertEqual("v1-b", (revisions_dir / "b.json").read_text(encoding="utf-8"))
            # revision-state resolver: full state via parent chain
            from workflow.actions import read_revision_state

            state = read_revision_state(root)
            self.assertEqual(b"v1-a", state["a.json"])
            self.assertEqual(b"v1-b", state["b.json"])

    def test_revision_identity_includes_target_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))
            env_p1 = _envelope("act-p1")
            stage_action_result(root, env_p1, {"svg": "<svg>P</svg>"})
            marker1 = commit_action_result(
                root, env_p1, current_input_fingerprint="fp-1",
                targets={"svg": root / "high_density_build" / "svg" / "P001.svg"},
            )
            env_p2 = _envelope("act-p2")
            stage_action_result(root, env_p2, {"svg": "<svg>P</svg>"})
            marker2 = commit_action_result(
                root, env_p2, current_input_fingerprint="fp-1",
                targets={"svg": root / "high_density_build" / "svg" / "P002.svg"},
            )
            self.assertNotEqual(marker1["revision_id"], marker2["revision_id"], "same content at different targets must be distinct revisions")


class AttemptLedgerTests(unittest.TestCase):
    def test_repeated_failures_each_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))
            for index in range(4):
                record_action_failure(root, action_id="act-flaky", task_id="task-1", reason=f"attempt {index}")
            budget = check_action_budget(root, "task-1", max_actions=4)
            self.assertEqual(4, budget["used"], "every failed attempt must be counted")

    def test_commit_enforces_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))
            for index in range(2):
                record_action_failure(root, action_id=f"act-f{index}", task_id="task-1", reason="stale")
            envelope = create_action_envelope(
                action_id="act-new", task_id="task-1", scope_pages=["P001"], input_fingerprint="fp-1",
                budget={"max_actions": 2},
            )
            stage_action_result(root, envelope, {"out.txt": "x"})
            with self.assertRaises(ActionBudgetExhaustedError):
                commit_action_result(root, envelope, current_input_fingerprint="fp-1", targets={"out.txt": root / "out.txt"})


if __name__ == "__main__":
    unittest.main()
