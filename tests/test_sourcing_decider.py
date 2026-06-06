from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.sourcing_decider import decide_for_beat


class SourcingDeciderTests(unittest.TestCase):
    def beat(self, role: str = "solution") -> dict:
        return {
            "beat_id": "beat_01_solution",
            "order": 1,
            "page_title": "总体方案",
            "role": role,
            "evidence_need": "历史方案页或通用方法论",
            "generation_brief": "生成总体方案",
        }

    def test_reuse_when_candidate_is_strong(self) -> None:
        decision = decide_for_beat(self.beat(), [{"confidence": 0.9, "win_rate": 0.7, "reuse_count": 3, "screenshot_path": "/tmp/a.svg"}])
        self.assertEqual("reuse", decision["source_decision"])

    def test_adapt_when_candidate_is_partial(self) -> None:
        decision = decide_for_beat(self.beat(), [{"confidence": 0.55, "win_rate": 0.2, "screenshot_path": "/tmp/a.svg"}])
        self.assertEqual("adapt", decision["source_decision"])

    def test_generate_when_no_candidate(self) -> None:
        decision = decide_for_beat(self.beat("architecture"), [])
        self.assertEqual("generate", decision["source_decision"])

    def test_manual_placeholder_when_case_evidence_missing(self) -> None:
        beat = self.beat("case")
        beat["evidence_need"] = "可引用客户案例或相似项目经验"
        decision = decide_for_beat(beat, [])
        self.assertEqual("manual_placeholder", decision["source_decision"])


if __name__ == "__main__":
    unittest.main()
