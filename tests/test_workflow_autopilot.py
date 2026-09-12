from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from deck_master import command_workflow_autopilot  # noqa: E402
from runtime.run_state import (  # noqa: E402
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    REQUEST_NAME,
    SOURCING_PLAN_NAME,
)


class WorkflowAutopilotTest(unittest.TestCase):
    def test_autopilot_preserves_unresolved_research_diagnostics(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "run-1", "run_mode": "fixture"})
        task = {"kind": "resolve_research_gap", "research_status": "inconclusive",
                "research_gaps": [{"affected_refs": ["RG-02"], "questions": ["Which case supports this claim?"]}]}
        state = {"stage": "blocked_research_gap", "next_command": "",
                 "host_task": task, "blocking_issues": ["RG-02 remains unresolved"]}
        args = Namespace(run_dir=str(self.run_dir), run_id=None, runs_dir=None,
                         workspace="", run_mode="fixture", dev_allow_unsetup=True,
                         mode="quick", max_steps=2)
        with patch("deck_master.resolve_run_state", return_value=state), patch("deck_master._autopilot_action", return_value=("", None)) as action:
            result = command_workflow_autopilot(args)
        self.assertEqual(result["host_task"], task)
        self.assertEqual(result["blocking_issues"], state["blocking_issues"])
        self.assertEqual(result["steps"], [])
        self.assertEqual(result["next_command"], "")
        action.assert_called_once()
        self.assertEqual(json.loads((self.run_dir / "workflow_autopilot_report.json").read_text()), result)

    def setUp(self) -> None:
        self.tmp_root = Path(tempfile.mkdtemp(prefix="dm_autopilot_"))
        self.run_dir = self.tmp_root / "run-1"
        self.run_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _write_json(self, rel: str | Path, payload: dict) -> None:
        path = self.run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_needs_build_run(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "run-1", "project_name": "Autopilot", "run_mode": "fixture"})
        self._write_json(CONTEXT_MANIFEST_NAME, {"files": []})
        self._write_json(DECK_BRIEF_NAME, {"title": "Autopilot"})
        self._write_json(CLAIM_MAP_NAME, {"claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"beats": []})
        self._write_json(PAGE_TASKS_NAME, {"tasks": []})
        self._write_json(SOURCING_PLAN_NAME, {"decisions": []})
        self._write_json(PREVIEW_MANIFEST_NAME, {"pages": [{"page_id": "p1", "decision": "approved", "title": "Page 1"}]})
        self._write_json("generation_tasks/index.json", {"tasks": [{"id": "task-1"}]})
        self._write_json(
            "generation_session.json",
            {"run_id": "run-1", "status": "quality_required", "quality_required_at": "2026-06-22T10:00:00+00:00"},
        )
        self._write_json(
            "quality_reports/draft_gate.json",
            {"status": "pass", "blocks_delivery": False, "created_at": "2026-06-22T10:01:00+00:00", "findings": []},
        )

    def test_autopilot_advances_build_prepare(self) -> None:
        self._write_needs_build_run()
        args = Namespace(
            run_dir=str(self.run_dir),
            run_id=None,
            runs_dir=None,
            workspace="",
            run_mode="fixture",
            dev_allow_unsetup=True,
            mode="quick",
            max_steps=1,
        )

        result = command_workflow_autopilot(args)

        self.assertEqual("max_steps_reached", result["status"])
        self.assertEqual("build prepare", result["steps"][0]["action"])
        self.assertEqual("deck-builder", result["steps"][0]["recommended_skill"])
        self.assertTrue((self.run_dir / "build" / "build_manifest.json").exists())
        self.assertTrue((self.run_dir / "workflow_autopilot_report.json").exists())


if __name__ == "__main__":
    unittest.main()
