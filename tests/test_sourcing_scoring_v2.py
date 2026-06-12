from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assets.scoring import (
    THRESHOLDS,
    WEIGHTS,
    compute_score_v2,
    tie_breaker,
)


def _strong_candidate(**overrides: object) -> dict:
    base = {
        "confidence": 0.95,
        "win_rate": 0.8,
        "screenshot_path": "/tmp/slide.svg",
        "source_project": "acme-v2",
        "role": "solution",
        "archetypes": ["solution", "overview"],
        "text_summary": "方案概述内容",
        "canonical_slide_id": "slide_01",
    }
    base.update(overrides)
    return base


def _beat(**overrides: object) -> dict:
    base = {
        "beat_id": "beat_01",
        "order": 1,
        "page_title": "总体方案",
        "role": "solution",
        "evidence_need": "历史方案页或通用方法论",
        "industry": "tech",
    }
    base.update(overrides)
    return base


class ComputeScoreV2Tests(unittest.TestCase):
    """compute_score_v2 核心行为。"""

    # ---- 返回值结构 ----
    def test_return_structure(self) -> None:
        result = compute_score_v2(_strong_candidate(), _beat())
        self.assertIn("total_score", result)
        self.assertIn("dimension_scores", result)
        self.assertIn("penalties_applied", result)
        self.assertIn("decision", result)
        self.assertIn("reason", result)
        self.assertIsInstance(result["dimension_scores"], dict)
        self.assertIsInstance(result["penalties_applied"], list)

    # ---- 权重正确应用 ----
    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_high_confidence_produces_high_semantic_match(self) -> None:
        result = compute_score_v2(_strong_candidate(confidence=0.95), _beat())
        self.assertAlmostEqual(result["dimension_scores"]["semantic_match"], 0.95, places=3)

    # ---- 稳定性 ----
    def test_deterministic_output(self) -> None:
        c = _strong_candidate()
        b = _beat()
        r1 = compute_score_v2(c, b)
        r2 = compute_score_v2(c, b)
        self.assertEqual(r1["total_score"], r2["total_score"])
        self.assertEqual(r1["decision"], r2["decision"])
        self.assertEqual(r1["dimension_scores"], r2["dimension_scores"])

    # ---- reuse 条件 ----
    def test_reuse_requires_screenshot_and_high_score(self) -> None:
        """有截图 + 高分 + 低冲突 → reuse。"""
        result = compute_score_v2(_strong_candidate(), _beat())
        self.assertEqual(result["decision"], "reuse")

    def test_no_screenshot_blocks_reuse(self) -> None:
        """缺截图 → 不能进入 reuse，即使分数高。"""
        c = _strong_candidate(screenshot_path=None)
        result = compute_score_v2(c, _beat())
        self.assertNotEqual(result["decision"], "reuse")

    def test_reuse_threshold_value(self) -> None:
        self.assertEqual(THRESHOLDS["reuse"]["min_score"], 0.78)
        self.assertTrue(THRESHOLDS["reuse"]["screenshot_required"])

    # ---- adapt 条件 ----
    def test_adapt_moderate_score(self) -> None:
        """中等分数 + 无截图 → adapt。"""
        c = _strong_candidate(confidence=0.6, win_rate=0.3, screenshot_path=None, source_project="")
        result = compute_score_v2(c, _beat())
        self.assertIn(result["decision"], {"adapt", "generate"})

    def test_adapt_threshold_value(self) -> None:
        self.assertEqual(THRESHOLDS["adapt"]["min_score"], 0.58)

    # ---- 客户语境冲突降级 ----
    def test_high_context_conflict_blocks_reuse(self) -> None:
        """行业不同 → 高冲突 → 不进入 reuse。"""
        c = _strong_candidate(industry="finance")
        b = _beat(industry="healthcare")
        result = compute_score_v2(c, b)
        self.assertNotEqual(result["decision"], "reuse")
        self.assertTrue(len(result["penalties_applied"]) > 0)
        penalty_reasons = [p["reason"] for p in result["penalties_applied"]]
        self.assertIn("high_customer_context_conflict", penalty_reasons)

    def test_medium_context_conflict_penalty(self) -> None:
        """metadata.industry 不同 → 中等冲突。"""
        c = _strong_candidate(metadata={"industry": "retail"})
        b = _beat(industry="tech")
        result = compute_score_v2(c, b)
        penalty_reasons = [p["reason"] for p in result["penalties_applied"]]
        self.assertIn("medium_customer_context_conflict", penalty_reasons)

    def test_same_industry_no_conflict_penalty(self) -> None:
        c = _strong_candidate(industry="tech")
        b = _beat(industry="tech")
        result = compute_score_v2(c, b)
        self.assertEqual(len(result["penalties_applied"]), 0)

    # ---- asset_feedback 集成 ----
    def test_asset_feedback_approval_history(self) -> None:
        fb = {"approval_count": 8, "total_events": 10, "delivered_count": 3}
        result = compute_score_v2(_strong_candidate(), _beat(), asset_feedback=fb)
        self.assertAlmostEqual(result["dimension_scores"]["approval_history"], 0.8, places=3)
        self.assertAlmostEqual(result["dimension_scores"]["delivery_history"], 1.0, places=3)

    def test_no_feedback_defaults_to_midpoint(self) -> None:
        result = compute_score_v2(_strong_candidate(), _beat())
        self.assertAlmostEqual(result["dimension_scores"]["approval_history"], 0.5, places=3)
        self.assertAlmostEqual(result["dimension_scores"]["delivery_history"], 0.5, places=3)

    # ---- manual_placeholder ----
    def test_manual_placeholder_when_evidence_missing(self) -> None:
        c = _strong_candidate(confidence=0.3, text_summary=None, excerpt=None)
        b = _beat(evidence_need="需要可引用客户案例或收益指标")
        result = compute_score_v2(c, b)
        self.assertEqual(result["decision"], "manual_placeholder")


class TieBreakerTests(unittest.TestCase):
    def test_evidence_sufficiency_first(self) -> None:
        items = [
            {"dimension_scores": {"evidence_sufficiency": 0.3, "approval_history": 0.9}, "canonical_slide_id": "b"},
            {"dimension_scores": {"evidence_sufficiency": 0.8, "approval_history": 0.2}, "canonical_slide_id": "a"},
        ]
        ranked = tie_breaker(items)
        self.assertEqual(ranked[0]["canonical_slide_id"], "a")

    def test_approval_history_second(self) -> None:
        items = [
            {"dimension_scores": {"evidence_sufficiency": 0.8, "approval_history": 0.3}, "canonical_slide_id": "b"},
            {"dimension_scores": {"evidence_sufficiency": 0.8, "approval_history": 0.9}, "canonical_slide_id": "a"},
        ]
        ranked = tie_breaker(items)
        self.assertEqual(ranked[0]["canonical_slide_id"], "a")

    def test_canonical_slide_id_final_tiebreak(self) -> None:
        items = [
            {"dimension_scores": {"evidence_sufficiency": 0.8, "approval_history": 0.8, "delivery_history": 0.8}, "canonical_slide_id": "slide_b"},
            {"dimension_scores": {"evidence_sufficiency": 0.8, "approval_history": 0.8, "delivery_history": 0.8}, "canonical_slide_id": "slide_a"},
        ]
        ranked = tie_breaker(items)
        self.assertEqual(ranked[0]["canonical_slide_id"], "slide_a")


if __name__ == "__main__":
    unittest.main()
