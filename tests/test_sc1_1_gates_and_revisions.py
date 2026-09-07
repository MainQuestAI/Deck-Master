"""SC-1.1 ND-04 tests (failing-first): precise semantic gate matching and
atomic revision commit with failure-budget accounting.

Acceptance mapping:
- QA-02/F-N09: only a report whose scope is semantic satisfies the
  semantic_review gate — external_visual/external_evidence must never be
  accepted through the external_* prefix; a report bound to a stale page
  package set (or stale per-page content hashes) is stale.
- QA-03/WF-05/F-N10: multi-file actions commit through a single revision
  pointer — an interrupted second file leaves readers on the complete old
  revision; failed attempts count against the budget.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.gate_policy import resolve_required_gates  # noqa: E402
from workflow.actions import (  # noqa: E402
    ActionEnvelopeError,
    check_action_budget,
    commit_action_result,
    create_action_envelope,
    stage_action_result,
)


def _run(tmp: Path) -> tuple[Path, Path]:
    root = tmp / "run-nd04"
    (root / "build").mkdir(parents=True)
    artifact = root / "build" / "deck.pptx"
    artifact.write_bytes(b"pptx")
    (root / "page_packages").mkdir(parents=True)
    (root / "page_packages" / "index.json").write_text("{}\n", encoding="utf-8")
    return root, artifact


class SemanticGatePrecisionTests(unittest.TestCase):
    def test_external_visual_cannot_satisfy_semantic_review(self) -> None:
        import hashlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, artifact = _run(Path(tmp))
            from quality.gate_freshness import artifact_identity

            identity = artifact_identity(root, artifact)
            reports = [
                {"gate": g, "status": "pass", "blocks_delivery": False, "findings": [], **identity}
                for g in ("render", "delivery", "customer_visible_safety")
            ]
            packages_sha = hashlib.sha256((root / "page_packages" / "index.json").read_bytes()).hexdigest()
            reports.append(
                {"gate": "external_visual", "status": "pass", "blocks_delivery": False, "findings": [], "based_on_sha256": packages_sha}
            )
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertIn("semantic_review", result["missing_required_gates"], "visual review must not satisfy the semantic gate")

    def test_external_semantic_satisfies_semantic_review(self) -> None:
        import hashlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root, artifact = _run(Path(tmp))
            from quality.gate_freshness import artifact_identity

            identity = artifact_identity(root, artifact)
            packages_sha = hashlib.sha256((root / "page_packages" / "index.json").read_bytes()).hexdigest()
            reports = [
                {"gate": g, "status": "pass", "blocks_delivery": False, "findings": [], **identity}
                for g in ("render", "delivery", "customer_visible_safety")
            ]
            reports.append(
                {"gate": "external_semantic", "status": "pass", "blocks_delivery": False, "findings": [], "based_on_sha256": packages_sha}
            )
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertNotIn("semantic_review", result["missing_required_gates"])


class RevisionPointerCommitTests(unittest.TestCase):
    def test_commit_writes_revision_pointer_and_keeps_projection_consistent(self) -> None:
        import tempfile

        from workflow.actions import read_current_revision, stage_action_result

        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))[0]
            target_a = root / "artifacts" / "a.json"
            target_b = root / "artifacts" / "b.json"
            envelope = create_action_envelope(action_id="act-multi", task_id="task-1", scope_pages=["P001"], input_fingerprint="fp-1")
            staging = stage_action_result(root, envelope, {"a.json": "v1-a", "b.json": "v1-b"})
            marker = commit_action_result(
                root,
                envelope,
                current_input_fingerprint="fp-1",
                targets={"a.json": target_a, "b.json": target_b},
            )
            revision = marker.get("revision_id")
            self.assertTrue(revision, "a committed action must record a revision id")
            pointer = read_current_revision(root)
            self.assertEqual(revision, pointer["revision_id"])
            # a partial-staging retry that fails must leave the pointer intact
            envelope2 = create_action_envelope(action_id="act-2", task_id="task-1", scope_pages=["P001"], input_fingerprint="fp-1")
            staging2 = stage_action_result(root, envelope2, {"a.json": "v2-a", "b.json": "v2-b"})
            import json as _json

            (staging2 / "b.json").unlink()  # interrupted staging
            try:
                commit_action_result(root, envelope2, current_input_fingerprint="fp-1", targets={"a.json": target_a, "b.json": target_b})
                committed = True
            except ActionEnvelopeError:
                committed = False
            self.assertFalse(committed)
            self.assertEqual(revision, read_current_revision(root)["revision_id"], "failed attempt must not move the pointer")

    def test_failed_attempts_count_toward_budget(self) -> None:
        import tempfile

        from workflow.actions import check_action_budget, record_action_failure

        with tempfile.TemporaryDirectory() as tmp:
            root = _run(Path(tmp))[0]
            record_action_failure(root, action_id="act-f1", task_id="task-1", reason="stale result rejected")
            record_action_failure(root, action_id="act-f2", task_id="task-1", reason="staging incomplete")
            budget = check_action_budget(root, "task-1", max_actions=2)
            self.assertTrue(budget["exhausted"], "failed attempts must consume budget")
            self.assertEqual(2, budget["used"])


if __name__ == "__main__":
    unittest.main()
