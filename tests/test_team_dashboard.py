"""Tests for scripts.team.dashboard — P5A-D Team Dashboards."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.team.dashboard import (
    generate_asset_usage_dashboard,
    generate_team_quality_dashboard,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TestTeamQualityDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        self.runs = Path(self.tmp.name) / "runs"
        self.ws.mkdir(parents=True)
        self.runs.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # ── 空 runs 目录 ─────────────────────────────────────────────

    def test_empty_runs_produces_zero_dashboard(self) -> None:
        dash = generate_team_quality_dashboard(self.ws, self.runs)
        m = dash["metrics"]
        self.assertEqual(m["run_count"], 0)
        self.assertEqual(m["p0_finding_count"], 0)
        self.assertEqual(m["delivered_deck_count"], 0)
        self.assertEqual(dash["schema_version"], "deck_team_dashboard.v1")

    def test_empty_runs_writes_file(self) -> None:
        generate_team_quality_dashboard(self.ws, self.runs)
        path = self.ws / "dashboards" / "team_quality_dashboard.json"
        self.assertTrue(path.exists())

    # ── 多 run 聚合 ──────────────────────────────────────────────

    def test_aggregates_multiple_runs(self) -> None:
        # Run A: draft gate score 80, 1 P0 finding, 2 pages (1 approved), reuse, delivered
        run_a = self.runs / "run_a"
        _write_json(run_a / "quality_reports" / "draft_gate.json", {
            "scorecard": {"clarity": 80, "structure": 80},
            "findings": [{"severity": "P0", "dimension": "evidence"}],
        })
        _write_json(run_a / "preview_manifest.json", {
            "pages": [
                {"decision": "approved"},
                {"decision": "revise"},
            ],
        })
        _write_json(run_a / "sourcing_plan.json", {
            "decisions": [
                {"source_decision": "reuse"},
                {"source_decision": "create"},
            ],
        })
        _write_json(run_a / "delivery" / "delivery_outcome.json", {"delivered": True})

        # Run B: draft gate score 60, 1 P1 finding, 1 page (approved), no reuse, not delivered
        run_b = self.runs / "run_b"
        _write_json(run_b / "quality_reports" / "draft_gate.json", {
            "scorecard": {"clarity": 60},
            "findings": [{"severity": "P1", "dimension": "narrative"}],
        })
        _write_json(run_b / "preview_manifest.json", {
            "pages": [{"decision": "approved"}],
        })
        _write_json(run_b / "sourcing_plan.json", {
            "decisions": [{"source_decision": "create"}],
        })
        _write_json(run_b / "delivery" / "delivery_outcome.json", {"delivered": False})

        dash = generate_team_quality_dashboard(self.ws, self.runs)
        m = dash["metrics"]

        self.assertEqual(m["run_count"], 2)
        # avg draft score: (80+60)/2 = 70
        self.assertEqual(m["average_draft_gate_score"], 70.0)
        self.assertEqual(m["p0_finding_count"], 1)
        self.assertEqual(m["p1_finding_count"], 1)
        # approved_page_rate: 2/3 ≈ 0.67
        self.assertAlmostEqual(m["approved_page_rate"], 0.67, places=2)
        # reuse_rate: 1/3 ≈ 0.33
        self.assertAlmostEqual(m["historical_reuse_rate"], 0.33, places=2)
        self.assertEqual(m["delivered_deck_count"], 1)

    def test_top_failure_modes_sorted(self) -> None:
        run = self.runs / "run_x"
        _write_json(run / "quality_reports" / "draft_gate.json", {
            "scorecard": {},
            "findings": [
                {"severity": "P1", "dimension": "evidence"},
                {"severity": "P0", "dimension": "evidence"},
                {"severity": "P1", "dimension": "narrative"},
            ],
        })
        dash = generate_team_quality_dashboard(self.ws, self.runs)
        modes = dash["top_failure_modes"]
        self.assertGreaterEqual(len(modes), 1)
        # evidence should be first (count=2 > narrative count=1)
        self.assertEqual(modes[0]["dimension"], "evidence")
        self.assertEqual(modes[0]["count"], 2)

    # ── metrics 计算边界 ─────────────────────────────────────────

    def test_draft_score_only_counts_runs_with_scorecard(self) -> None:
        # Run with empty scorecard should not affect average
        run = self.runs / "run_no_score"
        _write_json(run / "quality_reports" / "draft_gate.json", {
            "scorecard": {},
            "findings": [],
        })
        dash = generate_team_quality_dashboard(self.ws, self.runs)
        # No valid scorecard entries → default 0
        self.assertEqual(dash["metrics"]["average_draft_gate_score"], 0)

    def test_nonexistent_runs_dir(self) -> None:
        dash = generate_team_quality_dashboard(self.ws, self.runs / "nonexistent")
        self.assertEqual(dash["metrics"]["run_count"], 0)


class TestAssetUsageDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        self.ws.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_empty_workspace(self) -> None:
        dash = generate_asset_usage_dashboard(self.ws)
        m = dash["metrics"]
        self.assertEqual(m["total_assets"], 0)
        self.assertEqual(m["total_approvals"], 0)
        self.assertEqual(dash["schema_version"], "deck_asset_dashboard.v1")

    def test_counts_feedback_events(self) -> None:
        # Create asset graph
        _write_json(self.ws / "assets" / "asset_graph.json", {
            "assets": [{"id": "a1"}, {"id": "a2"}],
        })
        # Create feedback
        fb_path = self.ws / "assets" / "asset_feedback.jsonl"
        fb_path.parent.mkdir(parents=True, exist_ok=True)
        events = [
            {"event_type": "preview_approved"},
            {"event_type": "preview_approved"},
            {"event_type": "preview_rejected"},
            {"event_type": "delivered"},
        ]
        fb_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

        dash = generate_asset_usage_dashboard(self.ws)
        m = dash["metrics"]
        self.assertEqual(m["total_assets"], 2)
        self.assertEqual(m["total_approvals"], 2)
        self.assertEqual(m["total_rejections"], 1)
        self.assertEqual(m["total_deliveries"], 1)


if __name__ == "__main__":
    unittest.main()
