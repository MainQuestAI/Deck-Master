from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.scoring import (  # noqa: E402
    build_score,
    build_target_evaluation,
    evaluate_max_target,
    evaluate_min_target,
)


class BenchmarkScoringTests(unittest.TestCase):
    def test_max_target_pass_warning_fail_pending(self) -> None:
        self.assertEqual("pass", evaluate_max_target(45, 45))
        self.assertEqual("warning", evaluate_max_target(50, 45))
        self.assertEqual("fail", evaluate_max_target(60, 45))
        self.assertEqual("pending", evaluate_max_target(None, 45))
        self.assertEqual("not_applicable", evaluate_max_target(45, None))

    def test_min_target_pass_warning_fail_pending(self) -> None:
        self.assertEqual("pass", evaluate_min_target(0.5, 0.5))
        self.assertEqual("warning", evaluate_min_target(0.42, 0.5))
        self.assertEqual("fail", evaluate_min_target(0.35, 0.5))
        self.assertEqual("pending", evaluate_min_target(None, 0.5))

    def test_target_evaluation_and_score(self) -> None:
        evaluation = build_target_evaluation(
            {
                "context_to_preview_minutes": 45,
                "page_acceptance_rate_min": 0.5,
                "reuse_adapt_rate_min": 0.3,
                "p0_count_max": 0,
                "evidence_gap_visible": True,
                "quality_gate_required": True,
            },
            efficiency_metrics={"created_to_preview_minutes": 40},
            page_metrics={"page_acceptance_rate": 0.4},
            source_metrics={"reuse_adapt_rate": 0.35},
            quality_metrics={"p0": 0, "evidence_gap_count": 2, "quality_gate_present": True},
        )

        self.assertEqual("pass", evaluation["context_to_preview"])
        self.assertEqual("warning", evaluation["page_acceptance_rate"])
        self.assertEqual("pass", evaluation["reuse_adapt_rate"])
        self.assertEqual("pass", evaluation["p0_count"])
        score = build_score(evaluation, {"efficiency": 0.5, "page_acceptance": 0.5})
        self.assertGreater(score["overall"], 0)
        self.assertLessEqual(score["overall"], 1)


if __name__ == "__main__":
    unittest.main()

