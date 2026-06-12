from __future__ import annotations

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

    def _assert_shape(self, result: dict, expected_status: str) -> None:
        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()), f"Missing keys in {result}")
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["status"], expected_status)

    def test_empty_run_dir_returns_needs_request(self) -> None:
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_request")
        self.assertIn(REQUEST_NAME, result["missing_artifacts"])

    def test_has_request_missing_context_returns_needs_context(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_context")
        self.assertIn(CONTEXT_MANIFEST_NAME, result["missing_artifacts"])

    def test_has_context_missing_brief_returns_needs_brief(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_brief")
        self.assertIn(DECK_BRIEF_NAME, result["missing_artifacts"])

    def test_has_brief_missing_claim_map_returns_needs_claim_map(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_claim_map")
        self.assertIn(CLAIM_MAP_NAME, result["missing_artifacts"])

    def test_has_claim_map_missing_narrative_plan_returns_needs_narrative_plan(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_narrative_plan")
        self.assertIn(NARRATIVE_PLAN_NAME, result["missing_artifacts"])

    def test_has_narrative_plan_missing_page_tasks_returns_needs_page_tasks(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_page_tasks")
        self.assertIn(PAGE_TASKS_NAME, result["missing_artifacts"])

    def test_has_page_tasks_missing_sourcing_returns_needs_sourcing(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "t"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        self._write_json(PAGE_TASKS_NAME, {"tasks": []})
        result = resolve_next_step(self.run_dir)
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
        result = resolve_next_step(self.run_dir)
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

    def test_preview_with_approved_pages_returns_ready_to_export(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}, {"decision": "pending"}]})
        self._write_gate()
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "ready_to_export")
        self.assertEqual(result.get("approved_pages"), 1)
        self.assertIn("export", result["next_command"])

    def test_preview_without_approved_and_draft_gate_returns_needs_page_review(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "pending"}]})
        self._write_gate()
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_page_review")
        self.assertIn("preview", result["next_command"])

    def test_preview_without_approved_and_missing_draft_gate_returns_needs_draft_gate(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "pending"}]})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_draft_gate")
        self.assertIn("quality-gate", result["next_command"])

    def test_approved_page_without_draft_gate_returns_needs_draft_gate(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}]})
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_draft_gate")
        self.assertNotEqual("ready_to_export", result["status"])

    def test_blocking_draft_gate_returns_needs_quality_review(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}]})
        self._write_gate(status="rework_required", blocks=True)
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "needs_quality_review")
        self.assertIn("Draft gate blocks", result["blocking_issues"][0])

    def test_draft_v2_gate_is_supported(self) -> None:
        self._write_full_pipeline()
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"decision": "approved"}]})
        self._write_gate("draft_v2_gate.json")
        result = resolve_next_step(self.run_dir)
        self._assert_shape(result, "ready_to_export")

    def test_result_always_contains_required_keys(self) -> None:
        # Verify across multiple states that the shape is stable.
        for setup_fn, _ in [
            (lambda: None, "needs_request"),
            (lambda: self._write_json(REQUEST_NAME, {"run_id": "x"}), "needs_context"),
        ]:
            setup_fn()
            result = resolve_next_step(self.run_dir)
            self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))
            # Reset for next iteration.
            for child in list(self.run_dir.iterdir()):
                if child.is_file():
                    child.unlink()


if __name__ == "__main__":
    unittest.main()
