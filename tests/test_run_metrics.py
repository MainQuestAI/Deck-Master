"""Tests for Package I — Lightweight Metrics Hooks."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.metrics.run_metrics import summarize_run_metrics
from scripts.feedback.library_feedback import record_library_feedback
from scripts.runtime.import_log import append_import_log
from scripts.runtime.events import append_typed_event
from scripts.runtime.run_state import create_run, write_json


def _setup_run(tmp: Path) -> Path:
    runs_dir = tmp / "runs"
    runs_dir.mkdir()
    run_dir = create_run(runs_dir, {"project_name": "MetricsTest"}, run_id="metrics-test")
    write_json(run_dir / "page_tasks.json", {
        "tasks": [
            {"beat_id": "beat_001", "source_decision": "reuse",
             "planning": {"decision_intent": "reuse"}},
            {"beat_id": "beat_002", "source_decision": "generate",
             "planning": {"decision_intent": "generate"}},
            {"beat_id": "beat_003", "source_decision": "manual_placeholder",
             "planning": {"decision_intent": "manual_placeholder"}},
        ]
    })
    return run_dir


class MetricsMissingEventsTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_metrics_miss_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_missing_events_degrades_to_artifact_mtime(self) -> None:
        metrics = summarize_run_metrics(self.run_dir)
        self.assertEqual(metrics["schema_version"], "deck_run_metrics.v1")
        self.assertEqual(metrics["run_id"], "metrics-test")
        # Counts should still work from page_tasks.json.
        self.assertEqual(metrics["counts"]["pages"], 3)
        self.assertEqual(metrics["counts"]["reuse"], 1)
        self.assertEqual(metrics["counts"]["generate"], 1)
        self.assertEqual(metrics["counts"]["manual_placeholder"], 1)


class MetricsCompleteEventsTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_metrics_comp_")
        self.run_dir = _setup_run(Path(self._tmp))
        # Write some events.
        append_typed_event(
            self.run_dir, "step_completed", "preview.built",
            "Preview built.", run_id="metrics-test",
        )
        append_typed_event(
            self.run_dir, "step_completed", "quality_gate.draft",
            "Draft gate run.", run_id="metrics-test",
        )
        # Write quality reports.
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        write_json(quality_dir / "draft_gate.json", {
            "gate": "draft",
            "summary": {"p0_count": 0, "p1_count": 2, "p2_count": 5},
            "findings": [],
        })

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_metrics_from_events(self) -> None:
        metrics = summarize_run_metrics(self.run_dir)
        self.assertIn("durations", metrics)
        self.assertNotEqual(metrics["created_at"], "")

    def test_quality_counts(self) -> None:
        metrics = summarize_run_metrics(self.run_dir)
        self.assertEqual(metrics["counts"]["p1"], 2)
        self.assertEqual(metrics["counts"]["p2"], 5)
        self.assertEqual(metrics["counts"]["quality_findings"], 7)
        self.assertEqual(metrics["counts"]["blocking_quality_reports"], 1)

    def test_import_log_and_feedback_counts(self) -> None:
        append_import_log(
            self.run_dir,
            import_type="ppt_library_selection",
            source="ppt-library",
            status="imported",
            canonical_refs=["external/ppt_library/library_results.json"],
        )
        record_library_feedback(
            self.run_dir,
            run_id="metrics-test",
            page_task_id="page-001",
            beat_id="beat-001",
            candidate_id="slide-001",
            outcome="approved",
        )

        metrics = summarize_run_metrics(self.run_dir)

        self.assertEqual(2, metrics["counts"]["imports"])
        self.assertEqual(1, metrics["counts"]["pending_library_feedback"])
        self.assertEqual(1, metrics["library_feedback"]["pending"])


class MetricsPageCountsTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_metrics_pg_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_page_counts(self) -> None:
        metrics = summarize_run_metrics(self.run_dir)
        counts = metrics["counts"]
        self.assertEqual(counts["pages"], 3)
        self.assertEqual(counts["approved"], 0)
        self.assertEqual(counts["rejected"], 0)
        self.assertEqual(counts["needs_review"], 3)

    def test_page_and_source_counts_use_runtime_sources(self) -> None:
        write_json(self.run_dir / "preview_manifest.json", {
            "run_id": "metrics-test",
            "title": "MetricsTest",
            "status": "ready",
            "pages": [
                {"page_id": "beat_001", "order": 1, "source_type": "library_slide",
                 "preview_path": "links/beat_001.svg", "narrative_role": "test",
                 "decision": "approved", "review_status": "approved"},
                {"page_id": "beat_002", "order": 2, "source_type": "generated",
                 "preview_path": "links/beat_002.svg", "narrative_role": "test",
                 "decision": "rejected", "review_status": "rejected"},
                {"page_id": "beat_003", "order": 3, "source_type": "placeholder",
                 "preview_path": "links/beat_003.svg", "narrative_role": "test",
                 "decision": "needs_review"},
            ],
        })
        write_json(self.run_dir / "sourcing_plan.json", {
            "run_id": "metrics-test",
            "decisions": [
                {"beat_id": "beat_001", "source_decision": "adapt"},
                {"beat_id": "beat_002", "source_decision": "adapt"},
                {"beat_id": "beat_003", "source_decision": "generate"},
            ],
        })

        metrics = summarize_run_metrics(self.run_dir)
        counts = metrics["counts"]
        self.assertEqual(counts["approved"], 1)
        self.assertEqual(counts["rejected"], 1)
        self.assertEqual(counts["needs_review"], 1)
        self.assertEqual(counts["reuse"], 0)
        self.assertEqual(counts["adapt"], 2)
        self.assertEqual(counts["generate"], 1)

    def test_v2_sourcing_readiness_exposes_library_degradation_and_generate_gaps(self) -> None:
        write_json(self.run_dir / "sourcing_plan.json", {
            "schema_version": "deck_sourcing_plan.v2",
            "run_id": "metrics-test",
            "status": "draft",
            "source_fingerprint": "a" * 64,
            "created_at": "2026-07-10T00:00:00+00:00",
            "pages": [
                {"page_id": "beat_001", "page_task_id": "page_001", "decision": "reuse"},
                {"page_id": "beat_002", "page_task_id": "page_002", "decision": "adapt"},
                {"page_id": "beat_003", "page_task_id": "page_003", "decision": "generate"},
            ],
        })
        library_dir = self.run_dir / "library_results"
        library_dir.mkdir(exist_ok=True)
        write_json(library_dir / "selection.json", {
            "schema_version": "deck_master_ppt_library_selection.v2",
            "selections": [
                {
                    "beat_id": "beat_001",
                    "page_task_id": "page_001",
                    "retrieval_method": "role_selection",
                    "preview_status": "ready",
                    "preview_degraded": False,
                },
                {
                    "beat_id": "beat_002",
                    "page_task_id": "page_002",
                    "retrieval_method": "semantic_fallback",
                    "preview_status": "missing",
                    "preview_degraded": True,
                },
                {
                    "beat_id": "beat_003",
                    "page_task_id": "page_003",
                    "retrieval_method": "none",
                    "preview_status": "missing",
                    "preview_degraded": False,
                },
            ],
        })

        metrics = summarize_run_metrics(self.run_dir)

        self.assertEqual(1, metrics["sourcing_readiness"]["role_selection_count"])
        self.assertEqual(1, metrics["sourcing_readiness"]["semantic_fallback_count"])
        self.assertEqual(1, metrics["sourcing_readiness"]["preview_degradation_count"])
        self.assertEqual(1, metrics["sourcing_readiness"]["generate_gap_count"])
        self.assertEqual(1, metrics["counts"]["reuse"])
        self.assertEqual(1, metrics["counts"]["adapt"])
        self.assertEqual(1, metrics["counts"]["generate"])


if __name__ == "__main__":
    unittest.main()
