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


class SetupEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_setup_test_"))
        self.home = self.temp_dir / "home"
        self.home.mkdir()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deck_master.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(self.home)},
        )
        if check:
            self.assertEqual(0, completed.returncode, completed.stderr)
        return completed

    def _install_fake_skill(self) -> None:
        skill_dir = self.home / ".deck-master" / "current" / "skills" / "deck-master"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: deck-master\ndescription: Test Deck Master skill.\n---\n# Deck Master\n",
            encoding="utf-8",
        )
        codex_dir = self.home / ".codex" / "skills"
        codex_dir.mkdir(parents=True)
        (codex_dir / "deck-master").symlink_to(skill_dir)

    def test_real_run_blocks_before_setup(self) -> None:
        completed = self.run_cli(
            "plan",
            "--brief",
            "test brief",
            "--run-id",
            "blocked",
            "--runs-dir",
            str(self.temp_dir / "runs"),
            check=False,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("Deck Master setup is not ready", completed.stderr)
        self.assertIn("deck-master setup", completed.stderr)

    def test_setup_repair_workspace_and_status_ready(self) -> None:
        self._install_fake_skill()
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()

        setup = self.run_cli(
            "setup",
            "--workspace",
            str(workspace),
            "--repair-workspace",
            "--target",
            "codex",
        )
        setup_payload = json.loads(setup.stdout)
        self.assertEqual("setup_completed", setup_payload["status"])

        status = self.run_cli("setup-status")
        payload = json.loads(status.stdout)
        self.assertEqual("ready", payload["status"])
        self.assertEqual([], payload["missing_items"])
        self.assertEqual([], payload["repair_items"])
        self.assertEqual("http://127.0.0.1:5050", payload["config"]["review_cockpit_url"])
        self.assertTrue((workspace / "quality" / "delivery_checklist.md").exists())

    def test_setup_status_needs_repair_for_incomplete_workspace(self) -> None:
        self._install_fake_skill()
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        self.run_cli("setup", "--workspace", str(workspace), "--target", "codex")

        status = self.run_cli("setup-status")
        payload = json.loads(status.stdout)
        self.assertEqual("needs_repair", payload["status"])
        self.assertIn("quality/delivery_checklist.md", payload["repair_items"])

    def test_plan_defaults_to_active_workspace_runs_dir_after_setup(self) -> None:
        self._install_fake_skill()
        workspace = self.temp_dir / "workspace"
        self.run_cli(
            "setup",
            "--workspace",
            str(workspace),
            "--repair-workspace",
            "--target",
            "codex",
        )

        planned = self.run_cli(
            "plan",
            "--brief",
            "workspace default run",
            "--run-id",
            "workspace-run",
        )
        payload = json.loads(planned.stdout)

        self.assertEqual(str((workspace / "runs" / "workspace-run").resolve()), payload["run_dir"])
        self.assertTrue((workspace / "runs" / "workspace-run" / "request.json").exists())


if __name__ == "__main__":
    unittest.main()
