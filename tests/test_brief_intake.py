from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request


class BriefIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_text_brief_detects_topics(self) -> None:
        request = build_request(brief="零售数字化，关注全渠道、库存可视化、最后一公里配送", industry="retail")

        self.assertEqual("retail", request["industry"])
        self.assertIn("全渠道", request["must_cover_topics"])
        self.assertIn("库存可视化", request["must_cover_topics"])
        self.assertIn("最后一公里配送", request["must_cover_topics"])

    def test_file_brief(self) -> None:
        brief_file = self.temp_dir / "brief.txt"
        brief_file.write_text("客户经营方案，关注会员和私域", encoding="utf-8")

        request = build_request(brief_file=brief_file, target_pages="15", audience="exec")

        self.assertEqual("15", request["target_pages"])
        self.assertEqual("exec", request["audience"])
        self.assertIn("客户经营", request["must_cover_topics"])

    def test_json_brief(self) -> None:
        request = build_request(brief='{"project_name":"Demo","business_goal":"AI智能体方案","must_cover_topics":["AI智能体"]}')

        self.assertEqual("Demo", request["project_name"])
        self.assertEqual(["AI智能体"], request["must_cover_topics"])


if __name__ == "__main__":
    unittest.main()
