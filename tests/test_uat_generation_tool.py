"""Unit tests for v0.9.6 Generation Tool UAT contracts."""

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

generation_uat = importlib.import_module("scripts.uat.generation_tool")


class GenerationToolUATTest(unittest.TestCase):
    def _run_dir(self, root: Path, run_id: str = "retail-demo") -> Path:
        run_dir = root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.json").write_text(
            json.dumps({"run_id": run_id}, ensure_ascii=False),
            encoding="utf-8",
        )
        tasks_dir = run_dir / "generation_tasks"
        tasks_dir.mkdir()
        task = {
            "schema_version": "deck_generation_task.v1",
            "run_id": run_id,
            "task_id": "task-001",
            "beat_id": "beat-001",
            "generation_brief": "Create an architecture slide.",
            "workspace_refs": ["visual-system/spec_lock.md"],
            "quality_requirements": ["Must include a main claim."],
            "expected_outputs": ["preview_path", "artifact_path"],
        }
        (tasks_dir / "index.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_generation_task_index.v1",
                    "run_id": run_id,
                    "tasks": [task],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return run_dir

    def _write_result(
        self,
        run_dir: Path,
        *,
        preview_path: str = "previews/generated/beat-001.png",
        run_id: str = "retail-demo",
    ) -> Path:
        if preview_path and not preview_path.startswith("../"):
            preview_file = run_dir / preview_path
            preview_file.parent.mkdir(parents=True, exist_ok=True)
            preview_file.write_bytes(b"fake-png")

        results_dir = run_dir / "generation_results"
        results_dir.mkdir(exist_ok=True)
        result = {
            "schema_version": "deck_generation_result.v1",
            "run_id": run_id,
            "tool": "ppt-deck-pro-max",
            "task_id": "task-001",
            "beat_id": "beat-001",
            "status": "completed",
            "preview_path": preview_path,
            "errors": [],
        }
        path = results_dir / "task-001.json"
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return path

    def test_tasks_array_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))

            report = generation_uat.run_generation_tool_uat(
                run_dir=run_dir,
                tool="ppt-deck-pro-max",
            )

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["metrics"]["task_count"], 1)
            self.assertEqual(report["metrics"]["enhanced_task_count"], 1)

    def test_summary_index_loads_canonical_task_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            tasks_dir = run_dir / "generation_tasks"
            index = json.loads((tasks_dir / "index.json").read_text(encoding="utf-8"))
            full_task = index["tasks"][0]
            (tasks_dir / "task-001.json").write_text(json.dumps(full_task), encoding="utf-8")
            index["tasks"] = [{"task_id": "task-001", "page_task_id": "page-001"}]
            (tasks_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

            report = generation_uat.run_generation_tool_uat(run_dir, write=False)

            self.assertEqual("pass", report["status"], report)
            self.assertEqual(1, report["metrics"]["enhanced_task_count"])
            self.assertFalse(any("missing schema_version" in item["message"] for item in report["findings"]))

    def test_summary_index_missing_canonical_task_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            index_path = run_dir / "generation_tasks" / "index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["tasks"] = [{"task_id": "task-001", "page_task_id": "page-001"}]
            index_path.write_text(json.dumps(index), encoding="utf-8")

            report = generation_uat.run_generation_tool_uat(run_dir, write=False)

            self.assertEqual("fail", report["status"])
            self.assertTrue(any("generation_task_file_task-001" in item["finding_id"] for item in report["findings"]))

    def test_require_preview_missing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            self._write_result(run_dir, preview_path="")

            report = generation_uat.run_generation_tool_uat(
                run_dir=run_dir,
                tool="ppt-deck-pro-max",
                require_preview=True,
            )

            self.assertEqual(report["status"], "fail")
            self.assertTrue(
                any("preview" in finding["finding_id"] for finding in report["findings"])
            )

    def test_preview_path_outside_run_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            self._write_result(run_dir, preview_path="../outside.png")

            report = generation_uat.run_generation_tool_uat(
                run_dir=run_dir,
                tool="ppt-deck-pro-max",
            )

            self.assertEqual(report["status"], "fail")
            self.assertTrue(
                any("outside" in finding["finding_id"] for finding in report["findings"])
            )


if __name__ == "__main__":
    unittest.main()
