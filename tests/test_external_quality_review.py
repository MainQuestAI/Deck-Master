"""Tests for Package D — External Quality Review Contract."""

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

from scripts.quality.external_review import (
    RESULT_SCHEMA_VERSION,
    ExternalReviewError,
    import_external_review,
    prepare_quality_review,
    validate_external_review,
)
from scripts.runtime.run_state import create_run, read_json, write_json


def _setup_run(tmp: Path) -> Path:
    runs_dir = tmp / "runs"
    runs_dir.mkdir()
    run_dir = create_run(runs_dir, {"project_name": "ExtReview"}, run_id="ext-review")
    write_json(run_dir / "deck_brief.json", {"run_id": "ext-review", "objective": "Test"})
    write_json(run_dir / "page_tasks.json", {"tasks": [{"beat_id": "beat_001"}]})
    return run_dir


def _valid_review(**overrides) -> dict:
    base = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": "ext-review",
        "reviewer": "codex",
        "scope": "semantic",
        "created_at": "2026-06-12T00:00:00Z",
        "summary": {
            "status": "rework_required",
            "blocks_delivery": True,
            "p0_count": 0,
            "p1_count": 1,
            "p2_count": 2,
        },
        "findings": [
            {
                "finding_id": "ext_semantic_001",
                "severity": "P1",
                "page_id": "beat_001",
                "dimension": "claim_evidence_alignment",
                "message": "页面标题提出库存可视化价值，但正文没有履约效率证据。",
                "repair_instruction": "补充履约时效、缺货率指标。",
                "refs": ["page_tasks.json#beat_001"],
            },
            {
                "finding_id": "ext_semantic_002",
                "severity": "P2",
                "page_id": "beat_001",
                "dimension": "client_readability",
                "message": "页面标题过于内部视角。",
                "repair_instruction": "改为客户价值导向标题。",
                "refs": [],
            },
        ],
    }
    base.update(overrides)
    return base


class ExternalReviewValidationTest(unittest.TestCase):

    def test_valid_review(self) -> None:
        result = validate_external_review(_valid_review())
        self.assertTrue(result["valid"], result.get("errors"))

    def test_missing_schema_version(self) -> None:
        rev = _valid_review()
        del rev["schema_version"]
        result = validate_external_review(rev)
        self.assertFalse(result["valid"])

    def test_wrong_schema_version(self) -> None:
        result = validate_external_review(_valid_review(schema_version="wrong.v1"))
        self.assertFalse(result["valid"])

    def test_missing_reviewer(self) -> None:
        rev = _valid_review()
        del rev["reviewer"]
        result = validate_external_review(rev)
        self.assertFalse(result["valid"])

    def test_missing_scope(self) -> None:
        rev = _valid_review()
        del rev["scope"]
        result = validate_external_review(rev)
        self.assertFalse(result["valid"])

    def test_invalid_scope(self) -> None:
        result = validate_external_review(_valid_review(scope="nonsense"))
        self.assertFalse(result["valid"])

    def test_invalid_severity(self) -> None:
        rev = _valid_review()
        rev["findings"] = [
            {"finding_id": "f1", "severity": "P9", "message": "test"}
        ]
        result = validate_external_review(rev)
        self.assertFalse(result["valid"])

    def test_missing_finding_id(self) -> None:
        rev = _valid_review()
        rev["findings"] = [{"severity": "P1", "message": "test"}]
        result = validate_external_review(rev)
        self.assertFalse(result["valid"])

    def test_not_an_object(self) -> None:
        result = validate_external_review([])  # type: ignore[arg-type]
        self.assertFalse(result["valid"])


class ExternalReviewPrepareTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_ext_prep_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_prepare_semantic(self) -> None:
        result = prepare_quality_review(self.run_dir, scopes=["semantic"])
        self.assertEqual(result["scopes"], ["semantic"])
        task_path = self.run_dir / "quality_review_tasks" / "semantic_review_task.json"
        self.assertTrue(task_path.exists())

    def test_prepare_multiple_scopes(self) -> None:
        result = prepare_quality_review(self.run_dir, scopes=["semantic", "visual"])
        self.assertEqual(result["scopes"], ["semantic", "visual"])

    def test_prepare_invalid_scope_raises(self) -> None:
        with self.assertRaises(ExternalReviewError):
            prepare_quality_review(self.run_dir, scopes=["nonsense"])


class ExternalReviewImportTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_ext_import_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_valid_review(self) -> None:
        result = import_external_review(self.run_dir, _valid_review())
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["scope"], "semantic")
        self.assertEqual(result["reviewer"], "codex")
        self.assertEqual(result["p1_count"], 1)
        # Gate report should exist.
        gate_files = list((self.run_dir / "quality_reports").glob("external_semantic_codex_gate.json"))
        self.assertEqual(len(gate_files), 1)

    def test_import_invalid_raises(self) -> None:
        with self.assertRaises(ExternalReviewError):
            import_external_review(self.run_dir, {"schema_version": "wrong"})

    def test_p1_blocks_export_via_gate_report(self) -> None:
        import_external_review(self.run_dir, _valid_review())
        gate = read_json(self.run_dir / "quality_reports" / "external_semantic_codex_gate.json")
        p1_findings = [f for f in gate["findings"] if f["severity"] == "P1"]
        self.assertEqual(len(p1_findings), 1)

    def test_multiple_reviewers_coexist(self) -> None:
        import_external_review(self.run_dir, _valid_review(reviewer="codex"))
        import_external_review(
            self.run_dir,
            _valid_review(reviewer="claude-code", created_at="2026-06-12T01:00:00Z"),
        )
        quality_dir = self.run_dir / "quality_reports"
        codex = quality_dir / "external_semantic_codex_gate.json"
        claude = quality_dir / "external_semantic_claude_code_gate.json"
        self.assertTrue(codex.exists())
        self.assertTrue(claude.exists())

    def test_replace_without_flag_raises(self) -> None:
        import_external_review(self.run_dir, _valid_review())
        with self.assertRaises(ExternalReviewError) as ctx:
            import_external_review(self.run_dir, _valid_review())
        self.assertIn("--replace", str(ctx.exception))

    def test_replace_archives_old_report(self) -> None:
        import_external_review(self.run_dir, _valid_review())
        import_external_review(self.run_dir, _valid_review(), replace=True)
        archive_dir = self.run_dir / "quality_reports" / "archive"
        self.assertTrue(archive_dir.exists())
        archived = list(archive_dir.glob("*.json"))
        self.assertEqual(len(archived), 1)

    def test_event_written_after_import(self) -> None:
        from scripts.runtime.events import read_events
        import_external_review(self.run_dir, _valid_review())
        events = read_events(self.run_dir)
        ext_events = [e for e in events if e.get("step") == "external_quality_review.imported"]
        self.assertTrue(len(ext_events) >= 1)

    def test_bad_result_does_not_overwrite(self) -> None:
        import_external_review(self.run_dir, _valid_review())
        gate_before = read_json(self.run_dir / "quality_reports" / "external_semantic_codex_gate.json")
        with self.assertRaises(ExternalReviewError):
            import_external_review(self.run_dir, {"schema_version": "wrong"})
        gate_after = read_json(self.run_dir / "quality_reports" / "external_semantic_codex_gate.json")
        self.assertEqual(gate_before, gate_after)


if __name__ == "__main__":
    unittest.main()
