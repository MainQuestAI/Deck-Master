from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from tools.ppt_library_client import (
    PPTLibraryClientError,
    build_select_slides_command,
    import_library_selection,
    run_library_selection,
)
from runtime.import_log import read_import_log
from runtime.run_state import create_run, read_json


class PPTLibraryClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_builds_select_slides_command(self) -> None:
        command = build_select_slides_command(
            command="ppt-lib",
            plan_path=Path("narrative_plan.json"),
            brief="brief",
            output_path=Path("selection.json"),
        )
        self.assertIn("select-slides", command)
        self.assertIn("--ranking", command)
        self.assertIn("business", command)

    def test_fixture_selection_writes_by_beat_results(self) -> None:
        request = build_request(brief="零售方案，关注全渠道和库存可视化", industry="retail")
        plan = plan_narrative(request)
        plan_path = self.temp_dir / "narrative_plan.json"
        plan_path.write_text("{}", encoding="utf-8")

        results = run_library_selection(
            narrative_plan=plan,
            narrative_plan_path=plan_path,
            request=request,
            run_dir=self.temp_dir,
            mode="fixture",
        )

        self.assertEqual("fixture", results["source"])
        self.assertTrue((self.temp_dir / "library_results" / "selection.json").exists())
        self.assertIn(plan["beats"][0]["beat_id"], results["by_beat"])
        first_candidate = next(iter(results["by_beat"].values()))[0]
        self.assertEqual("fixture", first_candidate["candidate_origin"])

    def test_production_auto_blocks_fixture_fallback_by_default(self) -> None:
        request = build_request(brief="真实生产方案", industry="healthcare")
        request["run_mode"] = "production"
        plan = plan_narrative(request)
        plan_path = self.temp_dir / "narrative_plan.json"
        plan_path.write_text("{}", encoding="utf-8")

        with self.assertRaises(PPTLibraryClientError):
            run_library_selection(
                narrative_plan=plan,
                narrative_plan_path=plan_path,
                request=request,
                run_dir=self.temp_dir,
                mode="auto",
                command="missing-ppt-lib-command",
            )
        blocked = read_json(self.temp_dir / "external" / "ppt_library" / "library_results.v2.json")
        self.assertEqual("library_blocked", blocked["status"])

    def test_production_auto_blocks_explicit_fixture_fallback(self) -> None:
        request = build_request(brief="真实生产方案", industry="healthcare")
        request["run_mode"] = "production"
        plan = plan_narrative(request)
        plan_path = self.temp_dir / "narrative_plan.json"
        plan_path.write_text("{}", encoding="utf-8")

        with self.assertRaises(PPTLibraryClientError):
            run_library_selection(
                narrative_plan=plan,
                narrative_plan_path=plan_path,
                request=request,
                run_dir=self.temp_dir,
                mode="auto",
                command="missing-ppt-lib-command",
                allow_fixture_fallback=True,
            )

    def test_benchmark_blocks_fixture_library_mode(self) -> None:
        request = build_request(brief="真实 benchmark", industry="healthcare")
        request["run_mode"] = "benchmark"
        plan = plan_narrative(request)
        plan_path = self.temp_dir / "narrative_plan.json"
        plan_path.write_text("{}", encoding="utf-8")

        with self.assertRaises(PPTLibraryClientError):
            run_library_selection(
                narrative_plan=plan,
                narrative_plan_path=plan_path,
                request=request,
                run_dir=self.temp_dir,
                mode="fixture",
            )

    def test_import_library_selection_writes_canonical_and_legacy_results(self) -> None:
        run_dir = create_run(self.temp_dir / "runs", {"project_name": "Library", "run_id": "lib-run"}, force=True)
        selection_path = self.temp_dir / "selection.json"
        selection_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_master_ppt_library_selection.v1",
                    "run_id": "lib-run",
                    "source": "ppt-library",
                    "selections": [
                        {
                            "beat_id": "beat-001",
                            "page_task_id": "page-001",
                            "slot_id": "hero",
                            "query_trace_id": "query-001",
                            "role": "opener",
                            "candidates": [{"slide_id": "slide-001", "title": "客户首页", "score": 0.91}],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = import_library_selection(run_dir, selection_path)

        self.assertEqual("imported", result["status"])
        self.assertTrue((run_dir / "external" / "ppt_library" / "library_results.v2.json").exists())
        legacy = read_json(run_dir / "library_results" / "selection.json")
        self.assertEqual("imported", legacy["source"])
        self.assertRegex(legacy["selections"][0]["query_trace_id"], r"^[a-f0-9]{64}$")
        candidate = legacy["by_beat"]["beat-001"][0]
        self.assertEqual("page-001", candidate["page_task_id"])
        self.assertEqual("hero", candidate["slot_id"])
        self.assertEqual("query-001", candidate["query_trace_id"])
        self.assertEqual("ppt_library", candidate["candidate_origin"])
        logs = read_import_log(run_dir)
        self.assertEqual("ppt_library_selection", logs[-1]["import_type"])

    def test_bad_library_selection_does_not_overwrite_existing_results(self) -> None:
        run_dir = create_run(self.temp_dir / "runs", {"project_name": "Library", "run_id": "lib-run"}, force=True)
        good = self.temp_dir / "good_selection.json"
        good.write_text(
            json.dumps(
                {
                    "schema_version": "deck_master_ppt_library_selection.v1",
                    "run_id": "lib-run",
                    "by_beat": {"beat-001": [{"slide_id": "slide-001", "title": "A"}]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        import_library_selection(run_dir, good)
        before = (run_dir / "library_results" / "selection.json").read_text(encoding="utf-8")
        bad = self.temp_dir / "bad_selection.json"
        bad.write_text(json.dumps({"schema_version": "wrong", "run_id": "lib-run"}), encoding="utf-8")

        with self.assertRaises(PPTLibraryClientError):
            import_library_selection(run_dir, bad)

        after = (run_dir / "library_results" / "selection.json").read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual("rejected", read_import_log(run_dir)[-1]["status"])


if __name__ == "__main__":
    unittest.main()
