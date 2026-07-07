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
CLI = [sys.executable, str(ROOT / "scripts" / "deck_master.py")]


class AgentReadyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_agent_ready_"))
        self.home = self.temp_dir / "home"
        self.home.mkdir()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "HOME": str(self.home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DECK_MASTER_PPT_MASTER_BACKEND": "",
            "DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE": "",
        }
        completed = subprocess.run(
            [*CLI, *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        if check:
            self.assertEqual(0, completed.returncode, completed.stderr)
        return completed

    def write_demo_run(self, page_count: int = 10) -> Path:
        run_dir = self.temp_dir / "runs" / "oss-demo"
        run_dir.mkdir(parents=True)
        for name in ("request.json", "narrative_plan.json", "page_tasks.json", "sourcing_plan.json"):
            (run_dir / name).write_text(
                json.dumps({"run_id": "oss-demo", "run_mode": "fixture"}),
                encoding="utf-8",
            )
        manifest = {
            "run_id": "oss-demo",
            "title": "Retail Transformation Demo",
            "status": "draft",
            "pages": [
                {
                    "page_id": f"page_{index:03d}",
                    "order": index,
                    "title": f"Demo Page {index}",
                    "source_type": "fixture",
                    "preview_path": f"links/page_{index:03d}.svg",
                    "decision": "needs_review",
                }
                for index in range(1, page_count + 1)
            ],
        }
        (run_dir / "preview_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return run_dir

    def test_agent_docs_define_first_read_order_and_routes(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Agent First Read Order", agents)
        self.assertIn("docs/agent-task-index.md", agents)
        self.assertIn("docs/agent-recovery-playbook.md", agents)
        self.assertIn("docs/contracts/", agents)
        self.assertIn("Forbidden Actions", agents)
        self.assertIn("Task Routing", agents)
        self.assertIn("agent-doctor --mode preview", agents)

    def test_task_index_and_recovery_playbook_cover_required_workflows(self) -> None:
        task_index = (ROOT / "docs" / "agent-task-index.md").read_text(encoding="utf-8")
        playbook = (ROOT / "docs" / "agent-recovery-playbook.md").read_text(encoding="utf-8")

        for required in [
            "New Public Preview Run",
            "Continue Existing Run",
            "Check Client Delivery",
            "Repair Blocked Run",
            "Build And Verify Release",
            "QA",
        ]:
            self.assertIn(required, task_index)
        for command in ["next-step", "suite-status", "preview-gate", "final-readiness", "release-smoke"]:
            self.assertIn(command, task_index)
        for required in [
            "Backend Missing",
            "Preview Missing",
            "Schema Mismatch",
            "Stale Generation Result",
            "P0 Quality Finding",
            "Final Readiness Blocked",
            "Release Smoke Failed",
        ]:
            self.assertIn(required, playbook)

    def test_agent_doctor_preview_is_ready_without_backend_binding(self) -> None:
        completed = self.run_cli("agent-doctor", "--mode", "preview", "--output", "json")
        payload = json.loads(completed.stdout)

        self.assertEqual("deck_master_agent_doctor.v1", payload["schema_version"])
        self.assertEqual("preview", payload["mode"])
        self.assertEqual("ready", payload["status"])
        self.assertTrue(payload["next_agent_action"])
        self.assertIn("evidence_paths", payload)
        checks = {item["check_id"]: item for item in payload["checks"]}
        self.assertEqual("warn", checks["production_backend_projection"]["status"])
        self.assertIn("fixture mode", checks["production_backend_projection"]["summary"])
        self.assertEqual(["ppt-master"], checks["production_backend_projection"]["details"]["missing_or_unready"])

    def test_agent_doctor_production_blocks_without_backend_binding(self) -> None:
        completed = self.run_cli("agent-doctor", "--mode", "production", "--output", "json")
        payload = json.loads(completed.stdout)

        self.assertEqual("production", payload["mode"])
        self.assertEqual("blocked", payload["status"])
        self.assertTrue(payload["next_agent_action"])
        self.assertTrue(payload["errors"])
        checks = {item["check_id"]: item for item in payload["checks"]}
        self.assertEqual("blocked", checks["production_backend"]["status"])
        self.assertEqual(["ppt-master"], checks["production_backend"]["details"]["missing_or_unready"])

    def test_key_blocked_outputs_include_next_agent_action(self) -> None:
        bad_run = self.write_demo_run(page_count=3)
        preview = self.run_cli(
            "preview-gate",
            "--run-dir",
            str(bad_run),
            "--expect-unconfigured-backend-ok",
            check=False,
        )
        self.assertEqual(2, preview.returncode, preview.stdout)
        preview_payload = json.loads(preview.stdout)
        self.assertEqual("fail", preview_payload["status"])
        self.assertTrue(preview_payload["next_agent_action"])
        self.assertTrue(preview_payload["evidence_paths"])

        final = self.run_cli(
            "final-readiness",
            "--run-dir",
            str(bad_run),
            "--no-write",
            "--run-mode",
            "fixture",
            "--dev-allow-unsetup",
        )
        final_payload = json.loads(final.stdout)
        self.assertEqual("blocked", final_payload["status"])
        self.assertTrue(final_payload["next_agent_action"])
        self.assertTrue(final_payload["evidence_paths"])

        suite = self.run_cli("suite-status", "--output", "json")
        suite_payload = json.loads(suite.stdout)
        self.assertIn(suite_payload["status"], {"blocked", "degraded_ready"})
        self.assertTrue(suite_payload["next_agent_action"])
        self.assertTrue(suite_payload["evidence_paths"])

    def test_next_step_output_includes_agent_contract(self) -> None:
        run_dir = self.write_demo_run()
        completed = self.run_cli(
            "next-step",
            "--run-dir",
            str(run_dir),
            "--run-mode",
            "fixture",
            "--dev-allow-unsetup",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual("deck_next_step.v1", payload["schema_version"])
        self.assertTrue(payload["next_agent_action"])
        self.assertTrue(payload["evidence_paths"])

    def test_release_tree_contains_agent_entry_docs_and_contracts(self) -> None:
        release_root = self.temp_dir / "release"
        build = self.run_cli("release-build", "--output", str(release_root), "--force")
        build_payload = json.loads(build.stdout)
        self.assertEqual("built", build_payload["status"])

        for relative in [
            "AGENTS.md",
            "docs/agent-task-index.md",
            "docs/agent-recovery-playbook.md",
            "contracts/setup-status.v2.schema.json",
            "contracts/workflow-state.v1.schema.json",
            "contracts/final-readiness.v1.schema.json",
            "contracts/rc-gate-report.v1.schema.json",
        ]:
            self.assertTrue((release_root / relative).exists(), relative)

        smoke = self.run_cli(
            "release-smoke",
            "--release-root",
            str(release_root),
            "--no-smoke",
            "--output",
            "json",
        )
        smoke_payload = json.loads(smoke.stdout)
        self.assertEqual("passed", smoke_payload["status"])
        self.assertTrue(smoke_payload["next_agent_action"])


if __name__ == "__main__":
    unittest.main()
