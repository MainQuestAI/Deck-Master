"""Unit tests for v0.9.6 UAT report output contracts."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

uat_report = importlib.import_module("scripts.uat.report")


class UATReportTest(unittest.TestCase):
    def test_write_uat_report_outputs_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "runs" / "retail-demo"
            run_dir.mkdir(parents=True)
            (run_dir / "request.json").write_text(
                json.dumps({"run_id": "retail-demo"}, ensure_ascii=False),
                encoding="utf-8",
            )

            report = uat_report.build_uat_report(
                run_dir=run_dir,
                tool="ppt_library",
                checks=[
                    {
                        "check_id": "selection_json_readable",
                        "passed": True,
                        "severity": "info",
                        "message": "Selection JSON is readable.",
                    },
                    {
                        "check_id": "missing_canonical_id",
                        "passed": False,
                        "severity": "warning",
                        "message": "One candidate is missing canonical_slide_id.",
                        "refs": ["library_results/selection.json"],
                    },
                ],
                metrics={"candidate_count": 1},
                recommendations=["补齐 canonical_slide_id 以支持长期 asset feedback。"],
            )

            written = uat_report.write_uat_report(
                run_dir=run_dir,
                name="ppt_library_uat",
                report=report,
            )

            json_path = Path(written["json_path"])
            markdown_path = Path(written["markdown_path"])
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())

            saved = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], "deck_uat_report.v1")
            self.assertRegex(saved["run_id"], r"^uat-[a-f0-9]{16}$")
            self.assertNotIn("retail-demo", json_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["tool"], "ppt_library")
            self.assertEqual(saved["status"], "warning")
            self.assertEqual(saved["summary"]["checks"], 2)
            self.assertEqual(saved["summary"]["warnings"], 1)
            self.assertEqual(saved["metrics"]["candidate_count"], 1)

            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("ppt_library", markdown)
            self.assertIn("warning", markdown)
            self.assertIn("candidate_count", markdown)
            self.assertNotIn("retail-demo", markdown)

    def test_customer_run_id_is_redacted_from_report_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_run_id = "generic-run"
            raw_dir_name = "customer-name-private-deck"
            run_dir = Path(tmp) / raw_dir_name
            run_dir.mkdir()
            (run_dir / "request.json").write_text(json.dumps({"run_id": raw_run_id}), encoding="utf-8")
            report = uat_report.build_uat_report(
                run_dir,
                "ppt_library",
                [
                    {
                        "check_id": "run_id_mismatch",
                        "passed": False,
                        "severity": "warning",
                        "message": f"run_id {raw_run_id} needs review",
                        "refs": [],
                    }
                ],
                {raw_dir_name: [raw_run_id, raw_dir_name]},
                [f"Review {raw_run_id} in {raw_dir_name}."],
            )
            report["writer_regression"] = {raw_dir_name: [raw_run_id, raw_dir_name]}
            written = uat_report.write_uat_report(run_dir, "redacted", report)
            evidence = Path(written["json_path"]).read_text(encoding="utf-8") + Path(written["markdown_path"]).read_text(encoding="utf-8")

            self.assertNotIn(raw_run_id, evidence)
            self.assertNotIn(raw_dir_name, evidence)
            self.assertIn(report["run_id"], evidence)


if __name__ == "__main__":
    unittest.main()
