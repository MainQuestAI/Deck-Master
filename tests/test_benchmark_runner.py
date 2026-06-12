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

    def test_narrative_advice_missing_is_pending_external_agent(self) -> None:
        self.case.data["workflow"]["requires_external_quality_review"] = False
        self.case.data["workflow"]["requires_narrative_advice"] = True
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-narrative-missing")

        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual(["narrative_advice"], [item["step"] for item in pending])
        self.assertEqual("pending_external_agent", pending[0]["status"])
        self.assertTrue(pending[0]["path"].endswith("advisor_results/narrative_advice.json"))

    def test_narrative_advice_imported_requires_local_apply(self) -> None:
        self.case.data["workflow"]["requires_external_quality_review"] = False
        self.case.data["workflow"]["requires_narrative_advice"] = True
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-narrative-imported")
        advice_dir = run_dir / "advisor_results"
        advice_dir.mkdir()
        (advice_dir / "narrative_advice.json").write_text("{}", encoding="utf-8")

        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual(["narrative_advice"], [item["step"] for item in pending])
        self.assertEqual("pending_local_apply", pending[0]["status"])
        self.assertTrue(pending[0]["path"].endswith("quality_reports/external_narrative_gate.json"))

    def test_narrative_advice_gate_clears_pending(self) -> None:
        self.case.data["workflow"]["requires_external_quality_review"] = False
        self.case.data["workflow"]["requires_narrative_advice"] = True
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-narrative-complete")
        advice_dir = run_dir / "advisor_results"
        advice_dir.mkdir()
        (advice_dir / "narrative_advice.json").write_text("{}", encoding="utf-8")
        quality_dir = run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "external_narrative_gate.json").write_text("{}", encoding="utf-8")

        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual([], pending)


if __name__ == "__main__":
    unittest.main()
