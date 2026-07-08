from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EndToEndAutoplanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_fixture_autoplan_builds_preview_manifest(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deck_master.py"),
                "autoplan",
                "--brief-file",
                str(ROOT / "examples" / "briefs" / "retail_digital_transformation.txt"),
                "--industry",
                "retail",
                "--library-mode",
                "fixture",
                "--run-mode",
                "fixture",
                "--runs-dir",
                str(self.temp_dir),
                "--run-id",
                "e2e",
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
        manifest = json.loads((run_dir / "preview_manifest.json").read_text(encoding="utf-8"))
        sourcing = json.loads((run_dir / "sourcing_plan.json").read_text(encoding="utf-8"))
        page_tasks = json.loads((run_dir / "page_tasks.json").read_text(encoding="utf-8"))

        self.assertEqual("autoplan_preview_ready", payload["status"])
        self.assertGreaterEqual(len(manifest["pages"]), 10)
        self.assertIn("candidate_origin", manifest["pages"][0])
        self.assertIn("library_source", manifest["pages"][0])
        self.assertIn("planning", page_tasks["tasks"][0])
        source_decisions = {item["source_decision"] for item in sourcing["decisions"]}
        self.assertTrue({"reuse", "adapt", "generate"}.issubset(source_decisions))
        self.assertNotIn("manual_placeholder", source_decisions)


if __name__ == "__main__":
    unittest.main()
