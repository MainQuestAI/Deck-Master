from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConversationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def run_cli(self, *args: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deck_master.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        return json.loads(completed.stdout)

    def test_local_context_to_preview_and_draft_gate(self) -> None:
        context_file = ROOT / "examples" / "context" / "retail_meeting_transcript.txt"
        start = self.run_cli(
            "start-conversation",
            "--context-file",
            str(context_file),
            "--industry",
            "retail",
            "--runs-dir",
            str(self.temp_dir),
            "--run-id",
            "conversation-e2e",
        )
        run_dir = Path(start["run_dir"])

        self.run_cli("build-brief", "--run-dir", str(run_dir))
        self.run_cli("build-claim-map", "--run-dir", str(run_dir))
        preview = self.run_cli(
            "autoplan",
            "--run-dir",
            str(run_dir),
            "--library-mode",
            "fixture",
            "--planning-mode",
            "narrative_v2",
        )
        quality = self.run_cli("quality-gate", "--run-dir", str(run_dir), "draft")

        self.assertEqual("autoplan_preview_ready", preview["status"])
        self.assertTrue((run_dir / "context_manifest.json").exists())
        self.assertTrue((run_dir / "conversation_session.json").exists())
        self.assertTrue((run_dir / "deck_brief.json").exists())
        self.assertTrue((run_dir / "claim_map.json").exists())
        self.assertTrue((run_dir / "consulting_judgments.json").exists())
        self.assertTrue((run_dir / "claim_evidence_graph.json").exists())
        self.assertTrue((run_dir / "page_tasks.json").exists())
        self.assertTrue((run_dir / "preview_manifest.json").exists())
        self.assertTrue((run_dir / "quality_reports" / "draft_gate.json").exists())
        self.assertIn(quality["status"], {"pass", "conditional_pass", "rework_required"})

        page_tasks = json.loads((run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        narrative = json.loads((run_dir / "narrative_plan.json").read_text(encoding="utf-8"))
        first_task = page_tasks["tasks"][0]
        self.assertIn("planning", first_task)
        self.assertIn("retrieval", first_task)
        self.assertIn("sourcing", first_task)
        self.assertIn("generation", first_task)
        self.assertIn("decision_intent", first_task["planning"])
        self.assertIn("evidence_policy", first_task["planning"])
        self.assertIn(first_task["planning"]["core_claim"], narrative["beats"][0]["reuse_query"])


if __name__ == "__main__":
    unittest.main()
