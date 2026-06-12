"""Tests for Package G — Workspace Learning Pack."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.learning.pack import build_learning_pack, show_learning_pack
from scripts.runtime.run_state import create_run, write_json


def _setup_workspace(tmp: Path) -> Path:
    ws = tmp / "workspace"
    ws.mkdir()
    (ws / "assets").mkdir()
    (ws / "runs").mkdir()
    return ws


def _add_feedback(ws: Path, events: list[dict]) -> None:
    fb_path = ws / "assets" / "asset_feedback.jsonl"
    with fb_path.open("a", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def _add_run_with_quality(ws: Path, run_id: str, findings: list[dict]) -> None:
    run_dir = create_run(ws / "runs", {"project_name": run_id}, run_id=run_id)
    quality_dir = run_dir / "quality_reports"
    quality_dir.mkdir(exist_ok=True)
    write_json(quality_dir / "draft_gate.json", {
        "gate": "draft",
        "findings": findings,
    })


class EmptyWorkspaceTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_lp_empty_")
        self.ws = _setup_workspace(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_empty_workspace_produces_valid_pack(self) -> None:
        pack = build_learning_pack(self.ws)
        self.assertEqual(pack["schema_version"], "deck_workspace_learning_pack.v1")
        self.assertEqual(pack["frequent_failure_modes"], [])
        self.assertEqual(pack["strong_assets"], [])

    def test_empty_workspace_produces_markdown(self) -> None:
        build_learning_pack(self.ws)
        summary_path = self.ws / "learning" / "agent_context_summary.md"
        self.assertTrue(summary_path.exists())
        content = summary_path.read_text(encoding="utf-8")
        self.assertIn("Workspace Learning Summary", content)

    def test_show_learning_pack_not_found(self) -> None:
        result = show_learning_pack(self.ws)
        self.assertEqual(result["status"], "not_found")


class FeedbackAggregationTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_lp_fb_")
        self.ws = _setup_workspace(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_strong_assets_from_feedback(self) -> None:
        _add_feedback(self.ws, [
            {"event_type": "preview_approved", "canonical_slide_id": "slide_aaa"},
            {"event_type": "preview_approved", "canonical_slide_id": "slide_aaa"},
            {"event_type": "delivered", "canonical_slide_id": "slide_aaa"},
            {"event_type": "preview_rejected", "canonical_slide_id": "slide_bbb"},
        ])
        pack = build_learning_pack(self.ws)
        assets = pack["strong_assets"]
        self.assertTrue(len(assets) >= 1)
        top = assets[0]
        self.assertEqual(top["canonical_slide_id"], "slide_aaa")
        self.assertEqual(top["delivered_count"], 1)


class QualityFindingAggregationTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_lp_qf_")
        self.ws = _setup_workspace(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_failure_modes_aggregated(self) -> None:
        _add_run_with_quality(self.ws, "run_01", [
            {"finding_id": "f1", "severity": "P1",
             "message": "ROI 页面缺指标证据", "repair_instruction": "补业务指标"},
        ])
        _add_run_with_quality(self.ws, "run_02", [
            {"finding_id": "f2", "severity": "P1",
             "message": "ROI 页面缺指标证据", "repair_instruction": "补业务指标"},
        ])
        pack = build_learning_pack(self.ws)
        fms = pack["frequent_failure_modes"]
        self.assertTrue(len(fms) >= 1)
        top = fms[0]
        self.assertEqual(top["count"], 2)
        self.assertIn("ROI", top["description"])

    def test_agent_guidance_from_failures(self) -> None:
        _add_run_with_quality(self.ws, "run_01", [
            {"finding_id": "f1", "severity": "P1",
             "message": "证据不足", "repair_instruction": "补充证据"},
        ])
        pack = build_learning_pack(self.ws)
        self.assertTrue(len(pack["agent_guidance"]) >= 1)


class MarkdownOutputTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_lp_md_")
        self.ws = _setup_workspace(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_markdown_contains_sections(self) -> None:
        _add_run_with_quality(self.ws, "run_01", [
            {"finding_id": "f1", "severity": "P1",
             "message": "Test failure", "repair_instruction": "Fix it"},
        ])
        build_learning_pack(self.ws)
        summary = (self.ws / "learning" / "agent_context_summary.md").read_text(encoding="utf-8")
        self.assertIn("## Frequent failure modes", summary)
        self.assertIn("## Strong assets", summary)
        self.assertIn("## Agent guidance", summary)

    def test_show_after_build(self) -> None:
        build_learning_pack(self.ws)
        result = show_learning_pack(self.ws)
        self.assertEqual(result["status"], "found")
        self.assertIn("pack", result)


if __name__ == "__main__":
    unittest.main()
