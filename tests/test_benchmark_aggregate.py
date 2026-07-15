from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.aggregate import build_benchmark_aggregate_report, write_benchmark_aggregate_report  # noqa: E402
from runtime.run_state import write_json  # noqa: E402


def _real_case(case_id: str, industry: str) -> dict:
    return {
        "schema_version": "deck_benchmark_case.v1",
        "case_id": case_id,
        "case_type": "real_metadata",
        "case_name": f"Real metadata {case_id}",
        "industry": industry,
        "audience": "client",
        "target_pages": 12,
        "workspace": f"~/deck-master-local-benchmarks/{case_id}/workspace",
        "runs_dir": "benchmark_runs",
        "inputs": {
            "context_pack": f"~/deck-master-local-benchmarks/{case_id}/context_pack.json",
            "baseline_manual_hours": 14,
        },
        "workflow": {
            "planning_mode": "narrative_v2",
            "library_mode": "production",
        },
        "source_material": {
            "classification": "private_local_reference",
            "raw_source_policy": "local_path_only",
            "local_source_paths": [f"~/deck-master-local-benchmarks/{case_id}/raw"],
            "excluded_from_repo": True,
        },
        "success_targets": {
            "context_to_preview_minutes": 45,
            "page_acceptance_rate_min": 0.5,
            "p0_count_max": 0,
        },
    }


def _write_report(
    report_dir: Path,
    *,
    case_id: str,
    run_id: str,
    name: str,
    score: float = 0.8,
    status: str = "completed",
    payload_case_id: str | None = None,
    payload_run_id: str | None = None,
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json(report_dir / name, {
        "schema_version": "deck_benchmark_report.v1",
        "case_id": payload_case_id or case_id,
        "run_id": payload_run_id or run_id,
        "status": status,
        "readiness": {"final_ready": True},
        "rc_eligibility": {"eligible": True, "checks": {"final_ready": True}},
        "score": {"overall": score},
        "page_metrics": {"page_acceptance_rate": 0.75},
        "efficiency_metrics": {"estimated_time_saved_hours": 9.5},
    })


class BenchmarkAggregateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_bench_aggregate_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.bench_dir = self.temp_dir / "benchmarks"
        for case_id, industry in [
            ("real_retail_growth", "retail"),
            ("real_manufacturing_geo", "manufacturing"),
            ("real_healthcare_enablement", "healthcare"),
        ]:
            case_dir = self.bench_dir / "cases" / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            write_json(case_dir / "benchmark_case.json", _real_case(case_id, industry))

    def test_single_benchmark_report_does_not_make_p4_report_ready(self) -> None:
        report_dir = self.bench_dir / "results" / "real_retail_growth" / "run-001"
        _write_report(report_dir, case_id="real_retail_growth", run_id="run-001", name="benchmark_report.json")

        report = build_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("deck_benchmark_aggregate_report.v1", report["schema_version"])
        self.assertEqual("metadata_ready", report["status"])
        self.assertEqual(3, report["case_counts"]["real_metadata"])
        self.assertEqual(1, report["report_counts"]["total"])
        self.assertEqual(0, report["report_counts"]["complete_real_case_pairs"])
        self.assertEqual(0.8, report["metrics"]["average_score_overall"])
        self.assertEqual(1, report["metrics"]["final_ready_count"])
        coverage = {
            item["case_id"]: item
            for item in report["report_coverage"]["cases"]
        }
        self.assertFalse(coverage["real_retail_growth"]["complete"])
        self.assertEqual(["benchmark_rc_report.json"], coverage["real_retail_growth"]["missing_report_types"])
        self.assertFalse(report["private_source_policy"]["raw_sources_committed"])

    def test_three_real_cases_with_benchmark_and_rc_reports_make_report_ready(self) -> None:
        for index, case_id in enumerate([
            "real_retail_growth",
            "real_manufacturing_geo",
            "real_healthcare_enablement",
        ], start=1):
            report_dir = self.bench_dir / "results" / case_id / f"run-00{index}"
            _write_report(report_dir, case_id=case_id, run_id=f"run-00{index}", name="benchmark_report.json")
            _write_report(report_dir, case_id=case_id, run_id=f"run-00{index}", name="benchmark_rc_report.json")

        report = build_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("report_ready", report["status"])
        self.assertEqual(6, report["report_counts"]["total"])
        self.assertEqual(3, report["report_counts"]["benchmark_report"])
        self.assertEqual(3, report["report_counts"]["benchmark_rc_report"])
        self.assertEqual(3, report["report_counts"]["complete_real_case_pairs"])
        self.assertEqual(3, report["report_coverage"]["complete_real_case_count"])
        self.assertTrue(all(item["complete"] for item in report["report_coverage"]["cases"]))

    def test_report_types_split_across_runs_do_not_complete_real_case_pair(self) -> None:
        for index, case_id in enumerate([
            "real_retail_growth",
            "real_manufacturing_geo",
            "real_healthcare_enablement",
        ], start=1):
            _write_report(
                self.bench_dir / "results" / case_id / f"run-00{index}-a",
                case_id=case_id,
                run_id=f"run-00{index}-a",
                name="benchmark_report.json",
            )
            _write_report(
                self.bench_dir / "results" / case_id / f"run-00{index}-b",
                case_id=case_id,
                run_id=f"run-00{index}-b",
                name="benchmark_rc_report.json",
            )

        report = build_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("metadata_ready", report["status"])
        self.assertEqual(0, report["report_counts"]["complete_real_case_pairs"])
        self.assertFalse(any(item["complete"] for item in report["report_coverage"]["cases"]))

    def test_pending_or_warning_reports_do_not_complete_real_case_pair(self) -> None:
        for index, case_id in enumerate([
            "real_retail_growth",
            "real_manufacturing_geo",
            "real_healthcare_enablement",
        ], start=1):
            report_dir = self.bench_dir / "results" / case_id / f"run-00{index}"
            _write_report(
                report_dir,
                case_id=case_id,
                run_id=f"run-00{index}",
                name="benchmark_report.json",
                status="pending_external_agent",
            )
            _write_report(
                report_dir,
                case_id=case_id,
                run_id=f"run-00{index}",
                name="benchmark_rc_report.json",
                status="warning",
            )

        report = build_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("metadata_ready", report["status"])
        self.assertEqual(0, report["report_counts"]["complete_real_case_pairs"])
        self.assertEqual(0, report["report_coverage"]["complete_real_case_count"])
        self.assertTrue(all(not item["runs"] for item in report["report_coverage"]["cases"]))

    def test_payload_case_or_run_mismatch_does_not_complete_real_case_pair(self) -> None:
        for index, case_id in enumerate([
            "real_retail_growth",
            "real_manufacturing_geo",
            "real_healthcare_enablement",
        ], start=1):
            run_id = f"run-00{index}"
            report_dir = self.bench_dir / "results" / case_id / run_id
            _write_report(
                report_dir,
                case_id=case_id,
                run_id=run_id,
                name="benchmark_report.json",
                payload_case_id=f"{case_id}_other",
            )
            _write_report(
                report_dir,
                case_id=case_id,
                run_id=run_id,
                name="benchmark_rc_report.json",
                payload_run_id=f"{run_id}-other",
            )

        report = build_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("metadata_ready", report["status"])
        self.assertEqual(0, report["report_counts"]["complete_real_case_pairs"])
        self.assertEqual(0, report["report_coverage"]["complete_real_case_count"])
        self.assertFalse(all(item["payload_matches_path"] for item in report["reports"]))

    def test_aggregate_report_is_blocked_until_three_real_cases_exist(self) -> None:
        shutil.rmtree(self.bench_dir / "cases" / "real_healthcare_enablement")

        report = build_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("blocked", report["status"])
        self.assertEqual(2, report["case_counts"]["real_metadata"])

    def test_write_aggregate_report_outputs_json_and_markdown(self) -> None:
        result = write_benchmark_aggregate_report(self.bench_dir)

        self.assertEqual("metadata_ready", result["status"])
        self.assertTrue(Path(result["report"]).exists())
        self.assertTrue(Path(result["markdown"]).exists())
        self.assertIn("Benchmark Aggregate Report", Path(result["markdown"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
