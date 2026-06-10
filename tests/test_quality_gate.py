from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.draft_gate import evaluate_draft


class DraftGateTests(unittest.TestCase):
    def test_draft_gate_flags_missing_evidence(self) -> None:
        report = evaluate_draft(
            {"run_id": "run-1", "business_goal": "客户方案"},
            {
                "run_id": "run-1",
                "claims": [
                    {
                        "claim_id": "claim_01",
                        "claim": "需要全渠道库存可视化",
                        "risk_flags": ["evidence_gap"],
                    }
                ],
            },
            {
                "run_id": "run-1",
                "tasks": [
                    {
                        "beat_id": "beat_01",
                        "planning": {
                            "core_claim": "需要全渠道库存可视化",
                            "gaps": ["evidence_gap"],
                        },
                    }
                ],
            },
        )

        self.assertEqual("rework_required", report["status"])
        self.assertGreaterEqual(len(report["findings"]), 1)


if __name__ == "__main__":
    unittest.main()
