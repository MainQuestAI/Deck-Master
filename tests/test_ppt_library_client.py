from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from tools.ppt_library_client import build_select_slides_command, run_library_selection


class PPTLibraryClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_builds_select_slides_command(self) -> None:
        command = build_select_slides_command(
            command="ppt-lib",
            plan_path=Path("narrative_plan.json"),
            brief="brief",
            output_path=Path("selection.json"),
        )
        self.assertIn("select-slides", command)
        self.assertIn("--ranking", command)
        self.assertIn("business", command)

    def test_fixture_selection_writes_by_beat_results(self) -> None:
        request = build_request(brief="零售方案，关注全渠道和库存可视化", industry="retail")
        plan = plan_narrative(request)
        plan_path = self.temp_dir / "narrative_plan.json"
        plan_path.write_text("{}", encoding="utf-8")

        results = run_library_selection(
            narrative_plan=plan,
            narrative_plan_path=plan_path,
            request=request,
            run_dir=self.temp_dir,
            mode="fixture",
        )

        self.assertEqual("fixture", results["source"])
        self.assertTrue((self.temp_dir / "library_results" / "selection.json").exists())
        self.assertIn(plan["beats"][0]["beat_id"], results["by_beat"])


if __name__ == "__main__":
    unittest.main()
