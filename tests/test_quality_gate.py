from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.draft_gate import evaluate_draft
from quality.gate_runner import evaluate_delivery_gate, evaluate_render_gate


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
        self.assertIn("scorecard", report)
        self.assertTrue(report["blocks_delivery"])

    def test_delivery_gate_flags_pptx_package_risks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pptx = Path(temp) / "deck.pptx"
            write_minimal_pptx(
                pptx,
                [
                    {"text": "客户方案 这是一个可读页面，包含业务目标、证据和下一步行动。", "pictures": 0},
                    {"text": "内部 Brief", "pictures": 1},
                ],
            )

            report = evaluate_delivery_gate(
                "run-1",
                pptx,
                expected_pages=3,
                forbidden_terms=["内部", "Brief"],
            )

        self.assertEqual("rework_required", report["status"])
        self.assertTrue(report["blocks_delivery"])
        finding_ids = {finding["finding_id"] for finding in report["findings"]}
        self.assertIn("delivery_page_count_mismatch", finding_ids)
        self.assertTrue(any(item.startswith("slide_002_forbidden_terms") for item in finding_ids))

    def test_render_gate_flags_possible_full_slide_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pptx = Path(temp) / "deck.pptx"
            write_minimal_pptx(pptx, [{"text": "", "pictures": 1}])

            report = evaluate_render_gate("run-1", pptx, expected_pages=1)

        self.assertEqual("rework_required", report["status"])
        self.assertTrue(report["page_findings"])


def write_minimal_pptx(path: Path, slides: list[dict]) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        for index, slide in enumerate(slides, start=1):
            texts = "".join(f"<a:t>{text}</a:t>" for text in [slide.get("text", "")] if text)
            pics = "".join("<p:pic></p:pic>" for _ in range(slide.get("pictures", 0)))
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r>{texts}</a:r></a:p></p:txBody></p:sp>{pics}</p:spTree></p:cSld>
</p:sld>
""",
            )


if __name__ == "__main__":
    unittest.main()
