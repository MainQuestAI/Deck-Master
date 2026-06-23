from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from orchestrate.preview_builder import build_preview_from_sourcing
from runtime.run_state import (
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    create_run,
    read_json,
    write_json,
)
from runtime.sourcing_import import import_sourcing
from runtime.workspace_binding import bind_workspace
from workspace.foundation import init_workspace
from deck_master import write_plan_artifacts


class PlannerSourcingControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_b_control_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _run_with_plan(self) -> Path:
        run_dir = create_run(
            self.temp_dir / "runs",
            {"run_id": "source-run", "project_name": "Source Run", "run_mode": "fixture"},
            run_id="source-run",
        )
        write_json(
            run_dir / NARRATIVE_PLAN_NAME,
            {
                "run_id": "source-run",
                "title": "Source Run",
                "beats": [
                    {"beat_id": "beat_001", "order": 1, "page_title": "开场", "role": "opener"},
                    {"beat_id": "beat_002", "order": 2, "page_title": "方案", "role": "solution"},
                ],
            },
        )
        write_json(
            run_dir / PAGE_TASKS_NAME,
            {
                "run_id": "source-run",
                "tasks": [
                    {"beat_id": "beat_001", "order": 1},
                    {"beat_id": "beat_002", "order": 2},
                ],
            },
        )
        return run_dir

    def test_production_planner_without_claim_map_blocks(self) -> None:
        run_dir = create_run(
            self.temp_dir / "runs",
            {
                "run_id": "blocked-plan",
                "project_name": "Blocked Plan",
                "brief": "云南白药 AI 内容底座方案",
                "business_goal": "云南白药 AI 内容底座方案",
                "run_mode": "production",
            },
            run_id="blocked-plan",
        )
        request = read_json(run_dir / "request.json")

        with self.assertRaises(RunStateError):
            write_plan_artifacts(run_dir, request, planner_mode="production_narrative")

    def test_fixture_template_keeps_retail_beats(self) -> None:
        request = build_request(
            brief="零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送",
            industry="retail",
            target_pages="auto",
        )
        request["run_mode"] = "fixture"

        plan = plan_narrative(request, planner_mode="fixture_template")
        text = "\n".join(beat["page_title"] for beat in plan["beats"])

        self.assertIn("库存可视化", text)
        self.assertIn("最后一公里配送", text)
        self.assertEqual("fixture_template", plan["planner_mode"])

    def test_production_narrative_filters_restricted_retail_beats(self) -> None:
        request = build_request(
            brief="云南白药 DAM AI 内容底座方案，面向医药知识和内容中台治理",
            industry="医药",
            target_pages="auto",
        )
        request["run_mode"] = "production"

        plan = plan_narrative(request, planner_mode="production_narrative")
        text = "\n".join(beat["page_title"] for beat in plan["beats"])

        self.assertNotIn("库存可视化", text)
        self.assertNotIn("最后一公里配送", text)
        self.assertEqual("production_narrative", plan["planner_mode"])
        self.assertIn("deck_brief", plan["input_sources"])

    def test_bind_workspace_backs_up_request_and_writes_binding(self) -> None:
        run_dir = create_run(
            self.temp_dir / "runs",
            {"run_id": "bind-run", "project_name": "Bind Run", "run_mode": "fixture"},
            run_id="bind-run",
        )
        workspace = self.temp_dir / "workspace"
        init_workspace(workspace, "Binding Workspace")

        result = bind_workspace(run_dir, workspace, reason="Migrate old run")

        request = read_json(run_dir / "request.json")
        self.assertEqual(str(workspace.resolve()), request["workspace"])
        self.assertEqual("workspace_workspace", result["workspace_id"])
        self.assertEqual(result["workspace_id"], request["workspace_id"])
        self.assertTrue((Path(result["backup_dir"]) / "request.json").exists())
        self.assertTrue((run_dir / "workspace_binding.json").exists())
        self.assertIn("workspace.bound", (run_dir / "events.jsonl").read_text(encoding="utf-8"))

    def test_import_sourcing_missing_beat_fails(self) -> None:
        run_dir = self._run_with_plan()
        input_path = self.temp_dir / "bad_sourcing.json"
        write_json(
            input_path,
            {
                "schema_version": "deck_sourcing_plan.v1",
                "run_id": "source-run",
                "source": "human",
                "decisions": [
                    {
                        "beat_id": "beat_001",
                        "source_decision": "generate",
                        "decision_reason": "New page",
                        "generation_brief": "Build opener",
                    }
                ],
            },
        )

        with self.assertRaises(RunStateError):
            import_sourcing(run_dir, input_path, source="human")

    def test_import_sourcing_production_blocks_manual_placeholder(self) -> None:
        run_dir = self._run_with_plan()
        request = read_json(run_dir / "request.json")
        request["run_mode"] = "production"
        write_json(run_dir / "request.json", request)
        input_path = self.temp_dir / "production_placeholder_sourcing.json"
        write_json(
            input_path,
            {
                "schema_version": "deck_sourcing_plan.v1",
                "run_id": "source-run",
                "source": "human",
                "decisions": [
                    {
                        "beat_id": "beat_001",
                        "source_decision": "manual_placeholder",
                        "decision_reason": "No production evidence",
                        "generation_brief": "Do not ship",
                    },
                    {
                        "beat_id": "beat_002",
                        "source_decision": "generate",
                        "decision_reason": "Generate solution",
                        "generation_brief": "Build solution",
                    },
                ],
            },
        )

        with self.assertRaises(RunStateError) as ctx:
            import_sourcing(run_dir, input_path, source="human")

        self.assertIn("manual_placeholder is not allowed", str(ctx.exception))

    def test_import_sourcing_fixture_allows_manual_placeholder(self) -> None:
        run_dir = self._run_with_plan()
        input_path = self.temp_dir / "fixture_placeholder_sourcing.json"
        write_json(
            input_path,
            {
                "schema_version": "deck_sourcing_plan.v1",
                "run_id": "source-run",
                "source": "human",
                "decisions": [
                    {
                        "beat_id": "beat_001",
                        "source_decision": "manual_placeholder",
                        "decision_reason": "Fixture placeholder",
                        "generation_brief": "Fixture page",
                    },
                    {
                        "beat_id": "beat_002",
                        "source_decision": "generate",
                        "decision_reason": "Fixture generation",
                        "generation_brief": "Build solution",
                    },
                ],
            },
        )

        result = import_sourcing(run_dir, input_path, source="human")

        self.assertEqual("imported", result["status"])
        plan = read_json(run_dir / SOURCING_PLAN_NAME)
        self.assertEqual("manual_placeholder", plan["decisions"][0]["source_decision"])

    def test_production_preview_blocks_manual_placeholder(self) -> None:
        run_dir = self._run_with_plan()
        request = read_json(run_dir / "request.json")
        request["run_mode"] = "production"
        write_json(run_dir / "request.json", request)
        sourcing_plan = {
            "run_id": "source-run",
            "title": "Source Run",
            "decisions": [
                {
                    "beat_id": "beat_001",
                    "order": 1,
                    "page_title": "开场",
                    "source_decision": "manual_placeholder",
                    "decision_reason": "No source",
                }
            ],
        }

        with self.assertRaises(ValueError) as ctx:
            build_preview_from_sourcing(sourcing_plan, run_dir)

        self.assertIn("manual_placeholder sourcing is not allowed", str(ctx.exception))

    def test_import_sourcing_complete_backs_up_and_refreshes_preview(self) -> None:
        run_dir = self._run_with_plan()
        write_json(run_dir / SOURCING_PLAN_NAME, {"run_id": "source-run", "decisions": []})
        write_json(
            run_dir / "preview_manifest.json",
            {
                "run_id": "source-run",
                "title": "Source Run",
                "status": "draft",
                "pages": [
                    {
                        "page_id": "beat_001",
                        "beat_id": "beat_001",
                        "order": 1,
                        "source_type": "placeholder",
                        "preview_path": "links/beat_001.svg",
                        "narrative_role": "opener",
                        "decision": "needs_review",
                    },
                    {
                        "page_id": "beat_002",
                        "beat_id": "beat_002",
                        "order": 2,
                        "source_type": "placeholder",
                        "preview_path": "links/beat_002.svg",
                        "narrative_role": "solution",
                        "decision": "needs_review",
                    },
                ],
            },
        )
        input_path = self.temp_dir / "good_sourcing.json"
        write_json(
            input_path,
            {
                "schema_version": "deck_sourcing_plan.v1",
                "run_id": "source-run",
                "source": "human",
                "decisions": [
                    {
                        "beat_id": "beat_001",
                        "source_decision": "generate",
                        "decision_reason": "New opener",
                        "generation_brief": "Build opener",
                    },
                    {
                        "beat_id": "beat_002",
                        "source_decision": "adapt",
                        "decision_reason": "Reuse DAM structure",
                        "selected_candidate": {"candidate_id": "slide-1"},
                    },
                ],
            },
        )

        result = import_sourcing(run_dir, input_path, source="human")

        self.assertEqual("imported", result["status"])
        self.assertTrue((Path(result["backup_dir"]) / SOURCING_PLAN_NAME).exists())
        preview = read_json(run_dir / "preview_manifest.json")
        self.assertEqual(2, preview["sourcing_summary"]["total_decisions"])
        self.assertEqual("generate", preview["pages"][0]["source_decision"])
        self.assertIn("sourcing.override.imported", (run_dir / "events.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
