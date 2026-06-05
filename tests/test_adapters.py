from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "adapters"))

from deck_pro_max_to_plan import convert_deck_pro_max_project
from ppt_library_to_plan import convert_ppt_library_payload, load_json


PPT_LIBRARY_SAMPLE = ROOT / "examples" / "adapters" / "ppt_library_search.json"


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_ppt_library_search_to_plan(self) -> None:
        plan = convert_ppt_library_payload(
            load_json(PPT_LIBRARY_SAMPLE),
            run_id="retail-library-run",
            title="Retail Library Candidates",
        )

        self.assertEqual("retail-library-run", plan["run_id"])
        self.assertEqual(1, len(plan["pages"]))
        page = plan["pages"][0]
        self.assertEqual("library_slide", page["source_type"])
        self.assertEqual("../preview-run/links/page_001.svg", page["preview_asset"])
        self.assertEqual(7, page["ppt_library_slide_id"])
        self.assertEqual(0.6667, page["win_rate"])

    def test_ppt_library_select_slides_to_plan(self) -> None:
        payload = {
            "report": {
                "roles": [
                    {
                        "role": "case",
                        "slides": [
                            {
                                "slide_id": 11,
                                "title": "Case Study",
                                "source_file": "/deck.pptx",
                                "page_number": 3,
                                "screenshot_path": "/tmp/case.png",
                            }
                        ],
                    }
                ]
            }
        }
        plan = convert_ppt_library_payload(payload, run_id="selection-run", title="Selection")
        self.assertEqual("case_11", plan["pages"][0]["page_id"])
        self.assertEqual("case", plan["pages"][0]["narrative_role"])

    def test_ppt_library_relative_assets_can_be_resolved(self) -> None:
        payload = load_json(PPT_LIBRARY_SAMPLE)
        plan = convert_ppt_library_payload(
            payload,
            run_id="retail-library-run",
            title="Retail Library Candidates",
            asset_base_dir=PPT_LIBRARY_SAMPLE.parent,
        )
        expected = (PPT_LIBRARY_SAMPLE.parent / "../preview-run/links/page_001.svg").resolve()
        self.assertEqual(str(expected), plan["pages"][0]["preview_asset"])

    def test_deck_pro_max_rendered_images_to_plan(self) -> None:
        project = self.temp_dir / "deck-project"
        rendered = project / "rendered"
        rendered.mkdir(parents=True)
        (rendered / "slide_02.png").write_text("image", encoding="utf-8")
        (rendered / "slide_01.png").write_text("image", encoding="utf-8")

        plan = convert_deck_pro_max_project(project, run_id="generated-run", title="Generated")

        self.assertEqual(2, len(plan["pages"]))
        self.assertEqual(["generated_01", "generated_02"], [page["page_id"] for page in plan["pages"]])
        self.assertEqual("generated", plan["pages"][0]["source_type"])

    def test_deck_pro_max_rejects_missing_images(self) -> None:
        project = self.temp_dir / "empty-project"
        project.mkdir()
        with self.assertRaises(ValueError):
            convert_deck_pro_max_project(project, run_id="empty", title="Empty")


if __name__ == "__main__":
    unittest.main()
