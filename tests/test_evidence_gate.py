"""Tests for evidence_gate."""
from __future__ import annotations
import unittest

from scripts.quality.evidence_gate import evaluate_evidence_gate


class TestEvidenceGate(unittest.TestCase):

    def test_pass_when_all_claims_covered_and_no_gaps(self):
        result = evaluate_evidence_gate(
            run_id="run-001",
            claim_map={"claims": [{"claim_id": "c1", "claim": "AI 提升效率"}]},
            page_tasks={"tasks": [{"planning": {"claim_ref": "c1"}}]},
        )
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["blocks_delivery"])
        self.assertEqual(result["findings"], [])

    def test_p1_when_claim_has_no_page(self):
        result = evaluate_evidence_gate(
            run_id="run-002",
            claim_map={"claims": [{"claim_id": "c1", "claim": "AI 提升效率"}]},
            page_tasks={"tasks": []},
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])
        self.assertEqual(result["blocking_summary"]["p1_count"], 1)
        self.assertIn("claim_coverage", result["findings"][0]["dimension"])

    def test_p1_when_required_evidence_missing_via_graph(self):
        result = evaluate_evidence_gate(
            run_id="run-003",
            claim_map={"claims": [{"claim_id": "c1", "claim": "AI 提升效率"}]},
            page_tasks={"tasks": [{"planning": {"claim_ref": "c1"}}]},
            claim_evidence_graph={"gaps": [{"claim_id": "c1", "description": "缺少客户案例"}]},
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(any(f["dimension"] == "evidence_readiness" for f in result["findings"]))

    def test_p1_when_risk_flag_mentions_evidence(self):
        result = evaluate_evidence_gate(
            run_id="run-004",
            claim_map={"claims": [{"claim_id": "c1", "claim": "AI 提升效率", "risk_flags": ["no evidence"]}]},
            page_tasks={"tasks": [{"planning": {"claim_ref": "c1"}}]},
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(any(f["dimension"] == "evidence_readiness" for f in result["findings"]))

    def test_p0_when_internal_only_enters_client_queue(self):
        result = evaluate_evidence_gate(
            run_id="run-005",
            claim_map={"claims": [{"claim_id": "c1", "claim": "AI 提升效率"}]},
            page_tasks={"tasks": [{"planning": {"claim_ref": "c1"}}]},
            sourcing_plan={
                "decisions": [{
                    "beat_id": "b1",
                    "source_decision": "reuse",
                    "selected_candidate": {"publication_status": "internal_only"},
                }]
            },
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])
        self.assertEqual(result["blocking_summary"]["p0_count"], 1)

    def test_empty_inputs_pass(self):
        result = evaluate_evidence_gate(
            run_id="run-006",
            claim_map={"claims": []},
            page_tasks={"tasks": []},
        )
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["blocks_delivery"])

    def test_schema_version_present(self):
        result = evaluate_evidence_gate(
            run_id="run-007",
            claim_map={"claims": []},
            page_tasks={"tasks": []},
        )
        self.assertEqual(result["schema_version"], "deck_evidence_gate.v1")
        self.assertEqual(result["gate"], "evidence")


if __name__ == "__main__":
    unittest.main()
