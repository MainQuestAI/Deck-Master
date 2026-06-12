"""Tests for Package E — Build Tool Handoff / Handback Contract."""

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

from scripts.generation.handback import (
    RESULT_SCHEMA_VERSION,
    GenerationHandbackError,
    import_generation_result,
    prepare_generation_handoff,
    refresh_preview_from_generation,
    validate_generation_result,
)
from scripts.runtime.run_state import create_run, read_json, write_json


def _setup_run(tmp: Path) -> Path:
    runs_dir = tmp / "runs"
    runs_dir.mkdir()
    run_dir = create_run(runs_dir, {"project_name": "GenTest"}, run_id="gen-test")
    write_json(run_dir / "page_tasks.json", {
        "tasks": [
            {"beat_id": "beat_001", "planning": {"core_claim": "Test claim", "evidence_need": []}},
            {"beat_id": "beat_004", "planning": {"core_claim": "ROI claim", "evidence_need": ["metric_a"]}},
        ]
    })
    # Create generation tasks.
    tasks_dir = run_dir / "generation_tasks"
    tasks_dir.mkdir(exist_ok=True)
    write_json(tasks_dir / "index.json", {
        "task_ids": ["generation_001_beat_001", "generation_002_beat_004"],
    })
    write_json(tasks_dir / "generation_001_beat_001.json", {
        "task_id": "generation_001_beat_001",
        "beat_id": "beat_001",
        "page_title": "Test page",
        "source_decision": "generate",
        "status": "pending",
    })
    write_json(tasks_dir / "generation_002_beat_004.json", {
        "task_id": "generation_002_beat_004",
        "beat_id": "beat_004",
        "page_title": "ROI page",
        "source_decision": "generate",
        "status": "pending",
    })
    # Create preview manifest.
    write_json(run_dir / "preview_manifest.json", {
        "run_id": "gen-test",
        "pages": [
            {"beat_id": "beat_001", "preview_image": "", "source_type": "placeholder"},
            {"beat_id": "beat_004", "preview_image": "", "source_type": "placeholder"},
        ],
    })
    return run_dir


def _completed_result(**overrides) -> dict:
    base = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": "gen-test",
        "tool": "ppt-deck-pro-max",
        "task_id": "generation_001_beat_001",
        "beat_id": "beat_001",
        "status": "completed",
        "artifact_type": "pptx_slide",
        "artifact_path": "generated_assets/beat_001/slide.pptx",
        "preview_path": "generated_assets/beat_001/preview.png",
        "notes": "Generated.",
        "errors": [],
    }
    base.update(overrides)
    return base


def _failed_result(**overrides) -> dict:
    base = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": "gen-test",
        "tool": "ppt-deck-pro-max",
        "task_id": "generation_002_beat_004",
        "beat_id": "beat_004",
        "status": "failed",
        "artifact_type": "",
        "artifact_path": "",
        "preview_path": "",
        "notes": "",
        "errors": [{"code": "missing_reference_asset", "message": "Reference slide not found."}],
    }
    base.update(overrides)
    return base


class GenerationResultValidationTest(unittest.TestCase):

    def test_valid_completed(self) -> None:
        result = validate_generation_result(_completed_result())
        self.assertTrue(result["valid"], result.get("errors"))

    def test_valid_failed(self) -> None:
        result = validate_generation_result(_failed_result())
        self.assertTrue(result["valid"], result.get("errors"))

    def test_missing_schema_version(self) -> None:
        res = _completed_result()
        del res["schema_version"]
        result = validate_generation_result(res)
        self.assertFalse(result["valid"])

    def test_completed_missing_paths(self) -> None:
        res = _completed_result(artifact_path="", preview_path="")
        result = validate_generation_result(res)
        self.assertFalse(result["valid"])

    def test_failed_missing_errors(self) -> None:
        res = _failed_result(errors=[])
        result = validate_generation_result(res)
        self.assertFalse(result["valid"])

    def test_invalid_status(self) -> None:
        result = validate_generation_result(_completed_result(status="unknown"))
        self.assertFalse(result["valid"])

    def test_missing_beat_id(self) -> None:
        res = _completed_result()
        del res["beat_id"]
        result = validate_generation_result(res)
        self.assertFalse(result["valid"])


class GenerationImportTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_gen_import_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_completed(self) -> None:
        result = import_generation_result(self.run_dir, _completed_result())
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["result_status"], "completed")
        # Task status should be updated.
        task = read_json(self.run_dir / "generation_tasks" / "generation_001_beat_001.json")
        self.assertEqual(task["status"], "completed")

    def test_import_failed(self) -> None:
        result = import_generation_result(self.run_dir, _failed_result())
        self.assertEqual(result["result_status"], "failed")
        task = read_json(self.run_dir / "generation_tasks" / "generation_002_beat_004.json")
        self.assertEqual(task["status"], "failed")

    def test_import_partial(self) -> None:
        partial = _completed_result(
            status="partial",
            preview_path="",
            artifact_path="generated_assets/beat_001/slide.pptx",
        )
        result = import_generation_result(self.run_dir, partial)
        self.assertEqual(result["result_status"], "partial")

    def test_locked_page_blocks(self) -> None:
        # Lock beat_001.
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        page_tasks["tasks"][0]["locked"] = True
        write_json(self.run_dir / "page_tasks.json", page_tasks)
        with self.assertRaises(GenerationHandbackError) as ctx:
            import_generation_result(self.run_dir, _completed_result())
        self.assertIn("locked", str(ctx.exception))

    def test_locked_page_force_override(self) -> None:
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        page_tasks["tasks"][0]["locked"] = True
        write_json(self.run_dir / "page_tasks.json", page_tasks)
        result = import_generation_result(self.run_dir, _completed_result(), force=True)
        self.assertEqual(result["status"], "imported")

    def test_bad_json_rejected(self) -> None:
        with self.assertRaises(GenerationHandbackError):
            import_generation_result(self.run_dir, {"schema_version": "wrong"})

    def test_event_written_after_import(self) -> None:
        from scripts.runtime.events import read_events
        import_generation_result(self.run_dir, _completed_result())
        events = read_events(self.run_dir)
        gen_events = [e for e in events if e.get("step") == "generation_result.imported"]
        self.assertTrue(len(gen_events) >= 1)


class GenerationPreviewRefreshTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_gen_refresh_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_refresh_after_completed_import(self) -> None:
        import_generation_result(self.run_dir, _completed_result())
        result = refresh_preview_from_generation(self.run_dir)
        self.assertEqual(result["status"], "refreshed")
        self.assertIn("beat_001", result["updated"])
        # Preview manifest should be updated.
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["beat_id"] == "beat_001")
        self.assertEqual(page["source_type"], "generated")
        self.assertIn("preview.png", page["preview_image"])

    def test_refresh_no_results(self) -> None:
        result = refresh_preview_from_generation(self.run_dir)
        self.assertEqual(result["status"], "no_results")


class GenerationHandoffTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_gen_hoff_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_prepare_handoff(self) -> None:
        result = prepare_generation_handoff(self.run_dir)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["task_count"], 2)
        # Task should have new fields.
        task = read_json(self.run_dir / "generation_tasks" / "generation_001_beat_001.json")
        self.assertEqual(task["schema_version"], "deck_generation_task.v1")
        self.assertIn("workspace_refs", task)
        self.assertIn("quality_requirements", task)


if __name__ == "__main__":
    unittest.main()
