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


class SetupInstallSuiteRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_setup_install_suite_"))
        self.home = self.temp_dir / "home"
        self.home.mkdir()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def run_cli(self, *args: str) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deck_master.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(self.home), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        return json.loads(completed.stdout)

    def test_setup_install_suite_preserves_existing_workspace_config(self) -> None:
        # Regression: setup --install-suite without --workspace cleared the
        # active workspace and left local production setup in needs_workspace.
        # Found by /qa on 2026-06-22.
        workspace = self.temp_dir / "workspace"
        runs_dir = workspace / "runs"
        self.run_cli(
            "setup",
            "--workspace",
            str(workspace),
            "--runs-dir",
            str(runs_dir),
            "--repair-workspace",
            "--target",
            "codex",
            "--review-cockpit-url",
            "http://127.0.0.1:5055",
        )

        payload = self.run_cli("setup", "--install-suite", "--target", "codex")
        config = payload["config"]

        self.assertEqual(str(workspace.resolve()), config["active_workspace"])
        self.assertEqual(str(runs_dir.resolve()), config["default_runs_dir"])
        self.assertEqual("http://127.0.0.1:5055", config["review_cockpit_url"])
        self.assertEqual("ready", payload["setup_status"]["status"])


if __name__ == "__main__":
    unittest.main()
