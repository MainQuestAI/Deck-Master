from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so `runtime.next_step` imports work.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime.next_step import resolve_next_step, SCHEMA_VERSION  # noqa: E402
from runtime.run_state import (  # noqa: E402
    REQUEST_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    CLAIM_MAP_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    SOURCING_PLAN_NAME,
    PREVIEW_MANIFEST_NAME,
)


REQUIRED_KEYS = {"schema_version", "run_id", "status", "next_command", "missing_artifacts", "blocking_issues"}


class NextStepResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(tempfile.mkdtemp(prefix="deck_next_step_test_"))
        self.run_dir = self.tmp_root / "test-run"
        self.run_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _write_json(self, name: str, payload: dict) -> None:
        (self.run_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    def _write_gate(self, name: str = "draft_gate.json", *, status: str = "pass", blocks: bool = False) -> None:
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / name).write_text(
            json.dumps({"status": status, "blocks_delivery": blocks, "findings": []}),
            encoding="utf-8",
        )

    def _write_bound_gate(self, gate: str, artifact: Path) -> None:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        rel = artifact.relative_to(self.run_dir).as_posix()
        (quality_dir / f"{gate}_gate.json").write_text(
            json.dumps(
                {
                    "gate": gate,
                    "status": "pass",
                    "blocks_delivery": False,
                    "findings": [],
                    "artifact_path": rel,
                    "artifact_run_relative": rel,
                    "artifact_sha256": digest,
                    "artifact_binding": {
                        "artifact_run_relative": rel,
                        "artifact_sha256": digest,
                        "source_fingerprint": "",
                        "build_manifest_sha256": "",
                        "artifact_manifest_sha256": "",
                    },
                }
            ),
            encoding="utf-8",
        )

    def _write_generation_ready_for_build(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"page_id": "p1", "decision": "approved"}]})
        tasks_dir = self.run_dir / "generation_tasks"
        tasks_dir.mkdir()
        (tasks_dir / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False, "created_at": "2026-06-17T10:01:00+00:00"}),
            encoding="utf-8",
        )

    def _resolve(self, *, run_mode: str = "fixture") -> dict:
        return resolve_next_step(self.run_dir, run_mode=run_mode)

    def _assert_shape(self, result: dict, expected_status: str) -> None:
        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()), f"Missing keys in {result}")
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["status"], expected_status)

    def test_empty_run_dir_returns_needs_request(self) -> None:
        result = self._resolve()
        self._assert_shape(result, "needs_request")
        self.assertIn(REQUEST_NAME, result["missing_artifacts"])

    def test_has_request_missing_context_returns_needs_context(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        result = self._resolve()
        self._assert_shape(result, "needs_context")
        self.assertIn(CONTEXT_MANIFEST_NAME, result["missing_artifacts"])

    def test_has_context_missing_brief_returns_needs_brief(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        result = self._resolve()
        self._assert_shape(result, "needs_brief")
        self.assertIn(DECK_BRIEF_NAME, result["missing_artifacts"])
        self.assertEqual("deck-brief", result["recommended_skill"])

    def test_has_brief_missing_claim_map_returns_needs_claim_map(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        result = self._resolve()
        self._assert_shape(result, "needs_claim_map")
        self.assertIn(CLAIM_MAP_NAME, result["missing_artifacts"])

    def test_has_claim_map_missing_narrative_plan_returns_needs_narrative_plan(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        result = self._resolve()
        self._assert_shape(result, "needs_narrative_plan")
        self.assertIn(NARRATIVE_PLAN_NAME, result["missing_artifacts"])

    def test_has_narrative_plan_missing_page_tasks_returns_needs_page_tasks(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        result = self._resolve()
        self._assert_shape(result, "needs_page_tasks")
        self.assertIn(PAGE_TASKS_NAME, result["missing_artifacts"])

    def test_has_page_tasks_missing_sourcing_returns_needs_sourcing(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        self._write_json(PAGE_TASKS_NAME, {"tasks": []})
        result = self._resolve()
        self._assert_shape(result, "needs_sourcing")
        self.assertIn(SOURCING_PLAN_NAME, result["missing_artifacts"])

    def test_has_sourcing_missing_preview_returns_needs_preview(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        self._write_json(PAGE_TASKS_NAME, {"tasks": []})
        self._write_json(SOURCING_PLAN_NAME, {"sources": []})
        result = self._resolve()
        self._assert_shape(result, "needs_preview")
        self.assertIn(PREVIEW_MANIFEST_NAME, result["missing_artifacts"])

    def _write_full_pipeline(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        self._write_json(PAGE_TASKS_NAME, {"tasks": []})
        self._write_json(SOURCING_PLAN_NAME, {"sources": []})

    def test_preview_with_approved_and_pending_pages_returns_needs_page_review(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}, {"decision": "pending"}]})
        self._write_gate()
        result = self._resolve()
        self._assert_shape(result, "needs_page_review")
        self.assertEqual(result.get("approved_pages"), 1)
        self.assertIn("run-state", result["next_command"])

    def test_preview_without_approved_and_draft_gate_returns_needs_page_review(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "pending"}]})
        self._write_gate()
        result = self._resolve()
        self._assert_shape(result, "needs_page_review")
        self.assertIn("run-state", result["next_command"])

    def test_preview_without_approved_and_missing_draft_gate_returns_needs_draft_gate(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "pending"}]})
        result = self._resolve()
        self._assert_shape(result, "needs_page_review")
        self.assertIn("run-state", result["next_command"])

    def test_approved_page_without_draft_gate_returns_needs_draft_gate(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}]})
        result = self._resolve()
        self._assert_shape(result, "needs_draft_gate")
        self.assertNotEqual("ready_to_export", result["status"])

    def test_blocking_draft_gate_returns_needs_quality_review(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}]})
        self._write_gate(status="rework_required", blocks=True)
        result = self._resolve()
        self._assert_shape(result, "needs_quality_review")
        self.assertIn("draft gate blocks delivery", result["blocking_issues"][0])

    def test_draft_v2_gate_is_supported(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}]})
        self._write_gate("draft_v2_gate.json")
        result = self._resolve()
        self._assert_shape(result, "ready_to_export")

    def test_generation_ready_for_build_returns_needs_build(self) -> None:
        self._write_generation_ready_for_build()

        result = self._resolve()

        self._assert_shape(result, "needs_build")
        self.assertEqual("needs_build", result["runtime_stage"])
        self.assertEqual("deck-builder", result["recommended_skill"])
        self.assertIn("build prepare", result["next_command"])

    def test_prepared_build_without_render_returns_needs_render(self) -> None:
        self._write_generation_ready_for_build()
        build_dir = self.run_dir / "build"
        build_dir.mkdir()
        (build_dir / "build_manifest.json").write_text(
            json.dumps({"schema_version": "deck_build_manifest.v1", "run_id": "r1"}),
            encoding="utf-8",
        )

        result = self._resolve()

        self._assert_shape(result, "needs_render")
        self.assertEqual("needs_render", result["runtime_stage"])
        self.assertEqual("deck-builder", result["recommended_skill"])
        self.assertIn("build run", result["next_command"])

    def test_completed_high_density_with_only_semantic_gate_missing_returns_review_action(self) -> None:
        # SC-1.1 F-N06 regression: only semantic_review missing -> the next
        # action is preparing the v2 review, not a render gate.
        status_path = self.run_dir / "high_density_build" / "status.json"
        status_path.parent.mkdir(parents=True)
        self._write_json(REQUEST_NAME, {"run_id": "r1", "run_mode": "production"})
        status_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_high_density_status.v2",
                    "run_id": "r1",
                    "builder_profile": "high_density",
                    "status": "completed",
                    "current_stage": "pptx",
                    "next_action": {"kind": "complete"},
                }
            ),
            encoding="utf-8",
        )
        pptx_path = self.run_dir / "high_density_build" / "pptx" / "deck_high_density.pptx"
        pptx_path.parent.mkdir(parents=True)
        pptx_path.write_bytes(b"pptx")
        (self.run_dir / "quality_reports").mkdir(exist_ok=True)
        for gate in ("render_gate.json", "delivery_gate.json", "customer_visible_safety_gate.json"):
            digest = hashlib.sha256(pptx_path.read_bytes()).hexdigest()
            rel = pptx_path.relative_to(self.run_dir).as_posix()
            (self.run_dir / "quality_reports" / gate).write_text(
                json.dumps(
                    {
                        "gate": gate.removesuffix("_gate.json"),
                        "status": "pass",
                        "blocks_delivery": False,
                        "findings": [],
                        "artifact_path": rel,
                        "artifact_sha256": digest,
                    }
                ),
                encoding="utf-8",
            )

        result = self._resolve(run_mode="production")

        self._assert_shape(result, "needs_quality_review")
        self.assertIn("prepare-quality-review", result["next_command"])

    def test_completed_high_density_with_only_safety_gate_returns_render_gate(self) -> None:
        status_path = self.run_dir / "high_density_build" / "status.json"
        status_path.parent.mkdir(parents=True)
        self._write_json(REQUEST_NAME, {"run_id": "r1", "run_mode": "production"})
        status_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_high_density_status.v2",
                    "run_id": "r1",
                    "builder_profile": "high_density",
                    "status": "completed",
                    "current_stage": "pptx",
                    "next_action": {"kind": "complete"},
                }
            ),
            encoding="utf-8",
        )
        pptx_path = self.run_dir / "high_density_build" / "pptx" / "deck_high_density.pptx"
        pptx_path.parent.mkdir(parents=True)
        pptx_path.write_bytes(b"pptx")
        self._write_gate("customer_visible_safety_gate.json")

        result = self._resolve(run_mode="production")

        self._assert_shape(result, "needs_quality_review")
        self.assertIn("quality-gate render", result["next_command"])

    def test_completed_high_density_with_current_render_gate_returns_final_readiness(self) -> None:
        status_path = self.run_dir / "high_density_build" / "status.json"
        status_path.parent.mkdir(parents=True)
        self._write_json(REQUEST_NAME, {"run_id": "r1", "run_mode": "production"})
        status_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_high_density_status.v2",
                    "run_id": "r1",
                    "builder_profile": "high_density",
                    "status": "completed",
                    "current_stage": "pptx",
                    "next_action": {"kind": "complete"},
                }
            ),
            encoding="utf-8",
        )
        pptx_path = self.run_dir / "high_density_build" / "pptx" / "deck_high_density.pptx"
        pptx_path.parent.mkdir(parents=True)
        pptx_path.write_bytes(b"pptx")
        self._write_bound_gate("render", pptx_path)
        self._write_bound_gate("delivery", pptx_path)
        self._write_bound_gate("customer_visible_safety", pptx_path)
        # A hash-only legacy pass cannot satisfy the current independent review.
        (self.run_dir / "quality_reports" / "external_semantic_gate.json").write_text(
            json.dumps({"gate":"external_semantic", "status":"pass", "blocks_delivery":False,
                        "findings":[], "content_fingerprint":"legacy-hash"}), encoding="utf-8")
        self._assert_shape(self._resolve(run_mode="production"), "needs_quality_review")
        from quality_review_v2_helpers import canonical_gate
        canonical_gate(self.run_dir)

        result = self._resolve(run_mode="production")

        self._assert_shape(result, "ready_for_final_readiness")
        self.assertIn("final-readiness", result["next_command"])

    def test_result_always_contains_required_keys(self) -> None:
        # Verify across multiple states that the shape is stable.
        for setup_fn, _ in [
            (lambda: None, "needs_request"),
            (lambda: self._write_json(REQUEST_NAME, {"run_id": "x"}), "needs_context"),
        ]:
            setup_fn()
            result = self._resolve()
            self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))
            # Reset for next iteration.
            for child in list(self.run_dir.iterdir()):
                if child.is_file():
                    child.unlink()


if __name__ == "__main__":
    unittest.main()
