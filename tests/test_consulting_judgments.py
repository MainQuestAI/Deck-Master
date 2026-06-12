from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so narrative.judgment_builder is importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from narrative.judgment_builder import SCHEMA_VERSION, build_judgments


def _make_request(**overrides):
    base = {
        "run_id": "run-test-001",
        "business_goal": "提升客户续费率",
        "industry": "SaaS",
        "audience": "client",
    }
    base.update(overrides)
    return base


def _make_deck_brief(**overrides):
    base = {
        "run_id": "run-test-001",
        "core_points": ["诊断流失根因", "设计留存机制", "落地执行计划"],
        "business_goal": "提升客户续费率",
    }
    base.update(overrides)
    return base


def _make_claim_map(claims=None):
    if claims is None:
        claims = [
            {"claim_id": "c1", "claim": "客户流失主要源于上手困难", "risk_flags": [], "evidence_refs": ["transcript.md"]},
            {"claim_id": "c2", "claim": "缩短 TTV 可提升续费率 15%", "risk_flags": [], "evidence_refs": ["benchmark.pdf"]},
            {"claim_id": "c3", "claim": "竞品已提供自助 onboarding", "risk_flags": ["needs_customer_evidence"], "evidence_refs": []},
        ]
    return {"claims": claims}


class TestBuildJudgments(unittest.TestCase):
    def test_at_least_three_judgments_with_short_brief(self):
        request = _make_request()
        deck_brief = _make_deck_brief(core_points=["要点A"])
        claim_map = _make_claim_map()
        result = build_judgments(request, deck_brief, claim_map)
        self.assertGreaterEqual(len(result["judgments"]), 3)

    def test_judgment_required_fields(self):
        required_keys = {"judgment_id", "topic", "statement", "rationale", "confidence", "source_refs", "risk_flags"}
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = _make_claim_map()
        result = build_judgments(request, deck_brief, claim_map)
        for j in result["judgments"]:
            with self.subTest(judgment_id=j.get("judgment_id")):
                self.assertTrue(required_keys.issubset(j.keys()), f"missing keys: {required_keys - set(j.keys())}")
                self.assertIsInstance(j["confidence"], (int, float))
                self.assertTrue(0 <= j["confidence"] <= 1)
                self.assertIsInstance(j["source_refs"], list)
                self.assertIsInstance(j["risk_flags"], list)

    def test_missing_evidence_carries_risk_flag(self):
        # All claims have risk flags → evidence_sufficiency judgment must carry a flag.
        risky_claims = [
            {"claim_id": "r1", "claim": "高风险论点", "risk_flags": ["unverified"], "evidence_refs": []},
        ]
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = _make_claim_map(claims=risky_claims)
        result = build_judgments(request, deck_brief, claim_map)
        evidence_judgments = [j for j in result["judgments"] if j["topic"] == "evidence_sufficiency"]
        self.assertTrue(evidence_judgments, "expected at least one evidence_sufficiency judgment")
        flagged = [j for j in evidence_judgments if j["risk_flags"]]
        self.assertTrue(flagged, "evidence_sufficiency judgment should carry risk_flags when evidence is weak")

    def test_deterministic_output(self):
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = _make_claim_map()
        first = build_judgments(request, deck_brief, claim_map)
        second = build_judgments(request, deck_brief, claim_map)
        self.assertEqual(first, second)

    def test_schema_version_and_run_id_present(self):
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = _make_claim_map()
        result = build_judgments(request, deck_brief, claim_map)
        self.assertIn("schema_version", result)
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertIn("run_id", result)
        self.assertEqual(result["run_id"], "run-test-001")

    def test_empty_claims_still_produces_basic_judgments(self):
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = {"claims": []}
        result = build_judgments(request, deck_brief, claim_map)
        self.assertGreaterEqual(len(result["judgments"]), 3)
        topics = {j["topic"] for j in result["judgments"]}
        self.assertIn("business_problem", topics)
        self.assertIn("solution_approach", topics)
        self.assertIn("evidence_sufficiency", topics)

    def test_open_questions_nonempty_when_evidence_insufficient(self):
        # All claims risky → evidence ratio < 0.7 → open_questions should be populated.
        risky_claims = [
            {"claim_id": "r1", "claim": "论点A", "risk_flags": ["no_source"], "evidence_refs": []},
            {"claim_id": "r2", "claim": "论点B", "risk_flags": ["unverified"], "evidence_refs": []},
        ]
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = _make_claim_map(claims=risky_claims)
        result = build_judgments(request, deck_brief, claim_map)
        self.assertTrue(result["open_questions"], "open_questions should be non-empty when evidence is insufficient")

    def test_no_context_manifest_defaults_gracefully(self):
        request = _make_request()
        deck_brief = _make_deck_brief()
        claim_map = _make_claim_map()
        # context_manifest=None should not raise
        result = build_judgments(request, deck_brief, claim_map, context_manifest=None)
        self.assertIn("judgments", result)
        self.assertGreaterEqual(len(result["judgments"]), 3)


if __name__ == "__main__":
    unittest.main()
