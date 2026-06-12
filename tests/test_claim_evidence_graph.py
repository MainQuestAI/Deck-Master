from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so narrative.claim_graph is importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from narrative.claim_graph import SCHEMA_VERSION, build_claim_evidence_graph


VALID_PUBLICATION_STATUSES = {"safe_to_use", "internal_only", "needs_redaction", "unknown"}
VALID_EVIDENCE_TYPES = {
    "meeting_quote",
    "customer_material",
    "case_study",
    "product_screenshot",
    "data_point",
    "assumption",
}
VALID_CLAIM_TYPES = {"core", "supporting", "contextual"}


def _make_claim_map(claims=None, run_id="run-test-001"):
    if claims is None:
        claims = [
            {
                "claim_id": "c1",
                "claim": "客户流失主要源于上手困难",
                "risk_flags": [],
                "evidence_refs": ["transcript.md"],
                "evidence_needed": ["客户访谈引用"],
            },
            {
                "claim_id": "c2",
                "claim": "缩短 TTV 可提升续费率 15%",
                "risk_flags": [],
                "evidence_refs": ["benchmark.pdf"],
                "evidence_needed": [],
            },
            {
                "claim_id": "c3",
                "claim": "竞品已提供自助 onboarding",
                "risk_flags": ["needs_customer_evidence"],
                "evidence_refs": [],
                "evidence_needed": ["竞品截图", "客户对比反馈"],
            },
        ]
    return {"claims": claims, "run_id": run_id}


def _make_page_tasks(tasks=None):
    if tasks is None:
        tasks = [
            {"beat_id": "page_01", "planning": {"core_claim": "客户流失主要源于上手困难", "role": "problem"}},
            {"beat_id": "page_02", "planning": {"core_claim": "缩短 TTV 可提升续费率 15%", "role": "solution"}},
        ]
    return {"tasks": tasks}


def _make_context_manifest(sources=None):
    if sources is None:
        sources = [
            {"source_id": "transcript.md", "kind": "meeting_transcript", "summary": "客户反馈上手难"},
            {"source_id": "benchmark.pdf", "kind": "report", "summary": "行业基准 TTV 数据"},
            {"source_id": "internal.doc", "kind": "internal_doc", "excerpt": "内部分析笔记"},
        ]
    return {"sources": sources}


class TestBuildClaimEvidenceGraph(unittest.TestCase):
    def test_valid_graph_structure(self):
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            _make_context_manifest(),
        )
        self.assertIn("schema_version", graph)
        self.assertEqual(graph["schema_version"], SCHEMA_VERSION)
        self.assertIn("run_id", graph)
        self.assertEqual(graph["run_id"], "run-test-001")
        for key in ("claims", "evidence", "assumptions", "risks", "page_refs", "gaps"):
            self.assertIn(key, graph)

    def test_claim_required_fields(self):
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            _make_context_manifest(),
        )
        required_keys = {
            "claim_id",
            "type",
            "statement",
            "supporting_evidence",
            "assumptions",
            "risks",
            "required_evidence",
            "page_refs",
        }
        for claim in graph["claims"]:
            with self.subTest(claim_id=claim.get("claim_id")):
                missing = required_keys - set(claim.keys())
                self.assertFalse(missing, f"missing keys: {missing}")
                self.assertIn(claim["type"], VALID_CLAIM_TYPES)
                self.assertIsInstance(claim["supporting_evidence"], list)
                self.assertIsInstance(claim["assumptions"], list)
                self.assertIsInstance(claim["risks"], list)
                self.assertIsInstance(claim["required_evidence"], list)
                self.assertIsInstance(claim["page_refs"], list)

    def test_evidence_required_fields_and_publication_status(self):
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            _make_context_manifest(),
        )
        required_keys = {
            "evidence_id",
            "source_ref",
            "evidence_type",
            "summary",
            "confidence",
            "publication_status",
        }
        for ev in graph["evidence"]:
            with self.subTest(evidence_id=ev.get("evidence_id")):
                missing = required_keys - set(ev.keys())
                self.assertFalse(missing, f"missing keys: {missing}")
                self.assertIn(ev["publication_status"], VALID_PUBLICATION_STATUSES)
                self.assertIn(ev["evidence_type"], VALID_EVIDENCE_TYPES)
                self.assertIsInstance(ev["confidence"], (int, float))
                self.assertTrue(0 <= ev["confidence"] <= 1)

    def test_missing_evidence_creates_gap(self):
        # c3 has no evidence_refs but has evidence_needed → should produce a gap.
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            _make_context_manifest(),
        )
        gap_claim_ids = {g["claim_id"] for g in graph["gaps"]}
        self.assertIn("c3", gap_claim_ids)
        gap = next(g for g in graph["gaps"] if g["claim_id"] == "c3")
        self.assertIn("required_evidence", gap)
        self.assertIn("repair_instruction", gap)

    def test_page_refs_populated_from_page_tasks(self):
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            _make_context_manifest(),
        )
        # c1's statement matches page_01 core_claim exactly.
        self.assertIn("page_01", graph["page_refs"].get("c1", []))
        # c2's statement matches page_02 core_claim exactly.
        self.assertIn("page_02", graph["page_refs"].get("c2", []))
        # At least one claim must have non-empty page_refs.
        non_empty = [refs for refs in graph["page_refs"].values() if refs]
        self.assertTrue(non_empty, "expected at least one claim with non-empty page_refs")

    def test_empty_claim_map_returns_empty_graph(self):
        graph = build_claim_evidence_graph(
            {"claims": [], "run_id": "run-empty"},
            {"tasks": []},
            {},
        )
        self.assertEqual(graph["schema_version"], SCHEMA_VERSION)
        self.assertEqual(graph["run_id"], "run-empty")
        self.assertEqual(graph["claims"], [])
        self.assertEqual(graph["evidence"], [])
        self.assertEqual(graph["assumptions"], [])
        self.assertEqual(graph["risks"], [])
        self.assertEqual(graph["gaps"], [])
        self.assertEqual(graph["page_refs"], {})

    def test_no_context_manifest_defaults_gracefully(self):
        # context_manifest=None should not raise; evidence list should be empty.
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            None,
        )
        self.assertIn("claims", graph)
        self.assertEqual(graph["evidence"], [])
        # Without evidence, every claim with evidence_needed becomes a gap.
        self.assertGreater(len(graph["gaps"]), 0)

    def test_deterministic_output(self):
        args = (_make_claim_map(), _make_page_tasks(), _make_context_manifest())
        first = build_claim_evidence_graph(*args)
        second = build_claim_evidence_graph(*args)
        self.assertEqual(first, second)

    def test_risk_entries_created_for_flagged_claims(self):
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            _make_context_manifest(),
        )
        # c3 has risk_flags=["needs_customer_evidence"] → at least one risk entry.
        self.assertTrue(graph["risks"])
        risk_claim_ids = {r["claim_id"] for r in graph["risks"]}
        self.assertIn("c3", risk_claim_ids)
        risk = next(r for r in graph["risks"] if r["claim_id"] == "c3")
        self.assertEqual(risk["flag"], "needs_customer_evidence")

    def test_assumption_created_when_no_supporting_evidence(self):
        # Build a claim map where c3 has no matching evidence source.
        # Use a context manifest without c3's evidence_refs so supporting_evidence stays empty.
        sparse_manifest = {"sources": [{"source_id": "transcript.md", "kind": "meeting_transcript", "summary": "x"}]}
        graph = build_claim_evidence_graph(
            _make_claim_map(),
            _make_page_tasks(),
            sparse_manifest,
        )
        # c2 references benchmark.pdf which is NOT in sparse_manifest → assumption created.
        assumption_claim_ids = {a["claim_id"] for a in graph["assumptions"]}
        self.assertIn("c2", assumption_claim_ids)


if __name__ == "__main__":
    unittest.main()
