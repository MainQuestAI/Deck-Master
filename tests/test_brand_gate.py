"""Tests for brand_gate."""
from __future__ import annotations
import unittest
import tempfile
import os
from pathlib import Path

from scripts.quality.brand_gate import evaluate_brand_gate


class TestBrandGate(unittest.TestCase):

    def test_not_applicable_when_no_artifact(self):
        result = evaluate_brand_gate(run_id="run-001")
        self.assertEqual(result["status"], "not_applicable")
        self.assertFalse(result["blocks_delivery"])

    def test_not_applicable_when_artifact_missing(self):
        result = evaluate_brand_gate(
            run_id="run-002",
            final_artifact="/nonexistent/path/deck.pptx",
        )
        self.assertEqual(result["status"], "not_applicable")

    def test_pass_with_artifact_and_visual_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake artifact file
            artifact_path = Path(tmpdir) / "deck.pptx"
            artifact_path.write_bytes(b"fake pptx content")
            # Create visual-system dir with a file
            vs_dir = Path(tmpdir) / "visual-system"
            vs_dir.mkdir()
            (vs_dir / "design_spec.md").write_text("# Design Spec")

            result = evaluate_brand_gate(
                run_id="run-003",
                workspace_dir=tmpdir,
                final_artifact=str(artifact_path),
            )
            # No python-pptx available or fake file → actual_pages is None → no page count check
            # visual-system exists → no P2 finding
            self.assertIn(result["status"], ("pass", "conditional_pass"))

    def test_p2_when_no_visual_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "deck.pptx"
            artifact_path.write_bytes(b"fake pptx content")
            # No visual-system directory created

            result = evaluate_brand_gate(
                run_id="run-004",
                workspace_dir=tmpdir,
                final_artifact=str(artifact_path),
            )
            self.assertEqual(result["status"], "conditional_pass")
            self.assertTrue(any(f["severity"] == "P2" for f in result["findings"]))
            self.assertFalse(result["blocks_delivery"])  # P2 doesn't block

    def test_empty_visual_system_dir_triggers_p2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "deck.pptx"
            artifact_path.write_bytes(b"fake pptx content")
            vs_dir = Path(tmpdir) / "visual-system"
            vs_dir.mkdir()
            # Empty dir → has_visual_system = False

            result = evaluate_brand_gate(
                run_id="run-005",
                workspace_dir=tmpdir,
                final_artifact=str(artifact_path),
            )
            self.assertTrue(any(f["finding_id"] == "brand_no_visual_system" for f in result["findings"]))

    def test_schema_version_present(self):
        result = evaluate_brand_gate(run_id="run-006")
        self.assertEqual(result["schema_version"], "deck_brand_gate.v1")
        self.assertEqual(result["gate"], "brand")


if __name__ == "__main__":
    unittest.main()
