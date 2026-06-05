from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "orchestrate"))
sys.path.insert(0, str(ROOT / "scripts" / "preview"))

from build_run import build_run
from export_queue import export_queue
from manifest import load_manifest


PLAN = ROOT / "examples" / "orchestration-plan" / "deck_plan.json"


class OrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_build_run_creates_preview_manifest_and_links(self) -> None:
        run_dir = self.temp_dir / "run"
        manifest = build_run(PLAN, run_dir, force=True)

        self.assertEqual("sample-orchestrated-run", manifest["run_id"])
        self.assertEqual(3, len(manifest["pages"]))
        self.assertTrue((run_dir / "preview_manifest.json").exists())
        self.assertTrue((run_dir / "links" / "opening_problem.svg").exists())
        self.assertTrue((run_dir / "links" / "opening_problem.svg").is_symlink())

        loaded = load_manifest(run_dir)
        self.assertEqual("approved", loaded["pages"][0]["decision"])
        self.assertEqual("links/opening_problem.svg", loaded["pages"][0]["preview_path"])

    def test_export_queue_filters_by_decision(self) -> None:
        run_dir = self.temp_dir / "run"
        build_run(PLAN, run_dir, force=True)
        queue = export_queue(run_dir, {"approved"})

        self.assertEqual("sample-orchestrated-run", queue["run_id"])
        self.assertEqual(1, len(queue["pages"]))
        self.assertEqual("opening_problem", queue["pages"][0]["page_id"])

    def test_export_queue_rejects_invalid_decision(self) -> None:
        run_dir = self.temp_dir / "run"
        build_run(PLAN, run_dir, force=True)
        with self.assertRaises(ValueError):
            export_queue(run_dir, {"accepted"})


if __name__ == "__main__":
    unittest.main()
