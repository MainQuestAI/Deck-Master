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
from benchmark.runner import collect_pending_external_steps, create_benchmark_run, summarize_and_write_metrics  # noqa: E402


class BenchmarkRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_bench_runner_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.bench_dir = self.temp_dir / "benchmarks"
        self.case_dir = self.bench_dir / "cases" / "retail_fixture"
        self.case_dir.mkdir(parents=True)
        (self.case_dir / "benchmark_case.json").write_text(json.dumps({
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
            "success_targets": {"context_to_preview_minutes": 45},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.case_dir / "context_pack.json").write_text(json.dumps({
            "schema_version": "deck_context_pack.v1",
            "run_id": "placeholder",
            "sources": [
                {
                    "source_id": "s1",
                    "source_type": "business_context",
                    "origin_type": "fixture",
                    "origin_path": "fixture",
                    "title": "Retail context",
                    "summary": "Inventory visibility context.",
                    "evidence_candidates": [],
                }
            ],
            "global_constraints": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.case = load_benchmark_case(self.case_dir / "benchmark_case.json", benchmark_dir=self.bench_dir)

    def test_create_benchmark_run_writes_run_artifacts(self) -> None:
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-retail-test")

        self.assertTrue((run_dir / "request.json").exists())
        self.assertTrue((run_dir / "context_manifest.json").exists())
        self.assertTrue((run_dir / "conversation_session.json").exists())
        self.assertTrue((run_dir / "benchmark_checkpoints.json").exists())

        metrics = summarize_and_write_metrics(run_dir)
        self.assertEqual("deck_run_metrics.v1", metrics["schema_version"])
        self.assertTrue((run_dir / "run_metrics.json").exists())

    def test_pending_external_steps_are_reported(self) -> None:
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-retail-pending")
        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual(["external_quality_review"], [item["step"] for item in pending])
        self.assertEqual("pending_external_agent", pending[0]["status"])


if __name__ == "__main__":
    unittest.main()

