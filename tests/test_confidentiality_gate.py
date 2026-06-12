"""Tests for confidentiality_gate."""
from __future__ import annotations
import unittest
import tempfile
import os

from scripts.quality.confidentiality_gate import evaluate_confidentiality_gate


class TestConfidentialityGate(unittest.TestCase):

    def test_pass_when_clean(self):
        result = evaluate_confidentiality_gate(
            run_id="run-001",
            artifact_text="这是一份正常的方案介绍。",
        )
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["blocks_delivery"])

    def test_p1_forbidden_terms_in_artifact(self):
        result = evaluate_confidentiality_gate(
            run_id="run-002",
            forbidden_terms=["内部项目X"],
            artifact_text="这是关于内部项目X的方案。",
        )
        self.assertEqual(result["status"], "conditional_pass")
        self.assertFalse(result["blocks_delivery"])  # P1 doesn't block delivery
        self.assertTrue(any(f["dimension"] == "forbidden_terms" for f in result["findings"]))

    def test_p0_sensitive_pattern_api_key(self):
        result = evaluate_confidentiality_gate(
            run_id="run-003",
            artifact_text="api_key = sk-abc123def456",
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])
        self.assertTrue(any(f["dimension"] == "sensitive_data" for f in result["findings"]))

    def test_p0_sensitive_pattern_account(self):
        result = evaluate_confidentiality_gate(
            run_id="run-004",
            artifact_text="账号: admin@internal.com",
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])

    def test_p0_needs_redaction_source(self):
        result = evaluate_confidentiality_gate(
            run_id="run-005",
            sourcing_plan={
                "decisions": [{
                    "beat_id": "b1",
                    "source_decision": "reuse",
                    "selected_candidate": {"publication_status": "needs_redaction"},
                }]
            },
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])
        self.assertTrue(any(f["dimension"] == "source_publication" for f in result["findings"]))

    def test_forbidden_terms_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# comment line\n机密词A\n机密词B\n")
            tmp_path = f.name
        try:
            result = evaluate_confidentiality_gate(
                run_id="run-006",
                workspace_forbidden_terms_path=tmp_path,
                artifact_text="这里包含机密词A的内容。",
            )
            self.assertEqual(result["status"], "conditional_pass")
            self.assertTrue(any("机密词A" in f["message"] for f in result["findings"]))
        finally:
            os.unlink(tmp_path)

    def test_preview_manifest_forbidden_terms(self):
        result = evaluate_confidentiality_gate(
            run_id="run-007",
            forbidden_terms=["禁词"],
            preview_manifest={
                "pages": [{"page_id": "p1", "title": "含禁词的标题", "notes": ""}]
            },
        )
        self.assertEqual(result["status"], "conditional_pass")
        self.assertTrue(any(f["dimension"] == "forbidden_terms" for f in result["findings"]))

    def test_schema_version_present(self):
        result = evaluate_confidentiality_gate(run_id="run-008")
        self.assertEqual(result["schema_version"], "deck_confidentiality_gate.v1")
        self.assertEqual(result["gate"], "confidentiality")


if __name__ == "__main__":
    unittest.main()
