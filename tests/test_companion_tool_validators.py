"""Tests for Package H — Companion Tool UAT Contracts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.validators.companion_tools import (
    validate_ppt_library_result,
    validate_render_result,
)


class PPTLibraryValidatorTest(unittest.TestCase):

    def _valid_candidate(self, **overrides) -> dict:
        base = {
            "slide_id": "lib_slide_001",
            "canonical_slide_id": "slide_xxx",
            "title": "目标架构",
            "text_summary": "全渠道库存可视化目标架构。",
            "source_file": "/tmp/history.pptx",
            "page_number": 12,
            "screenshot_path": "/tmp/screenshot.png",
            "confidence": 0.82,
            "narrative_role": "architecture",
            "page_archetype": "target_architecture",
        }
        base.update(overrides)
        return base

    def test_valid_candidate(self) -> None:
        result = validate_ppt_library_result(self._valid_candidate())
        self.assertTrue(result["valid"], result.get("errors"))

    def test_valid_candidates_list(self) -> None:
        result = validate_ppt_library_result({
            "candidates": [self._valid_candidate(), self._valid_candidate(slide_id="lib_002")]
        })
        self.assertTrue(result["valid"], result.get("errors"))

    def test_missing_slide_id(self) -> None:
        c = self._valid_candidate()
        del c["slide_id"]
        result = validate_ppt_library_result(c)
        self.assertFalse(result["valid"])
        self.assertIn("slide_id", " ".join(result["errors"]))

    def test_missing_required_fields(self) -> None:
        result = validate_ppt_library_result({"slide_id": "x"})
        self.assertFalse(result["valid"])

    def test_confidence_out_of_range(self) -> None:
        result = validate_ppt_library_result(self._valid_candidate(confidence=1.5))
        self.assertFalse(result["valid"])
        self.assertIn("confidence", " ".join(result["errors"]))

    def test_confidence_negative(self) -> None:
        result = validate_ppt_library_result(self._valid_candidate(confidence=-0.1))
        self.assertFalse(result["valid"])

    def test_page_number_not_numeric(self) -> None:
        result = validate_ppt_library_result(self._valid_candidate(page_number="abc"))
        self.assertFalse(result["valid"])
        self.assertIn("page_number", " ".join(result["errors"]))

    def test_missing_canonical_slide_id_warning(self) -> None:
        c = self._valid_candidate()
        del c["canonical_slide_id"]
        result = validate_ppt_library_result(c)
        self.assertTrue(result["valid"])
        self.assertTrue(any("canonical_slide_id" in w for w in result["warnings"]))

    def test_missing_screenshot_path_warning(self) -> None:
        c = self._valid_candidate()
        del c["screenshot_path"]
        result = validate_ppt_library_result(c)
        self.assertTrue(result["valid"])
        self.assertTrue(any("screenshot_path" in w for w in result["warnings"]))

    def test_source_file_nonexistent_warning(self) -> None:
        result = validate_ppt_library_result(self._valid_candidate(source_file="/nonexistent/path.pptx"))
        self.assertTrue(result["valid"])
        self.assertTrue(any("source_file" in w for w in result["warnings"]))

    def test_not_an_object(self) -> None:
        result = validate_ppt_library_result([])  # type: ignore[arg-type]
        self.assertFalse(result["valid"])


class RenderResultValidatorTest(unittest.TestCase):

    def _valid_render(self, **overrides) -> dict:
        base = {
            "schema_version": "deck_render_result.v1",
            "run_id": "test-run",
            "tool": "ppt-master",
            "status": "completed",
            "artifact_type": "pptx",
            "artifact_path": "/tmp/final.pptx",
            "page_count": 14,
            "errors": [],
        }
        base.update(overrides)
        return base

    def test_valid_completed(self) -> None:
        result = validate_render_result(self._valid_render())
        self.assertTrue(result["valid"], result.get("errors"))

    def test_valid_completed_v2(self) -> None:
        result = validate_render_result(
            self._valid_render(
                schema_version="deck_render_result.v2",
                source_fingerprint="a" * 64,
                artifacts=[{"artifact_id": "deck_html", "path": "/tmp/final.html"}],
            )
        )
        self.assertTrue(result["valid"], result.get("errors"))

    def test_v2_requires_artifacts(self) -> None:
        result = validate_render_result(
            self._valid_render(schema_version="deck_render_result.v2", source_fingerprint="a" * 64)
        )
        self.assertFalse(result["valid"])

    def test_valid_failed(self) -> None:
        result = validate_render_result(self._valid_render(
            status="failed",
            artifact_path="",
            errors=[{"code": "render_error", "message": "Failed."}],
        ))
        self.assertTrue(result["valid"], result.get("errors"))

    def test_wrong_schema_version(self) -> None:
        result = validate_render_result(self._valid_render(schema_version="wrong"))
        self.assertFalse(result["valid"])

    def test_missing_run_id(self) -> None:
        r = self._valid_render()
        del r["run_id"]
        result = validate_render_result(r)
        self.assertFalse(result["valid"])

    def test_completed_missing_artifact_path(self) -> None:
        result = validate_render_result(self._valid_render(artifact_path=""))
        self.assertFalse(result["valid"])

    def test_failed_missing_errors(self) -> None:
        result = validate_render_result(self._valid_render(status="failed", errors=[]))
        self.assertFalse(result["valid"])

    def test_invalid_status(self) -> None:
        result = validate_render_result(self._valid_render(status="unknown"))
        self.assertFalse(result["valid"])

    def test_page_count_not_integer(self) -> None:
        result = validate_render_result(self._valid_render(page_count="14"))
        self.assertFalse(result["valid"])

    def test_not_an_object(self) -> None:
        result = validate_render_result("not an object")  # type: ignore[arg-type]
        self.assertFalse(result["valid"])


class UATDocsExistTest(unittest.TestCase):

    def test_ppt_library_uat_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "docs" / "uat" / "ppt-library-contract-uat.md").exists())

    def test_ppt_deck_pro_max_uat_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "docs" / "uat" / "ppt-deck-pro-max-contract-uat.md").exists())

    def test_ppt_master_uat_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "docs" / "uat" / "ppt-master-contract-uat.md").exists())


if __name__ == "__main__":
    unittest.main()
