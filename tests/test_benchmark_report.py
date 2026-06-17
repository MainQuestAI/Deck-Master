from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.case import load_benchmark_case  # noqa: E402
from benchmark.report import BenchmarkReportError, build_benchmark_report, write_benchmark_report  # noqa: E402
from deck_master import command_benchmark_report, command_benchmark_rc_report  # noqa: E402
from runtime.render import CANONICAL_RENDER_RESULT  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402
from workspace.foundation import init_workspace  # noqa: E402


def _case_payload(case_id: str = "retail_fixture", workflow_library_mode: str | None = None) -> dict:
    case_payload = {
        "schema_version": "deck_benchmark_case.v1",
        "case_id": case_id,
        "case_name": f"Retail fixture {case_id}",
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
            "context_to_review_ready_minutes": 90,
            "context_to_approved_queue_minutes": 120,
            "page_acceptance_rate_min": 0.5,
            "reuse_adapt_rate_min": 0.3,
            "p0_count_max": 0,
            "quality_gate_required": True,
        },
    }
    if workflow_library_mode is not None:
        case_payload["workflow"]["library_mode"] = workflow_library_mode
    return case_payload


def _run_ready_payload(run_id: str, run_mode: str) -> dict:
    return {
        "run_id": run_id,
        "project_name": "Retail fixture",
        "run_mode": run_mode,
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

        self.rc_case_dir = self.bench_dir / "cases" / "retail_benchmark"
        self.rc_case_dir.mkdir(parents=True)
        write_json(self.rc_case_dir / "benchmark_case.json", _case_payload("retail_benchmark"))
        write_json(self.rc_case_dir / "context_pack.json", {"schema_version": "deck_context_pack.v1"})
        self.rc_case = load_benchmark_case(
            self.rc_case_dir / "benchmark_case.json",
            benchmark_dir=self.bench_dir,
        )

        self.fixture_case_dir = self.bench_dir / "cases" / "fixture_example"
        self.fixture_case_dir.mkdir(parents=True)
        write_json(self.fixture_case_dir / "benchmark_case.json", _case_payload("fixture_example", workflow_library_mode="fixture"))
        write_json(self.fixture_case_dir / "context_pack.json", {"schema_version": "deck_context_pack.v1"})
        self.fixture_case = load_benchmark_case(
            self.fixture_case_dir / "benchmark_case.json",
            benchmark_dir=self.bench_dir,
        )

        self.run_dir = create_run(self.temp_dir / "runs", {"project_name": "Retail fixture"}, run_id="retail-demo")
        self.workspace_dir = self.temp_dir / "workspace"
        init_workspace(self.workspace_dir, name="benchmark-docs-workspace")
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

    def test_checkpoint_metrics_drive_context_targets(self) -> None:
        write_json(self.run_dir / "benchmark_checkpoints.json", {
            "schema_version": "deck_benchmark_checkpoints.v1",
            "run_id": "retail-demo",
            "updated_at": "2026-06-12T12:00:00+00:00",
            "checkpoints": {
                "context_ready": {"timestamp": "2026-06-12T10:00:00+00:00", "note": ""},
                "preview_ready": {"timestamp": "2026-06-12T10:30:00+00:00", "note": ""},
                "human_review_started": {"timestamp": "2026-06-12T11:00:00+00:00", "note": ""},
                "human_review_completed": {"timestamp": "2026-06-12T11:20:00+00:00", "note": ""},
                "approved_queue_ready": {"timestamp": "2026-06-12T11:40:00+00:00", "note": ""},
            },
        })

        report = build_benchmark_report(self.case, self.run_dir)

        self.assertEqual(30, report["efficiency_metrics"]["context_to_preview_minutes"])
        self.assertEqual(60, report["efficiency_metrics"]["context_to_review_ready_minutes"])
        self.assertEqual(100, report["efficiency_metrics"]["context_to_approved_queue_minutes"])
        self.assertEqual(20, report["efficiency_metrics"]["human_review_minutes"])
        self.assertEqual("pass", report["target_evaluation"]["context_to_approved_queue"])

    def test_missing_approved_queue_checkpoint_is_pending_not_fail(self) -> None:
        write_json(self.run_dir / "benchmark_checkpoints.json", {
            "schema_version": "deck_benchmark_checkpoints.v1",
            "run_id": "retail-demo",
            "updated_at": "2026-06-12T12:00:00+00:00",
            "checkpoints": {
                "context_ready": {"timestamp": "2026-06-12T10:00:00+00:00", "note": ""},
                "preview_ready": {"timestamp": "2026-06-12T10:30:00+00:00", "note": ""},
            },
        })

        report = build_benchmark_report(self.case, self.run_dir)

        self.assertIsNone(report["efficiency_metrics"]["context_to_approved_queue_minutes"])
        self.assertEqual("pending", report["target_evaluation"]["context_to_approved_queue"])

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

    def test_command_benchmark_report_recomputes_pending_for_existing_run(self) -> None:
        result = command_benchmark_report(Namespace(
            case=str(self.case_dir / "benchmark_case.json"),
            benchmark_dir=str(self.bench_dir),
            run_dir=str(self.run_dir),
            run_id=None,
            runs_dir=str(self.temp_dir / "runs"),
            rc_readiness=False,
            force=True,
        ))

        report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
        self.assertEqual("pending_external_agent", report["status"])
        self.assertEqual(["external_quality_review"], [item["step"] for item in report["pending_external_steps"]])

    def _ready_benchmark_run(self, case, run_mode: str) -> Path:
        run_dir = create_run(
            self.temp_dir / "runs",
            {
                **_run_ready_payload(f"{case.data['case_id']}-ready", run_mode),
                "workspace": str(self.workspace_dir),
            },
            run_id=f"{case.data['case_id']}-ready",
            force=True,
        )
        write_json(run_dir / "context_manifest.json", {"run_id": run_dir.name})
        write_json(run_dir / "deck_brief.json", {"run_id": run_dir.name})
        write_json(run_dir / "claim_map.json", {"run_id": run_dir.name, "claims": []})
        write_json(run_dir / "narrative_plan.json", {"run_id": run_dir.name, "beats": []})
        write_json(run_dir / "page_tasks.json", {"run_id": run_dir.name, "tasks": []})
        write_json(run_dir / "sourcing_plan.json", {"run_id": run_dir.name, "tasks": []})
        write_json(run_dir / "preview_manifest.json", {"run_id": run_dir.name, "pages": []})
        quality_dir = run_dir / "quality_reports"
        quality_dir.mkdir(parents=True, exist_ok=True)
        write_json(quality_dir / "draft_v2_gate.json", {"status": "pass", "blocks_delivery": False})
        return run_dir

    def test_benchmark_rc_report_requires_ready_for_benchmark(self) -> None:
        run_dir = self._ready_benchmark_run(self.rc_case, "benchmark")
        result = command_benchmark_rc_report(Namespace(
            case=str(self.rc_case_dir / "benchmark_case.json"),
            benchmark_dir=str(self.bench_dir),
            run_dir=str(run_dir),
            run_id=None,
            runs_dir=str(self.temp_dir / "runs"),
            force=True,
        ))
        report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
        self.assertEqual("benchmark_rc_report.json", Path(result["report"]).name)
        self.assertEqual(run_dir.name, report["run_id"])

    def test_benchmark_rc_report_blocks_missing_required_render_result(self) -> None:
        payload = _case_payload("retail_benchmark")
        payload["workflow"]["requires_render_result"] = True
        write_json(self.rc_case_dir / "benchmark_case.json", payload)
        run_dir = self._ready_benchmark_run(self.rc_case, "benchmark")
        with self.assertRaises(BenchmarkReportError):
            command_benchmark_rc_report(Namespace(
                case=str(self.rc_case_dir / "benchmark_case.json"),
                benchmark_dir=str(self.bench_dir),
                run_dir=str(run_dir),
                run_id=None,
                runs_dir=str(self.temp_dir / "runs"),
                force=True,
            ))

        render_path = run_dir / CANONICAL_RENDER_RESULT
        render_path.parent.mkdir(parents=True)
        write_json(
            render_path,
            {
                "schema_version": "deck_render_result.v1",
                "run_id": run_dir.name,
                "tool": "ppt-master",
                "status": "completed",
                "artifact_path": "rendered/index.html",
            },
        )
        result = command_benchmark_rc_report(Namespace(
            case=str(self.rc_case_dir / "benchmark_case.json"),
            benchmark_dir=str(self.bench_dir),
            run_dir=str(run_dir),
            run_id=None,
            runs_dir=str(self.temp_dir / "runs"),
            force=True,
        ))
        self.assertEqual("benchmark_rc_report.json", Path(result["report"]).name)

    def test_benchmark_rc_report_blocks_non_benchmark_run_mode(self) -> None:
        run_dir = self._ready_benchmark_run(self.rc_case, "production")
        with self.assertRaises(BenchmarkReportError):
            command_benchmark_rc_report(Namespace(
                case=str(self.rc_case_dir / "benchmark_case.json"),
                benchmark_dir=str(self.bench_dir),
                run_dir=str(run_dir),
                run_id=None,
                runs_dir=str(self.temp_dir / "runs"),
                force=True,
            ))

    def test_benchmark_rc_report_blocks_fixture_benchmark(self) -> None:
        run_dir = self._ready_benchmark_run(self.fixture_case, "fixture")
        with self.assertRaises(BenchmarkReportError):
            command_benchmark_rc_report(Namespace(
                case=str(self.fixture_case_dir / "benchmark_case.json"),
                benchmark_dir=str(self.bench_dir),
                run_dir=str(run_dir),
                run_id=None,
                runs_dir=str(self.temp_dir / "runs"),
                force=True,
            ))


if __name__ == "__main__":
    unittest.main()
