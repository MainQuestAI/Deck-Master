"""Unit tests for v0.9.6 PPT Library UAT contracts."""

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

ppt_library_uat = importlib.import_module("scripts.uat.ppt_library")


class PPTLibraryUATTest(unittest.TestCase):
    def _run_dir(self, root: Path, run_id: str = "retail-demo") -> Path:
        run_dir = root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.json").write_text(
            json.dumps({"run_id": run_id}, ensure_ascii=False),
            encoding="utf-8",
        )
        return run_dir

    def _selection_path(
        self,
        run_dir: Path,
        *,
        run_id: str = "retail-demo",
        include_screenshot: bool = True,
    ) -> Path:
        screenshot = run_dir / "library_results" / "slide-001.png"
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        if include_screenshot:
            screenshot.write_bytes(b"fake-png")

        candidate = {
            "slide_id": "lib-slide-001",
            "canonical_slide_id": "deckmaster:library:001",
            "title": "目标架构",
            "text_summary": "全渠道库存可视化目标架构。",
            "source_file": "history.pptx",
            "page_number": 12,
            "screenshot_path": str(screenshot.relative_to(run_dir)),
            "confidence": 0.82,
        }
        if not include_screenshot:
            candidate.pop("screenshot_path")

        selection = {
            "schema_version": "ppt_library_selection.v1",
            "run_id": run_id,
            "by_beat": {"beat-001": [candidate]},
        }
        path = run_dir / "library_results" / "selection.json"
        path.write_text(json.dumps(selection, ensure_ascii=False), encoding="utf-8")
        return path

    def test_valid_selection_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            input_path = self._selection_path(run_dir)

            report = ppt_library_uat.run_ppt_library_uat(
                run_dir=run_dir,
                input_path=input_path,
                require_screenshot=True,
            )

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["metrics"]["candidate_count"], 1)
            self.assertEqual(report["metrics"]["beats_with_candidates"], 1)
            self.assertEqual(report["metrics"]["missing_screenshot_count"], 0)

    def test_missing_screenshot_warns_without_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            input_path = self._selection_path(run_dir, include_screenshot=False)

            report = ppt_library_uat.run_ppt_library_uat(
                run_dir=run_dir,
                input_path=input_path,
                require_screenshot=False,
            )

            self.assertEqual(report["status"], "warning")
            self.assertGreater(report["metrics"]["missing_screenshot_count"], 0)
            self.assertTrue(
                any("screenshot" in finding["finding_id"] for finding in report["findings"])
            )

    def test_missing_screenshot_fails_when_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            input_path = self._selection_path(run_dir, include_screenshot=False)

            report = ppt_library_uat.run_ppt_library_uat(
                run_dir=run_dir,
                input_path=input_path,
                require_screenshot=True,
            )

            self.assertEqual(report["status"], "fail")
            self.assertTrue(
                any(finding["severity"] == "error" for finding in report["findings"])
            )

    def test_run_id_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp), run_id="retail-demo")
            input_path = self._selection_path(run_dir, run_id="other-run")

            report = ppt_library_uat.run_ppt_library_uat(
                run_dir=run_dir,
                input_path=input_path,
            )

            self.assertEqual(report["status"], "fail")
            self.assertTrue(
                any("run_id" in finding["finding_id"] for finding in report["findings"])
            )


if __name__ == "__main__":
    unittest.main()
