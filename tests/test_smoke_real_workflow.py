"""Unit tests for v0.9.6 real workflow smoke contracts."""

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

real_workflow_smoke = importlib.import_module("scripts.uat.real_workflow_smoke")


class RealWorkflowSmokeTest(unittest.TestCase):
    def _complete_run(self, root: Path, run_id: str = "retail-demo") -> Path:
        run_dir = root / run_id
        run_dir.mkdir(parents=True)
        fixture_docs = {
            "request.json": {"run_id": run_id, "project_name": "Retail Demo"},
            "context_manifest.json": {"run_id": run_id, "sources": []},
            "deck_brief.json": {"run_id": run_id, "title": "Retail Demo"},
            "claim_map.json": {"run_id": run_id, "claims": []},
            "narrative_plan.json": {"run_id": run_id, "beats": []},
            "page_tasks.json": {
                "run_id": run_id,
                "tasks": [
                    {
                        "beat_id": "beat-001",
                        "source_decision": "generate",
                        "review_status": "approved",
                        "planning": {
                            "core_claim": "Retail operations need unified visibility.",
                            "decision_intent": "generate",
                        },
                    }
                ],
            },
            "sourcing_plan.json": {
                "run_id": run_id,
                "decisions": [{"beat_id": "beat-001", "source_decision": "generate"}],
            },
            "preview_manifest.json": {
                "run_id": run_id,
                "title": "Retail Demo",
                "status": "ready",
                "pages": [
                    {
                        "page_id": "beat-001",
                        "beat_id": "beat-001",
                        "order": 1,
                        "title": "Unified visibility",
                        "source_type": "generated",
                        "preview_path": "previews/beat-001.png",
                        "narrative_role": "architecture",
                        "decision": "approved",
                        "review_status": "approved",
                    }
                ],
            },
        }
        (run_dir / "previews").mkdir()
        (run_dir / "previews" / "beat-001.png").write_bytes(b"fake-png")
        for name, payload in fixture_docs.items():
            (run_dir / name).write_text(json.dumps(payload), encoding="utf-8")
        (run_dir / "generation_tasks").mkdir()
        (run_dir / "generation_tasks" / "index.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_generation_task_index.v1",
                    "run_id": run_id,
                    "tasks": [
                        {
                            "schema_version": "deck_generation_task.v1",
                            "run_id": run_id,
                            "task_id": "task-001",
                            "beat_id": "beat-001",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "quality_reports").mkdir()
        (run_dir / "quality_reports" / "draft_gate.json").write_text(
            json.dumps({"status": "pass"}), encoding="utf-8"
        )
        (run_dir / "advisor_tasks").mkdir()
        (run_dir / "advisor_tasks" / "narrative_advice_task.json").write_text("{}", encoding="utf-8")
        (run_dir / "quality_review_tasks").mkdir()
        (run_dir / "uat_reports").mkdir()
        for report_name in [
            "ppt_library_uat.json",
            "generation_tool_uat.json",
            "render_tool_uat.json",
        ]:
            (run_dir / "uat_reports" / report_name).write_text(
                json.dumps({"schema_version": "deck_uat_report.v1", "status": "pass"}),
                encoding="utf-8",
            )
        return run_dir

    def _set_companion_status(self, run_dir: Path, report_name: str, status: str, *, schema: str = "deck_uat_report.v1") -> None:
        (run_dir / "uat_reports" / report_name).write_text(
            json.dumps({"schema_version": schema, "status": status, "private": "/Users/example/raw"}),
            encoding="utf-8",
        )

    def test_complete_fixture_passes_or_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._complete_run(Path(tmp))

            report = real_workflow_smoke.run_real_workflow_smoke(run_dir=run_dir)

            self.assertIn(report["status"], {"pass", "warning"})
            self.assertEqual(report["schema_version"], "deck_real_workflow_smoke.v1")
            self.assertRegex(report["run_id"], r"^uat-[a-f0-9]{16}$")
            self.assertIn(report["phases"]["run_artifacts"], {"pass", "warning"})
            self.assertEqual(report["phases"]["companion_uat"], "pass")

    def test_missing_preview_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._complete_run(Path(tmp))
            (run_dir / "preview_manifest.json").unlink()

            report = real_workflow_smoke.run_real_workflow_smoke(run_dir=run_dir)

            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["phases"]["run_artifacts"], "fail")
            self.assertTrue(
                any("preview_manifest" in finding["finding_id"] for finding in report["findings"])
            )

    def test_companion_report_status_controls_phase(self) -> None:
        cases = (("pass", "pass"), ("warning", "warning"), ("fail", "fail"))
        for companion_status, expected in cases:
            with self.subTest(status=companion_status), tempfile.TemporaryDirectory() as tmp:
                run_dir = self._complete_run(Path(tmp))
                self._set_companion_status(run_dir, "ppt_library_uat.json", companion_status)
                report = real_workflow_smoke.run_real_workflow_smoke(run_dir=run_dir, write=False)

                self.assertEqual(expected, report["phases"]["companion_uat"])
                self.assertEqual(expected, report["status"])
                self.assertNotIn("/Users/example/raw", json.dumps(report))

    def test_invalid_companion_schema_fails_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._complete_run(Path(tmp))
            self._set_companion_status(run_dir, "ppt_library_uat.json", "pass", schema="wrong")
            report = real_workflow_smoke.run_real_workflow_smoke(run_dir=run_dir, write=False)

            self.assertEqual("fail", report["phases"]["companion_uat"])
            self.assertEqual("fail", report["status"])


if __name__ == "__main__":
    unittest.main()
