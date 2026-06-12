"""Tests for context_conflict_gate."""
from __future__ import annotations
import unittest

from scripts.quality.context_conflict_gate import evaluate_context_conflict_gate


class TestContextConflictGate(unittest.TestCase):

    def test_pass_when_no_conflicts(self):
        result = evaluate_context_conflict_gate(
            run_id="run-001",
            request={"industry": "金融", "project_name": "BankA"},
            sourcing_plan={
                "decisions": [{
                    "beat_id": "b1",
                    "source_decision": "reuse",
                    "selected_candidate": {"industry": "金融", "client_name": "BankA"},
                }]
            },
        )
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["blocks_delivery"])

    def test_p1_industry_conflict(self):
        result = evaluate_context_conflict_gate(
            run_id="run-002",
            request={"industry": "金融", "project_name": "BankA"},
            sourcing_plan={
                "decisions": [{
                    "beat_id": "b1",
                    "source_decision": "reuse",
                    "selected_candidate": {"industry": "医疗", "client_name": "BankA"},
                }]
            },
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])
        dims = [f["dimension"] for f in result["findings"]]
        self.assertIn("industry_conflict", dims)

    def test_p1_client_name_residual(self):
        result = evaluate_context_conflict_gate(
            run_id="run-003",
            request={"industry": "金融", "project_name": "BankA"},
            sourcing_plan={
                "decisions": [{
                    "beat_id": "b1",
                    "source_decision": "adapt",
                    "selected_candidate": {"industry": "金融", "client_name": "OldClient"},
                }]
            },
        )
        self.assertEqual(result["status"], "rework_required")
        dims = [f["dimension"] for f in result["findings"]]
        self.assertIn("client_name_residual", dims)

    def test_skip_non_reuse_adapt_decisions(self):
        result = evaluate_context_conflict_gate(
            run_id="run-004",
            request={"industry": "金融", "project_name": "BankA"},
            sourcing_plan={
                "decisions": [{
                    "beat_id": "b1",
                    "source_decision": "generate",
                    "selected_candidate": {"industry": "医疗", "client_name": "OtherClient"},
                }]
            },
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])

    def test_pass_when_no_sourcing_decisions(self):
        result = evaluate_context_conflict_gate(
            run_id="run-005",
            request={"industry": "金融", "project_name": "BankA"},
            sourcing_plan={"decisions": []},
        )
        self.assertEqual(result["status"], "pass")

    def test_schema_version_present(self):
        result = evaluate_context_conflict_gate(
            run_id="run-006",
            request={},
            sourcing_plan={"decisions": []},
        )
        self.assertEqual(result["schema_version"], "deck_context_conflict_gate.v1")
        self.assertEqual(result["gate"], "context_conflict")


if __name__ == "__main__":
    unittest.main()
