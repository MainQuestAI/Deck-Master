"""Tests for Package E — Build Tool Handoff / Handback Contract."""

from __future__ import annotations

import json
import io
import shutil
import sys
import tempfile
import unittest
import hashlib
import zipfile
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.generation.handback import (
    LEGACY_RESULT_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    GenerationHandbackError,
    import_generation_result,
    prepare_generation_handoff,
    refresh_preview_from_generation,
    source_fingerprint_for_run,
    validate_generation_result,
)
from scripts.preview.manifest import load_manifest
from scripts.runtime.run_state import create_run, read_json, write_json

PNG_2X2 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc"
    b"\xff\x1f\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _pptx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pptx:
        pptx.writestr(
            "[Content_Types].xml",
            "<Types><Override PartName=\"/ppt/presentation.xml\"/>"
            "<Override PartName=\"/ppt/slides/slide1.xml\"/></Types>",
        )
        pptx.writestr("ppt/presentation.xml", "<p:presentation/>")
        pptx.writestr(
            "ppt/slides/slide1.xml",
            "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
            "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\"><a:t>Generated</a:t></p:sld>",
        )
    return buffer.getvalue()


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
    links_dir = run_dir / "links"
    links_dir.mkdir(exist_ok=True)
    (links_dir / "beat_001.svg").write_text("<svg></svg>\n", encoding="utf-8")
    (links_dir / "beat_004.svg").write_text("<svg></svg>\n", encoding="utf-8")
    write_json(run_dir / "preview_manifest.json", {
        "run_id": "gen-test",
        "title": "GenTest",
        "status": "ready",
        "pages": [
            {
                "page_id": "beat_001",
                "beat_id": "beat_001",
                "order": 1,
                "title": "Test page",
                "source_type": "placeholder",
                "preview_path": "links/beat_001.svg",
                "narrative_role": "test",
                "decision": "needs_review",
            },
            {
                "page_id": "beat_004",
                "beat_id": "beat_004",
                "order": 2,
                "title": "ROI page",
                "source_type": "placeholder",
                "preview_path": "links/beat_004.svg",
                "narrative_role": "test",
                "decision": "needs_review",
            },
        ],
    })
    return run_dir


def _write_generation_assets(
    run_dir: Path,
    *,
    beat_id: str = "beat_001",
    artifact_body: bytes | None = None,
    preview_body: bytes | None = None,
) -> None:
    generated_dir = run_dir / "generated_assets" / beat_id
    generated_dir.mkdir(parents=True, exist_ok=True)
    (generated_dir / "slide.pptx").write_bytes(artifact_body if artifact_body is not None else _pptx_bytes())
    (generated_dir / "preview.png").write_bytes(preview_body if preview_body is not None else PNG_2X2)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(
    run_dir: Path,
    relative_path: str,
    *,
    artifact_id: str,
    kind: str,
    page_id: str,
    editability: str = "unknown",
) -> dict:
    path = run_dir / relative_path
    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "path": relative_path,
        "media_type": "image/png" if relative_path.endswith(".png") else "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
        "validation_status": "validated",
        "editability": editability,
        "page_id": page_id,
        "created_at": "2026-06-22T00:00:00+00:00",
    }


def _completed_result(
    run_dir: Path,
    *,
    artifact_body: bytes | None = None,
    preview_body: bytes | None = None,
    **overrides,
) -> dict:
    _write_generation_assets(run_dir, artifact_body=artifact_body, preview_body=preview_body)
    base = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": "gen-test",
        "session_id": "session-1",
        "tool": "ppt-deck-pro-max",
        "task_id": "generation_001_beat_001",
        "beat_id": "beat_001",
        "page_id": "beat_001",
        "producer": {
            "capability": "ppt-deck-pro-max",
            "version": "test",
            "source_ref": "test",
        },
        "status": "completed",
        "source_fingerprint": source_fingerprint_for_run(run_dir),
        "artifacts": [
            _descriptor(
                run_dir,
                "generated_assets/beat_001/slide.pptx",
                artifact_id="beat_001_artifact",
                kind="page_pptx",
                page_id="beat_001",
                editability="native",
            )
        ],
        "preview": _descriptor(
            run_dir,
            "generated_assets/beat_001/preview.png",
            artifact_id="beat_001_preview",
            kind="page_png",
            page_id="beat_001",
            editability="not_applicable",
        ),
        "artifact_type": "pptx_slide",
        "artifact_path": "generated_assets/beat_001/slide.pptx",
        "preview_path": "generated_assets/beat_001/preview.png",
        "notes": "Generated.",
        "errors": [],
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _failed_result(run_dir: Path, **overrides) -> dict:
    base = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": "gen-test",
        "session_id": "session-1",
        "tool": "ppt-deck-pro-max",
        "task_id": "generation_002_beat_004",
        "beat_id": "beat_004",
        "page_id": "beat_004",
        "producer": {
            "capability": "ppt-deck-pro-max",
            "version": "test",
            "source_ref": "test",
        },
        "status": "failed",
        "source_fingerprint": source_fingerprint_for_run(run_dir),
        "artifact_type": "",
        "artifact_path": "",
        "preview_path": "",
        "notes": "",
        "errors": [{"code": "missing_reference_asset", "message": "Reference slide not found."}],
        "created_at": "2026-06-22T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _legacy_completed_result(run_dir: Path, **overrides) -> dict:
    _write_generation_assets(run_dir)
    base = {
        "schema_version": LEGACY_RESULT_SCHEMA_VERSION,
        "run_id": "gen-test",
        "session_id": "session-1",
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


class GenerationResultValidationTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_gen_validation_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_valid_completed(self) -> None:
        result = validate_generation_result(_completed_result(self.run_dir), run_dir=self.run_dir)
        self.assertTrue(result["valid"], result.get("errors"))

    def test_valid_failed(self) -> None:
        result = validate_generation_result(_failed_result(self.run_dir), run_dir=self.run_dir)
        self.assertTrue(result["valid"], result.get("errors"))

    def test_missing_schema_version(self) -> None:
        res = _completed_result(self.run_dir)
        del res["schema_version"]
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])

    def test_completed_missing_paths(self) -> None:
        res = _completed_result(self.run_dir)
        res["artifacts"] = []
        del res["preview"]
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])

    def test_failed_missing_errors(self) -> None:
        res = _failed_result(self.run_dir, errors=[])
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])

    def test_invalid_status(self) -> None:
        result = validate_generation_result(_completed_result(self.run_dir, status="unknown"), run_dir=self.run_dir)
        self.assertFalse(result["valid"])

    def test_missing_page_identity(self) -> None:
        res = _completed_result(self.run_dir)
        del res["beat_id"]
        del res["page_id"]
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])

    def test_checksum_mismatch_rejected(self) -> None:
        res = _completed_result(self.run_dir)
        res["artifacts"][0]["sha256"] = "0" * 64
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])
        self.assertTrue(any("sha256 mismatch" in error for error in result["errors"]))

    def test_stale_source_fingerprint_rejected(self) -> None:
        res = _completed_result(self.run_dir)
        res["source_fingerprint"] = "0" * 64
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])
        self.assertTrue(any("source_fingerprint is stale" in error for error in result["errors"]))

    def test_legacy_stale_source_fingerprint_rejected(self) -> None:
        res = _legacy_completed_result(self.run_dir, source_fingerprint="0" * 64)
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])
        self.assertTrue(any("source_fingerprint is stale" in error for error in result["errors"]))

    def test_missing_artifact_file_rejected(self) -> None:
        res = _completed_result(self.run_dir)
        (self.run_dir / "generated_assets" / "beat_001" / "slide.pptx").unlink()
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])

    def test_production_placeholder_rejected(self) -> None:
        res = _completed_result(
            self.run_dir,
            artifact_body=b"deck-master bundled generation placeholder",
        )
        result = validate_generation_result(res, run_dir=self.run_dir)
        self.assertFalse(result["valid"])
        self.assertTrue(any("placeholder" in error for error in result["errors"]))


class GenerationImportTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_gen_import_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_completed(self) -> None:
        result = import_generation_result(self.run_dir, _completed_result(self.run_dir))
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["result_status"], "completed")
        # Task status should be updated.
        task = read_json(self.run_dir / "generation_tasks" / "generation_001_beat_001.json")
        self.assertEqual(task["status"], "completed")

    def test_import_failed(self) -> None:
        result = import_generation_result(self.run_dir, _failed_result(self.run_dir))
        self.assertEqual(result["result_status"], "failed")
        task = read_json(self.run_dir / "generation_tasks" / "generation_002_beat_004.json")
        self.assertEqual(task["status"], "failed")

    def test_import_partial(self) -> None:
        partial = _completed_result(
            self.run_dir,
            status="partial",
        )
        result = import_generation_result(self.run_dir, partial)
        self.assertEqual(result["result_status"], "partial")

    def test_import_migrates_legacy_v1_result(self) -> None:
        result = import_generation_result(self.run_dir, _legacy_completed_result(self.run_dir))
        self.assertEqual(result["result_status"], "completed")
        written = read_json(self.run_dir / "generation_results" / "generation_001_beat_001.json")
        self.assertEqual(RESULT_SCHEMA_VERSION, written["schema_version"])
        self.assertEqual(LEGACY_RESULT_SCHEMA_VERSION, written["source_schema_version"])
        self.assertEqual(source_fingerprint_for_run(self.run_dir), written["source_fingerprint"])

    def test_locked_page_blocks(self) -> None:
        # Lock beat_001.
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        page_tasks["tasks"][0]["locked"] = True
        write_json(self.run_dir / "page_tasks.json", page_tasks)
        with self.assertRaises(GenerationHandbackError) as ctx:
            import_generation_result(self.run_dir, _completed_result(self.run_dir))
        self.assertIn("locked", str(ctx.exception))

    def test_locked_page_force_override(self) -> None:
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        page_tasks["tasks"][0]["locked"] = True
        write_json(self.run_dir / "page_tasks.json", page_tasks)
        result = import_generation_result(self.run_dir, _completed_result(self.run_dir), force=True)
        self.assertEqual(result["status"], "imported")

    def test_bad_json_rejected(self) -> None:
        with self.assertRaises(GenerationHandbackError):
            import_generation_result(self.run_dir, {"schema_version": "wrong"})

    def test_import_rejects_run_id_mismatch(self) -> None:
        with self.assertRaises(GenerationHandbackError) as ctx:
            import_generation_result(self.run_dir, _completed_result(self.run_dir, run_id="other-run"))
        self.assertIn("run_id mismatch", str(ctx.exception))
        result_path = self.run_dir / "generation_results" / "generation_001_beat_001.json"
        self.assertFalse(result_path.exists())

    def test_event_written_after_import(self) -> None:
        from scripts.runtime.events import read_events
        import_generation_result(self.run_dir, _completed_result(self.run_dir))
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
        import_generation_result(self.run_dir, _completed_result(self.run_dir))
        result = refresh_preview_from_generation(self.run_dir)
        self.assertEqual(result["status"], "refreshed")
        self.assertIn("beat_001", result["updated"])
        # Preview manifest should be updated.
        preview = load_manifest(self.run_dir)
        page = next(p for p in preview["pages"] if p["beat_id"] == "beat_001")
        self.assertEqual(page["source_type"], "generated")
        self.assertEqual(page["preview_path"], "generated_assets/beat_001/preview.png")
        self.assertEqual(page["previous_preview_path"], "links/beat_001.svg")
        self.assertEqual(page["source_preview_asset"], "generated_assets/beat_001/preview.png")
        self.assertEqual(page["generation_status"], "completed")

    def test_import_rejects_preview_path_outside_run(self) -> None:
        result = _completed_result(self.run_dir, preview_path="../outside.png")
        result["preview"]["path"] = "../outside.png"
        with self.assertRaises(GenerationHandbackError) as ctx:
            import_generation_result(self.run_dir, result)
        self.assertIn("run-relative", str(ctx.exception))

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

    def test_prepare_handoff_real_task_builder_format(self) -> None:
        """Regression: real create-generation-tasks writes index.json with
        {"tasks": [task_dict, ...]}, not {"task_ids": [...]}. handoff must
        read both formats."""
        # Overwrite index.json with real task_builder format.
        tasks_dir = self.run_dir / "generation_tasks"
        write_json(tasks_dir / "index.json", {
            "run_id": "gen-test",
            "deck_pro_max_project": str(tasks_dir.parent / "deck_pro_max_project"),
            "tasks": [
                {
                    "task_id": "generation_001_beat_001",
                    "beat_id": "beat_001",
                    "page_title": "Test page",
                    "source_decision": "generate",
                    "status": "pending",
                },
                {
                    "task_id": "generation_002_beat_004",
                    "beat_id": "beat_004",
                    "page_title": "ROI page",
                    "source_decision": "generate",
                    "status": "pending",
                },
            ],
        })
        result = prepare_generation_handoff(self.run_dir)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["task_count"], 2)

    def test_prepare_handoff_syncs_index_tasks(self) -> None:
        """Regression: after handoff, index.json tasks[] entries must carry
        the same handoff fields as individual task files."""
        tasks_dir = self.run_dir / "generation_tasks"
        write_json(tasks_dir / "index.json", {
            "run_id": "gen-test",
            "tasks": [
                {"task_id": "generation_001_beat_001", "beat_id": "beat_001",
                 "status": "pending"},
                {"task_id": "generation_002_beat_004", "beat_id": "beat_004",
                 "status": "pending"},
            ],
        })
        prepare_generation_handoff(self.run_dir)
        # Read updated index and verify tasks are enhanced.
        index = read_json(tasks_dir / "index.json")
        for task in index["tasks"]:
            self.assertEqual(task["schema_version"], "deck_generation_task.v1")
            self.assertIn("workspace_refs", task)
            self.assertIn("quality_requirements", task)


if __name__ == "__main__":
    unittest.main()
