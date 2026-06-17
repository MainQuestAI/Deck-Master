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

    def test_start_without_context_file_reports_setup_next_action(self) -> None:
        completed = self.run_cli("start")
        payload = json.loads(completed.stdout)

        self.assertEqual("deck_master_start.v1", payload["schema_version"])
        self.assertEqual("blocked", payload["status"])
        self.assertIn("suite", payload)
        self.assertIn("blocked_capabilities", payload)
        self.assertIn("first_action", payload)
        self.assertIn("deck-master setup", payload["next_command"])

    def test_setup_status_include_suite_is_non_mutating_without_setup(self) -> None:
        completed = self.run_cli("setup-status", "--include-suite", "--output", "json")
        payload = json.loads(completed.stdout)

        self.assertEqual("blocked", payload["status"])
        self.assertIn("suite", payload)
        self.assertFalse((self.home / ".deck-master").exists())

    def test_suite_status_is_non_mutating_without_setup(self) -> None:
        completed = self.run_cli("suite-status", "--output", "json")
        payload = json.loads(completed.stdout)

        self.assertIn(payload["status"], {"blocked", "degraded_ready"})
        self.assertFalse((self.home / ".deck-master").exists())

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

        start = self.run_cli("start", "--workspace", str(workspace))
        start_payload = json.loads(start.stdout)
        self.assertEqual("ready", start_payload["setup_status"]["status"])
        self.assertTrue(start_payload["production_ready"])
        self.assertFalse(start_payload["full_suite_ready"])
        self.assertTrue(start_payload["blocked_capabilities"])
        self.assertIn("suite-repair", start_payload["next_command"])

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
            "--run-mode",
            "fixture",
        )
        payload = json.loads(planned.stdout)
        request = json.loads((workspace / "runs" / "workspace-run" / "request.json").read_text(encoding="utf-8"))

        self.assertEqual(str((workspace / "runs" / "workspace-run").resolve()), payload["run_dir"])
        self.assertTrue((workspace / "runs" / "workspace-run" / "request.json").exists())
        self.assertEqual(str(workspace.resolve()), request["workspace"])
        self.assertEqual("workspace_workspace", request["workspace_id"])
        self.assertEqual("workspace_manifest.json", request["workspace_manifest_ref"])
        self.assertEqual("setup", request["workspace_resolved_from"])

    def test_existing_run_blocks_conflicting_cli_workspace(self) -> None:
        run_dir = self.temp_dir / "runs" / "conflict-run"
        run_dir.mkdir(parents=True)
        request_workspace = self.temp_dir / "request_workspace"
        cli_workspace = self.temp_dir / "cli_workspace"
        request_workspace.mkdir()
        cli_workspace.mkdir()
        (run_dir / "request.json").write_text(
            json.dumps(
                {
                    "run_id": "conflict-run",
                    "project_name": "Conflict Run",
                    "run_mode": "fixture",
                    "workspace": str(request_workspace.resolve()),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        completed = self.run_cli(
            "autoplan",
            "--run-dir",
            str(run_dir),
            "--workspace",
            str(cli_workspace),
            "--run-mode",
            "fixture",
            check=False,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("workspace", completed.stderr)


if __name__ == "__main__":
    unittest.main()
