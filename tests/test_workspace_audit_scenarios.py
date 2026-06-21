from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "preview"))
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.run_state_resolver import resolve_run_state  # noqa: E402
from workspace_api import build_workspace_payload  # noqa: E402
from workspace_audit_scenarios import generate_workspace_audit_runs  # noqa: E402


class WorkspaceAuditScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.report = generate_workspace_audit_runs(self.temp_dir / "audit-runs")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generated_scenarios_cover_expected_workspace_stages(self) -> None:
        expected = {
            "run-init-wait-preview": ("needs_preview", "待准备"),
            "generation-running": ("generation_running", "生成中"),
            "needs-review": ("needs_review", "待审阅"),
            "needs-evidence": ("needs_review", "待补依据"),
            "pending-approval": ("ready_for_client_export", "待审批"),
            "export-ready": ("ready_for_client_export", "可交付"),
            "delivered-review": ("ready_for_client_export", "已交付"),
        }
        seen = {item["run_id"] for item in self.report["runs"]}
        self.assertEqual(set(expected), seen)

        for item in self.report["runs"]:
            run_dir = Path(item["run_dir"])
            run_state = resolve_run_state(run_dir)
            workspace = build_workspace_payload(run_dir)
            expected_runtime_stage, expected_workspace_stage = expected[item["run_id"]]
            self.assertEqual(expected_runtime_stage, run_state["stage"])
            self.assertEqual(expected_workspace_stage, workspace["stage"]["label"])
            if item["run_id"] in {"export-ready", "delivered-review"}:
                delivery_preview = (workspace["run_summary"] or {}).get("delivery_preview") or {}
                self.assertTrue(delivery_preview.get("artifact_ready"))
                self.assertEqual("ready", delivery_preview.get("status"))


if __name__ == "__main__":
    unittest.main()
