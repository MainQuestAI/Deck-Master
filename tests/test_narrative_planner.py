from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative


class NarrativePlannerTests(unittest.TestCase):
    def test_retail_golden_plan_contains_required_topics(self) -> None:
        request = build_request(
            brief="零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送",
            industry="retail",
            target_pages="auto",
        )
        plan = plan_narrative(request)

        self.assertGreaterEqual(len(plan["beats"]), 10)
        text = "\n".join(f"{beat['page_title']} {beat['reuse_query']}" for beat in plan["beats"])
        for keyword in ("全渠道", "库存可视化", "最后一公里", "目标架构", "案例", "价值"):
            self.assertIn(keyword, text)

    def test_page_count_can_be_explicit(self) -> None:
        request = build_request(brief="通用解决方案", target_pages="30")
        plan = plan_narrative(request)
        self.assertEqual(30, len(plan["beats"]))
        self.assertEqual("solution", plan["density"])


if __name__ == "__main__":
    unittest.main()
