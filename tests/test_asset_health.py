from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assets.schema import save_asset_graph
from assets.feedback import append_feedback
from assets.health import evaluate_asset_health
from assets.archetype_tagger import tag_archetypes


class AssetHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _save_graph(self, assets: list[dict]) -> None:
        save_asset_graph(self.temp_dir, {"schema_version": "deck_asset_graph.v1", "assets": assets})

    # --- low_approval_rate ---

    def test_low_approval_rate_flagged_when_below_half_with_3plus_feedback(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-low",
            "title": "Low Approval Slide",
            "screenshot_available": True,
            "health_flags": [],
        }])
        # 1 approval + 3 rejections = rate 0.25 < 0.5
        append_feedback(self.temp_dir, "preview_approved", "slide-low")
        append_feedback(self.temp_dir, "preview_rejected", "slide-low")
        append_feedback(self.temp_dir, "preview_rejected", "slide-low")
        append_feedback(self.temp_dir, "preview_rejected", "slide-low")

        report = evaluate_asset_health(self.temp_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-low")
        self.assertIn("low_approval_rate", asset_report["health_flags"])

    # --- missing_screenshot ---

    def test_missing_screenshot_flagged(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-no-ss",
            "title": "No Screenshot",
            "screenshot_available": False,
            "health_flags": [],
        }])
        # 引用该 asset 避免 orphan flag 干扰本测试断言
        append_feedback(self.temp_dir, "preview_approved", "slide-no-ss")

        report = evaluate_asset_health(self.temp_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-no-ss")
        self.assertIn("missing_screenshot", asset_report["health_flags"])

    # --- orphan_asset ---

    def test_orphan_asset_flagged_when_not_referenced(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-orphan",
            "title": "Orphan Slide",
            "screenshot_available": True,
            "health_flags": [],
        }])
        # 不写任何 feedback，也不提供 runs_dir → 该 asset 未被引用

        report = evaluate_asset_health(self.temp_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-orphan")
        self.assertIn("orphan_asset", asset_report["health_flags"])

    def test_orphan_cleared_when_referenced_in_run(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-used",
            "title": "Used Slide",
            "screenshot_available": True,
            "health_flags": [],
        }])
        # 在 runs_dir 中写入 asset_refs 引用该 slide
        runs_dir = self.temp_dir / "runs"
        run_dir = runs_dir / "run-001"
        run_dir.mkdir(parents=True)
        refs = {"asset_refs": [{"canonical_slide_id": "slide-used"}]}
        (run_dir / "asset_refs.json").write_text(json.dumps(refs), encoding="utf-8")

        report = evaluate_asset_health(self.temp_dir, runs_dir=runs_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-used")
        self.assertNotIn("orphan_asset", asset_report["health_flags"])

    # --- healthy asset ---

    def test_healthy_asset_has_no_flags(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-healthy",
            "title": "Healthy Slide",
            "screenshot_available": True,
            "health_flags": [],
        }])
        # 给出足够的 approval 避免 low_approval_rate
        append_feedback(self.temp_dir, "preview_approved", "slide-healthy")
        append_feedback(self.temp_dir, "preview_approved", "slide-healthy")
        append_feedback(self.temp_dir, "preview_approved", "slide-healthy")

        report = evaluate_asset_health(self.temp_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-healthy")
        self.assertEqual([], asset_report["health_flags"])

    # --- empty graph ---

    def test_empty_graph_returns_empty_report(self) -> None:
        # 不写 graph，load_asset_graph 返回空列表
        report = evaluate_asset_health(self.temp_dir)

        self.assertEqual(0, report["total_assets"])
        self.assertEqual(0, report["healthy_count"])
        self.assertEqual(0, report["flagged_count"])
        self.assertEqual([], report["assets"])

    # --- confidential_risk ---

    def test_confidential_risk_flagged_for_needs_redaction(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-conf",
            "title": "Confidential",
            "screenshot_available": True,
            "publication_status": "needs_redaction",
            "health_flags": [],
        }])
        append_feedback(self.temp_dir, "preview_approved", "slide-conf")

        report = evaluate_asset_health(self.temp_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-conf")
        self.assertIn("confidential_risk", asset_report["health_flags"])

    # --- report written to disk ---

    def test_report_written_to_file(self) -> None:
        self._save_graph([])
        evaluate_asset_health(self.temp_dir)

        report_path = self.temp_dir / "assets" / "asset_health_report.json"
        self.assertTrue(report_path.exists())
        data = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual("deck_asset_health.v1", data["schema_version"])

    # --- high_rejection_rate ---

    def test_high_rejection_rate_flagged(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-rej",
            "title": "Rejected Slide",
            "screenshot_available": True,
            "health_flags": [],
        }])
        append_feedback(self.temp_dir, "preview_rejected", "slide-rej")
        append_feedback(self.temp_dir, "preview_rejected", "slide-rej")

        report = evaluate_asset_health(self.temp_dir)

        asset_report = next(a for a in report["assets"] if a["canonical_slide_id"] == "slide-rej")
        self.assertIn("high_rejection_rate", asset_report["health_flags"])

    # --- health_flags persisted back to graph ---

    def test_health_flags_persisted_to_asset_graph(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "slide-persist",
            "title": "Persist Test",
            "screenshot_available": False,
            "health_flags": [],
        }])
        append_feedback(self.temp_dir, "preview_approved", "slide-persist")

        evaluate_asset_health(self.temp_dir)

        from assets.schema import load_asset_graph
        graph = load_asset_graph(self.temp_dir)
        asset = next(a for a in graph["assets"] if a["canonical_slide_id"] == "slide-persist")
        self.assertIn("missing_screenshot", asset["health_flags"])


class ArchetypeTaggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _save_graph(self, assets: list[dict]) -> None:
        save_asset_graph(self.temp_dir, {"schema_version": "deck_asset_graph.v1", "assets": assets})

    def test_tag_by_title_keywords(self) -> None:
        self._save_graph([
            {"canonical_slide_id": "s1", "title": "核心问题与挑战", "metadata": {}},
            {"canonical_slide_id": "s2", "title": "系统架构总览", "metadata": {}},
        ])

        result = tag_archetypes(self.temp_dir)

        self.assertEqual(2, result["tagged_count"])
        from assets.schema import load_asset_graph
        graph = load_asset_graph(self.temp_dir)
        s1 = next(a for a in graph["assets"] if a["canonical_slide_id"] == "s1")
        s2 = next(a for a in graph["assets"] if a["canonical_slide_id"] == "s2")
        self.assertIn("problem_statement", s1["archetypes"])
        self.assertIn("architecture", s2["archetypes"])

    def test_tag_by_metadata_role(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "s3",
            "title": "某页",
            "metadata": {"role": "case study page"},
        }])

        tag_archetypes(self.temp_dir)

        from assets.schema import load_asset_graph
        graph = load_asset_graph(self.temp_dir)
        s3 = next(a for a in graph["assets"] if a["canonical_slide_id"] == "s3")
        self.assertIn("case_study", s3["archetypes"])

    def test_no_match_gives_empty_archetypes(self) -> None:
        self._save_graph([{
            "canonical_slide_id": "s4",
            "title": "普通页面没有关键词",
            "metadata": {},
        }])

        result = tag_archetypes(self.temp_dir)

        self.assertEqual(0, result["tagged_count"])
        from assets.schema import load_asset_graph
        graph = load_asset_graph(self.temp_dir)
        s4 = next(a for a in graph["assets"] if a["canonical_slide_id"] == "s4")
        self.assertEqual([], s4["archetypes"])

    def test_empty_graph_returns_zero(self) -> None:
        result = tag_archetypes(self.temp_dir)
        self.assertEqual(0, result["total_assets"])
        self.assertEqual(0, result["tagged_count"])


if __name__ == "__main__":
    unittest.main()
