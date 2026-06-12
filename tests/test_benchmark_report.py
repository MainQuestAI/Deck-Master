from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.case import load_benchmark_case  # noqa: E402
from benchmark.report import BenchmarkReportError, build_benchmark_report, write_benchmark_report  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402


def _case_payload() -> dict:
    return {
        "schema_version": "deck_benchmark_case.v1",
        "case_id": "retail_fixture",
        "case_name": "Retail fixture",
        "industry": "retail",
        "audience": "client",
        "target_pages": 3,
        "runs_dir": "benchmark_runs",
        "inputs": {
            "context_pack": "context_pack.json",
            "baseline_manual_hours": 12,
        },
        "workflow": {
            "planning_mode": "narrative_v2",
            "requires_external_quality_review": True,
        },
        "success_targets": {
            "context_to_preview_minutes": 45,
            "page_acceptance_rate_min": 0.5,
            "reuse_adapt_rate_min": 0.3,
            "p0_count_max": 0,
            "quality_gate_required": True,
        },
    }


class BenchmarkReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_bench_report_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.bench_dir = self.temp_dir / "benchmarks"
        self.case_dir = self.bench_dir / "cases" / "retail_fixture"
        self.case_dir.mkdir(parents=True)
        write_json(self.case_dir / "benchmark_case.json", _case_payload())
        write_json(self.case_dir / "context_pack.json", {"schema_version": "deck_context_pack.v1"})
        self.case = load_benchmark_case(self.case_dir / "benchmark_case.json", benchmark_dir=self.bench_dir)

        self.run_dir = create_run(self.temp_dir / "runs", {"project_name": "Retail fixture"}, run_id="retail-demo")
        write_json(self.run_dir / "preview_manifest.json", {
            "run_id": "retail-demo",
            "title": "Retail fixture",
            "pages": [
                {"page_id": "p1", "order": 1, "source_type": "generated", "preview_path": "links/p1.svg", "decision": "approved", "review_status": "approved"},
                {"page_id": "p2", "order": 2, "source_type": "generated", "preview_path": "links/p2.svg", "decision": "needs_review"},
            ],
        })
        write_json(self.run_dir / "sourcing_plan.json", {
            "run_id": "retail-demo",
            "decisions": [
                {"beat_id": "p1", "source_decision": "reuse"},
                {"beat_id": "p2", "source_decision": "generate"},
            ],
        })
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        write_json(quality_dir / "draft_gate.json", {
            "gate": "draft",
            "status": "pass",
            "blocks_delivery": False,
            "summary": {"p0_count": 0, "p1_count": 0, "p2_count": 1},
            "findings": [{"finding_id": "F-1", "severity": "P2", "message": "Needs clearer evidence."}],
        })
        write_json(self.run_dir / "claim_evidence_graph.json", {
            "run_id": "retail-demo",
            "claims": [],
            "evidence": [],
            "gaps": [{"claim_id": "c1"}],
        })
        uat_dir = self.run_dir / "uat_reports"
        uat_dir.mkdir(exist_ok=True)
        write_json(uat_dir / "ppt_library_uat.json", {
            "schema_version": "deck_uat_report.v1",
            "status": "pass",
        })
        write_json(self.run_dir / "run_metrics.json", {
            "schema_version": "deck_run_metrics.v1",
            "run_id": "retail-demo",
            "created_at": "2026-06-12T00:00:00+00:00",
            "durations": {"created_to_preview_minutes": 30},
            "counts": {
                "pages": 2,
                "approved": 1,
                "rejected": 0,
                "needs_review": 1,
                "reuse": 1,
                "adapt": 0,
                "generate": 1,
                "manual_placeholder": 0,
                "p0": 0,
                "p1": 0,
                "p2": 1,
            },
        })

    def test_build_benchmark_report_includes_metrics_and_uat(self) -> None:
        report = build_benchmark_report(self.case, self.run_dir)

        self.assertEqual("deck_benchmark_report.v1", report["schema_version"])
        self.assertEqual("retail_fixture", report["case_id"])
        self.assertEqual(2, report["page_metrics"]["pages"])
        self.assertEqual(0.5, report["page_metrics"]["page_acceptance_rate"])
        self.assertEqual("pass", report["uat_summary"]["ppt_library"])
        self.assertEqual(1, report["quality_metrics"]["evidence_gap_count"])
        self.assertIn("artifact_index", report)
        self.assertIn("target_evaluation", report)

    def test_write_benchmark_report_outputs_json_markdown_and_protects_existing(self) -> None:
        written = write_benchmark_report(self.case, self.run_dir, benchmark_dir=self.bench_dir)

        report_path = Path(written["report"])
        markdown_path = Path(written["markdown"])
        self.assertTrue(report_path.exists())
        self.assertTrue(markdown_path.exists())
        self.assertTrue((Path(written["result_dir"]) / "uat_summary.json").exists())
        self.assertIn("Benchmark Report", markdown_path.read_text(encoding="utf-8"))

        with self.assertRaises(BenchmarkReportError):
            write_benchmark_report(self.case, self.run_dir, benchmark_dir=self.bench_dir)


if __name__ == "__main__":
    unittest.main()

