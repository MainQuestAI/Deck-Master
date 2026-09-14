"""No-library is a normal creation path.

Creating a new deck without a PPT Library must work through the normal
entries: autoplan skips the search when no library is available, decide-
sourcing continues without library candidates, and an explicitly requested
real library keeps its real dependency failure.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deck_master import command_decide_sourcing  # noqa: E402
from planning.brief_intake import build_request  # noqa: E402
from planning.narrative_planner import plan_narrative  # noqa: E402
from tools.ppt_library_client import PPTLibraryClientError, run_library_selection  # noqa: E402
from runtime.run_state import create_run, read_json, write_json  # noqa: E402


class NoLibraryPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_autoplan_without_library_completes_and_records_skip(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deck_master.py"),
                "autoplan",
                "--brief-file",
                str(ROOT / "examples" / "briefs" / "retail_digital_transformation.txt"),
                "--industry",
                "retail",
                "--run-mode",
                "fixture",
                "--ppt-lib-command",
                "definitely-not-installed-ppt-lib",
                "--runs-dir",
                str(self.temp_dir),
                "--run-id",
                "nolib",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "DECK_MASTER_DEV_SKIP_SETUP": "1"},
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        run_dir = Path(payload["run_dir"])
        self.assertEqual("autoplan_preview_ready", payload["status"])
        self.assertFalse((run_dir / "library_results" / "selection.json").exists())
        events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("ppt_library.skipped_unavailable", events)
        self.assertIn("sourcing.library_results_absent", events)
        sourcing = read_json(run_dir / "sourcing_plan.json")
        decisions = {page["decision"] for page in sourcing["pages"]}
        self.assertEqual({"generate"}, decisions)
        manifest = read_json(run_dir / "preview_manifest.json")
        self.assertGreaterEqual(len(manifest["pages"]), 10)

    def test_decide_sourcing_tolerates_missing_selection(self) -> None:
        run_dir = create_run(
            self.temp_dir,
            {"run_id": "nolib-unit", "project_name": "No Lib", "business_goal": "goal"},
            run_id="nolib-unit",
        )
        request = build_request(brief="零售方案，关注全渠道和库存可视化", industry="retail")
        plan = plan_narrative(request)
        write_json(run_dir / "page_tasks.json", {"run_id": "nolib-unit", "tasks": []})
        # minimal page tasks come from the narrative plan
        from planning.page_tasks import build_page_tasks

        write_json(run_dir / "page_tasks.json", build_page_tasks(plan, {"run_id": "nolib-unit", "claims": []}))

        result = command_decide_sourcing(argparse.Namespace(run_dir=str(run_dir), run_id="nolib-unit"))

        self.assertEqual("nolib-unit", result["run_id"])
        sourcing = read_json(run_dir / "sourcing_plan.json")
        self.assertEqual("deck_sourcing_plan.v2", sourcing["schema_version"])
        self.assertTrue(sourcing["pages"])
        self.assertTrue(
            all("NO_CANDIDATE" in str(page.get("decision_reason") or "") or page["decision"] == "generate" for page in sourcing["pages"]),
            sourcing["pages"][:2],
        )
        events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("sourcing.library_results_absent", events)

    def test_explicit_real_library_failure_is_preserved(self) -> None:
        request = build_request(brief="零售方案，关注全渠道和库存可视化", industry="retail")
        plan = plan_narrative(request)
        plan_path = self.temp_dir / "narrative_plan.json"
        plan_path.write_text("{}", encoding="utf-8")

        with self.assertRaises(PPTLibraryClientError) as ctx:
            run_library_selection(
                narrative_plan=plan,
                narrative_plan_path=plan_path,
                request=request,
                run_dir=self.temp_dir,
                mode="real",
                command="definitely-not-installed-ppt-lib",
            )
        self.assertIn("PPT Library", str(ctx.exception))
        selection = read_json(self.temp_dir / "library_results" / "selection.json")
        self.assertEqual("library_blocked", selection.get("status"))


if __name__ == "__main__":
    unittest.main()
