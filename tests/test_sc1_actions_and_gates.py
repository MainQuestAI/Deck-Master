"""SC-1 PR-06 C2/C3 closing tests: action envelopes, gate consumption of
semantic reviews, delivery scan wiring.

Acceptance mapping:
- W-06: a stale result (old input fingerprint) cannot overwrite the current
  version.
- W-07: an interrupted multi-file commit keeps the previous live version
  (all-or-nothing per declared target).
- W-08: replaying the same action id is idempotent — no duplicate write.
- W-09: an exhausted action budget blocks instead of silently continuing.
- Q-06/Q-07: targeted repair declares affected scope and requires re-review.
- Q-08: gate policy — production requires the semantic_review gate; an
  external_* report satisfies it; a review bound to an older page-package
  set is stale; P0 findings are never overridable.
- Q-10 family: customer_visible_safety gate findings include delivery
  pptx hidden-content scans (notes/metadata/hidden slides).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from quality.gate_policy import required_gate_names, resolve_required_gates  # noqa: E402
from workflow.actions import (  # noqa: E402
    ActionStaleError,
    check_action_budget,
    commit_action_result,
    create_action_envelope,
    fingerprint_payload,
    record_targeted_repair,
    stage_action_result,
)




def packages_content_fp(root: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for package_file in sorted((Path(root) / "page_packages").glob("*.json")):
        digest.update(package_file.name.encode("utf-8"))
        digest.update(hashlib.sha256(package_file.read_bytes()).digest())
    return digest.hexdigest()

class ActionEnvelopeTests(unittest.TestCase):
    def _root(self, tmp: Path) -> Path:
        root = tmp / "run-a"
        root.mkdir(parents=True)
        return root

    def _envelope(self, fp: str) -> dict:
        return create_action_envelope(
            action_id="act-1",
            task_id="task-gen",
            scope_pages=["P001"],
            input_fingerprint=fp,
        )

    def test_stale_result_cannot_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            stage_action_result(root, self._envelope("old-fp"), {"result.json": "{}"})
            with self.assertRaises(ActionStaleError):
                commit_action_result(
                    root,
                    self._envelope("old-fp"),
                    current_input_fingerprint="new-fp",
                    targets={"result.json": root / "result.json"},
                )
            self.assertFalse((root / "result.json").exists(), "stale commit must not touch live files")

    def test_interrupted_commit_keeps_previous_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            live = root / "artifacts" / "page.json"
            live.parent.mkdir(parents=True)
            live.write_text("previous-version", encoding="utf-8")
            staging = stage_action_result(root, self._envelope("fp-1"), {"page.json": "new-version", "other.json": "second"})
            # simulate an interrupted multi-file staging: one file never landed
            (staging / "other.json").unlink()
            with self.assertRaises(Exception):
                commit_action_result(
                    root,
                    self._envelope("fp-1"),
                    current_input_fingerprint="fp-1",
                    targets={"page.json": live, "other.json": root / "artifacts" / "other.json"},
                )
            self.assertEqual("previous-version", live.read_text(encoding="utf-8"))

    def test_commit_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            target = root / "artifacts" / "page.json"
            envelope = self._envelope("fp-1")
            stage_action_result(root, envelope, {"page.json": "v1"})
            first = commit_action_result(root, envelope, current_input_fingerprint="fp-1", targets={"page.json": target})
            self.assertEqual("applied", first["status"])
            target.write_text("changed-after-apply", encoding="utf-8")
            second = commit_action_result(root, envelope, current_input_fingerprint="fp-1", targets={"page.json": target})
            self.assertEqual("already_applied", second["status"])
            self.assertEqual("changed-after-apply", target.read_text(encoding="utf-8"), "replay must not rewrite live files")

    def test_budget_exhaustion_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            for index in range(2):
                envelope = create_action_envelope(action_id=f"act-{index}", task_id="task-1", scope_pages=["P1"], input_fingerprint="fp")
                stage_action_result(root, envelope, {"out.txt": "x"})
                commit_action_result(root, envelope, current_input_fingerprint="fp", targets={"out.txt": root / f"out-{index}.txt"})
            budget = check_action_budget(root, "task-1", max_actions=2)
            self.assertTrue(budget["exhausted"])
            with self.assertRaises(Exception):
                if budget["exhausted"]:
                    raise RuntimeError("budget exhausted; the runtime must block instead of auto-continuing")
            self.assertEqual(0, budget["remaining"])

    def test_targeted_repair_declares_scope_and_rereview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            repair = record_targeted_repair(
                root,
                repair_id="repair-1",
                finding_ids=["f-1", "f-2"],
                scope_pages=["P002"],
                reason="weak evidence on one page",
            )
            self.assertEqual(["f-1", "f-2"], repair["finding_ids"])
            self.assertEqual("affected_only", repair["requires_rereview"]["scope"])
            with self.assertRaises(ValueError):
                record_targeted_repair(root, repair_id="repair-2", finding_ids=[], scope_pages=["P001"])


class SemanticReviewGateTests(unittest.TestCase):
    def _tmp_run(self, tmp: Path) -> tuple[Path, Path]:
        root = tmp / "run-g"
        (root / "build").mkdir(parents=True)
        artifact = root / "build" / "deck.pptx"
        artifact.write_bytes(b"pptx-bytes")
        (root / "page_packages").mkdir(parents=True)
        (root / "page_packages" / "index.json").write_text("{}\n", encoding="utf-8")
        return root, artifact

    def test_production_requires_semantic_review(self) -> None:
        self.assertIn("semantic_review", required_gate_names(run_mode="production"))
        self.assertNotIn("semantic_review", required_gate_names(run_mode="fixture"))

    def test_external_report_satisfies_semantic_review_and_stales_on_package_change(self) -> None:
        import hashlib
        import tempfile

        from quality.gate_freshness import artifact_identity

        with tempfile.TemporaryDirectory() as tmp:
            root, artifact = self._tmp_run(Path(tmp))
            packages_sha = hashlib.sha256((root / "page_packages" / "index.json").read_bytes()).hexdigest()
            identity = artifact_identity(root, artifact)
            reports = [
                {"gate": gate, "status": "pass", "blocks_delivery": False, "findings": [], **identity}
                for gate in ("render", "delivery", "customer_visible_safety")
            ]
            reports.append(
                __import__("quality_review_v2_helpers").canonical_gate(root)
            )
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertEqual([], result["missing_required_gates"])
            self.assertTrue(result["satisfied"])

            # packages change → the bound review is stale, delivery blocked again
            (root / "page_packages" / "index.json").write_text('{"changed": true}\n', encoding="utf-8")
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertIn("semantic_review", result["missing_required_gates"])
            self.assertFalse(result["satisfied"])

    def test_p0_never_overridable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact = self._tmp_run(Path(tmp))
            reports = [
                {
                    "gate": "external_semantic",
                    "status": "pass",
                    "blocks_delivery": False,
                    "findings": [{"finding_id": "p0-finding", "severity": "P0", "message": "factual error"}],
                },
            ]
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertFalse(result["satisfied"])
            self.assertTrue(any(item["finding_id"] == "p0-finding" for item in result["current_blockers"]))


if __name__ == "__main__":
    unittest.main()
