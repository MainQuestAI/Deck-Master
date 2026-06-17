from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.orchestration import import_plan, import_render_result, orchestration_check  # noqa: E402
from runtime.render import CANONICAL_RENDER_RESULT  # noqa: E402
from runtime.run_state import create_run, read_json, write_json  # noqa: E402


class OrchestrationEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_orch_test_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.run_dir = create_run(
            self.temp_dir,
            {
                "run_id": "orch-run",
                "project_name": "Orchestration Run",
                "business_goal": "Build a test deck",
            },
            run_id="orch-run",
        )

    def test_orchestration_check_reports_missing_context(self) -> None:
        result = orchestration_check(self.run_dir, run_mode="fixture")

        self.assertEqual("deck_orchestration_check.v1", result["schema_version"])
        self.assertEqual("blocked", result["status"])
        self.assertIn("context_manifest.json", result["missing_artifacts"])
        self.assertFalse(result["allow_external_production"])
        self.assertIn("import-context-pack", result["next_command"])
        self.assertIn("--input <context_pack.json>", result["next_command"])

    def test_import_markdown_plan_backs_up_and_writes_events(self) -> None:
        old_plan = {"run_id": "orch-run", "title": "old", "beats": []}
        (self.run_dir / "narrative_plan.json").write_text(json.dumps(old_plan), encoding="utf-8")
        (self.run_dir / "page_tasks.json").write_text(json.dumps({"run_id": "orch-run", "tasks": []}), encoding="utf-8")
        plan = self.temp_dir / "plan.md"
        plan.write_text(
            "\n".join(
                [
                    "# Human Plan",
                    "## 01｜开场定位",
                    "## 02｜监管问题",
                    "## 03｜底座架构",
                ]
            ),
            encoding="utf-8",
        )

        result = import_plan(self.run_dir, plan, source="human")

        self.assertEqual("imported", result["status"])
        self.assertEqual(3, result["beats"])
        self.assertTrue((Path(result["backup_dir"]) / "narrative_plan.json").exists())
        narrative = read_json(self.run_dir / "narrative_plan.json")
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        self.assertEqual(3, len(narrative["beats"]))
        self.assertEqual(3, len(page_tasks["tasks"]))
        events = (self.run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("plan.override.imported", events)

    def test_orchestration_check_requires_quality_before_external_production(self) -> None:
        for name in [
            "context_manifest.json",
            "deck_brief.json",
            "claim_map.json",
            "narrative_plan.json",
            "page_tasks.json",
            "sourcing_plan.json",
            "preview_manifest.json",
        ]:
            (self.run_dir / name).write_text(json.dumps({}), encoding="utf-8")

        result = orchestration_check(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_quality_gate", result["status"])
        self.assertFalse(result["allow_external_production"])

        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "draft_gate.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
        result = orchestration_check(self.run_dir, run_mode="fixture")
        self.assertEqual("ready_for_external_production", result["status"])
        self.assertTrue(result["allow_external_production"])

    def test_import_render_result_updates_preview_manifest_and_events(self) -> None:
        write_json(
            self.run_dir / "preview_manifest.json",
            {
                "run_id": "orch-run",
                "title": "Orchestration Run",
                "status": "ready",
                "pages": [
                    {
                        "page_id": "beat_01",
                        "beat_id": "beat_01",
                        "order": 1,
                        "source_type": "placeholder",
                        "preview_path": "links/old.svg",
                        "narrative_role": "opener",
                        "decision": "needs_review",
                    }
                ],
            },
        )
        artifact = self.temp_dir / "deck.pptx"
        artifact.write_text("fake", encoding="utf-8")
        render_result = self.temp_dir / "render_result.json"
        write_json(
            render_result,
            {
                "schema_version": "deck_render_result.v1",
                "run_id": "orch-run",
                "tool": "ppt-master",
                "status": "completed",
                "artifact_path": str(artifact),
                "preview_dir": "final-preview",
                "page_count": 1,
                "page_previews": [{"page_id": "beat_01", "preview_path": "final-preview/beat_01.png"}],
            },
        )

        result = import_render_result(self.run_dir, render_result)

        self.assertEqual("imported", result["status"])
        self.assertTrue(result["preview_manifest_updated"])
        preview = read_json(self.run_dir / "preview_manifest.json")
        self.assertEqual(str(artifact), preview["final_artifact_path"])
        self.assertTrue((self.run_dir / CANONICAL_RENDER_RESULT).exists())
        self.assertEqual(str(CANONICAL_RENDER_RESULT), preview["external_render_result"])
        self.assertEqual("final-preview/beat_01.png", preview["pages"][0]["preview_path"])
        events = (self.run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("external_result.imported", events)
        imports = (self.run_dir / "imports" / "import_log.jsonl").read_text(encoding="utf-8")
        self.assertIn("render_result", imports)


if __name__ == "__main__":
    unittest.main()
