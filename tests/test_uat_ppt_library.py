"""Unit tests for v0.9.6 PPT Library UAT contracts."""

from __future__ import annotations

import hashlib
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

    def _v2_selection_path(self, run_dir: Path, *, raw_source_field: str | None = None) -> Path:
        preview = run_dir / "preview_assets" / "ppt_library" / "slide-001.png"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(b"fake-png")
        candidate = {
            "candidate_id": "candidate-001",
            "slide_id": "slide-001",
            "asset_key": "canonical:slide-001",
            "title": "Target architecture",
            "text_summary": "Safe reusable architecture page.",
            "page_number": 1,
            "score": 0.9,
            "confidence": 0.9,
            "source_asset_id": hashlib.sha256(b"source").hexdigest(),
            "source_display_name": "Reference Deck.pptx",
            "screenshot_ref": "preview_assets/ppt_library/slide-001.png",
            "candidate_origin": "ppt_library",
            "reuse_policy": "reuse_or_adapt",
        }
        if raw_source_field:
            candidate[raw_source_field] = "/Users/example/private-deck.pptx"
        trace_id = hashlib.sha256(b"query").hexdigest()
        selection = {
            "schema_version": "deck_master_ppt_library_selection.v2",
            "run_id": "retail-demo",
            "status": "library_ready",
            "source": "ppt_library",
            "preview_degraded": False,
            "warnings": [],
            "selections": [
                {
                    "beat_id": "beat-001",
                    "page_task_id": "page-001",
                    "query_trace_id": trace_id,
                    "role_original": "architecture",
                    "role_strategy": "passthrough",
                    "role_mapped": "architecture",
                    "retrieval_method": "role_selection",
                    "fallback_reason": "",
                    "preview_status": "ready",
                    "preview_degraded": False,
                    "candidates": [candidate],
                }
            ],
            "by_beat": {"beat-001": [candidate]},
        }
        path = run_dir / "external" / "ppt_library" / "library_results.v2.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(selection), encoding="utf-8")
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

    def test_v2_safe_candidate_passes_without_legacy_source_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            report = ppt_library_uat.run_ppt_library_uat(
                run_dir,
                self._v2_selection_path(run_dir),
                require_screenshot=True,
                write=False,
            )

            self.assertEqual("pass", report["status"], report)
            self.assertEqual("deck_master_ppt_library_selection.v2", report["metrics"]["selection_schema"])
            self.assertFalse(any("source_file" in item["finding_id"] for item in report["findings"]))
            self.assertFalse(any("canonical_slide_id" in item["finding_id"] for item in report["findings"]))

    def test_v2_raw_source_fields_fail(self) -> None:
        for field in ("source_file", "source_path"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                run_dir = self._run_dir(Path(tmp))
                report = ppt_library_uat.run_ppt_library_uat(
                    run_dir,
                    self._v2_selection_path(run_dir, raw_source_field=field),
                    write=False,
                )

                self.assertEqual("fail", report["status"])
                self.assertTrue(any(field in item["finding_id"] for item in report["findings"]))

    def test_v2_candidate_can_appear_in_multiple_page_pools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            selection_path = self._v2_selection_path(run_dir)
            payload = json.loads(selection_path.read_text(encoding="utf-8"))
            second = json.loads(json.dumps(payload["selections"][0]))
            second["beat_id"] = "beat-002"
            second["page_task_id"] = "page-002"
            second["query_trace_id"] = hashlib.sha256(b"query-2").hexdigest()
            payload["selections"].append(second)
            selection_path.write_text(json.dumps(payload), encoding="utf-8")

            report = ppt_library_uat.run_ppt_library_uat(
                run_dir,
                selection_path,
                require_screenshot=True,
                write=False,
            )

            self.assertEqual("pass", report["status"], report)
            self.assertEqual(0, report["metrics"]["duplicate_slide_id_count"])


if __name__ == "__main__":
    unittest.main()
