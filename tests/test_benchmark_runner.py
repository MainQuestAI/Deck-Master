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
from benchmark.runner import (  # noqa: E402
    BenchmarkRunError,
    collect_pending_external_steps,
    create_benchmark_run,
    run_local_preview_pipeline,
    summarize_and_write_metrics,
)
from runtime.render import CANONICAL_RENDER_RESULT  # noqa: E402


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

    def _write_real_case(
        self,
        *,
        case_id: str,
        context_pack: Path,
        raw_source_dir: Path,
        workspace_dir: Path | None = None,
    ) -> Path:
        real_case_dir = self.bench_dir / "cases" / case_id
        real_case_dir.mkdir(parents=True, exist_ok=True)
        actual_workspace = workspace_dir or self.temp_dir / "private" / case_id / "workspace"
        (real_case_dir / "benchmark_case.json").write_text(json.dumps({
            "schema_version": "deck_benchmark_case.v1",
            "case_id": case_id,
            "case_type": "real_metadata",
            "case_name": f"Real case {case_id}",
            "industry": "retail",
            "audience": "client",
            "target_pages": 12,
            "workspace": str(actual_workspace),
            "runs_dir": "benchmark_runs",
            "inputs": {
                "context_pack": str(context_pack),
                "baseline_manual_hours": 14,
            },
            "workflow": {
                "planning_mode": "narrative_v2",
                "library_mode": "production",
            },
            "source_material": {
                "classification": "private_local_reference",
                "raw_source_policy": "local_path_only",
                "local_source_paths": [str(raw_source_dir)],
                "excluded_from_repo": True,
            },
            "success_targets": {"context_to_preview_minutes": 45},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return real_case_dir / "benchmark_case.json"

    def test_create_benchmark_run_writes_run_artifacts(self) -> None:
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-retail-test")

        self.assertTrue((run_dir / "request.json").exists())
        self.assertTrue((run_dir / "context_manifest.json").exists())
        self.assertTrue((run_dir / "conversation_session.json").exists())
        self.assertTrue((run_dir / "benchmark_checkpoints.json").exists())

        metrics = summarize_and_write_metrics(run_dir)
        self.assertEqual("deck_run_metrics.v1", metrics["schema_version"])
        self.assertTrue((run_dir / "run_metrics.json").exists())

    def test_real_case_missing_context_pack_fails_preflight(self) -> None:
        private_raw = self.temp_dir / "private" / "real_missing_context" / "raw"
        private_raw.mkdir(parents=True)
        case_path = self._write_real_case(
            case_id="real_missing_context",
            context_pack=self.temp_dir / "private" / "real_missing_context" / "context_pack.json",
            raw_source_dir=private_raw,
        )
        case = load_benchmark_case(case_path, benchmark_dir=self.bench_dir)

        with self.assertRaises(BenchmarkRunError) as ctx:
            create_benchmark_run(case, run_id="bench-real-missing-context")

        message = str(ctx.exception)
        self.assertIn("Benchmark real case input preflight failed", message)
        self.assertIn("inputs.context_pack does not exist", message)

    def test_real_case_missing_private_source_dir_fails_preflight(self) -> None:
        private_dir = self.temp_dir / "private" / "real_missing_raw"
        context_pack = private_dir / "context_pack.json"
        context_pack.parent.mkdir(parents=True)
        context_pack.write_text(json.dumps({
            "schema_version": "deck_context_pack.v1",
            "sources": [],
            "global_constraints": [],
        }), encoding="utf-8")
        case_path = self._write_real_case(
            case_id="real_missing_raw",
            context_pack=context_pack,
            raw_source_dir=private_dir / "raw",
        )
        case = load_benchmark_case(case_path, benchmark_dir=self.bench_dir)

        with self.assertRaises(BenchmarkRunError) as ctx:
            create_benchmark_run(case, run_id="bench-real-missing-raw")

        message = str(ctx.exception)
        self.assertIn("Benchmark real case input preflight failed", message)
        self.assertIn("source_material.local_source_paths[0] does not exist", message)

    def test_real_case_missing_workspace_fails_preflight(self) -> None:
        private_dir = self.temp_dir / "private" / "real_missing_workspace"
        context_pack = private_dir / "context_pack.json"
        raw_dir = private_dir / "raw"
        raw_dir.mkdir(parents=True)
        context_pack.write_text(json.dumps({
            "schema_version": "deck_context_pack.v1",
            "sources": [],
            "global_constraints": [],
        }), encoding="utf-8")
        case_path = self._write_real_case(
            case_id="real_missing_workspace",
            context_pack=context_pack,
            raw_source_dir=raw_dir,
            workspace_dir=private_dir / "workspace",
        )
        case = load_benchmark_case(case_path, benchmark_dir=self.bench_dir)

        with self.assertRaises(BenchmarkRunError) as ctx:
            create_benchmark_run(case, run_id="bench-real-missing-workspace")

        message = str(ctx.exception)
        self.assertIn("Benchmark real case input preflight failed", message)
        self.assertIn("workspace does not exist", message)

    def test_real_case_unwritable_workspace_fails_preflight(self) -> None:
        private_dir = self.temp_dir / "private" / "real_unwritable_workspace"
        workspace_dir = private_dir / "workspace"
        raw_dir = private_dir / "raw"
        context_pack = private_dir / "context_pack.json"
        workspace_dir.mkdir(parents=True)
        raw_dir.mkdir(parents=True)
        context_pack.write_text(json.dumps({
            "schema_version": "deck_context_pack.v1",
            "sources": [],
            "global_constraints": [],
        }), encoding="utf-8")
        workspace_dir.chmod(0o555)
        self.addCleanup(lambda: workspace_dir.chmod(0o755) if workspace_dir.exists() else None)
        case_path = self._write_real_case(
            case_id="real_unwritable_workspace",
            context_pack=context_pack,
            raw_source_dir=raw_dir,
            workspace_dir=workspace_dir,
        )
        case = load_benchmark_case(case_path, benchmark_dir=self.bench_dir)

        with self.assertRaises(BenchmarkRunError) as ctx:
            create_benchmark_run(case, run_id="bench-real-unwritable-workspace")

        message = str(ctx.exception)
        self.assertIn("Benchmark real case input preflight failed", message)
        self.assertIn("workspace is not writable", message)

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

    def test_narrative_gate_does_not_complete_external_quality_review(self) -> None:
        self.case.data["workflow"]["requires_external_quality_review"] = True
        self.case.data["workflow"]["requires_narrative_advice"] = True
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-narrative-not-quality")
        advice_dir = run_dir / "advisor_results"
        advice_dir.mkdir()
        (advice_dir / "narrative_advice.json").write_text("{}", encoding="utf-8")
        quality_dir = run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "external_narrative_gate.json").write_text("{}", encoding="utf-8")

        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual(["external_quality_review"], [item["step"] for item in pending])

    def test_external_quality_review_gate_clears_pending(self) -> None:
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-external-quality-complete")
        quality_dir = run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "external_semantic_codex_gate.json").write_text("{}", encoding="utf-8")

        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual([], pending)

    def test_render_result_pending_uses_canonical_path(self) -> None:
        self.case.data["workflow"]["requires_external_quality_review"] = False
        self.case.data["workflow"]["requires_render_result"] = True
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-render-pending")

        pending = collect_pending_external_steps(self.case, run_dir)

        self.assertEqual(["render_result"], [item["step"] for item in pending])
        self.assertTrue(pending[0]["path"].endswith(str(CANONICAL_RENDER_RESULT)))

    def test_failed_preview_pipeline_does_not_write_preview_ready(self) -> None:
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-preview-fails")

        def ok(_args):
            return {"status": "ok"}

        def fail(_args):
            raise RuntimeError("autoplan failed")

        steps = run_local_preview_pipeline(
            self.case,
            run_dir,
            command_funcs={
                "build_brief": ok,
                "build_claim_map": ok,
                "autoplan": fail,
                "quality_gate": ok,
            },
        )

        checkpoints = json.loads((run_dir / "benchmark_checkpoints.json").read_text(encoding="utf-8"))
        self.assertEqual("warning", steps[-1]["status"])
        self.assertNotIn("preview_ready", checkpoints["checkpoints"])

    def test_preview_pipeline_writes_preview_ready_when_manifest_exists(self) -> None:
        run_dir, _pack = create_benchmark_run(self.case, run_id="bench-preview-ready")

        def ok(_args):
            return {"status": "ok"}

        def write_preview(args):
            run_root = Path(args.run_dir)
            (run_root / "preview_manifest.json").write_text(json.dumps({
                "run_id": "bench-preview-ready",
                "title": "Preview Ready",
                "status": "ready",
                "pages": [
                    {
                        "page_id": "p1",
                        "order": 1,
                        "source_type": "generated",
                        "preview_path": "links/p1.svg",
                        "narrative_role": "opener",
                        "decision": "needs_review",
                    }
                ],
            }), encoding="utf-8")
            return {"status": "ok"}

        steps = run_local_preview_pipeline(
            self.case,
            run_dir,
            command_funcs={
                "build_brief": ok,
                "build_claim_map": ok,
                "autoplan": write_preview,
                "quality_gate": ok,
            },
        )

        checkpoints = json.loads((run_dir / "benchmark_checkpoints.json").read_text(encoding="utf-8"))
        self.assertTrue(all(item["status"] == "completed" for item in steps))
        self.assertIn("preview_ready", checkpoints["checkpoints"])


if __name__ == "__main__":
    unittest.main()
